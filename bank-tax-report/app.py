"""맥 앱 화면: 신한은행 기업 거래·이체 + 홈택스 세금계산서 → 엑셀.

install_mac.command 가 만든 「거래·세금계산서 조회.app」이 이 파일을 실행한다.
조회·엑셀 생성은 report.py 의 run() 을 그대로 쓴다.
"""

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

APP_NAME = "거래·세금계산서 조회"
SUPPORT = Path.home() / "Library" / "Application Support" / "BankTaxReport"
os.environ.setdefault("BTR_HOME", str(SUPPORT))
SETTINGS_FILE = SUPPORT / "settings.json"  # CODEF 키 등. 인증서 비밀번호는 저장하지 않음
DEFAULT_OUTPUT = Path.home() / "Documents" / "거래_세금계산서"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import report  # noqa: E402

SETTING_KEYS = {
    "CODEF_CLIENT_ID": "Client ID",
    "CODEF_CLIENT_SECRET": "Client Secret",
    "CODEF_PUBLIC_KEY": "Public Key",
    "CODEF_ENV": "환경 (demo / production)",
    "SHINHAN_ACCOUNTS": "신한 계좌번호 (쉼표, 비우면 전체)",
}


# ------------------------------------------------------------------ 설정 파일


def load_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(settings: dict) -> None:
    SUPPORT.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(SETTINGS_FILE, 0o600)


# ------------------------------------------------------------------ 인증서 찾기


def npki_roots() -> list[Path]:
    roots = [Path.home() / "Library" / "Preferences" / "NPKI", Path.home() / "NPKI"]
    roots += sorted(Path("/Volumes").glob("*/NPKI"))  # USB
    return [r for r in roots if r.is_dir()]


def find_certificates() -> list[tuple[str, Path]]:
    """(표시 이름, 폴더) 목록. 만료되지 않은 것만, 만료일이 늦은 순."""
    from cryptography import x509
    from cryptography.x509.oid import NameOID

    found, seen = [], set()
    for root in npki_roots():
        for der in root.rglob("signCert.der"):
            folder = der.parent
            if not (folder / "signPri.key").is_file():
                continue
            try:
                cert = x509.load_der_x509_certificate(der.read_bytes())
            except (OSError, ValueError):
                continue
            if cert.fingerprint(cert.signature_hash_algorithm) in seen:
                continue
            seen.add(cert.fingerprint(cert.signature_hash_algorithm))
            until = cert.not_valid_after_utc.date()
            if until < date.today():
                continue
            names = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
            name = str(names[0].value) if names else folder.name
            found.append((until, f"{name}  —  {until}까지", folder))
    found.sort(key=lambda item: item[0], reverse=True)
    return [(label, folder) for _, label, folder in found]


