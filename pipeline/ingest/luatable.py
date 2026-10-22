"""Minimal Lua table-literal parser (no external Lua library)."""
import re

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_ESCAPES = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", "'": "'", '"': '"'}
_PUNCT = "{}[]=,"


def _tokenize(text: str) -> list[tuple[str, object]]:
    tokens: list[tuple[str, object]] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif text.startswith("--", i):
            m = re.match(r"--\[(=*)\[", text[i:])
            if m:
                close = "]" + m.group(1) + "]"
                end = text.find(close, i)
                if end < 0:
                    raise ValueError("unterminated block comment")
                i = end + len(close)
            else:
                end = text.find("\n", i)
                i = n if end < 0 else end
        elif c in "\"'":
            i, s = _read_string(text, i)
            tokens.append(("str", s))
        elif c in _PUNCT:
            tokens.append((c, c))
            i += 1
        else:
            m = _NUMBER.match(text, i)
            if m:
                raw = m.group()
                is_float = any(ch in raw for ch in ".eE")
                tokens.append(("num", float(raw) if is_float else int(raw)))
                i = m.end()
                continue
            m = _NAME.match(text, i)
            if not m:
                raise ValueError(f"unexpected character {c!r} at offset {i}")
            tokens.append(("name", m.group()))
            i = m.end()
    return tokens


def _read_string(text: str, i: int) -> tuple[int, str]:
    quote = text[i]
    i += 1
    out: list[str] = []
    while i < len(text):
        c = text[i]
        if c == quote:
            return i + 1, "".join(out)
        if c == "\\":
            i += 1
            if i >= len(text):
                break
            e = text[i]
            if e == "\r" and text[i + 1 : i + 2] == "\n":  # backslash-newline
                i += 1
                out.append("\n")
            elif e == "\n":
                out.append("\n")
            elif e.isdigit():
                m = re.compile(r"\d{1,3}").match(text, i)
                value = int(m.group())
                if value > 255:
                    raise ValueError(f"decimal escape too large at offset {i - 1}")
                out.append(chr(value))
                i = m.end() - 1
            elif e in _ESCAPES:
                out.append(_ESCAPES[e])
            else:
                raise ValueError(f"unsupported escape '\\{e}' at offset {i - 1}")
        else:
            out.append(c)
        i += 1
    raise ValueError("unterminated string")


class _Parser:
    def __init__(self, tokens: list[tuple[str, object]]):
        self.t = tokens
        self.i = 0

    def peek(self) -> tuple[str, object] | None:
        return self.t[self.i] if self.i < len(self.t) else None

    def expect(self, kind: str) -> object:
        tok = self.peek()
        if tok is None or tok[0] != kind:
            raise ValueError(f"expected {kind!r}, got {tok!r}")
        self.i += 1
        return tok[1]

    def parse_value(self):
        tok = self.peek()
        if tok is None:
            raise ValueError("unexpected end of input")
        kind, val = tok
        if kind == "{":
            return self.parse_table()
        if kind in ("str", "num"):
            self.i += 1
            return val
        if kind == "name" and val in ("true", "false", "nil"):
            self.i += 1
            return {"true": True, "false": False, "nil": None}[val]
        raise ValueError(f"unexpected token {tok!r}")

    def parse_table(self):
        self.expect("{")
        items: dict = {}
        positional = 0
        while True:
            tok = self.peek()
            if tok is None:
                raise ValueError("unterminated table")
            if tok[0] == "}":
                self.i += 1
                break
            if tok[0] == "[":
                self.i += 1
                key = self.parse_value()
                self.expect("]")
                self.expect("=")
                items[key] = self.parse_value()
            else:
                positional += 1
                items[positional] = self.parse_value()
            nxt = self.peek()
            if nxt is not None and nxt[0] == ",":
                self.i += 1
        if all(k == idx for idx, k in enumerate(items, start=1)):
            return list(items.values())
        return items


def parse_lua_table(text: str) -> dict | list:
    """Parse the first table literal that follows the first `=` in text."""
    tokens = _tokenize(text)
    for idx, (kind, _) in enumerate(tokens):
        if kind == "=":
            return _Parser(tokens[idx + 1 :]).parse_table()
    raise ValueError("no '=' found")
