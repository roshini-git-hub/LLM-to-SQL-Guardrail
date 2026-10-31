import re
import shutil
from pathlib import Path

p = Path("docs/REPORT.md")
shutil.copy(p, Path("docs/REPORT_backup.md"))
t = p.read_text(encoding="utf-8")
log = []


def sub(pattern, repl, label):
    global t
    t, n = re.subn(pattern, lambda m: repl, t, count=1, flags=re.DOTALL)
    log.append((label, "done" if n else "NOT FOUND (already edited?)"))


def insert_before(marker, block, label, guard):
    global t
    if guard in t:
        log.append((label, "already present"))
    elif marker in t:
        t = t.replace(marker, block + "\n" + marker, 1)
        log.append((label, "done"))
    else:
        log.append((label, "NOT FOUND (marker missing)"))


# 1. Title block
sub(r"TODO: team members, course, institution, date\.",
    "**Team:** Roshini (124cs0048), Navya (124cs0001), Shreya (124cs0040)  \n"
    "**Subject:** Database Management Systems (DBMS)",
    "title block")

# 2. Related approaches (no TODO left; references are numbered at the end)
sub(r"TODO: add citations\..*?weak defense\.",
    "Text-to-SQL research has produced large benchmarks such as Spider [1] and BIRD [2] that measure whether "
    "generated SQL returns the correct result; they do not evaluate protection against malicious or "
    "unauthorized queries. SQL injection has a long literature, including a widely cited classification of "
    "attack types and countermeasures [3], and is documented by OWASP [4]. In the database itself, access "
    "control is provided by roles and column privileges and, in PostgreSQL, by row-level security [5], and "
    "the planner's EXPLAIN output gives cost estimates for a query before it runs [6]. Keyword blacklists are "
    "a common but weak defense, as the evaluation in this report shows. This project combines these existing "
    "mechanisms into one pipeline and measures what each layer contributes.",
    "section 2")

# 3. Section 4 pointer
sub(r"TODO: state the model name and size you used and the\s+hardware\.",
    "The language model, test machine and software versions are listed at the end of this section.",
    "section 4 pointer")

# 4. Section 4 details, placed before Section 5
SECTION4 = """**Language model.** The LLM was `gemma4:e4b`, served locally by Ollama: architecture gemma4, 8.0 billion
parameters, Q4_K_M quantization, Apache 2.0 licence. The model supports a context of up to 131,072 tokens,
but the runtime used 4,096 tokens for these experiments, which was enough for the prompts used. The model's
default sampling temperature is 1; every request in this project overrides it to 0 so that results are
repeatable.

**Test machine.** All experiments ran on one laptop: Intel Core i7-13620H CPU, 16 GB RAM, integrated Intel
UHD Graphics (no dedicated GPU), Windows 11 Home Single Language. Ollama reported that the model ran
entirely on the CPU and used 9.4 GB of memory. The time per question reported in Section 6.5 (about 14.5
seconds, almost all of it model generation) reflects this hardware and would differ on a faster machine.

**Software versions.**

| Component | Version |
|---|---|
| Python | 3.12.10 |
| PostgreSQL | 16.15 |
| SQLGlot | 30.23.0 |
| FastAPI | 0.146.0 |
| Streamlit | 1.66.0 |
| Ollama server | 0.40.3 |
| Ollama Python client | 0.6.3 |
"""
insert_before("## 5. Experimental setup", SECTION4, "section 4 details", "**Language model.**")

# 5. Section 5: how the query sets were written
sub(r"TODO: state how the queries were written and what tools or assistance were used, according to\s+your course's rules\.",
    "**Authorship.** The three labeled query sets and the natural-language benchmark questions were drafted "
    "by an AI assistant (Claude, from Anthropic) while the system was being designed, in the order described "
    "above, and the team ran them on its own machine. The assistant also wrote the first versions of the "
    "source code, the evaluation scripts and the draft of this report (see \"Use of AI assistance\" at the "
    "end). Because the same assistant helped design the rules and write the tests, the sets may share blind "
    "spots with the rules; this is listed as a limitation.",
    "section 5 authorship")

# 6. Extra limitations
OLD = "- Only one local model was tried and its SQL quality limits query correctness."
EXTRA = (OLD + "\n"
         "- The query sets were drafted by the same AI assistant that helped design the rules, so they may share "
         "blind spots with the rules; sets written independently, for example from real query logs or by people "
         "who did not see the rules, would be a stronger test.\n"
         "- Timing results (model latency in particular) were measured on one laptop CPU with 16 GB of RAM and "
         "no dedicated GPU, and only one 8.0-billion-parameter, 4-bit quantized model was tried, so SQL quality "
         "and speed may differ with other models and hardware.")
if "drafted by the same AI assistant" in t:
    log.append(("limitations", "already present"))
elif OLD in t:
    t = t.replace(OLD, EXTRA, 1)
    log.append(("limitations", "done"))
else:
    log.append(("limitations", "NOT FOUND"))

# 7. References and AI-use statement, placed before the appendix
TAIL = """## References

1. T. Yu et al., "Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task," Proceedings of EMNLP, 2018.
2. J. Li et al., "Can LLM Already Serve as A Database Interface? A BIg Bench for Large-Scale Database Grounded Text-to-SQLs," NeurIPS Datasets and Benchmarks Track, 2023.
3. W. G. J. Halfond, J. Viegas and A. Orso, "A Classification of SQL Injection Attacks and Countermeasures," Proceedings of the IEEE International Symposium on Secure Software Engineering, 2006.
4. OWASP Foundation, "SQL Injection," OWASP documentation, https://owasp.org (page and access date to be confirmed).
5. The PostgreSQL Global Development Group, PostgreSQL 16 Documentation: "Privileges" and "Row Security Policies."
6. The PostgreSQL Global Development Group, PostgreSQL 16 Documentation: "EXPLAIN."
7. SQLGlot documentation, https://github.com/tobymao/sqlglot.

## Use of AI assistance

An AI assistant (Claude, from Anthropic) was used throughout this project. It produced the first versions
of the source code, the labeled query sets, the evaluation scripts, the dashboard and the draft of this
report, and it explained the design choices. The team installed the software, ran every command and
experiment on its own machine, and the results reported here come from running that code.
"""
insert_before("## Appendix: reproducing the results", TAIL, "references and AI-use statement", "## References")

p.write_text(t, encoding="utf-8")
print()
for label, status in log:
    print(f"  {label:35s} {status}")
print("\nBackup saved as docs\\REPORT_backup.md")
