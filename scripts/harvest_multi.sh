#!/bin/zsh
# 批量采集职位池：遍历检索 URL，每个加载后提取列表卡片，追加到输出文件。
#
# 用法:
#   harvest_multi.sh <urls.txt> <out.txt>
#
# 说明:
# - 每个 URL 约 8.5s（open 7s + eval）。113 个 URL ≈ 16 分钟。
# - 必须用 run_in_background 跑，否则会随 Bash 调用结束被回收。
# - 结果行是列表 JSON，交给 scripts/filter_candidates.py 去重 + 过滤。

SDIR="${0:A:h}"          # 本脚本所在目录（技能 scripts/）
URLS=${1:?用法: harvest_multi.sh <urls.txt> <out.txt>}
OUT=${2:?用法: harvest_multi.sh <urls.txt> <out.txt>}

: > "$OUT"
i=0
while read -r u; do
  [ -z "$u" ] && continue
  i=$((i+1))
  "$SDIR/ab.sh" open "$u" >/dev/null 2>&1
  sleep 7
  "$SDIR/ab.sh" eval "$(cat "$SDIR/boss_extract.js")" >/dev/null 2>&1
  "$SDIR/ab.sh" eval '__bossExtractList()' 2>/dev/null | tail -1 >> "$OUT"
  echo "[$i] $(wc -c < "$OUT") bytes  ${u##*query=}"
done < "$URLS"
echo MULTI_DONE
