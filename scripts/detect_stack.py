#!/usr/bin/env python3
"""Read-only project inventory for the Bodyguard skill.

The script uses only Python's standard library and read-only git commands.
It does not access the network, install dependencies, run project code, or
print environment-variable values.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

MAX_FILE_BYTES = 1_000_000
DEFAULT_MAX_FILES = 20_000

EXCLUDED_DIRS = {
    ".git", ".next", ".nuxt", ".output", ".turbo", ".vercel", ".venv",
    "venv", "node_modules", "vendor", "dist", "build", "coverage", "target",
    "out", "tmp", "temp", "__pycache__", ".pytest_cache", ".mypy_cache",
}

TEXT_EXTENSIONS = {
    ".c", ".cc", ".conf", ".config", ".cpp", ".cs", ".css", ".go", ".graphql",
    ".gql", ".h", ".html", ".ini", ".java", ".js", ".json", ".jsx", ".kt",
    ".kts", ".md", ".mjs", ".mts", ".php", ".prisma", ".properties", ".py",
    ".rb", ".rs", ".sh", ".sql", ".svelte", ".swift", ".toml", ".ts", ".tsx",
    ".txt", ".vue", ".xml", ".yaml", ".yml",
}

SPECIAL_FILES = {
    "Dockerfile", "Gemfile", "Procfile", "Rakefile", "composer.json",
    "composer.lock", "go.mod", "go.sum", "package.json", "package-lock.json",
    "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb", "requirements.txt",
    "pyproject.toml", "uv.lock", "Pipfile", "Pipfile.lock", "Cargo.toml", "Cargo.lock",
    "vercel.json", "netlify.toml", "fly.toml", "railway.json",
}

ENV_NAME_RE = re.compile(r"(?m)^\s*(?:export\s+)?([A-Z][A-Z0-9_]{2,})\s*=")

SERVICE_MARKERS: dict[str, tuple[str, ...]] = {
    "Supabase": ("@supabase/supabase-js", "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_PUBLISHABLE_KEY"),
    "Stripe": ("stripe", "@stripe/stripe-js", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"),
    "OpenAI": ("openai", "OPENAI_API_KEY"),
    "Anthropic": ("@anthropic-ai/sdk", "anthropic", "ANTHROPIC_API_KEY"),
    "Google AI": ("@google/generative-ai", "google-generativeai", "GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "Resend": ("resend", "RESEND_API_KEY"),
    "SendGrid": ("@sendgrid/mail", "sendgrid", "SENDGRID_API_KEY"),
    "Postmark": ("postmark", "POSTMARK_SERVER_TOKEN"),
    "Twilio": ("twilio", "TWILIO_ACCOUNT_SID"),
    "Clerk": ("@clerk/nextjs", "CLERK_SECRET_KEY"),
    "Auth0": ("@auth0/nextjs-auth0", "AUTH0_SECRET"),
    "Sentry": ("@sentry/nextjs", "sentry-sdk", "SENTRY_DSN"),
    "Prisma": ("@prisma/client", "prisma", "schema.prisma"),
    "PostgreSQL": ("pg", "psycopg", "psycopg2", "DATABASE_URL"),
    "MongoDB": ("mongodb", "mongoose", "MONGODB_URI"),
    "Redis": ("redis", "ioredis", "UPSTASH_REDIS", "REDIS_URL"),
}

FEATURE_PATTERNS: dict[str, tuple[str, ...]] = {
    "authentication": ("auth", "login", "sign-in", "signin", "session", "clerk", "next-auth"),
    "authorization_roles": ("role", "permission", "policy", "is_admin", "organization_id", "tenant_id"),
    "payments": ("stripe", "checkout", "payment", "subscription", "invoice", "refund"),
    "file_uploads": ("upload", "multipart", "formdata", "storage.objects", "signedurl"),
    "webhooks": ("webhook", "stripe-signature", "svix-signature"),
    "email": ("resend", "sendgrid", "postmark", "nodemailer", "smtp"),
    "sms": ("twilio", "sms"),
    "ai": ("openai", "anthropic", "gemini", "generative-ai", "chat.completions", "responses.create", "tool_calls"),
    "external_url_fetching": ("fetch(url", "axios.get(url", "requests.get(url", "httpx.get(url", "urllib.request"),
    "cron_jobs": ("cron", "schedule:", "on.schedule", "crontab"),
    "admin_area": ("/admin", "admin/", "is_admin", "administrator"),
}


def run_command(args: Sequence[str], cwd: Path, timeout: int = 10) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        list(args), cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False, timeout=timeout,
    )


def git_info(root: Path) -> dict[str, Any]:
    info: dict[str, Any] = {
        "is_repository": False,
        "root": None,
        "branch": None,
        "commit": None,
        "dirty": None,
        "changed_files_count": None,
    }
    try:
        top = run_command(["git", "rev-parse", "--show-toplevel"], root)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return info
    if top.returncode != 0:
        return info
    repo_root = Path(top.stdout.decode("utf-8", "replace").strip()).resolve()
    info["is_repository"] = True
    info["root"] = str(repo_root)

    commands = {
        "branch": ["git", "branch", "--show-current"],
        "commit": ["git", "rev-parse", "HEAD"],
        "status": ["git", "status", "--porcelain", "--untracked-files=normal"],
    }
    results: dict[str, subprocess.CompletedProcess[bytes]] = {}
    for key, command in commands.items():
        try:
            results[key] = run_command(command, repo_root)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    if results.get("branch") and results["branch"].returncode == 0:
        info["branch"] = results["branch"].stdout.decode("utf-8", "replace").strip() or "DETACHED_HEAD"
    if results.get("commit") and results["commit"].returncode == 0:
        info["commit"] = results["commit"].stdout.decode("utf-8", "replace").strip()
    if results.get("status") and results["status"].returncode == 0:
        lines = [line for line in results["status"].stdout.decode("utf-8", "replace").splitlines() if line]
        info["dirty"] = bool(lines)
        info["changed_files_count"] = len(lines)
    return info


def is_text_candidate(path: Path) -> bool:
    if path.name in SPECIAL_FILES:
        return True
    if path.name.startswith(".env"):
        return True
    if path.name in {".gitignore", ".dockerignore", ".npmrc", ".yarnrc", ".yarnrc.yml"}:
        return True
    return path.suffix.lower() in TEXT_EXTENSIONS


def iter_files(root: Path, max_files: int) -> Iterable[Path]:
    yielded = 0
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in EXCLUDED_DIRS)
        base = Path(current_root)
        for filename in sorted(filenames):
            path = base / filename
            if is_text_candidate(path):
                yield path
                yielded += 1
                if yielded >= max_files:
                    return


def safe_read(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        data = path.read_bytes()
    except (OSError, PermissionError):
        return None
    if b"\x00" in data[:8192]:
        return None
    return data.decode("utf-8", "replace")


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any]:
    text = safe_read(path)
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def dependency_map(package_json: dict[str, Any]) -> dict[str, str]:
    output: dict[str, str] = {}
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        section = package_json.get(key)
        if isinstance(section, dict):
            for name, version in section.items():
                if isinstance(name, str) and isinstance(version, str):
                    output[name] = version
    return output


def detect_package_managers(root: Path, package_json: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [
        ("npm", "package-lock.json"),
        ("pnpm", "pnpm-lock.yaml"),
        ("yarn", "yarn.lock"),
        ("bun", "bun.lock"),
        ("bun", "bun.lockb"),
        ("uv", "uv.lock"),
        ("pipenv", "Pipfile.lock"),
        ("poetry/pep621", "pyproject.toml"),
        ("composer", "composer.lock"),
        ("bundler", "Gemfile.lock"),
        ("cargo", "Cargo.lock"),
        ("go", "go.sum"),
    ]
    managers: list[dict[str, Any]] = []
    for name, filename in candidates:
        if (root / filename).exists():
            managers.append({"name": name, "evidence": filename})
    declared = package_json.get("packageManager")
    if isinstance(declared, str):
        managers.append({"name": declared.split("@", 1)[0], "declared": declared, "evidence": "package.json#packageManager"})
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in managers:
        key = (str(item.get("name")), str(item.get("evidence")))
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def detect_frameworks(root: Path, deps: dict[str, str], all_text: str) -> list[dict[str, Any]]:
    frameworks: list[dict[str, Any]] = []

    def add(name: str, version: str | None, evidence: str) -> None:
        frameworks.append({"name": name, "version": version, "evidence": evidence})

    js_map = {
        "next": "Next.js", "react": "React", "vue": "Vue", "@sveltejs/kit": "SvelteKit",
        "svelte": "Svelte", "express": "Express", "fastify": "Fastify", "hono": "Hono",
        "nestjs": "NestJS", "@nestjs/core": "NestJS", "nuxt": "Nuxt",
    }
    for dep, name in js_map.items():
        if dep in deps:
            add(name, deps[dep], f"package.json:{dep}")

    pyproject = safe_read(root / "pyproject.toml") or ""
    requirements = safe_read(root / "requirements.txt") or ""
    python_text = (pyproject + "\n" + requirements + "\n" + all_text[:200_000]).lower()
    for marker, name in (("django", "Django"), ("fastapi", "FastAPI"), ("flask", "Flask")):
        if marker in python_text:
            add(name, None, "Python manifest/source marker")

    composer = load_json(root / "composer.json")
    php_deps: dict[str, Any] = {}
    for key in ("require", "require-dev"):
        section = composer.get(key)
        if isinstance(section, dict):
            php_deps.update(section)
    if "laravel/framework" in php_deps or (root / "artisan").exists():
        add("Laravel", str(php_deps.get("laravel/framework")) if "laravel/framework" in php_deps else None, "composer.json/artisan")
    if "symfony/framework-bundle" in php_deps:
        add("Symfony", str(php_deps["symfony/framework-bundle"]), "composer.json")

    if (root / "go.mod").exists():
        add("Go", None, "go.mod")
    if (root / "Cargo.toml").exists():
        add("Rust", None, "Cargo.toml")

    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in frameworks:
        if item["name"] not in seen:
            seen.add(item["name"])
            unique.append(item)
    return unique


def detect_hosting(root: Path, files: list[Path], all_text: str) -> list[dict[str, str]]:
    names = {rel(path, root) for path in files}
    hosting: list[dict[str, str]] = []
    checks = [
        ("Vercel", "vercel.json", (root / "vercel.json").exists() or any(name.startswith(".vercel/") for name in names)),
        ("Netlify", "netlify.toml", (root / "netlify.toml").exists()),
        ("Cloudflare", "wrangler.toml/json", (root / "wrangler.toml").exists() or (root / "wrangler.json").exists()),
        ("Fly.io", "fly.toml", (root / "fly.toml").exists()),
        ("Railway", "railway.json", (root / "railway.json").exists()),
        ("Docker", "Dockerfile", any(Path(name).name.startswith("Dockerfile") for name in names)),
        ("GitHub Actions", ".github/workflows", any(name.startswith(".github/workflows/") for name in names)),
    ]
    for name, evidence, present in checks:
        if present:
            hosting.append({"name": name, "evidence": evidence})
    if "VERCEL_URL" in all_text or "VERCEL_ENV" in all_text:
        if not any(item["name"] == "Vercel" for item in hosting):
            hosting.append({"name": "Vercel", "evidence": "VERCEL_* marker"})
    return hosting


def detect_routes(root: Path, files: list[Path]) -> dict[str, Any]:
    routes: list[str] = []
    for path in files:
        name = rel(path, root)
        lower = name.lower()
        if re.search(r"(?:^|/)app/api/.+/route\.(?:ts|tsx|js|mjs)$", lower):
            routes.append(name)
        elif re.search(r"(?:^|/)pages/api/.+\.(?:ts|tsx|js|mjs)$", lower):
            routes.append(name)
        elif "/routes/" in lower or lower.endswith("urls.py"):
            routes.append(name)
    return {"count": len(routes), "examples": routes[:30], "truncated": len(routes) > 30}


def scan_project(root: Path, max_files: int) -> dict[str, Any]:
    files = list(iter_files(root, max_files))
    texts: list[tuple[Path, str]] = []
    skipped = 0
    env_names: set[str] = set()
    for path in files:
        text = safe_read(path)
        if text is None:
            skipped += 1
            continue
        texts.append((path, text))
        if path.name.startswith(".env"):
            env_names.update(ENV_NAME_RE.findall(text))

    package_json = load_json(root / "package.json")
    deps = dependency_map(package_json)
    service_parts = [" ".join(deps.keys()), " ".join(env_names)]
    feature_parts = [" ".join(deps.keys())]
    for file_path, file_text in texts:
        service_parts.append(file_text[:50_000])
        # SERVICE_ROLE and similar environment names describe provider
        # credentials, not necessarily application roles. Exclude .env content
        # from feature inference to reduce that false positive.
        if not file_path.name.startswith(".env"):
            feature_parts.append(file_text[:50_000])
    all_text = "\n".join(service_parts)
    all_lower = all_text.lower()
    feature_lower = "\n".join(feature_parts).lower()

    services: list[dict[str, Any]] = []
    for service, markers in SERVICE_MARKERS.items():
        found = [marker for marker in markers if marker.lower() in all_lower]
        if found:
            services.append({"name": service, "evidence": sorted(set(found))[:10]})

    features: list[dict[str, Any]] = []
    for feature, patterns in FEATURE_PATTERNS.items():
        found = [pattern for pattern in patterns if pattern.lower() in feature_lower]
        if found:
            features.append({"name": feature, "evidence": sorted(set(found))[:10]})

    environments = sorted({
        path.name for path, _ in texts
        if path.name.startswith(".env") or path.name in {"vercel.json", "netlify.toml", "fly.toml", "railway.json"}
    })

    return {
        "root": str(root),
        "git": git_info(root),
        "files_considered": len(files),
        "files_read": len(texts),
        "files_skipped": skipped,
        "file_limit_reached": len(files) >= max_files,
        "package_managers": detect_package_managers(root, package_json),
        "frameworks": detect_frameworks(root, deps, all_text),
        "hosting_and_ci": detect_hosting(root, files, all_text),
        "services": services,
        "features": features,
        "routes": detect_routes(root, files),
        "environment_files": environments,
        "environment_variable_names": sorted(env_names),
        "notes": [
            "Inventura je heuristická a musí být potvrzena ruční kontrolou.",
            "Skript nevytiskl hodnoty environment variables, nepoužil síť a nespustil projektový kód.",
        ],
    }


def render_markdown(result: dict[str, Any]) -> str:
    git = result["git"]
    lines = [
        "# Bodyguard: inventura projektu",
        "",
        f"- Kořen: `{result['root']}`",
        f"- Git větev: `{git.get('branch') or 'NEOVĚŘENO'}`",
        f"- Commit: `{git.get('commit') or 'NEOVĚŘENO'}`",
        f"- Pracovní strom: `{'změny' if git.get('dirty') else 'čistý' if git.get('dirty') is False else 'NEOVĚŘENO'}`",
        f"- Přečtené soubory: {result['files_read']} z {result['files_considered']}",
        "",
    ]
    for title, key in (
        ("Frameworky", "frameworks"),
        ("Package managery", "package_managers"),
        ("Hosting a CI", "hosting_and_ci"),
        ("Služby", "services"),
        ("Funkce", "features"),
    ):
        lines.append(f"## {title}")
        items = result[key]
        if not items:
            lines.append("- Nezjištěno")
        else:
            for item in items:
                version = f" {item['version']}" if item.get("version") else ""
                evidence = item.get("evidence")
                lines.append(f"- {item['name']}{version} — důkaz: `{evidence}`")
        lines.append("")
    lines.extend([
        "## API a route soubory",
        f"- Počet rozpoznaných kandidátů: {result['routes']['count']}",
    ])
    for route in result["routes"]["examples"]:
        lines.append(f"- `{route}`")
    lines.extend(["", "## Poznámky"])
    lines.extend(f"- {note}" for note in result["notes"])
    return "\n".join(lines)


def self_test() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "app" / "api" / "demo").mkdir(parents=True)
        (root / "package.json").write_text(
            json.dumps({
                "packageManager": "npm@10.0.0",
                "dependencies": {
                    "next": "16.0.0",
                    "react": "19.0.0",
                    "@supabase/supabase-js": "2.0.0",
                    "stripe": "18.0.0",
                },
            }),
            encoding="utf-8",
        )
        (root / "package-lock.json").write_text("{}\n", encoding="utf-8")
        (root / ".env.example").write_text(
            "SUPABASE_URL=https://example.invalid\nSUPABASE_PUBLISHABLE_KEY=placeholder\n",
            encoding="utf-8",
        )
        (root / "app" / "api" / "demo" / "route.ts").write_text(
            "export async function POST() { /* webhook upload auth */ }\n",
            encoding="utf-8",
        )
        result = scan_project(root, 100)
        framework_names = {item["name"] for item in result["frameworks"]}
        service_names = {item["name"] for item in result["services"]}
        assert "Next.js" in framework_names
        assert "Supabase" in service_names
        assert "Stripe" in service_names
        assert result["routes"]["count"] == 1
        serialized = json.dumps(result)
        assert "https://example.invalid" not in serialized
    print("detect_stack.py self-test: OK")
    return 0


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only stack and feature inventory for Bodyguard.")
    parser.add_argument("path", nargs="?", default=".", help="Kořenová složka projektu")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.self_test:
        return self_test()
    root = Path(args.path).expanduser().resolve()
    if not root.is_dir():
        print(f"Cesta není existující složka: {root}", file=sys.stderr)
        return 2
    if args.max_files < 1:
        print("--max-files musí být kladné číslo", file=sys.stderr)
        return 2
    try:
        result = scan_project(root, args.max_files)
    except Exception as exc:
        print(f"Inventura selhala bezpečným způsobem: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
