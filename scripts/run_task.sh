#!/bin/zsh
# 一键跑完整采集流程：建池 → 过滤候选 → 采详情 → 合并导出。
#
# 用法（必须 run_in_background 跑，全程约 20~60 分钟）:
#   run_task.sh <工作目录> <城市码> <关键词,逗号分隔> <目标条数> <输出CSV>
#
# 例:
#   run_task.sh ~/boss-zhipin-work 101010100 "AI产品经理,AI产品,大模型产品经理" 200 ~/boss-zhipin-work/boss_AI产品经理_北京.csv
#
# 前置：
#   1) 已跑过 scripts/setup.sh
#   2) 已用 scripts/launch_chrome.sh 起了 9222 端口的 Chrome（后台）
#   3) 浏览器已登录 zhipin.com（未登录会拿不到数据，需要先扫码）
#
# 特点：--csv 既是已有数据来源也是输出目标，所以重复跑会自动累加、不丢历史。

set -e
ROOT=$1; CITY=$2; KWS=$3; TARGET=$4; OUT=$5
SDIR="${0:A:h}"

# 沙箱注入的代理会污染 Chrome（见 SKILL.md §1 第 4 条），全程清掉
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
export NO_PROXY="127.0.0.1,localhost"

if [ -z "$OUT" ]; then
  echo "用法: run_task.sh <工作目录> <城市码> <关键词,逗号分隔> <目标条数> <输出CSV>"
  exit 1
fi

mkdir -p "$ROOT"
cd "$ROOT"

STAMP=$(date +%m%d_%H%M)
URLS="/tmp/urls_$STAMP.txt"
HARV="/tmp/harvest_$STAMP.txt"
DET="/tmp/det_$STAMP"
SEEN="$ROOT/.seen_ids.txt"

echo "==================== [$STAMP] 任务开始 ===================="

# ---------- 1) 从已交付 CSV 导出链接黑名单（避免重复采集） ----------
if [ -f "$OUT" ]; then
  python3 - "$OUT" "$SEEN" <<'PY'
import csv, sys
src, dst = sys.argv[1], sys.argv[2]
ids = set()
for r in csv.DictReader(open(src, encoding='utf-8-sig')):
    u = (r.get('岗位链接') or '').strip()
    if u:
        ids.add(u.rsplit('/', 1)[-1].replace('.html', ''))
open(dst, 'w').write('\n'.join(sorted(ids)))
print(f'[1/5] 既有职位黑名单: {len(ids)} 条')
PY
else
  : > "$SEEN"
  echo "[1/5] 无既有 CSV，黑名单为空"
fi

# ---------- 2) 生成检索 URL（多关键词 × 筛选组合） ----------
python3 "$SDIR/build_urls.py" --city "$CITY" --kw "$KWS" --out "$URLS"

# ---------- 3) 采集职位池 ----------
echo "[3/5] 开始采集职位池（这一步最慢）"
"$SDIR/harvest_multi.sh" "$URLS" "$HARV"

# ---------- 4) 过滤候选 ----------
echo "[4/5] 过滤候选"
python3 "$SDIR/filter_candidates.py" "$HARV" --seen "$SEEN" --out-prefix "$STAMP"

CAND="/tmp/cand_$STAMP.txt"
NLIST="/tmp/list_$STAMP.json"
NCAND=$(grep -c . "$CAND" || true)
echo "[4/5] 候选 $NCAND 条"

# ---------- 5) 采详情 + 合成 ----------
if [ "$NCAND" -gt 0 ]; then
  echo "[5/5] 采集详情（约 $((NCAND * 95 / 600)) 分钟）"
  "$SDIR/scrape_batch.sh" "$CAND" "$DET"
  python3 "$SDIR/finalize_batch.py" --csv "$OUT" --list "$NLIST" --det "$DET" --target "$TARGET"
else
  echo "[5/5] 没有新候选，跳过详情采集"
fi

echo "==================== [$STAMP] 任务结束 ===================="
