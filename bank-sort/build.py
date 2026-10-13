# BankSort.bas.in → BankSort.bas (ASCII 전용). {K:한글} 은 U("코드,...") 로, 주석의 한글은 지운다.
import re, sys, pathlib
here = pathlib.Path(__file__).parent
src = (here / "BankSort.bas.in").read_text("utf-8")
src = re.sub(r"\{K:(.*?)\}", lambda m: 'U("' + ",".join(str(ord(c)) for c in m.group(1)) + '")', src)
out = []
for line in src.splitlines():
    if line.lstrip().startswith("'"):
        line = "".join(c for c in line if ord(c) < 128).rstrip()
        if line.strip() == "'":
            continue
    out.append(line)
text = "\r\n".join(out) + "\r\n"
assert all(ord(c) < 128 for c in text), "non-ASCII left"
dst = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else here / "BankSort.bas"
dst.write_text(text, "ascii")
print(dst)
