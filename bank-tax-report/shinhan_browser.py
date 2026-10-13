"""신한은행 기업뱅킹 화면 반자동 조회 (CODEF 없이).

1. 이 앱 전용 크롬 창으로 신한 기업뱅킹을 연다(실제 크롬, 원격 디버깅 포트로 연결).
2. 로그인은 사람이 직접 한다(공동인증서 비밀번호는 앱이 다루지 않는다).
3. 로그인되면 화면 글자를 보고 조회 → 거래내역조회 → 기간 → 조회 → 엑셀저장을 누른다.
4. 자동 클릭이 실패하면 그 창에서 사람이 엑셀을 내려받으면 된다. 받은 파일을 감지해 이어서 진행한다.
   실패한 화면의 메뉴 글자·스크린샷은 debug 폴더에 남긴다(다음 버전에서 고칠 수 있도록).

메뉴 이름이 다르면 CLICK_STEPS 의 후보 글자만 고치면 된다.
"""

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

SHINHAN_URL = os.environ.get("SHINHAN_URL", "https://bizbank.shinhan.com/")
DEBUG_PORT = int(os.environ.get("BTR_CHROME_PORT", "9333"))
LOGIN_TIMEOUT = 10 * 60
MANUAL_TIMEOUT = 15 * 60
EXCEL_SUFFIXES = (".xls", ".xlsx", ".csv", ".htm", ".html")

# 순서대로 누를 메뉴. 각 단계는 후보 글자 중 화면에 보이는 첫 번째를 누른다.
MENU_STEPS = [
    ("조회 메뉴", ["조회"], True),  # (설명, 후보, 없으면 건너뛰어도 되는지)
    ("거래내역조회 메뉴", ["거래내역조회", "입출금거래내역조회", "거래내역 조회", "입출금내역조회"], False),
]
WEEK_BUTTONS = ["1주일", "1주", "일주일", "7일"]
SEARCH_BUTTONS = ["조회", "조회하기"]
EXCEL_BUTTONS = ["엑셀저장", "엑셀 저장", "엑셀다운로드", "엑셀 다운로드", "엑셀파일저장", "Excel", "엑셀"]
LOGGED_IN_MARKERS = ["로그아웃", "LOGOUT", "Logout"]


class StepFailed(Exception):
    pass


# ------------------------------------------------------------------ 크롬


def chrome_path() -> str:
    override = os.environ.get("BTR_CHROME")
    candidates = [override] if override else []
    candidates += [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        shutil.which("google-chrome") or "",
        shutil.which("chromium") or "",
    ]
    for path in candidates:
        if path and Path(path).is_file():
            return path
    raise StepFailed("Google Chrome 을 찾지 못했습니다. 설치 명령을 다시 실행하면 크롬도 설치됩니다.")


def port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def launch_chrome(profile: Path, log) -> None:
    if port_open(DEBUG_PORT):
        return  # 이전에 연 앱 전용 크롬이 아직 떠 있음
    profile.mkdir(parents=True, exist_ok=True)
    args = [
        chrome_path(),
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        SHINHAN_URL,
    ]
    if os.environ.get("BTR_CHROME_ARGS"):
        args[1:1] = os.environ["BTR_CHROME_ARGS"].split()
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(60):
        if port_open(DEBUG_PORT):
            return
        time.sleep(0.5)
    raise StepFailed("크롬을 띄우지 못했습니다. 크롬을 모두 닫고 다시 시도하세요.")


# ------------------------------------------------------------------ 화면 조작


def frames(context):
    """최근에 열린 창(팝업)부터, 안쪽 프레임(본문)부터. 위쪽 메뉴의 같은 글자보다 본문 버튼을 먼저 누르려고."""
    for page in reversed(context.pages):
        if page.is_closed():
            continue
        for frame in reversed(page.frames):
            yield page, frame


def visible_locators(frame, text: str, exact: bool = True):
    for locator in (
        frame.get_by_role("button", name=text, exact=exact),
        frame.get_by_role("link", name=text, exact=exact),
        frame.locator(f'input[type=button][value="{text}"], input[type=submit][value="{text}"]'),
        frame.get_by_text(text, exact=exact),
    ):
        try:
            count = min(locator.count(), 20)
        except Exception:
            continue
        for index in range(count):
            item = locator.nth(index)
            try:
                if item.is_visible():
                    yield item
            except Exception:
                continue


