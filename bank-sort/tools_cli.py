# -*- coding: utf-8 -*-
"""토르크 관리 맥 앱(래퍼 bankTools 브리지)이 부르는 입구. 결과는 JSON 한 줄로 표준출력.

  python tools_cli.py hometax      ← 표준입력: 공동인증서 비밀번호
  python tools_cli.py gmail
  python tools_cli.py daily        ← 표준입력: {"projects": ["프로젝트 이름", ...]}
"""
import json
import subprocess
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    stdin = sys.stdin.read() if not sys.stdin.isatty() else ""
    try:
        if action == "hometax":
            import hometax_fetch
            import keyring
            KC = ("TORQUE 홈택스", "공동인증서")       # 맥 키체인 항목(서비스, 계정)
            try:
                req = json.loads(stdin) if stdin.strip().startswith("{") else {"password": stdin.strip()}
            except json.JSONDecodeError:
                req = {"password": stdin.strip()}
            pw = (req.get("password") or "").strip()
            used_saved = False
            if not pw:
                pw = keyring.get_password(*KC) or ""     # 비어 있으면 키체인에 기억해 둔 비밀번호
                used_saved = bool(pw)
            # 비밀번호가 없어도 홈택스 로그인 세션이 살아 있으면 그대로 조회된다
            cdir = hometax_fetch.cert_dir()
            if not cdir:
                raise RuntimeError("공동인증서를 찾지 못했습니다 (~/Library/Preferences/NPKI).")
            try:
                paths, counts, (start, end) = hometax_fetch.fetch_last_week(pw, cdir, log=lambda t: None)
            except Exception as e:
                if "decryption" in str(e).lower() or "password" in str(e).lower() or "비밀번호" in str(e):
                    if used_saved:
                        keyring.delete_password(*KC)
                        return {"ok": False, "action": action, "needPassword": True,
                                "error": "기억해 둔 비밀번호가 맞지 않아 지웠습니다. 비밀번호를 다시 입력하세요."}
                    return {"ok": False, "action": action, "needPassword": True,
                            "error": "인증서 비밀번호가 맞지 않거나 로그인이 만료됐습니다. 비밀번호를 다시 입력하세요."}
                raise
            remembered = used_saved
            if pw and not used_saved and req.get("remember", True):
                keyring.set_password(*KC, pw)
                remembered = True
            subprocess.run(["open", str(Path(paths[0]).parent)])   # 다운로드 폴더를 띄운다
            return {"ok": True, "action": action, "start": str(start), "end": str(end), "counts": counts,
                    "files": [str(p) for p in paths], "remembered": remembered}
        if action == "forget_hometax":
            import keyring
            try:
                keyring.delete_password("TORQUE 홈택스", "공동인증서")
            except Exception:
                pass
            return {"ok": True, "action": action}
        if action == "gmail":
            import gmail_routine
            return {"ok": True, "action": action, "report": gmail_routine.run(log=lambda t: None)}
        if action == "daily":
            import daily_digest
            req = json.loads(stdin or "{}")
            try:
                result = daily_digest.run(req.get("projects", []), log=lambda t: None)
            except daily_digest.NeedPermission as e:
                which = "「전체 디스크 접근」(문자 읽기)" if str(e) == "sms" else "「손쉬운 사용」(카톡 읽기)"
                return {"ok": False, "action": action, "permission": str(e),
                        "error": f"토르크 관리 앱에 {which} 권한이 필요합니다.\n"
                                 "시스템 설정 → 개인정보 보호 및 보안에서 토르크 관리를 켠 뒤, "
                                 "토르크 관리를 완전히 껐다가(⌘Q) 다시 열어야 적용됩니다."}
            return {"ok": True, "action": action, **result}
        return {"ok": False, "action": action, "error": f"모르는 기능: {action}"}
    except Exception as e:
        (HERE / "tools_error.log").write_text(traceback.format_exc(), "utf-8")
        return {"ok": False, "action": action, "error": str(e)}


def _log(text):
    from datetime import datetime
    with open(HERE / "tools_run.log", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {text}\n")


if __name__ == "__main__":
    _log(f"시작 {sys.argv[1:]}")
    result = main()
    _log(f"끝 ok={result.get('ok')} {result.get('error', '')}")
    print(json.dumps(result, ensure_ascii=False))
