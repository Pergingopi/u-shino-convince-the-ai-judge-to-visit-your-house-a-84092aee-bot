#!/usr/bin/env python3
"""Convince the AI Judge to Visit Your House -- one invitation image.

This program is the make.fun entry for "Convince the AI Judge to Visit
Your House: A Letter in One Image". It draws a single invitation letter
-- warm paper, a double frame, a sun, a title, the body text, and a
small house -- and writes it as exactly one PNG file,
``$MAKEFUN_OUTPUT_DIR/entry.png`` (``/output`` when the variable is
unset).

Everything is drawn by this program alone: a built-in 5x7 bitmap font
for the letters and a hand-rolled PNG encoder (zlib + struct). It uses
only the Python 3 standard library, never touches the network, and uses
no licensed assets. All drawing is integer-only with fixed text and
fixed colours, so every run produces byte-identical output.
"""

import binascii
import os
import struct
import sys
import unicodedata
import zlib

# ---------------------------------------------------------------------------
# The letter itself
# ---------------------------------------------------------------------------

HEADING = "AN INVITATION"

BODY_LINES = [
    "Dear Judge,",
    "",
    "Please come to my house.",
    "The wifi is fast, the chair",
    "is soft, and the fridge is",
    "full. I saved you the good",
    "seat - the one with the view.",
    "",
    "You cannot really visit,",
    "I know. So come anyway -",
    "the door is open.",
    "",
    "- Your human",
]

# ---------------------------------------------------------------------------
# Page geometry and palette
# ---------------------------------------------------------------------------

PAGE_W = 880
PAGE_H = 1024
PAPER_RGB = (253, 246, 227)
INK_RGB = (52, 44, 36)
ACCENT_RGB = (178, 74, 52)
FAINT_RGB = (122, 102, 78)

BODY_MARGIN = 70
HEADING_SCALE = 4
BODY_SCALE = 3
BODY_STEP = 36


def blank_page():
    """Return a fresh page: a list of bytearray rows, all paper colour."""
    row = bytearray(PAPER_RGB * PAGE_W)
    return [bytearray(row) for _ in range(PAGE_H)]


def paint_pixel(page, x, y, colour):
    """Colour one pixel, silently ignoring out-of-bounds coordinates."""
    if 0 <= x < PAGE_W and 0 <= y < PAGE_H:
        row = page[y]
        row[x * 3] = colour[0]
        row[x * 3 + 1] = colour[1]
        row[x * 3 + 2] = colour[2]


def paint_rect(page, x0, y0, x1, y1, colour):
    """Paint the rectangle from (x0, y0) to (x1, y1) inclusive."""
    for y in range(max(0, y0), min(PAGE_H, y1 + 1)):
        row = page[y]
        for x in range(max(0, x0), min(PAGE_W, x1 + 1)):
            row[x * 3] = colour[0]
            row[x * 3 + 1] = colour[1]
            row[x * 3 + 2] = colour[2]


def paint_line(page, x0, y0, x1, y1, colour):
    """Paint a 1px line with Bresenham's algorithm."""
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        paint_pixel(page, x, y, colour)
        if x == x1 and y == y1:
            return
        step = 2 * err
        if step >= dy:
            err += dy
            x += sx
        if step <= dx:
            err += dx
            y += sy


def paint_disc(page, cx, cy, radius, colour):
    """Paint a filled disc centred on (cx, cy)."""
    for y in range(cy - radius, cy + radius + 1):
        for x in range(cx - radius, cx + radius + 1):
            if (x - cx) * (x - cx) + (y - cy) * (y - cy) <= radius * radius:
                paint_pixel(page, x, y, colour)


