#!/usr/bin/env python3
"""Lightweight naming screen for domain and DNS sanity checks.

Usage:
    python scripts/naming_domain_screen.py debugdojo bugforge bugquest
"""

from __future__ import annotations

import json
import socket
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass


USER_AGENT = "CodeFlashNamingScreen/1.0"


@dataclass
class DomainStatus:
    domain: str
    registered: str
    registration_date: str
    dns_resolves: str
    note: str


def fetch_json(url: str) -> dict | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def rdap_status(domain: str) -> tuple[str, str, str]:
    url = f"https://rdap.org/domain/{domain}"
    try:
        payload = fetch_json(url)
    except Exception as exc:  # pragma: no cover - network failure path
        return ("unknown", "", f"rdap_error={type(exc).__name__}")

    if payload is None:
        return ("no", "", "rdap_404")

    registration_date = ""
    for event in payload.get("events", []):
        if event.get("eventAction") == "registration":
            registration_date = event.get("eventDate", "")
            break
    return ("yes", registration_date, "")


def dns_status(domain: str) -> tuple[str, str]:
    try:
        socket.getaddrinfo(domain, None)
        return ("yes", "")
    except socket.gaierror:
        return ("no", "")
    except Exception as exc:  # pragma: no cover - platform-specific path
        return ("unknown", f"dns_error={type(exc).__name__}")


def screen_name(name: str) -> list[DomainStatus]:
    rows: list[DomainStatus] = []
    for tld in (".com", ".ai"):
        domain = f"{name}{tld}"
        registered, registration_date, rdap_note = rdap_status(domain)
        resolves, dns_note = dns_status(domain)
        note = ", ".join(part for part in (rdap_note, dns_note) if part)
        rows.append(
            DomainStatus(
                domain=domain,
                registered=registered,
                registration_date=registration_date,
                dns_resolves=resolves,
                note=note,
            )
        )
    return rows


def print_table(rows: list[DomainStatus]) -> None:
    headers = ("domain", "registered", "registration_date", "dns_resolves", "note")
    widths = {header: len(header) for header in headers}

    for row in rows:
        for header in headers:
            widths[header] = max(widths[header], len(getattr(row, header)))

    def line(values: tuple[str, ...]) -> str:
        return " | ".join(value.ljust(widths[header]) for value, header in zip(values, headers))

    print(line(headers))
    print("-+-".join("-" * widths[header] for header in headers))
    for row in rows:
        print(
            line(
                (
                    row.domain,
                    row.registered,
                    row.registration_date,
                    row.dns_resolves,
                    row.note,
                )
            )
        )


def main(argv: list[str]) -> int:
    names = [arg.strip().lower() for arg in argv[1:] if arg.strip()]
    if not names:
        print("usage: python scripts/naming_domain_screen.py <candidate> [<candidate> ...]")
        return 1

    rows: list[DomainStatus] = []
    for name in names:
        rows.extend(screen_name(name))

    print_table(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
