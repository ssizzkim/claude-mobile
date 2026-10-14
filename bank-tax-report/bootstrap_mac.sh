#!/bin/bash
# 터미널 한 줄 설치:
#   curl -fsSL https://raw.githubusercontent.com/ssizzkim/claude-mobile/refs/heads/main/bank-tax-report/bootstrap_mac.sh | bash
# 최신 앱 파일을 내려받아 install_mac.command 를 실행한다. 필요한 Python·패키지도 함께 설치된다.
set -euo pipefail
REF="${BTR_REF:-main}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
echo "앱 파일 내려받는 중 ($REF)..."
curl -fsSL "https://github.com/ssizzkim/claude-mobile/archive/refs/heads/$REF.zip" -o "$WORK/src.zip"
unzip -q "$WORK/src.zip" -d "$WORK"
bash "$WORK"/claude-mobile-*/bank-tax-report/install_mac.command </dev/null
open -a "/Applications/거래·세금계산서 조회.app" 2>/dev/null ||
  open -a "$HOME/Applications/거래·세금계산서 조회.app" 2>/dev/null || true
