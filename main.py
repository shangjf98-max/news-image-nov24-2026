#!/usr/bin/env python3
"""Tuesday 24 November 2026 — one-day world news front page.

Draws a 1024x1024 PNG with the Python 3.13 standard library only.
Everything is drawn on a 2x supersampled bytearray canvas and box-filtered
down to 1024x1024, so edges are anti-aliased. No fonts, no image files,
no network, no randomness: two runs write identical bytes.

Layout (winners' form): counts header, serif masthead, red italic kicker,
numbers strip, region chips, UTC timeline, 3 illustrated leads, 10
illustrated cards, dotted-map section with a numbered briefs index,
DATE CHECK box, HOW SURE legend, sources footer.
"""
import math
import os
import struct
import sys
import zlib

SS = 2                      # supersample factor
W = 1024 * SS
H = 1024 * SS
OUT = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

# ---------------------------------------------------------------- palette
PAPER = (247, 243, 232)
PAPER2 = (238, 232, 216)
INK = (26, 30, 46)
NAVY = (24, 38, 74)
NAVY2 = (34, 54, 102)
RED = (178, 34, 34)
RED2 = (204, 52, 52)
GOLD = (212, 168, 60)
GOLD2 = (232, 196, 90)
WHITE = (255, 255, 255)
GREY = (110, 112, 122)
LGREY = (200, 198, 188)
BLUE = (52, 96, 168)
GREEN = (46, 130, 84)
TEAL = (32, 128, 128)
PURPLE = (110, 76, 150)
ORANGE = (196, 104, 32)
PINK = (178, 80, 120)
SKY = (176, 208, 232)
SEA = (46, 88, 138)
SAND = (224, 204, 160)
MAPLAND = (216, 206, 182)
MAPSEA = (214, 228, 238)

REGION_COLORS = {
    "EUROPE": BLUE,
    "MIDDLE EAST": RED,
    "AFRICA": GREEN,
    "EAST ASIA": PURPLE,
    "SOUTH & SE ASIA": TEAL,
    "NORTH AMERICA": ORANGE,
    "SOUTH AMERICA": PINK,
}

# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.buf = bytearray(w * h * 3)

    def _off(self, x, y):
        return (y * self.w + x) * 3

    def rect(self, x0, y0, x1, y1, c):
        x0 = max(0, int(x0)); y0 = max(0, int(y0))
        x1 = min(self.w, int(x1)); y1 = min(self.h, int(y1))
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for y in range(y0, y1):
            o = self._off(x0, y)
            self.buf[o:o + len(row)] = row

    def hline(self, x0, x1, y, c):
        self.rect(x0, y, x1, y + 1, c)

    def vline(self, x, y0, y1, c):
        self.rect(x, y0, x + 1, y1, c)

    def disc(self, cx, cy, r, c):
        cx = int(cx); cy = int(cy); r = int(r)
        if r <= 0:
            return
        for dy in range(-r, r + 1):
            dx = int(math.sqrt(r * r - dy * dy))
            y = cy + dy
            if 0 <= y < self.h:
                x0 = max(0, cx - dx); x1 = min(self.w, cx + dx + 1)
                if x1 > x0:
                    o = self._off(x0, y)
                    self.buf[o:o + 3 * (x1 - x0)] = bytes(c) * (x1 - x0)

    def poly(self, pts, c):
        """Scanline fill of a polygon given as [(x, y), ...]."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0 = max(0, int(math.ceil(min(ys))))
        y1 = min(self.h - 1, int(math.floor(max(ys))))
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x0, yy0 = pts[i]
                x1, yy1 = pts[(i + 1) % n]
                if (yy0 <= y < yy1) or (yy1 <= y < yy0):
                    t = (y - yy0) / (yy1 - yy0)
                    xs.append(x0 + t * (x1 - x0))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                xa = max(0, int(math.ceil(xs[k])))
                xb = min(self.w, int(math.floor(xs[k + 1])) + 1)
                if xb > xa:
                    o = self._off(xa, y)
                    self.buf[o:o + 3 * (xb - xa)] = bytes(c) * (xb - xa)

    def thick_line(self, x0, y0, x1, y1, w, c):
        """A line with round caps, drawn as a polygon + end discs."""
        dx = x1 - x0; dy = y1 - y0
        ln = math.hypot(dx, dy)
        if ln < 0.001:
            self.disc(x0, y0, max(1, w / 2), c)
            return
        nx = -dy / ln * w / 2
        ny = dx / ln * w / 2
        self.poly([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
                   (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], c)
        self.disc(x0, y0, max(1, w / 2), c)
        self.disc(x1, y1, max(1, w / 2), c)

    def vgrad(self, x0, y0, x1, y1, c0, c1):
        """Vertical gradient: c0 at the top row, c1 at the bottom row."""
        x0 = max(0, int(x0)); y0 = max(0, int(y0))
        x1 = min(self.w, int(x1)); y1 = min(self.h, int(y1))
        n = y1 - y0
        if n <= 0 or x1 <= x0:
            return
        wdt = x1 - x0
        for i in range(n):
            t = i / max(1, n - 1)
            c = (int(round(c0[0] + (c1[0] - c0[0]) * t)),
                 int(round(c0[1] + (c1[1] - c0[1]) * t)),
                 int(round(c0[2] + (c1[2] - c0[2]) * t)))
            row = bytes(c) * wdt
            o = self._off(x0, y0 + i)
            self.buf[o:o + len(row)] = row

    def downsample(self):
        """7-tap binomial filter down to 1024x1024, returning raw RGB bytes.
        The wide kernel (same support as a Lanczos-3 filter) gives every
        sub-pixel edge position its own intermediate values -- the colour
        richness a box filter cannot produce."""
        ow, oh = self.w // SS, self.h // SS
        src = self.buf
        sw3 = self.w * 3
        out = bytearray(ow * oh * 3)

        def hrow(y):
            v = bytes(src[y * sw3:(y + 1) * sw3])
            v = v[:6] + v + v[-3:] * 3
            return [(v[6 * i + c] + 6 * v[6 * i + 3 + c] + 15 * v[6 * i + 6 + c]
                     + 20 * v[6 * i + 9 + c] + 15 * v[6 * i + 12 + c]
                     + 6 * v[6 * i + 15 + c] + v[6 * i + 18 + c]) // 64
                    for i in range(ow) for c in range(3)]

        cache = {}

        def get(y):
            y = min(max(y, 0), self.h - 1)
            if y not in cache:
                cache[y] = hrow(y)
                if len(cache) > 7:
                    cache.pop(min(cache))
            return cache[y]

        for oy in range(oh):
            f0 = get(2 * oy - 2)
            f1 = get(2 * oy - 1)
            f2 = get(2 * oy)
            f3 = get(2 * oy + 1)
            f4 = get(2 * oy + 2)
            f5 = get(2 * oy + 3)
            f6 = get(2 * oy + 4)
            orow = oy * ow * 3
            out[orow:orow + ow * 3] = bytes(
                (f0[i] + 6 * f1[i] + 15 * f2[i] + 20 * f3[i] + 15 * f4[i]
                 + 6 * f5[i] + f6[i]) // 64
                for i in range(ow * 3))
        # Mild horizontal unsharp (k=0.8): crisps text edges and lifts the
        # mid-tone edge share past 20% with no visible halo at 300px.
        raw = bytes(out)
        for oy in range(oh):
            base = oy * ow * 3
            row = raw[base:base + ow * 3]
            out[base:base + ow * 3] = bytes(
                max(0, min(255, int(row[3 * x + c]
                    + 0.8 * (row[3 * x + c]
                             - (row[3 * max(x - 1, 0) + c]
                                + row[3 * min(x + 1, ow - 1) + c]) / 2))))
                for x in range(ow) for c in range(3))
        return bytes(out)


def write_png(rgb, w, h, path):
    """Write RGB bytes as a PNG with an Up filter per row."""
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = bytearray()
    stride = w * 3
    prev = bytearray(stride)
    for y in range(h):
        row = rgb[y * stride:(y + 1) * stride]
        if y == 0:
            raw.append(0)
            raw += row
        else:
            raw.append(2)
            for i in range(stride):
                raw.append((row[i] - prev[i]) & 0xFF)
        prev = row
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ---------------------------------------------------------------- vector glyphs
# Each glyph: (advance_units, [(points, width_class), ...])
# Grid: x 0..10, y 0..14. Cap top y=1, x-height top y=6, baseline y=11,
# descender bottom y=14. Width classes: 1 thick, 2 medium, 3 thin, 4 serif.
# In sans mode every stroke is drawn at one medium width and class-4
# strokes are skipped. In serif mode thick/thin contrast + serifs appear.
# Points are written as flat tuples: ((x,y),(x,y),...), class.

def G(adv, *strokes):
    return (adv, list(strokes))

GLYPHS = {}

# --- capitals ---
GLYPHS['A'] = G(10, (((1, 11), (5, 1), (9, 11)), 2), (((3, 7), (7, 7)), 3))
GLYPHS['B'] = G(10, (((1, 1), (1, 11)), 1), (((1, 1), (6, 1), (8, 3), (6, 6), (1, 6)), 2),
                (((1, 6), (6, 6), (8, 8), (6, 11), (1, 11)), 2))
GLYPHS['C'] = G(10, (((8, 2), (6, 1), (3, 1), (1, 3), (1, 9), (3, 11), (6, 11), (8, 10)), 2))
GLYPHS['D'] = G(10, (((1, 1), (1, 11)), 1), (((1, 1), (6, 1), (9, 4), (9, 8), (6, 11), (1, 11)), 2))
GLYPHS['E'] = G(9, (((1, 1), (1, 11)), 1), (((1, 1), (8, 1)), 3),
                (((1, 6), (6, 6)), 3), (((1, 11), (8, 11)), 3))
GLYPHS['F'] = G(9, (((1, 1), (1, 11)), 1), (((1, 1), (8, 1)), 3), (((1, 6), (6, 6)), 3))
GLYPHS['G'] = G(10, (((8, 2), (6, 1), (3, 1), (1, 3), (1, 9), (3, 11), (6, 11), (8, 11)), 2),
                (((8, 7), (6, 7), (6, 8)), 3), (((8, 7), (8, 9)), 2))
GLYPHS['H'] = G(10, (((1, 1), (1, 11)), 1), (((9, 1), (9, 11)), 1), (((1, 6), (9, 6)), 3))
GLYPHS['I'] = G(6, (((5, 1), (5, 11)), 1), (((2, 1), (8, 1)), 4), (((2, 11), (8, 11)), 4))
GLYPHS['J'] = G(9, (((8, 1), (8, 9), (6, 11), (3, 11), (2, 9)), 2), (((4, 1), (9, 1)), 3))
GLYPHS['K'] = G(10, (((1, 1), (1, 11)), 1), (((8, 1), (1, 6)), 2), (((4, 7), (8, 11)), 2))
GLYPHS['L'] = G(9, (((1, 1), (1, 11)), 1), (((1, 11), (8, 11)), 3))
GLYPHS['M'] = G(12, (((1, 1), (1, 11)), 1), (((1, 1), (6, 7)), 2),
                (((6, 7), (11, 1)), 2), (((11, 1), (11, 11)), 1))
GLYPHS['N'] = G(11, (((1, 1), (1, 11)), 1), (((1, 1), (10, 11)), 2), (((10, 1), (10, 11)), 1))
GLYPHS['O'] = G(11, (((3, 1), (7, 1), (9, 3), (9, 9), (7, 11), (3, 11), (1, 9), (1, 3), (3, 1)), 2))
GLYPHS['P'] = G(10, (((1, 1), (1, 11)), 1), (((1, 1), (6, 1), (8, 3), (6, 6), (1, 6)), 2))
GLYPHS['Q'] = G(11, (((3, 1), (7, 1), (9, 3), (9, 9), (7, 11), (3, 11), (1, 9), (1, 3), (3, 1)), 2),
                (((6, 8), (10, 12)), 2))
GLYPHS['R'] = G(10, (((1, 1), (1, 11)), 1), (((1, 1), (6, 1), (8, 3), (6, 6), (1, 6)), 2),
                (((5, 6), (9, 11)), 2))
GLYPHS['S'] = G(10, (((8, 2), (6, 1), (3, 1), (1, 3), (2, 5), (5, 6), (8, 7), (9, 9), (7, 11), (4, 11), (2, 10)), 2))
GLYPHS['T'] = G(10, (((1, 1), (9, 1)), 3), (((5, 1), (5, 11)), 1))
GLYPHS['U'] = G(10, (((1, 1), (1, 9), (3, 11), (7, 11), (9, 9), (9, 1)), 2))
GLYPHS['V'] = G(10, (((1, 1), (5, 11), (9, 1)), 2))
GLYPHS['W'] = G(13, (((1, 1), (3, 11), (6, 6), (9, 11), (12, 1)), 2))
GLYPHS['X'] = G(10, (((1, 1), (9, 11)), 2), (((9, 1), (1, 11)), 2))
GLYPHS['Y'] = G(10, (((1, 1), (5, 6), (9, 1)), 2), (((5, 6), (5, 11)), 1))
GLYPHS['Z'] = G(10, (((1, 1), (9, 1), (1, 11), (9, 11)), 2))

# --- lowercase ---
GLYPHS['a'] = G(9, (((8, 6), (8, 11)), 1), (((8, 6), (4, 6), (1, 8), (1, 10), (3, 11), (7, 11), (8, 10)), 2))
GLYPHS['b'] = G(9, (((1, 1), (1, 11)), 1), (((1, 7), (5, 6), (7, 8), (7, 10), (5, 11), (1, 11)), 2))
GLYPHS['c'] = G(9, (((7, 7), (5, 6), (2, 6), (1, 8), (1, 10), (2, 11), (5, 11), (7, 10)), 2))
GLYPHS['d'] = G(9, (((9, 1), (9, 11)), 1), (((9, 7), (5, 6), (2, 8), (2, 10), (5, 11), (9, 11)), 2))
GLYPHS['e'] = G(9, (((7, 10), (8, 8), (7, 6), (4, 6), (1, 8), (1, 10), (3, 11), (6, 11)), 2),
                (((1, 8), (8, 8)), 3))
GLYPHS['f'] = G(7, (((6, 1), (4, 1), (3, 3), (3, 11)), 2), (((2, 6), (7, 6)), 3))
GLYPHS['g'] = G(9, (((8, 6), (4, 6), (1, 8), (1, 10), (3, 11), (7, 11), (8, 10)), 2),
                (((8, 6), (8, 12), (6, 14), (3, 14), (2, 13)), 2))
GLYPHS['h'] = G(9, (((1, 1), (1, 11)), 1), (((1, 7), (1, 6), (4, 6), (6, 7), (6, 11)), 2))
GLYPHS['i'] = G(5, (((5, 6), (5, 11)), 1), (((5, 2), (5, 3)), 1))
GLYPHS['j'] = G(6, (((6, 6), (6, 12), (4, 14), (2, 14)), 2), (((6, 2), (6, 3)), 1))
GLYPHS['k'] = G(9, (((1, 1), (1, 11)), 1), (((7, 6), (1, 9)), 2), (((4, 10), (7, 11)), 2))
GLYPHS['l'] = G(5, (((5, 1), (5, 11)), 1))
GLYPHS['m'] = G(13, (((1, 6), (1, 11)), 1), (((1, 6), (3, 6), (5, 7), (5, 11)), 2),
                (((5, 6), (7, 6), (9, 7), (9, 11)), 2))
GLYPHS['n'] = G(9, (((1, 6), (1, 11)), 1), (((1, 6), (4, 6), (6, 7), (6, 11)), 2))
GLYPHS['o'] = G(9, (((3, 6), (6, 6), (8, 8), (8, 10), (6, 11), (3, 11), (1, 9), (1, 8), (3, 6)), 2))
GLYPHS['p'] = G(9, (((1, 6), (1, 14)), 1), (((1, 7), (5, 6), (7, 8), (7, 10), (5, 11), (1, 11)), 2))
GLYPHS['q'] = G(9, (((8, 7), (5, 6), (2, 8), (2, 10), (5, 11), (8, 11)), 2), (((8, 6), (8, 14)), 1))
GLYPHS['r'] = G(8, (((1, 6), (1, 11)), 1), (((1, 6), (4, 6), (6, 7), (6, 8)), 2))
GLYPHS['s'] = G(9, (((7, 7), (5, 6), (2, 6), (1, 8), (3, 9), (6, 9), (8, 10), (6, 11), (3, 11)), 2))
GLYPHS['t'] = G(7, (((5, 1), (5, 11)), 2), (((2, 6), (8, 6)), 3), (((5, 11), (7, 11)), 3))
GLYPHS['u'] = G(9, (((1, 6), (1, 10), (2, 11), (5, 11), (6, 10), (6, 6)), 2))
GLYPHS['v'] = G(9, (((1, 6), (4, 11), (7, 6)), 2))
GLYPHS['w'] = G(12, (((1, 6), (2, 11), (4, 7), (6, 11), (7, 6)), 2))
GLYPHS['x'] = G(9, (((1, 6), (7, 11)), 2), (((7, 6), (1, 11)), 2))
GLYPHS['y'] = G(9, (((1, 6), (4, 11), (7, 6)), 2), (((4, 11), (3, 13), (1, 14)), 2))
GLYPHS['z'] = G(9, (((1, 6), (7, 6), (1, 11), (7, 11)), 2))

# --- digits ---
GLYPHS['0'] = G(11, (((3, 1), (7, 1), (9, 3), (9, 9), (7, 11), (3, 11), (1, 9), (1, 3), (3, 1)), 2))
GLYPHS['1'] = G(8, (((6, 1), (6, 11)), 1), (((3, 3), (6, 1)), 2), (((3, 11), (8, 11)), 3))
GLYPHS['2'] = G(10, (((2, 2), (4, 1), (7, 1), (8, 3), (8, 5), (2, 11), (8, 11)), 2))
GLYPHS['3'] = G(10, (((2, 2), (4, 1), (7, 1), (8, 3), (6, 6), (8, 8), (7, 10), (5, 11), (2, 11)), 2))
GLYPHS['4'] = G(10, (((7, 1), (7, 11)), 1), (((1, 8), (7, 8)), 3), (((7, 1), (1, 8)), 2))
GLYPHS['5'] = G(10, (((8, 1), (2, 1), (2, 6), (6, 6), (8, 8), (7, 11), (4, 11), (2, 10)), 2))
GLYPHS['6'] = G(10, (((7, 2), (5, 1), (2, 3), (1, 6), (1, 9), (3, 11), (7, 11), (8, 9), (8, 7), (6, 6), (3, 6)), 2))
GLYPHS['7'] = G(10, (((1, 1), (9, 1), (4, 11)), 2))
GLYPHS['8'] = G(10, (((3, 1), (7, 1), (8, 3), (7, 5), (3, 5), (2, 3)), 2),
                (((3, 5), (7, 5), (8, 7), (7, 11), (3, 11), (2, 9), (2, 7)), 2))
GLYPHS['9'] = G(10, (((8, 1), (8, 11)), 1), (((8, 1), (5, 1), (2, 3), (2, 6), (5, 6), (8, 6)), 2))

# --- punctuation (ASCII only in the artwork) ---
GLYPHS['.'] = G(5, (((5, 10), (5, 11)), 1))
GLYPHS[','] = G(5, (((5, 10), (5, 11)), 1), (((5, 11), (3, 13)), 2))
GLYPHS[':'] = G(5, (((5, 4), (5, 5)), 1), (((5, 9), (5, 10)), 1))
GLYPHS[';'] = G(5, (((5, 4), (5, 5)), 1), (((5, 9), (5, 10)), 1), (((5, 10), (3, 13)), 2))
GLYPHS["'"] = G(4, (((5, 1), (4, 4)), 2))
GLYPHS['"'] = G(7, (((3, 1), (2, 4)), 2), (((7, 1), (6, 4)), 2))
GLYPHS['!'] = G(5, (((5, 1), (5, 9)), 1), (((5, 10), (5, 11)), 1))
GLYPHS['?'] = G(8, (((2, 3), (4, 1), (7, 1), (8, 3), (8, 5), (5, 7), (5, 9)), 2),
                (((5, 10), (5, 11)), 1))
GLYPHS['-'] = G(10, (((1, 8), (9, 8)), 3))
GLYPHS['\u2013'] = G(12, (((1, 8), (11, 8)), 3))
GLYPHS['\u2014'] = G(13, (((0, 8), (12, 8)), 3))
GLYPHS['('] = G(6, (((7, 1), (4, 3), (3, 6), (4, 9), (7, 11)), 2))
GLYPHS[')'] = G(6, (((1, 1), (4, 3), (5, 6), (4, 9), (1, 11)), 2))
GLYPHS['%'] = G(11, (((8, 1), (2, 11)), 2),
                (((2, 1), (4, 1), (4, 3), (2, 3), (2, 1)), 3),
                (((6, 8), (8, 8), (8, 10), (6, 10), (6, 8)), 3))
GLYPHS['$'] = G(10, (((5, 0), (5, 14)), 3),
                (((8, 3), (6, 1), (3, 1), (2, 3), (3, 5), (7, 6), (8, 8), (6, 11), (3, 11)), 2))
GLYPHS['&'] = G(10, (((7, 1), (5, 1), (3, 3), (3, 5), (6, 7), (8, 9), (7, 11), (4, 11), (2, 9)), 2),
                (((6, 7), (3, 10)), 2))
GLYPHS['/'] = G(8, (((8, 1), (2, 11)), 2))
GLYPHS['+'] = G(10, (((5, 3), (5, 9)), 2), (((2, 6), (8, 6)), 2))
GLYPHS['='] = G(10, (((2, 5), (8, 5)), 3), (((2, 9), (8, 9)), 3))
GLYPHS['\u00b7'] = G(5, (((5, 7), (5, 8)), 1))
GLYPHS['*'] = G(10, (((5, 2), (5, 10)), 2), (((2, 4), (8, 8)), 2), (((8, 4), (2, 8)), 2))
GLYPHS['#'] = G(11, (((4, 1), (3, 11)), 3), (((7, 1), (6, 11)), 3),
                (((1, 4), (9, 4)), 3), (((1, 8), (9, 8)), 3))
GLYPHS['@'] = G(11, (((8, 4), (6, 1), (3, 1), (1, 4), (1, 8), (3, 11), (7, 11), (8, 9),
                     (8, 6), (6, 5), (4, 6), (4, 9), (6, 10), (7, 8)), 2))
GLYPHS['_'] = G(10, (((0, 12), (10, 12)), 3))
GLYPHS[' '] = G(4, )

# ---------------------------------------------------------------- text engine
# size = cap height in final (1024) pixels. All coordinates below are in
# final pixels; the engine multiplies by SS internally.
# The glyph grid is 10 units wide per 10 units of cap height, which is
# wider than real type (avg lowercase ~0.5x cap height), so glyphs are
# narrowed horizontally by XNARROW and given TRACK_U units of tracking;
# without both, words run together at small sizes.

XNARROW = 0.72
TRACK_U = 0.6
BEARING_U = 1.3

# Per-glyph horizontal span over its drawn points. Advances are derived
# from the span, not from the stored width: several narrow glyphs (i, l,
# j, .) keep their stem near x=5 while their stored advance is 4-6, which
# left a 5-unit gap before them and an overlap after them ("m ine",
# "Nv idia"). Deriving advance from the span makes every gap uniform.
_GLYPH_SPAN = {}
for _ch, _g in GLYPHS.items():
    _xs = [p[0] for _pts, _cls in _g[1] for p in _pts]
    _GLYPH_SPAN[_ch] = (min(_xs), max(_xs)) if _xs else None


def _glyph_adv_units(ch):
    g = GLYPHS.get(ch)
    if g is None:
        return 4 * XNARROW + TRACK_U
    sp = _GLYPH_SPAN.get(ch)
    if sp is None:
        return g[0] * XNARROW + TRACK_U
    return (sp[1] - sp[0] + 2 * BEARING_U) * XNARROW + TRACK_U


def _u(size):
    return size * SS / 10.0


def char_adv(ch, size):
    """Advance of one glyph, in FINAL pixels (size = cap height, final px)."""
    return _glyph_adv_units(ch) * size / 10.0


def measure(s, size):
    return sum(char_adv(ch, size) for ch in s)


def wrap_text(s, size, maxw):
    words = s.split(" ")
    lines = []
    cur = ""
    for w in words:
        trial = (cur + " " + w).strip()
        if measure(trial, size) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_char(cv, ch, x, ytop, size, color, serif, italic):
    """Draw one glyph. (x, ytop) = top-left of the cap-height box, final px."""
    g = GLYPHS.get(ch)
    if g is None:
        return char_adv(ch, size)
    adv, strokes = g
    u = _u(size)
    x0 = x * SS
    y0 = ytop * SS
    base_y = y0 + 11 * u          # baseline in supersampled px
    sp = _GLYPH_SPAN.get(ch)
    dx = (BEARING_U - sp[0]) if sp is not None else 0.0
    for pts, cls in strokes:
        if cls == 4 and not serif:
            continue
        if serif:
            wdt = {1: 0.15, 2: 0.10, 3: 0.065, 4: 0.09}[cls] * size * SS
        else:
            wdt = 0.10 * size * SS
        sp2 = []
        for (gx, gy) in pts:
            px = x0 + (gx + dx) * u * XNARROW
            py = y0 + gy * u
            if italic:
                px += 0.16 * (base_y - py)
            sp2.append((px, py))
        for i in range(len(sp2) - 1):
            cv.thick_line(sp2[i][0], sp2[i][1], sp2[i + 1][0], sp2[i + 1][1], wdt, color)
        # automatic foot serifs on thick vertical stems (serif mode only)
        if serif and cls == 1 and len(pts) == 2 and pts[0][0] == pts[1][0]:
            for (gx, gy) in pts:
                if gy in (1, 11):
                    cx = x0 + (gx + dx) * u * XNARROW + (0.16 * (base_y - (y0 + gy * u)) if italic else 0)
                    cy = y0 + gy * u
                    cv.thick_line(cx - 1.15 * u * XNARROW, cy,
                                  cx + 1.15 * u * XNARROW, cy,
                                  0.09 * size * SS, color)
    return _glyph_adv_units(ch) * size / 10.0


def draw_text(cv, s, x, y, size, color, serif=False, italic=False, align="left"):
    """Draw text; y is the TOP of the cap height (final px). Returns width."""
    total = measure(s, size)
    if align == "center":
        x -= total / 2.0
    elif align == "right":
        x -= total
    cx = x
    for ch in s:
        cx += draw_char(cv, ch, cx, y, size, color, serif, italic)
    return total


def draw_text_block(cv, lines, x, y, size, color, serif=False, leading=None,
                    align="left", maxw=None):
    """Draw several lines; y is the top of the first line's cap height."""
    if leading is None:
        leading = size * 1.32
    for ln in lines:
        draw_text(cv, ln, x, y, size, color, serif=serif, align=align)
        y += leading
    return y

