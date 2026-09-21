#!/usr/bin/env python3
"""Render a small Markdown subset to PDF, using nothing but the standard library.

This host has no PDF toolchain at all -- no pandoc, no weasyprint, no reportlab,
not even the `markdown` module -- and it is shared with other vhosts, so
installing one for a recurring management summary is a bigger commitment than
writing one. Everything else in this workspace is stdlib-only for the same
reason (ops/feedback/collector.py is a plain ThreadingHTTPServer), so this fits
the house style rather than breaking it.

Supported, because that is what a management summary actually uses:

    # / ## / ###    headings
    paragraphs      wrapped, justified left
    - bullets       including a second level with two spaces of indent
    | tables |      rendered as rows with a light rule
    ---             horizontal rule
    **bold**        inline, real Helvetica-Bold runs
    `code`          inline, Courier

Deliberately NOT supported: images, links as clickable areas, nested emphasis,
numbered-list renumbering. A summary that needs those wants a real typesetter.

Encoding: the core PDF fonts are WinAnsi, so characters outside it (arrows, box
drawing, emoji) are transliterated rather than silently dropped -- a dropped
glyph reads as a typo, a transliterated one reads as a choice.
"""
from __future__ import annotations

import re
import sys
import zlib
from pathlib import Path

# --- page geometry (A4, points) -------------------------------------------
PAGE_W, PAGE_H = 595.28, 841.89
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 62.0, 72.0, 64.0
CONTENT_W = PAGE_W - 2 * MARGIN_X

BODY_SIZE, BODY_LEAD = 10.5, 15.5
H_SIZES = {1: 20.0, 2: 14.5, 3: 11.5}
H_LEAD = {1: 26.0, 2: 21.0, 3: 17.0}
H_SPACE_BEFORE = {1: 0.0, 2: 17.0, 3: 12.0}

ACCENT = (0.09, 0.42, 0.62)
INK = (0.13, 0.14, 0.16)
MUTED = (0.42, 0.44, 0.47)
RULE = (0.80, 0.82, 0.85)

REGULAR, BOLD, MONO = "F1", "F2", "F3"

#: Real Helvetica advance widths (per 1000 units), not estimates. Letters
#: inside a word are positioned by the viewer's own metrics, so only the gap
#: BETWEEN words depends on this table -- but an underestimate there makes
#: words collide, which is exactly the kind of defect nobody notices until the
#: PDF is already in a manager's inbox.
_W = {
    " ": 278, "!": 278, '"': 355, "#": 556, "$": 556, "%": 889, "&": 667,
    "'": 191, "(": 333, ")": 333, "*": 389, "+": 584, ",": 278, "-": 333,
    ".": 278, "/": 278, ":": 278, ";": 278, "<": 584, "=": 584, ">": 584,
    "?": 556, "@": 1015, "[": 278, "\\": 278, "]": 278, "^": 469, "_": 556,
    "`": 333, "{": 334, "|": 260, "}": 334, "~": 584,
    "a": 556, "b": 556, "c": 500, "d": 556, "e": 556, "f": 278, "g": 556,
    "h": 556, "i": 222, "j": 222, "k": 500, "l": 222, "m": 833, "n": 556,
    "o": 556, "p": 556, "q": 556, "r": 333, "s": 500, "t": 278, "u": 556,
    "v": 500, "w": 722, "x": 500, "y": 500, "z": 500,
    "A": 667, "B": 667, "C": 722, "D": 722, "E": 667, "F": 611, "G": 778,
    "H": 722, "I": 278, "J": 500, "K": 667, "L": 556, "M": 833, "N": 722,
    "O": 778, "P": 667, "Q": 778, "R": 722, "S": 667, "T": 611, "U": 722,
    "V": 667, "W": 944, "X": 667, "Y": 667, "Z": 611,
}
for _c in "0123456789": _W[_c] = 556

#: WinAnsi has no arrows, box drawing or emoji. Say what they meant instead.
TRANSLITERATE = {
    "—": "-", "–": "-", "→": "->", "←": "<-", "↔": "<->", "·": "-",
    "“": '"', "”": '"', "‘": "'", "’": "'", "…": "...", "•": "-",
    "✅": "[OK]", "✔": "[OK]", "❌": "[x]", "⚠": "[!]", "🔴": "[!]",
    "🟢": "[ok]", "📬": "", "💬": "", "⏸": "", "⏵": "", "×": "x",
    "≥": ">=", "≤": "<=", "│": "|", "▼": "v", "└": "+", "├": "+", "─": "-",
}


def sanitize(text: str) -> str:
    for bad, good in TRANSLITERATE.items():
        text = text.replace(bad, good)
    # Anything still outside WinAnsi would break the content stream.
    return "".join(ch if ord(ch) < 256 else "?" for ch in text)