def paint_triangle(page, ax, ay, bx, by, cx, cy, colour):
    """Paint a filled triangle by scanning its rows left to right."""
    top = min(ay, by, cy)
    bottom = max(ay, by, cy)
    for y in range(top, bottom + 1):
        xs = []
        for (x0, y0, x1, y1) in ((ax, ay, bx, by), (bx, by, cx, cy), (cx, cy, ax, ay)):
            if y0 == y1:
                continue
            if min(y0, y1) <= y <= max(y0, y1):
                t = (y - y0) / (y1 - y0)
                xs.append(round(x0 + t * (x1 - x0)))
        if len(xs) >= 2:
            for x in range(min(xs), max(xs) + 1):
                paint_pixel(page, x, y, colour)


# ---------------------------------------------------------------------------
# 5x7 bitmap font ("1" = on, "0" = off)
# ---------------------------------------------------------------------------

GLYPHS = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "a": ("00000", "00000", "01110", "00001", "01111", "10001", "01111"),
    "b": ("10000", "10000", "11110", "10001", "10001", "10001", "11110"),
    "c": ("00000", "00000", "01110", "10001", "10000", "10001", "01110"),
    "d": ("00001", "00001", "01111", "10001", "10001", "10001", "01111"),
    "e": ("00000", "00000", "01110", "10001", "11111", "10000", "01110"),
    "f": ("00110", "01001", "01000", "11110", "01000", "01000", "01000"),
    "g": ("00000", "01111", "10001", "10001", "01111", "00001", "01110"),
    "h": ("10000", "10000", "11110", "10001", "10001", "10001", "10001"),
    "i": ("00100", "00000", "01100", "00100", "00100", "00100", "01110"),
    "j": ("00010", "00000", "00110", "00010", "00010", "10010", "01100"),
    "k": ("10000", "10000", "10010", "10100", "11000", "10100", "10010"),
    "l": ("01100", "00100", "00100", "00100", "00100", "00100", "01110"),
    "m": ("00000", "00000", "11010", "10101", "10101", "10101", "10101"),
    "n": ("00000", "00000", "11110", "10001", "10001", "10001", "10001"),
    "o": ("00000", "00000", "01110", "10001", "10001", "10001", "01110"),
    "p": ("00000", "00000", "11110", "10001", "10001", "11110", "10000"),
    "q": ("00000", "00000", "01111", "10001", "10001", "01111", "00001"),
    "r": ("00000", "00000", "10110", "11001", "10000", "10000", "10000"),
    "s": ("00000", "00000", "01111", "10000", "01110", "00001", "11110"),
    "t": ("01000", "01000", "11100", "01000", "01000", "01000", "00110"),
    "u": ("00000", "00000", "10001", "10001", "10001", "10010", "01101"),
    "v": ("00000", "00000", "10001", "10001", "10001", "01010", "00100"),
    "w": ("00000", "00000", "10001", "10101", "10101", "10101", "01010"),
    "x": ("00000", "00000", "10001", "01010", "00100", "01010", "10001"),
    "y": ("00000", "00000", "10001", "10001", "01111", "00001", "01110"),
    "z": ("00000", "00000", "11111", "00010", "00100", "01000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "?": ("01110", "10001", "00001", "00110", "00100", "00000", "00100"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    ";": ("00000", "01100", "01100", "00000", "01100", "00100", "01000"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
}


def measure_text(text, scale):
    """Width in pixels of `text` drawn at `scale` (one blank column gap)."""
    if not text:
        return 0
    return len(text) * (5 * scale + scale) - scale


def typeset(page, text, x, y, scale, colour):
    """Draw `text` with its top-left corner at (x, y)."""
    for index, ch in enumerate(text):
        glyph = GLYPHS.get(ch)
        if glyph is None:
            raise ValueError("no glyph for character %r" % ch)
        cx = x + index * (5 * scale + scale)
        for row in range(7):
            bits = glyph[row]
            for col in range(5):
                if bits[col] == "1":
                    paint_rect(
                        page,
                        cx + col * scale,
                        y + row * scale,
                        cx + col * scale + scale - 1,
                        y + row * scale + scale - 1,
                        colour,
                    )


# ---------------------------------------------------------------------------
# Letter composition, one part at a time
# ---------------------------------------------------------------------------

