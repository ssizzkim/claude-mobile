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
"$APP/venv/bin/python" -m pip install -q "openpyxl==3.1.5" "xlrd==2.0.2" pillow numpy "keyring==25.6.0" \
  "hometax @ https://github.com/hjsh200219/hometax/archive/15aa5d490398bfc42fd3ae3541e8f206ec443a9d.zip"

cp "$HERE/banksort.py" "$HERE/integrate.py" "$HERE/hometax_fetch.py" "$HERE/buttons.py" "$HERE/gmail_routine.py" "$HERE/daily_digest.py" "$HERE/tools_cli.py" "$HERE/icon.png" "$HERE"/tile_*.png "$APP/"
swiftc -O "$HERE/kakaoread.swift" -o "$APP/kakaoread"   # 카톡 화면 읽기 도구
osacompile -o "$SCRIPTS/banksort.scpt" "$HERE/banksort.applescript"
"$APP/venv/bin/python" "$HERE/build.py" "$APP/BankSort.bas" >/dev/null
echo "설치 완료: $APP"
echo "엑셀 연결: $SCRIPTS/banksort.scpt"