def width_of(text: str, size: float, bold: bool = False) -> float:
    total = sum(_W.get(ch, 500) for ch in text)
    if bold:
        total *= 1.06  # Helvetica-Bold runs a little wider
    return total / 1000.0 * size


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


# --- inline parsing --------------------------------------------------------

_INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")


def runs(text: str) -> list:
    """Split a line into (text, font) pairs, honouring **bold** and `code`."""
    out = []
    for part in _INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            # `code` nested inside **bold** is common in these documents. The
            # bold alternation wins the match, so strip the backticks rather
            # than printing them: one font per run, and bold is the outer one.
            out.append((part[2:-2].replace("`", ""), BOLD))
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            out.append((part[1:-1], MONO))
        else:
            out.append((part.replace("**", ""), REGULAR))
    return out or [("", REGULAR)]


def wrap_runs(parts: list, size: float, max_width: float) -> list:
    """Greedy wrap that keeps each run's font. Returns a list of lines."""
    lines, line, used = [], [], 0.0
    for text, font in parts:
        for word in re.split(r"(\s+)", text):
            if not word:
                continue
            w = width_of(word, size, font == BOLD)
            if word.isspace():
                if line and used + w <= max_width:
                    line.append((word, font))
                    used += w
                continue
            if used + w > max_width and line:
                lines.append(line)
                line, used = [], 0.0
            line.append((word, font))
            used += w
    if line:
        lines.append(line)
    return lines or [[("", REGULAR)]]


# --- document model --------------------------------------------------------

class Doc:
    def __init__(self, subtitle: str = ""):
        self.pages, self.ops = [], []
        self.y = MARGIN_TOP
        self.subtitle = subtitle

    # -- low level
    def _color(self, rgb):
        self.ops.append(f"{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} rg")

    def _text(self, x, y, size, font, text):
        self.ops.append(
            f"BT /{font} {size:.2f} Tf 1 0 0 1 {x:.2f} {PAGE_H - y:.2f} Tm "
            f"({_escape(text)}) Tj ET")

    def _rule(self, y, color=RULE, width=0.6, x0=None, x1=None):
        self.ops.append(
            f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} RG {width} w "
            f"{(x0 or MARGIN_X):.2f} {PAGE_H - y:.2f} m "
            f"{(x1 or PAGE_W - MARGIN_X):.2f} {PAGE_H - y:.2f} l S")

    def _break(self, needed: float):
        if self.y + needed > PAGE_H - MARGIN_BOTTOM:
            self.new_page()

    def new_page(self):
        if self.ops:
            self.pages.append("\n".join(self.ops))
        self.ops, self.y = [], MARGIN_TOP

    # -- blocks
    def line_runs(self, parts, size, lead, color=INK, indent=0.0):
        for line in wrap_runs(parts, size, CONTENT_W - indent):
            self._break(lead)
            x = MARGIN_X + indent
            self._color(color)
            for text, font in line:
                self._text(x, self.y + size, size, font, sanitize(text))
                x += width_of(text, size, font == BOLD)
            self.y += lead

    def heading(self, level, text):
        size, lead = H_SIZES[level], H_LEAD[level]
        self._break(lead + H_SPACE_BEFORE[level] + 6)
        self.y += H_SPACE_BEFORE[level]
        color = ACCENT if level <= 2 else INK
        for line in wrap_runs(runs(text), size, CONTENT_W):
            x = MARGIN_X
            self._color(color)
            for t, f in line:
                self._text(x, self.y + size, size, BOLD, sanitize(t))
                x += width_of(t, size, True)
            self.y += lead
        if level == 1:
            self._rule(self.y - 4, ACCENT, 1.2)
            self.y += 8
        elif level == 2:
            self._rule(self.y - 5, RULE, 0.6)
            self.y += 6

    def paragraph(self, text):
        self.line_runs(runs(text), BODY_SIZE, BODY_LEAD)
        self.y += 5

    def bullet(self, text, depth=0):
        indent = 14.0 + depth * 14.0
        self._break(BODY_LEAD)
        self._color(ACCENT)
        self._text(MARGIN_X + depth * 14.0, self.y + BODY_SIZE, BODY_SIZE, REGULAR, "-")
        self.line_runs(runs(text), BODY_SIZE, BODY_LEAD, indent=indent)

    def table_row(self, cells, header=False):
        size = BODY_SIZE - 0.5
        widths = [CONTENT_W / len(cells)] * len(cells)
        wrapped = [wrap_runs(runs(c), size, w - 8) for c, w in zip(cells, widths)]
        height = max(len(w) for w in wrapped) * (BODY_LEAD - 1.5)
        self._break(height + 4)
        top = self.y
        for idx, lines in enumerate(wrapped):
            x0 = MARGIN_X + sum(widths[:idx])
            y = top
            for line in lines:
                x = x0
                self._color(INK if not header else ACCENT)
                for t, f in line:
                    self._text(x, y + size, size, BOLD if header else f, sanitize(t))
                    x += width_of(t, size, header or f == BOLD)
                y += BODY_LEAD - 1.5
        self.y = top + height + 3
        self._rule(self.y - 1)
        self.y += 3

    def rule(self):
        self._break(12)
        self.y += 4
        self._rule(self.y)
        self.y += 10

    def footer_ops(self, page_no, total):
        label = f"{self.subtitle}  ·  halaman {page_no} dari {total}"
        size = 8.0
        w = width_of(sanitize(label), size)
        return (f"{MUTED[0]:.3f} {MUTED[1]:.3f} {MUTED[2]:.3f} rg "
                f"BT /{REGULAR} {size:.2f} Tf 1 0 0 1 {PAGE_W - MARGIN_X - w:.2f} "
                f"{MARGIN_BOTTOM - 28:.2f} Tm ({_escape(sanitize(label))}) Tj ET")