def click_text(context, candidates: list[str], timeout: float, log, label: str) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        for exact in (True, False):
            for _, frame in frames(context):
                for text in candidates:
                    if not exact and len(text) < 4:  # '조회' 같은 짧은 글자는 정확히 같을 때만
                        continue
                    for item in visible_locators(frame, text, exact):
                        try:
                            item.click(timeout=3000)
                            log(f"  · {label}: '{text}' 클릭")
                            return text
                        except Exception:
                            continue
        time.sleep(0.7)
    raise StepFailed(f"{label}({' / '.join(candidates)})을(를) 화면에서 찾지 못했습니다.")


def logged_in(context) -> bool:
    for _, frame in frames(context):
        for marker in LOGGED_IN_MARKERS:
            for _ in visible_locators(frame, marker):
                return True
    return False


DATE_JS = """
([start, end]) => {
  const re = /^(\\d{4})([-./]?)(\\d{2})\\2(\\d{2})$/;
  const inputs = [...document.querySelectorAll('input')].filter(
    el => el.offsetParent !== null && re.test((el.value || '').trim()));
  if (inputs.length < 2) return 0;
  const put = (el, iso) => {
    const sep = (el.value.trim().match(re) || [])[2] || '';
    el.removeAttribute('readonly');
    el.value = iso.replaceAll('-', sep);
    for (const type of ['input', 'change', 'blur']) el.dispatchEvent(new Event(type, {bubbles: true}));
  };
  put(inputs[0], start); put(inputs[1], end);
  return inputs.length;
}
"""


def set_period(context, start: date, end: date, log) -> None:
    if (end - start).days == 6 and end == date.today():
        try:
            click_text(context, WEEK_BUTTONS, 3, log, "기간 1주일")
        except StepFailed:
            pass
    for _, frame in frames(context):
        try:
            if frame.evaluate(DATE_JS, [start.isoformat(), end.isoformat()]):
                log(f"  · 조회기간 {start} ~ {end} 입력")
                return
        except Exception:
            continue
    log("  · 날짜 입력칸을 찾지 못해 화면 기본 기간으로 조회합니다(나중에 기간으로 걸러냄).")


def new_files(folder: Path) -> dict[str, int]:
    """다 받아진(크기가 0이 아닌) 엑셀 파일 이름 → 크기."""
    return {
        p.name: p.stat().st_size for p in folder.iterdir()
        if p.suffix.lower() in EXCEL_SUFFIXES and not p.name.startswith(".") and p.stat().st_size > 0
    }  # fmt: skip


def wait_for_files(folder: Path, timeout: float, idle, done=None) -> list[Path]:
    """새 엑셀 파일을 기다린다. done(이벤트)이 오면 그때까지 받은 것을 돌려준다.

    idle(): 기다리는 동안 브라우저 이벤트(다운로드)를 처리하게 하는 함수."""
    deadline = time.time() + timeout
    found: dict[str, int] = {}
    stable_since = time.time()
    while time.time() < deadline:
        current = new_files(folder)
        if current != found:
            found, stable_since = current, time.time()
        settled = found and time.time() - stable_since > 3
        if done is not None and done.is_set() and (settled or not found):
            break
        if done is None and settled:
            break
        idle()
    return sorted(folder / name for name in found)


def dump_debug(context, folder: Path, log) -> Path | None:
    """메뉴 글자와 스크린샷 저장 — 이 파일을 보내 주면 메뉴 후보를 고칠 수 있다."""
    try:
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        info = []
        for page, frame in frames(context):
            try:
                texts = frame.evaluate(
                    """() => [...document.querySelectorAll('a,button,input[type=button],input[type=submit],li,span,td')]
                        .filter(el => el.offsetParent !== null)
                        .map(el => (el.value || el.innerText || '').trim())
                        .filter(t => t && t.length <= 20).slice(0, 400)"""
                )
            except Exception:
                texts = []
            info.append({"page": page.url, "frame": frame.url, "texts": sorted(set(texts))})
        path = folder / f"shinhan-{stamp}.json"
        path.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
        for index, page in enumerate(p for p in context.pages if not p.is_closed()):
            try:
                page.screenshot(path=str(folder / f"shinhan-{stamp}-{index}.png"))
            except Exception:
                pass
        log(f"  · 화면 정보를 저장했습니다: {path}")
        return path
    except Exception:
        return None


