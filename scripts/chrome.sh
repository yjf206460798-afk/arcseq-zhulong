#!/bin/sh
# 云端容器以 root 运行，Chromium 需要 --no-sandbox。Anatomy 的截图脚本通过 CHROME_PATH 调用本包装。
BIN="${CHROMIUM_BIN:-$(ls -d /opt/pw-browsers/chromium-*/chrome-linux/chrome 2>/dev/null | head -1)}"
[ -z "$BIN" ] && BIN="$(command -v chromium || command -v chromium-browser || command -v google-chrome)"
[ -z "$BIN" ] && { echo "chrome.sh: 找不到 Chromium" >&2; exit 127; }
exec "$BIN" --no-sandbox "$@"
