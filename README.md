# claude-mobile

Static apps hosted via GitHub Pages. Each subfolder is an independent, self-contained app.

## Apps

- [`kpop-comeback-radar/`](./kpop-comeback-radar) — K-POP Comeback Radar demo. Clean-line, infographic-style dashboard with animated charts. Runs entirely client-side in demo mode (no API keys, no backend, no external network calls). Includes a "전체 데이터 초기화" control that clears all locally stored test data (selected artist, chat history).
- [`bank-tax-report/`](./bank-tax-report) — 신한은행 기업 계좌 거래·이체 내역 + 홈택스 세금계산서 발급/수취 내역을 공동인증서로 조회해 엑셀 한 파일로 저장하는 맥 앱 (`install_mac.command`로 설치, Windows/명령줄도 지원).
- [`mercari-watch/`](./mercari-watch) — 메르카리(일본) 키워드 신착 알림. GitHub Actions가 10분마다 검색해 새 상품을 이메일로 보냅니다 (웹 앱이 아닌 예약 작업).
