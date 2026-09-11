#!/usr/bin/env python3
"""Perform a passive, unauthenticated check of one supplied HTTP(S) URL.

The script sends only GET requests to the supplied URL and redirect targets. It
never submits forms, guesses paths, logs in, stores cookies, or disables TLS
verification. DNS is resolved and the connection is pinned to a validated IP to
reduce server-side request forgery and DNS-rebinding risk.
"""

from __future__ import annotations

import argparse
import http.client
import ipaddress
import json
import re
import socket
import ssl
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

REDIRECT_STATUSES = {301, 302, 303, 307, 308}
SENSITIVE_QUERY_MARKERS = ("token", "secret", "password", "passwd", "key", "signature", "sig", "auth", "code")
SESSION_COOKIE_MARKERS = ("session", "sess", "auth", "token", "jwt", "login", "sid")

BODY_PATTERNS: tuple[tuple[str, re.Pattern[str], str, str], ...] = (
    (
        "debug_traceback",
        re.compile(r"Traceback \(most recent call last\)|Stack trace:|Whoops, looks like something went wrong|Django Version:", re.IGNORECASE),
        "high",
        "Odpověď připomíná vývojářskou chybovou stránku nebo traceback.",
    ),
    (
        "database_error_detail",
        re.compile(r"SQLSTATE\[|psycopg2\.|SequelizeDatabaseError|PrismaClientKnownRequestError|PDOException", re.IGNORECASE),
        "high",
        "Odpověď zřejmě odhaluje detail databázové chyby.",
    ),
    (
        "absolute_server_path",
        re.compile(r"(?:/var/www/|/home/[A-Za-z0-9._-]+/|[A-Z]:\\(?:Users|inetpub)\\)", re.IGNORECASE),
        "medium",
        "Odpověď zřejmě odhaluje interní cestu na serveru.",
    ),
    (
        "directory_listing",
        re.compile(r"<title>Index of /|Directory listing for /", re.IGNORECASE),
        "medium",
        "Odpověď vypadá jako veřejný výpis adresáře.",
    ),
)


@dataclass
class Finding:
    detector: str
    severity: str
    confidence: str
    layer: str
    evidence: str
    reason: str


class PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, connect_ip: str, timeout: float) -> None:
        super().__init__(host=host, port=port, timeout=timeout)
        self._connect_ip = connect_ip

    def connect(self) -> None:
        self.sock = socket.create_connection((self._connect_ip, self.port), self.timeout)
        if self._tunnel_host:
            self._tunnel()


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(
        self,
        host: str,
        port: int,
        connect_ip: str,
        timeout: float,
        context: ssl.SSLContext,
    ) -> None:
        super().__init__(host=host, port=port, timeout=timeout, context=context)
        self._connect_ip = connect_ip

    def connect(self) -> None:
        raw = socket.create_connection((self._connect_ip, self.port), self.timeout)
        if self._tunnel_host:
            self.sock = raw
            self._tunnel()
            assert self.sock is not None
            raw = self.sock
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


def sanitize_text(value: str, limit: int = 2_000) -> str:
    text = value.replace("\r", " ").replace("\n", " ").strip()
    text = re.sub(
        r"(?i)(token|secret|password|passwd|api[_-]?key|authorization|signature|sig)=([^&\s]+)",
        r"\1=<redacted>",
        text,
    )
    text = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~-]+", r"\1<redacted>", text)
    return text[:limit]


def display_url(raw_url: str) -> str:
    parsed = urlsplit(raw_url)
    query = []
    for key, _value in parse_qsl(parsed.query, keep_blank_values=True):
        # Query strings routinely contain personal data even when their names do
        # not look secret. Preserve only keys in all user-visible output.
        query.append((key, "<redacted>"))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query, doseq=True), ""))