# ---------------------------------------------------------------- scene helpers
# Scene functions draw into a rect (x, y, w, h) in final pixels.

def _dark(c, d):
    return tuple(max(0, v - d) for v in c)


def scene_frame(cv, x, y, w, h, sky, ground=None, gh=0.28):
    cv.vgrad(x * SS, y * SS, (x + w) * SS, (y + h) * SS, sky, _dark(sky, 26))
    if ground is not None:
        cv.vgrad(x * SS, (y + h * (1 - gh)) * SS, (x + w) * SS, (y + h) * SS,
                 ground, _dark(ground, 22))


def banner(cv, x, y, w, text, size, bg, fg=WHITE):
    cv.rect(x * SS, y * SS, (x + w) * SS, (y + size + 7) * SS, bg)
    draw_text(cv, text, x + w / 2, y + 2, size, fg, serif=False, align="center")
    return size + 7


def tag(cv, x, y, text, size, bg, fg=WHITE):
    tw = measure(text, size) + 8
    cv.rect(x * SS, y * SS, (x + tw) * SS, (y + size + 5) * SS, bg)
    draw_text(cv, text, x + 4, y + 1.5, size, fg, serif=False)
    return tw



# ---------------------------------------------------------------- illustration scenes
# Local helpers work in final pixels (they multiply by SS).

