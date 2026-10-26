# -*- coding: utf-8 -*-
"""은행·홈택스 — 맥 앱 화면. 기능 버튼(타일)을 가로 한 줄로 늘어놓는다.
새 기능은 make_tiles.py 에 아이콘을 하나 그리고, 아래 App.TILES 끝에 한 줄 더하면 오른쪽에 붙는다.

[신한은행] 사파리로 신한 기업뱅킹 첫 화면을 띄운다(로그인은 직접).
[홈택스] 공동인증서 비밀번호를 물어 지난 7일 매출·매입 세금계산서를 엑셀로 받는다.
[지메일 정리] Claude 가 광고 보관·오래된 메일 정리·업무 라벨·중요 메일 요약을 한다(gmail_routine.py).
"""
import json
import os
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import gmail_routine
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
    # (아이콘 파일, 이름, 설명, 메서드 이름) — 순서대로 왼쪽부터 가로로 붙는다
    TILES = [
        ("tile_bank.png", "신한은행", "사파리로 열기", "shinhan"),
        ("tile_hometax.png", "홈택스", "지난 7일 계산서", "hometax"),
        ("tile_gmail.png", "지메일 정리", "광고·라벨·요약", "gmail"),
    ]
    TILE_W = 120

    def __init__(self, root):
        self.root = root
        root.title("은행·홈택스")
        root.resizable(False, False)
        row = tk.Frame(root)
        row.pack(padx=14, pady=(16, 4))
        self.images, self.buttons, self.running = [], {}, set()
        for i, (icon, name, sub, method) in enumerate(self.TILES):
            img = tk.PhotoImage(file=str(Path(__file__).with_name(icon)))
            self.images.append(img)
            cell = tk.Frame(row, width=self.TILE_W)
            cell.grid(row=0, column=i, padx=6)
            # 맥의 tk.Button 은 회색 테두리가 생겨서 아이콘 그림 자체를 누르는 라벨로 쓴다
            btn = tk.Label(cell, image=img, cursor="hand2", borderwidth=0, highlightthickness=0)
            btn.bind("<Button-1>", lambda e, m=method: self.click(m))
            btn.pack()
            tk.Label(cell, text=name, font=("", 13, "bold")).pack(pady=(6, 0))
            tk.Label(cell, text=sub, fg="#777", font=("", 11)).pack()
            self.buttons[method] = btn
        self.status = tk.Label(root, text="", fg="#666", wraplength=self.TILE_W * len(self.TILES), justify="center")
        self.status.pack(padx=14, pady=(6, 12))

    def click(self, method):
        if method in self.running:
            return          # 같은 기능이 아직 도는 중
        getattr(self, method)()

    def busy(self, method, on):
        (self.running.add if on else self.running.discard)(method)
        self.buttons[method].config(cursor="watch" if on else "hand2")

    def shinhan(self):
        open_shinhan()
        self.status.config(text="사파리에서 신한은행 기업뱅킹을 열었습니다. 로그인은 직접 하세요.")

    def hometax(self):
        """비밀번호를 묻는 작은 창. 확인을 누르면 바로 가져온다."""
        win = tk.Toplevel(self.root)
        win.title("홈택스 — 지난 7일 매출·매입")
        win.resizable(False, False)
        win.transient(self.root)
        tk.Label(win, text="공동인증서 비밀번호", font=("", 13)).pack(anchor="w", padx=16, pady=(14, 4))
        entry = tk.Entry(win, show="●", width=28)
        entry.pack(padx=16)
        entry.focus_set()

        def go(_e=None):
            pw = entry.get()
            win.destroy()
            if pw:
                self.fetch(pw)
        bar = tk.Frame(win)
        bar.pack(fill="x", padx=16, pady=12)
        tk.Button(bar, text="가져오기", command=go, default="active").pack(side="right")
        tk.Button(bar, text="취소", command=win.destroy).pack(side="right", padx=6)
        entry.bind("<Return>", go)
        entry.bind("<Escape>", lambda e: win.destroy())
        win.grab_set()

    def gmail(self):
        self.busy("gmail", True)

        def work():
            try:
                report = gmail_routine.run(log=self.log)
                self.root.after(0, lambda: self.show_report(report))
            except Exception as e:
                msg = str(e)
                self.root.after(0, lambda: messagebox.showerror("지메일 정리", msg))
            finally:
                self.root.after(0, lambda: self.busy("gmail", False))

        threading.Thread(target=work, daemon=True).start()

    def show_report(self, report):
        self.status.config(text="지메일 정리 완료")
        win = tk.Toplevel(self.root)
        win.title("지메일 정리 결과")
        win.geometry("620x520")
        box = tk.Text(win, wrap="word", font=("", 13), padx=12, pady=10)
        box.insert("1.0", report)
        box.config(state="disabled")
        box.pack(fill="both", expand=True)

    def log(self, text):
        self.root.after(0, lambda: self.status.config(text=text))

    def fetch(self, password):
        cdir = cert_dir()
        if not cdir:
            messagebox.showerror("은행·홈택스", "공동인증서를 찾지 못했습니다 (~/Library/Preferences/NPKI).")
            return
        self.busy("hometax", True)

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
        self.busy("hometax", False)
        self.status.config(text="홈택스 가져오기 완료" if ok else "홈택스 가져오기 실패")
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
