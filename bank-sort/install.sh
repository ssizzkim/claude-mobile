#!/bin/bash
# 은행정리 설치/업데이트: 파이썬 환경, 엔진, 엑셀 연결 스크립트, VBA 모듈을 준비한다.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$HOME/Library/Application Support/BankSort"
SCRIPTS="$HOME/Library/Application Scripts/com.microsoft.Excel"
mkdir -p "$APP" "$SCRIPTS"

PY=""
for c in /Library/Frameworks/Python.framework/Versions/Current/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  if [ -x "$c" ]; then PY="$c"; break; fi
done
[ -n "$PY" ] || { echo "python3 를 찾지 못했습니다"; exit 1; }
if [ ! -x "$APP/venv/bin/python" ]; then
  "$PY" -m venv "$APP/venv"
fi
"$APP/venv/bin/python" -m pip install -q --upgrade pip >/dev/null
"$APP/venv/bin/python" -m pip install -q "openpyxl==3.1.5" "xlrd==2.0.2" pillow numpy \
  "hometax @ https://github.com/hjsh200219/hometax/archive/15aa5d490398bfc42fd3ae3541e8f206ec443a9d.zip"

cp "$HERE/banksort.py" "$HERE/integrate.py" "$HERE/hometax_fetch.py" "$HERE/buttons.py" "$HERE/gmail_routine.py" "$HERE/icon.png" "$HERE"/tile_*.png "$APP/"
osacompile -o "$SCRIPTS/banksort.scpt" "$HERE/banksort.applescript"
"$APP/venv/bin/python" "$HERE/build.py" "$APP/BankSort.bas" >/dev/null
# 「은행·홈택스」 버튼 앱
BUNDLE="/Applications/은행·홈택스.app"
mkdir -p "$BUNDLE/Contents/MacOS"
cat > "$BUNDLE/Contents/MacOS/run" <<RUN
#!/bin/bash
export LANG=ko_KR.UTF-8 LC_ALL=ko_KR.UTF-8 PYTHONIOENCODING=utf-8
cd "$APP"
exec "$APP/venv/bin/python" "$APP/buttons.py" >> "$APP/buttons.log" 2>&1
RUN
chmod +x "$BUNDLE/Contents/MacOS/run"
# 아이콘
ICONSET="$(mktemp -d)/AppIcon.iconset"; mkdir -p "$ICONSET" "$BUNDLE/Contents/Resources"
for s in 16 32 128 256 512; do
  sips -z $s $s "$HERE/icon.png" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  sips -z $((s*2)) $((s*2)) "$HERE/icon.png" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$BUNDLE/Contents/Resources/AppIcon.icns"
cat > "$BUNDLE/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>은행·홈택스</string>
<key>CFBundleDisplayName</key><string>은행·홈택스</string>
<key>CFBundleIdentifier</key><string>com.torque.bankbuttons</string>
<key>CFBundleExecutable</key><string>run</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleVersion</key><string>1</string>
<key>CFBundleIconFile</key><string>AppIcon</string>
</dict></plist>
PLIST
echo "설치 완료: $APP"
touch "$BUNDLE"   # Finder·Dock 아이콘 새로 읽게
echo "버튼 앱: $BUNDLE"
echo "엑셀 연결: $SCRIPTS/banksort.scpt"