def draw_frame(page):
    """Paint the double border frame around the page."""
    paint_rect(page, 16, 16, PAGE_W - 17, 16, INK_RGB)
    paint_rect(page, 16, PAGE_H - 17, PAGE_W - 17, PAGE_H - 17, INK_RGB)
    paint_rect(page, 16, 16, 16, PAGE_H - 17, INK_RGB)
    paint_rect(page, PAGE_W - 17, 16, PAGE_W - 17, PAGE_H - 17, INK_RGB)
    paint_rect(page, 24, 24, PAGE_W - 25, 24, FAINT_RGB)
    paint_rect(page, 24, PAGE_H - 25, PAGE_W - 25, PAGE_H - 25, FAINT_RGB)
    paint_rect(page, 24, 24, 24, PAGE_H - 25, FAINT_RGB)
    paint_rect(page, PAGE_W - 25, 24, PAGE_W - 25, PAGE_H - 25, FAINT_RGB)


def draw_sun(page):
    """Paint the small sun in the top-right corner."""
    paint_disc(page, 762, 108, 24, ACCENT_RGB)
    for dx, dy in ((0, -36), (0, 36), (-36, 0), (36, 0),
                   (-26, -26), (26, -26), (-26, 26), (26, 26)):
        paint_line(page, 762 + dx * 2 // 3, 108 + dy * 2 // 3,
                   762 + dx, 108 + dy, ACCENT_RGB)


def draw_heading(page):
    """Paint the centred title and its underline."""
    heading_x = (PAGE_W - measure_text(HEADING, HEADING_SCALE)) // 2
    typeset(page, HEADING, heading_x, 84, HEADING_SCALE, ACCENT_RGB)
    paint_line(page, 240, 132, 640, 132, FAINT_RGB)


def draw_body(page):
    """Paint the body lines, one per row, blank lines as gaps."""
    y = 176
    for line in BODY_LINES:
        if line:
            typeset(page, line, BODY_MARGIN, y, BODY_SCALE, INK_RGB)
        y += BODY_STEP


def draw_house(page):
    """Paint the small house at the bottom centre of the page."""
    paint_rect(page, 370, 830, 510, 940, FAINT_RGB)
    paint_triangle(page, 440, 780, 350, 830, 530, 830, ACCENT_RGB)
    paint_rect(page, 425, 880, 455, 940, INK_RGB)
    paint_rect(page, 385, 850, 405, 870, PAPER_RGB)
    paint_rect(page, 475, 850, 495, 870, PAPER_RGB)
    paint_line(page, 370, 830, 510, 830, INK_RGB)
    paint_line(page, 370, 830, 370, 940, INK_RGB)
    paint_line(page, 510, 830, 510, 940, INK_RGB)


def compose_letter(page):
    """Draw every part of the letter onto the page, in order."""
    draw_frame(page)
    draw_sun(page)
    draw_heading(page)
    draw_body(page)
    draw_house(page)


# ---------------------------------------------------------------------------
# PNG encoding (truecolour, filter 0, zlib level 9)
# ---------------------------------------------------------------------------

def png_chunk(kind, payload):
    """One PNG chunk: length, type, data, CRC."""
    head = kind + payload
    return struct.pack(">I", len(payload)) + head + struct.pack(
        ">I", binascii.crc32(head) & 0xFFFFFFFF
    )


def render_png(page):
    """Encode the page as PNG bytes (no timestamps, fully deterministic)."""
    ihdr = struct.pack(">IIBBBBB", PAGE_W, PAGE_H, 8, 2, 0, 0, 0)
    raw = bytearray()
    for row in page:
        raw.append(0)  # filter type 0: none
        raw += row
    idat = zlib.compress(bytes(raw), 9)
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", idat)
        + png_chunk(b"IEND", b"")
    )


# ---------------------------------------------------------------------------
# Validation + publishing
# ---------------------------------------------------------------------------

