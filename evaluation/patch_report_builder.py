from pathlib import Path

p = Path("evaluation/build_report.py")
t = p.read_text(encoding="utf-8")
done = []

WRITE = '(OUT / "REPORT.md").write_text(report, encoding="utf-8")'
EXTRA = '''extra = ""
for name in ("repair_stress_section.md", "cost_model_section.md"):
    sec = OUT / name
    if sec.exists():
        body = sec.read_text(encoding="utf-8").strip()
        if body.splitlines()[0] not in report:
            extra += body + "\\n\\n"
marker = "## 7. Error analysis: what the evaluation found"
if extra and marker in report:
    report = report.replace(marker, extra + marker, 1)

'''

if "repair_stress_section" not in t:
    if WRITE not in t:
        raise SystemExit("Could not find the line that writes REPORT.md. Paste the last 5 lines of build_report.py.")
    t = t.replace(WRITE, EXTRA + WRITE)
    done.append("added the extra-sections block")
elif '"cost_model_section.md"' not in t:
    t = t.replace('("repair_stress_section.md",)', '("repair_stress_section.md", "cost_model_section.md")')
    done.append("added the cost model section")

OLD = "The unsafe requests in this benchmark were mostly refused by the model itself (it was only told"
NOTE = ("Reading this table: in this run the model made no mistake that the guardrail could detect, so the "
        "three setups scored the same and the repair loop did not fire. The benchmark therefore shows that "
        "the guardrail did not reduce correctness; it does not show a benefit, which the SQL sets and the "
        "repair stress test measure. The questions were also used to decide on the value-hint fix, so they "
        "are not an independent test. Time per question is almost entirely model generation; differences of "
        "a few tens of milliseconds between setups are within noise.")
if "Reading this table" not in t:
    if OLD in t:
        t = t.replace(OLD, NOTE + "\n\n" + OLD, 1)
        done.append("added the benchmark note")
    else:
        done.append("benchmark note NOT added (text not found)")

p.write_text(t, encoding="utf-8")
print("Changes:", done if done else "none needed, already up to date")
