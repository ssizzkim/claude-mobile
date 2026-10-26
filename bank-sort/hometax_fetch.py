# -*- coding: utf-8 -*-
"""홈택스에서 공동인증서로 로그인해 기간 안의 매출·매입 전자세금계산서를 받아
홈택스 「목록조회」 엑셀과 같은 머리글의 .xlsx 로 저장한다(banksort.py 가 그대로 읽는다).

조회·로그인은 오픈소스 hometax 도구(hjsh200219/hometax)의 함수를 그대로 쓴다.
비밀번호는 이 실행 동안 메모리에만 두고 어디에도 저장하지 않는다.
"""
import argparse
import asyncio
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import openpyxl
from openpyxl.styles import Font

SEOUL = timezone(timedelta(hours=9))

# 홈택스 목록조회 엑셀과 같은 머리글(겹치는 이름은 앞=공급자, 뒤=공급받는자)
HEADERS = ["작성일자", "승인번호", "발급일자", "전송일자", "공급자사업자등록번호", "종사업장 번호", "상호", "대표자명", "주소",
           "공급받는자사업자등록번호", "종사업장 번호", "상호", "대표자명", "주소", "합계금액", "공급가액", "세액",
           "전자세금계산서분류", "전자세금계산서종류", "발급유형", "비고", "영수/청구 구분", "공급자 이메일",
           "공급받는자 이메일1", "공급받는자 이메일2", "품목일자", "품목명", "품목규격", "품목수량", "품목단가",
           "품목공급가액", "품목세액", "품목비고"]

# 두벌식: 한글 입력 상태로 친 비밀번호를 실제로 누른 영문 키로 되돌린다
_CHO = "rRseEfaqQtTdwWczxvg"
_JUNG = ["k", "o", "i", "O", "j", "p", "u", "P", "h", "hk", "ho", "hl", "y", "n", "nj", "np", "nl", "b", "m", "ml", "l"]
_JONG = ["", "r", "R", "rt", "s", "sw", "sg", "e", "f", "fr", "fa", "fq", "ft", "fx", "fv", "fg", "a", "q", "qt", "t",
         "T", "d", "w", "c", "z", "x", "v", "g"]
_JAMO = {"ㄱ": "r", "ㄲ": "R", "ㄳ": "rt", "ㄴ": "s", "ㄵ": "sw", "ㄶ": "sg", "ㄷ": "e", "ㄸ": "E", "ㄹ": "f", "ㄺ": "fr",
         "ㄻ": "fa", "ㄼ": "fq", "ㄽ": "ft", "ㄾ": "fx", "ㄿ": "fv", "ㅀ": "fg", "ㅁ": "a", "ㅂ": "q", "ㅃ": "Q", "ㅄ": "qt",
         "ㅅ": "t", "ㅆ": "T", "ㅇ": "d", "ㅈ": "w", "ㅉ": "W", "ㅊ": "c", "ㅋ": "z", "ㅌ": "x", "ㅍ": "v", "ㅎ": "g",
         "ㅏ": "k", "ㅐ": "o", "ㅑ": "i", "ㅒ": "O", "ㅓ": "j", "ㅔ": "p", "ㅕ": "u", "ㅖ": "P", "ㅗ": "h", "ㅘ": "hk",
         "ㅙ": "ho", "ㅚ": "hl", "ㅛ": "y", "ㅜ": "n", "ㅝ": "nj", "ㅞ": "np", "ㅟ": "nl", "ㅠ": "b", "ㅡ": "m", "ㅢ": "ml",
         "ㅣ": "l"}


