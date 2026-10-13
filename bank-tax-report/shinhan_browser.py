"""신한은행 기업뱅킹 화면 반자동 조회 (CODEF 없이) — "한 번 보여주면 기억".

1. 이 앱 전용 크롬 창(설치된 크롬, 앱 전용 프로필)으로 신한 기업뱅킹을 연다.
2. 로그인은 사람이 직접 한다(공동인증서 비밀번호는 앱이 다루지 않는다).
3. 받을 자료(거래내역조회, 이체결과조회)마다:
   - 기억한 클릭 순서가 있으면 그대로 다시 누르고, '조회' 직전에 기간을 넣고, 엑셀을 받는다.
   - 없거나 실패하면 사람이 크롬에서 직접 메뉴 → 조회 → 엑셀저장을 한다. 앱은 그 클릭을 기록해
     recipes.json 에 저장하고, 다음부터는 자동으로 한다.
4. 받은 파일은 자료별로 돌려준다.
"""

import json
import os
import shutil
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

SHINHAN_URL = os.environ.get("SHINHAN_URL", "https://bizbank.shinhan.com/")
LOGIN_TIMEOUT = 10 * 60
TEACH_TIMEOUT = 15 * 60
EXCEL_SUFFIXES = (".xls", ".xlsx", ".csv", ".htm", ".html")

# 받을 자료: (키, 화면에서 찾을 메뉴 이름 — 사람에게 안내용)
REPORTS = [
    ("transactions", "거래내역조회"),
    ("transfers", "이체결과조회"),
]
WEEK_BUTTONS = ["1주일", "1주", "일주일", "7일"]
SEARCH_BUTTONS = ["조회", "조회하기", "검색"]
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


HIDE_WEBDRIVER_JS = "Object.defineProperty(Navigator.prototype, 'webdriver', {get: () => undefined});"


def open_chrome(pw, profile: Path):
    """설치된 크롬을 이 앱 전용 프로필로 띄운다(일반 크롬과 섞이지 않음)."""
    profile.mkdir(parents=True, exist_ok=True)
    # 경고 줄이 뜨는 플래그(--disable-blink-features 등)는 쓰지 않고, 자동화 표시는 스크립트로 숨긴다
    args = ["--no-first-run", "--no-default-browser-check"]
    args += os.environ.get("BTR_CHROME_ARGS", "").split()
    try:
        context = pw.chromium.launch_persistent_context(
            str(profile),
            executable_path=chrome_path(),
            headless=False,
            chromium_sandbox=True,  # 기본값이면 --no-sandbox 가 붙어 경고 줄이 뜬다
            accept_downloads=True,
            no_viewport=True,
            args=args,
            ignore_default_args=["--enable-automation"],
        )
    except Exception as error:
        if "ProcessSingleton" in str(error) or "profile" in str(error).lower():
            raise StepFailed("앱이 전에 연 크롬 창이 아직 열려 있습니다. 그 크롬 창을 닫고 다시 시도하세요.") from None
        raise StepFailed(f"크롬을 띄우지 못했습니다: {error}") from None
    context.add_init_script(HIDE_WEBDRIVER_JS)
    return context


# ------------------------------------------------------------------ 화면 찾기


def frames(context):
    """최근에 열린 창(팝업)부터, 안쪽 프레임(본문)부터."""
    for page in reversed(context.pages):
        if page.is_closed():
            continue
        for frame in reversed(page.frames):
            yield page, frame


def visible(locator, limit: int = 20):
    try:
        count = min(locator.count(), limit)
    except Exception:
        return
    for index in range(count):
        item = locator.nth(index)
        try:
            if item.is_visible():
                yield item
        except Exception:
            continue


def by_text(frame, text: str):
    quoted = text.replace('"', '\\"')
    for locator in (
        frame.get_by_role("button", name=text, exact=True),
        frame.get_by_role("link", name=text, exact=True),
        frame.locator(f'input[type=button][value="{quoted}"], input[type=submit][value="{quoted}"]'),
        frame.get_by_text(text, exact=True),
    ):
        yield from visible(locator)


def logged_in(context) -> bool:
    for _, frame in frames(context):
        for marker in LOGGED_IN_MARKERS:
            for _ in by_text(frame, marker):
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


def set_period(context, start: date, end: date, log, quiet: bool = False) -> bool:
    for _, frame in frames(context):
        try:
            if frame.evaluate(DATE_JS, [start.isoformat(), end.isoformat()]):
                log(f"  · 조회기간 {start} ~ {end} 입력")
                return True
        except Exception:
            continue
    if not quiet:
        log("  · 날짜 입력칸을 찾지 못해 화면에 있는 기간으로 조회합니다(나중에 기간으로 걸러냄).")
    return False


