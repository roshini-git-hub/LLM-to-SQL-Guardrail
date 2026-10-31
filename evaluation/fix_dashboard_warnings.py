from pathlib import Path

changed = []
for p in sorted(Path("dashboard").rglob("*.py")):
    t = p.read_text(encoding="utf-8")
    new = (t.replace("use_container_width=True", 'width="stretch"')
            .replace("use_container_width=False", 'width="content"')
            .replace('("Unknown", "?", "")', '("Unknown", "\\u2754", "")'))
    if new != t:
        p.write_text(new, encoding="utf-8")
        changed.append(str(p))

print("Files updated:")
for c in changed:
    print("  ", c)

left = [str(p) for p in Path("dashboard").rglob("*.py")
        if "use_container_width" in p.read_text(encoding="utf-8")]
print("\nStill using the old setting:", left if left else "none")
