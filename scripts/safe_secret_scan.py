#!/usr/bin/env python3
"""Read-only secret pre-scanner that never prints detected values.

The scanner inspects the working tree and, optionally, added lines in Git
history. Findings contain only a detector name, location, variable name when
available, and a redaction marker. This is a heuristic pre-scan, not proof that
an exposed credential is active.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".next",
    ".nuxt",
    ".output",
    ".vercel",
    ".turbo",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "coverage",
    "target",
    ".venv",
    "venv",
    "env",
}

PUBLIC_ENV_PREFIXES = (
    "NEXT_PUBLIC_",
    "VITE_",
    "REACT_APP_",
    "NUXT_PUBLIC_",
    "PUBLIC_",
    "EXPO_PUBLIC_",
    "ASTRO_PUBLIC_",
)

SECRET_NAME_MARKERS = (
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "PRIVATE",
    "SERVICE_ROLE",
    "DATABASE_URL",
    "CONNECTION_STRING",
    "ADMIN_KEY",
    "ROOT_KEY",
    "MASTER_KEY",
    "ACCESS_TOKEN",
    "AUTH_TOKEN",
    "API_KEY",
)

# API_KEY alone is intentionally absent: some browser APIs use public,
# domain-restricted identifiers. A known server-secret format is still caught.
PUBLIC_SECRET_NAME_MARKERS = (
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "PRIVATE",
    "SERVICE_ROLE",
    "DATABASE_URL",
    "CONNECTION_STRING",
    "ADMIN_KEY",
    "ROOT_KEY",
    "MASTER_KEY",
    "ACCESS_TOKEN",
    "AUTH_TOKEN",
)

SAFE_ENV_TEMPLATES = {
    ".env.example",
    ".env.sample",
    ".env.template",
    ".env.defaults",
    ".env.dist",
}

PLACEHOLDER_MARKERS = (
    "example",
    "placeholder",
    "replace-me",
    "replace_me",
    "replacewith",
    "your-",
    "your_",
    "dummy",
    "fake",
    "sample",
    "changeme",
    "change-me",
    "not-a-real",
    "not_real",
    "redacted",
    "<secret>",
    "<token>",
    "xxx",
)


@dataclass(frozen=True)
class Detector:
    name: str
    pattern: re.Pattern[str]
    severity: str
    confidence: str
    reason: str


DETECTORS: tuple[Detector, ...] = (
    Detector(
        "private_key",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"),
        "critical",
        "high",
        "Soubor nebo řádek obsahuje hlavičku privátního klíče.",
    ),
    Detector(
        "aws_access_key_id",
        re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
        "high",
        "high",
        "Řádek odpovídá formátu AWS access key ID.",
    ),
    Detector(
        "github_token",
        re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,255}\b|\bgithub_pat_[A-Za-z0-9_]{50,255}\b"),
        "critical",
        "high",
        "Řádek odpovídá formátu GitHub tokenu.",
    ),
    Detector(
        "gitlab_token",
        re.compile(r"\bglpat-[A-Za-z0-9_-]{20,255}\b"),
        "critical",
        "high",
        "Řádek odpovídá formátu GitLab tokenu.",
    ),
    Detector(
        "stripe_secret_key",
        re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,255}\b"),
        "critical",
        "high",
        "Řádek odpovídá tajnému nebo omezenému Stripe klíči.",
    ),
    Detector(
        "stripe_webhook_secret",
        re.compile(r"\bwhsec_[A-Za-z0-9]{16,255}\b"),
        "critical",
        "high",
        "Řádek odpovídá podpisovému tajemství Stripe webhooku.",
    ),
    Detector(
        "supabase_secret_key",
        re.compile(r"\bsb_secret_[A-Za-z0-9._-]{16,255}\b"),
        "critical",
        "high",
        "Řádek odpovídá Supabase secret key určenému jen pro server.",
    ),
    Detector(
        "openai_secret_key",
        re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,255}\b"),
        "critical",
        "high",
        "Řádek odpovídá formátu tajného OpenAI API klíče.",
    ),
    Detector(
        "anthropic_secret_key",
        re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,255}\b"),
        "critical",
        "high",
        "Řádek odpovídá formátu tajného Anthropic API klíče.",
    ),
    Detector(
        "google_api_key",
        re.compile(r"\bAIza[0-9A-Za-z_-]{30,80}\b"),
        "high",
        "high",
        "Řádek odpovídá formátu Google API klíče; jeho riziko závisí na omezeních klíče.",
    ),
    Detector(
        "slack_token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,255}\b"),
        "critical",
        "high",
        "Řádek odpovídá formátu Slack tokenu.",
    ),
    Detector(
        "sendgrid_api_key",
        re.compile(r"\bSG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{20,}\b"),
        "critical",
        "high",
        "Řádek odpovídá formátu SendGrid API klíče.",
    ),
    Detector(
        "npm_access_token",
        re.compile(r"\bnpm_[A-Za-z0-9]{30,255}\b"),
        "critical",
        "high",
        "Řádek odpovídá formátu npm access tokenu.",
    ),
    Detector(
        "database_url_with_password",
        re.compile(
            r"\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|amqp)://"
            r"[^\s:/@]+:[^\s/@]{3,}@[^\s]+",
            re.IGNORECASE,
        ),
        "critical",
        "high",
        "Connection URL zřejmě obsahuje uživatelské jméno a heslo.",
    ),
)

ASSIGNMENT_QUOTED = re.compile(
    r"(?i)\b([A-Z0-9_.-]*(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|private[_-]?key|database[_-]?url|connection[_-]?string)[A-Z0-9_.-]*)"
    r"\s*[:=]\s*(['\"])([^'\"\r\n]{6,})\2"
)

ASSIGNMENT_PLAIN = re.compile(
    r"(?i)^\s*(?:export\s+)?([A-Z0-9_.-]*(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|private[_-]?key|database[_-]?url|connection[_-]?string)[A-Z0-9_.-]*)"
    r"\s*[:=]\s*([^#\s][^#\r\n]{5,}?)\s*$"
)

ENV_ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


@dataclass
class Finding:
    detector: str
    severity: str
    confidence: str
    source: str
    path: str
    line: int | None
    commit: str | None
    variable: str | None
    redaction: str
    reason: str


class ScanState:
    def __init__(self, max_findings: int) -> None:
        self.findings: list[Finding] = []
        self.errors: list[str] = []
        self.scanned_files = 0
        self.skipped_large_files = 0
        self.max_findings = max_findings
        self.truncated = False
        self.history_commits_scanned = 0
        self.history_total_commits: int | None = None
        self.history_truncated = False
        self._seen: set[tuple[str, str, str, str | None]] = set()

    def add(self, finding: Finding, secret_value: str | None = None) -> None:
        # The value is used only to deduplicate in memory and is never serialized.
        marker = secret_value or finding.variable or finding.reason
        key = (finding.detector, finding.source, finding.path, _safe_internal_marker(marker))
        if key in self._seen:
            return
        self._seen.add(key)
        if len(self.findings) >= self.max_findings:
            self.truncated = True
            return
        self.findings.append(finding)


def _safe_internal_marker(value: str) -> str:
    # Deliberately not a reversible hash and never emitted. The process-local
    # hash is sufficient for deduplication during one run.
    return str(hash(value))


def _redaction(value: str) -> str:
    length = len(value.strip())
    if length <= 0:
        return "<redacted>"
    return f"<redacted:{length} chars>"


def _is_placeholder(value: str) -> bool:
    candidate = value.strip().strip("'\"").lower()
    if not candidate:
        return True
    if candidate in {"null", "none", "undefined", "true", "false"}:
        return True
    if candidate.startswith(("${", "{{", "$env", "process.env", "os.getenv", "getenv(", "env(")):
        return True
    if candidate.startswith("<") and candidate.endswith(">"):
        return True
    return any(marker in candidate for marker in PLACEHOLDER_MARKERS)


def _sanitize_error(text: str) -> str:
    sanitized = text.replace("\r", " ").replace("\n", " ").strip()
    for detector in DETECTORS:
        sanitized = detector.pattern.sub("<redacted>", sanitized)
    sanitized = re.sub(
        r"(?i)(authorization|token|password|secret|api[_-]?key)\s*[:=]\s*\S+",
        r"\1=<redacted>",
        sanitized,
    )
    return sanitized[:500]


def _run_git(root: Path, args: Sequence[str], timeout: int = 30) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def _is_git_repo(root: Path) -> bool:
    if not shutil.which("git"):
        return False
    result = _run_git(root, ["rev-parse", "--is-inside-work-tree"])
    return result.returncode == 0 and result.stdout.strip() == b"true"


def _normalize_relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return path.as_posix()


def _git_file_paths(root: Path, state: ScanState) -> list[Path]:
    result = _run_git(root, ["ls-files", "-co", "--exclude-standard", "-z"])
    if result.returncode != 0:
        state.errors.append("Nepodařilo se načíst seznam souborů z Gitu: " + _sanitize_error(result.stderr.decode("utf-8", "replace")))
        return []
    paths: list[Path] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8", "surrogateescape")
        candidate = root / rel
        if candidate.is_file() and not candidate.is_symlink():
            paths.append(candidate)
    return paths


def _walk_file_paths(root: Path, max_files: int) -> Iterator[Path]:
    count = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [name for name in dirnames if name not in EXCLUDED_DIRS and not (Path(dirpath) / name).is_symlink()]
        for filename in filenames:
            candidate = Path(dirpath) / filename
            if candidate.is_symlink() or not candidate.is_file():
                continue
            yield candidate
            count += 1
            if count >= max_files:
                return


def _tracked_env_files(root: Path, state: ScanState) -> set[str]:
    if not _is_git_repo(root):
        return set()
    result = _run_git(root, ["ls-files", "-z"])
    if result.returncode != 0:
        state.errors.append("Nepodařilo se ověřit sledované .env soubory.")
        return set()
    tracked: set[str] = set()
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8", "surrogateescape")
        if Path(rel).name.startswith(".env"):
            tracked.add(rel)
    return tracked


def _scan_line(
    line: str,
    *,
    source: str,
    path: str,
    line_number: int | None,
    commit: str | None,
    state: ScanState,
) -> None:
    for detector in DETECTORS:
        for match in detector.pattern.finditer(line):
            value = match.group(0)
            state.add(
                Finding(
                    detector=detector.name,
                    severity=detector.severity,
                    confidence=detector.confidence,
                    source=source,
                    path=path,
                    line=line_number,
                    commit=commit,
                    variable=None,
                    redaction=_redaction(value),
                    reason=detector.reason,
                ),
                secret_value=value,
            )

    generic_matches: list[tuple[str, str]] = []
    for match in ASSIGNMENT_QUOTED.finditer(line):
        generic_matches.append((match.group(1), match.group(3)))
    plain = ASSIGNMENT_PLAIN.match(line)
    if plain:
        generic_matches.append((plain.group(1), plain.group(2).strip()))

    for variable, value in generic_matches:
        if _is_placeholder(value):
            continue
        # Public identifiers that are explicitly designed for a browser are not
        # treated as secrets merely because their variable name contains KEY.
        upper_variable = variable.upper()
        if upper_variable.startswith(PUBLIC_ENV_PREFIXES):
            # The exact value patterns above still detect known server secrets.
            # A generic key-looking name in a client variable is not enough to
            # call it a leak because some providers issue public identifiers.
            continue
        state.add(
            Finding(
                detector="generic_secret_assignment",
                severity="high",
                confidence="medium",
                source=source,
                path=path,
                line=line_number,
                commit=commit,
                variable=variable,
                redaction=_redaction(value),
                reason="Proměnná s citlivým názvem obsahuje přímo zapsanou ne-placeholderovou hodnotu.",
            ),
            secret_value=value,
        )


def _scan_file(root: Path, path: Path, max_file_size: int, state: ScanState) -> None:
    try:
        size = path.stat().st_size
    except OSError as exc:
        state.errors.append(f"Nelze přečíst metadata souboru {_normalize_relative(root, path)}: {_sanitize_error(str(exc))}")
        return
    if size > max_file_size:
        state.skipped_large_files += 1
        return
    try:
        data = path.read_bytes()
    except OSError as exc:
        state.errors.append(f"Nelze přečíst soubor {_normalize_relative(root, path)}: {_sanitize_error(str(exc))}")
        return
    if b"\x00" in data[:8192]:
        return
    text = data.decode("utf-8", "replace")
    relative = _normalize_relative(root, path)
    state.scanned_files += 1
    for number, line in enumerate(text.splitlines(), start=1):
        _scan_line(
            line,
            source="working_tree",
            path=relative,
            line_number=number,
            commit=None,
            state=state,
        )


def _scan_public_env_names(root: Path, max_file_size: int, state: ScanState) -> None:
    for path in _walk_file_paths(root, 100_000):
        if not path.name.startswith(".env"):
            continue
        try:
            if path.stat().st_size > max_file_size:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        relative = _normalize_relative(root, path)
        for number, line in enumerate(text.splitlines(), start=1):
            match = ENV_ASSIGNMENT.match(line)
            if not match:
                continue
            variable, value = match.group(1), match.group(2).strip().strip("'\"")
            upper = variable.upper()
            if not upper.startswith(PUBLIC_ENV_PREFIXES):
                continue
            sensitive_name = any(marker in upper for marker in PUBLIC_SECRET_NAME_MARKERS)
            detector_match = next((detector for detector in DETECTORS if detector.pattern.search(value)), None)
            if sensitive_name or detector_match:
                state.add(
                    Finding(
                        detector="secret_in_public_environment_variable",
                        severity="critical",
                        confidence="high" if detector_match else "medium",
                        source="environment_configuration",
                        path=relative,
                        line=number,
                        commit=None,
                        variable=variable,
                        redaction=_redaction(value),
                        reason="Proměnná určená pro klientský balíček má citlivý název nebo hodnotu odpovídající serverovému tajemství.",
                    ),
                    secret_value=value or variable,
                )


def _add_tracked_env_findings(root: Path, tracked: Iterable[str], state: ScanState) -> None:
    for rel in sorted(tracked):
        name = Path(rel).name
        if name in SAFE_ENV_TEMPLATES:
            continue
        state.add(
            Finding(
                detector="tracked_environment_file",
                severity="high",
                confidence="high",
                source="git_index",
                path=rel,
                line=None,
                commit=None,
                variable=None,
                redaction="<file contents not shown>",
                reason="Git sleduje .env soubor, který může obsahovat skutečná tajemství. Ověř obsah a historii; pouhá existence lokálního ignorovaného .env souboru není chyba.",
            )
        )


def _scan_git_history(root: Path, max_commits: int, state: ScanState) -> None:
    if not _is_git_repo(root):
        state.errors.append("Historii nelze skenovat: zadaná cesta není Git repozitář nebo Git není dostupný.")
        return

    command = [
        "git",
        "-C",
        str(root),
        "log",
        "--all",
        f"--max-count={max_commits}",
        "--no-color",
        "--no-ext-diff",
        "--format=__BG_COMMIT__%H",
        "--unified=0",
        "-p",
    ]
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        state.errors.append("Historii nelze skenovat: " + _sanitize_error(str(exc)))
        return

    assert process.stdout is not None
    current_commit: str | None = None
    current_path = "<unknown>"
    new_line_number: int | None = None

    for raw_line in process.stdout:
        line = raw_line.rstrip("\n")
        if line.startswith("__BG_COMMIT__"):
            state.history_commits_scanned += 1
            current_commit = line.removeprefix("__BG_COMMIT__")[:12]
            current_path = "<unknown>"
            new_line_number = None
            continue
        if line.startswith("+++ "):
            candidate = line[4:]
            if candidate == "/dev/null":
                current_path = "<deleted>"
            elif candidate.startswith("b/"):
                current_path = candidate[2:]
            else:
                current_path = candidate
            continue
        hunk = HUNK_HEADER.match(line)
        if hunk:
            new_line_number = int(hunk.group(1))
            continue
        if line.startswith("+") and not line.startswith("+++"):
            content = line[1:]
            _scan_line(
                content,
                source="git_history",
                path=current_path,
                line_number=new_line_number,
                commit=current_commit,
                state=state,
            )
            if new_line_number is not None:
                new_line_number += 1
        elif line.startswith(" ") and new_line_number is not None:
            new_line_number += 1
        elif line.startswith("-"):
            continue

    stderr = ""
    if process.stderr is not None:
        stderr = process.stderr.read()
    return_code = process.wait()
    if return_code != 0:
        state.errors.append("Git historie nebyla kompletně prohledána: " + _sanitize_error(stderr))

    count_result = _run_git(root, ["rev-list", "--count", "--all"])
    if count_result.returncode == 0:
        try:
            state.history_total_commits = int(count_result.stdout.strip())
        except ValueError:
            state.history_total_commits = None
    if state.history_total_commits is not None and state.history_total_commits > max_commits:
        state.history_truncated = True
        state.errors.append(
            f"Git historie má {state.history_total_commits} commitů, ale sken byl omezen na {max_commits}; čistý výsledek by nebyl úplný."
        )


def _format_text(result: dict[str, object]) -> str:
    lines = [
        "Bodyguard safe secret scan",
        f"Cesta: {result['project_path']}",
        f"Git historie: {'ano' if result['history_scanned'] else 'ne'}",
        f"Prohledané soubory: {result['summary']['scanned_files']}",  # type: ignore[index]
        f"Nálezy: {result['summary']['finding_count']}",  # type: ignore[index]
    ]
    findings = result["findings"]
    assert isinstance(findings, list)
    for index, item in enumerate(findings, start=1):
        assert isinstance(item, dict)
        location = item["path"]
        if item.get("line"):
            location = f"{location}:{item['line']}"
        if item.get("commit"):
            location = f"{location} @ {item['commit']}"
        variable = f"; proměnná {item['variable']}" if item.get("variable") else ""
        lines.append(
            f"{index}. [{str(item['severity']).upper()}] {item['detector']} — {location}{variable}; {item['redaction']}"
        )
        lines.append(f"   {item['reason']}")
    errors = result["errors"]
    assert isinstance(errors, list)
    if errors:
        lines.append("Neúplné kontroly / chyby:")
        lines.extend(f"- {error}" for error in errors)
    if result["summary"]["truncated"]:  # type: ignore[index]
        lines.append("Výstup byl zkrácen kvůli limitu nálezů.")
    return "\n".join(lines)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only secret scanner with mandatory redaction.")
    parser.add_argument("path", help="Cesta ke kořeni projektu")
    parser.add_argument("--history", action="store_true", help="Prohledat také přidané řádky v Git historii")
    parser.add_argument("--max-history-commits", type=int, default=500, help="Maximum commitů při skenu historie")
    parser.add_argument("--max-file-size", type=int, default=2_000_000, help="Maximum bajtů jednoho souboru")
    parser.add_argument("--max-files", type=int, default=100_000, help="Maximum souborů při skenu bez Gitu")
    parser.add_argument("--max-findings", type=int, default=500, help="Maximum reportovaných nálezů")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    root = Path(args.path).expanduser().resolve()
    if not root.is_dir():
        message = {"error": "Zadaná cesta není existující adresář.", "project_path": str(root)}
        print(json.dumps(message, ensure_ascii=False, indent=2) if args.format == "json" else message["error"])
        return 3
    if args.max_history_commits < 1 or args.max_file_size < 1 or args.max_files < 1 or args.max_findings < 1:
        print("Číselné limity musí být kladné.", file=sys.stderr)
        return 3

    state = ScanState(max_findings=args.max_findings)
    git_repo = _is_git_repo(root)
    paths = _git_file_paths(root, state) if git_repo else list(_walk_file_paths(root, args.max_files))
    if not git_repo and len(paths) >= args.max_files:
        state.errors.append("Sken souborů dosáhl nastaveného limitu; výsledek nemusí být úplný.")

    tracked_env = _tracked_env_files(root, state) if git_repo else set()
    _add_tracked_env_findings(root, tracked_env, state)

    for path in paths:
        _scan_file(root, path, args.max_file_size, state)

    # Inspect variable names in local ignored .env files without treating their
    # expected server-side values as leaks.
    _scan_public_env_names(root, args.max_file_size, state)

    if args.history:
        _scan_git_history(root, args.max_history_commits, state)

    findings_dict = [asdict(item) for item in state.findings]
    result: dict[str, object] = {
        "tool": "bodyguard-safe-secret-scan",
        "project_path": str(root),
        "read_only": True,
        "git_repository": git_repo,
        "history_scanned": bool(args.history and git_repo),
        "history": {
            "requested": bool(args.history),
            "commits_scanned": state.history_commits_scanned,
            "total_commits": state.history_total_commits,
            "commit_limit": args.max_history_commits if args.history else None,
            "truncated": state.history_truncated,
        },
        "limitations": [
            "Heuristický sken může mít falešné pozitivní i falešné negativní výsledky.",
            "Nález nepotvrzuje, že hodnota je aktivní; při podezření postupuj jako při incidentu.",
            "Výstup záměrně neobsahuje nalezené hodnoty.",
        ],
        "summary": {
            "scanned_files": state.scanned_files,
            "skipped_large_files": state.skipped_large_files,
            "finding_count": len(findings_dict),
            "error_count": len(state.errors),
            "truncated": state.truncated,
        },
        "findings": findings_dict,
        "errors": state.errors,
    }

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(_format_text(result))

    if state.findings:
        return 2
    if state.errors:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