# ------------------------------------------------------------------ 클릭 기록·재생

RECORDER_JS = r"""
(() => {
  if (window.__btrRecorder) return;
  window.__btrRecorder = true;
  const label = el => {
    const raw = (el.tagName === 'INPUT') ? (el.value || el.title || '') :
      (el.innerText || el.alt || el.title || el.getAttribute('aria-label') || '');
    return raw.trim().replace(/\s+/g, ' ');
  };
  const send = step => { try { window.__btrRecord && window.__btrRecord(step); } catch (e) {} };
  document.addEventListener('click', e => {
    let el = e.target.closest('a,button,input,[onclick],[role=button],[role=tab],label,li') || e.target;
    if (el.tagName === 'SELECT') return;
    if (el.tagName === 'INPUT' && !['button', 'submit', 'image', 'radio', 'checkbox'].includes(el.type)) return;
    let text = label(el);
    if (text.length > 40) { el = e.target; text = label(el); }
    if (text.length > 40) text = '';
    if (!text && !el.id) return;
    send({kind: 'click', text, id: el.id || '', tag: el.tagName, frame: location.pathname});
  }, true);
  document.addEventListener('change', e => {
    const el = e.target;
    if (el.tagName !== 'SELECT') return;
    send({kind: 'select', id: el.id || '', name: el.name || '', value: el.value,
          text: (el.selectedOptions[0] || {}).text || '', frame: location.pathname});
  }, true);
})();
"""


def clean_steps(steps: list[dict]) -> list[dict]:
    """달력 날짜 클릭, 바로 반복된 클릭을 뺀다."""
    result = []
    for step in steps:
        text = step.get("text", "")
        if step["kind"] == "click" and text.isdigit() and len(text) <= 2 and not step.get("id"):
            continue  # 달력의 날짜(기간은 재생 때 따로 넣는다)
        if result and result[-1] == step:
            continue
        result.append(step)
    return result


def find_step(context, step):
    """기록한 단계에 해당하는 화면 요소(같은 프레임 경로 우선)."""
    ordered = sorted(frames(context), key=lambda pf: urlparse(pf[1].url).path != step.get("frame"))
    for _, frame in ordered:
        if step["kind"] == "select":
            attr = f'select[id="{step["id"]}"]' if step.get("id") else f'select[name="{step.get("name", "")}"]'
            for item in visible(frame.locator(attr)):
                return item
            continue
        if step.get("id"):
            for item in visible(frame.locator(f'[id="{step["id"]}"]')):
                return item
        if step.get("text"):
            for item in by_text(frame, step["text"]):
                return item
    return None


def replay(context, steps, start, end, log, pause) -> None:
    period_set = False
    for number, step in enumerate(steps, start=1):
        is_search = step["kind"] == "click" and step.get("text") in SEARCH_BUTTONS
        if is_search and not period_set:  # 날짜칸이 실제로 채워질 때까지 '조회' 때마다 시도
            pause(1)
            period_set = set_period(context, start, end, log, quiet=True)
        deadline = time.time() + 15
        item = None
        while item is None and time.time() < deadline:
            item = find_step(context, step)
            if item is None:
                pause(0.7)
        name = step.get("text") or step.get("id")
        if item is None:
            raise StepFailed(f"{number}번째 클릭('{name}')을 화면에서 찾지 못했습니다.")
        try:
            if step["kind"] == "select":
                item.select_option(value=step["value"], timeout=5000)
            else:
                item.click(timeout=5000)
        except Exception as error:
            raise StepFailed(f"{number}번째 클릭('{name}') 실패: {error}") from None
        log(f"  · {number}/{len(steps)} '{name}'")
        pause(1.5 if not is_search else 3)


# ------------------------------------------------------------------ 다운로드 감지


def finished_files(folder: Path) -> dict[str, int]:
    """다 받아진(크기가 0이 아닌) 엑셀 파일 이름 → 크기."""
    return {
        p.name: p.stat().st_size for p in folder.iterdir()
        if p.suffix.lower() in EXCEL_SUFFIXES and not p.name.startswith(".") and p.stat().st_size > 0
    }  # fmt: skip


USER_DOWNLOADS = Path.home() / "Downloads"


def adopt_stray_downloads(folder: Path, since: float) -> None:
    """크롬이 지정 폴더 대신 ~/Downloads 에 저장했으면 그 새 파일을 지정 폴더로 복사한다."""
    if not USER_DOWNLOADS.is_dir() or USER_DOWNLOADS == folder:
        return
    for path in USER_DOWNLOADS.iterdir():
        try:
            if (path.suffix.lower() in EXCEL_SUFFIXES and path.stat().st_mtime >= since
                    and path.stat().st_size > 0 and not (folder / path.name).exists()):  # fmt: skip
                shutil.copy2(path, folder / path.name)
        except OSError:
            continue


