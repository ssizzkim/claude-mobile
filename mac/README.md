# 조각 — 맥 네이티브 앱 (SwiftUI)

맥에서 새로 개발하는 네이티브 버전입니다. 의존성 없는 Swift Package라서
Xcode만 있으면 바로 열어서 실행할 수 있습니다.

## 실행하기

**Xcode로 (권장)**

1. Xcode 실행 → **File → Open…** → 이 `mac` 폴더 선택
2. 상단 실행 대상이 **My Mac**인지 확인
3. **▶ (⌘R)** 실행

**터미널로**

```bash
cd mac
swift run
```

## 지금 되는 것 (v0.1 스캐폴드)

- 조각 작성(⌘N)·수정·삭제·고정, ⌘Enter 저장
- 서랍 사이드바: 만들기/이름 변경/삭제(우클릭), 서랍별 개수, 미분류함
- 검색 (툴바)
- 데이터는 `~/Library/Application Support/Jogak/jogak.json`에 저장 —
  **웹 앱의 JSON 백업과 같은 형식**이라 나중에 서로 가져오기가 가능합니다
  (`Store.importBackup(from:)` 준비됨, UI 연결은 다음 단계)

## 다음 할 일

1. 가져오기/내보내기 메뉴 연결 (웹 앱 ↔ 맥 앱 데이터 이동)
2. 사진 사본 첨부 (드래그&드롭, 붙여넣기)
3. ⌘⇧J 글로벌 빠른 캡처 창, ⌘⇧S 영역 스크린샷 캡처
4. iCloud/서버 동기화

## 구조

```
mac/
  Package.swift              Swift Package 정의 (macOS 14+)
  Sources/Jogak/
    JogakApp.swift           앱 진입점
    Models.swift             JCard/JFolder — 웹 백업과 같은 JSON 필드
    Store.swift              저장/불러오기, 검색·필터, 백업 병합
    ContentView.swift        사이드바(서랍) + 카드 목록
    ComposeView.swift        조각 작성/수정 시트
```