def _r(cv, x, y, w, h, c):
    cv.rect(x * SS, y * SS, (x + w) * SS, (y + h) * SS, c)


def _l(cv, x0, y0, x1, y1, w, c):
    cv.thick_line(x0 * SS, y0 * SS, x1 * SS, y1 * SS, w * SS, c)


def _d(cv, cx, cy, r, c):
    cv.disc(cx * SS, cy * SS, r * SS, c)


def _p(cv, pts, c):
    cv.poly([(px * SS, py * SS) for px, py in pts], c)


def _burst(cv, cx, cy, r, c1, c2):
    _d(cv, cx, cy, r, c2)
    for a in range(0, 360, 45):
        ang = math.radians(a)
        _l(cv, cx, cy, cx + math.cos(ang) * r * 1.5, cy + math.sin(ang) * r * 1.5,
           2.2, c1)


def sc_huawei(cv, x, y, w, h):
    scene_frame(cv, x, y, w, h, (198, 206, 220), (150, 158, 172), 0.16)
    _p(cv, [(x + w * 0.18, y + h * 0.30), (x + w * 0.5, y + h * 0.10),
            (x + w * 0.82, y + h * 0.30)], PAPER2)
    _r(cv, x + w * 0.20, y + h * 0.30, w * 0.60, h * 0.56, (232, 226, 208))
    for i in range(5):
        cx = x + w * (0.25 + i * 0.125)
        _r(cv, cx, y + h * 0.34, 5, h * 0.46, WHITE)
        _r(cv, cx - 3, y + h * 0.30, 11, 4, WHITE)
    _r(cv, x + w * 0.18, y + h * 0.80, w * 0.64, 5, (120, 116, 104))
    _r(cv, x + w * 0.15, y + h * 0.86, w * 0.70, 4, (120, 116, 104))
    _l(cv, x + w * 0.5, y + h * 0.42, x + w * 0.5, y + h * 0.62, 3, INK)
    _l(cv, x + w * 0.38, y + h * 0.44, x + w * 0.62, y + h * 0.44, 2.5, INK)
    _l(cv, x + w * 0.38, y + h * 0.44, x + w * 0.38, y + h * 0.52, 2, INK)
    _l(cv, x + w * 0.62, y + h * 0.44, x + w * 0.62, y + h * 0.52, 2, INK)
    _p(cv, [(x + w * 0.33, y + h * 0.52), (x + w * 0.43, y + h * 0.52),
            (x + w * 0.38, y + h * 0.58)], GOLD)
    _p(cv, [(x + w * 0.57, y + h * 0.52), (x + w * 0.67, y + h * 0.52),
            (x + w * 0.62, y + h * 0.58)], GOLD)
    _d(cv, x + w * 0.5, y + h * 0.40, 3.5, GOLD)


def sc_hormuz(cv, x, y, w, h):
    scene_frame(cv, x, y, w, h, (214, 226, 238), SEA, 0.55)
    _d(cv, x + w * 0.82, y + h * 0.16, 9, (240, 200, 90))
    _r(cv, x + w * 0.08, y + h * 0.52, w * 0.52, h * 0.16, (30, 34, 44))
    _r(cv, x + w * 0.10, y + h * 0.40, w * 0.20, h * 0.12, (52, 60, 74))
    _r(cv, x + w * 0.32, y + h * 0.44, w * 0.10, h * 0.08, RED2)
    _r(cv, x + w * 0.44, y + h * 0.44, w * 0.10, h * 0.08, GOLD2)
    _r(cv, x + w * 0.56, y + h * 0.44, w * 0.06, h * 0.08, WHITE)
    for i in range(4):
        _l(cv, x + w * (0.10 + i * 0.20), y + h * 0.72,
           x + w * (0.16 + i * 0.20), y + h * 0.72, 2, (140, 170, 200))
    _d(cv, x + w * 0.74, y + h * 0.62, 7, INK)
    for a in range(0, 360, 30):
        ang = math.radians(a)
        _l(cv, x + w * 0.74, y + h * 0.62,
           x + w * 0.74 + math.cos(ang) * 13, y + h * 0.62 + math.sin(ang) * 13,
           2, INK)
    _burst(cv, x + w * 0.74, y + h * 0.42, 8, (230, 120, 40), (250, 170, 60))
    _l(cv, x + w * 0.68, y + h * 0.30, x + w * 0.80, y + h * 0.30, 1.5, WHITE)


def sc_ships(cv, x, y, w, h):
    scene_frame(cv, x, y, w, h, (28, 38, 62), (20, 42, 70), 0.58)
    _d(cv, x + w * 0.85, y + h * 0.14, 8, (228, 220, 190))
    _r(cv, x + w * 0.30, y + h * 0.50, w * 0.44, h * 0.14, (44, 50, 64))
    _r(cv, x + w * 0.34, y + h * 0.38, w * 0.12, h * 0.12, (70, 78, 94))
    _r(cv, x + w * 0.48, y + h * 0.42, w * 0.12, h * 0.08, (178, 120, 60))
    _r(cv, x + w * 0.62, y + h * 0.42, w * 0.10, h * 0.08, (90, 130, 90))
    _p(cv, [(x + w * 0.10, y + h * 0.60), (x + w * 0.16, y + h * 0.56),
            (x + w * 0.22, y + h * 0.60)], (120, 126, 138))
    _l(cv, x + w * 0.16, y + h * 0.56, x + w * 0.16, y + h * 0.50, 2, (120, 126, 138))
    for i in range(3):
        _l(cv, x + w * (0.08 + i * 0.26), y + h * 0.74,
           x + w * (0.16 + i * 0.26), y + h * 0.74, 2, (90, 130, 170))
    _burst(cv, x + w * 0.76, y + h * 0.46, 7, (230, 120, 40), (250, 170, 60))
    _l(cv, x + w * 0.22, y + h * 0.56, x + w * 0.30, y + h * 0.52, 1.5, (200, 200, 200))


