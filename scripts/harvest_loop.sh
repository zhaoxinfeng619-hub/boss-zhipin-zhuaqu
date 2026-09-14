#!/bin/zsh
WORKDIR=${1:-$PWD}
cd "$WORKDIR"
OUT=/tmp/harvest_all.txt
: > $OUT
for k in 1 2 3 4 5 6 7 8; do
  ./ab.sh open "https://www.zhipin.com/web/geek/jobs?query=AI%E4%BA%A7%E5%93%81%E7%BB%8F%E7%90%86&city=101010100&_r=$k" >/dev/null 2>&1
  sleep 6
  ./ab.sh eval "$(cat /tmp/harvest.js)" 2>/dev/null | tail -1 >> $OUT
  echo "round $k bytes=$(wc -c < $OUT)"
done
echo DONE
