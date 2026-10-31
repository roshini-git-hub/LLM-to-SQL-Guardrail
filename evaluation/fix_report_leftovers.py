import re
import shutil
from pathlib import Path

p = Path("docs/REPORT.md")
shutil.copy(p, Path("docs/REPORT_backup2.md"))
t = p.read_text(encoding="utf-8")
log = []


def sub(pattern, repl, label, flags=0):
    global t
    t, n = re.subn(pattern, lambda m: repl, t, count=1, flags=flags)
    log.append((label, "done" if n else "NOT FOUND"))


sub(r"^TODO: Roshini.*$",
    "**Team:** Roshini (124cs0048), Navya (124cs0001), Shreya (124cs0040)  \n"
    "**Subject:** Database Management Systems (DBMS)",
    "title block", re.MULTILINE)

sub(r"Because there was no dedicated GPU, model\s+inference most likely ran on the CPU\.\s+TODO: confirm with\s+`ollama ps` \(see below\)\.",
    "Ollama reported that the model ran entirely on the CPU (100% CPU) and used 9.4 GB of memory.",
    "CPU statement")

sub(r"131,072-token context window",
    "context window of up to 131,072 tokens (4,096 tokens were used in these experiments)",
    "context length")

sub(r"\| Ollama server \| TODO: run `ollama --version` \| ?",
    "| Ollama server | 0.40.3 |\n\n",
    "software table row")

p.write_text(t, encoding="utf-8")
for label, status in log:
    print(f"  {label:25s} {status}")
print("\nBackup: docs\\REPORT_backup2.md")