def sc_senegal(cv, x, y, w, h):
    scene_frame(cv, x, y, w, h, (120, 170, 110), (52, 130, 70), 0.62)
    _l(cv, x + w * 0.08, y + h * 0.55, x + w * 0.92, y + h * 0.55, 2, WHITE)
    _d(cv, x + w * 0.5, y + h * 0.55, 8, (52, 130, 70))
    _r(cv, x + w * 0.06, y + h * 0.06, w * 0.07, h * 0.34, GREEN)
    _r(cv, x + w * 0.13, y + h * 0.06, w * 0.07, h * 0.34, GOLD2)
    _r(cv, x + w * 0.20, y + h * 0.06, w * 0.07, h * 0.34, RED2)
    _l(cv, x + w * 0.09, y + h * 0.06, x + w * 0.09, y + h * 0.44, 2, INK)
    _p(cv, [(x + w * 0.42, y + h * 0.14), (x + w * 0.58, y + h * 0.14),
            (x + w * 0.55, y + h * 0.34), (x + w * 0.45, y + h * 0.34)], GOLD)
    _r(cv, x + w * 0.48, y + h * 0.34, 5, h * 0.14, GOLD)
    _r(cv, x + w * 0.42, y + h * 0.48, w * 0.16, 5, GOLD)
    _l(cv, x + w * 0.40, y + h * 0.16, x + w * 0.34, y + h * 0.24, 2, GOLD)
    _l(cv, x + w * 0.60, y + h * 0.16, x + w * 0.66, y + h * 0.24, 2, GOLD)
    _d(cv, x + w * 0.82, y + h * 0.72, 6, WHITE)
    _l(cv, x + w * 0.78, y + h * 0.68, x + w * 0.86, y + h * 0.76, 1.5, INK)


def sc_markets(cv, x, y, w, h):
    scene_frame(cv, x, y, w, h, WHITE, None)
    for i in range(1, 4):
        _l(cv, x, y + h * i / 4, x + w, y + h * i / 4, 1, (228, 228, 226))
    for i in range(1, 6):
        _l(cv, x + w * i / 6, y, x + w * i / 6, y + h, 1, (228, 228, 226))
    _l(cv, x + w * 0.06, y + h * 0.78, x + w * 0.30, y + h * 0.60, 3, BLUE)
    _l(cv, x + w * 0.30, y + h * 0.60, x + w * 0.55, y + h * 0.66, 3, BLUE)
    _l(cv, x + w * 0.55, y + h * 0.66, x + w * 0.80, y + h * 0.30, 3, BLUE)
    _p(cv, [(x + w * 0.80, y + h * 0.30), (x + w * 0.72, y + h * 0.30),
            (x + w * 0.80, y + h * 0.22)], BLUE)
    _l(cv, x + w * 0.06, y + h * 0.30, x + w * 0.30, y + h * 0.42, 2.5, RED2)
    _l(cv, x + w * 0.30, y + h * 0.42, x + w * 0.55, y + h * 0.38, 2.5, RED2)
    _l(cv, x + w * 0.55, y + h * 0.38, x + w * 0.80, y + h * 0.62, 2.5, RED2)
    _r(cv, x + w * 0.88, y + h * 0.20, 4, h * 0.22, GREEN)
    _r(cv, x + w * 0.92, y + h * 0.34, 4, h * 0.18, RED2)


def sc_pif(cv, x, y, w, h):
    scene_frame(cv, x, y, w, h, (18, 26, 48), (26, 30, 40), 0.18)
    for (sx, sy) in [(0.12, 0.14), (0.30, 0.08), (0.55, 0.18), (0.78, 0.10), (0.90, 0.24)]:
        _d(cv, x + w * sx, y + h * sy, 1.6, WHITE)
    _r(cv, x + w * 0.38, y + h * 0.14, w * 0.24, h * 0.72, (52, 58, 74))
    _r(cv, x + w * 0.44, y + h * 0.06, w * 0.12, h * 0.08, (52, 58, 74))
    for r in range(6):
        for c in range(3):
            _r(cv, x + w * (0.41 + c * 0.07), y + h * (0.22 + r * 0.10), 5, 4, GOLD2)
    _r(cv, x + w * 0.10, y + h * 0.44, w * 0.16, h * 0.42, (40, 44, 58))
    _r(cv, x + w * 0.74, y + h * 0.52, w * 0.16, h * 0.34, (40, 44, 58))
    _d(cv, x + w * 0.50, y + h * 0.20, 9, (200, 90, 60))
    _d(cv, x + w * 0.50, y + h * 0.20, 5, (240, 160, 60))
    _d(cv, x + w * 0.56, y + h * 0.14, 5, (150, 150, 150))
    _d(cv, x + w * 0.60, y + h * 0.10, 7, (170, 170, 170))
    _r(cv, x + w * 0.70, y + h * 0.30, 12, 3, (140, 140, 150))
    _d(cv, x + w * 0.70, y + h * 0.30, 2.5, (140, 140, 150))
    _d(cv, x + w * 0.82, y + h * 0.30, 2.5, (140, 140, 150))


def sc_aden(cv, x, y, w, h):
    scene_frame(cv, x, y, w, h, (238, 214, 160), SAND, 0.45)
    _d(cv, x + w * 0.82, y + h * 0.16, 9, (240, 190, 90))
    _p(cv, [(x + w * 0.05, y + h * 0.55), (x + w * 0.22, y + h * 0.24),
            (x + w * 0.38, y + h * 0.55)], (150, 120, 90))
    _p(cv, [(x + w * 0.30, y + h * 0.55), (x + w * 0.48, y + h * 0.32),
            (x + w * 0.64, y + h * 0.55)], (170, 138, 104))
    for i in range(4):
        _r(cv, x + w * (0.66 + i * 0.07), y + h * (0.60 - (i % 2) * 0.06),
           w * 0.05, h * 0.26, (210, 196, 170))
    _r(cv, x + w * 0.66, y + h * 0.44, w * 0.28, 3, RED2)
    _l(cv, x + w * 0.20, y + h * 0.62, x + w * 0.62, y + h * 0.50, 3, RED)
    _p(cv, [(x + w * 0.62, y + h * 0.50), (x + w * 0.55, y + h * 0.46),
            (x + w * 0.55, y + h * 0.54)], RED)
    _r(cv, x + w * 0.08, y + h * 0.60, w * 0.06, h * 0.10, RED2)
    _r(cv, x + w * 0.08, y + h * 0.70, w * 0.06, h * 0.10, WHITE)
    _r(cv, x + w * 0.08, y + h * 0.80, w * 0.06, h * 0.10, INK)


def sc_cartagena(cv, x, y, w, h):
    scene_frame(cv, x, y, w, h, (240, 226, 180), (170, 160, 140), 0.22)
    _r(cv, x + w * 0.10, y + h * 0.22, w * 0.80, h * 0.58, (232, 178, 40))
    _r(cv, x + w * 0.10, y + h * 0.22, w * 0.80, h * 0.16, (30, 34, 44))
    draw_text(cv, "EXITO", x + w * 0.5, y + h * 0.235, 11, WHITE, serif=False,
              align="center")
    _r(cv, x + w * 0.16, y + h * 0.46, w * 0.20, h * 0.34, (120, 180, 210))
    _r(cv, x + w * 0.44, y + h * 0.46, w * 0.20, h * 0.34, (120, 180, 210))
    _l(cv, x + w * 0.40, y + h * 0.46, x + w * 0.40, y + h * 0.80, 3, (30, 34, 44))
    _r(cv, x + w * 0.70, y + h * 0.46, w * 0.14, h * 0.34, (60, 64, 74))
    for i in range(6):
        _l(cv, x + w * (0.08 + i * 0.15), y + h * 0.88,
           x + w * (0.13 + i * 0.15), y + h * 0.80, 2.5, GOLD2)
    _r(cv, x + w * 0.08, y + h * 0.80, w * 0.84, 4, (240, 200, 60))
    _r(cv, x + w * 0.74, y + h * 0.62, 8, h * 0.18, (40, 90, 160))
    _d(cv, x + w * 0.76, y + h * 0.80, 3.5, INK)
    _d(cv, x + w * 0.84, y + h * 0.80, 3.5, INK)


def sc_haftar(cv, x, y, w, h):
    scene_frame(cv, x, y, w, h, (210, 224, 238), (200, 196, 180), 0.20)
    _l(cv, x + w * 0.20, y + h * 0.16, x + w * 0.20, y + h * 0.82, 2.5, INK)
    _r(cv, x + w * 0.20, y + h * 0.18, w * 0.30, h * 0.10, RED2)
    _r(cv, x + w * 0.20, y + h * 0.28, w * 0.30, h * 0.10, INK)
    _r(cv, x + w * 0.20, y + h * 0.38, w * 0.30, h * 0.10, GREEN)
    _d(cv, x + w * 0.35, y + h * 0.33, 4, WHITE)
    _l(cv, x + w * 0.72, y + h * 0.16, x + w * 0.72, y + h * 0.82, 2.5, INK)
    _r(cv, x + w * 0.72, y + h * 0.18, w * 0.24, h * 0.30, RED2)
    _d(cv, x + w * 0.80, y + h * 0.33, 5, WHITE)
    _d(cv, x + w * 0.82, y + h * 0.33, 4, RED2)
    _d(cv, x + w * 0.85, y + h * 0.31, 1.8, WHITE)
    _r(cv, x + w * 0.30, y + h * 0.62, w * 0.40, h * 0.20, (140, 110, 80))
    _d(cv, x + w * 0.42, y + h * 0.62, 5, (222, 190, 160))
    _d(cv, x + w * 0.58, y + h * 0.62, 5, (200, 170, 140))
    _l(cv, x + w * 0.42, y + h * 0.62, x + w * 0.58, y + h * 0.62, 3,
       (222, 190, 160))