def wait_for_files(folder: Path, timeout: float, idle, done=None, since: float | None = None) -> list[Path]:
    """새 파일이 생기고 3초간 변화가 없으면 돌려준다. done(이벤트)이 오면 그때까지 받은 것."""
    deadline = time.time() + timeout
    found: dict[str, int] = {}
    stable_since = time.time()
    while time.time() < deadline:
        if since is not None:
            adopt_stray_downloads(folder, since)
        current = finished_files(folder)
        if current != found:
            found, stable_since = current, time.time()
        if found and time.time() - stable_since > 3:
            break
        if done is not None and done.is_set():
            break
        idle()
    return sorted(folder / name for name in found)


def dump_debug(context, folder: Path, log) -> None:
    """메뉴 글자와 스크린샷 저장 — 문제를 고칠 때 참고용."""
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
        (folder / f"shinhan-{stamp}.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
        for index, page in enumerate(p for p in context.pages if not p.is_closed()):
            try:
                page.screenshot(path=str(folder / f"shinhan-{stamp}-{index}.png"))
            except Exception:
                pass
        log(f"  · 화면 정보를 저장했습니다: {folder}")
    except Exception:
        pass


# ------------------------------------------------------------------ 기억한 순서 파일


def recipes_path(home: Path) -> Path:
    return home / "recipes.json"


def load_recipes(home: Path) -> dict:
    try:
        return json.loads(recipes_path(home).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_recipes(home: Path, recipes: dict) -> None:
    home.mkdir(parents=True, exist_ok=True)
    recipes_path(home).write_text(json.dumps(recipes, ensure_ascii=False, indent=1), encoding="utf-8")


def forget_recipes(home: Path) -> None:
    try:
        recipes_path(home).unlink()
    except OSError:
        pass


# ------------------------------------------------------------------ 전체 흐름


def download_statements(start: date, end: date, home: Path, log=print, done=None,
                        save_dir: Path | None = None) -> dict[str, list[Path]]:
    """신한 기업뱅킹에서 거래내역·이체결과 엑셀을 받아 {자료: [파일]} 로 돌려준다.

    done: 사람이 앱에서 [다음 ▶]을 누르면 set 되는 threading.Event (로그인 완료 / 이 자료 건너뛰기).
    save_dir: 은행 원본 파일을 복사해 둘 폴더. 그 아래 조회시각/자료별 폴더가 생긴다.

    크롬은 항상 앱 폴더(home/downloads)에 받는다. 데스크탑·문서는 macOS 가 크롬의 쓰기를
    막을 수 있어서, 받은 뒤 앱이 save_dir 로 복사한다."""
    from playwright.sync_api import sync_playwright

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = home / "downloads" / stamp
    recipes = load_recipes(home)
    result: dict[str, list[Path]] = {}

    def pressed() -> bool:
        if done is not None and done.is_set():
            done.clear()
            return True
        return False

    log("  · 크롬으로 신한 기업뱅킹을 엽니다.")
    with sync_playwright() as pw:
        context = open_chrome(pw, home / "chrome")
        target = {"folder": run_dir}  # 지금 받는 자료의 폴더
        pending: list = []

        def on_download(download):  # 실제 저장은 idle() 에서(이벤트 처리 중에 기다리면 멈출 수 있음)
            log(f"  · 다운로드 시작: {download.suggested_filename}")
            pending.append(download)

        def save_pending():
            while pending:
                download = pending.pop(0)
                name = download.suggested_filename or "download.xls"
                dest = target["folder"] / name
                if dest.exists():
                    dest = dest.with_name(f"{dest.stem}-{int(time.time())}{dest.suffix}")
                try:
                    download.save_as(str(dest))
                    log(f"  · 다운로드 완료: {dest.name}")
                except Exception as error:
                    log(f"  · 다운로드 실패: {name} ({download.failure() or error})")

        recorded: list[dict] = []
        recording = {"on": False}

        def record(_source, step):
            if recording["on"] and isinstance(step, dict):
                recorded.append(step)

        context.expose_binding("__btrRecord", record)
        context.add_init_script(RECORDER_JS)

        def inject():
            for _, frame in frames(context):
                try:
                    frame.evaluate(RECORDER_JS)
                except Exception:
                    pass

        def idle():  # 브라우저 이벤트(다운로드·기록)를 처리하며 잠깐 쉰다
            pages = [p for p in context.pages if not p.is_closed()]
            if not pages:
                raise StepFailed("크롬 창이 닫혔습니다.")
            try:
                pages[-1].wait_for_timeout(500)
            except Exception:
                time.sleep(0.5)
            save_pending()

        def pause(seconds):
            end_at = time.time() + seconds
            while time.time() < end_at:
                idle()

        def watch(page):
            page.on("dialog", lambda dialog: dialog.accept())
            page.on("download", on_download)

        for page in context.pages:
            watch(page)
        context.on("page", watch)
        page = context.pages[0] if context.pages else context.new_page()
        try:
            page.goto(SHINHAN_URL, timeout=60000)
        except Exception as error:
            log(f"  · 신한 기업뱅킹 페이지를 여는 중 문제가 있었습니다({error}). 크롬 창을 확인하세요.")

        log("  ▶ 크롬 창에서 공동인증서로 로그인하세요.")
        log("    (로그인되면 자동으로 이어집니다. 안 넘어가면 앱의 [다음 ▶]을 누르세요)")
        deadline = time.time() + LOGIN_TIMEOUT
        last_inject = 0.0
        while not logged_in(context):
            if pressed():
                break
            if time.time() > deadline:
                raise StepFailed("10분 안에 로그인이 확인되지 않았습니다.")
            if time.time() - last_inject > 2:  # 기록기를 미리 설치해 로그인 직후 클릭도 놓치지 않게
                inject()
                last_inject = time.time()
            idle()
        inject()
        log("  · 로그인 확인")

        names = {"transactions": "거래내역", "transfers": "이체결과"}
        for key, menu in REPORTS:
            folder = run_dir / names.get(key, key)
            folder.mkdir(parents=True, exist_ok=True)
            target["folder"] = folder
            files: list[Path] = []
            began = time.time() - 2
            steps = recipes.get(key)
            if steps:
                log(f"  · {menu}: 기억한 순서({len(steps)}단계)대로 진행합니다.")
                try:
                    replay(context, steps, start, end, log, pause)
                    files = wait_for_files(folder, 60, idle, since=began)
                    if not files:
                        raise StepFailed("엑셀 파일이 내려받아지지 않았습니다.")
                except StepFailed as error:
                    log(f"  · 자동 진행 실패: {error}")
                    dump_debug(context, home / "debug", log)
                    log("    화면이 바뀐 것 같습니다. 한 번 더 보여 주시면 새 순서를 기억합니다.")
            if not files:
                log(f"  ▶ 크롬에서 직접: [{menu}] 메뉴 → 기간 선택 → 조회 → 엑셀저장")
                log("    앱이 클릭 순서를 기억해서 다음부터는 자동으로 합니다.")
                log(f"    ({menu} 자료가 필요 없으면 앱의 [다음 ▶]을 누르세요)")
                recorded.clear()
                recording["on"] = True
                inject()
                deadline = time.time() + TEACH_TIMEOUT
                last_inject = time.time()
                while time.time() < deadline:
                    adopt_stray_downloads(folder, began)
                    if finished_files(folder):
                        files = wait_for_files(folder, 30, idle, since=began)
                        break
                    if pressed():
                        break
                    if time.time() - last_inject > 2:  # 새로 열린 프레임에도 기록기 설치
                        inject()
                        last_inject = time.time()
                    idle()
                recording["on"] = False
                if files:
                    learned = clean_steps(recorded)
                    if learned:
                        recipes[key] = learned
                        save_recipes(home, recipes)
                        log(f"  · {menu} 클릭 순서 {len(learned)}단계를 기억했습니다.")
                else:
                    log(f"  · {menu}: 받은 파일이 없어 건너뜁니다.")
            if files:
                log(f"  · {menu} 파일: {', '.join(p.name for p in files)}")
            result[key] = files
        try:
            context.close()  # 앱이 연 크롬 창을 닫는다(로그인 정보는 다음을 위해 프로필에 남음)
        except Exception:
            pass
    if save_dir:
        result = copy_out(result, run_dir, save_dir / stamp, log)
    return result


def copy_out(result: dict[str, list[Path]], run_dir: Path, target: Path, log) -> dict[str, list[Path]]:
    """앱 폴더에 받은 원본을 저장 폴더로 복사한다. 실패하면 앱 폴더 원본을 그대로 쓴다."""
    copied: dict[str, list[Path]] = {}
    for key, files in result.items():
        copied[key] = []
        for path in files:
            dest = target / path.relative_to(run_dir)
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dest)
                copied[key].append(dest)
            except OSError as error:
                log(f"  · 저장 폴더로 복사하지 못했습니다({error}). 원본: {path}")
                copied[key].append(path)
    if any(copied.values()):
        log(f"  · 은행 원본 파일: {target}")
    return copied


if __name__ == "__main__":  # 단독 시험: python shinhan_browser.py
    home = Path(os.environ.get("BTR_HOME", Path(__file__).resolve().parent))
    today = date.today()
    print(download_statements(today - timedelta(days=6), today, home))
    sys.exit(0)
