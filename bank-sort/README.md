# 은행정리 (bank-sort)

수동으로 받은 신한은행 「거래내역조회」·「이체결과조회」, 홈택스 전자세금계산서 매출·매입 목록 엑셀을
`~/Desktop/은행` 폴더의 통합 파일에 더하고 「은행내역 통합 2024-2026.xlsx」를 다시 만든다.

- 엑셀 버튼: `~/Desktop/은행/은행정리.xlsm` → [은행정리 실행] → 파일 선택
- 연결: `~/Library/Application Scripts/com.microsoft.Excel/banksort.scpt` (AppleScriptTask)
- 엔진: `~/Library/Application Support/BankSort/` (venv, banksort.py, integrate.py)

## 파일
- `banksort.py` 파일 판별·중복 제거·추가분 저장·계산서 통합 파일 갱신·손편집 보존·「이번 정리」·「현장별 합계」(통합내역 현장 열 → 수식 합계)
- `integrate.py` 분류·매칭 규칙 (원래 「은행내역 통합_스크립트.py」 2026-09-18, 파일 읽기/저장만 분리)
- `BankSort.bas.in` → `build.py` → `BankSort.bas` (한글은 U("코드") 로 바꿔 ASCII 로)
- `banksort.applescript` 엑셀 ↔ 파이썬 연결
- `은행정리.xlsm` 버튼 파일 원본

## 설치/업데이트
```bash
bash bank-sort/install.sh
```
VBA 를 바꿨다면 엑셀 VBA 편집기에서 BankSort 모듈을 지우고 `~/Library/Application Support/BankSort/BankSort.bas` 를 다시 가져오기.