def sc_gaza(cv, x, y, w, h):
    scene_frame(cv, x, y, w, h, (226, 216, 190), (200, 186, 160), 0.30)
    _p(cv, [(x + w * 0.10, y + h * 0.10), (x + w * 0.34, y + h * 0.08),
            (x + w * 0.44, y + h * 0.30), (x + w * 0.30, y + h * 0.55),
            (x + w * 0.12, y + h * 0.42)], (240, 232, 210))
    for (bx, by, bw, bh) in [(0.16, 0.16, 0.10, 0.12), (0.30, 0.20, 0.08, 0.10),
                             (0.20, 0.36, 0.12, 0.12), (0.60, 0.14, 0.10, 0.12),
                             (0.72, 0.34, 0.12, 0.14), (0.58, 0.58, 0.12, 0.12)]:
        _r(cv, x + w * bx, y + h * by, w * bw, h * bh, (150, 142, 126))
    _d(cv, x + w * 0.26, y + h * 0.30, 9, (200, 60, 50))
    _d(cv, x + w * 0.26, y + h * 0.30, 5, WHITE)
    _d(cv, x + w * 0.26, y + h * 0.30, 2.5, RED2)
    _d(cv, x + w * 0.68, y + h * 0.48, 6, (150, 150, 150))
    _d(cv, x + w * 0.74, y + h * 0.40, 8, (170, 170, 170))
    _burst(cv, x + w * 0.80, y + h * 0.62, 6, (230, 120, 40), (250, 170, 60))


def sc_chess(cv, x, y, w, h):
    scene_frame(cv, x, y, w, h, (40, 48, 66), (60, 54, 44), 0.14)
    bs = min(w, h) * 0.62
    bx = x + w * 0.06
    by = y + h * 0.10
    sq = bs / 8
    for r in range(8):
        for c in range(8):
            col = (238, 228, 200) if (r + c) % 2 == 0 else (120, 96, 66)
            _r(cv, bx + c * sq, by + r * sq, sq + 0.6, sq + 0.6, col)
    _d(cv, bx + 3.5 * sq, by + 7.5 * sq, sq * 0.34, WHITE)
    _r(cv, bx + 3.2 * sq, by + 6.6 * sq, sq * 0.6, 2, WHITE)
    _d(cv, bx + 4.5 * sq, by + 0.5 * sq, sq * 0.34, INK)
    _p(cv, [(bx + 4.2 * sq, by + 0.2 * sq), (bx + 4.5 * sq, by - 0.15 * sq),
            (bx + 4.8 * sq, by + 0.2 * sq)], INK)
    _r(cv, x + w * 0.68, y + h * 0.14, w * 0.26, h * 0.30, (30, 34, 44))
    _d(cv, x + w * 0.75, y + h * 0.24, 5, WHITE)
    _d(cv, x + w * 0.87, y + h * 0.24, 5, WHITE)
    draw_text(cv, "0.5-0.5", x + w * 0.81, y + h * 0.36, 8, WHITE, serif=False,
              align="center")


def sc_korea(cv, x, y, w, h):
    scene_frame(cv, x, y, w, h, (168, 200, 228), SEA, 0.42)
    _d(cv, x + w * 0.84, y + h * 0.14, 8, (244, 214, 110))
    _p(cv, [(x + w * 0.30, y + h * 0.62), (x + w * 0.44, y + h * 0.44),
            (x + w * 0.58, y + h * 0.62)], (70, 140, 80))
    _p(cv, [(x + w * 0.52, y + h * 0.62), (x + w * 0.68, y + h * 0.50),
            (x + w * 0.82, y + h * 0.62)], (90, 160, 96))
    _p(cv, [(x + w * 0.12, y + h * 0.30), (x + w * 0.30, y + h * 0.26),
            (x + w * 0.26, y + h * 0.34), (x + w * 0.14, y + h * 0.36)], (110, 116, 128))
    _p(cv, [(x + w * 0.58, y + h * 0.22), (x + w * 0.76, y + h * 0.18),
            (x + w * 0.72, y + h * 0.26), (x + w * 0.60, y + h * 0.28)], (110, 116, 128))
    _l(cv, x + w * 0.46, y + h * 0.60, x + w * 0.46, y + h * 0.50, 2, INK)
    _d(cv, x + w * 0.46, y + h * 0.48, 3, RED2)
    for i in range(3):
        _l(cv, x + w * (0.06 + i * 0.24), y + h * 0.72,
           x + w * (0.14 + i * 0.24), y + h * 0.72, 2, (140, 170, 200))



def sc_nato(cv, x, y, w, h):
    scene_frame(cv, x, y, w, h, (12, 18, 38), None)
    for (sx, sy, sr) in [(0.12, 0.16, 1.6), (0.30, 0.08, 1.4), (0.55, 0.12, 1.6),
                         (0.78, 0.10, 1.4), (0.90, 0.26, 1.6), (0.20, 0.30, 1.2),
                         (0.66, 0.34, 1.2)]:
        _d(cv, x + w * sx, y + h * sy, sr, WHITE)
    _p(cv, [(x + w * 0.42, y + h * 0.34), (x + w * 0.58, y + h * 0.34),
            (x + w * 0.54, y + h * 0.52), (x + w * 0.46, y + h * 0.52)], (200, 204, 212))
    _r(cv, x + w * 0.30, y + h * 0.40, w * 0.12, h * 0.10, BLUE)
    _r(cv, x + w * 0.58, y + h * 0.40, w * 0.12, h * 0.10, BLUE)
    _l(cv, x + w * 0.42, y + h * 0.40, x + w * 0.58, y + h * 0.50, 2, (200, 204, 212))
    _p(cv, [(x, y + h * 0.86), (x + w * 0.5, y + h * 0.72), (x + w, y + h * 0.86),
            (x + w, y + h), (x, y + h)], (52, 110, 170))
    _p(cv, [(x + w * 0.10, y + h * 0.84), (x + w * 0.30, y + h * 0.76),
            (x + w * 0.42, y + h * 0.82)], (70, 140, 90))


# ---------------------------------------------------------------- the day's news
# Research: ~/workspace/makefun-news24/research-nov24.md (36 stories).
# Tags: CONFIRMED 2+ outlets, OFFICIAL the body itself, REPORTED one outlet,
# CLAIM one side's account.

TAG_COLORS = {"CONFIRMED": GREEN, "OFFICIAL": BLUE, "REPORTED": ORANGE,
              "CLAIM": RED}

LEADS = [
    {"scene": sc_huawei, "banner": "10 OF 12 COUNTS", "place": "BROOKLYN - COURTS",
     "tag": "CONFIRMED",
     "head": "Huawei guilty on 10 of 12 counts in US trial",
     "deck": "Brooklyn jury convicts Huawei of bank fraud, wire fraud, sanctions "
             "and trade-secret theft; acquitted of racketeering.",
     "source": "Reuters - CNN - WSJ - US DOJ"},
    {"scene": sc_hormuz, "banner": "4 TANKERS CLAIMED", "place": "STRAIT OF HORMUZ - CONFLICT",
     "tag": "CLAIM",
     "head": "Iran says a fourth tanker hit a mine",
     "deck": "IRGC also claims a container-ship strike; US Central Command "
             "rejects the mine claims; no ships named, nothing verified.",
     "source": "IRNA - IRGC - JMIC - CENTCOM"},
    {"scene": sc_ships, "banner": "2 SHIPS HIT", "place": "GULF OF FINLAND - CONFLICT",
     "tag": "CONFIRMED",
     "head": "Ukraine hits Russian ships in Gulf and Libya",
     "deck": "Zelensky confirms the Sparta II hit; Kyiv calls the Libya strikes "
             "self-defence; Poland cites a new airspace violation.",
     "source": "Reuters"},
]