def keyboard_ascii(text):
    out = []
    for ch in text:
        code = ord(ch) - 0xAC00
        if 0 <= code < 11172:
            out.append(_CHO[code // 588] + _JUNG[(code % 588) // 28] + _JONG[code % 28])
        else:
            out.append(_JAMO.get(ch, ch))
    return "".join(out)


def cert_dir():
    """공동인증서 폴더: 설정 → 예전 앱 설정 → NPKI 에서 '토르크' 인증서."""
    import json
    home = Path(os.environ.get("BANKSORT_HOME", Path.home() / "Library/Application Support/BankSort"))
    for cfg_path, key in ((home / "config.json", "cert_dir"),
                          (Path.home() / "Library/Application Support/BankTaxReport/settings.json", "CERT_DIR")):
        try:
            v = json.loads(cfg_path.read_text("utf-8")).get(key)
            if v and Path(v).is_dir():
                return v
        except Exception:
            pass
    for p in (Path.home() / "Library/Preferences/NPKI").glob("*/USER/*"):
        if "토르크" in p.name and (p / "signCert.der").exists():
            return str(p)
    return None


def today_kst():
    return datetime.now(SEOUL).date()


def last_week():
    end = today_kst()
    return end - timedelta(days=6), end


def dashed_approval(n):
    n = str(n or "").replace("-", "")
    return f"{n[:8]}-{n[8:16]}-{n[16:24]}" if len(n) == 24 else n


def dashed_reg(n):
    n = "".join(ch for ch in str(n or "") if ch.isdigit())
    return f"{n[:3]}-{n[3:5]}-{n[5:]}" if len(n) == 10 else (n or None)


def num_or_none(v):
    if v in (None, ""):
        return None
    try:
        f = float(str(v).replace(",", ""))
        return int(f) if f.is_integer() else f
    except ValueError:
        return v


async def raw_detail(client, item, direction):
    """홈택스 상세 원본에서 거래처 정보를 직접 꺼낸다.
    hometax 도구의 detail() 은 개인 구매자(상호 공백)면 검사에서 떨어뜨리므로 이쪽을 쓴다."""
    from hometax_login import invoices as inv
    svc = client.invoices
    tin, _company = await svc._business()
    data = svc.client._json(await svc.client._request(
        "POST", inv.ET_BASE + "/wqAction.do",
        params={"actionId": "ATEETBDA001R02", "screenId": "UTEETBDA38", "popupYn": "true", "realScreenId": ""},
        json={"etxivIsnBrkdTermDVOPrmt": {"etan": item.approval_number, "screenId": inv.LIST_SCREEN,
                                          "pageNum": "1", "slsPrhClCd": "01" if direction == "sales" else "02",
                                          "etxivTin": tin, "etxivClCd": "", "etxivClsfCd": "",
                                          "etxivMpbNo": svc.business_mpb_no}}))
    body = data.get("etxivIsnBrkdTermDVO") or {}
    lines = data.get("lsatInfrBizSVOList") or []
    s = lambda k: (str(body.get(k)).strip() or None) if body.get(k) not in (None, "") else None
    first = lines[0] if lines and isinstance(lines[0], dict) else {}
    return {
        "sup_reg": s("splrTxprDscmNo"), "sup_name": s("splrTnmNm"), "sup_rep": s("splrRprsFnm"), "sup_addr": s("splrPfbAdr"),
        "sup_mail": s("splrMchrgEmlAdr"),
        "cus_reg": s("dmnrTxprDscmNo"), "cus_name": s("dmnrTnmNm"), "cus_rep": s("dmnrRprsFnm"), "cus_addr": s("dmnrPfbAdr"),
        "cus_mail": s("dmnrMchrgEmlAdr"),
        "line_name": first.get("lsatNm"), "line_date": first.get("lsatSplDt"), "line_spec": first.get("lsatRszeNm"),
        "line_qty": first.get("lsatQty"), "line_price": first.get("lsatUtprc"), "line_remark": first.get("lsatRmrkCntn"),
        "line_supply": first.get("lsatSplCft"), "line_tax": first.get("lsatTxamt"),
    }


async def _fetch(start, end, cert_dir, password, log):
    from hometax_login import cli
    os.environ["HOMETAX_PW"] = password
    args = argparse.Namespace(cert=str(cert_dir) if cert_dir else None, company=None, choose=False,
                              remember=False, no_remember=True, json=True)
    try:
        log("홈택스 로그인 중...")
        client, _identity = await cli.session_client(args)
        result = {}
        try:
            for direction, label in (("sales", "매출"), ("purchases", "매입")):
                log(f"{label} 세금계산서 목록 조회 중...")
                items = await cli.fetch_invoices(client, start, end, direction, "issued")
                rows = []
                for i, item in enumerate(items, 1):
                    log(f"{label} 상세 {i}/{len(items)}")
                    try:
                        detail = await raw_detail(client, item, direction)
                    except Exception:
                        detail = None
                    rows.append((item, detail))
                    await asyncio.sleep(0.2)
                result[label] = rows
        finally:
            await client.close()
        return result
    finally:
        os.environ.pop("HOMETAX_PW", None)


def to_row(item, d):
    d = d or {}
    return [item.written_date.isoformat(), dashed_approval(item.approval_number), item.issued_date.isoformat(),
            item.transmitted_date.isoformat() if item.transmitted_date else None,
            dashed_reg(d.get("sup_reg")), None, d.get("sup_name"), d.get("sup_rep"), d.get("sup_addr"),
            dashed_reg(d.get("cus_reg")), None, d.get("cus_name"), d.get("cus_rep"), d.get("cus_addr"),
            item.total_amount, item.supply_amount, item.tax_amount,
            "세금계산서", "일반", None, d.get("line_remark"), None, d.get("sup_mail"), d.get("cus_mail"), None,
            d.get("line_date"), d.get("line_name") or item.item_name, d.get("line_spec"),
            num_or_none(d.get("line_qty")), num_or_none(d.get("line_price")),
            num_or_none(d.get("line_supply")), num_or_none(d.get("line_tax")), None]


def fill_sheet(ws, label, rows, start, end):
    ws.title = label
    ws.append([f"전자세금계산서 {label} 목록 (홈택스 자동 조회, 발급일 기준)"])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([f"조회기간 {start.isoformat()} ~ {end.isoformat()}"])
    ws.append([])
    ws.append(HEADERS)
    for c in ws[4]:
        c.font = Font(bold=True)
    for item, detail in rows:
        ws.append(to_row(item, detail))


def save_both(data, start, end, folder):
    """매출·매입을 엑셀 파일 하나에 시트 두 개로 저장한다(파일명 끝에 받은 시각, 초까지)."""
    wb = openpyxl.Workbook()
    fill_sheet(wb.active, "매출", data.get("매출", []), start, end)
    fill_sheet(wb.create_sheet(), "매입", data.get("매입", []), start, end)
    stamp = datetime.now(SEOUL).strftime("%Y%m%d_%H%M%S")
    path = Path(folder) / f"홈택스_세금계산서_{start:%Y%m%d}-{end:%Y%m%d}_{stamp}.xlsx"
    wb.save(str(path))
    return path


def save(label, rows, start, end, folder):
    """시트 하나짜리(시험용)."""
    wb = openpyxl.Workbook()
    fill_sheet(wb.active, label, rows, start, end)
    stamp = datetime.now(SEOUL).strftime("%Y%m%d_%H%M%S")
    path = Path(folder) / f"{label}전자세금계산서목록_자동_{start:%Y%m%d}-{end:%Y%m%d}_{stamp}.xlsx"
    wb.save(str(path))
    return path


def fetch_last_week(password, cert_dir=None, folder=None, log=print):
    """지난 7일(오늘 포함) 매출·매입을 받아 엑셀 두 개로 저장하고 (경로들, 건수) 를 돌려준다."""
    if any(0xAC00 <= ord(c) <= 0xD7A3 or 0x3131 <= ord(c) <= 0x3163 for c in password):
        password = keyboard_ascii(password)
        log("비밀번호가 한글 입력 상태로 들어와 영문 키로 바꿨습니다.")
    start, end = last_week()
    data = asyncio.run(_fetch(start, end, cert_dir, password, log))
    folder = Path(folder or Path.home() / "Downloads")
    counts = {label: len(data.get(label, [])) for label in ("매출", "매입")}
    return [save_both(data, start, end, folder)], counts, (start, end)