def validate_url(raw_url: str, allow_private: bool) -> tuple[str, list[str], str, int]:
    parsed = urlsplit(raw_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Povoleny jsou pouze URL se schématem http nebo https.")
    if not parsed.hostname:
        raise ValueError("URL neobsahuje platný hostname.")
    if parsed.username or parsed.password:
        raise ValueError("URL s uživatelským jménem nebo heslem není povolena.")
    for key, _value in parse_qsl(parsed.query, keep_blank_values=True):
        if any(marker in key.lower() for marker in SENSITIVE_QUERY_MARKERS):
            raise ValueError(
                "URL obsahuje citlivě pojmenovaný query parametr. Pro pasivní kontrolu použij veřejnou URL bez tokenu, podpisu nebo hesla."
            )

    host = parsed.hostname.encode("idna").decode("ascii")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("DNS překlad selhal: " + sanitize_text(str(exc))) from exc

    addresses: list[str] = []
    for answer in answers:
        address = answer[4][0]
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise ValueError("DNS nevrátilo žádnou adresu.")

    if not allow_private:
        non_global = []
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not ip.is_global:
                non_global.append(address)
        if non_global:
            raise ValueError(
                "Cílový hostname se překládá na neveřejnou, lokální nebo rezervovanou IP adresu. "
                "Použij --allow-private jen pro vlastní lokální či staging prostředí."
            )
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, "")), addresses, host, port


def request_target(raw_url: str) -> str:
    parsed = urlsplit(raw_url)
    return urlunsplit(("", "", parsed.path or "/", parsed.query, ""))


