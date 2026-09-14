#!/bin/zsh
# 起一个「指纹正常」的后台 Chrome（无窗口，不占用用户屏幕）
# 必须用 run_in_background 跑，否则命令一结束进程就被回收。
#
# 用法（在 Bash 工具里）:
#   ./launch_chrome.sh <工作目录>
#
# 关键点:
# - 用系统 Chrome + --headless=new，UA 是正常的桌面 Chrome，
#   navigator.webdriver=false，BOSS 不会识别成机器人。
# - 千万不要用 agent-browser 自带的 daemon：它跑的是 HeadlessChrome。
# - 带 --no-sandbox，否则沙箱里 Chrome 起不来（macOS）。
# - 用户数据目录固定，登录态可复用，不用每次扫码。
#
# ⚠️ 启动前必须清理残留的 SingletonLock：
#   Chrome 上次没退干净时，锁文件里的 `<hostname>-<pid>` 与当前环境不匹配，
#   Chrome 会判定「profile 正被其他计算机的进程使用」并以**降级模式**启动 ——
#   表现是 CDP 9222 能连上、`open` 也报成功，但新标签页立即消失、
#   后续 eval 永远只能读到 about:blank。清掉锁再启动即可恢复正常。

DIR=${1:-$PWD}
PROFILE="$DIR/.chrome-profile"
PORT=9222

mkdir -p "$PROFILE"

# 沙箱代理会挡住 127.0.0.1，探测端口前先清掉
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
export NO_PROXY="127.0.0.1,localhost"

# 9222 没被占用却留着锁 → 说明是上次的残留，清掉
if ! curl -s --noproxy '*' -m 2 "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1; then
  rm -f "$PROFILE/SingletonLock" "$PROFILE/SingletonCookie" "$PROFILE/SingletonSocket"
  echo "==> 已清理 profile 残留锁"
fi

exec "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new \
  --remote-debugging-port=$PORT \
  --user-data-dir="$PROFILE" \
  --user-agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36" \
  --no-first-run --no-default-browser-check --no-sandbox --disable-gpu \
  --window-size=1440,1000 "about:blank"