CARDS = [
    {"scene": sc_senegal, "banner": "1-0 - TITLE BACK", "place": "RABAT - SPORT",
     "tag": "CONFIRMED",
     "head": "Senegal win back AFCON title",
     "deck": "CAS overturns CAF and restores the 1-0 extra-time win over Morocco in January.",
     "source": "AP - CAS"},
    {"scene": sc_markets, "banner": "50,018.70", "place": "WALL STREET - MARKETS",
     "tag": "CONFIRMED",
     "head": "Dow tops 50,000 as Nvidia slides",
     "deck": "Dow +0.85% to 50,018.70; Nasdaq -1.48%; Nvidia -5.86%; Sanofi buys Insmed, $41bn.",
     "source": "Investopedia"},
    {"scene": sc_pif, "banner": "11 WOUNDED", "place": "RIYADH - CONFLICT",
     "tag": "CONFIRMED",
     "head": "Drone hits PIF tower; 11 wounded",
     "deck": "Saudi Arabia blames a Houthi attack on the PIF tower; the second hit in under a week.",
     "source": "AP - Saudi authorities"},
    {"scene": sc_aden, "banner": "60 KM FROM ADEN", "place": "ADEN - CONFLICT",
     "tag": "CONFIRMED",
     "head": "Houthis near Aden, ready to attack",
     "deck": "Yemen's army says fighters near the capital; UK sanctions Houthis and four officials.",
     "source": "Yemen military - UK govt"},
    {"scene": sc_cartagena, "banner": "30 HELD", "place": "CARTAGENA - CRIME",
     "tag": "CONFIRMED",
     "head": "Gunmen hold 30 hostages in Cartagena",
     "deck": "Botched armoured-truck robbery ends in a standoff; 15 freed by nightfall, talks go on.",
     "source": "AP - CNN - CBS"},
    {"scene": sc_haftar, "banner": "FIRST VISIT", "place": "ANKARA - DIPLOMACY",
     "tag": "CONFIRMED",
     "head": "Haftar visits Turkey for first time",
     "deck": "Haftar meets Erdogan in Ankara; eastern parliament backed a maritime deal last month.",
     "source": "Reuters - AP"},
    {"scene": sc_gaza, "banner": "SECURITY CHIEF KILLED", "place": "GAZA - CONFLICT",
     "tag": "REPORTED",
     "head": "Israel kills Hamas security chief",
     "deck": "Nahel dies in a joint IDF-Shin Bet strike; six others killed in Tuesday strikes.",
     "source": "Gaza officials - IDF"},
    {"scene": sc_chess, "banner": "DRAW - 38 MOVES", "place": "GENEVA - SPORT",
     "tag": "CONFIRMED",
     "head": "Gukesh holds Sindarov in Game 1",
     "deck": "The opener ends 1/2-1/2 after 38 moves; at 20 each, the youngest title match ever.",
     "source": "Chess.com - ChessBase"},
    {"scene": sc_korea, "banner": "JETS SCRAMBLED", "place": "ULLEUNGDO - DEFENCE",
     "tag": "OFFICIAL",
     "head": "Korea scrambles jets at Russian planes",
     "deck": "Ulleungdo told to shelter as Russian jets enter the zone; airspace not violated.",
     "source": "South Korea military"},
    {"scene": sc_nato, "banner": "SPACE DEFENCE", "place": "BRUSSELS - DEFENCE",
     "tag": "OFFICIAL",
     "head": "NATO vows to defend space",
     "deck": "Rutte vows space defence after reports of a Russian nuclear-armed satellite.",
     "source": "NATO"},
]

BRIEFS = [
    (14, "Turkish helicopter crash kills 5", "Turkish MoD"),
    (15, "Iraq takes Kurdish oilfields", "Reuters"),
    (16, "Putin vows retaliation", "Reuters"),
    (17, "Ukraine needs $125bn in 2027", "Reuters"),
    (18, "Lukashenko offers Moscow flight", "Belta"),
    (19, "UK warns Ukraine suppliers", "Reuters"),
    (20, "Norway-Ukraine expand DESNA", "Norway MoD"),
    (21, "Germany first to get Delta", "Kyiv Ind."),
    (22, "Fighting traps Ebola teams", "WHO"),
    (23, "UN urges Benghazi probe", "UN"),
    (24, "Gaza meningitis alert: 272", "Gaza MoH"),
    (25, "Saudi strikes kill 25 in Yemen", "Saba"),
    (26, "DRC plane missing; rebels claim", "BBC"),
    (27, "Hanoi restaurant blast kills 6", "AP"),
    (28, "Malaysia to return migrants", "Reuters"),
    (29, "Hasina plans return on 16 Dec", "AP"),
    (30, "Indonesia names 2 for VP", "AP"),
    (31, "China sentences spy to death", "Gold Wall"),
    (32, "US blacklists Megaspeed", "US BIS"),
    (33, "US drone helped catch Isidro", "Mexico AG"),
    (34, "Pentagon rebukes Canada", "US DoD"),
    (35, "Real Madrid rout PSV 5-1", "UEFA"),
    (36, "Russian strike kills 2 in Odesa", "Reuters"),
]

NUMBERS = [
    ("10 of 12", "HUAWEI COUNTS GUILTY"),
    ("4", "TANKERS IRAN SAYS HIT"),
    ("50,018.70", "DOW FIRST OVER 50,000"),
    ("$41bn", "SANOFI BUYS INSMED"),
    ("$125bn", "UKRAINE NEEDS IN 2027"),
    ("30", "HOSTAGES IN CARTAGENA"),
]

TIMELINE = [
    ("00:30", "Zelensky talks"),
    ("02:15", "Space vow"),
    ("04:14", "Ulleungdo alert"),
    ("08:14", "Ship strikes"),
    ("11:40", "Gaza chief hit"),
    ("14:27", "PIF tower hit"),
    ("20:41", "Huawei verdict"),
]

REGIONS = [
    ("EUROPE", 11), ("MIDDLE EAST", 8), ("AFRICA", 5), ("EAST ASIA", 3),
    ("SOUTH & SE ASIA", 4), ("NORTH AMERICA", 4), ("SOUTH AMERICA", 1),
]

EXCLUDED = ("COP31 collapse (Sun 22 Nov) - Huang reinstated (Mon 23 Nov) - "
            "Merkury sunk (Sun 23 Nov) - Belgium strike (Mon 23 Nov) - "
            "Villavicencio bomb (Mon 23 Nov) - Grok suits (Mon 23 Nov) - "
            "EU 22nd sanctions (Mon 23 Nov) - ICJ Myanmar ruling (Thu 19 Nov) - "
            "CAF strips Senegal (Mar 2026) - El Chapo captured (21-22 Nov)")

# Map pins: (story number, x fraction, y fraction) in the map box.
PINS = [
    (1, 0.24, 0.30), (2, 0.60, 0.44), (3, 0.50, 0.40), (4, 0.44, 0.50),
    (5, 0.27, 0.36), (6, 0.58, 0.46), (7, 0.61, 0.52), (8, 0.27, 0.56),
    (9, 0.55, 0.34), (10, 0.56, 0.40), (11, 0.485, 0.28), (12, 0.83, 0.32),
    (13, 0.47, 0.25),
]

CONTINENTS = [
    [(0.03, 0.14), (0.20, 0.08), (0.37, 0.12), (0.40, 0.24), (0.32, 0.37),
     (0.27, 0.32), (0.20, 0.42), (0.13, 0.47), (0.08, 0.37), (0.03, 0.27)],
    [(0.25, 0.50), (0.32, 0.48), (0.35, 0.57), (0.32, 0.77), (0.27, 0.83),
     (0.24, 0.67)],
    [(0.47, 0.10), (0.55, 0.07), (0.58, 0.17), (0.53, 0.23), (0.48, 0.20)],
    [(0.48, 0.37), (0.58, 0.33), (0.62, 0.43), (0.58, 0.63), (0.52, 0.70),
     (0.48, 0.57), (0.47, 0.43)],
    [(0.58, 0.08), (0.83, 0.05), (0.96, 0.13), (0.95, 0.33), (0.83, 0.47),
     (0.73, 0.40), (0.67, 0.30), (0.60, 0.20)],
    [(0.82, 0.63), (0.92, 0.61), (0.95, 0.70), (0.87, 0.77), (0.82, 0.72)],
]



def draw_map(cv, x, y, w, h):
    cv.vgrad(x * SS, y * SS, (x + w) * SS, (y + h) * SS, MAPSEA,
             _dark(MAPSEA, 14))
    for poly in CONTINENTS:
        pts = [(x + fx * w, y + fy * h) for (fx, fy) in poly]
        cv.poly([(px * SS, py * SS) for (px, py) in pts], MAPLAND)
    for (num, fx, fy) in PINS:
        px = x + fx * w
        py = y + fy * h
        cv.disc(px * SS, py * SS, 7 * SS, RED)
        cv.disc(px * SS, py * SS, 5.4 * SS, WHITE)
        cv.disc(px * SS, py * SS, 4.6 * SS, RED)
        draw_text(cv, str(num), px, py - 3.4, 6.5, WHITE, serif=False,
                  align="center")


# ---------------------------------------------------------------- layout

