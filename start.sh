#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT="${HALLOWEEN_OUTPUT:-HDMI-A-1}"
MODE="1280x400"

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
if [[ -z "${WAYLAND_DISPLAY:-}" && -S "$XDG_RUNTIME_DIR/wayland-0" ]]; then
  export WAYLAND_DISPLAY=wayland-0
fi

configure_output() {
  wlr-randr --output "$OUTPUT" --mode "$MODE" --pos 0,0 2>/dev/null || \
    wlr-randr --output "$OUTPUT" --custom-mode "${MODE}@60Hz" --pos 0,0 2>/dev/null
}

if [[ "${HALLOWEEN_SKIP_OUTPUT_SETUP:-0}" != "1" ]]; then
  ready=0
  for _ in {1..15}; do
    if configure_output; then
      ready=1
      break
    fi
    sleep 1
  done
  if [[ "$ready" != "1" ]]; then
    printf '无法将 %s 设置为 %s，请检查 HDMI0 连接。\n' "$OUTPUT" "$MODE" >&2
    exit 1
  fi
fi

platform=()
if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
  platform=(--ozone-platform=wayland)
fi

profile="${XDG_CONFIG_HOME:-$HOME/.config}/halloween-chromium"
mkdir -p "$profile/Default"
python3 -B - "$profile/Default/Preferences" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    preferences = json.loads(path.read_text(encoding='utf-8'))
except (FileNotFoundError, json.JSONDecodeError):
    preferences = {}
browser = preferences.setdefault('browser', {})
browser['check_default_browser'] = False
browser['enable_translate'] = False
intl = preferences.setdefault('intl', {})
intl['accept_languages'] = 'zh-CN,zh,en-US,en'
intl['selected_languages'] = 'zh-CN,zh,en-US,en'
preferences.setdefault('translate', {})['enabled'] = False
preferences['translate_allowed'] = False
preferences['translate_language_blocklist'] = ['zh-CN', 'zh']
path.write_text(json.dumps(preferences, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
PY

soundscape_pid=''
led_pid=''
cleanup() {
  if [[ -n "$led_pid" ]]; then
    kill "$led_pid" 2>/dev/null || true
    wait "$led_pid" 2>/dev/null || true
  fi
  if [[ -n "$soundscape_pid" ]]; then
    kill "$soundscape_pid" 2>/dev/null || true
    wait "$soundscape_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

if [[ "${HALLOWEEN_MUTE:-0}" != "1" ]]; then
  python3 -B "$ROOT/soundscape.py" --volume "${HALLOWEEN_VOLUME:-0.10}" &
  soundscape_pid=$!
fi

if [[ "${HALLOWEEN_LED:-1}" != "0" && -e /dev/spidev0.0 ]]; then
  python3 -B "$ROOT/led_strip.py" --brightness "${HALLOWEEN_LED_BRIGHTNESS:-1.0}" &
  led_pid=$!
fi

chromium \
  "${platform[@]}" \
  --user-data-dir="$profile" \
  --kiosk \
  --window-size=1280,400 \
  --window-position=0,0 \
  --force-device-scale-factor=1 \
  --no-first-run \
  --no-default-browser-check \
  --disable-session-crashed-bubble \
  --disable-infobars \
  --disable-background-networking \
  --disable-component-update \
  --disable-features=Translate,TranslateUI \
  --disable-translate \
  --password-store=basic \
  "file://$ROOT/index.html"
