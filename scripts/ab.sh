#!/bin/zsh
# agent-browser 包装：固定 CDP 端口 + 会话名，并绕开沙箱代理。
#
# 用法:
#   ab.sh open <url>          # 在当前 tab 打开页面
#   ab.sh eval '<js>'         # 在页面上下文执行 JS
#   ab.sh screenshot <path>   # 截图
#
# 依赖：本机已用 launch_chrome.sh 起好 9222 端口的 Chrome。
# 不写死工作目录 —— 由调用方的 cwd 决定文件落点。

NODEBIN=($HOME/.workbuddy/binaries/node/versions/*/bin)
export PATH="${NODEBIN[1]}:$HOME/.workbuddy/binaries/node/workspace/node_modules/.bin:$PATH"

# 沙箱会注入 HTTP_PROXY=127.0.0.1:<port>，导致连不上 CDP 9222
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
export NO_PROXY="127.0.0.1,localhost"

exec agent-browser --cdp 9222 --session boss "$@"
