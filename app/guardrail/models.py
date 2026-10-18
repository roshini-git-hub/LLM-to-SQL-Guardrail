from dataclasses import dataclass, field
from typing import List


@dataclass
class Finding:
    rule: str          # e.g. "forbidden_statement"
    severity: str      # "block" or "warn"
    message: str


@dataclass
class ValidationResult:
    sql: str
    findings: List[Finding] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return any(f.severity == "block" for f in self.findings)

    def add(self, rule: str, severity: str, message: str):
        self.findings.append(Finding(rule, severity, message))