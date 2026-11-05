"""Minimal parser for Valve KeyValues text files (``.vdf`` / ``.acf``).

Supports quoted and unquoted tokens, nested blocks, ``//`` comments and the
``\\\\`` / ``\\"`` escapes used in Steam library paths.
"""
from __future__ import annotations

from typing import Any


class VdfError(ValueError):
    pass


def _tokens(text: str):
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c == "/" and text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
        elif c in "{}":
            yield c
            i += 1
        elif c == '"':
            i += 1
            out = []
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    nxt = text[i + 1]
                    out.append({"n": "\n", "t": "\t"}.get(nxt, nxt))
                    i += 2
                else:
                    out.append(text[i])
                    i += 1
            if i >= n:
                raise VdfError("unterminated string")
            i += 1
            yield ("s", "".join(out))
        else:
            start = i
            while i < n and not text[i].isspace() and text[i] not in '{}"':
                i += 1
            yield ("s", text[start:i])


def loads(text: str) -> dict[str, Any]:
    stack: list[dict[str, Any]] = [{}]
    key: str | None = None
    for tok in _tokens(text.lstrip("\ufeff")):
        if tok == "{":
            if key is None:
                raise VdfError("block without a key")
            child: dict[str, Any] = {}
            stack[-1][key] = child
            stack.append(child)
            key = None
        elif tok == "}":
            if len(stack) == 1:
                raise VdfError("unbalanced '}'")
            stack.pop()
        else:
            value = tok[1]
            if key is None:
                key = value
            else:
                stack[-1][key] = value
                key = None
    if len(stack) != 1:
        raise VdfError("unclosed block")
    return stack[0]


def get_ci(d: dict[str, Any], key: str, default: Any = None) -> Any:
    """Case-insensitive lookup (Valve files are inconsistent: AppState vs appstate)."""
    low = key.lower()
    for k, v in d.items():
        if k.lower() == low:
            return v
    return default
