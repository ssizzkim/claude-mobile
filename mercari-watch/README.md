# Mercari Watch (メルカリ 키워드 알림)

일본 메르카리(jp.mercari.com)에 지정한 키워드의 새 상품이 올라오면 이메일로 알려줍니다.
GitHub Actions가 10분마다 실행되며, 서버나 비용이 필요 없습니다.

## 설정 (최초 1회)

1. **Gmail 앱 비밀번호 만들기**
   Google 계정 → 보안 → 2단계 인증 켜기 → <https://myaccount.google.com/apppasswords> 에서 16자리 앱 비밀번호 생성
2. **저장소 Secrets 등록** (Settings → Secrets and variables → Actions → New repository secret)
   | 이름 | 값 |
   |---|---|
   | `GMAIL_USER` | 보내는 Gmail 주소 |
   | `GMAIL_APP_PASSWORD` | 위에서 만든 앱 비밀번호 |
   | `MAIL_TO` | (선택) 받는 주소. 없으면 `GMAIL_USER`로 발송 |
3. **키워드 설정** — `config.json` 수정
   ```json
   {
     "watches": [
       { "keyword": "BTS トレカ", "exclude": "", "price_min": 0, "price_max": 0 },
       { "keyword": "ジミン ラキドロ", "exclude": "ブロマイド", "price_min": 0, "price_max": 5000 }
     ]
   }
   ```
   - `exclude`: 제외할 단어 (띄어쓰기로 여러 개)
   - `title_any`: (선택) 상품명에 이 중 하나라도 들어간 것만 알림. 영문은 단어 단위로 비교합니다(`ti`는 "Sol Ti"에는 걸리고 "edition"에는 안 걸림)
   - `price_min` / `price_max`: 엔 단위, `0`이면 제한 없음
   - 이 저장소는 공개라서 `config.json` 내용도 공개됩니다. 키워드를 숨기고 싶으면 같은 JSON을 `WATCH_CONFIG` Secret에 넣으세요. Secret이 있으면 파일보다 우선합니다.
4. Actions 탭 → **Mercari keyword watch** → **Run workflow**로 한 번 실행해 동작을 확인합니다.

## 동작 방식

- 각 키워드를 신착순으로 검색하고, 이전에 본 적 없는 판매중 상품만 메일 한 통으로 묶어 보냅니다.
- 새 키워드를 추가한 첫 실행에서는 현재 올라와 있는 상품을 기록만 하고 알림은 보내지 않습니다.
- 이미 본 상품 목록은 Actions 캐시에 저장됩니다(커밋이 생기지 않음).

## 참고

- GitHub의 예약 실행은 부하에 따라 몇 분씩 늦어지거나 가끔 건너뛸 수 있습니다.
- 저장소에 60일간 활동이 없으면 GitHub가 예약 실행을 자동으로 멈춥니다. Actions 탭에서 다시 켜면 됩니다.
- 메르카리 비공식 웹 API를 사용하므로, 메르카리가 사양을 바꾸면 수정이 필요할 수 있습니다.

로컬 테스트: `pip install cryptography && DRY_RUN=1 python mercari-watch/watch.py`
