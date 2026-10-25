"""Server-side request guard: links users paste are fetched by the server, so
they must point at the public internet, not at the API itself, the host's
private network or cloud metadata addresses (SSRF)."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit


def is_public_url(url: str) -> bool:
    """http(s) on the default port, and every address the host resolves to is public."""
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return False
    if parts.scheme not in ("http", "https") or not parts.hostname or port not in (None, 80, 443):
        return False
    try:
        infos = socket.getaddrinfo(parts.hostname, port or 443, proto=socket.IPPROTO_TCP)
    except OSError:
        return False
    addresses = {info[4][0] for info in infos}
    return bool(addresses) and all(ipaddress.ip_address(a).is_global for a in addresses)
