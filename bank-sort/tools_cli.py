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
            # 비밀번호가 비어 있어도 홈택스 로그인 세션이 살아 있으면 그대로 조회된다
            cdir = hometax_fetch.cert_dir()
            if not cdir:
                raise RuntimeError("공동인증서를 찾지 못했습니다 (~/Library/Preferences/NPKI).")
            try:
                paths, counts, (start, end) = hometax_fetch.fetch_last_week(stdin.strip(), cdir, log=lambda t: None)
            except Exception as e:
                if "decryption" in str(e).lower() or "password" in str(e).lower() or "비밀번호" in str(e):
                    raise RuntimeError("인증서 비밀번호가 맞지 않거나, 로그인이 만료됐습니다. 비밀번호를 넣어 다시 시도하세요.") from None
                raise
            subprocess.run(["open", "-R", str(paths[0])])
            return {"ok": True, "action": action, "start": str(start), "end": str(end), "counts": counts,
                    "files": [str(p) for p in paths]}
        if action == "gmail":
            import gmail_routine
            return {"ok": True, "action": action, "report": gmail_routine.run(log=lambda t: None)}
        if action == "daily":
            import daily_digest
            req = json.loads(stdin or "{}")
            try:
                result = daily_digest.run(req.get("projects", []), log=lambda t: None)
            except daily_digest.NeedPermission as e:
                return {"ok": False, "action": action, "permission": str(e),
                        "error": "문자를 읽으려면 「전체 디스크 접근」, 카톡을 읽으려면 「손쉬운 사용」 권한을 "
                                 "토르크 관리 앱에 허용해야 합니다 (시스템 설정 → 개인정보 보호 및 보안)."}
            return {"ok": True, "action": action, **result}
        return {"ok": False, "action": action, "error": f"모르는 기능: {action}"}
    except Exception as e:
        (HERE / "tools_error.log").write_text(traceback.format_exc(), "utf-8")
        return {"ok": False, "action": action, "error": str(e)}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False))
