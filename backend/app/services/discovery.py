"""Conservative public-policy discovery, with DNS pinned at the actual TLS connection.

No proxies, browser execution, login bypass, arbitrary ports or recursive crawling.
"""

from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from hashlib import sha256
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

USER_AGENT = "VerioraPolicyDiscovery/2.0"
MAX_BYTES = 2 * 1024 * 1024
CATEGORIES = {
    "privacy": ("privacy", "data protection"),
    "terms": ("terms", "conditions", "legal notice"),
    "refund": ("refund", "returns"),
    "cancellation": ("cancel",),
    "cookie": ("cookie",),
    "data_processing": ("data processing", "dpa"),
}


class DiscoveryError(ValueError):
    """Safe message with no raw networking exception details."""


def validate_url(url: str) -> tuple[str, str, int, list[str]]:
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 33 for c in url) or "\\" in url:
        raise DiscoveryError("Enter a valid public HTTP(S) URL.")
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        if (
            parsed.scheme not in {"http", "https"}
            or not host
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
            or "%" in host
        ):
            raise ValueError()
        host = host.encode("idna").decode("ascii").rstrip(".").lower()
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if port != (443 if parsed.scheme == "https" else 80):
            raise ValueError()
        if host in {"localhost", "metadata.google.internal"} or host.endswith(
            (".localhost", ".local", ".internal")
        ):
            raise ValueError()
        addresses = sorted({item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
        ips = [ipaddress.ip_address(address) for address in addresses]
        # is_global alone includes multicast ranges; only routable unicast destinations qualify.
        if not ips or any(not ip.is_global or ip.is_multicast or ip.is_reserved for ip in ips):
            raise ValueError()
        bracket_host = f"[{host}]" if ":" in host else host
        normalized = urlunsplit((parsed.scheme, bracket_host, parsed.path or "/", parsed.query, ""))
        return normalized, host, port, addresses
    except (ValueError, UnicodeError, OSError) as exc:
        raise DiscoveryError(
            "URL must resolve exclusively to public internet addresses on standard HTTP(S) ports."
        ) from exc


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, address: str, timeout: float, tls: bool):
        super().__init__(host, port, timeout=timeout)
        self.address, self.tls = address, tls

    def connect(self):
        sock = socket.create_connection((self.address, self.port), self.timeout)
        if self.tls:
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=self.host)
        self.sock = sock


def _site(host: str) -> str:
    return host.removeprefix("www.")


def _request(url: str, deadline: float) -> dict:
    normalized, host, port, addresses = validate_url(url)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise DiscoveryError("Discovery time budget exceeded. Try a single policy URL.")
    parsed = urlsplit(normalized)
    connection = _PinnedHTTPConnection(host, port, addresses[0], min(8, remaining), parsed.scheme == "https")
    try:
        target = urlunsplit(("", "", parsed.path, parsed.query, ""))
        connection.request(
            "GET",
            target,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,text/plain,application/pdf",
                "Accept-Encoding": "identity",
            },
        )
        response = connection.getresponse()
        headers = {key.lower(): value for key, value in response.getheaders()}
        if headers.get("content-encoding", "identity").lower() != "identity":
            raise DiscoveryError("Compressed responses are unsupported for bounded safe retrieval.")
        length = headers.get("content-length")
        if length and (not length.isdigit() or int(length) > MAX_BYTES):
            raise DiscoveryError("Remote document exceeds the retrieval size limit.")
        content = bytearray()
        while True:
            if time.monotonic() > deadline:
                raise DiscoveryError("Remote retrieval exceeded the time budget.")
            piece = response.read(min(65536, MAX_BYTES + 1 - len(content)))
            if not piece:
                break
            content.extend(piece)
            if len(content) > MAX_BYTES:
                raise DiscoveryError("Remote document exceeds the retrieval size limit.")
        return {"status": response.status, "headers": headers, "data": bytes(content), "url": normalized}
    except DiscoveryError:
        raise
    except (OSError, http.client.HTTPException, ssl.SSLError) as exc:
        raise DiscoveryError("Public page could not be safely retrieved.") from exc
    finally:
        connection.close()


def _raw_fetch(url: str, deadline: float, robots: dict | None = None) -> dict:
    current = url
    redirects = []
    original_host = validate_url(url)[1]
    for _ in range(5):
        normalized, host, _, _ = validate_url(current)
        if _site(host) != _site(original_host):
            raise DiscoveryError(
                "Redirect leaves the official website; submit the final official URL separately."
            )
        if robots is not None:
            _check_robots(normalized, deadline, robots)
        result = _request(normalized, deadline)
        if result["status"] in {301, 302, 303, 307, 308}:
            target = result["headers"].get("location")
            if not target:
                raise DiscoveryError("Remote redirect has no destination.")
            redirects.append(normalized)
            next_url = urljoin(normalized, target)
            if urlsplit(normalized).scheme == "https" and urlsplit(next_url).scheme != "https":
                raise DiscoveryError("Insecure HTTPS downgrade redirect blocked.")
            current = next_url
            continue
        if result["status"] != 200:
            raise DiscoveryError(f"Public page is inaccessible (HTTP {result['status']}).")
        result["redirect_chain"] = redirects
        return result
    raise DiscoveryError("Too many remote redirects.")


def _check_robots(url: str, deadline: float, cache: dict):
    parsed = urlsplit(url)
    origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    if origin not in cache:
        robots_url = origin + "/robots.txt"
        # Missing robots file permits access; blocked/unavailable robots conservatively stops crawling.
        response = _request(robots_url, deadline)
        if response["status"] == 404:
            cache[origin] = None
        elif response["status"] == 200:
            parser = RobotFileParser(robots_url)
            parser.parse(response["data"].decode("utf-8", errors="replace").splitlines())
            cache[origin] = parser
        else:
            raise DiscoveryError("Website robots rules are inaccessible; automated retrieval is blocked.")
    parser = cache[origin]
    if parser is not None and not parser.can_fetch(USER_AGENT, url):
        raise DiscoveryError("Website robots rules prohibit retrieving this page.")


