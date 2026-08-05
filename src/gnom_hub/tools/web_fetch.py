"""Safe HTTP fetch for tools — blocks SSRF to private networks by default."""

from __future__ import annotations

import ipaddress
import os
import re
import socket
import urllib.error
import urllib.request
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "noscript"):
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript"):
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip:
            t = data.strip()
            if t:
                self._chunks.append(t)

    def text(self) -> str:
        return "\n".join(self._chunks)


def _is_private_host(host: str) -> bool:
    host = host.strip("[]").lower()
    if host in ("localhost", "0.0.0.0"):
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True  # unresolvable → block
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return True
    return False


def web_fetch(
    url: str,
    *,
    max_chars: int = 8000,
    timeout: float = 12.0,
) -> dict[str, Any]:
    """
    Fetch a public HTTP(S) URL and return plain text.
    Blocks private/localhost unless GNOM_WEB_ALLOW_LOCAL=1.
    """
    raw = (url or "").strip()
    if not raw:
        return {"ok": False, "error": "empty url"}
    if not re.match(r"^https?://", raw, flags=re.IGNORECASE):
        return {"ok": False, "error": "only http/https allowed"}

    parsed = urlparse(raw)
    host = parsed.hostname or ""
    if not host:
        return {"ok": False, "error": "missing host"}

    allow_local = os.getenv("GNOM_WEB_ALLOW_LOCAL", "0").strip() in ("1", "true", "yes")
    if not allow_local and _is_private_host(host):
        return {"ok": False, "error": "private/local hosts blocked (set GNOM_WEB_ALLOW_LOCAL=1)"}

    class _SafeRedirect(urllib.request.HTTPRedirectHandler):
        """Re-check every redirect hop so public→private SSRF is blocked."""

        def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
            parsed_new = urlparse(newurl)
            new_host = parsed_new.hostname or ""
            if not re.match(r"^https?://", newurl, flags=re.IGNORECASE):
                raise urllib.error.HTTPError(newurl, 403, "redirect scheme blocked", headers, fp)
            if not allow_local and new_host and _is_private_host(new_host):
                raise urllib.error.HTTPError(
                    newurl, 403, "redirect to private/local host blocked", headers, fp
                )
            return urllib.request.HTTPRedirectHandler.redirect_request(
                self, req, fp, code, msg, headers, newurl
            )

    req = urllib.request.Request(
        raw,
        headers={
            "User-Agent": "Gnom-Hub/1.8 web_fetch",
            "Accept": "text/html,application/xhtml+xml,text/plain,*/*;q=0.8",
        },
        method="GET",
    )
    opener = urllib.request.build_opener(_SafeRedirect())
    try:
        with opener.open(req, timeout=timeout) as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            data = resp.read(600_000)
            final_url = resp.geturl()
            status = resp.getcode()
    except urllib.error.HTTPError as e:
        err = str(e.reason) if e.reason else f"HTTP {e.code}"
        if e.code == 403 and "private" in err.lower():
            return {"ok": False, "error": err, "url": raw}
        return {"ok": False, "error": f"HTTP {e.code}" + (f" ({err})" if err else ""), "url": raw}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "url": raw}

    # Defense in depth: re-validate final URL after redirects
    final_host = urlparse(final_url).hostname or ""
    if not allow_local and final_host and _is_private_host(final_host):
        return {
            "ok": False,
            "error": "final URL resolved to private/local host (blocked)",
            "url": final_url,
        }

    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        text = data.decode("latin-1", errors="replace")

    if (
        "html" in ctype
        or text.lstrip().lower().startswith("<!doctype")
        or "<html" in text[:200].lower()
    ):
        parser = _TextExtractor()
        try:
            parser.feed(text)
            text = parser.text()
        except Exception:  # noqa: BLE001
            text = re.sub(r"<[^>]+>", " ", text)

    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > max_chars:
        text = text[: max_chars - 1] + "…"

    return {
        "ok": True,
        "url": final_url,
        "status": status,
        "content_type": ctype,
        "text": text,
        "chars": len(text),
    }
