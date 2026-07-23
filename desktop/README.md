# 조각 — 맥 앱 (desktop)

웹 앱(`app/index.html`)을 그대로 감싼 Electron 맥 앱입니다.
같은 UI에 더해, 맥에서만 되는 것:

- **⌘⇧J 글로벌 빠른 캡처** — 어떤 앱을 쓰고 있든 단축키를 누르면 캡처 창이 떠서 조각 하나를 바로 저장합니다. 창을 다 닫아도 앱이 살아 있어 단축키가 계속 동작합니다.
- **스크린샷 → 조각** — `⌘⇧⌃4`(영역을 클립보드로 캡처) 후 캡처 창에서 `⌘V` 붙여넣기 하면 사진 조각이 됩니다. 이미지 파일 드래그&드롭도 됩니다.
- 데이터는 맥에 저장됩니다 (`~/Library/Application Support/조각/`).

## 실행하기 (개발 모드)

[Node.js](https://nodejs.org) (LTS)가 설치되어 있어야 합니다.

```bash
cd desktop
npm install
npm start
```

## .app / .dmg 만들기

```bash
cd desktop
npm install
npm run dist
```

`desktop/dist/` 안에 `조각-0.1.0-arm64.dmg`(Apple Silicon 기준)가 생깁니다.
dmg를 열어 `조각.app`을 응용 프로그램 폴더로 끌어다 놓으면 설치 완료.

> **처음 열 때**: 서명되지 않은 앱이라 "확인되지 않은 개발자" 경고가 뜹니다.
> 앱을 **우클릭 → 열기**로 한 번만 승인하면 이후에는 그냥 열립니다.

## 웹/모바일과 데이터 옮기기

맥 앱과 웹 앱(아티팩트)은 저장 공간이 분리되어 있습니다.
앱 안의 **더보기 → JSON 백업 / 가져오기**로 양쪽을 옮길 수 있습니다.
실시간 동기화는 다음 단계(서버 연동)에서 추가 예정입니다.

## 구조

```
desktop/
  main.js        Electron 메인 프로세스 (창, 메뉴, ⌘⇧J 단축키)
  package.json   실행/빌드 스크립트 (renderer는 ../app/index.html을 복사해 사용)
  renderer/      npm start / npm run dist 시 자동 생성 (커밋하지 않음)
```

UI를 고치려면 `app/index.html`만 수정하면 됩니다 — 실행할 때마다 자동으로 복사됩니다.
