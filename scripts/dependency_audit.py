#!/usr/bin/env python3
"""Plan or execute read-only dependency vulnerability audits.

The script never installs, upgrades, fixes, or removes dependencies. It selects
an audit command from an existing lockfile and an already-installed package
manager/auditor, runs commands without a shell, and distinguishes a completed
audit with findings from a tool failure.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

SECRET_PATTERNS = (
    re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{12,}\b"),
    re.compile(r"\bwhsec_[A-Za-z0-9]{12,}\b"),
    re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bsb_secret_[A-Za-z0-9._-]{16,}\b"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,}\b"),
    re.compile(r"(?i)(authorization|password|secret|token|api[_-]?key)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)://([^\s:/@]+):([^\s/@]+)@"),
)

SEVERITIES = ("critical", "high", "moderate", "medium", "low", "info", "unknown")


@dataclass
class AuditPlan:
    ecosystem: str
    manager: str
    manifest: str | None
    lockfile: str
    command: list[str] | None
    tool_available: bool
    executable: str | None
    ready: bool
    notes: list[str] = field(default_factory=list)


@dataclass
class AuditResult:
    ecosystem: str
    manager: str
    command: list[str]
    status: str
    exit_code: int | None
    finding_count: int | None
    severity_counts: dict[str, int]
    affected_packages: list[dict[str, str]]
    notes: list[str]
    error: str | None


def sanitize(text: str, limit: int = 4_000) -> str:
    value = text.replace("\r", " ").strip()
    for pattern in SECRET_PATTERNS:
        if pattern.pattern.startswith("(?i)://"):
            value = pattern.sub("://<redacted>:<redacted>@", value)
        elif "authorization" in pattern.pattern.lower():
            value = pattern.sub(lambda match: match.group(1) + "=<redacted>", value)
        else:
            value = pattern.sub("<redacted>", value)
    return value[:limit]


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def relative(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def executable_path(name: str) -> str | None:
    return shutil.which(name)


def declared_package_manager(root: Path) -> str | None:
    package = read_json(root / "package.json")
    raw = package.get("packageManager")
    if not isinstance(raw, str):
        return None
    match = re.match(r"^([A-Za-z0-9._-]+)@", raw)
    return match.group(1).lower() if match else None


def parse_package_manager_version(root: Path, expected: str) -> int | None:
    package = read_json(root / "package.json")
    raw = package.get("packageManager")
    if not isinstance(raw, str):
        return None
    match = re.match(rf"^{re.escape(expected)}@(\d+)", raw)
    return int(match.group(1)) if match else None


def requirements_are_pinned(path: Path) -> tuple[bool, list[str]]:
    notes: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False, ["Soubor requirements nelze přečíst."]
    seen_requirement = False
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(("--", "-r", "-c")):
            continue
        seen_requirement = True
        if line.startswith(("git+", "http://", "https://", "file:")):
            notes.append("Requirements obsahují URL nebo VCS závislost; výsledek může vyžadovat síť a další ověření.")
            continue
        if "==" not in line and " @ " not in line:
            return False, ["Requirements nejsou plně připnuté na konkrétní verze; audit by nebyl reprodukovatelný."]
    if not seen_requirement:
        return False, ["Requirements soubor neobsahuje auditovatelné balíčky."]
    return True, notes


def detect_plans(root: Path) -> tuple[list[AuditPlan], list[str]]:
    plans: list[AuditPlan] = []
    warnings: list[str] = []

    node_locks: list[tuple[str, str]] = []
    if (root / "npm-shrinkwrap.json").is_file():
        node_locks.append(("npm", "npm-shrinkwrap.json"))
    elif (root / "package-lock.json").is_file():
        node_locks.append(("npm", "package-lock.json"))
    if (root / "pnpm-lock.yaml").is_file():
        node_locks.append(("pnpm", "pnpm-lock.yaml"))
    if (root / "yarn.lock").is_file():
        node_locks.append(("yarn", "yarn.lock"))
    if (root / "bun.lock").is_file():
        node_locks.append(("bun", "bun.lock"))
    if (root / "bun.lockb").is_file():
        node_locks.append(("bun", "bun.lockb"))

    distinct_node_managers = sorted({manager for manager, _ in node_locks})
    declared_node_manager = declared_package_manager(root)
    if len(distinct_node_managers) > 1:
        if declared_node_manager in distinct_node_managers:
            warnings.append(
                "Projekt obsahuje lockfily více Node package managerů: "
                + ", ".join(distinct_node_managers)
                + f". package.json deklaruje {declared_node_manager}; ostatní audity budou z bezpečnostních důvodů přeskočeny."
            )
        else:
            warnings.append(
                "Projekt obsahuje lockfily více Node package managerů: "
                + ", ".join(distinct_node_managers)
                + ". package.json neurčuje jednoznačný autoritativní nástroj; Node audity nebudou automaticky spuštěny."
            )

    for manager, lockfile in node_locks:
        tool = executable_path(manager)
        notes: list[str] = []
        command: list[str]
        unsafe_project_tooling = False
        if manager == "npm":
            command = ["npm", "audit", "--json", "--audit-level=moderate", "--ignore-scripts"]
        elif manager == "pnpm":
            command = ["pnpm", "audit", "--json", "--audit-level", "moderate"]
            if any((root / name).is_file() for name in (".pnpmfile.cjs", "pnpmfile.cjs", ".pnpmfile.js")):
                unsafe_project_tooling = True
                notes.append("Projekt obsahuje pnpm hook soubor, který může spouštět projektový kód. Audit bez izolace se nepustí.")
        elif manager == "yarn":
            major = parse_package_manager_version(root, "yarn")
            modern = major is not None and major >= 2
            if modern or (root / ".yarnrc.yml").is_file():
                command = ["yarn", "npm", "audit", "--json", "--severity", "moderate"]
                notes.append("Používám syntaxi Yarn 2+ podle packageManager nebo .yarnrc.yml.")
                yarnrc = root / ".yarnrc.yml"
                yarnrc_text = yarnrc.read_text(encoding="utf-8", errors="replace") if yarnrc.is_file() else ""
                if re.search(r"(?m)^\s*yarnPath\s*:", yarnrc_text) or (root / ".yarn/plugins").is_dir():
                    unsafe_project_tooling = True
                    notes.append("Projekt používá lokální Yarn binary nebo pluginy, tedy projektový kód. Audit bez izolace se nepustí.")
            else:
                command = ["yarn", "audit", "--json", "--level", "moderate"]
                notes.append("Verzi Yarn se nepodařilo potvrdit; před interpretací ověřte, zda jde o Yarn Classic.")
        else:
            command = ["bun", "audit", "--json"]
        manager_selected = (
            (len(distinct_node_managers) <= 1 and declared_node_manager in (None, manager))
            or declared_node_manager == manager
        )
        if declared_node_manager and declared_node_manager != manager:
            notes.append(
                f"package.json deklaruje {declared_node_manager}, ale tento lockfile patří {manager}; audit se automaticky nepustí."
            )
        elif not manager_selected:
            notes.append("Tento lockfile není jednoznačně autoritativní a audit se automaticky nepustí.")
        plans.append(
            AuditPlan(
                ecosystem="node",
                manager=manager,
                manifest="package.json" if (root / "package.json").is_file() else None,
                lockfile=lockfile,
                command=command,
                tool_available=tool is not None,
                executable=tool,
                ready=bool(tool and manager_selected and not unsafe_project_tooling),
                notes=notes + ([] if tool else [f"Příkaz {manager} není v prostředí dostupný; Bodyguard ho nesmí automaticky instalovat."]),
            )
        )

    if (root / ".npmrc").is_file():
        warnings.append("Projekt obsahuje .npmrc. Před online auditem ověřte vlastní registry a bezpečné uložení autentizačních tokenů.")

    composer_lock = root / "composer.lock"
    if composer_lock.is_file():
        tool = executable_path("composer")
        plans.append(
            AuditPlan(
                ecosystem="php",
                manager="composer",
                manifest="composer.json" if (root / "composer.json").is_file() else None,
                lockfile="composer.lock",
                command=["composer", "audit", "--format=json", "--no-interaction", "--no-plugins", "--no-scripts"],
                tool_available=tool is not None,
                executable=tool,
                ready=tool is not None,
                notes=[] if tool else ["Composer není dostupný; Bodyguard ho nesmí automaticky instalovat."],
            )
        )

    requirement_candidates = [
        root / "requirements.lock",
        root / "requirements.txt",
        root / "requirements-prod.txt",
    ]
    selected_requirement = next((path for path in requirement_candidates if path.is_file()), None)
    if selected_requirement:
        pinned, notes = requirements_are_pinned(selected_requirement)
        tool = executable_path("pip-audit")
        command = [
            "pip-audit",
            "-r",
            relative(root, selected_requirement),
            "--format=json",
            "--progress-spinner=off",
            "--disable-pip",
        ]
        if not tool:
            notes.append("pip-audit není dostupný; Bodyguard ho nesmí automaticky instalovat.")
        plans.append(
            AuditPlan(
                ecosystem="python",
                manager="pip-audit",
                manifest=relative(root, selected_requirement),
                lockfile=relative(root, selected_requirement),
                command=command,
                tool_available=tool is not None,
                executable=tool,
                ready=bool(tool and pinned),
                notes=notes,
            )
        )

    for unsupported in ("poetry.lock", "uv.lock", "Pipfile.lock"):
        if (root / unsupported).is_file() and not selected_requirement:
            warnings.append(
                f"Nalezen {unsupported}, ale tento předskener nemá bezpečný univerzální read-only audit pro tento formát. Použijte aktuální oficiální nástroj po samostatném ověření."
            )

    if (root / "Gemfile.lock").is_file():
        tool = executable_path("bundle-audit")
        plans.append(
            AuditPlan(
                ecosystem="ruby",
                manager="bundle-audit",
                manifest="Gemfile" if (root / "Gemfile").is_file() else None,
                lockfile="Gemfile.lock",
                command=["bundle-audit", "check", "--format", "json"],
                tool_available=tool is not None,
                executable=tool,
                ready=tool is not None,
                notes=[] if tool else ["bundle-audit není dostupný; Bodyguard ho nesmí automaticky instalovat."],
            )
        )

    if (root / "Cargo.lock").is_file():
        cargo = executable_path("cargo")
        cargo_audit = executable_path("cargo-audit")
        available = bool(cargo and cargo_audit)
        plans.append(
            AuditPlan(
                ecosystem="rust",
                manager="cargo-audit",
                manifest="Cargo.toml" if (root / "Cargo.toml").is_file() else None,
                lockfile="Cargo.lock",
                command=["cargo", "audit", "--json"],
                tool_available=available,
                executable=cargo_audit,
                ready=available,
                notes=[] if available else ["cargo a cargo-audit nejsou oba dostupné; Bodyguard je nesmí automaticky instalovat."],
            )
        )

    if not plans:
        warnings.append("Nebyl nalezen podporovaný lockfile pro read-only audit závislostí.")
    return plans, warnings


def severity_template() -> dict[str, int]:
    return {severity: 0 for severity in SEVERITIES}


def normalize_severity(value: Any) -> str:
    raw = str(value or "unknown").lower()
    if raw == "medium":
        return "medium"
    if raw in SEVERITIES:
        return raw
    return "unknown"


def add_package(packages: list[dict[str, str]], name: Any, version: Any, severity: Any) -> None:
    safe_name = str(name or "unknown")[:200]
    safe_version = str(version or "unknown")[:100]
    safe_severity = normalize_severity(severity)
    item = {"name": safe_name, "version": safe_version, "severity": safe_severity}
    if item not in packages and len(packages) < 100:
        packages.append(item)


def parse_npm_like(stdout: str) -> tuple[int, dict[str, int], list[dict[str, str]], list[str]]:
    notes: list[str] = []
    severity = severity_template()
    packages: list[dict[str, str]] = []
    data = json.loads(stdout)
    if not isinstance(data, dict):
        raise ValueError("Audit JSON není objekt.")

    metadata = data.get("metadata")
    if isinstance(metadata, dict):
        vulnerabilities = metadata.get("vulnerabilities")
        if isinstance(vulnerabilities, dict):
            for key, count in vulnerabilities.items():
                if str(key).lower() == "total":
                    continue
                normalized = normalize_severity(key)
                if isinstance(count, int):
                    severity[normalized] = max(severity[normalized], count)

    vulnerabilities_obj = data.get("vulnerabilities")
    if isinstance(vulnerabilities_obj, dict):
        for name, details in vulnerabilities_obj.items():
            if isinstance(details, dict):
                add_package(packages, name, details.get("version", "unknown"), details.get("severity"))
    advisories = data.get("advisories")
    if isinstance(advisories, dict):
        for details in advisories.values():
            if not isinstance(details, dict):
                continue
            module = details.get("module_name") or details.get("module") or "unknown"
            sev = details.get("severity")
            findings = details.get("findings")
            version = "unknown"
            if isinstance(findings, list) and findings and isinstance(findings[0], dict):
                paths = findings[0].get("paths")
                version = str(paths[0]) if isinstance(paths, list) and paths else "unknown"
            add_package(packages, module, version, sev)
            severity[normalize_severity(sev)] += 1

    count = sum(severity.values())
    if count == 0 and packages:
        count = len(packages)
        for item in packages:
            severity[item["severity"]] += 1
    return count, severity, packages, notes


def parse_yarn_lines(stdout: str) -> tuple[int, dict[str, int], list[dict[str, str]], list[str]]:
    # Yarn Classic emits one JSON object per line; modern Yarn can emit one object.
    stripped = stdout.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            json.loads(stripped)
        except json.JSONDecodeError:
            pass
        else:
            return parse_npm_like(stripped)
    severity = severity_template()
    packages: list[dict[str, str]] = []
    notes: list[str] = []
    parsed_any = False
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        parsed_any = True
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        data = item.get("data")
        if item_type == "auditAdvisory" and isinstance(data, dict):
            advisory = data.get("advisory")
            if isinstance(advisory, dict):
                sev = normalize_severity(advisory.get("severity"))
                severity[sev] += 1
                add_package(packages, advisory.get("module_name"), advisory.get("findings", "unknown"), sev)
        elif item_type == "auditSummary" and isinstance(data, dict):
            vulnerabilities = data.get("vulnerabilities")
            if isinstance(vulnerabilities, dict):
                for key, count in vulnerabilities.items():
                    if str(key).lower() == "total":
                        continue
                    if isinstance(count, int):
                        severity[normalize_severity(key)] = max(severity[normalize_severity(key)], count)
    if not parsed_any:
        raise ValueError("Výstup Yarn neobsahuje rozpoznatelné JSON záznamy.")
    return sum(severity.values()), severity, packages, notes


def parse_composer(stdout: str) -> tuple[int, dict[str, int], list[dict[str, str]], list[str]]:
    data = json.loads(stdout)
    if not isinstance(data, dict):
        raise ValueError("Composer audit JSON není objekt.")
    severity = severity_template()
    packages: list[dict[str, str]] = []
    advisories = data.get("advisories", {})
    if isinstance(advisories, dict):
        for package_name, package_advisories in advisories.items():
            if isinstance(package_advisories, list):
                items = package_advisories
            elif isinstance(package_advisories, dict) and not any(
                key in package_advisories for key in ("severity", "affectedVersions", "advisoryId")
            ):
                items = list(package_advisories.values())
            else:
                items = [package_advisories]
            for advisory in items:
                if not isinstance(advisory, dict):
                    continue
                sev = normalize_severity(advisory.get("severity"))
                severity[sev] += 1
                add_package(packages, package_name, advisory.get("affectedVersions", "unknown"), sev)
    notes: list[str] = []
    abandoned = data.get("abandoned")
    if isinstance(abandoned, dict) and abandoned:
        notes.append(f"Composer označil {len(abandoned)} balíčků jako abandoned; nejde nutně o zranitelnost, ale vyžaduje plán náhrady.")
    return sum(severity.values()), severity, packages, notes


def parse_pip_audit(stdout: str) -> tuple[int, dict[str, int], list[dict[str, str]], list[str]]:
    data = json.loads(stdout)
    dependencies: Any
    if isinstance(data, dict):
        dependencies = data.get("dependencies", data.get("packages", []))
    else:
        dependencies = data
    if not isinstance(dependencies, list):
        raise ValueError("pip-audit JSON neobsahuje seznam závislostí.")
    severity = severity_template()
    packages: list[dict[str, str]] = []
    count = 0
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            continue
        vulns = dependency.get("vulns") or dependency.get("vulnerabilities") or []
        if not isinstance(vulns, list):
            continue
        for vuln in vulns:
            if not isinstance(vuln, dict):
                continue
            # pip-audit advisories often omit CVSS severity. Keep it unknown
            # instead of inventing a classification.
            sev = normalize_severity(vuln.get("severity"))
            severity[sev] += 1
            count += 1
            add_package(packages, dependency.get("name"), dependency.get("version"), sev)
    return count, severity, packages, ["Chybějící závažnost u Python advisory zůstává UNKNOWN; Bodyguard ji nesmí odhadovat."]


def parse_bundle_audit(stdout: str) -> tuple[int, dict[str, int], list[dict[str, str]], list[str]]:
    data = json.loads(stdout)
    results = data.get("results", data.get("advisories", [])) if isinstance(data, dict) else []
    if not isinstance(results, list):
        raise ValueError("bundle-audit JSON neobsahuje seznam výsledků.")
    severity = severity_template()
    packages: list[dict[str, str]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        advisory = item.get("advisory", item)
        if not isinstance(advisory, dict):
            continue
        sev = normalize_severity(advisory.get("criticality") or advisory.get("severity"))
        severity[sev] += 1
        add_package(packages, item.get("gem", advisory.get("gem")), item.get("version", "unknown"), sev)
    return sum(severity.values()), severity, packages, []


def parse_cargo_audit(stdout: str) -> tuple[int, dict[str, int], list[dict[str, str]], list[str]]:
    data = json.loads(stdout)
    vulnerabilities = data.get("vulnerabilities", {}) if isinstance(data, dict) else {}
    items = vulnerabilities.get("list", []) if isinstance(vulnerabilities, dict) else []
    if not isinstance(items, list):
        raise ValueError("cargo-audit JSON neobsahuje seznam zranitelností.")
    severity = severity_template()
    packages: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        package = item.get("package", {})
        advisory = item.get("advisory", {})
        sev = normalize_severity(advisory.get("severity") if isinstance(advisory, dict) else None)
        severity[sev] += 1
        if isinstance(package, dict):
            add_package(packages, package.get("name"), package.get("version"), sev)
    return sum(severity.values()), severity, packages, []


PARSERS: dict[str, Callable[[str], tuple[int, dict[str, int], list[dict[str, str]], list[str]]]] = {
    "npm": parse_npm_like,
    "pnpm": parse_npm_like,
    "bun": parse_npm_like,
    "yarn": parse_yarn_lines,
    "composer": parse_composer,
    "pip-audit": parse_pip_audit,
    "bundle-audit": parse_bundle_audit,
    "cargo-audit": parse_cargo_audit,
}


def audit_environment() -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "CI": "1",
            "NO_COLOR": "1",
            "FORCE_COLOR": "0",
            "npm_config_ignore_scripts": "true",
            "NPM_CONFIG_IGNORE_SCRIPTS": "true",
            "YARN_ENABLE_SCRIPTS": "false",
            "COREPACK_ENABLE_NETWORK": "0",
            "COREPACK_ENABLE_DOWNLOAD_PROMPT": "0",
        }
    )
    return env


def run_plan(root: Path, plan: AuditPlan, timeout: int) -> AuditResult:
    assert plan.command is not None
    try:
        completed = subprocess.run(
            plan.command,
            cwd=root,
            env=audit_environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return AuditResult(
            ecosystem=plan.ecosystem,
            manager=plan.manager,
            command=plan.command,
            status="failed",
            exit_code=None,
            finding_count=None,
            severity_counts=severity_template(),
            affected_packages=[],
            notes=plan.notes,
            error=f"Audit překročil limit {timeout} sekund.",
        )
    except OSError as exc:
        return AuditResult(
            ecosystem=plan.ecosystem,
            manager=plan.manager,
            command=plan.command,
            status="failed",
            exit_code=None,
            finding_count=None,
            severity_counts=severity_template(),
            affected_packages=[],
            notes=plan.notes,
            error=sanitize(str(exc)),
        )

    parser = PARSERS.get(plan.manager)
    if parser is None:
        return AuditResult(
            ecosystem=plan.ecosystem,
            manager=plan.manager,
            command=plan.command,
            status="failed",
            exit_code=completed.returncode,
            finding_count=None,
            severity_counts=severity_template(),
            affected_packages=[],
            notes=plan.notes,
            error="Pro tento auditovací výstup není definovaný bezpečný parser.",
        )

    try:
        count, severity, packages, parser_notes = parser(completed.stdout)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        diagnostic = sanitize(completed.stderr or completed.stdout, limit=1_500)
        return AuditResult(
            ecosystem=plan.ecosystem,
            manager=plan.manager,
            command=plan.command,
            status="failed",
            exit_code=completed.returncode,
            finding_count=None,
            severity_counts=severity_template(),
            affected_packages=[],
            notes=plan.notes,
            error=f"Výstup nešel bezpečně interpretovat: {sanitize(str(exc))}. Diagnostika: {diagnostic}",
        )

    # A non-zero exit code commonly means the audit completed and found
    # vulnerabilities. Parsed JSON is the evidence; do not label that as tool
    # unavailability or execution failure.
    status = "completed_with_findings" if count > 0 else "completed_clean"
    notes = list(plan.notes) + parser_notes
    if completed.returncode not in (0, 1) and count == 0:
        notes.append(
            f"Nástroj vrátil neobvyklý exit code {completed.returncode}; čistý výsledek proto vyžaduje ruční potvrzení."
        )
        status = "completed_unverified"
    stderr = sanitize(completed.stderr, limit=1_000)
    if stderr:
        notes.append("Nástroj vypsal diagnostiku: " + stderr)

    return AuditResult(
        ecosystem=plan.ecosystem,
        manager=plan.manager,
        command=plan.command,
        status=status,
        exit_code=completed.returncode,
        finding_count=count,
        severity_counts=severity,
        affected_packages=packages,
        notes=notes,
        error=None,
    )


def command_for_display(command: list[str] | None) -> list[str] | None:
    # Arguments contain no secret values by design; return a copy so callers
    # cannot mutate the plan.
    return list(command) if command else None


def format_text(result: dict[str, Any]) -> str:
    lines = [
        "Bodyguard dependency audit",
        f"Režim: {result['mode']}",
        f"Cesta: {result['project_path']}",
    ]
    for warning in result["warnings"]:
        lines.append("Upozornění: " + warning)
    if result["mode"] == "plan":
        for plan in result["plans"]:
            lines.append(
                f"- {plan['manager']} / {plan['lockfile']}: "
                + ("připraveno" if plan["ready"] else "nelze spustit")
            )
            if plan["command"]:
                lines.append("  Příkaz: " + " ".join(plan["command"]))
            for note in plan["notes"]:
                lines.append("  Poznámka: " + note)
    else:
        for item in result["results"]:
            lines.append(
                f"- {item['manager']}: {item['status']}; nálezy="
                + (str(item["finding_count"]) if item["finding_count"] is not None else "neznámé")
            )
            if item["error"]:
                lines.append("  Chyba: " + item["error"])
            for note in item["notes"]:
                lines.append("  Poznámka: " + note)
    return "\n".join(lines)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan or run dependency audits without installing or fixing packages.")
    parser.add_argument("path", help="Cesta ke kořeni projektu")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true", help="Pouze vypsat bezpečný plán")
    mode.add_argument("--execute", action="store_true", help="Spustit dostupné read-only audity")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    parser.add_argument("--timeout", type=int, default=120, help="Limit sekund na jeden audit")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    root = Path(args.path).expanduser().resolve()
    if not root.is_dir():
        payload = {"error": "Zadaná cesta není existující adresář.", "project_path": str(root)}
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.format == "json" else payload["error"])
        return 3
    if args.timeout < 1:
        print("Timeout musí být kladný.", file=sys.stderr)
        return 3

    plans, warnings = detect_plans(root)
    base: dict[str, Any] = {
        "tool": "bodyguard-dependency-audit",
        "project_path": str(root),
        "read_only": True,
        "installs_or_fixes_packages": False,
        "network_may_be_used_in_execute_mode": True,
        "mode": "plan" if args.plan else "execute",
        "warnings": warnings,
        "limitations": [
            "Audit databáze může být neaktuální nebo nedostupná.",
            "Známé zranitelnosti závislostí nepokrývají chyby vlastního kódu ani obchodní logiky.",
            "Čistý audit není důkaz, že je aplikace bezpečná.",
        ],
    }

    if args.plan:
        base["plans"] = [
            {
                **asdict(plan),
                "command": command_for_display(plan.command),
            }
            for plan in plans
        ]
        output = base
        exit_code = 0
    else:
        results: list[AuditResult] = []
        for plan in plans:
            if not plan.ready or not plan.command:
                results.append(
                    AuditResult(
                        ecosystem=plan.ecosystem,
                        manager=plan.manager,
                        command=command_for_display(plan.command) or [],
                        status="skipped",
                        exit_code=None,
                        finding_count=None,
                        severity_counts=severity_template(),
                        affected_packages=[],
                        notes=plan.notes,
                        error="Chybí podporovaný lockfile nebo již nainstalovaný auditovací nástroj.",
                    )
                )
                continue
            results.append(run_plan(root, plan, args.timeout))
        base["results"] = [asdict(result) for result in results]
        output = base
        if any(result.status == "completed_with_findings" for result in results):
            exit_code = 2
        elif not results or any(result.status in {"failed", "skipped", "completed_unverified"} for result in results):
            exit_code = 3
        else:
            exit_code = 0

    if args.format == "json":
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(format_text(output))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
