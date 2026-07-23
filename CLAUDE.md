# 조각 (JOGAK) — 카드 노트 앱

단편적인 글을 카드("조각") 단위로 수집하고, 얕은 폴더("서랍")로 정리하는 개인 노트 앱.
노트북과 모바일 연동이 최종 목표. 사용자와 한국어로 대화하고, UI 문구도 한국어를 유지한다.

## 구조

- `mac/` — **맥 네이티브 앱 (SwiftUI, Swift Package). 현재 개발 본진.** Xcode로 `mac` 폴더를 열거나 `swift run`.
- `app/index.html` — 동작하는 웹 앱 v0.1. 의존성 없는 단일 HTML 파일(바닐라 JS). 모바일에서는 이걸 쓴다.
- `desktop/` — Electron 래퍼(웹 앱을 감싼 임시 맥 앱). 네이티브 앱이 자리 잡으면 제거 후보.
- `design/index.html` — 디자인 시안 문서 (화면 목업, 데이터 구조, 디자인 토큰).

## 실행

- 맥 네이티브: Xcode에서 `mac` 폴더 열고 ⌘R, 또는 `cd mac && swift run`
- 웹: `app/index.html`을 브라우저에서 열기
- Electron: `cd desktop && npm install && npm start`

## 데이터 호환

맥 앱(`~/Library/Application Support/Jogak/jogak.json`)과 웹 앱(localStorage `jogak.v1`)은
같은 JSON 필드(`cards`/`folders`, `created_at` 등)를 쓴다. 새 필드를 추가할 때는 양쪽 모두 반영하고,
디코딩은 관대하게(모르는 필드 무시, 누락 필드 기본값) 유지한다.

## 확정된 결정 (뒤집을 때는 사용자에게 확인)

- 카드가 기본 단위. 제목·필수 항목 없음. 저장까지 3초가 목표.
- 서랍은 1단계(트리 없음). 한 카드가 여러 서랍에 동시 소속 가능(`folders` 배열). 빈 배열 = 미분류함.
- **사진은 사본 저장** (iCloud 링크는 보류, PhotoKit 참조는 네이티브 단계). 첨부 시 캔버스로 최대 1024px JPEG 리사이즈.
- 화면 캡처는 핵심 기능: 맥 앱 ⌘⇧J 글로벌 빠른 캡처, 스크린샷 클립보드 붙여넣기(⌘V)·드래그&드롭 첨부. OCR 검색은 로드맵.
- 데이터는 기기별 localStorage(`jogak.v1` 키). 이동은 더보기 탭의 JSON 백업/가져오기(id 기준 병합, updated_at 최신 우선).

## 디자인 토큰

- 액센트: 쪽빛 `#2D5BA8` (다크에서 `#7FA4E0`), 바탕은 푸른 기 도는 종이색 `#F1F3F6`.
- 타이포: UI는 고딕(Pretendard/Apple SD Gothic Neo 계열), 인용·상세 본문만 명조(Noto Serif KR 계열).
- 라이트/다크 모두 지원: 토큰은 `:root` 커스텀 프로퍼티, `prefers-color-scheme` + `data-theme` 오버라이드 패턴 유지.

## 로드맵 (다음 할 일)

1. 실시간 동기화 — local-first + 서버(또는 iCloud/CloudKit) 동기화 설계. 현재 가장 큰 미해결 과제.
2. 캡처 강화 — 맥 ⌘⇧S 영역 스크린샷 캡처, OCR 텍스트 추출·검색, 브라우저 확장.
3. 연결된 조각 — 상세 화면에서 같은 서랍·유사 내용 카드 추천 (시안 2-4 참고).
4. iOS 네이티브 — 공유 시트로 조각 저장, PhotoKit 사진 참조.
