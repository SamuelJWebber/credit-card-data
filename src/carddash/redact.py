"""Keep credentials out of everything the pipeline writes.

This repository is public and the nightly job commits data/ and docs/. GitHub masks secrets in the Actions log only,
not in committed files, so a credential that reaches health.json, the page or a raw file is published. Two layers:

- `redact()`: every health message passes through it before it is stored or printed. It removes the literal values
  of the secrets the pipeline holds (SECRET_ENV_VARS) and the value of anything that looks like a credential in a
  query string. requests puts the full URL, query string included, into the text of an HTTPError or a
  ConnectionError, and FRED takes its key in the query string: that is the path this closes.
- `scan_paths()`: the workflow's last step before `git add` (`carddash scan-secrets`). It fails closed if any file
  under the given paths carries one of those values or a credential-shaped query parameter, and it reports where
  without printing what it found.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

SECRET_ENV_VARS = ("FRED_API_KEY", "CARDDASH_CONTACT")  # the contact is an address the SEC requires, not public
PLACEHOLDER = "[redacted]"
MIN_SECRET_LEN = 6  # an unset or one-letter variable must not turn every 'a' on the page into [redacted]

# Redaction is deliberately broad: a word-bounded credential name followed by '=' anywhere in a message.
_REDACT = re.compile(
    r"(?i)\b(api[_-]?key|apikey|access[_-]?token|auth[_-]?token|client[_-]?secret|password|passwd|token|secret|key"
    r"|sig|signature)=(?!\[redacted\])([^&\s\"'<>]+)"
)
# The scan has to be right every night or the commit is refused, so it is narrower: names that only ever mean a
# credential anywhere, and the generic ones only as a query parameter, with a value long enough to be one.
_STRONG = re.compile(
    r"(?i)\b(api[_-]?key|apikey|access[_-]?token|auth[_-]?token|client[_-]?secret|password|passwd)="
    r"(?!\[redacted\])[^&\s\"'<>]{6,}"
)
_WEAK = re.compile(r"(?i)[?&](token|key|secret|sig|signature)=(?!\[redacted\])[^&\s\"'<>]{6,}")
TEXT_SUFFIXES = {".csv", ".json", ".html", ".htm", ".txt", ".yaml", ".yml", ".md", ".xml", ".js", ".css", ".svg", ".tsv"}


def secret_values() -> dict[str, str]:
    """name -> value for each secret set in the environment (values shorter than MIN_SECRET_LEN are ignored)."""
    out = {}
    for name in SECRET_ENV_VARS:
        value = (os.environ.get(name) or "").strip()
        if len(value) >= MIN_SECRET_LEN:
            out[name] = value
    return out


def redact(text: str) -> str:
    if not text:
        return text
    for value in secret_values().values():
        text = text.replace(value, PLACEHOLDER)
    return _REDACT.sub(lambda m: f"{m.group(1)}={PLACEHOLDER}", text)


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int  # 1-based; 0 for a binary file, where a line means nothing
    kind: str

    def __str__(self) -> str:  # never the matched text: the point is not to print the secret
        return f"{self.path}:{self.line}: {self.kind}" if self.line else f"{self.path}: {self.kind}"


def _files(paths: list[Path]):
    for p in paths:
        if p.is_file():
            yield p
        elif p.is_dir():
            yield from sorted(q for q in p.rglob("*") if q.is_file() and ".git" not in q.parts)


def scan_paths(paths: list[Path]) -> list[Finding]:
    """Every place under `paths` that carries a secret value or a credential in a query string."""
    secrets = {name: value.encode("utf-8") for name, value in secret_values().items()}
    found: list[Finding] = []
    for f in _files([Path(p) for p in paths]):
        data = f.read_bytes()
        is_text = f.suffix.lower() in TEXT_SUFFIXES
        lines = data.split(b"\n") if is_text else None
        for name, value in secrets.items():
            if value in data:
                line = next(i for i, ln in enumerate(lines, 1) if value in ln) if lines is not None else 0
                found.append(Finding(f, line, f"value of {name}"))
        if is_text:
            text = data.decode("utf-8", errors="replace")
            if _STRONG.search(text) or _WEAK.search(text):
                for i, ln in enumerate(text.split("\n"), 1):
                    if _STRONG.search(ln) or _WEAK.search(ln):
                        found.append(Finding(f, i, "credential parameter"))
                        break
    return found
