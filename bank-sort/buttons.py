# -*- coding: utf-8 -*-
"""은행·홈택스 버튼 — 맥 앱 화면.
[신한은행 기업 열기] 사파리로 신한 기업뱅킹 첫 화면을 띄운다(로그인은 직접).
[홈택스 지난 7일 가져오기] 공동인증서 비밀번호로 홈택스 매출·매입 세금계산서를 엑셀로 받는다.
"""
import json
import os
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import hometax_fetch

HOME = Path(os.environ.get("BANKSORT_HOME", Path.home() / "Library/Application Support/BankSort"))
CONFIG = HOME / "config.json"
SHINHAN_URL = "https://bizbank.shinhan.com/"
OLD_SETTINGS = Path.home() / "Library/Application Support/BankTaxReport/settings.json"


def load_config():
    try:
        return json.loads(CONFIG.read_text("utf-8"))
    except Exception:
        return {}


def cert_dir():
    """공동인증서 폴더: 설정 → 예전 앱 설정 → NPKI 에서 '토르크' 인증서."""
    cfg = load_config()
    if cfg.get("cert_dir") and Path(cfg["cert_dir"]).is_dir():
        return cfg["cert_dir"]
    try:
        old = json.loads(OLD_SETTINGS.read_text("utf-8")).get("CERT_DIR")
        if old and Path(old).is_dir():
            return old
    except Exception:
        pass
    for p in (Path.home() / "Library/Preferences/NPKI").glob("*/USER/*"):
        if "토르크" in p.name and (p / "signCert.der").exists():
            return str(p)
    return None


def open_shinhan():
    # 신한 기업뱅킹 로그인은 맥 크롬에서 안 되고 사파리에서 된다
    for cmd in (["open", "-a", "Safari", SHINHAN_URL], ["open", SHINHAN_URL]):
        if subprocess.run(cmd).returncode == 0:
            return


class App:
    def __init__(self, root):
        self.root = root
        root.title("은행·홈택스")
        root.geometry("420x330")
        root.resizable(False, False)
        pad = dict(padx=18, pady=6)

        tk.Label(root, text="신한은행 기업뱅킹", font=("", 13, "bold")).pack(anchor="w", **pad)
        tk.Button(root, text="신한은행 기업 열기", font=("", 15), height=2, command=open_shinhan).pack(fill="x", padx=18)
        tk.Label(root, text="첫 화면까지 열어 줍니다. 로그인과 엑셀 받기는 직접 하세요.", fg="#666").pack(anchor="w", padx=18)

        tk.Frame(root, height=1, bg="#ccc").pack(fill="x", padx=18, pady=10)

        tk.Label(root, text="홈택스 세금계산서 (지난 7일, 매출·매입)", font=("", 13, "bold")).pack(anchor="w", padx=18)
        row = tk.Frame(root)
        row.pack(fill="x", padx=18, pady=4)
        tk.Label(row, text="인증서 비밀번호").pack(side="left")
        self.pw = tk.Entry(row, show="●")
        self.pw.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self.pw.bind("<Return>", lambda e: self.fetch())
        self.btn = tk.Button(root, text="홈택스에서 가져오기", font=("", 15), height=2, command=self.fetch)
        self.btn.pack(fill="x", padx=18)
        self.status = tk.Label(root, text="엑셀은 다운로드 폴더에 저장됩니다.", fg="#666", wraplength=380, justify="left")
        self.status.pack(anchor="w", padx=18, pady=4)
        self.pw.focus_set()

    def log(self, text):
        self.root.after(0, lambda: self.status.config(text=text))

    def fetch(self):
        password = self.pw.get()
        if not password:
            messagebox.showwarning("은행·홈택스", "공동인증서 비밀번호를 입력하세요.")
            return
        cdir = cert_dir()
        if not cdir:
            messagebox.showerror("은행·홈택스", "공동인증서를 찾지 못했습니다 (~/Library/Preferences/NPKI).")
            return
        self.btn.config(state="disabled")
        self.pw.delete(0, "end")          # 비밀번호는 화면에 남기지 않는다

        def work():
            try:
                paths, counts, (start, end) = hometax_fetch.fetch_last_week(password, cdir, log=self.log)
                msg = (f"{start} ~ {end} (발급일 기준)\n매출 {counts['매출']}건 · 매입 {counts['매입']}건\n\n"
                       + "\n".join(p.name for p in paths)
                       + "\n\n다운로드 폴더에 저장했습니다. 은행정리 버튼에서 이 파일들을 고르면 됩니다.")
                self.root.after(0, lambda: self.done(True, msg, paths))
            except Exception as e:
                text = str(e)
                if "decryption" in text.lower() or "password" in text.lower():
                    text = "인증서 비밀번호가 맞지 않습니다. 다시 입력해 주세요."
                self.root.after(0, lambda: self.done(False, text, None))

        threading.Thread(target=work, daemon=True).start()

    def done(self, ok, msg, paths):
        self.btn.config(state="normal")
        self.status.config(text="완료" if ok else "실패")
        if ok:
            subprocess.run(["open", "-R", str(paths[0])])
            messagebox.showinfo("홈택스 가져오기 완료", msg)
        else:
            messagebox.showerror("홈택스 가져오기 실패", msg)


if __name__ == "__main__":
    root = tk.Tk()
    try:   # 실행 중 Dock 에 파이썬 대신 앱 아이콘이 보이게
        root.iconphoto(True, tk.PhotoImage(file=str(Path(__file__).with_name("icon.png"))))
    except Exception:
        pass
    App(root)
    root.mainloop()
