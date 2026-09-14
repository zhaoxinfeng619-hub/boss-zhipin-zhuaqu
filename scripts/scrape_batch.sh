#!/bin/zsh
# 批量采集职位详情：逐条打开详情页，注入提取脚本，每条输出一个 JSON。
#
# 用法:
#   scrape_batch.sh <urls.txt> <详情输出目录>
#
# 说明:
# - 实测约 9.5s/条（open 7s + eval + sleep 2），200 条 ≈ 32 分钟。
# - 必须用 run_in_background 跑，否则会随 Bash 调用结束被回收。
# - 结果目录交给 scripts/finalize_batch.py 合成。

SDIR="${0:A:h}"
URLS=${1:?用法: scrape_batch.sh <urls.txt> <outdir>}
DIR=${2:?用法: scrape_batch.sh <urls.txt> <outdir>}

mkdir -p "$DIR"
i=0
while read -r u; do
  [ -z "$u" ] && continue
  i=$((i+1))
  "$SDIR/ab.sh" open "$u" >/dev/null 2>&1
  sleep 5
  "$SDIR/ab.sh" eval "$(cat "$SDIR/boss_extract.js")" >/dev/null 2>&1
  "$SDIR/ab.sh" eval '__bossExtractDetail()' 2>/dev/null | tail -1 > "$DIR/$i.json"
  echo "[$i] $(wc -c < "$DIR/$i.json") bytes"
  sleep 2
done < "$URLS"
echo BATCH_DONE
