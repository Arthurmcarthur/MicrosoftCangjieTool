"""從 URL 取得 txt 碼表。只用標準庫 urllib，不加依賴。"""
from __future__ import annotations

import hashlib
import re
import urllib.request
from pathlib import Path

_UA = "cjtoolkit/2.0 (+https://github.com/Arthurmcarthur/MicrosoftCangjieTool)"

_GITHUB_BLOB = re.compile(
    r"^https://github\.com/([^/]+)/([^/]+)/blob/(.+)$"
)


def normalise_url(url: str) -> str:
    """github.com/.../blob/... → raw.githubusercontent.com/...；其餘原樣。"""
    m = _GITHUB_BLOB.match(url)
    if m:
        user, repo, rest = m.groups()
        return f"https://raw.githubusercontent.com/{user}/{repo}/{rest}"
    return url


def fetch_text(url: str, *, timeout: float = 30.0) -> str:
    url = normalise_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (http(s) only)
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"只接受 http(s) URL: {url!r}")
        raw = resp.read()
    return raw.decode("utf-8-sig")


def fetch_to_file(url: str, dest: Path, *, timeout: float = 30.0) -> Path:
    text = fetch_text(url, timeout=timeout)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    return dest


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