# --- markdown -> document --------------------------------------------------

def render(markdown: str, subtitle: str = "") -> Doc:
    doc = Doc(subtitle)
    rows_pending = []

    def flush_table():
        nonlocal rows_pending
        for i, row in enumerate(rows_pending):
            doc.table_row(row, header=(i == 0))
        if rows_pending:
            doc.y += 4
        rows_pending = []

    for raw in markdown.splitlines():
        line = raw.rstrip()
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue  # the |---|---| separator row
            rows_pending.append(cells)
            continue
        flush_table()

        if not line.strip():
            doc.y += 4
            continue
        if re.fullmatch(r"-{3,}", line.strip()):
            doc.rule()
            continue
        m = re.match(r"^(#{1,3})\s+(.*)$", line)
        if m:
            doc.heading(len(m.group(1)), m.group(2))
            continue
        m = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if m:
            doc.bullet(m.group(2), depth=1 if len(m.group(1)) >= 2 else 0)
            continue
        doc.paragraph(line.strip())

    flush_table()
    doc.new_page()
    return doc


# --- PDF assembly ----------------------------------------------------------

def build(doc: Doc) -> bytes:
    total = len(doc.pages)
    streams = []
    for i, content in enumerate(doc.pages, start=1):
        streams.append(zlib.compress((content + "\n" + doc.footer_ops(i, total)).encode("latin-1", "replace")))

    objects, page_ids = [], []
    # 1 catalog, 2 pages, then 3 fonts, then per page: page + content
    font_ids = {REGULAR: 3, BOLD: 4, MONO: 5}
    first_page_id = 6
    for i in range(total):
        page_ids.append(first_page_id + i * 2)

    objects.append((1, b"<< /Type /Catalog /Pages 2 0 R >>"))
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects.append((2, f"<< /Type /Pages /Count {total} /Kids [{kids}] >>".encode()))
    for name, base in ((REGULAR, "Helvetica"), (BOLD, "Helvetica-Bold"), (MONO, "Courier")):
        objects.append((font_ids[name],
                        f"<< /Type /Font /Subtype /Type1 /BaseFont /{base} "
                        f"/Encoding /WinAnsiEncoding >>".encode()))
    for i, pid in enumerate(page_ids):
        cid = pid + 1
        objects.append((pid, (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W:.2f} {PAGE_H:.2f}] "
            f"/Resources << /Font << /{REGULAR} {font_ids[REGULAR]} 0 R "
            f"/{BOLD} {font_ids[BOLD]} 0 R /{MONO} {font_ids[MONO]} 0 R >> >> "
            f"/Contents {cid} 0 R >>").encode()))
        objects.append((cid, b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(streams[i])
                        + streams[i] + b"\nendstream"))

    objects.sort(key=lambda o: o[0])
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for num, body in objects:
        offsets[num] = len(out)
        out += f"{num} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    highest = max(offsets)
    out += f"xref\n0 {highest + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for num in range(1, highest + 1):
        out += f"{offsets.get(num, 0):010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {highest + 1} /Root 1 0 R >>\nstartxref\n"
            f"{xref_at}\n%%EOF\n").encode()
    return bytes(out)


def convert(markdown: str, subtitle: str = "") -> bytes:
    return build(render(markdown, subtitle))


def main(argv: list) -> int:
    if len(argv) < 3:
        print("usage: md2pdf.py <input.md> <output.pdf> [subtitle]")
        return 2
    src, dst = Path(argv[1]), Path(argv[2])
    subtitle = argv[3] if len(argv) > 3 else src.stem
    data = convert(src.read_text(encoding="utf-8"), subtitle)
    dst.write_bytes(data)
    print(f"{dst} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