def headers_to_map(headers: Iterable[tuple[str, str]]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for key, value in headers:
        result.setdefault(key.lower(), []).append(value)
    return result


def first_header(headers: dict[str, list[str]], name: str) -> str | None:
    values = headers.get(name.lower())
    return values[0] if values else None


def safe_header_value(name: str, value: str) -> str:
    lowered = name.lower()
    if lowered == "set-cookie":
        return "<cookie value omitted>"
    if lowered in {"authorization", "proxy-authorization"}:
        return "<redacted>"
    if lowered == "location":
        return display_url(value)
    return sanitize_text(value)


def parse_cookie_flags(raw_cookie: str) -> dict[str, Any]:
    first_segment = raw_cookie.split(";", 1)[0]
    name = first_segment.split("=", 1)[0].strip() or "<unknown>"
    same_site_match = re.search(r"(?i)(?:^|;)\s*samesite\s*=\s*(lax|strict|none)", raw_cookie)
    secure = bool(re.search(r"(?i)(?:^|;)\s*secure\s*(?:;|$)", raw_cookie))
    http_only = bool(re.search(r"(?i)(?:^|;)\s*httponly\s*(?:;|$)", raw_cookie))
    return {
        "name": name[:120],
        "secure": secure,
        "http_only": http_only,
        "same_site": same_site_match.group(1).lower() if same_site_match else None,
        "session_like": any(marker in name.lower() for marker in SESSION_COOKIE_MARKERS),
    }


def tls_details(connection: PinnedHTTPSConnection) -> dict[str, Any]:
    if connection.sock is None:
        return {}
    cert = connection.sock.getpeercert()
    result: dict[str, Any] = {}
    if not isinstance(cert, dict):
        return result
    not_after = cert.get("notAfter")
    if isinstance(not_after, str):
        try:
            epoch = ssl.cert_time_to_seconds(not_after)
            expiry = datetime.fromtimestamp(epoch, tz=timezone.utc)
            days = int((expiry - datetime.now(timezone.utc)).total_seconds() // 86_400)
            result["expires_at"] = expiry.isoformat()
            result["days_remaining"] = days
        except (ValueError, OverflowError):
            pass
    subject_alt_names = cert.get("subjectAltName")
    if isinstance(subject_alt_names, tuple):
        result["subject_alt_name_count"] = len(subject_alt_names)
    cipher = connection.sock.cipher()
    if cipher:
        result["cipher"] = cipher[0]
        result["tls_version"] = connection.sock.version()
    return result


def fetch_once(
    raw_url: str,
    addresses: list[str],
    host: str,
    port: int,
    timeout: float,
    max_bytes: int,
) -> dict[str, Any]:
    parsed = urlsplit(raw_url)
    errors: list[str] = []
    context = ssl.create_default_context()
    try:
        context.set_alpn_protocols(["http/1.1"])
    except NotImplementedError:
        pass

    for address in addresses:
        connection: PinnedHTTPConnection | PinnedHTTPSConnection
        try:
            if parsed.scheme == "https":
                connection = PinnedHTTPSConnection(host, port, address, timeout, context)
            else:
                connection = PinnedHTTPConnection(host, port, address, timeout)
            connection.connect()
            current_tls = tls_details(connection) if isinstance(connection, PinnedHTTPSConnection) else {}
            connection.request(
                "GET",
                request_target(raw_url),
                headers={
                    "User-Agent": "Bodyguard-Passive-Security-Check/1.0",
                    "Accept": "text/html,application/json;q=0.9,*/*;q=0.1",
                    "Accept-Encoding": "identity",
                    "Cache-Control": "no-cache",
                    "Range": f"bytes=0-{max_bytes - 1}",
                    "Connection": "close",
                },
            )
            response = connection.getresponse()
            raw_headers = response.getheaders()
            body = response.read(max_bytes + 1)
            truncated = len(body) > max_bytes
            if truncated:
                body = body[:max_bytes]
            connection.close()
            return {
                "status": response.status,
                "reason": sanitize_text(response.reason or ""),
                "headers": raw_headers,
                "body": body,
                "body_truncated": truncated,
                "connected_ip": address,
                "tls": current_tls,
            }
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            errors.append(f"{address}: {sanitize_text(str(exc), 500)}")
            try:
                connection.close()
            except (UnboundLocalError, OSError):
                pass
    raise OSError("; ".join(errors) or "Připojení selhalo.")


def analyze_response(
    url: str,
    status: int,
    headers: dict[str, list[str]],
    body: bytes,
    tls: dict[str, Any],
) -> tuple[list[Finding], list[dict[str, Any]], dict[str, str | None]]:
    findings: list[Finding] = []
    parsed = urlsplit(url)
    raw_content_type = first_header(headers, "content-type") or ""
    body_prefix = body[:512].lstrip().lower()
    is_html = "text/html" in raw_content_type.lower() or body_prefix.startswith((b"<!doctype html", b"<html"))

    selected_headers = {
        "strict-transport-security": first_header(headers, "strict-transport-security"),
        "content-security-policy": first_header(headers, "content-security-policy"),
        "content-security-policy-report-only": first_header(headers, "content-security-policy-report-only"),
        "x-content-type-options": first_header(headers, "x-content-type-options"),
        "x-frame-options": first_header(headers, "x-frame-options"),
        "referrer-policy": first_header(headers, "referrer-policy"),
        "permissions-policy": first_header(headers, "permissions-policy"),
        "access-control-allow-origin": first_header(headers, "access-control-allow-origin"),
        "access-control-allow-credentials": first_header(headers, "access-control-allow-credentials"),
        "cache-control": first_header(headers, "cache-control"),
        "server": first_header(headers, "server"),
        "x-powered-by": first_header(headers, "x-powered-by"),
        "content-type": first_header(headers, "content-type"),
    }
    selected_headers = {
        key: safe_header_value(key, value) if value is not None else None for key, value in selected_headers.items()
    }

    hsts = first_header(headers, "strict-transport-security")
    if parsed.scheme == "https" and not hsts:
        findings.append(
            Finding(
                "missing_hsts",
                "medium",
                "high",
                "live_application",
                "Finální HTTPS odpověď nemá Strict-Transport-Security.",
                "Prohlížeč nedostal pokyn používat pro tuto doménu vždy HTTPS. HSTS zapínej až po ověření všech dotčených HTTPS domén.",
            )
        )

    csp = first_header(headers, "content-security-policy")
    csp_report_only = first_header(headers, "content-security-policy-report-only")
    if is_html and not csp:
        evidence = "Chybí vynucovaná Content-Security-Policy na HTML odpovědi."
        if csp_report_only:
            evidence += " Přítomna je pouze report-only varianta."
        findings.append(
            Finding(
                "missing_enforced_csp",
                "medium",
                "high",
                "live_application",
                evidence,
                "CSP omezuje, odkud může prohlížeč načítat a spouštět obsah; report-only politika sama útok neblokuje.",
            )
        )
    elif is_html:
        lowered_csp = csp.lower()
        weak_signals = []
        if re.search(r"(?:default-src|script-src)[^;]*\*", lowered_csp):
            weak_signals.append("wildcard u default-src nebo script-src")
        if "'unsafe-eval'" in lowered_csp:
            weak_signals.append("unsafe-eval")
        if "'unsafe-inline'" in lowered_csp:
            weak_signals.append("unsafe-inline")
        if weak_signals:
            findings.append(
                Finding(
                    "broad_csp_review",
                    "medium",
                    "medium",
                    "live_application",
                    "CSP obsahuje: " + ", ".join(weak_signals) + ".",
                    "Přítomnost CSP nestačí; široká pravidla mohou výrazně snížit její ochranu. Posuď nonce, hash a skutečné zdroje aplikace.",
                )
            )

    frame_ancestors = bool(csp and re.search(r"(?:^|;)\s*frame-ancestors\s+", csp, re.IGNORECASE))
    xfo = first_header(headers, "x-frame-options")
    if is_html and not frame_ancestors and not xfo:
        findings.append(
            Finding(
                "missing_frame_embedding_policy",
                "low",
                "high",
                "live_application",
                "Chybí CSP frame-ancestors i X-Frame-Options.",
                "Web nemá z odpovědi zřejmou ochranu proti nechtěnému vložení do cizí stránky. Ověř, zda legitimní iframe není součástí produktu.",
            )
        )

    if (first_header(headers, "x-content-type-options") or "").lower() != "nosniff":
        findings.append(
            Finding(
                "missing_nosniff",
                "low",
                "high",
                "live_application",
                "X-Content-Type-Options není nastaveno na nosniff.",
                "Prohlížeč může hádat typ obsahu místo respektování deklarovaného Content-Type.",
            )
        )

    if is_html and not first_header(headers, "referrer-policy"):
        findings.append(
            Finding(
                "missing_referrer_policy",
                "low",
                "high",
                "live_application",
                "Chybí Referrer-Policy.",
                "Aplikace neurčuje, kolik informace o původní URL se má posílat při přechodu jinam.",
            )
        )

    acao = first_header(headers, "access-control-allow-origin")
    acac = (first_header(headers, "access-control-allow-credentials") or "").lower()
    if acao == "*" and acac == "true":
        findings.append(
            Finding(
                "invalid_cors_combination",
                "medium",
                "high",
                "live_application",
                "Access-Control-Allow-Origin je * a Access-Control-Allow-Credentials je true.",
                "Tato kombinace je v prohlížeči neplatná a často ukazuje na nepochopenou CORS konfiguraci. Wildcard sám není automatická chyba u veřejného neautentizovaného zdroje.",
            )
        )

    if first_header(headers, "x-powered-by"):
        findings.append(
            Finding(
                "technology_header_disclosure",
                "low",
                "high",
                "live_application",
                "Odpověď obsahuje X-Powered-By.",
                "Hlavička zbytečně prozrazuje technologii. Sama o sobě obvykle není závažná, ale lze ji odstranit.",
            )
        )

    cookies = [parse_cookie_flags(raw) for raw in headers.get("set-cookie", [])]
    for cookie in cookies:
        if parsed.scheme == "https" and not cookie["secure"]:
            findings.append(
                Finding(
                    "cookie_missing_secure",
                    "high" if cookie["session_like"] else "medium",
                    "high",
                    "live_application",
                    f"Cookie {cookie['name']} nemá atribut Secure.",
                    "Cookie může být bez tohoto atributu odeslána i přes nezabezpečené HTTP spojení.",
                )
            )
        if cookie["session_like"] and not cookie["http_only"]:
            findings.append(
                Finding(
                    "session_cookie_missing_httponly",
                    "high",
                    "medium",
                    "live_application",
                    f"Session-like cookie {cookie['name']} nemá HttpOnly.",
                    "JavaScript na stránce může cookie přečíst. Název je pouze heuristika; potvrď skutečný účel cookie.",
                )
            )
        if cookie["session_like"] and not cookie["same_site"]:
            findings.append(
                Finding(
                    "session_cookie_missing_samesite",
                    "medium",
                    "medium",
                    "live_application",
                    f"Session-like cookie {cookie['name']} nemá zřejmý SameSite atribut.",
                    "SameSite pomáhá omezit podvržené požadavky z cizích stránek, ale nenahrazuje ve všech případech CSRF ochranu.",
                )
            )
        if cookie["same_site"] == "none" and not cookie["secure"]:
            findings.append(
                Finding(
                    "samesite_none_without_secure",
                    "medium",
                    "high",
                    "live_application",
                    f"Cookie {cookie['name']} používá SameSite=None bez Secure.",
                    "Moderní prohlížeče takovou cookie obvykle odmítnou; konfigurace je nekonzistentní.",
                )
            )

    days_remaining = tls.get("days_remaining")
    if isinstance(days_remaining, int) and days_remaining < 30:
        findings.append(
            Finding(
                "tls_certificate_expiry",
                "high" if days_remaining < 14 else "medium",
                "high",
                "live_application",
                f"TLS certifikát má přibližně {days_remaining} dní do expirace.",
                "Ověř automatickou obnovu certifikátu a upozornění. Krátká platnost může být normální jen tehdy, když obnova spolehlivě funguje.",
            )
        )

    content_type = first_header(headers, "content-type") or ""
    charset_match = re.search(r"charset=([A-Za-z0-9._-]+)", content_type, re.IGNORECASE)
    encoding = charset_match.group(1) if charset_match else "utf-8"
    try:
        text = body.decode(encoding, "replace")
    except LookupError:
        text = body.decode("utf-8", "replace")
    for detector, pattern, severity, reason in BODY_PATTERNS:
        if pattern.search(text):
            findings.append(
                Finding(
                    detector,
                    severity,
                    "medium",
                    "live_application",
                    "V omezeném vzorku těla odpovědi byl nalezen odpovídající signál; obsah se záměrně nevypisuje.",
                    reason,
                )
            )

    if status >= 500:
        findings.append(
            Finding(
                "server_error_response",
                "medium",
                "high",
                "live_application",
                f"Kontrolovaná URL vrátila HTTP {status}.",
                "Serverová chyba neznamená automaticky bezpečnostní zranitelnost, ale brání spolehlivému ověření a může odhalovat detaily.",
            )
        )

    return findings, cookies, selected_headers


def format_text(payload: dict[str, Any]) -> str:
    lines = [
        "Bodyguard passive live check",
        f"Počáteční URL: {payload['requested_url']}",
        f"Finální URL: {payload.get('final_url', '<nedostupná>')}",
        f"HTTP stav: {payload.get('status', '<nedostupný>')}",
        f"Nálezy: {payload['summary']['finding_count']}",
    ]
    for index, finding in enumerate(payload.get("findings", []), start=1):
        lines.append(
            f"{index}. [{finding['severity'].upper()}] {finding['detector']}: {finding['evidence']}"
        )
        lines.append("   " + finding["reason"])
    for error in payload.get("errors", []):
        lines.append("Chyba: " + error)
    return "\n".join(lines)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Passive unauthenticated check of one supplied HTTP(S) URL.")
    parser.add_argument("url", help="Veřejná URL bez přihlašovacího nebo podpisového tokenu")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    parser.add_argument("--timeout", type=float, default=10.0, help="Timeout jednoho připojení v sekundách")
    parser.add_argument("--max-bytes", type=int, default=262_144, help="Maximum načtených bajtů těla odpovědi")
    parser.add_argument("--max-redirects", type=int, default=5, help="Maximum následovaných redirectů")
    parser.add_argument(
        "--allow-private",
        action="store_true",
        help="Povolit lokální nebo privátní IP pouze pro vlastní lokální/staging prostředí",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.timeout <= 0 or args.max_bytes < 1 or args.max_redirects < 0:
        print("Timeout a max-bytes musí být kladné; max-redirects nesmí být záporné.", file=sys.stderr)
        return 3

    requested_display = display_url(args.url)
    payload: dict[str, Any] = {
        "tool": "bodyguard-passive-live-check",
        "requested_url": requested_display,
        "read_only": True,
        "authenticated": False,
        "path_enumeration": False,
        "tls_verification_disabled": False,
        "limitations": [
            "Kontrola se týká pouze dodané URL a neprochází další cesty.",
            "Bez přihlášení nelze ověřit autorizaci, soukromé odpovědi ani session workflow.",
            "Hlavičky se mohou lišit podle cesty, CDN, regionu a přihlášení.",
            "Nález chybějící hlavičky vyžaduje posouzení podle funkce aplikace.",
        ],
        "redirects": [],
        "findings": [],
        "errors": [],
    }

    current = args.url
    try:
        for redirect_index in range(args.max_redirects + 1):
            normalized, addresses, host, port = validate_url(current, args.allow_private)
            response = fetch_once(normalized, addresses, host, port, args.timeout, args.max_bytes)
            header_map = headers_to_map(response["headers"])
            status = int(response["status"])
            location = first_header(header_map, "location")
            if status in REDIRECT_STATUSES and location:
                if redirect_index >= args.max_redirects:
                    raise ValueError("Byl překročen povolený počet redirectů.")
                target = urljoin(normalized, location)
                payload["redirects"].append(
                    {
                        "status": status,
                        "from": display_url(normalized),
                        "to": display_url(target),
                    }
                )
                current = target
                continue

            findings, cookies, selected_headers = analyze_response(
                normalized,
                status,
                header_map,
                response["body"],
                response["tls"],
            )
            payload.update(
                {
                    "final_url": display_url(normalized),
                    "status": status,
                    "reason": response["reason"],
                    "connected_ip": response["connected_ip"],
                    "body_bytes_read": len(response["body"]),
                    "body_truncated": response["body_truncated"],
                    "tls": response["tls"],
                    "selected_headers": selected_headers,
                    "cookies": cookies,
                    "findings": [asdict(finding) for finding in findings],
                }
            )
            break
    except (ValueError, OSError, ssl.SSLError, http.client.HTTPException) as exc:
        payload["errors"].append(sanitize_text(str(exc)))

    findings_list = payload.get("findings", [])
    if not payload["errors"]:
        for redirect in payload.get("redirects", []):
            if urlsplit(redirect["from"]).scheme == "https" and urlsplit(redirect["to"]).scheme == "http":
                findings_list.append(
                    asdict(
                        Finding(
                            "https_to_http_redirect",
                            "high",
                            "high",
                            "live_application",
                            f"Redirect {redirect['from']} směřuje z HTTPS na HTTP.",
                            "Přesměrování snižuje ochranu přenosu a může vystavit data nebo uživatele nezabezpečenému spojení.",
                        )
                    )
                )
        payload["findings"] = findings_list
    payload["summary"] = {
        "finding_count": len(findings_list),
        "error_count": len(payload["errors"]),
        "severity_counts": {
            severity: sum(1 for item in findings_list if item.get("severity") == severity)
            for severity in ("critical", "high", "medium", "low")
        },
    }

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_text(payload))

    if payload["errors"]:
        return 3
    if findings_list:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
