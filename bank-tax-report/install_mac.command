#!/bin/bash
# 「거래·세금계산서 조회.app」 설치 스크립트 (macOS)
# Finder 에서 더블클릭하거나, 터미널에서 bash install_mac.command
set -euo pipefail

APP_NAME="거래·세금계산서 조회"
SRC="$(cd "$(dirname "$0")" && pwd)"
SUPPORT="$HOME/Library/Application Support/BankTaxReport"
VENV="$SUPPORT/venv"
CODE="$SUPPORT/app"

echo "== $APP_NAME 설치 =="

# 1) Python 3.12 이상 + tkinter. 없으면 uv 로 이 앱 전용 파이썬을 받는다(관리자 암호 불필요)
#    (/usr/bin/python3 은 개발자 도구 설치 창을 띄울 수 있어 후보에서 뺀다)
PY=""
for candidate in \
  /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 \
  /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
  /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
  /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if [ -x "$candidate" ] &&
     "$candidate" -c 'import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1; then
    PY="$candidate"; break
  fi
done
if [ -z "$PY" ]; then
  echo "알맞은 Python 이 없어 앱 전용 Python 3.13 을 내려받습니다..."
  mkdir -p "$SUPPORT/bin"
  if [ ! -x "$SUPPORT/bin/uv" ]; then
    curl -LsSf https://astral.sh/uv/install.sh |
      env UV_INSTALL_DIR="$SUPPORT/bin" UV_NO_MODIFY_PATH=1 INSTALLER_NO_MODIFY_PATH=1 sh
  fi
  export UV_PYTHON_INSTALL_DIR="$SUPPORT/python"
  "$SUPPORT/bin/uv" python install 3.13
  PY="$("$SUPPORT/bin/uv" python find 3.13)"
  "$PY" -c 'import tkinter' || { echo "Python 화면 모듈(tkinter)을 불러오지 못했습니다."; exit 1; }
fi
echo "Python: $PY ($("$PY" --version))"

# 2) 가상환경 + 패키지
mkdir -p "$SUPPORT" "$CODE"
"$VENV/bin/python" -c 'import tkinter' >/dev/null 2>&1 || { rm -rf "$VENV"; "$PY" -m venv "$VENV"; }
"$VENV/bin/python" -m pip install --upgrade --quiet pip
"$VENV/bin/python" -m pip install --quiet -r "$SRC/requirements.txt"
cp "$SRC/report.py" "$SRC/app.py" "$CODE/"

# 3) .app 번들
DEST="/Applications"
[ -w "$DEST" ] || { DEST="$HOME/Applications"; mkdir -p "$DEST"; }
BUNDLE="$DEST/$APP_NAME.app"
rm -rf "$BUNDLE"
mkdir -p "$BUNDLE/Contents/MacOS" "$BUNDLE/Contents/Resources"

cat > "$BUNDLE/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>$APP_NAME</string>
  <key>CFBundleDisplayName</key><string>$APP_NAME</string>
  <key>CFBundleIdentifier</key><string>local.banktaxreport</string>
  <key>CFBundleExecutable</key><string>launcher</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST

cat > "$BUNDLE/Contents/MacOS/launcher" <<LAUNCH
#!/bin/bash
export LANG=ko_KR.UTF-8 LC_ALL=ko_KR.UTF-8 PYTHONIOENCODING=utf-8
export BTR_HOME="$SUPPORT"
exec "$VENV/bin/python" "$CODE/app.py" >> "$SUPPORT/app.log" 2>&1
LAUNCH
chmod +x "$BUNDLE/Contents/MacOS/launcher"
touch "$BUNDLE"

echo
echo "설치 완료: $BUNDLE"
echo "Launchpad 또는 응용 프로그램 폴더에서 「$APP_NAME」을 실행하세요."
open -R "$BUNDLE" || true