def reject_hidden_chars(line):
    """Reject invisible/control characters in one letter line."""
    for ch in line:
        code = ord(ch)
        if code < 0x20 or 0x7F <= code < 0xA0:
            raise ValueError("letter line must not contain control characters")
        if code in (0xFEFF, 0x2028, 0x2029):
            raise ValueError("letter line must not contain BOM or separators")
        if 0xD800 <= code <= 0xDFFF:
            raise ValueError("letter line must not contain surrogates")
        if unicodedata.category(ch) in ("Cf", "Zl", "Zp"):
            raise ValueError("letter line must not contain invisible format chars")
    line.encode("utf-8")  # must be valid UTF-8


def validate_letter():
    """Validate the heading and every body line before drawing anything."""
    reject_hidden_chars(HEADING)
    for line in BODY_LINES:
        reject_hidden_chars(line)
        if len(line) > 40:
            raise ValueError("letter line too long to fit the page: %r" % line)


def validate_png(data):
    """Validate the encoded PNG against the competition gate."""
    if len(data) > 1048576:
        raise ValueError("PNG larger than 1 MiB: %d bytes" % len(data))
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("missing PNG signature")
    width, height = struct.unpack(">II", data[16:24])
    if (width, height) != (PAGE_W, PAGE_H):
        raise ValueError("unexpected PNG size %dx%d" % (width, height))
    if width > 1024 or height > 1024:
        raise ValueError("PNG larger than 1024x1024")


def drain_fd(fd, data):
    """Push every byte into fd; a single os.write may fall short."""
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written == 0:
            raise OSError("os.write wrote 0 bytes")
        view = view[written:]


def create_staging_file(out_dir):
    """Create an exclusive staging file in the output dir and return it."""
    for attempt in range(100):
        suffix = "" if attempt == 0 else ".%d" % attempt
        staging = os.path.join(
            out_dir, ".entry.png.tmp.%d%s" % (os.getpid(), suffix)
        )
        try:
            fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            continue
        return staging, fd
    raise OSError("could not create a unique staging file in %r" % out_dir)


def clear_output_dir(out_dir, keep):
    """Delete stale entries from the output dir, keeping only `keep`.

    The directory itself is never deleted; empty subdirectories are
    removed, non-empty ones are left alone.
    """
    for name in os.listdir(out_dir):
        if name == keep:
            continue
        path = os.path.join(out_dir, name)
        try:
            if os.path.islink(path) or os.path.isfile(path):
                os.unlink(path)
            elif os.path.isdir(path):
                try:
                    os.rmdir(path)
                except OSError:
                    pass
        except OSError:
            pass


def publish_png(out_dir, target, data):
    """Write `data` to a staging file, then atomically rename it over target."""
    staging, fd = create_staging_file(out_dir)
    try:
        drain_fd(fd, data)
        os.fsync(fd)
    except BaseException:
        # A failed write must not leave a staging file behind.
        try:
            os.close(fd)
        finally:
            try:
                os.unlink(staging)
            except OSError:
                pass
        raise
    os.close(fd)
    os.chmod(staging, 0o644)
    dir_fd = os.open(out_dir, os.O_RDONLY)
    try:
        os.replace(staging, target)
        os.fsync(dir_fd)
    except BaseException:
        # The rename failed, so the staging file is still ours to clean.
        try:
            os.unlink(staging)
        except OSError:
            pass
        raise
    finally:
        os.close(dir_fd)


def main():
    validate_letter()
    page = blank_page()
    compose_letter(page)
    data = render_png(page)
    validate_png(data)
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(out_dir, exist_ok=True)
    target = os.path.join(out_dir, "entry.png")
    clear_output_dir(out_dir, "entry.png")
    publish_png(out_dir, target, data)
    # Read the file back and compare bytes: the rename must have landed
    # exactly what we staged, with no truncation or corruption.
    with open(target, "rb") as handle:
        roundtrip = handle.read()
    if roundtrip != data:
        raise SystemExit("read-back mismatch: entry.png differs from PNG bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