# ------------------------------------------------------------------ 전체 흐름


def download_statements(start: date, end: date, home: Path, log=print, done=None) -> list[Path]:
    """신한 기업뱅킹에서 거래내역 엑셀을 받아 파일 경로 목록을 돌려준다."""
    from playwright.sync_api import sync_playwright

    downloads = home / "downloads" / datetime.now().strftime("%Y%m%d-%H%M%S")
    downloads.mkdir(parents=True, exist_ok=True)

    log("  · 크롬으로 신한 기업뱅킹을 엽니다.")
    launch_chrome(home / "chrome-profile", log)
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{DEBUG_PORT}")
        context = browser.contexts[0]
        # 크롬이 내려받는 파일을 이번 조회 폴더로 바로 저장하게 한다
        cdp = browser.new_browser_cdp_session()

        def allow_downloads():
            cdp.send("Browser.setDownloadBehavior",
                     {"behavior": "allow", "downloadPath": str(downloads), "eventsEnabled": True})  # fmt: skip

        allow_downloads()

        def idle():  # 브라우저 이벤트를 처리하며 잠깐 쉰다
            pages = [p for p in context.pages if not p.is_closed()]
            if pages:
                try:
                    pages[-1].wait_for_timeout(500)
                    return
                except Exception:
                    pass
            time.sleep(0.5)

        def pause(seconds):
            end_at = time.time() + seconds
            while time.time() < end_at:
                idle()

        def watch(page):
            page.on("dialog", lambda dialog: dialog.accept())

        for page in context.pages:
            watch(page)
        context.on("page", watch)
        if not any(SHINHAN_URL.split("/")[2] in p.url for p in context.pages):
            page = context.new_page()
            page.goto(SHINHAN_URL)

        log("  ▶ 크롬 창에서 공동인증서로 로그인하세요. (로그인되면 자동으로 이어집니다)")
        deadline = time.time() + LOGIN_TIMEOUT
        while not logged_in(context):
            if time.time() > deadline:
                raise StepFailed("10분 안에 로그인이 확인되지 않았습니다.")
            if done is not None and done.is_set():
                break
            idle()
        log("  · 로그인 확인")

        try:
            for label, candidates, optional in MENU_STEPS:
                try:
                    click_text(context, candidates, 15, log, label)
                    pause(1.5)
                except StepFailed:
                    if not optional:
                        raise
            pause(2)
            set_period(context, start, end, log)
            click_text(context, SEARCH_BUTTONS, 10, log, "조회 버튼")
            pause(4)
            allow_downloads()
            click_text(context, EXCEL_BUTTONS, 15, log, "엑셀 저장")
            files = wait_for_files(downloads, 60, idle)
            if not files:
                raise StepFailed("엑셀 파일이 내려받아지지 않았습니다.")
        except StepFailed as error:
            log(f"  · 자동 진행 실패: {error}")
            dump_debug(context, home / "debug", log)
            allow_downloads()
            log("  ▶ 크롬 창에서 거래내역조회 → 엑셀저장을 직접 해 주세요.")
            log("    (계좌가 여러 개면 모두 받은 뒤 앱의 [은행 엑셀 받기 완료]를 누르세요)")
            files = wait_for_files(downloads, MANUAL_TIMEOUT, idle, done)
            if not files:
                raise StepFailed("은행 엑셀 파일을 받지 못했습니다.") from None
        else:
            if done is not None and not done.is_set():
                # 자동으로 한 계좌를 받은 뒤, 다른 계좌도 받을 시간을 잠깐 준다
                log("  · 다른 계좌도 받으려면 지금 크롬에서 더 받은 뒤 [은행 엑셀 받기 완료]를 누르세요.")
                log("    (30초 안에 더 받지 않으면 그대로 진행합니다)")
                more = wait_for_files(downloads, 30, idle, done)
                files = more or files
    log(f"  · 받은 파일: {', '.join(p.name for p in files)}")
    return files


if __name__ == "__main__":  # 단독 시험: python shinhan_browser.py
    home = Path(os.environ.get("BTR_HOME", Path(__file__).resolve().parent))
    today = date.today()
    print(download_statements(today - timedelta(days=6), today, home))
    sys.exit(0)
