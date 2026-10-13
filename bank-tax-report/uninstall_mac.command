#!/bin/bash
# 「거래·세금계산서 조회.app」과 설정·가상환경을 지웁니다. 저장한 엑셀(문서 폴더)은 남깁니다.
APP_NAME="거래·세금계산서 조회"
rm -rf "/Applications/$APP_NAME.app" "$HOME/Applications/$APP_NAME.app" \
       "$HOME/Library/Application Support/BankTaxReport"
echo "삭제했습니다."