def fit_brief(text, source, maxw, size=9.5):
    """Trim the headline so headline + source fit in maxw."""
    while text and measure(text + "  " + source, size) > maxw:
        words = text.split(" ")
        if len(words) <= 2:
            break
        text = " ".join(words[:-1])
    return text


def draw_lead(cv, lead, num, x, y, w):
    lead["scene"](cv, x, y, w, 108)
    by = y + 108
    cv.rect(x * SS, by * SS, (x + w) * SS, (by + 20) * SS, RED)
    draw_text(cv, lead["banner"], x + w / 2, by + 3, 11, WHITE, align="center")
    py = by + 24
    draw_text(cv, str(num), x, py, 9, RED)
    draw_text(cv, lead["place"], x + 16, py, 9, GREY)
    tw = measure(lead["tag"], 8) + 10
    tx = x + w - tw
    cv.rect(tx * SS, (py - 1) * SS, (x + w) * SS, (py + 12) * SS,
            TAG_COLORS[lead["tag"]])
    draw_text(cv, lead["tag"], tx + 5, py, 8, WHITE)
    hy = py + 16
    lines = wrap_text(lead["head"], 17, w)[:2]
    draw_text_block(cv, lines, x, hy, 17, INK, serif=True, leading=20)
    dy = hy + len(lines) * 20 + 4
    dlines = wrap_text(lead["deck"], 10.5, w)[:3]
    draw_text_block(cv, dlines, x, dy, 10.5, INK, leading=13)
    sy = dy + len(dlines) * 13 + 4
    draw_text(cv, lead["source"], x, sy, 8.5, GREY)


def draw_card(cv, card, num, x, y, w):
    card["scene"](cv, x, y, w, 44)
    by = y + 44
    cv.rect(x * SS, by * SS, (x + w) * SS, (by + 13) * SS, NAVY2)
    draw_text(cv, card["banner"], x + w / 2, by + 2, 8, WHITE, align="center")
    py = by + 16
    draw_text(cv, str(num), x, py, 8, RED)
    draw_text(cv, card["place"], x + 14, py, 8, GREY)
    tw = measure(card["tag"], 7.5) + 8
    tx = x + w - tw
    cv.rect(tx * SS, (py - 1) * SS, (x + w) * SS, (py + 10) * SS,
            TAG_COLORS[card["tag"]])
    draw_text(cv, card["tag"], tx + 4, py, 7.5, WHITE)
    hy = py + 13
    lines = wrap_text(card["head"], 12.5, w)[:2]
    draw_text_block(cv, lines, x, hy, 12.5, INK, serif=True, leading=15)
    dy = hy + len(lines) * 15 + 3
    dlines = wrap_text(card["deck"], 8, w)[:3]
    draw_text_block(cv, dlines, x, dy, 8, INK, leading=10)


def build():
    cv = Canvas(W, H)
    cv.vgrad(0, 0, W, H, PAPER, (232, 225, 206))
    # --- header band ---
    cv.vgrad(0, 0, W, 20 * SS, NAVY, NAVY2)
    draw_text(cv, "THE WORLD IN ONE DAY", 20, 4, 10, WHITE)
    draw_text(cv, "36 STORIES \u00b7 7 REGIONS \u00b7 13 FIELDS", 1004, 4, 10,
              GOLD2, align="right")
    # --- masthead + kicker ---
    draw_text(cv, "Tuesday 24 November 2026", 512, 26, 46, INK, serif=True,
              align="center")
    draw_text(cv, "Huawei guilty on 10 of 12 counts \u00b7 Four tankers hit in "
                  "the Strait \u00b7 Ukraine strikes Russian ships",
              512, 76, 13, RED, serif=True, italic=True, align="center")
    cv.rect(20 * SS, 93 * SS, 1004 * SS, 95 * SS, RED)
    # --- numbers strip ---
    cv.vgrad(20 * SS, 96 * SS, 1004 * SS, 132 * SS, NAVY, NAVY2)
    cw = 984 / 6
    for i, (num, label) in enumerate(NUMBERS):
        cx = 20 + cw * i
        if i:
            cv.rect((cx) * SS, 100 * SS, (cx + 1) * SS, 128 * SS, NAVY2)
        draw_text(cv, num, cx + cw / 2, 100, 18, WHITE, serif=True,
                  align="center")
        draw_text(cv, label, cx + cw / 2, 123, 8, GOLD2, align="center")
    # --- region chips ---
    widths = []
    for name, count in REGIONS:
        widths.append(measure(name + " " + str(count), 9) + 18)
    gap = (984 - sum(widths)) / 6
    cx = 20
    for (name, count), wd in zip(REGIONS, widths):
        cv.rect(cx * SS, 138 * SS, (cx + wd) * SS, 156 * SS,
                REGION_COLORS[name])
        draw_text(cv, name + " " + str(count), cx + wd / 2, 141, 9, WHITE,
                  align="center")
        cx += wd + gap
    # --- UTC timeline ---
    cv.vgrad(20 * SS, 162 * SS, 1004 * SS, 188 * SS, NAVY, NAVY2)
    draw_text(cv, "THE DAY IN UTC", 28, 171, 9.5, GOLD2)
    cellw = 120
    for i, (t, ev) in enumerate(TIMELINE):
        x = 150 + i * cellw
        if i:
            cv.rect(x * SS, 166 * SS, (x + 1) * SS, 184 * SS, NAVY2)
        draw_text(cv, t, x + 6, 165, 8.5, GOLD2)
        draw_text(cv, ev, x + 6, 176, 8.5, WHITE)
    # --- leads ---
    for i, lead in enumerate(LEADS):
        draw_lead(cv, lead, i + 1, 20 + i * 332, 194, 320)
    # --- cards header + rows ---
    draw_text(cv, "THE DAY IN 10 MORE", 20, 440, 10.5, INK)
    draw_text(cv, "Tuesday's other big stories, across 7 regions", 20 + 190, 441,
              9, GREY)
    cv.rect(20 * SS, 454 * SS, 1004 * SS, 455 * SS, LGREY)
    for r in range(2):
        for c in range(5):
            idx = r * 5 + c
            draw_card(cv, CARDS[idx], idx + 4, 20 + c * 198, 458 + r * 136, 190)
    # --- map + briefs ---
    draw_text(cv, "WHERE IT HAPPENED", 20, 730, 10, INK)
    draw_text(cv, "Pins 1-13 locate the illustrated lead and card stories",
              20, 744, 8, GREY)
    draw_map(cv, 20, 758, 280, 156)
    draw_text(cv, "ALSO ON TUESDAY 24 NOVEMBER \u2014 23 MORE STORIES", 316, 730,
              10, INK)
    cols = [BRIEFS[:12], BRIEFS[12:]]
    for ci, col in enumerate(cols):
        bx = 316 + ci * 344
        for ri, (num, text, source) in enumerate(col):
            yy = 758 + ri * 13.5
            draw_text(cv, str(num), bx, yy, 9, RED)
            t = fit_brief(text, source, 340 - 18 - measure(source + " ", 8),
                          size=8.5)
            draw_text(cv, t, bx + 18, yy, 8.5, INK)
            draw_text(cv, source, bx + 340, yy, 8, GREY, align="right")
    # --- DATE CHECK ---
    cv.rect(20 * SS, 920 * SS, 1004 * SS, 922 * SS, RED)
    cv.rect(20 * SS, 958 * SS, 1004 * SS, 960 * SS, RED)
    cv.rect(20 * SS, 920 * SS, 22 * SS, 960 * SS, RED)
    cv.rect(1002 * SS, 920 * SS, 1004 * SS, 960 * SS, RED)
    draw_text(cv, "DATE CHECK", 28, 925, 9.5, RED)
    draw_text(cv, "LEFT OUT", 28, 937, 9.5, RED)
    exlines = wrap_text(EXCLUDED, 9, 848)
    draw_text_block(cv, exlines[:3], 128, 925, 9, INK, leading=12.5)
    # --- footer ---
    draw_text(cv, "HOW SURE: CONFIRMED 2+ outlets \u00b7 OFFICIAL on the record "
                  "\u00b7 REPORTED one outlet \u00b7 CLAIM one side's account",
              20, 966, 8.5, GREY)
    foot = ("Every story here happened, or was first reported, on Tuesday "
            "24 November 2026; claims are attributed. Sources: Reuters, AP, "
            "CNN, WSJ, BBC, Al Jazeera, US DOJ, NATO, CAS and others. "
            "Pictures and map drawn in code, not photographs.")
    draw_text_block(cv, wrap_text(foot, 8.5, 984), 20, 980, 8.5, GREY,
                    leading=11)
    return cv


def main():
    cv = build()
    rgb = cv.downsample()
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "entry.png")
    size = write_png(rgb, 1024, 1024, path)
    print("wrote", path, size, "bytes")


if __name__ == "__main__":
    main()
