"""Minimal ESC/POS builder + raw TCP sender for network thermal printers.

Only plain printable ASCII is ever sent: cheap printers ship with unknown code
pages, so Uzbek apostrophes (o', g') and Cyrillic are normalised/transliterated
here instead of risking garbage on paper.
"""

from __future__ import annotations

import asyncio
import ipaddress
import textwrap
import unicodedata

ESC = b"\x1b"
GS = b"\x1d"

# Chars per line (Font A) for the two common paper widths.
CHARS_PER_LINE = {58: 32, 80: 48}

_APOSTROPHES = "‘’ʻʼ`´′"
_CYRILLIC = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya", "ў": "o'", "қ": "q", "ғ": "g'", "ҳ": "h",
}


def to_printable_ascii(text: str) -> str:
    out: list[str] = []
    for ch in text:
        if ch in _APOSTROPHES:
            out.append("'")
            continue
        low = ch.lower()
        if low in _CYRILLIC:
            tr = _CYRILLIC[low]
            out.append(tr.capitalize() if ch != low else tr)
            continue
        out.append(ch)
    folded = unicodedata.normalize("NFKD", "".join(out))
    return "".join(c if 32 <= ord(c) <= 126 else ("" if unicodedata.combining(c) else "?") for c in folded)


class Escpos:
    def __init__(self, paper_width: int = 80) -> None:
        self.width = CHARS_PER_LINE.get(paper_width, 48)
        self._buf = bytearray(ESC + b"@")  # initialise printer

    def align(self, where: str) -> "Escpos":
        self._buf += ESC + b"a" + bytes([{"left": 0, "center": 1, "right": 2}[where]])
        return self

    def bold(self, on: bool) -> "Escpos":
        self._buf += ESC + b"E" + (b"\x01" if on else b"\x00")
        return self

    def big(self, on: bool) -> "Escpos":
        self._buf += GS + b"!" + (b"\x11" if on else b"\x00")
        return self

    def text(self, value: str = "") -> "Escpos":
        for part in (to_printable_ascii(value) or "").split("\n"):
            lines = textwrap.wrap(part, self.width) if part else [""]
            for line in lines:
                self._buf += line.encode("ascii") + b"\n"
        return self

    def rule(self, char: str = "-") -> "Escpos":
        return self.text(char * self.width)

    def columns(self, left: str, right: str) -> "Escpos":
        left, right = to_printable_ascii(left), to_printable_ascii(right)
        gap = self.width - len(right)
        if gap < 2:
            return self.text(left).align("right").text(right).align("left")
        return self.text(left[: gap - 1].ljust(gap) + right)

    def feed(self, lines: int = 3) -> "Escpos":
        self._buf += b"\n" * lines
        return self

    def cut(self) -> "Escpos":
        self._buf += GS + b"VB\x00"  # feed then partial cut
        return self

    def to_bytes(self) -> bytes:
        return bytes(self._buf)


def validate_private_ipv4(host: str) -> str:
    """Printers live on the LAN: accept only private IPv4 literals so the
    server can never be pointed at loopback, link-local/metadata or public
    hosts through this setting."""
    try:
        ip = ipaddress.ip_address(host.strip())
    except ValueError as exc:
        raise ValueError("Printer address must be an IPv4 address like 192.168.1.50") from exc
    if ip.version != 4 or not ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_unspecified:
        raise ValueError("Printer address must be a private LAN IPv4 (10.x, 172.16-31.x, 192.168.x)")
    return str(ip)


async def send(host: str, port: int, data: bytes, *, connect_timeout: float = 3.0, write_timeout: float = 5.0) -> None:
    reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), connect_timeout)
    try:
        writer.write(data)
        await asyncio.wait_for(writer.drain(), write_timeout)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # noqa: BLE001 — printer may drop the socket right after receiving
            pass
