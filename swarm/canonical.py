"""Canonical grids and the hashes the contract checks.

A grid is ASCII: one digit 0-9 per cell, rows joined by ';'.
Example: [[1, 2], [3, 0]] -> '12;30'.

answer hash = hex sha256(canonical utf-8)
commitment = hex sha256(canonical + '|' + salt)
"""

from __future__ import annotations

import hashlib
import re

from swarm.rules import MAX_SIDE, MAX_STRING

_GRID = re.compile(r"[0-9;]+")
_SALT = re.compile(r"[A-Za-z0-9]{1,64}")
_HEX64 = re.compile(r"[0-9a-f]{64}")


def parse_grid(text: str) -> list[list[int]]:
    if not isinstance(text, str) or not text or len(text) > MAX_STRING:
        raise ValueError("bad grid")
    if not _GRID.fullmatch(text) or text[0] == ";" or text[-1] == ";":
        raise ValueError("bad grid")
    rows = text.split(";")
    width = len(rows[0])
    if width == 0 or width > MAX_SIDE or len(rows) > MAX_SIDE:
        raise ValueError("bad grid")
    if any(len(row) != width for row in rows):
        raise ValueError("bad grid")
    return [[int(ch) for ch in row] for row in rows]


def canonical(grid: list[list[int]]) -> str:
    if not grid or not grid[0]:
        raise ValueError("bad grid")
    width = len(grid[0])
    if len(grid) > MAX_SIDE or width > MAX_SIDE:
        raise ValueError("bad grid")
    rows = []
    for row in grid:
        if len(row) != width:
            raise ValueError("bad grid")
        chars = []
        for value in row:
            if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 9:
                raise ValueError("bad grid")
            chars.append(str(value))
        rows.append("".join(chars))
    return ";".join(rows)


def valid_grid(text: str) -> bool:
    try:
        parse_grid(text)
    except ValueError:
        return False
    return True


def valid_salt(salt: str) -> bool:
    return isinstance(salt, str) and bool(_SALT.fullmatch(salt))


def valid_hash(text: str) -> bool:
    return isinstance(text, str) and bool(_HEX64.fullmatch(text))


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def answer_hash(grid_or_text: list[list[int]] | str) -> str:
    text = grid_or_text if isinstance(grid_or_text, str) else canonical(grid_or_text)
    parse_grid(text)
    return sha256_hex(text)


def commitment(grid_or_text: list[list[int]] | str, salt: str) -> str:
    if not valid_salt(salt):
        raise ValueError("bad salt")
    text = grid_or_text if isinstance(grid_or_text, str) else canonical(grid_or_text)
    parse_grid(text)
    return sha256_hex(f"{text}|{salt}")


def encode_demos(demos: list[tuple[list[list[int]], list[list[int]]]]) -> str:
    parts = [f"{canonical(inp)}|{canonical(out)}" for inp, out in demos]
    if not parts:
        raise ValueError("no demos")
    encoded = "&".join(parts)
    if len(encoded) > MAX_STRING:
        raise ValueError("demos too long")
    decode_demos(encoded)
    return encoded


def decode_demos(text: str) -> list[tuple[str, str]]:
    if not text or len(text) > MAX_STRING or "&" not in text and "|" not in text:
        raise ValueError("bad demos")
    pairs = []
    for part in text.split("&"):
        pieces = part.split("|")
        if len(pieces) != 2:
            raise ValueError("bad demos")
        parse_grid(pieces[0])
        parse_grid(pieces[1])
        pairs.append((pieces[0], pieces[1]))
    if not pairs:
        raise ValueError("bad demos")
    return pairs