# ------------------------------------------------------------------ 화면


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.settings = load_settings()
        self.messages: queue.Queue = queue.Queue()
        self.certs: list[tuple[str, Path]] = []
        self.last_output: Path | None = None

        root.title(APP_NAME)
        root.minsize(620, 560)
        frame = ttk.Frame(root, padding=16)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        row = 0

        ttk.Label(frame, text=APP_NAME, font=("", 18, "bold")).grid(row=row, column=0, columnspan=3, sticky="w")
        row += 1
        ttk.Label(frame, text="신한은행 기업 계좌 거래·이체내역 + 홈택스 세금계산서 발급·수취내역 → 엑셀",
                  foreground="#666").grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 12))  # fmt: skip
        row += 1

        # 인증서
        ttk.Label(frame, text="공동인증서").grid(row=row, column=0, sticky="w")
        self.cert_var = tk.StringVar()
        self.cert_box = ttk.Combobox(frame, textvariable=self.cert_var, state="readonly")
        self.cert_box.grid(row=row, column=1, sticky="ew", padx=8)
        ttk.Button(frame, text="폴더 선택…", command=self.pick_cert_folder).grid(row=row, column=2)
        row += 1

        ttk.Label(frame, text="인증서 비밀번호").grid(row=row, column=0, sticky="w", pady=6)
        self.password = ttk.Entry(frame, show="•")
        self.password.grid(row=row, column=1, sticky="ew", padx=8, pady=6)
        row += 1

        # 기간
        ttk.Label(frame, text="조회 기간").grid(row=row, column=0, sticky="w")
        period = ttk.Frame(frame)
        period.grid(row=row, column=1, columnspan=2, sticky="w", padx=8)
        self.start_var, self.end_var = tk.StringVar(), tk.StringVar()
        ttk.Entry(period, textvariable=self.start_var, width=12).pack(side="left")
        ttk.Label(period, text=" ~ ").pack(side="left")
        ttk.Entry(period, textvariable=self.end_var, width=12).pack(side="left")
        ttk.Button(period, text="최근 7일", command=self.last_7_days).pack(side="left", padx=(10, 0))
        ttk.Button(period, text="지난주(월~일)", command=self.last_week).pack(side="left", padx=4)
        self.last_7_days()
        row += 1

        # 대상
        ttk.Label(frame, text="조회 대상").grid(row=row, column=0, sticky="w", pady=6)
        targets = ttk.Frame(frame)
        targets.grid(row=row, column=1, columnspan=2, sticky="w", padx=8, pady=6)
        self.bank_on, self.hometax_on = tk.BooleanVar(value=True), tk.BooleanVar(value=True)
        ttk.Checkbutton(targets, text="신한은행 거래·이체", variable=self.bank_on).pack(side="left")
        ttk.Checkbutton(targets, text="홈택스 세금계산서", variable=self.hometax_on).pack(side="left", padx=12)
        row += 1

        # 저장 폴더
        ttk.Label(frame, text="저장 폴더").grid(row=row, column=0, sticky="w")
        self.output_var = tk.StringVar(value=self.settings.get("OUTPUT_DIR") or str(DEFAULT_OUTPUT))
        ttk.Entry(frame, textvariable=self.output_var).grid(row=row, column=1, sticky="ew", padx=8)
        ttk.Button(frame, text="변경…", command=self.pick_output).grid(row=row, column=2)
        row += 1

        # 버튼
        buttons = ttk.Frame(frame)
        buttons.grid(row=row, column=0, columnspan=3, sticky="ew", pady=14)
        self.run_button = ttk.Button(buttons, text="조회하고 엑셀 저장", command=self.start)
        self.run_button.pack(side="left")
        ttk.Button(buttons, text="CODEF 설정…", command=self.open_settings).pack(side="left", padx=8)
        ttk.Button(buttons, text="데모 엑셀", command=lambda: self.start(demo=True)).pack(side="left")
        self.open_button = ttk.Button(buttons, text="엑셀 열기", command=self.open_output, state="disabled")
        self.open_button.pack(side="right")
        row += 1

        # 진행 로그
        frame.rowconfigure(row, weight=1)
        self.log = tk.Text(frame, height=12, wrap="word", state="disabled", relief="solid", borderwidth=1)
        self.log.grid(row=row, column=0, columnspan=3, sticky="nsew")

        self.refresh_certs()
        if not self.settings.get("CODEF_CLIENT_ID"):
            self.write("처음이면 [CODEF 설정…]에서 CODEF 키를 넣어 주세요(신한은행 조회용).")
            self.write("홈택스만 조회할 거면 키 없이 [신한은행] 체크를 끄고 실행하면 됩니다.")
        root.after(100, self.drain)

    # -- 입력 도우미

    def last_7_days(self):
        end = report.today_kst()
        self.start_var.set(str(end - timedelta(days=6)))
        self.end_var.set(str(end))

    def last_week(self):
        today = report.today_kst()
        monday = today - timedelta(days=today.weekday() + 7)
        self.start_var.set(str(monday))
        self.end_var.set(str(monday + timedelta(days=6)))

    def refresh_certs(self, prefer: Path | None = None):
        self.certs = find_certificates()
        if prefer and all(folder != prefer for _, folder in self.certs):
            self.certs.insert(0, (f"{prefer.name}  [{prefer}]", prefer))
        self.cert_box["values"] = [label for label, _ in self.certs]
        remembered = prefer or Path(self.settings.get("CERT_DIR", "/nonexistent"))
        index = next((i for i, (_, f) in enumerate(self.certs) if f == remembered), 0)
        if self.certs:
            self.cert_box.current(index)
        else:
            self.write("인증서를 찾지 못했습니다. [폴더 선택…]으로 signCert.der 가 있는 폴더를 고르세요.")

    def pick_cert_folder(self):
        start = npki_roots()[0] if npki_roots() else Path.home()
        chosen = filedialog.askdirectory(title="signCert.der 가 들어 있는 폴더", initialdir=start)
        if chosen:
            folder = Path(chosen)
            if not (folder / "signCert.der").is_file():
                messagebox.showerror(APP_NAME, "이 폴더에 signCert.der / signPri.key 가 없습니다.")
                return
            self.refresh_certs(prefer=folder)

    def pick_output(self):
        chosen = filedialog.askdirectory(title="엑셀 저장 폴더", initialdir=self.output_var.get())
        if chosen:
            self.output_var.set(chosen)

    def selected_cert(self) -> Path | None:
        index = self.cert_box.current()
        return self.certs[index][1] if 0 <= index < len(self.certs) else None

    # -- CODEF 설정 창

    def open_settings(self):
        window = tk.Toplevel(self.root)
        window.title("CODEF 설정")
        window.transient(self.root)
        body = ttk.Frame(window, padding=16)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        ttk.Label(body, text="codef.io → 로그인 → 키 관리 화면의 값을 붙여 넣으세요.",
                  foreground="#666").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))  # fmt: skip
        entries = {}
        for i, (key, label) in enumerate(SETTING_KEYS.items(), start=1):
            ttk.Label(body, text=label).grid(row=i, column=0, sticky="w", pady=3)
            default = "demo" if key == "CODEF_ENV" else ""
            var = tk.StringVar(value=self.settings.get(key, default))
            ttk.Entry(body, textvariable=var, width=52,
                      show="•" if key == "CODEF_CLIENT_SECRET" else "").grid(row=i, column=1, sticky="ew", padx=8)  # fmt: skip
            entries[key] = var

        def save():
            for key, var in entries.items():
                self.settings[key] = var.get().strip()
            if self.settings.get("CODEF_ENV") not in report.CODEF_DOMAINS:
                messagebox.showerror("CODEF 설정", "환경은 demo 또는 production 이어야 합니다.", parent=window)
                return
            save_settings(self.settings)
            window.destroy()
            self.write("CODEF 설정을 저장했습니다.")

        ttk.Button(body, text="저장", command=save).grid(row=len(SETTING_KEYS) + 1, column=1, sticky="e", pady=(12, 0))

    # -- 실행

    def start(self, demo: bool = False):
        try:
            start = date.fromisoformat(self.start_var.get().strip())
            end = date.fromisoformat(self.end_var.get().strip())
        except ValueError:
            messagebox.showerror(APP_NAME, "날짜는 2026-10-07 형식으로 입력하세요.")
            return
        if start > end or end > report.today_kst():
            messagebox.showerror(APP_NAME, "기간을 확인하세요(시작일 ≤ 종료일 ≤ 오늘).")
            return
        cert_dir, password = self.selected_cert(), self.password.get()
        if not demo:
            if not (self.bank_on.get() or self.hometax_on.get()):
                messagebox.showerror(APP_NAME, "조회 대상을 하나 이상 고르세요.")
                return
            if not cert_dir or not password:
                messagebox.showerror(APP_NAME, "공동인증서와 비밀번호를 입력하세요.")
                return
            if self.bank_on.get() and not self.settings.get("CODEF_CLIENT_ID"):
                messagebox.showerror(APP_NAME, "신한은행 조회에는 CODEF 설정이 필요합니다. [CODEF 설정…]을 눌러 주세요.")
                return

        # report.py 가 읽는 환경 변수로 설정 전달
        for key in SETTING_KEYS:
            os.environ[key] = self.settings.get(key, "")
        os.environ["OUTPUT_DIR"] = self.output_var.get().strip() or str(DEFAULT_OUTPUT)
        if cert_dir:
            self.settings["CERT_DIR"] = str(cert_dir)
        self.settings["OUTPUT_DIR"] = os.environ["OUTPUT_DIR"]
        save_settings(self.settings)

        self.run_button.configure(state="disabled")
        self.open_button.configure(state="disabled")
        self.clear()
        self.demo = demo
        options = dict(cert_dir=cert_dir, password=password, bank_on=self.bank_on.get(),
                       hometax_on=self.hometax_on.get(), demo=demo, log=self.messages.put)  # fmt: skip
        threading.Thread(target=self.work, args=(start, end, options), daemon=True).start()

    def work(self, start, end, options):
        try:
            out, warnings = report.run(start, end, **options)
            self.messages.put(("done", out, warnings))
        except Exception as error:  # 화면에 보여 주고 끝낸다
            self.messages.put(("error", str(error), None))

    def drain(self):
        while not self.messages.empty():
            item = self.messages.get()
            if isinstance(item, tuple):
                self.finish(*item)
            else:
                self.write(item)
        self.root.after(100, self.drain)

    def finish(self, kind, value, warnings):
        self.run_button.configure(state="normal")
        if kind == "error":
            self.write(f"오류: {value}")
            messagebox.showerror(APP_NAME, value)
            return
        self.last_output = value
        self.open_button.configure(state="normal")
        if warnings and not self.demo:
            messagebox.showwarning(APP_NAME, "엑셀을 저장했지만 일부 조회에 문제가 있었습니다.\n\n" + "\n".join(warnings))
        self.open_output()

    def open_output(self):
        if self.last_output and self.last_output.exists():
            subprocess.run(["open", str(self.last_output)], check=False)

    # -- 로그

    def write(self, text: str):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def clear(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")


def main():
    root = tk.Tk()
    App(root)
    root.lift()
    root.attributes("-topmost", True)
    root.after(300, lambda: root.attributes("-topmost", False))
    root.mainloop()


if __name__ == "__main__":
    main()