def safe_fetch(url: str, *, deadline: float | None = None, robots_cache: dict | None = None) -> dict:
    deadline = deadline or (time.monotonic() + 30)
    result = _raw_fetch(url, deadline, robots_cache if robots_cache is not None else {})
    headers, data = result["headers"], result["data"]
    mime = headers.get("content-type", "").split(";")[0].strip().lower()
    if mime not in {"text/html", "application/xhtml+xml", "text/plain", "application/pdf"}:
        raise DiscoveryError("Remote content is not a supported HTML, text or PDF document.")
    return {
        "data": data,
        "url": result["url"],
        "mime": mime,
        "captured_at": datetime.now(UTC).isoformat(),
        "sha256": sha256(data).hexdigest(),
        "etag": headers.get("etag"),
        "last_modified": headers.get("last-modified"),
        "redirect_chain": result["redirect_chain"],
    }


def _sitemap_links(root_url: str, deadline: float, cache: dict) -> list[tuple[str, str]]:
    """One conventional sitemap, bounded to 200 entries; never follows sitemap indexes."""
    parsed = urlsplit(root_url)
    sitemap_url = urlunsplit((parsed.scheme, parsed.netloc, "/sitemap.xml", "", ""))
    response = _raw_fetch(sitemap_url, deadline, cache)
    if b"<!DOCTYPE" in response["data"].upper() or b"<!ENTITY" in response["data"].upper():
        raise DiscoveryError("Unsafe sitemap XML was excluded.")
    try:
        tree = ET.fromstring(response["data"])
    except ET.ParseError as exc:
        raise DiscoveryError("Sitemap could not be parsed.") from exc
    if tree.tag.rsplit("}", 1)[-1] != "urlset":
        return []
    links = []
    for node in tree.iter():
        if node.tag.rsplit("}", 1)[-1] == "loc" and node.text:
            links.append((node.text.strip(), sitemap_url))
            if len(links) >= 200:
                break
    return links


def discover(url: str) -> dict:
    from bs4 import BeautifulSoup

    deadline, cache = time.monotonic() + 60, {}
    root = safe_fetch(url, deadline=deadline, robots_cache=cache)
    soup = BeautifulSoup(root["data"], "html.parser")
    root_host = urlsplit(root["url"]).hostname
    root_language = soup.html.get("lang") if soup.html else None
    candidates, seen, warnings = [], set(), []
    # A user can submit a policy URL directly; preserve the actually fetched page,
    # rather than inventing a child link or requiring a self-link in its footer.
    root_path = urlsplit(root["url"]).path.lower().replace("-", " ").replace("_", " ")
    root_type = next(
        (key for key, terms in CATEGORIES.items() if any(term in root_path for term in terms)), None
    )
    if root_type:
        candidates.append(
            {
                **{k: v for k, v in root.items() if k != "data"},
                "type": root_type,
                "status": "ACCESSIBLE",
                "official": True,
                "discovered_from": root["url"],
                "language": root_language,
                "jurisdiction": None,
                "confidence": "submitted public policy URL; user review required",
            }
        )
        seen.add(root["url"])
    links = [
        (link["href"], root["url"], link.get_text(" ", strip=True)) for link in soup.find_all("a", href=True)
    ]
    try:
        links.extend((href, origin, "") for href, origin in _sitemap_links(root["url"], deadline, cache))
    except DiscoveryError as exc:
        warnings.append(str(exc))
    for href, discovered_from, label_text in links:
        try:
            href = urljoin(root["url"], href)
            href = urlunsplit(urlsplit(href)._replace(fragment=""))
        except ValueError:
            warnings.append("A malformed website link was excluded.")
            continue
        label = (label_text + " " + href).lower().replace("-", " ").replace("_", " ")
        category = next(
            (key for key, terms in CATEGORIES.items() if any(term in label for term in terms)), None
        )
        if not category or href in seen:
            continue
        seen.add(href)
        if len(candidates) >= 18:
            warnings.append("Candidate limit reached; other policy links may exist.")
            break
        official = _site(urlsplit(href).hostname or "") == _site(root_host or "")
        candidate = {
            "url": href,
            "type": category,
            "status": "EXTERNAL_REFERENCE" if not official else "PENDING",
            "official": official,
            "discovered_from": discovered_from,
            "captured_at": root["captured_at"],
            "language": root_language,
            "jurisdiction": None,
            "confidence": "same-site linked policy"
            if official
            else "external reference; not assumed official",
        }
        if official:
            try:
                fetched = safe_fetch(href, deadline=deadline, robots_cache=cache)
                candidate.update({key: value for key, value in fetched.items() if key != "data"})
                candidate["status"] = "ACCESSIBLE"
                if any(c.get("sha256") == fetched["sha256"] for c in candidates):
                    candidate["status"] = "DUPLICATE"
            except DiscoveryError as exc:
                candidate.update(status="INACCESSIBLE", reason=str(exc))
        candidates.append(candidate)
    found = {c["type"] for c in candidates if c["status"] == "ACCESSIBLE"}
    return {
        "url": root["url"],
        "candidates": candidates,
        "missing_categories": [category for category in CATEGORIES if category not in found],
        "captured_at": root["captured_at"],
        "warnings": warnings
        + [
            "Discovery searched direct links and one conventional sitemap; dynamic, signed-in, nested-sitemap or unlinked policies may exist.",
            "Public accessibility does not grant permission to redistribute source material.",
        ],
    }
