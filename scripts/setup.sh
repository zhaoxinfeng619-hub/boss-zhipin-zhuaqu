#!/bin/zsh
# 一次性环境准备：装 agent-browser + 下载它自带的 Chromium
# 只需跑一次；已装好会直接跳过。
set -e

WORK="$HOME/.workbuddy/binaries/node/workspace"
mkdir -p "$WORK"
cd "$WORK"

if [ ! -d node_modules/agent-browser ]; then
  echo "==> 安装 agent-browser"
  "$HOME"/.workbuddy/binaries/node/versions/*/bin/npm install agent-browser
else
  echo "==> agent-browser 已安装，跳过"
fi

# Chromium 下载走本机代理，否则 storage.googleapis.com 会超时
if [ ! -d "$HOME/.cache/agent-browser" ] && [ ! -d "$HOME/Library/Caches/agent-browser" ]; then
  echo "==> 下载 Chromium（走代理 127.0.0.1:7890）"
  export HTTPS_PROXY=http://127.0.0.1:7890 HTTP_PROXY=http://127.0.0.1:7890
  ./node_modules/.bin/agent-browser install
else
  echo "==> Chromium 已存在，跳过"
fi

echo "==> 完成。agent-browser 路径：$WORK/node_modules/.bin/agent-browser"
