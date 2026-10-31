import re
from pathlib import Path

D = Path("dashboard")
OK, REVIEW, BLOCK = r"\u2705", r"\u26a0\ufe0f", r"\u26d4"
GOOD = {"Orders per status", "Average price", "Top customers", "Normal query", "Uses CASE"}
log = []


def const(s):
    return lambda m: s


def edit(name, rules):
    p = D / name
    if not p.exists():
        log.append((name, "missing, skipped"))
        return
    t = p.read_text(encoding="utf-8", errors="replace")
    total = 0
    for pat, repl in rules:
        t, n = re.subn(pat, repl, t)
        total += n
    p.write_text(t, encoding="utf-8")
    log.append((name, f"{total} edits"))


def icon(code):
    return (r'page_icon="[^"]*"', const('page_icon="' + code + '"'))


def title(name, code):
    return (r'st\.title\("[^"]*' + re.escape(name) + r'"\)',
            const('st.title("' + code + " " + name + '")'))


edit("common.py", [
    (r'("ALLOW": \("Safe to run", )"[^"]*"', lambda m: m.group(1) + '"' + OK + '"'),
    (r'("REVIEW": \("Needs a human check", )"[^"]*"', lambda m: m.group(1) + '"' + REVIEW + '"'),
    (r'("BLOCK": \("Blocked", )"[^"]*"', lambda m: m.group(1) + '"' + BLOCK + '"'),
    (r'icons = \{[^}]*\}',
     const('icons = {"ok": "' + OK + '", "fail": "' + r'\u274c' + '", "warn": "' + REVIEW +
           '", "skip": "' + r'\u23ed\ufe0f' + '"}')),
])

edit("Home.py", [
    icon(r'\U0001F6E1'),
    title("SQL Guardrail", r'\U0001F6E1\ufe0f'),
    (r"'\?{1,4} Safe to run</div>", const("'" + OK + " Safe to run</div>")),
    (r"'\?{1,4} Needs a human check</div>", const("'" + REVIEW + " Needs a human check</div>")),
    (r"'\?{1,4} Blocked</div>", const("'" + BLOCK + " Blocked</div>")),
])

edit("pages/1_Try_it.py", [
    icon(r'\U0001F9EA'),
    title("Try it", r'\U0001F9EA'),
    (r'st\.tabs\(\[[^\]]*\]\)',
     const('st.tabs(["' + r'\U0001F4AC' + ' Ask in plain English", "' + r'\U0001F4DD' + ' Paste SQL"])')),
    (r'\("\?{1,4} ([^"]+)",',
     lambda m: '("' + (OK if m.group(1) in GOOD else BLOCK) + " " + m.group(1) + '",'),
])

edit("pages/2_History.py", [
    icon(r'\U0001F4DC'),
    title("History", r'\U0001F4DC'),
    (r'LABELS = \{[^}]*\}',
     const('LABELS = {"ALLOW": "' + OK + ' Safe", "REVIEW": "' + REVIEW + ' Review", "BLOCK": "' + BLOCK + ' Blocked"}')),
])

edit("pages/3_Results.py", [icon(r'\U0001F4CA'), title("Results", r'\U0001F4CA')])
edit("pages/4_Detailed_results.py", [icon(r'\U0001F4CA')])
edit("pages/5_Question_tests.py", [icon(r'\U0001F4AC')])

for name, status in log:
    print(f"  {name:32s} {status}")

# Report any corrupted icon that is still left
left = re.compile(r'''["']\?{1,4}["' ]''')
print()
found = False
for p in sorted(D.rglob("*.py")):
    for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if left.search(line):
            print(f"  still has a '?': {p}:{i}: {line.strip()[:90]}")
            found = True
if not found:
    print("  No corrupted icons left.")
