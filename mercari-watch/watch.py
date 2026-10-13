"""Mercari Japan keyword watcher.

Searches jp.mercari.com for each watch in config.json and emails any listings
that were not seen on a previous run. Seen item IDs are kept in a state file
(restored between GitHub Actions runs via actions/cache).

Environment:
  GMAIL_USER          Gmail address used to send (required unless DRY_RUN=1)
  GMAIL_APP_PASSWORD  Gmail app password (required unless DRY_RUN=1)
  MAIL_TO             Recipient (defaults to GMAIL_USER)
  WATCH_CONFIG        Optional JSON that overrides config.json (keeps keywords private)
  STATE_FILE          Path of the seen-IDs file (default: seen.json next to this script)
  DRY_RUN=1           Print new items instead of sending email
"""

import base64
import html
import json
import os
import re
import smtplib
import sys
import time
import urllib.error
import urllib.request
import uuid
from email.mime.text import MIMEText
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

SEARCH_URL = "https://api.mercari.jp/v2/entities:search"
HERE = Path(__file__).resolve().parent
MAX_SEEN_PER_WATCH = 3000


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def dpop_token(key: ec.EllipticCurvePrivateKey, url: str, method: str) -> str:
    """Mercari's web API requires a DPoP proof JWT signed with an ES256 key."""
    nums = key.public_key().public_numbers()
    header = {
        "typ": "dpop+jwt",
        "alg": "ES256",
        "jwk": {
            "crv": "P-256",
            "kty": "EC",
            "x": b64url(nums.x.to_bytes(32, "big")),
            "y": b64url(nums.y.to_bytes(32, "big")),
        },
    }
    payload = {
        "iat": int(time.time()),
        "jti": str(uuid.uuid4()),
        "htu": url,
        "htm": method,
        "uuid": str(uuid.uuid4()),
    }
    signing_input = (
        b64url(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + b64url(json.dumps(payload, separators=(",", ":")).encode())
    )
    r, s = decode_dss_signature(key.sign(signing_input.encode(), ec.ECDSA(hashes.SHA256())))
    return signing_input + "." + b64url(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


def search(key, watch: dict) -> list:
    body = {
        "userId": "",
        "pageSize": 120,
        "pageToken": "",
        "searchSessionId": uuid.uuid4().hex,
        "indexRouting": "INDEX_ROUTING_UNSPECIFIED",
        "thumbnailTypes": [],
        "searchCondition": {
            "keyword": watch["keyword"],
            "excludeKeyword": watch.get("exclude", ""),
            "sort": "SORT_CREATED_TIME",
            "order": "ORDER_DESC",
            "status": ["STATUS_ON_SALE"],
            "sizeId": [],
            "categoryId": [],
            "brandId": [],
            "sellerId": [],
            "priceMin": int(watch.get("price_min") or 0),
            "priceMax": int(watch.get("price_max") or 0),
            "itemConditionId": [],
            "shippingPayerId": [],
            "shippingFromArea": [],
            "shippingMethod": [],
            "colorId": [],
            "hasCoupon": False,
            "attributes": [],
            "itemTypes": [],
            "skuIds": [],
        },
        "defaultDatasets": ["DATASET_TYPE_MERCARI", "DATASET_TYPE_BEYOND"],
        "serviceFrom": "suruga",
        "withItemBrand": True,
        "withItemSize": False,
        "withItemPromotions": True,
        "withItemSizes": True,
        "withShopname": False,
    }
    req = urllib.request.Request(
        SEARCH_URL,
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "DPoP": dpop_token(key, SEARCH_URL, "POST"),
            "X-Platform": "web",
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "*/*",
            "Accept-Language": "ja",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp).get("items", [])


def title_matches(name: str, words: list) -> bool:
    """True if the title contains any of the words (case-insensitive).

    Latin words must stand alone ("ti" matches "Sol Ti" / "SOL-TI" but not "edition");
    Japanese words match anywhere in the title.
    """
    if not words:
        return True
    for w in words:
        if w.isascii():
            if re.search(rf"(?<![a-z]){re.escape(w.lower())}(?![a-z])", name.lower()):
                return True
        elif w in name:
            return True
    return False


def item_url(item: dict) -> str:
    if item.get("itemType") == "ITEM_TYPE_BEYOND":
        return f"https://jp.mercari.com/shops/product/{item['id']}"
    return f"https://jp.mercari.com/item/{item['id']}"


def render_email(found: list) -> str:
    rows = []
    for watch, items in found:
        rows.append(f"<h2 style='font-size:16px;margin:20px 0 8px'>🔎 {html.escape(watch['keyword'])}</h2>")
        for it in items:
            thumb = (it.get("thumbnails") or [""])[0]
            rows.append(
                "<table style='margin:0 0 10px;border-collapse:collapse'><tr>"
                f"<td style='padding-right:10px'><a href='{item_url(it)}'>"
                f"<img src='{html.escape(thumb)}' width='90' height='90' style='object-fit:cover;border-radius:6px'></a></td>"
                f"<td style='vertical-align:top;font-family:sans-serif'>"
                f"<a href='{item_url(it)}' style='color:#111;font-weight:bold;text-decoration:none'>{html.escape(it.get('name', ''))}</a>"
                f"<div style='color:#e0303c;font-size:16px;margin-top:4px'>¥{int(it.get('price', 0)):,}</div>"
                "</td></tr></table>"
            )
    return "<div style='font-family:sans-serif'>" + "".join(rows) + "</div>"


def send_email(subject: str, body_html: str) -> None:
    user = os.environ["GMAIL_USER"]
    to = os.environ.get("MAIL_TO") or user
    msg = MIMEText(body_html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(user, os.environ["GMAIL_APP_PASSWORD"])
        smtp.send_message(msg)


def main() -> int:
    raw = os.environ.get("WATCH_CONFIG") or (HERE / "config.json").read_text(encoding="utf-8")
    watches = [w for w in json.loads(raw)["watches"] if w.get("keyword")]
    state_path = Path(os.environ.get("STATE_FILE") or HERE / "seen.json")
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    dry_run = os.environ.get("DRY_RUN") == "1"

    key = ec.generate_private_key(ec.SECP256R1())
    found, failures, alerted = [], 0, set()
    for watch in watches:
        state_key = json.dumps([watch["keyword"], watch.get("exclude", ""),
                                watch.get("price_min", 0), watch.get("price_max", 0)], ensure_ascii=False)
        try:
            items = search(key, watch)
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            print(f"[error] {watch['keyword']}: {e}", file=sys.stderr)
            failures += 1
            continue
        seen = state.get(state_key)
        ids = [it["id"] for it in items]
        if seen is None:
            # First run for this watch: remember current listings without alerting.
            print(f"[init] {watch['keyword']}: {len(ids)} existing items recorded")
            state[state_key] = ids
            continue
        seen_set = set(seen)
        # Skip items another watch already reported in this run (overlapping keywords).
        new = [it for it in items if it["id"] not in seen_set and it["id"] not in alerted
               and title_matches(it.get("name", ""), watch.get("title_any", []))]
        alerted.update(it["id"] for it in new)
        print(f"[ok] {watch['keyword']}: {len(items)} fetched, {len(new)} new")
        if new:
            found.append((watch, new))
        state[state_key] = (ids + [i for i in seen if i not in set(ids)])[:MAX_SEEN_PER_WATCH]

    if found:
        total = sum(len(items) for _, items in found)
        names = ", ".join(w["keyword"] for w, _ in found)
        subject = f"[メルカリ] 새 상품 {total}건 - {names}"
        if dry_run:
            print(subject)
            for watch, items in found:
                for it in items:
                    print(f"  {watch['keyword']} | ¥{it.get('price')} | {it.get('name')} | {item_url(it)}")
        else:
            send_email(subject, render_email(found))
            print(f"[mail] sent: {subject}")

    # Save state only after the email went out, so a failed send is retried next run.
    state_path.write_text(json.dumps(state, ensure_ascii=False))
    return 1 if watches and failures == len(watches) else 0


if __name__ == "__main__":
    sys.exit(main())
