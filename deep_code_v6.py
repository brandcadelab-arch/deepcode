# -*- coding: utf-8 -*-
"""
============================================================================
  DEEP CODE :: STRAZNIK GLEBIN   —   wersja 2.0
  Eko-programowanie / gra edukacyjna w czystym Tkinterze (bez zaleznosci)
============================================================================
  Ulepszenia wzgledem v1:
   * silnik oparty na delta-time (plynne 60 FPS, niezalezne od maszyny)
   * pelny system czasteczek, pierscieni uderzeniowych i tekstow unoszacych
   * proceduralna ryba: splajny, rotacja, machanie ogonem, smuga, dash
   * dynamiczne tlo (gradient 48 pasm) zmieniajace palete w kazdym sektorze
   * promienie swiatla, falujace wodorosty, parallaks, banki powietrza
   * HUD na plotnie: zycie, wynik, combo, pasek dashu, pipsy sektorow
   * 6 przeprojektowanych mini-gier + system ulepszen wplywajacych na gre
   * pauza, restart, ekran tytulowy, ekran koncowy z ranga
============================================================================
"""

import tkinter as tk
import tkinter.font as tkfont
import math
import random
import time

# ---------------------------------------------------------------------------
# KONFIGURACJA
# ---------------------------------------------------------------------------
WIDTH, HEIGHT = 960, 600          # rozmiar swiata gry
PAD = 40                          # margines na wstrzasy ekranu (screen shake)
FPS = 60
FRAME_MS = int(1000 / FPS)

DEEP = "#03101A"                  # bazowy kolor glebi (do mieszania poswiat)

# Palety kolorystyczne kolejnych sektorow: gora, dol, mgla, akcent
PALETTES = [
    {"top": "#0A4E7A", "bot": "#02121F", "fog": "#12729B", "acc": "#FFE066"},  # 1 swiatlo
    {"top": "#4A3416", "bot": "#0E0A06", "fog": "#7A5520", "acc": "#FFB347"},  # 2 korporacja
    {"top": "#06553C", "bot": "#01130E", "fog": "#0C8A5E", "acc": "#3CFFB0"},  # 3 wodorosty
    {"top": "#241046", "bot": "#080415", "fog": "#4A1C78", "acc": "#C08CFF"},  # 4 strefa martwa
    {"top": "#4C0E36", "bot": "#14040D", "fog": "#8A1860", "acc": "#FF5FA2"},  # 5 chemia
    {"top": "#04414E", "bot": "#020A0E", "fog": "#0A93A8", "acc": "#4FF3FF"},  # 6 rdzen
]
MENU_PAL = {"top": "#053049", "bot": "#010A12", "fog": "#0C4E70", "acc": "#4FF3FF"}

# Kolory konsoli
C_OK = "#4FFFC4"
C_BAD = "#FF5C7A"
C_WARN = "#FFD34F"
C_TXT = "#BFEFFF"
C_PANEL = "#061620"
C_PANEL2 = "#0B2434"

SEQUENCE_COLORS = ["RED", "GREEN", "BLUE", "YELLOW"]
COLOR_MAP = {"RED": "#FF3B5C", "GREEN": "#3CFF87", "BLUE": "#4AA8FF", "YELLOW": "#FFD84A"}
COLOR_PL = {"RED": "CZERWONY", "GREEN": "ZIELONY", "BLUE": "NIEBIESKI", "YELLOW": "ZOLTY"}

GARBAGE_TYPES = {
    "PLAST":  {"color": "#D7E7F0", "bin": "YELLOW", "shape": "bottle", "pl": "butelka PET"},
    "METAL":  {"color": "#9AA7B0", "bin": "YELLOW", "shape": "can",    "pl": "puszka"},
    "REDTOX": {"color": "#FF4A5F", "bin": "RED",    "shape": "barrel", "pl": "beczka z toksyna"},
    "SZKLO":  {"color": "#A8F0E4", "bin": "GREEN",  "shape": "bottle", "pl": "sloik"},
    "PAPIER": {"color": "#F2E3B0", "bin": "BLUE",   "shape": "box",    "pl": "karton"},
}
BIN_ORDER = ["RED", "YELLOW", "GREEN", "BLUE"]
BIN_LABEL = {"RED": "TOKSYCZNE", "YELLOW": "METAL/PLAST", "GREEN": "SZKLO", "BLUE": "PAPIER"}


# ---------------------------------------------------------------------------
# NARZEDZIA
# ---------------------------------------------------------------------------
def clamp(v, a, b):
    return a if v < a else (b if v > b else v)


def lerp(a, b, t):
    return a + (b - a) * t


def hex2rgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb2hex(c):
    return "#%02x%02x%02x" % (int(clamp(c[0], 0, 255)),
                              int(clamp(c[1], 0, 255)),
                              int(clamp(c[2], 0, 255)))


def mix(c1, c2, t):
    """Miesza dwa kolory hex (t=0 -> c1, t=1 -> c2)."""
    a, b = hex2rgb(c1), hex2rgb(c2)
    return rgb2hex(tuple(lerp(a[i], b[i], t) for i in range(3)))


def shade(c, f):
    """Rozjasnia (f>1) lub przyciemnia (f<1) kolor."""
    return rgb2hex(tuple(x * f for x in hex2rgb(c)))


def glow_of(c, strength=0.72):
    """Kolor 'poswiaty' — udawana przezroczystosc przez zmieszanie z glebia."""
    return mix(c, DEEP, strength)


def ang_diff(a, b):
    d = (b - a + math.pi) % (2 * math.pi) - math.pi
    return d


# Ksztalt ciala ryby w przestrzeni lokalnej (skala = body_size)
BODY_PTS = [(1.08, 0.00), (0.74, -0.33), (0.20, -0.50), (-0.34, -0.42),
            (-0.80, -0.20), (-0.95, 0.00), (-0.80, 0.20), (-0.34, 0.42),
            (0.20, 0.50), (0.74, 0.33)]


# ---------------------------------------------------------------------------
# PROCEDURALNE STWORZENIA (błazenek, pokolec, krewetka, plankton, meduza)
# ---------------------------------------------------------------------------
def xform(x, y, pts, s=1.0, ang=0.0, flip=1):
    """Przenosi punkty z przestrzeni lokalnej stworzenia na ekran."""
    ca, sa = math.cos(ang), math.sin(ang)
    out = []
    for lx, ly in pts:
        lx *= s
        ly *= s * flip
        out.append(x + lx * ca - ly * sa)
        out.append(y + lx * sa + ly * ca)
    return out


def _poly(c, fill, outline="", w=0):
    return c.create_polygon([0, 0, 1, 1, 2, 2], fill=fill, outline=outline, width=w, smooth=True)


CLOWN_BODY = [(1.00, 0.02), (0.62, -0.40), (0.05, -0.60), (-0.48, -0.48),
              (-0.82, -0.20), (-0.92, 0.02), (-0.82, 0.24), (-0.48, 0.50),
              (0.05, 0.62), (0.62, 0.44)]
CLOWN_BANDS = [[(0.56, -0.44), (0.40, -0.50), (0.28, 0.50), (0.46, 0.46)],
               [(0.06, -0.60), (-0.13, -0.58), (-0.24, 0.58), (-0.03, 0.60)],
               [(-0.60, -0.38), (-0.73, -0.32), (-0.78, 0.32), (-0.65, 0.38)]]
TANG_BODY = [(1.06, 0.06), (0.74, -0.30), (0.20, -0.54), (-0.34, -0.46),
             (-0.72, -0.20), (-0.84, 0.04), (-0.70, 0.30), (-0.20, 0.50),
             (0.34, 0.46), (0.80, 0.26)]
TANG_MARK = [(0.46, -0.14), (0.18, -0.42), (-0.30, -0.38), (-0.60, -0.12),
             (-0.60, 0.10), (-0.28, 0.04), (0.08, 0.04), (0.32, -0.02)]


def make_clownfish(game, layer="L_WORLD"):
    """Błazenek: pomarańczowe ciało, trzy białe pasy z czarną obwódką."""
    c = game.canvas
    d = {"kind": "clown"}
    order = []
    d["glow"] = c.create_oval(0, 0, 1, 1, fill="#000000", outline="")
    order.append(d["glow"])
    for k, col in (("tail", "#FF7A18"), ("dorsal", "#FF7A18"), ("pelvic", "#FF9440")):
        d[k] = _poly(c, col, "#2A1206", 2)
        order.append(d[k])
    d["body"] = _poly(c, "#FF8A2B", "#2A1206", 2)
    order.append(d["body"])
    for k in ("b1", "b2", "b3"):
        d[k] = _poly(c, "#FFF6E8", "#2A1206", 1)
        order.append(d[k])
    d["pect"] = _poly(c, "#FFA24E", "#2A1206", 1)
    order.append(d["pect"])
    d["eye"] = c.create_oval(0, 0, 1, 1, fill="#FFFFFF", outline="#2A1206")
    d["pupil"] = c.create_oval(0, 0, 1, 1, fill="#0B0703", outline="")
    order += [d["eye"], d["pupil"]]
    for i in order:
        game.to_layer(i, layer)
    d["ids"] = order
    return d


def draw_clownfish(game, d, x, y, s, ang=0.0, ph=0.0):
    c = game.canvas
    flip = -1 if math.cos(ang) < 0 else 1
    wag = math.sin(ph * 6) * 0.16
    flap = math.sin(ph * 8) * 0.14

    def L(pts):
        return xform(x, y, pts, s, ang, flip)
    r = s * 1.85
    c.coords(d["glow"], x - r, y - r, x + r, y + r)
    c.itemconfigure(d["glow"], fill=mix("#FF8A2B", game.bg_at(y), 0.86))
    c.coords(d["tail"], *L([(-0.86, 0.0), (-1.30, -0.52 + wag), (-1.46, -0.20 + wag),
                            (-1.42, 0.0), (-1.46, 0.24 + wag), (-1.30, 0.56 + wag)]))
    c.coords(d["dorsal"], *L([(0.26, -0.52), (-0.06, -0.86), (-0.46, -0.46)]))
    c.coords(d["pelvic"], *L([(0.10, 0.54), (-0.08, 0.84), (-0.34, 0.46)]))
    c.coords(d["body"], *L(CLOWN_BODY))
    for k, pts in zip(("b1", "b2", "b3"), CLOWN_BANDS):
        c.coords(d[k], *L(pts))
    c.coords(d["pect"], *L([(0.28, 0.20), (-0.02, 0.56 + flap), (0.06, 0.16)]))
    ex, ey = L([(0.56, -0.16)])
    er = s * 0.19
    c.coords(d["eye"], ex - er, ey - er, ex + er, ey + er)
    px, py = L([(0.60, -0.16)])
    pr = s * 0.10
    c.coords(d["pupil"], px - pr, py - pr, px + pr, py + pr)


def make_tang(game, layer="L_WORLD"):
    """Pokolec królewski: granatowo-niebieskie ciało, żółty ogon."""
    c = game.canvas
    d = {"kind": "tang"}
    order = []
    d["glow"] = c.create_oval(0, 0, 1, 1, fill="#000000", outline="")
    order.append(d["glow"])
    d["tail"] = _poly(c, "#FFD23A", "#0E1730", 2)
    d["dorsal"] = _poly(c, "#3B9BF0", "#0E1730", 2)
    d["anal"] = _poly(c, "#3B9BF0", "#0E1730", 2)
    order += [d["tail"], d["dorsal"], d["anal"]]
    d["body"] = _poly(c, "#3B9BF0", "#0E1730", 2)
    d["mark"] = _poly(c, "#101B36", "", 0)
    d["pect"] = _poly(c, "#7FC2FF", "#0E1730", 1)
    order += [d["body"], d["mark"], d["pect"]]
    d["eye"] = c.create_oval(0, 0, 1, 1, fill="#FFFFFF", outline="#0E1730")
    d["pupil"] = c.create_oval(0, 0, 1, 1, fill="#08131C", outline="")
    order += [d["eye"], d["pupil"]]
    for i in order:
        game.to_layer(i, layer)
    d["ids"] = order
    return d


def draw_tang(game, d, x, y, s, ang=0.0, ph=0.0):
    c = game.canvas
    flip = -1 if math.cos(ang) < 0 else 1
    wag = math.sin(ph * 5) * 0.18
    flap = math.sin(ph * 7) * 0.14

    def L(pts):
        return xform(x, y, pts, s, ang, flip)
    r = s * 1.9
    c.coords(d["glow"], x - r, y - r, x + r, y + r)
    c.itemconfigure(d["glow"], fill=mix("#3B9BF0", game.bg_at(y), 0.80))
    c.coords(d["tail"], *L([(-0.80, 0.02), (-1.24, -0.46 + wag), (-1.34, -0.10 + wag),
                            (-1.30, 0.06), (-1.34, 0.20 + wag), (-1.24, 0.52 + wag)]))
    c.coords(d["dorsal"], *L([(0.42, -0.40), (0.00, -0.66), (-0.56, -0.34), (-0.20, -0.40)]))
    c.coords(d["anal"], *L([(0.22, 0.44), (-0.10, 0.70), (-0.56, 0.34), (-0.20, 0.44)]))
    c.coords(d["body"], *L(TANG_BODY))
    c.coords(d["mark"], *L(TANG_MARK))
    c.coords(d["pect"], *L([(0.30, 0.18), (0.00, 0.54 + flap), (0.10, 0.14)]))
    ex, ey = L([(0.62, -0.12)])
    er = s * 0.20
    c.coords(d["eye"], ex - er, ey - er, ex + er, ey + er)
    px, py = L([(0.67, -0.12)])
    pr = s * 0.11
    c.coords(d["pupil"], px - pr, py - pr, px + pr, py + pr)


def make_shrimp(game, layer="L_WORLD"):
    """Krewetka: przezroczysto-pomarańczowy odwłok, wachlarz ogonowy, czułki."""
    c = game.canvas
    d = {"kind": "shrimp"}
    order = []
    d["glow"] = c.create_oval(0, 0, 1, 1, fill="#000000", outline="")
    d["ant1"] = c.create_line(0, 0, 1, 1, fill="#FFCFA0", width=1, smooth=True)
    d["ant2"] = c.create_line(0, 0, 1, 1, fill="#FFCFA0", width=1, smooth=True)
    d["fan"] = _poly(c, "#FFC07A", "#7A3A10", 1)
    d["body"] = _poly(c, "#FF9F5A", "#7A3A10", 2)
    d["seg"] = c.create_line(0, 0, 1, 1, fill="#C46A28", width=1, smooth=True)
    d["legs"] = c.create_line(0, 0, 1, 1, fill="#C46A28", width=1, smooth=True)
    d["eye"] = c.create_oval(0, 0, 1, 1, fill="#1B0E06", outline="")
    order = [d["glow"], d["ant1"], d["ant2"], d["fan"], d["body"], d["seg"], d["legs"], d["eye"]]
    for i in order:
        game.to_layer(i, layer)
    d["ids"] = order
    return d


def draw_shrimp(game, d, x, y, s, ang=0.0, ph=0.0):
    c = game.canvas
    flip = -1 if math.cos(ang) < 0 else 1
    curl = math.sin(ph * 5) * 0.12

    def L(pts):
        return xform(x, y, pts, s, ang, flip)
    r = s * 1.9
    c.coords(d["glow"], x - r, y - r, x + r, y + r)
    c.itemconfigure(d["glow"], fill=mix("#FF9F5A", game.bg_at(y), 0.86))
    c.coords(d["body"], *L([(0.92, -0.10), (0.55, -0.46), (0.00, -0.52),
                            (-0.55, -0.30 + curl), (-0.92, 0.10 + curl), (-0.55, 0.34 + curl),
                            (0.00, 0.30), (0.55, 0.16)]))
    c.coords(d["seg"], *L([(0.42, -0.40), (0.10, -0.44), (-0.28, -0.30)]))
    c.coords(d["fan"], *L([(-0.85, 0.06 + curl), (-1.35, -0.36 + curl),
                           (-1.18, 0.08 + curl), (-1.35, 0.48 + curl)]))
    c.coords(d["ant1"], *L([(0.85, -0.14), (1.35, -0.42 + curl), (1.72, -0.30)]))
    c.coords(d["ant2"], *L([(0.85, -0.02), (1.40, 0.14 + curl), (1.78, 0.06)]))
    c.coords(d["legs"], *L([(0.42, 0.20), (0.20, 0.50), (-0.10, 0.28), (-0.34, 0.52)]))
    ex, ey = L([(0.66, -0.22)])
    er = s * 0.13
    c.coords(d["eye"], ex - er, ey - er, ex + er, ey + er)


def make_plankton(game, layer="L_WORLD"):
    """Plankton: świecąca komórka z wieńcem rzęsek."""
    c = game.canvas
    d = {"kind": "plankton", "cilia": []}
    d["glow"] = c.create_oval(0, 0, 1, 1, fill="#000000", outline="")
    order = [d["glow"]]
    for _ in range(7):
        ln = c.create_line(0, 0, 1, 1, fill="#BFFF9E", width=1)
        d["cilia"].append(ln)
        order.append(ln)
    d["cell"] = c.create_oval(0, 0, 1, 1, fill="#8CFF6B", outline="#EAFFDF", width=2)
    d["core"] = c.create_oval(0, 0, 1, 1, fill="#3FBF2E", outline="")
    order += [d["cell"], d["core"]]
    for i in order:
        game.to_layer(i, layer)
    d["ids"] = order
    return d


def draw_plankton(game, d, x, y, s, ang=0.0, ph=0.0):
    c = game.canvas
    r = s * (1 + 0.10 * math.sin(ph * 4))
    c.coords(d["cell"], x - r, y - r, x + r, y + r)
    c.coords(d["core"], x - r * 0.38, y - r * 0.38, x + r * 0.38, y + r * 0.38)
    g = r * 2.2
    c.coords(d["glow"], x - g, y - g, x + g, y + g)
    c.itemconfigure(d["glow"], fill=mix("#8CFF6B", game.bg_at(y), 0.80))
    for k, ln in enumerate(d["cilia"]):
        a = ph * 0.9 + math.tau * k / len(d["cilia"])
        w = math.sin(ph * 6 + k) * 0.22
        c.coords(ln, x + math.cos(a) * r * 0.9, y + math.sin(a) * r * 0.9,
                 x + math.cos(a + w) * r * 1.75, y + math.sin(a + w) * r * 1.75)


def make_jelly(game, color, layer="L_WORLD"):
    """Meduza: dzwon + macki."""
    c = game.canvas
    d = {"kind": "jelly", "col": color, "tent": []}
    d["glow"] = c.create_oval(0, 0, 1, 1, fill="#000000", outline="")
    order = [d["glow"]]
    for _ in range(5):
        ln = c.create_line(0, 0, 1, 1, fill=color, width=2, smooth=True)
        d["tent"].append(ln)
        order.append(ln)
    d["bell"] = _poly(c, mix(color, DEEP, 0.30), color, 2)
    d["shine"] = _poly(c, mix(color, "#FFFFFF", 0.45), "", 0)
    order += [d["bell"], d["shine"]]
    for i in order:
        game.to_layer(i, layer)
    d["ids"] = order
    return d


def draw_jelly(game, d, x, y, r, ph=0.0):
    c = game.canvas
    rr = r * (1 + 0.14 * math.sin(ph * 3))
    pts = []
    for k in range(9):
        a = math.pi + math.pi * k / 8.0
        pts += [x + math.cos(a) * rr, y + math.sin(a) * rr * 1.05]
    pts += [x + rr * 0.55, y + rr * 0.34, x, y + rr * 0.12, x - rr * 0.55, y + rr * 0.34]
    c.coords(d["bell"], *pts)
    c.coords(d["shine"], x - rr * 0.5, y - rr * 0.42, x - rr * 0.1, y - rr * 0.62,
             x + rr * 0.25, y - rr * 0.40, x - rr * 0.1, y - rr * 0.30)
    g = rr * 2.1
    c.coords(d["glow"], x - g, y - g, x + g, y + g)
    c.itemconfigure(d["glow"], fill=mix(d["col"], game.bg_at(y), 0.74))
    for k, ln in enumerate(d["tent"]):
        tx = x - rr * 0.62 + k * (rr * 0.31)
        p2 = []
        for j in range(4):
            f = j / 3.0
            p2 += [tx + math.sin(ph * 3 + f * 3.2 + k) * rr * 0.28 * f,
                   y + rr * 0.30 + f * rr * 1.9]
        c.coords(ln, *p2)


# ---------------------------------------------------------------------------
# SYSTEM EFEKTOW (czasteczki, pierscienie, teksty)
# ---------------------------------------------------------------------------
class Fx:
    def __init__(self, game, cap=170, rings=14, texts=10):
        self.g = game
        c = game.canvas
        self.free, self.live = [], []
        for _ in range(cap):
            i = c.create_oval(-60, -60, -56, -56, fill="#ffffff", outline="", state="hidden")
            game.to_layer(i, "L_FX")
            self.free.append(i)
        self.ring_free, self.ring_live = [], []
        for _ in range(rings):
            i = c.create_oval(-60, -60, -50, -50, outline="#ffffff", width=2, state="hidden")
            game.to_layer(i, "L_FX")
            self.ring_free.append(i)
        self.txt_free, self.txt_live = [], []
        for _ in range(texts):
            sh = c.create_text(-60, -60, text="", fill="#000000", font=game.f_small,
                               state="hidden")
            i = c.create_text(-60, -60, text="", fill="#ffffff", font=game.f_small,
                              state="hidden")
            game.to_layer(sh, "L_FX")
            game.to_layer(i, "L_FX")
            self.txt_free.append((i, sh))

    # -- czasteczki -------------------------------------------------------
    def spawn(self, x, y, vx, vy, color, size=4, life=0.7, grav=0.0, fade_to=None):
        if not self.free:
            return
        i = self.free.pop()
        self.g.canvas.itemconfigure(i, fill=color, state="normal")
        self.live.append({"id": i, "x": x, "y": y, "vx": vx, "vy": vy, "s": size,
                          "t": 0.0, "life": life, "g": grav,
                          "c0": color, "c1": fade_to or mix(color, self.g.bg_at(y), 0.92)})

    def burst(self, x, y, color, n=14, speed=170, size=4, life=0.6, spread=math.tau, base=0.0, grav=0.0):
        for _ in range(n):
            a = base + random.uniform(-spread / 2, spread / 2)
            sp = speed * random.uniform(0.35, 1.0)
            self.spawn(x, y, math.cos(a) * sp, math.sin(a) * sp, color,
                       size * random.uniform(0.6, 1.4), life * random.uniform(0.7, 1.3), grav)

    # -- pierscienie ------------------------------------------------------
    def ring(self, x, y, color, r0, r1, life=0.5, width=3):
        if not self.ring_free:
            return
        i = self.ring_free.pop()
        self.g.canvas.itemconfigure(i, outline=color, width=width, state="normal")
        self.ring_live.append({"id": i, "x": x, "y": y, "r0": r0, "r1": r1,
                               "t": 0.0, "life": life, "w": width, "c": color})

    # -- teksty -----------------------------------------------------------
    def text(self, x, y, txt, color, life=0.9, rise=46, font=None):
        if not self.txt_free:
            return
        i, sh = self.txt_free.pop()
        f = font or self.g.f_small
        self.g.canvas.itemconfigure(sh, text=txt, state="normal", font=f,
                                    fill=mix(self.g.bg_at(y), "#000000", 0.75))
        self.g.canvas.itemconfigure(i, text=txt, fill=color, state="normal", font=f)
        self.g.canvas.tag_raise(sh)
        self.g.canvas.tag_raise(i)
        self.txt_live.append({"id": i, "sh": sh, "x": x, "y": y, "t": 0.0, "life": life,
                              "rise": rise, "c": color})

    # -- aktualizacja -----------------------------------------------------
    def update(self, dt):
        c = self.g.canvas
        for p in self.live[:]:
            p["t"] += dt
            k = p["t"] / p["life"]
            if k >= 1.0:
                c.itemconfigure(p["id"], state="hidden")
                self.free.append(p["id"])
                self.live.remove(p)
                continue
            p["vy"] += p["g"] * dt
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vx"] *= (1 - 1.6 * dt)
            p["vy"] *= (1 - 1.6 * dt)
            s = p["s"] * (1 - k * 0.75)
            c.coords(p["id"], p["x"] - s, p["y"] - s, p["x"] + s, p["y"] + s)
            c.itemconfigure(p["id"], fill=mix(p["c0"], p["c1"], k))

        for r in self.ring_live[:]:
            r["t"] += dt
            k = r["t"] / r["life"]
            if k >= 1.0:
                c.itemconfigure(r["id"], state="hidden")
                self.ring_free.append(r["id"])
                self.ring_live.remove(r)
                continue
            rr = lerp(r["r0"], r["r1"], 1 - (1 - k) ** 2)
            c.coords(r["id"], r["x"] - rr, r["y"] - rr, r["x"] + rr, r["y"] + rr)
            c.itemconfigure(r["id"], outline=mix(r["c"], self.g.bg_at(r["y"]), k),
                            width=max(1, r["w"] * (1 - k)))

        for t in self.txt_live[:]:
            t["t"] += dt
            k = t["t"] / t["life"]
            if k >= 1.0:
                c.itemconfigure(t["id"], state="hidden")
                c.itemconfigure(t["sh"], state="hidden")
                self.txt_free.append((t["id"], t["sh"]))
                self.txt_live.remove(t)
                continue
            ty = t["y"] - t["rise"] * k
            c.coords(t["id"], t["x"], ty)
            c.coords(t["sh"], t["x"] + 1.5, ty + 1.5)
            bg = self.g.bg_at(t["y"])
            c.itemconfigure(t["id"], fill=mix(t["c"], bg, k * 0.95))
            c.itemconfigure(t["sh"], fill=mix(mix(bg, "#000000", 0.75), bg, k * 0.95))

    def clear(self):
        c = self.g.canvas
        for p in self.live:
            c.itemconfigure(p["id"], state="hidden")
            self.free.append(p["id"])
        for r in self.ring_live:
            c.itemconfigure(r["id"], state="hidden")
            self.ring_free.append(r["id"])
        for t in self.txt_live:
            c.itemconfigure(t["id"], state="hidden")
            c.itemconfigure(t["sh"], state="hidden")
            self.txt_free.append((t["id"], t["sh"]))
        self.live, self.ring_live, self.txt_live = [], [], []


# ---------------------------------------------------------------------------
# RYBA / MIKROBA — proceduralnie rysowana postac
# ---------------------------------------------------------------------------
class Fish:
    def __init__(self, game, x, y, size, body, fin, is_player=False, trail=0):
        self.g = game
        c = game.canvas
        self.x, self.y = x, y
        self.vx = self.vy = 0.0
        self.size = size
        self.body_col, self.fin_col = body, fin
        self.is_player = is_player
        self.angle = 0.0
        self.flip = 1
        self.phase = random.uniform(0, math.tau)
        self.upgrades = 0
        self.parts = []
        self.layer = "L_PLAYER" if is_player else "L_WORLD"

        gl = glow_of(body, 0.80)
        gl2 = glow_of(body, 0.90)
        self.trail_ids = []
        for _ in range(trail):
            i = c.create_oval(-60, -60, -50, -50, fill=gl2, outline="", state="hidden")
            game.to_layer(i, self.layer)
            self.trail_ids.append(i)
        self.trail_pts = []

        self.glow3 = self._mk(c.create_oval(0, 0, 1, 1, fill=gl2, outline=""))
        self.glow2 = self._mk(c.create_oval(0, 0, 1, 1, fill=gl2, outline=""))
        self.glow = self._mk(c.create_oval(0, 0, 1, 1, fill=gl, outline=""))
        self.tail = self._mk(c.create_polygon([0, 0, 1, 1, 2, 2], fill=fin,
                                              outline=shade(fin, 0.72), width=1, smooth=True))
        self.rays = [self._mk(c.create_line(0, 0, 1, 1, fill=shade(fin, 0.7), width=1,
                                            smooth=True)) for _ in range(3)]
        self.dorsal = self._mk(c.create_polygon([0, 0, 1, 1, 2, 2], fill=fin, outline="", smooth=True))
        self.pect = self._mk(c.create_polygon([0, 0, 1, 1, 2, 2], fill=shade(fin, 0.85), outline="", smooth=True))
        self.body = self._mk(c.create_polygon([0, 0, 1, 1, 2, 2], fill=body,
                                              outline=shade(body, 1.35), width=2, smooth=True))
        self.belly = self._mk(c.create_polygon([0, 0, 1, 1, 2, 2], fill=shade(body, 0.72),
                                               outline="", smooth=True))
        self.back = self._mk(c.create_polygon([0, 0, 1, 1, 2, 2], fill=shade(body, 1.32),
                                              outline="", smooth=True))
        self.gill = self._mk(c.create_line(0, 0, 1, 1, fill=shade(body, 0.66), width=2,
                                           smooth=True))
        self.eye = self._mk(c.create_oval(0, 0, 1, 1, fill="#F4FBFF", outline=""))
        self.pupil = self._mk(c.create_oval(0, 0, 1, 1, fill="#08131C", outline=""))
        self.shine = self._mk(c.create_oval(0, 0, 1, 1, fill="#FFFFFF", outline=""))
        # elementy ulepszen (tworzone od razu, ukryte)
        self.up_shield = self._mk(c.create_oval(0, 0, 1, 1, outline=C_OK, width=2, state="hidden"))
        self.up_core = self._mk(c.create_oval(0, 0, 1, 1, fill="#5CFFE0", outline="#EAFFFA",
                                              width=1, state="hidden"))
        self.up_ant = self._mk(c.create_line(0, 0, 1, 1, fill="#FFE066", width=2, state="hidden"))
        self.up_ant_d = self._mk(c.create_oval(0, 0, 1, 1, fill="#FFE066", outline="", state="hidden"))

    def _mk(self, item):
        self.g.to_layer(item, self.layer)
        self.parts.append(item)
        return item

    def destroy(self):
        for i in self.parts + self.trail_ids:
            self.g.canvas.delete(i)
        self.parts, self.trail_ids = [], []

    # -- transformacja lokalna -> ekran ----------------------------------
    def loc(self, pts, s=None):
        s = s or self.size
        ca, sa = math.cos(self.angle), math.sin(self.angle)
        out = []
        for lx, ly in pts:
            lx *= s
            ly *= s * self.flip
            out.append(self.x + lx * ca - ly * sa)
            out.append(self.y + lx * sa + ly * ca)
        return out

    def face(self, dt, moving_angle=None):
        if moving_angle is not None:
            self.angle += ang_diff(self.angle, moving_angle) * min(1.0, dt * 9.0)
        self.flip = -1 if math.cos(self.angle) < 0 else 1

    def draw(self, dt, speed_hint=0.0):
        c = self.g.canvas
        s = self.size
        self.phase += dt * (5.0 + min(11.0, speed_hint * 0.02))
        wag = math.sin(self.phase) * 0.22
        flap = math.sin(self.phase * 1.7) * 0.18

        # smuga
        if self.trail_ids:
            self.trail_pts.insert(0, (self.x, self.y))
            del self.trail_pts[len(self.trail_ids) * 3:]
            for n, i in enumerate(self.trail_ids):
                k = n * 3
                if k < len(self.trail_pts) and speed_hint > 70:
                    tx, ty = self.trail_pts[k]
                    r = s * 0.55 * (1 - n / (len(self.trail_ids) + 1.0))
                    c.coords(i, tx - r, ty - r, tx + r, ty + r)
                    c.itemconfigure(i, state="normal",
                                    fill=mix(self.body_col, self.g.bg_at(ty), 0.72))
                else:
                    c.itemconfigure(i, state="hidden")

        bg = self.g.bg_at(self.y)
        g1 = s * 1.30
        c.coords(self.glow, self.x - g1, self.y - g1, self.x + g1, self.y + g1)
        g2 = s * 1.72
        c.coords(self.glow2, self.x - g2, self.y - g2, self.x + g2, self.y + g2)
        g3 = s * (2.25 + 0.10 * math.sin(self.phase * 0.7))
        c.coords(self.glow3, self.x - g3, self.y - g3, self.x + g3, self.y + g3)
        c.itemconfigure(self.glow, fill=mix(self.body_col, bg, 0.68))
        c.itemconfigure(self.glow2, fill=mix(self.body_col, bg, 0.84))
        c.itemconfigure(self.glow3, fill=mix(self.body_col, bg, 0.93))

        c.coords(self.tail, *self.loc([
            (-0.82, 0.00), (-1.20, -0.40 + wag), (-1.58, -0.66 + wag * 1.9),
            (-1.26, 0.00), (-1.58, 0.62 + wag * 1.9), (-1.20, 0.38 + wag)]))
        for ri, ray in enumerate(self.rays):
            fr = -0.35 + ri * 0.35
            c.coords(ray, *self.loc([(-0.92, fr * 0.30),
                                     (-1.20, fr * 0.62 + wag * 0.9),
                                     (-1.52, fr * 0.95 + wag * 1.7)]))
        c.coords(self.dorsal, *self.loc([
            (0.20, -0.44), (-0.10, -0.86 + wag * 0.35), (-0.52, -0.34)]))
        c.coords(self.pect, *self.loc([
            (0.42, 0.16), (-0.02, 0.52 + flap), (0.14, 0.15)]))
        c.coords(self.body, *self.loc(BODY_PTS))
        c.coords(self.belly, *self.loc([
            (0.72, 0.20), (0.18, 0.42), (-0.32, 0.34), (-0.70, 0.14), (-0.20, 0.10), (0.35, 0.12)]))
        c.coords(self.back, *self.loc([
            (0.74, -0.16), (0.22, -0.36), (-0.30, -0.31), (-0.66, -0.13),
            (-0.22, -0.09), (0.34, -0.11)]))
        c.coords(self.gill, *self.loc([(0.40, -0.30), (0.30, 0.00), (0.40, 0.28)]))

        ex, ey = self.loc([(0.60, -0.17)])
        r = s * 0.17
        c.coords(self.eye, ex - r, ey - r, ex + r, ey + r)
        px, py = self.loc([(0.66, -0.17)])
        r2 = s * 0.085
        c.coords(self.pupil, px - r2, py - r2, px + r2, py + r2)
        sx, sy = self.loc([(0.63, -0.24)])
        r3 = s * 0.045
        c.coords(self.shine, sx - r3, sy - r3, sx + r3, sy + r3)

        # ulepszenia
        if self.upgrades >= 1:
            on = self.g.shield_ready
            rr = s * (1.85 + 0.10 * math.sin(self.phase * 1.3))
            c.coords(self.up_shield, self.x - rr, self.y - rr, self.x + rr, self.y + rr)
            c.itemconfigure(self.up_shield, state="normal" if on else "hidden",
                            outline=mix(C_OK, DEEP, 0.25))
        if self.upgrades >= 2:
            cx, cy = self.loc([(-0.72, 0.0)])
            pr = s * (0.20 + 0.06 * math.sin(self.phase * 3.2))
            c.coords(self.up_core, cx - pr, cy - pr, cx + pr, cy + pr)
            c.itemconfigure(self.up_core, state="normal")
            if speed_hint > 120 and random.random() < 0.55:
                a = self.angle + math.pi + random.uniform(-0.4, 0.4)
                self.g.fx.spawn(cx, cy, math.cos(a) * 90, math.sin(a) * 90,
                                "#7CFFE8", 3, 0.35)
        if self.upgrades >= 3:
            a1 = self.loc([(0.25, -0.42)])
            a2 = self.loc([(0.05, -1.05)])
            c.coords(self.up_ant, a1[0], a1[1], a2[0], a2[1])
            dr = s * 0.11
            c.coords(self.up_ant_d, a2[0] - dr, a2[1] - dr, a2[0] + dr, a2[1] + dr)
            c.itemconfigure(self.up_ant, state="normal")
            c.itemconfigure(self.up_ant_d, state="normal",
                            fill="#FFE066" if int(self.phase * 3) % 2 else "#FF9F2E")

    def set_upgrades(self, n):
        self.upgrades = n


# ---------------------------------------------------------------------------
# SEKTORY
# ---------------------------------------------------------------------------
class Sector:
    name = "SEKTOR"
    subtitle = ""
    console = True          # czy pole konsoli jest aktywne
    reward = ""
    enemies = True          # czy w tym sektorze patrolują AWARY

    def __init__(self, game):
        self.g = game

    @property
    def head(self):
        """Nagłówek z numerem pozycji — kolejność sektorów jest losowa."""
        return "SEKTOR %d · %s" % (self.g.sector_i + 1, self.name)

    def start(self):
        pass

    def update(self, dt):
        pass

    def on_code(self, code):
        return False

    def on_key(self, key):
        pass

    def on_click(self, x, y):
        pass

    def cleanup(self):
        pass

    def hint(self):
        return ""


# ------------------------------ SEKTOR 1 -----------------------------------
class LightSector(Sector):
    name = "FOTOSYNTEZA"
    subtitle = "Zbierz fotony i uruchom przemianę energii"
    console = False
    reward = "OSŁONA FOTOSYNTEZY  (tarcza pochłaniająca jedno trafienie)"

    def start(self):
        self.target = 8
        self.got = 0
        self.photons = []
        self.sludge = []
        self.t = 0.0
        for _ in range(5):
            self._spawn_photon()
        for _ in range(3):
            self._spawn_sludge()
        self.g.say("Sterowanie: prowadź Mikrobę MYSZKĄ (lub strzałkami). Klik / SPACJA = zryw.",
                   "Wchłoń 8 fotonów. Omijaj fioletowe kłęby toksyn — parzą!", C_TXT)
        self._obj()

    def _obj(self):
        self.g.objective("%s — FOTONY %d/%d" % (self.head, self.got, self.target))

    def _spawn_photon(self):
        c = self.g.canvas
        x = random.uniform(WIDTH * 0.28, WIDTH - 60)
        y = random.uniform(70, HEIGHT - 70)
        halo = c.create_oval(0, 0, 1, 1, fill=glow_of("#FFE066", 0.72), outline="")
        star = c.create_polygon([0, 0, 1, 1, 2, 2], fill="#FFF6C2", outline="", smooth=False)
        core = c.create_oval(0, 0, 1, 1, fill="#FFFDF2", outline="#FFE066", width=2)
        for i in (halo, star, core):
            self.g.to_layer(i, "L_WORLD")
        a = random.uniform(0, math.tau)
        self.photons.append({"x": x, "y": y, "vx": math.cos(a) * 55, "vy": math.sin(a) * 55,
                             "halo": halo, "star": star, "core": core,
                             "ph": random.uniform(0, 6)})

    def _spawn_sludge(self):
        c = self.g.canvas
        x = random.uniform(WIDTH * 0.4, WIDTH - 40)
        y = random.uniform(60, HEIGHT - 60)
        halo = c.create_oval(0, 0, 1, 1, fill=glow_of("#9B4DFF", 0.62), outline="")
        core = c.create_polygon([0, 0, 1, 1, 2, 2], fill="#7A2FD0",
                                outline="#C08CFF", width=2, smooth=True)
        self.g.to_layer(halo, "L_WORLD")
        self.g.to_layer(core, "L_WORLD")
        a = random.uniform(0, math.tau)
        self.sludge.append({"x": x, "y": y, "vx": math.cos(a) * 40, "vy": math.sin(a) * 40,
                            "halo": halo, "core": core, "ph": random.uniform(0, 6), "r": 20})

    def update(self, dt):
        self.t += dt
        c = self.g.canvas
        p = self.g.player
        mag = 120 if self.g.upgrades >= 3 else 0

        for ph in self.photons[:]:
            ph["ph"] += dt * 3
            dx, dy = p.x - ph["x"], p.y - ph["y"]
            d = math.hypot(dx, dy) + 0.001
            if mag and d < mag:
                ph["vx"] += dx / d * 260 * dt
                ph["vy"] += dy / d * 260 * dt
            ph["vx"] += random.uniform(-40, 40) * dt
            ph["vy"] += random.uniform(-40, 40) * dt
            sp = math.hypot(ph["vx"], ph["vy"])
            if sp > 150:
                ph["vx"] *= 150 / sp
                ph["vy"] *= 150 / sp
            ph["x"] += ph["vx"] * dt
            ph["y"] += ph["vy"] * dt
            if ph["x"] < 24 or ph["x"] > WIDTH - 24:
                ph["vx"] *= -1
                ph["x"] = clamp(ph["x"], 24, WIDTH - 24)
            if ph["y"] < 24 or ph["y"] > HEIGHT - 24:
                ph["vy"] *= -1
                ph["y"] = clamp(ph["y"], 24, HEIGHT - 24)
            r = 8 + math.sin(ph["ph"]) * 1.6
            R = r * (2.1 + 0.25 * math.sin(ph["ph"] * 0.8))
            c.coords(ph["core"], ph["x"] - r, ph["y"] - r, ph["x"] + r, ph["y"] + r)
            c.coords(ph["halo"], ph["x"] - R, ph["y"] - R, ph["x"] + R, ph["y"] + R)
            c.itemconfigure(ph["halo"], fill=mix("#FFE066", self.g.bg_at(ph["y"]), 0.76))
            spts = []
            for k in range(8):
                aa = ph["ph"] * 0.6 + math.tau * k / 8
                rad = r * (2.6 if k % 2 == 0 else 0.75)
                spts += [ph["x"] + math.cos(aa) * rad, ph["y"] + math.sin(aa) * rad]
            c.coords(ph["star"], *spts)
            c.itemconfigure(ph["star"], fill=mix("#FFF0A8", self.g.bg_at(ph["y"]), 0.45))
            if random.random() < 0.06:
                self.g.fx.spawn(ph["x"], ph["y"], random.uniform(-20, 20),
                                random.uniform(-20, 20), "#FFE066", 2.4, 0.6)
            if d < p.size * 1.1 + 12:
                self._collect(ph)
                if self.got >= self.target:
                    return

        for s in self.sludge:
            s["ph"] += dt * 2
            s["vx"] += random.uniform(-35, 35) * dt
            s["vy"] += random.uniform(-35, 35) * dt
            sp = math.hypot(s["vx"], s["vy"])
            if sp > 95:
                s["vx"] *= 95 / sp
                s["vy"] *= 95 / sp
            s["x"] += s["vx"] * dt
            s["y"] += s["vy"] * dt
            if s["x"] < 30 or s["x"] > WIDTH - 30:
                s["vx"] *= -1
                s["x"] = clamp(s["x"], 30, WIDTH - 30)
            if s["y"] < 30 or s["y"] > HEIGHT - 30:
                s["vy"] *= -1
                s["y"] = clamp(s["y"], 30, HEIGHT - 30)
            pts = []
            for k in range(7):
                a = math.tau * k / 7
                rr = s["r"] * (1 + 0.22 * math.sin(s["ph"] * 1.6 + k * 1.7))
                pts.append((math.cos(a) * rr, math.sin(a) * rr))
            flat = []
            for lx, ly in pts:
                flat += [s["x"] + lx, s["y"] + ly]
            c.coords(s["core"], *flat)
            R = s["r"] * 1.9
            c.coords(s["halo"], s["x"] - R, s["y"] - R, s["x"] + R, s["y"] + R)
            c.itemconfigure(s["halo"], fill=mix("#9B4DFF", self.g.bg_at(s["y"]), 0.70))
            if random.random() < 0.05:
                self.g.fx.spawn(s["x"], s["y"], random.uniform(-15, 15), -18,
                                "#9B4DFF", 3, 0.8)
            if math.hypot(p.x - s["x"], p.y - s["y"]) < p.size * 0.9 + s["r"]:
                if self.g.damage(1, "Toksyczny kłąb poparzył Mikrobę!"):
                    a = math.atan2(p.y - s["y"], p.x - s["x"])
                    p.vx += math.cos(a) * 340
                    p.vy += math.sin(a) * 340

    def _collect(self, ph):
        if ph not in self.photons:
            return
        c = self.g.canvas
        for k in ("halo", "star", "core"):
            c.delete(ph[k])
        self.photons.remove(ph)
        self.got += 1
        self.g.fx.burst(ph["x"], ph["y"], "#FFE066", 18, 210, 4, 0.55)
        self.g.fx.ring(ph["x"], ph["y"], "#FFF6C2", 8, 46, 0.4, 3)
        self.g.add_score(120, ph["x"], ph["y"], combo=True)
        self.g.cmd("photosynthesis.absorb(%d/%d)" % (self.got, self.target))
        self._obj()
        if self.got >= self.target:
            self.g.finish_sector()
        elif len(self.photons) < 5:
            self._spawn_photon()

    def cleanup(self):
        c = self.g.canvas
        for ph in self.photons:
            for k in ("halo", "star", "core"):
                c.delete(ph[k])
        for s in self.sludge:
            c.delete(s["halo"])
            c.delete(s["core"])
        self.photons, self.sludge = [], []

    def hint(self):
        return "Zbieraj światło — konsola w tym sektorze jest wyłączona."


# ------------------------------ SEKTOR 2 -----------------------------------
class SortSector(Sector):
    name = "KORPORACJA"
    subtitle = "Zbieraj odpady i wrzucaj do właściwych koszy"
    console = False
    reward = "MINI-REAKTOR  (+szybkość, krótszy cooldown zrywu)"

    BIN_W, BIN_H = 150, 78

    def start(self):
        self.target = 6
        self.done = 0
        self.items = []
        self.carried = None
        self.carry_t = 0.0
        self.bins = {}
        self.bin_ids = []
        self._draw_bins()
        for _ in range(4):
            self._spawn_item()
        self.g.say("Podpłyń do odpadu, żeby go CHWYCIĆ, a potem wpłyń w kosz o właściwym kolorze.",
                   "CZERWONY = toksyczne · ŻÓŁTY = metal i plastik · ZIELONY = szkło · NIEBIESKI = papier",
                   C_TXT)
        self._obj()

    def _obj(self):
        if self.carried:
            t = self.carried["type"]
            self.g.objective("%s — %d/%d · NIESIESZ: %s (%s)"
                             % (self.head, self.done, self.target, t, GARBAGE_TYPES[t]["pl"]))
        else:
            self.g.objective("%s — POSORTOWANE %d/%d"
                             % (self.head, self.done, self.target))

    # -- kosze ------------------------------------------------------------
    def _draw_bins(self):
        c = self.g.canvas
        n = len(BIN_ORDER)
        w, h = self.BIN_W, self.BIN_H
        gap = (WIDTH - n * w) / (n + 1)
        for i, col in enumerate(BIN_ORDER):
            x = gap + i * (w + gap)
            y = HEIGHT - 150
            k = COLOR_MAP[col]
            body = c.create_polygon(x + 12, y, x + w - 12, y, x + w - 24, y + h, x + 24, y + h,
                                    fill=mix(k, DEEP, 0.76), outline=k, width=2)
            lid = c.create_rectangle(x + 2, y - 14, x + w - 2, y, fill=mix(k, DEEP, 0.5),
                                     outline=k, width=2)
            mouth = c.create_oval(x + 22, y - 10, x + w - 22, y + 10,
                                  fill=mix(DEEP, "#000000", 0.4), outline=mix(k, DEEP, 0.3))
            lab = c.create_text(x + w / 2, y + 30, text=BIN_LABEL[col], fill=k, font=self.g.f_tiny)
            key = c.create_text(x + w / 2, y + 52, text=col, fill=mix(k, "#FFFFFF", 0.45),
                                font=self.g.f_small)
            for it in (body, lid, mouth, lab, key):
                self.g.to_layer(it, "L_FG")
            self.bin_ids += [body, lid, mouth, lab, key]
            self.bins[col] = {"x": x, "y": y, "w": w, "h": h, "cx": x + w / 2, "cy": y + 26,
                              "body": body, "lid": lid, "col": k}

    # -- odpady -----------------------------------------------------------
    def _spawn_item(self):
        c = self.g.canvas
        t = random.choice(list(GARBAGE_TYPES.keys()))
        col = GARBAGE_TYPES[t]["color"]
        shape = GARBAGE_TYPES[t]["shape"]
        ids = [c.create_oval(0, 0, 1, 1, fill=mix(col, self.g.bg_at(HEIGHT * 0.35), 0.92),
                             outline="")]
        if shape == "bottle":
            ids.append(c.create_polygon([0, 0, 1, 1, 2, 2], fill=col, outline=shade(col, 0.7),
                                        width=2, smooth=True))
            ids.append(c.create_rectangle(0, 0, 1, 1, fill=shade(col, 0.8), outline=""))
        elif shape == "can":
            ids.append(c.create_rectangle(0, 0, 1, 1, fill=col, outline=shade(col, 0.6), width=2))
            ids.append(c.create_oval(0, 0, 1, 1, fill=shade(col, 1.25), outline=""))
        elif shape == "box":
            ids.append(c.create_rectangle(0, 0, 1, 1, fill=col, outline=shade(col, 0.6), width=2))
            ids.append(c.create_line(0, 0, 1, 1, fill=shade(col, 0.65), width=3))
        else:
            ids.append(c.create_oval(0, 0, 1, 1, fill=col, outline="#FFD84A", width=2))
            ids.append(c.create_line(0, 0, 1, 1, fill="#FFD84A", width=2))
        label = c.create_text(0, 0, text=t, fill="#08131C", font=self.g.f_tiny)
        ids.append(label)
        for i in ids:
            self.g.to_layer(i, "L_WORLD")
        x = random.uniform(90, WIDTH - 90)
        y = random.uniform(95, HEIGHT - 250)
        a = random.uniform(0, math.tau)
        it = {"type": t, "ids": ids, "label": label, "x": x, "y": y,
              "vx": math.cos(a) * 34, "vy": math.sin(a) * 34, "ph": random.uniform(0, 6),
              "shape": shape}
        self.items.append(it)
        self.g.fx.ring(x, y, mix(col, DEEP, 0.3), 6, 44, 0.5, 2)
        return it

    def _place(self, it, x, y, scale=1.0):
        c = self.g.canvas
        s = 30 * scale
        sh = it["shape"]
        c.coords(it["ids"][0], x - s * 1.18, y - s * 1.18, x + s * 1.18, y + s * 1.18)
        if sh == "bottle":
            c.coords(it["ids"][1], x - s * .5, y - s * .5, x + s * .5, y - s * .5,
                     x + s * .55, y + s * .8, x - s * .55, y + s * .8)
            c.coords(it["ids"][2], x - s * .2, y - s * .95, x + s * .2, y - s * .45)
        elif sh == "can":
            c.coords(it["ids"][1], x - s * .45, y - s * .7, x + s * .45, y + s * .8)
            c.coords(it["ids"][2], x - s * .45, y - s * .85, x + s * .45, y - s * .55)
        elif sh == "box":
            c.coords(it["ids"][1], x - s * .65, y - s * .6, x + s * .65, y + s * .7)
            c.coords(it["ids"][2], x - s * .65, y + s * .05, x + s * .65, y + s * .05)
        else:
            c.coords(it["ids"][1], x - s * .6, y - s * .85, x + s * .6, y + s * .85)
            c.coords(it["ids"][2], x - s * .58, y, x + s * .58, y)
        c.coords(it["label"], x, y + s * 1.25)

    def _drop_ids(self, it):
        for i in it["ids"]:
            self.g.canvas.delete(i)

    # -- logika -----------------------------------------------------------
    def update(self, dt):
        p = self.g.player
        c = self.g.canvas

        for it in self.items:
            it["ph"] += dt * 2
            it["vx"] += random.uniform(-30, 30) * dt
            it["vy"] += random.uniform(-30, 30) * dt
            sp = math.hypot(it["vx"], it["vy"])
            if sp > 60:
                it["vx"] *= 60 / sp
                it["vy"] *= 60 / sp
            it["x"] += it["vx"] * dt
            it["y"] += it["vy"] * dt
            if it["x"] < 60 or it["x"] > WIDTH - 60:
                it["vx"] *= -1
                it["x"] = clamp(it["x"], 60, WIDTH - 60)
            if it["y"] < 80 or it["y"] > HEIGHT - 210:
                it["vy"] *= -1
                it["y"] = clamp(it["y"], 80, HEIGHT - 210)
            self._place(it, it["x"], it["y"] + math.sin(it["ph"]) * 4)

        # chwytanie
        if self.carried is None:
            for it in self.items:
                if math.hypot(p.x - it["x"], p.y - it["y"]) < p.size * 1.0 + 30:
                    self.items.remove(it)
                    self.carried = it
                    self.carry_t = 0.0
                    self.g.fx.ring(it["x"], it["y"], "#FFFFFF", 10, 54, 0.35, 2)
                    self.g.fx.burst(it["x"], it["y"], GARBAGE_TYPES[it["type"]]["color"],
                                    10, 140, 3, 0.4)
                    self.g.cmd("grab(%s)" % it["type"])
                    self.g.say("🫳 CHWYCONO: %s (%s)" % (it["type"], GARBAGE_TYPES[it["type"]]["pl"]),
                               "Wpłyń w kosz o właściwym kolorze, żeby go wyrzucić.", C_OK)
                    self._obj()
                    break
        else:
            it = self.carried
            self.carry_t += dt
            tx, ty = p.x, p.y - p.size * 1.9
            it["x"] += (tx - it["x"]) * min(1, dt * 12)
            it["y"] += (ty - it["y"]) * min(1, dt * 12)
            self._place(it, it["x"], it["y"], 0.85)
            if random.random() < 0.15:
                self.g.fx.spawn(it["x"], it["y"], random.uniform(-20, 20), 20,
                                GARBAGE_TYPES[it["type"]]["color"], 2.4, 0.5)
            want = GARBAGE_TYPES[it["type"]]["bin"]
            # podpowiedz po 5 s niesienia
            for col, b in self.bins.items():
                if col == want and self.carry_t > 5.0:
                    k = 0.5 + 0.5 * math.sin(self.g.t * 6)
                    c.itemconfigure(b["body"], fill=mix(b["col"], DEEP, 0.76 - 0.35 * k))
                else:
                    c.itemconfigure(b["body"], fill=mix(b["col"], DEEP, 0.76))
            for col, b in self.bins.items():
                if (b["x"] - 6 < p.x < b["x"] + b["w"] + 6
                        and b["y"] - 26 < p.y < b["y"] + b["h"]):
                    self._deposit(col)
                    break

    def _deposit(self, col):
        it = self.carried
        want = GARBAGE_TYPES[it["type"]]["bin"]
        b = self.bins[col]
        if col == want:
            self.carried = None
            self.done += 1
            self._drop_ids(it)
            self.g.fx.burst(b["cx"], b["cy"], COLOR_MAP[col], 24, 260, 4, 0.6)
            self.g.fx.ring(b["cx"], b["cy"], COLOR_MAP[col], 8, 90, 0.5, 4)
            bonus = int(max(0, 240 - self.carry_t * 20))
            self.g.add_score(200 + bonus, b["cx"], b["cy"] - 30, combo=True, label="POSORTOWANE")
            self.g.cmd("sort(%s → %s)  ✔" % (it["type"], col))
            self.g.say("✅ %s trafił do kosza %s. (+%d pkt)" % (it["type"], col, 200 + bonus),
                       "Zebrano %d z %d. Płyń po kolejny odpad!" % (self.done, self.target), C_OK)
            self._obj()
            if self.done >= self.target:
                self.g.finish_sector()
            else:
                self.g.later(400, self._spawn_item)
        else:
            self.carried = None
            it["x"], it["y"] = b["cx"], b["y"] - 60
            it["vx"] = random.uniform(-80, 80)
            it["vy"] = -110
            self.items.append(it)
            self.g.break_combo()
            self.g.shake(9)
            self.g.fx.ring(b["cx"], b["cy"], C_BAD, 8, 80, 0.45, 3)
            self.g.cmd("sort(%s → %s)  ✘ BŁĄD" % (it["type"], col))
            self.g.say("❌ %s nie należy do kosza %s!" % (it["type"], col),
                       "%s to %s → kosz %s. Odpad wrócił do wody."
                       % (it["type"], GARBAGE_TYPES[it["type"]]["pl"], want), C_BAD)
            self._obj()

    def cleanup(self):
        for it in self.items:
            self._drop_ids(it)
        if self.carried:
            self._drop_ids(self.carried)
        self.items, self.carried = [], None
        for i in self.bin_ids:
            self.g.canvas.delete(i)
        self.bin_ids = []

    def hint(self):
        if self.carried:
            t = self.carried["type"]
            if self.carry_t > 5.0:
                return "Właściwy kosz pulsuje — wpłyń w niego"
            return "Niesiesz %s (%s) — wybierz kosz" % (t, GARBAGE_TYPES[t]["pl"])
        return "Podpłyń do odpadu, aby go chwycić"


class RhythmSector(Sector):
    name = "LAS WODOROSTÓW"
    subtitle = "Trafiaj w pulsujące węzły energii"
    console = False
    reward = "ANTENA SENSORYCZNA  (magnes na fotony + podpowiedzi)"

    def start(self):
        self.target = 9
        self.got = 0
        self.perfect = 0
        self.node = None
        self.cool = 0.7
        self.dur = 1.9
        self.g.say("Węzły energii zapalają się w losowych miejscach — kurczący się pierścień odlicza czas.",
                   "Bądź W ŚRODKU węzła w chwili domknięcia pierścienia. Środek = trafienie IDEALNE.",
                   C_TXT)
        self._obj()

    def _obj(self):
        self.g.objective("%s — ENERGIA %d/%d · IDEALNE %d"
                         % (self.head, self.got, self.target, self.perfect))

    def _spawn(self):
        c = self.g.canvas
        p = self.g.player
        for _ in range(24):
            x = random.uniform(120, WIDTH - 120)
            y = random.uniform(110, HEIGHT - 80)
            if math.hypot(x - p.x, y - p.y) > 180:
                break
        col = self.g.pal["acc"]
        halo = c.create_oval(x - 62, y - 62, x + 62, y + 62,
                             fill=mix(col, self.g.bg_at(y), 0.80), outline="")
        outer = c.create_oval(x - 58, y - 58, x + 58, y + 58,
                              outline=mix(col, DEEP, 0.62), width=2)
        core = c.create_oval(x - 30, y - 30, x + 30, y + 30,
                             outline=mix(col, DEEP, 0.25), width=3)
        ring = c.create_oval(x - 86, y - 86, x + 86, y + 86, outline=col, width=4)
        for i in (halo, outer, core, ring):
            self.g.to_layer(i, "L_WORLD")
        self.node = {"x": x, "y": y, "t": 0.0, "ids": [halo, outer, core, ring],
                     "ring": ring, "col": col}

    def _kill(self):
        if self.node:
            for i in self.node["ids"]:
                self.g.canvas.delete(i)
            self.node = None

    def update(self, dt):
        p = self.g.player
        if self.node is None:
            self.cool -= dt
            if self.cool <= 0:
                self._spawn()
            return
        n = self.node
        n["t"] += dt
        k = min(1.0, n["t"] / self.dur)
        r = lerp(86, 26, k)
        self.g.canvas.coords(n["ring"], n["x"] - r, n["y"] - r, n["x"] + r, n["y"] + r)
        if random.random() < 0.25:
            a = random.uniform(0, math.tau)
            self.g.fx.spawn(n["x"] + math.cos(a) * r, n["y"] + math.sin(a) * r,
                            0, 0, n["col"], 2.6, 0.35)
        if k >= 1.0:
            d = math.hypot(p.x - n["x"], p.y - n["y"])
            x, y = n["x"], n["y"]
            self._kill()
            if d <= 32:
                self.got += 1
                self.perfect += 1
                self.g.add_score(420, x, y, combo=True, label="IDEALNIE!")
                self.g.fx.burst(x, y, "#FFFFFF", 28, 320, 4, 0.65)
                self.g.fx.ring(x, y, "#FFFFFF", 20, 130, 0.55, 4)
                self.g.cmd("absorb(photon, PERFECT)")
                self.g.say("⚡ IDEALNIE! Rytm fotosyntezy przyspiesza.", "", C_OK)
            elif d <= 62:
                self.got += 1
                self.g.add_score(160, x, y, combo=True, label="OK")
                self.g.fx.burst(x, y, self.g.pal["acc"], 16, 210, 3, 0.5)
                self.g.cmd("absorb(photon, OK)")
                self.g.say("✅ Energia wchłonięta — ale celuj bliżej środka.", "", C_TXT)
            else:
                self.g.break_combo()
                self.g.fx.ring(x, y, C_BAD, 24, 70, 0.4, 3)
                self.g.cmd("absorb(photon)  ✘ MISS")
                self.g.say("❌ Węzeł zgasł, zanim dopłynęłaś.",
                           "Ruszaj w stronę węzła od razu, gdy się pojawi.", C_BAD)
            self.dur = max(1.05, self.dur - 0.08)
            self.cool = 0.45
            self._obj()
            if self.got >= self.target:
                self.g.finish_sector()

    def cleanup(self):
        self._kill()

    def hint(self):
        return "Bądź w środku węzła, gdy pierścień się domknie"


class SequenceSector(Sector):
    name = "STREFA MARTWA"
    subtitle = "Odtwórz kod cyklu życia"
    console = False
    enemies = False
    reward = "BŁONA REGENERACYJNA  (+1 maksymalne życie, pełna regeneracja)"

    def start(self):
        self.round = 0
        self.rounds = 3
        self.seq = []
        self.player_seq = []
        self.state = "wait"
        self.timer = 1.0
        self.flash_i = 0
        self.flash_t = 0.0
        self.pads = {}
        self.in_pad = None
        self._draw_pads()
        self.g.say("Zapamiętaj kolejność zapalanych pól, a potem WPŁYWAJ w nie w tej samej kolejności.",
                   "Możesz też kliknąć pole myszką. Pole liczy się raz — wypłyń i wróć, by je powtórzyć.",
                   C_TXT)
        self._obj()

    def _obj(self):
        self.g.objective("%s — RUNDA %d/%d · DŁUGOŚĆ %d"
                         % (self.head, min(self.round + 1, self.rounds), self.rounds, 3 + self.round))

    def _draw_pads(self):
        c = self.g.canvas
        cx, cy = WIDTH / 2, HEIGHT / 2 - 10
        size, gap = 132, 18
        pos = {"RED": (-1, -1), "GREEN": (0, -1), "BLUE": (-1, 0), "YELLOW": (0, 0)}
        self.pad_ids = []
        for i, (name, (gx, gy)) in enumerate(pos.items()):
            x = cx + gx * (size + gap) + gap / 2
            y = cy + gy * (size + gap) + gap / 2
            col = COLOR_MAP[name]
            box = c.create_rectangle(x, y, x + size, y + size, fill=mix(col, DEEP, 0.86),
                                     outline=mix(col, DEEP, 0.35), width=3)
            inner = c.create_oval(x + 26, y + 26, x + size - 26, y + size - 26,
                                  fill=mix(col, DEEP, 0.78), outline="")
            key = c.create_text(x + size / 2, y + size / 2 + 4, text=str(i + 1),
                                fill=mix(col, "#FFFFFF", 0.5), font=self.g.f_big)
            lab = c.create_text(x + size / 2, y + size - 16, text=COLOR_PL[name],
                                fill=mix(col, DEEP, 0.25), font=self.g.f_tiny)
            for it in (box, inner, key, lab):
                self.g.to_layer(it, "L_WORLD")
            self.pad_ids += [box, inner, key, lab]
            self.pads[name] = {"box": box, "inner": inner, "cx": x + size / 2, "cy": y + size / 2,
                               "x": x, "y": y, "s": size, "col": col, "on": 0.0}

    def _light(self, name, strong=True):
        p = self.pads[name]
        p["on"] = 0.35
        self.g.fx.ring(p["cx"], p["cy"], p["col"], 30, 96, 0.45, 3)
        if strong:
            self.g.fx.burst(p["cx"], p["cy"], p["col"], 10, 150, 3, 0.4)

    def _begin_round(self):
        self.seq = [random.choice(SEQUENCE_COLORS) for _ in range(3 + self.round)]
        self.player_seq = []
        self.state = "show"
        self.flash_i = 0
        self.flash_t = 0.0
        self._obj()
        self.g.say("▶ Uwaga — emisja wzorca (%d sygnałów)..." % len(self.seq),
                   "Patrz uważnie na kolejność zapalanych pól.", C_WARN)

    def update(self, dt):
        for name, p in self.pads.items():
            if p["on"] > 0:
                p["on"] = max(0.0, p["on"] - dt)
                k = p["on"] / 0.35
                self.g.canvas.itemconfigure(p["box"], fill=mix(p["col"], DEEP, 0.86 - 0.6 * k))
                self.g.canvas.itemconfigure(p["inner"], fill=mix(p["col"], DEEP, 0.78 - 0.75 * k))

        p = self.g.player
        here = None
        for name, pd in self.pads.items():
            if pd["x"] <= p.x <= pd["x"] + pd["s"] and pd["y"] <= p.y <= pd["y"] + pd["s"]:
                here = name
                break
        if here != self.in_pad:
            self.in_pad = here
            if here and self.state == "input":
                self._input(here)

        if self.state == "wait":
            self.timer -= dt
            if self.timer <= 0:
                self._begin_round()
        elif self.state == "show":
            self.flash_t -= dt
            if self.flash_t <= 0:
                if self.flash_i < len(self.seq):
                    self._light(self.seq[self.flash_i])
                    self.flash_i += 1
                    self.flash_t = 0.52
                else:
                    self.state = "input"
                    self.in_pad = None
                    self.g.say("⬜ TWÓJ RUCH — wpłyń kolejno w %d pola w zapamiętanej kolejności." % len(self.seq),
                               "CZERWONY · ZIELONY · NIEBIESKI · ŻÓŁTY — kolejność ma znaczenie.", C_TXT)

    def _input(self, name):
        if self.state != "input":
            return
        self._light(name, False)
        self.player_seq.append(name)
        i = len(self.player_seq) - 1
        if self.seq[i] != name:
            self.state = "wait"
            self.timer = 1.1
            self.g.break_combo()
            self.g.shake(9)
            self.g.say("❌ Wzorzec przerwany na pozycji %d." % (i + 1),
                       "Runda powtórzona od początku.", C_BAD)
            return
        if len(self.player_seq) == len(self.seq):
            self.round += 1
            self.g.add_score(500 + 200 * self.round, WIDTH / 2, HEIGHT / 2 - 120,
                             combo=True, label="WZORZEC OK")
            self.g.cmd("lifecycle.verify(%s)  ✔" % "-".join(self.seq))
            self.g.fx.ring(WIDTH / 2, HEIGHT / 2 - 10, C_OK, 40, 300, 0.7, 4)
            if self.round >= self.rounds:
                self.g.finish_sector()
            else:
                self.state = "wait"
                self.timer = 1.2
                self.g.say("✅ Runda zaliczona. Kod cyklu życia stabilizuje się...",
                           "Kolejna sekwencja będzie dłuższa.", C_OK)

    def on_key(self, key):
        if key in "1234":
            self._input(SEQUENCE_COLORS[int(key) - 1])


    def on_click(self, x, y):
        for name, p in self.pads.items():
            if p["x"] <= x <= p["x"] + p["s"] and p["y"] <= y <= p["y"] + p["s"]:
                self._input(name)
                return

    def cleanup(self):
        for i in self.pad_ids:
            self.g.canvas.delete(i)
        self.pad_ids = []

    def hint(self):
        if self.state == "input":
            return "Wpływaj w pola w zapamiętanej kolejności"
        return "Zapamiętaj kolejność zapalanych pól"


# ------------------------------ SEKTOR 5 -----------------------------------
class ChemSector(Sector):
    name = "SKŁADOWISKO"
    subtitle = "Przywróć równowagę pH"
    console = False
    reward = "STABILIZATOR pH  (większy zasięg fali neutralizującej)"

    MAX_CH = 3

    def start(self):
        self.toxins = []
        self.caps = []
        self.charges = 0
        self.start_n = 10
        self.spawn_t = 8.0
        for _ in range(self.start_n):
            self._spawn_toxin()
        for _ in range(3):
            self._spawn_cap()
        self._draw_bar()
        self.g.say("Zbieraj zielone KAPSUŁY ZASADOWE (ALKA), a potem wpływaj w toksyny, aby je neutralizować.",
                   "Bez ładunku dotknięcie toksyny rani Mikrobę! Jedna kapsuła = jedna fala neutralizująca.",
                   C_TXT)
        self._obj()

    def _obj(self):
        dots = "●" * self.charges + "○" * (self.MAX_CH - self.charges)
        self.g.objective("%s — TOKSYNY %d · ALKA %s"
                         % (self.head, len(self.toxins), dots))

    def _radius(self):
        return 170 if self.g.upgrades >= 5 else 135

    def _draw_bar(self):
        c = self.g.canvas
        x0, x1 = WIDTH - 62, WIDTH - 34
        y0, y1 = 96, HEIGHT - 130
        self.bar_bg = c.create_rectangle(x0, y0, x1, y1, fill=mix(DEEP, "#FFFFFF", 0.06),
                                         outline=mix(C_TXT, DEEP, 0.6), width=2)
        self.bar_fill = c.create_rectangle(x0 + 3, y0, x1 - 3, y1, fill=C_BAD, outline="")
        self.bar_lab = c.create_text((x0 + x1) / 2, y0 - 16, text="pH", fill=C_TXT,
                                     font=self.g.f_tiny)
        self.bar_val = c.create_text((x0 + x1) / 2, y1 + 16, text="", fill=C_TXT,
                                     font=self.g.f_tiny)
        for i in (self.bar_bg, self.bar_fill, self.bar_lab, self.bar_val):
            self.g.to_layer(i, "L_WORLD")
        self.g.canvas.tag_raise(self.bar_fill)

    def _spawn_toxin(self):
        c = self.g.canvas
        for _ in range(24):
            x = random.uniform(60, WIDTH - 110)
            y = random.uniform(80, HEIGHT - 60)
            if math.hypot(x - self.g.player.x, y - self.g.player.y) > 170:
                break
        halo = c.create_oval(0, 0, 1, 1, fill=glow_of("#FF5FA2", 0.72), outline="")
        core = c.create_polygon([0, 0, 1, 1, 2, 2], fill="#C4185F", outline="#FF8FC0",
                                width=2, smooth=True)
        self.g.to_layer(halo, "L_WORLD")
        self.g.to_layer(core, "L_WORLD")
        self.toxins.append({"x": x, "y": y, "halo": halo, "core": core,
                            "ph": random.uniform(0, 6), "r": random.uniform(11, 16)})

    def _spawn_cap(self):
        c = self.g.canvas
        x = random.uniform(70, WIDTH - 120)
        y = random.uniform(90, HEIGHT - 70)
        halo = c.create_oval(0, 0, 1, 1, fill=mix("#4FFFC4", self.g.bg_at(y), 0.68), outline="")
        core = c.create_oval(0, 0, 1, 1, fill="#DFFFF4", outline="#4FFFC4", width=3)
        mark = c.create_text(x, y, text="A", fill="#0B3B30", font=self.g.f_small)
        orb = [c.create_oval(0, 0, 1, 1, fill="#DFFFF4", outline="") for _ in range(2)]
        for i in [halo, core, mark] + orb:
            self.g.to_layer(i, "L_WORLD")
        self.caps.append({"x": x, "y": y, "halo": halo, "core": core, "mark": mark,
                          "orb": orb, "ph": random.uniform(0, 6)})
        self.g.fx.ring(x, y, "#4FFFC4", 6, 46, 0.5, 2)

    def _del_cap(self, cp):
        for k in ("halo", "core", "mark"):
            self.g.canvas.delete(cp[k])
        for ob in cp["orb"]:
            self.g.canvas.delete(ob)
        self.caps.remove(cp)

    def update(self, dt):
        c = self.g.canvas
        p = self.g.player

        # kapsuly ALKA
        for cp in self.caps[:]:
            cp["ph"] += dt * 3
            r = 13 + math.sin(cp["ph"]) * 2
            c.coords(cp["core"], cp["x"] - r, cp["y"] - r, cp["x"] + r, cp["y"] + r)
            R = r * 2.1
            c.coords(cp["halo"], cp["x"] - R, cp["y"] - R, cp["x"] + R, cp["y"] + R)
            c.itemconfigure(cp["halo"], fill=mix("#4FFFC4", self.g.bg_at(cp["y"]), 0.68))
            for oi, ob in enumerate(cp["orb"]):
                oa = cp["ph"] * 1.6 + oi * math.pi
                ox = cp["x"] + math.cos(oa) * (r + 9)
                oy = cp["y"] + math.sin(oa) * (r + 9) * 0.55
                c.coords(ob, ox - 2.6, oy - 2.6, ox + 2.6, oy + 2.6)
            if random.random() < 0.05:
                self.g.fx.spawn(cp["x"], cp["y"], random.uniform(-18, 18), -20,
                                "#4FFFC4", 2.4, 0.6)
            if math.hypot(p.x - cp["x"], p.y - cp["y"]) < p.size + 18:
                self._del_cap(cp)
                if self.charges < self.MAX_CH:
                    self.charges += 1
                self.g.add_score(80, p.x, p.y - 40, combo=False, label="+ALKA")
                self.g.fx.ring(p.x, p.y, "#4FFFC4", 10, 60, 0.4, 3)
                self.g.cmd("load(ALKA)  [%d/%d]" % (self.charges, self.MAX_CH))
                self.g.say("🧪 Kapsuła zasadowa pobrana (%d/%d)." % (self.charges, self.MAX_CH),
                           "Wpłyń teraz w skupisko toksyn — fala zneutralizuje wszystkie w zasięgu.",
                           C_OK)
                self._obj()
                self.g.later(2600, self._spawn_cap)

        # toksyny
        for t in self.toxins[:]:
            t["ph"] += dt * 2.4
            dx, dy = p.x - t["x"], p.y - t["y"]
            d = math.hypot(dx, dy) + 0.001
            sp = 26 if d > 90 else 46
            t["x"] += dx / d * sp * dt
            t["y"] += dy / d * sp * dt
            t["x"] += math.sin(t["ph"] * 1.3) * 18 * dt
            t["y"] += math.cos(t["ph"] * 1.1) * 18 * dt
            pts = []
            for k in range(8):
                a = math.tau * k / 8
                rr = t["r"] * (1 + 0.25 * math.sin(t["ph"] * 2 + k))
                pts += [t["x"] + math.cos(a) * rr, t["y"] + math.sin(a) * rr]
            c.coords(t["core"], *pts)
            R = t["r"] * 1.95
            c.coords(t["halo"], t["x"] - R, t["y"] - R, t["x"] + R, t["y"] + R)
            c.itemconfigure(t["halo"], fill=mix("#FF5FA2", self.g.bg_at(t["y"]), 0.72))
            if random.random() < 0.04:
                self.g.fx.spawn(t["x"], t["y"], random.uniform(-20, 20), -25, "#FF5FA2", 2.5, 0.7)
            if d < p.size * 0.9 + t["r"]:
                if self.charges > 0:
                    self._neutralize()
                    break
                elif self.g.damage(1, "Żrąca toksyna! Potrzebujesz kapsuły ALKA."):
                    a = math.atan2(p.y - t["y"], p.x - t["x"])
                    p.vx += math.cos(a) * 320
                    p.vy += math.sin(a) * 320

        # wyciek
        self.spawn_t -= dt
        if self.spawn_t <= 0 and self.toxins:
            self.spawn_t = 9.0
            self._spawn_toxin()
            self.g.fx.text(WIDTH / 2, 120, "WYCIEK! +1 TOKSYNA", C_BAD, 1.0)
            self._obj()

        # pasek pH
        k = clamp(len(self.toxins) / float(self.start_n), 0, 1)
        y0, y1 = 96, HEIGHT - 130
        yy = lerp(y1, y0, k)
        col = C_BAD if k > 0.55 else (C_WARN if k > 0.2 else C_OK)
        c.coords(self.bar_fill, WIDTH - 59, yy, WIDTH - 37, y1)
        c.itemconfigure(self.bar_fill, fill=col)
        c.itemconfigure(self.bar_val, text="%d" % len(self.toxins))

    def _neutralize(self):
        p = self.g.player
        self.charges -= 1
        R = self._radius()
        self.g.fx.ring(p.x, p.y, C_OK, 12, R, 0.5, 5)
        self.g.fx.ring(p.x, p.y, "#FFFFFF", 10, R * 0.65, 0.35, 3)
        self.g.fx.burst(p.x, p.y, C_OK, 20, 260, 4, 0.55)
        self.g.shake(5)
        hit = 0
        for t in self.toxins[:]:
            if math.hypot(t["x"] - p.x, t["y"] - p.y) <= R:
                self.g.canvas.delete(t["halo"])
                self.g.canvas.delete(t["core"])
                self.toxins.remove(t)
                self.g.fx.burst(t["x"], t["y"], "#7CFFE8", 12, 190, 3, 0.5)
                hit += 1
        self.g.add_score(150 * hit, p.x, p.y - 40, combo=True, label="NEUTRALIZACJA x%d" % hit)
        self.g.cmd("neutralize(pH, r=%d) → -%d" % (R, hit))
        self.g.say("✅ Fala zasadowa rozbiła %d toksyn. Pozostało: %d." % (hit, len(self.toxins)),
                   "Ładunki ALKA: %d/%d — zbierz kolejne kapsuły." % (self.charges, self.MAX_CH),
                   C_OK)
        self._obj()
        if not self.toxins:
            self.g.finish_sector()

    def cleanup(self):
        c = self.g.canvas
        for t in self.toxins:
            c.delete(t["halo"])
            c.delete(t["core"])
        self.toxins = []
        for cp in self.caps[:]:
            self._del_cap(cp)
        for i in (self.bar_bg, self.bar_fill, self.bar_lab, self.bar_val):
            c.delete(i)

    def hint(self):
        if self.charges:
            return "Wpłyń w toksyny — masz %d ładunek(i) ALKA" % self.charges
        return "Zbierz zieloną kapsułę ALKA"


# ------------------------------ SEKTOR: SIECI WIDMA ------------------------
class NetsSector(Sector):
    name = "SIECI WIDMA"
    subtitle = "Uwolnij ryby z porzuconych sieci"
    console = False

    HOLD = 1.8

    def start(self):
        self.target = 5
        self.freed = 0
        self.nets = []
        for _ in range(3):
            self._spawn_net()
        self.g.say("Porzucone sieci wciąż łowią. Wpłyń w sieć i UTRZYMAJ POZYCJĘ, aż pierścień się domknie.",
                   "Wypłynięcie cofa postęp. Każda sieć ma swój czas — potem ryba w niej ginie.", C_TXT)
        self._obj()

    def _obj(self):
        self.g.objective("%s — UWOLNIONE %d/%d" % (self.head, self.freed, self.target))

    def _spawn_net(self):
        c = self.g.canvas
        p = self.g.player
        for _ in range(24):
            x = random.uniform(110, WIDTH - 110)
            y = random.uniform(110, HEIGHT - 110)
            ok = math.hypot(x - p.x, y - p.y) > 190
            for n in self.nets:
                if math.hypot(x - n["x"], y - n["y"]) < 190:
                    ok = False
            if ok:
                break
        R = 58
        ids = []
        mesh = "#93A6B3"
        rope, mesh_lines = [], []
        for k in range(-3, 4):
            h = c.create_line(0, 0, 1, 1, fill=mesh, width=1, smooth=True)
            v = c.create_line(0, 0, 1, 1, fill=mesh, width=1, smooth=True)
            mesh_lines.append(("h", k * 19, h))
            mesh_lines.append(("v", k * 19, v))
            ids += [h, v]
        ring = c.create_oval(x - R, y - R, x + R, y + R, outline=mix(mesh, DEEP, 0.35), width=3)
        ids.append(ring)
        knots = []
        for k in range(8):
            a = math.tau * k / 8
            kn = c.create_oval(0, 0, 1, 1, fill=mix("#C8D6DE", DEEP, 0.25), outline="")
            knots.append((a, kn))
            ids.append(kn)
        buoy = c.create_oval(x - 12, y - R - 26, x + 12, y - R - 4, fill="#E8552F",
                             outline="#FFD3C4", width=2)
        buoy2 = c.create_line(x, y - R - 4, x, y - R + 6, fill="#C8D6DE", width=2)
        ids += [buoy, buoy2]
        fish = make_tang(self.g)
        ids += fish["ids"]
        arc = c.create_arc(x - R - 11, y - R - 11, x + R + 11, y + R + 11, start=90, extent=0,
                           style="arc", outline=C_OK, width=6)
        ids.append(arc)
        for i in ids:
            self.g.to_layer(i, "L_WORLD")
        self.nets.append({"x": x, "y": y, "r": R, "ids": ids, "arc": arc, "hold": 0.0,
                          "life": 26.0, "fish": fish, "mesh": mesh_lines, "knots": knots,
                          "buoy": (buoy, buoy2), "ph": random.uniform(0, 6)})

    def _del_net(self, n):
        for i in n["ids"]:
            self.g.canvas.delete(i)
        if n in self.nets:
            self.nets.remove(n)

    def update(self, dt):
        c = self.g.canvas
        p = self.g.player
        for n in self.nets[:]:
            n["ph"] += dt * 3
            n["life"] -= dt
            x, y, R = n["x"], n["y"], n["r"]
            for kind, off, ln in n["mesh"]:
                span = R - abs(off) * 0.42
                pts = []
                for j in range(5):
                    f = -1 + 2.0 * j / 4.0
                    wob = math.sin(n["ph"] * 1.4 + f * 2.5 + off * 0.05) * 3.0
                    if kind == "h":
                        pts += [x + span * f, y + off + wob]
                    else:
                        pts += [x + off + wob, y + span * f]
                c.coords(ln, *pts)
            for a, kn in n["knots"]:
                kx = x + math.cos(a + math.sin(n["ph"] * 0.7) * 0.05) * R
                ky = y + math.sin(a + math.sin(n["ph"] * 0.7) * 0.05) * R
                c.coords(kn, kx - 3.5, ky - 3.5, kx + 3.5, ky + 3.5)
            wig = math.sin(n["ph"] * 2.2) * 0.55
            draw_tang(self.g, n["fish"], x + math.sin(n["ph"]) * 5, y + math.cos(n["ph"] * 1.3) * 4,
                      24, wig, n["ph"])
            inside = math.hypot(p.x - n["x"], p.y - n["y"]) < n["r"]
            if inside:
                n["hold"] = min(self.HOLD, n["hold"] + dt)
                if random.random() < 0.5:
                    a = random.uniform(0, math.tau)
                    self.g.fx.spawn(n["x"] + math.cos(a) * n["r"], n["y"] + math.sin(a) * n["r"],
                                    0, 0, C_OK, 2.6, 0.35)
            else:
                n["hold"] = max(0.0, n["hold"] - dt * 1.4)
            c.itemconfigure(n["arc"], extent=-359.9 * (n["hold"] / self.HOLD),
                            outline=C_OK if inside else mix(C_OK, DEEP, 0.45))
            if n["life"] < 6:
                blink = int(n["life"] * 4) % 2 == 0
                for kind, off, ln in n["mesh"]:
                    c.itemconfigure(ln, fill=C_BAD if blink else "#93A6B3")
            if n["hold"] >= self.HOLD:
                self._free(n)
            elif n["life"] <= 0:
                self._del_net(n)
                self.g.break_combo()
                self.g.fx.burst(n["x"], n["y"], "#556672", 16, 150, 3, 0.8, grav=200)
                self.g.say("💀 Ryba w sieci nie doczekała pomocy.",
                           "Zaczynaj od sieci, która miga na czerwono.", C_BAD)
                self.g.later(600, self._spawn_net)

    def _free(self, n):
        x, y = n["x"], n["y"]
        self._del_net(n)
        self.freed += 1
        self.g.fx.burst(x, y, "#8FE3FF", 26, 260, 4, 0.7)
        self.g.fx.ring(x, y, C_OK, 12, 120, 0.55, 4)
        self.g.add_score(320, x, y, combo=True, label="UWOLNIONA!")
        self.g.cmd("net.cut(%d/%d)  ✔" % (self.freed, self.target))
        self.g.say("✅ Sieć przecięta — ryba odpływa wolno!",
                   "Uwolnione: %d z %d." % (self.freed, self.target), C_OK)
        self._obj()
        if self.freed >= self.target:
            self.g.finish_sector()
        else:
            self.g.later(500, self._spawn_net)

    def cleanup(self):
        for n in self.nets[:]:
            self._del_net(n)

    def hint(self):
        return "Wpłyń w sieć i nie ruszaj się, aż pierścień się domknie"


# ------------------------------ SEKTOR: PRĄD GŁĘBINOWY ---------------------
class CurrentSector(Sector):
    name = "PRĄD GŁĘBINOWY"
    subtitle = "Przepłyń bramki wbrew prądom"
    console = False
    enemies = False

    def start(self):
        self.gates = []
        self.idx = 0
        self.streams = []
        self.streaks = []
        self._build_streams()
        self._build_gates()
        self.g.say("Silne prądy znoszą Mikrobę. Przepłyń przez 6 bramek W KOLEJNOŚCI (świeci następna).",
                   "Zryw (klik / SPACJA) przebija prąd — używaj go, gdy woda spycha cię w bok.", C_TXT)
        self._obj()

    def _obj(self):
        self.g.objective("%s — BRAMKA %d/%d" % (self.head, self.idx, len(self.gates)))

    def _build_streams(self):
        c = self.g.canvas
        for i in range(3):
            y = 120 + i * ((HEIGHT - 200) / 3.0) + random.uniform(-20, 20)
            h = random.uniform(70, 110)
            fx = random.choice([-1, 1]) * random.uniform(140, 230)
            band = c.create_rectangle(-PAD, y - h / 2, WIDTH + PAD, y + h / 2,
                                      fill="#123", outline="")
            self.g.to_layer(band, "L_MID")
            self.streams.append({"y": y, "h": h, "fx": fx, "band": band})
            for _ in range(11):
                ln = c.create_line(0, 0, 1, 1, fill="#7FD8F0", width=3,
                                   capstyle="round", arrow="last",
                                   arrowshape=(9, 11, 4))
                self.g.to_layer(ln, "L_MID")
                self.streaks.append({"id": ln, "x": random.uniform(0, WIDTH),
                                     "y": y + random.uniform(-h / 2, h / 2),
                                     "v": fx * random.uniform(0.8, 1.3)})

    def _build_gates(self):
        c = self.g.canvas
        n = 6
        for i in range(n):
            x = 140 + i * ((WIDTH - 280) / (n - 1.0))
            y = (200 if i % 2 == 0 else HEIGHT - 190) + random.uniform(-45, 45)
            col = self.g.pal["acc"]
            field = c.create_rectangle(x - 15, y - 52, x + 15, y + 52,
                                       fill=mix(col, DEEP, 0.86), outline="")
            self.g.to_layer(field, "L_WORLD")
            top = c.create_rectangle(x - 13, y - 78, x + 13, y - 50, fill=mix(col, DEEP, 0.5),
                                     outline=col, width=2)
            bot = c.create_rectangle(x - 13, y + 50, x + 13, y + 78, fill=mix(col, DEEP, 0.5),
                                     outline=col, width=2)
            beam = c.create_line(x, y - 52, x, y + 52, fill=mix(col, DEEP, 0.6), width=4,
                                 dash=(9, 7))
            num = c.create_text(x, y - 98, text=str(i + 1), fill=mix(col, DEEP, 0.45),
                                font=self.g.f_big)
            for it in (top, bot, beam, num):
                self.g.to_layer(it, "L_WORLD")
            self.gates.append({"x": x, "y": y, "ids": [field, top, bot, beam, num],
                               "beam": beam, "num": num, "field": field, "done": False})

    def update(self, dt):
        c = self.g.canvas
        p = self.g.player
        for st in self.streaks:
            st["x"] += st["v"] * dt
            if st["x"] < -60:
                st["x"] = WIDTH + 40
            elif st["x"] > WIDTH + 60:
                st["x"] = -40
            ln = 34 if st["v"] > 0 else -34
            c.coords(st["id"], st["x"], st["y"], st["x"] + ln, st["y"])
            c.itemconfigure(st["id"], fill=mix(self.g.bg_at(st["y"]), "#DFF6FF", 0.42))
        for st in self.streams:
            c.itemconfigure(st["band"], fill=mix(self.g.bg_at(st["y"]), "#BFF0FF", 0.055))
        for s in self.streams:
            if abs(p.y - s["y"]) < s["h"] / 2:
                p.vx += s["fx"] * dt * 1.5
                if random.random() < 0.10:
                    self.g.fx.spawn(p.x, p.y, s["fx"] * 0.4, 0,
                                    mix("#BFF0FF", self.g.bg_at(p.y), 0.4), 2.4, 0.4)

        for i, g in enumerate(self.gates):
            col = self.g.pal["acc"]
            if g["done"]:
                c.itemconfigure(g["beam"], fill=mix(C_OK, DEEP, 0.6))
                c.itemconfigure(g["num"], fill=mix(C_OK, DEEP, 0.5))
                c.itemconfigure(g["field"], fill=mix(C_OK, self.g.bg_at(g["y"]), 0.90))
            elif i == self.idx:
                k = 0.5 + 0.5 * math.sin(self.g.t * 6)
                c.itemconfigure(g["field"],
                                fill=mix(col, self.g.bg_at(g["y"]), 0.80 - 0.12 * k))
                if random.random() < 0.30:
                    self.g.fx.spawn(g["x"], g["y"] + random.uniform(-50, 50),
                                    random.uniform(-25, 25), -40, col, 2.6, 0.5)
                c.itemconfigure(g["beam"], fill=mix(col, "#FFFFFF", k * 0.6), width=6)
                c.itemconfigure(g["num"], fill=mix(col, "#FFFFFF", k * 0.5))
                if abs(p.x - g["x"]) < 24 and abs(p.y - g["y"]) < 52:
                    self._pass(g)
            else:
                c.itemconfigure(g["beam"], fill=mix(col, DEEP, 0.72), width=3)
                c.itemconfigure(g["num"], fill=mix(col, DEEP, 0.6))
                c.itemconfigure(g["field"], fill=mix(col, self.g.bg_at(g["y"]), 0.92))

    def _pass(self, g):
        g["done"] = True
        self.idx += 1
        self.g.fx.ring(g["x"], g["y"], self.g.pal["acc"], 20, 110, 0.5, 4)
        self.g.fx.burst(g["x"], g["y"], self.g.pal["acc"], 18, 240, 4, 0.5)
        self.g.add_score(260, g["x"], g["y"] - 60, combo=True, label="BRAMKA %d" % self.idx)
        self.g.cmd("gate.pass(%d/%d)" % (self.idx, len(self.gates)))
        self._obj()
        if self.idx >= len(self.gates):
            self.g.finish_sector()
        else:
            nx = self.gates[self.idx]
            self.g.say("✅ Bramka %d zaliczona." % self.idx,
                       "Następna bramka świeci — uważaj na prądy po drodze.", C_OK)

    def cleanup(self):
        c = self.g.canvas
        for g in self.gates:
            for i in g["ids"]:
                c.delete(i)
        for st in self.streaks:
            c.delete(st["id"])
        for st in self.streams:
            c.delete(st["band"])
        self.gates, self.streaks, self.streams = [], [], []

    def hint(self):
        return "Płyń przez świecącą bramkę nr %d" % (self.idx + 1)


# ------------------------------ SEKTOR: ŁAŃCUCH POKARMOWY ------------------
class FoodChainSector(Sector):
    name = "ŁAŃCUCH POKARMOWY"
    subtitle = "Jedz zgodnie z porządkiem troficznym"
    console = False
    enemies = False

    CHAIN = [("PLANKTON", "#8CFF6B", 11), ("KREWETKA", "#FF9F5A", 15),
             ("BŁAZENEK", "#FF8A2B", 18)]

    def start(self):
        self.target = 9
        self.eaten = 0
        self.step = 0
        self.things = []
        for _ in range(9):
            self._spawn(random.randrange(3))
        for _ in range(3):
            self._spawn(-1)
        self.g.say("Jedz w kolejności łańcucha: PLANKTON → KREWETKA → BŁAZENEK, potem od nowa.",
                   "Zły poziom troficzny psuje łańcuch (combo znika). Meduzy parzą — omijaj je!", C_TXT)
        self._obj()

    def _obj(self):
        need = self.CHAIN[self.step][0]
        self.g.objective("%s — %d/%d · TERAZ ZJEDZ: %s"
                         % (self.head, self.eaten, self.target, need))

    def _spawn(self, tier):
        x = random.uniform(80, WIDTH - 80)
        y = random.uniform(95, HEIGHT - 85)
        if tier < 0:
            d = make_jelly(self.g, "#FF6BD6")
            r = 18
        elif tier == 0:
            d = make_plankton(self.g)
            r = 11
        elif tier == 1:
            d = make_shrimp(self.g)
            r = 15
        else:
            d = make_clownfish(self.g)
            r = 21
        a = random.uniform(0, math.tau)
        self.things.append({"tier": tier, "d": d, "ids": d["ids"], "x": x, "y": y, "r": r,
                            "vx": math.cos(a) * 42, "vy": math.sin(a) * 42,
                            "ang": a, "ph": random.uniform(0, 6)})

    def _kill(self, t):
        for i in t["ids"]:
            self.g.canvas.delete(i)
        if t in self.things:
            self.things.remove(t)

    def update(self, dt):
        p = self.g.player
        for t in self.things[:]:
            t["ph"] += dt * 2.4
            t["vx"] += random.uniform(-40, 40) * dt
            t["vy"] += random.uniform(-40, 40) * dt
            if t["tier"] < 0:
                dx, dy = p.x - t["x"], p.y - t["y"]
                d = math.hypot(dx, dy) + 0.001
                t["vx"] += dx / d * 30 * dt
                t["vy"] += dy / d * 30 * dt
            sp = math.hypot(t["vx"], t["vy"])
            lim = 78 if t["tier"] >= 0 else 52
            if sp > lim:
                t["vx"] *= lim / sp
                t["vy"] *= lim / sp
            t["x"] += t["vx"] * dt
            t["y"] += t["vy"] * dt
            if t["x"] < 45 or t["x"] > WIDTH - 45:
                t["vx"] *= -1
                t["x"] = clamp(t["x"], 45, WIDTH - 45)
            if t["y"] < 75 or t["y"] > HEIGHT - 45:
                t["vy"] *= -1
                t["y"] = clamp(t["y"], 75, HEIGHT - 45)
            if sp > 8:
                want = math.atan2(t["vy"], t["vx"])
                t["ang"] += ang_diff(t["ang"], want) * min(1.0, dt * 4.0)
            x, y = t["x"], t["y"]
            if t["tier"] < 0:
                t["y"] -= 8 * dt
                draw_jelly(self.g, t["d"], x, y, t["r"], t["ph"])
                if random.random() < 0.03:
                    self.g.fx.spawn(x, y + t["r"], random.uniform(-12, 12), 22,
                                    "#FF6BD6", 2.4, 0.7)
            elif t["tier"] == 0:
                draw_plankton(self.g, t["d"], x, y, t["r"], t["ang"], t["ph"])
            elif t["tier"] == 1:
                draw_shrimp(self.g, t["d"], x, y, t["r"], t["ang"], t["ph"])
            else:
                draw_clownfish(self.g, t["d"], x, y, t["r"], t["ang"], t["ph"])
            if math.hypot(p.x - x, p.y - y) < p.size * 0.85 + t["r"]:
                self._touch(t)

    def _touch(self, t):
        p = self.g.player
        if t["tier"] < 0:
            if self.g.damage(1, "Parzące macki meduzy!"):
                a = math.atan2(p.y - t["y"], p.x - t["x"])
                p.vx += math.cos(a) * 330
                p.vy += math.sin(a) * 330
            return
        name, col, _ = self.CHAIN[t["tier"]]
        x, y = t["x"], t["y"]
        if t["tier"] == self.step:
            self._kill(t)
            self.eaten += 1
            self.step = (self.step + 1) % len(self.CHAIN)
            self.g.fx.burst(x, y, col, 18, 220, 4, 0.55)
            self.g.fx.ring(x, y, col, 8, 70, 0.4, 3)
            self.g.add_score(240, x, y, combo=True, label=name)
            self.g.cmd("trophic.eat(%s)  ✔" % name)
            self.g.say("✅ %s zjedzony — łańcuch rośnie." % name,
                       "Teraz: %s" % self.CHAIN[self.step][0], C_OK)
            self._obj()
            self.g.later(700, lambda: self._spawn(random.randrange(3)))
            if self.eaten >= self.target:
                self.g.finish_sector()
        else:
            self._kill(t)
            self.g.break_combo()
            self.g.shake(8)
            self.g.fx.ring(x, y, C_BAD, 8, 70, 0.4, 3)
            self.g.cmd("trophic.eat(%s)  ✘ ZŁY POZIOM" % name)
            self.g.say("❌ %s wypada z kolejności — łańcuch przerwany." % name,
                       "Potrzebny był: %s. Zaczynasz ten krok od nowa."
                       % self.CHAIN[self.step][0], C_BAD)
            self.g.later(700, lambda: self._spawn(random.randrange(3)))

    def cleanup(self):
        for t in self.things[:]:
            self._kill(t)

    def hint(self):
        return "Zjedz: %s" % self.CHAIN[self.step][0]


class CoreSector(Sector):
    name = "RDZEŃ OCEANU"
    subtitle = "Przetrwaj kalibrację"
    console = False
    enemies = False
    reward = ""

    DURATION = 24.0

    def start(self):
        self.t = 0.0
        self.pulses = []
        self.tele = []
        self.next_aim = 1.0
        self.next_burst = 4.0
        self.next_wall = 9.0
        self.angle = 0.0
        c = self.g.canvas
        self.cx, self.cy = WIDTH - 150, HEIGHT / 2
        self.core_glow = c.create_oval(0, 0, 1, 1,
                                       fill=mix("#4FF3FF", self.g.bg_at(HEIGHT / 2), 0.66),
                                       outline="")
        self.core_glow2 = c.create_oval(0, 0, 1, 1,
                                        fill=mix("#4FF3FF", self.g.bg_at(HEIGHT / 2), 0.84),
                                        outline="")
        self.core_ring = c.create_oval(0, 0, 1, 1, outline="#4FF3FF", width=3)
        self.core_segs = [c.create_arc(0, 0, 1, 1, start=0, extent=74, style="arc",
                                       outline=mix("#9BF9FF", DEEP, 0.25), width=6)
                          for _ in range(3)]
        self.core_arms = [c.create_polygon([0, 0, 1, 1, 2, 2], fill=mix("#4FF3FF", DEEP, 0.32),
                                           outline="#9BF9FF", width=1, smooth=True)
                          for _ in range(3)]
        self.core_shell = c.create_polygon([0, 0, 1, 1, 2, 2], fill="",
                                           outline=mix("#CFFBFF", DEEP, 0.15), width=2)
        self.bolts = [c.create_line(0, 0, 1, 1, fill="#DFFBFF", width=2, smooth=True)
                      for _ in range(4)]
        self.core = c.create_oval(0, 0, 1, 1, fill="#CFFBFF", outline="#4FF3FF", width=3)
        self.core_hot = c.create_oval(0, 0, 1, 1, fill="#FFFFFF", outline="")
        for i in ([self.core_glow, self.core_glow2, self.core_ring, self.core_shell,
                   self.core, self.core_hot] + self.core_arms + self.core_segs + self.bolts):
            self.g.to_layer(i, "L_WORLD")
        self.g.say("SYSTEM KRYTYCZNY. Unikaj impulsów przez 24 sekundy — klik / SPACJA to zryw z nietykalnością.",
                   "Czerwone pierścienie ostrzegają przed salwą promienistą.", C_WARN)
        self._obj()

    def _obj(self):
        self.g.objective("%s — STABILIZACJA %4.1f / %.0f s"
                         % (self.head, min(self.t, self.DURATION), self.DURATION))

    def _pulse(self, x, y, vx, vy, r=11, col="#FF3B5C"):
        c = self.g.canvas
        halo = c.create_oval(0, 0, 1, 1, fill=glow_of(col, 0.7), outline="")
        core = c.create_oval(0, 0, 1, 1, fill=col, outline="#FFD3DC", width=1)
        spark = c.create_oval(0, 0, 1, 1, fill="#FFFFFF", outline="")
        self.g.to_layer(halo, "L_WORLD")
        self.g.to_layer(core, "L_WORLD")
        self.g.to_layer(spark, "L_WORLD")
        self.pulses.append({"x": x, "y": y, "vx": vx, "vy": vy, "r": r,
                            "halo": halo, "core": core, "spark": spark, "col": col})

    def _aimed(self, speed=260):
        p = self.g.player
        a = math.atan2(p.y - self.cy, p.x - self.cx) + random.uniform(-0.12, 0.12)
        self._pulse(self.cx, self.cy, math.cos(a) * speed, math.sin(a) * speed, 12)

    def _radial(self, n=14, speed=190):
        off = random.uniform(0, math.tau)
        for i in range(n):
            a = off + math.tau * i / n
            self._pulse(self.cx, self.cy, math.cos(a) * speed, math.sin(a) * speed, 10, "#FF7A3B")

    def _wall(self):
        gap = random.uniform(90, HEIGHT - 90)
        y = 30
        while y < HEIGHT - 20:
            if abs(y - gap) > 78:
                self._pulse(WIDTH + 20, y, -230, 0, 13, "#C08CFF")
            y += 46

    def update(self, dt):
        c = self.g.canvas
        p = self.g.player
        self.t += dt
        self.angle += dt * 1.4
        phase = 1 if self.t < 8 else (2 if self.t < 16 else 3)

        # rdzen
        cx, cy = self.cx, self.cy
        pr = 32 + math.sin(self.t * 4) * 4
        c.coords(self.core, cx - pr, cy - pr, cx + pr, cy + pr)
        hr = pr * (0.42 + 0.10 * math.sin(self.t * 9))
        c.coords(self.core_hot, cx - hr, cy - hr, cx + hr, cy + hr)
        gr = pr * 2.4
        c.coords(self.core_glow, cx - gr, cy - gr, cx + gr, cy + gr)
        c.itemconfigure(self.core_glow, fill=mix("#4FF3FF", self.g.bg_at(cy), 0.70))
        gr2 = pr * 3.6 + math.sin(self.t * 2.5) * 6
        c.coords(self.core_glow2, cx - gr2, cy - gr2, cx + gr2, cy + gr2)
        c.itemconfigure(self.core_glow2, fill=mix("#4FF3FF", self.g.bg_at(cy), 0.88))
        rr = 62 + math.sin(self.t * 2) * 6
        c.coords(self.core_ring, cx - rr, cy - rr, cx + rr, cy + rr)
        # segmentowy pierscien wirujacy w druga strone
        sr = 82 + math.sin(self.t * 1.6) * 5
        deg = -math.degrees(self.angle) * 1.4
        for i, seg in enumerate(self.core_segs):
            c.coords(seg, cx - sr, cy - sr, cx + sr, cy + sr)
            c.itemconfigure(seg, start=deg + i * 120)
        # heksagonalna powloka
        hex_pts = []
        for k in range(6):
            a = -self.angle * 0.8 + math.tau * k / 6
            hrr = 50 + 5 * math.sin(self.t * 5 + k)
            hex_pts += [cx + math.cos(a) * hrr, cy + math.sin(a) * hrr]
        c.coords(self.core_shell, *hex_pts)
        # zakrzywione ramiona energii
        for i, arm in enumerate(self.core_arms):
            a = self.angle + math.tau * i / 3
            fwd, back = [], []
            for k in range(6):
                tt = k / 5.0
                rad = 44 + 66 * tt
                aa = a + 0.62 * tt
                w = 14 * (1 - tt) + 3
                ca_, sa_ = math.cos(aa), math.sin(aa)
                fwd += [cx + ca_ * rad - sa_ * w, cy + sa_ * rad + ca_ * w]
                back = [cx + ca_ * rad + sa_ * w, cy + sa_ * rad - ca_ * w] + back
            c.coords(arm, *(fwd + back))
        # trzaskajace luki energii
        for b in self.bolts:
            if random.random() < 0.35:
                a = random.uniform(0, math.tau)
                pts = []
                for k in range(4):
                    tt = k / 3.0
                    rad = pr + (66 - pr) * tt
                    aa = a + random.uniform(-0.22, 0.22)
                    pts += [cx + math.cos(aa) * rad, cy + math.sin(aa) * rad]
                c.coords(b, *pts)
                c.itemconfigure(b, state="normal",
                                fill="#FFFFFF" if random.random() < 0.4 else "#8FF6FF")
            elif random.random() < 0.25:
                c.itemconfigure(b, state="hidden")
        if random.random() < 0.5:
            a = random.uniform(0, math.tau)
            self.g.fx.spawn(cx + math.cos(a) * 70, cy + math.sin(a) * 70,
                            -math.cos(a) * 60, -math.sin(a) * 60, "#8FF6FF", 3, 0.5)

        # ataki
        self.next_aim -= dt
        if self.next_aim <= 0:
            self._aimed(240 + phase * 32)
            self.next_aim = max(0.30, 1.05 - 0.16 * phase)
            self.g.fx.spawn(self.cx, self.cy, 0, 0, "#FFFFFF", 5, 0.25)
        if phase >= 2:
            self.next_burst -= dt
            if self.next_burst <= 0:
                self.g.fx.ring(self.cx, self.cy, "#FF3B5C", 40, 150, 0.55, 4)
                self.g.later(520, lambda: self._radial(12 + phase * 3, 180 + phase * 18))
                self.next_burst = 4.6 - phase * 0.5
        if phase >= 3:
            self.next_wall -= dt
            if self.next_wall <= 0:
                self.g.fx.text(WIDTH / 2, 118, "⚠ ŚCIANA IMPULSÓW", C_WARN, 1.1)
                self.g.later(700, self._wall)
                self.next_wall = 6.0

        for q in self.pulses[:]:
            q["x"] += q["vx"] * dt
            q["y"] += q["vy"] * dt
            r = q["r"]
            c.coords(q["core"], q["x"] - r, q["y"] - r, q["x"] + r, q["y"] + r)
            R = r * 1.95
            c.coords(q["halo"], q["x"] - R, q["y"] - R, q["x"] + R, q["y"] + R)
            c.itemconfigure(q["halo"], fill=mix(q["col"], self.g.bg_at(q["y"]), 0.66))
            sr = r * 0.42
            c.coords(q["spark"], q["x"] - sr, q["y"] - sr, q["x"] + sr, q["y"] + sr)
            if random.random() < 0.25:
                self.g.fx.spawn(q["x"], q["y"], -q["vx"] * 0.08, -q["vy"] * 0.08, q["col"], 2.6, 0.3)
            if q["x"] < -60 or q["x"] > WIDTH + 80 or q["y"] < -60 or q["y"] > HEIGHT + 60:
                for k in ("halo", "core", "spark"):
                    c.delete(q[k])
                self.pulses.remove(q)
                continue
            if math.hypot(q["x"] - p.x, q["y"] - p.y) < r + p.size * 0.8:
                if self.g.damage(1, "Impuls rdzenia trafił w Mikrobę!"):
                    for k in ("halo", "core", "spark"):
                        c.delete(q[k])
                    self.pulses.remove(q)
                    self.g.fx.burst(q["x"], q["y"], q["col"], 20, 240, 4, 0.5)

        if int(self.t * 4) != int((self.t - dt) * 4):
            self._obj()
        if self.t >= self.DURATION:
            self.g.finish_sector()

    def cleanup(self):
        c = self.g.canvas
        for q in self.pulses:
            for k in ("halo", "core", "spark"):
                c.delete(q[k])
        self.pulses = []
        for i in ([self.core_glow, self.core_glow2, self.core_ring, self.core_shell,
                   self.core, self.core_hot] + self.core_arms + self.core_segs + self.bolts):
            c.delete(i)

    def hint(self):
        return "Unikaj impulsów. Klik / SPACJA = zryw."


# ---------------------------------------------------------------------------
# GRA
# ---------------------------------------------------------------------------
LAYERS = ["L_BG", "L_SHAFT", "L_FAR", "L_MID", "L_WORLD", "L_PLAYER", "L_FX",
          "L_FG", "L_HUD", "L_TOP"]
NEXT_LAYER = {LAYERS[i]: LAYERS[i + 1] for i in range(len(LAYERS) - 1)}
NBANDS = 48

REWARDS = ["OSŁONA FOTOSYNTEZY  (tarcza pochłaniająca jedno trafienie)",
           "MINI-REAKTOR  (+szybkość, krótszy cooldown zrywu)",
           "ANTENA SENSORYCZNA  (magnes na fotony i okazy)",
           "BŁONA REGENERACYJNA  (+1 maksymalne życie, pełna regeneracja)",
           "STABILIZATOR pH  (większy zasięg fali neutralizującej)"]

RANKS = [(26000, "S", "STRAŻNIK GŁĘBIN"), (19000, "A", "INŻYNIER EKOSYSTEMU"),
         (13000, "B", "TECHNIK RAFY"), (7000, "C", "PRAKTYKANT"), (0, "D", "REKRUT")]


class Game:
    def __init__(self, root):
        self.root = root
        root.title("DEEP CODE :: Strażnik Głębin")
        root.configure(bg=C_PANEL)
        root.resizable(False, False)
        self._fonts()

        self.canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg=DEEP,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        self.canvas.configure(scrollregion=(-PAD, -PAD, WIDTH + PAD, HEIGHT + PAD))
        self._build_console()

        self.gen = 0
        self.pending = []
        self.paused = False
        self.state = "menu"
        self.last = time.perf_counter()
        self.sx = self.sy = 0.0
        self.shake_amt = 0.0

        self.key_states = {}
        root.bind("<KeyPress>", self.on_press)
        root.bind("<KeyRelease>", self.on_release)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<B1-Motion>", self.on_motion)
        self.canvas.bind("<Leave>", self.on_leave)
        root.bind("<Return>", self.on_enter)
        self.mouse = None
        self.use_mouse = False

        self.build_world()
        self.show_menu()
        self.loop()

    # -- czcionki ---------------------------------------------------------
    def _fonts(self):
        fams = set(tkfont.families(self.root))
        mono = next((f for f in ("Consolas", "DejaVu Sans Mono", "Menlo", "Liberation Mono",
                                 "Courier New", "Courier") if f in fams), "Courier")
        self.mono = mono
        self.f_tiny = (mono, 9, "bold")
        self.f_small = (mono, 11, "bold")
        self.f_ui = (mono, 12, "bold")
        self.f_big = (mono, 26, "bold")
        self.f_huge = (mono, 44, "bold")
        self.f_title = (mono, 54, "bold")

    # -- panel konsoli ----------------------------------------------------
    def _build_console(self):
        """Dolny panel: komunikaty misji + auto-konsola (log wykonanych poleceń)."""
        f = tk.Frame(self.root, bg=C_PANEL, pady=8)
        f.pack(fill="x")
        top = tk.Frame(f, bg=C_PANEL)
        top.pack(fill="x", padx=14)
        self.lbl1 = tk.Label(top, text="", fg=C_TXT, bg=C_PANEL, font=self.f_ui,
                             anchor="w", justify="left")
        self.lbl1.pack(fill="x")
        self.lbl2 = tk.Label(top, text="", fg=mix(C_TXT, DEEP, 0.35), bg=C_PANEL,
                             font=self.f_small, anchor="w", justify="left")
        self.lbl2.pack(fill="x")
        row = tk.Frame(f, bg=C_PANEL2)
        row.pack(fill="x", padx=14, pady=(8, 0), ipady=6)
        self.prompt = tk.Label(row, text="▶ AUTO-KONSOLA", fg=C_OK, bg=C_PANEL2,
                               font=self.f_small)
        self.prompt.pack(side="left", padx=(10, 10))
        self.cmd_lbl = tk.Label(row, text="system.boot()  ✔", fg=C_OK, bg=C_PANEL2,
                                font=(self.mono, 13, "bold"), anchor="w")
        self.cmd_lbl.pack(side="left", fill="x", expand=True)
        self.hint_lbl = tk.Label(row, text="", fg=C_WARN, bg=C_PANEL2, font=self.f_small)
        self.hint_lbl.pack(side="right", padx=(10, 10))

    def cmd(self, text):
        """Wyświetla polecenie, które Mikroba wykonała 'sama' — klimat programowania."""
        self.cmd_lbl.config(text=text)

    # -- warstwy ----------------------------------------------------------
    def to_layer(self, item, layer):
        """Wstawia obiekt na koniec danej warstwy (zachowuje kolejnosc tworzenia)."""
        self.canvas.tag_lower(item, self.marks[NEXT_LAYER[layer]])

    def _build_layers(self):
        self.marks = {}
        for n in LAYERS:
            self.marks[n] = self.canvas.create_rectangle(-999, -999, -998, -998,
                                                         outline="", state="hidden")

    # -- swiat ------------------------------------------------------------
    def build_world(self):
        c = self.canvas
        self._build_layers()

        # gradient
        self.bands = []
        bh = (HEIGHT + 2 * PAD) / NBANDS
        for i in range(NBANDS):
            y0 = -PAD + i * bh
            r = c.create_rectangle(-PAD, y0 - 1, WIDTH + PAD, y0 + bh + 1,
                                   fill="#000000", outline="")
            self.to_layer(r, "L_BG")
            self.bands.append(r)
        self.pal = dict(MENU_PAL)
        self.pal_from = dict(MENU_PAL)
        self.pal_to = dict(MENU_PAL)
        self.pal_t = 1.0

        # promienie swiatla
        self.shafts = []
        for i in range(6):
            p = c.create_polygon([0, 0, 1, 1, 2, 2], fill="#123", outline="")
            self.to_layer(p, "L_SHAFT")
            self.shafts.append({"id": p, "x": random.uniform(-50, WIDTH),
                                "w": random.uniform(40, 110),
                                "sp": random.uniform(4, 12), "ph": random.uniform(0, 6)})

        # dalekie drobiny (parallaks)
        self.dots = []
        for _ in range(46):
            x, y = random.uniform(-PAD, WIDTH + PAD), random.uniform(-PAD, HEIGHT + PAD)
            r = random.uniform(1.0, 2.6)
            d = c.create_oval(x, y, x + r, y + r, fill="#2A4E6E", outline="")
            self.to_layer(d, "L_FAR")
            self.dots.append(d)

        # wodorosty
        self.kelp = []
        for layer, n, col, wd in (("L_MID", 13, "#0A4A3A", 5), ("L_FG", 6, "#052B22", 11)):
            for _ in range(n):
                k = {"x": random.uniform(-20, WIDTH + 20), "h": random.uniform(120, 330),
                     "amp": random.uniform(12, 34), "sp": random.uniform(0.5, 1.2),
                     "ph": random.uniform(0, 6)}
                k["id"] = c.create_line(0, 0, 1, 1, fill=col, width=wd,
                                        smooth=True, capstyle="round")
                self.to_layer(k["id"], layer)
                self.kelp.append(k)

        # skalne formacje w tle
        self.rocks = []
        for _ in range(7):
            bx = random.uniform(-80, WIDTH + 80)
            bw = random.uniform(120, 320)
            bh = random.uniform(70, 210)
            pts = [bx - bw / 2, HEIGHT + 60]
            steps = 8
            for k in range(steps + 1):
                f = k / float(steps)
                pts += [bx - bw / 2 + bw * f,
                        HEIGHT + 24 - bh * (math.sin(f * math.pi) ** 0.75)
                        * random.uniform(0.7, 1.0)]
            pts += [bx + bw / 2, HEIGHT + 60]
            r = c.create_polygon(*pts, fill="#101820", outline="", smooth=True)
            self.to_layer(r, "L_FAR")
            self.rocks.append(r)

        # dno morskie (dwie warstwy wydm)
        fl = []
        for k in range(19):
            f = k / 18.0
            fl += [-PAD + (WIDTH + 2 * PAD) * f,
                   HEIGHT - 30 + math.sin(f * 7.0) * 13 + math.sin(f * 19.0) * 5]
        self.floor_far = c.create_polygon(*(fl + [WIDTH + PAD, HEIGHT + PAD, -PAD, HEIGHT + PAD]),
                                          fill="#0B1A22", outline="", smooth=True)
        self.to_layer(self.floor_far, "L_MID")
        fl2 = []
        for k in range(15):
            f = k / 14.0
            fl2 += [-PAD + (WIDTH + 2 * PAD) * f,
                    HEIGHT - 6 + math.sin(f * 5.0 + 1.2) * 11]
        self.floor_near = c.create_polygon(*(fl2 + [WIDTH + PAD, HEIGHT + PAD, -PAD, HEIGHT + PAD]),
                                           fill="#060F14", outline="", smooth=True)
        self.to_layer(self.floor_near, "L_FG")

        # meduzy (tlo zywe, nieinteraktywne)
        self.jellies = []
        for _ in range(3):
            bell = c.create_polygon([0, 0, 1, 1, 2, 2], fill="#123", outline="", smooth=True)
            self.to_layer(bell, "L_MID")
            tents = [c.create_line(0, 0, 1, 1, fill="#123", width=2, smooth=True)
                     for _ in range(4)]
            for t in tents:
                self.to_layer(t, "L_MID")
            self.jellies.append({"bell": bell, "tent": tents, "x": random.uniform(0, WIDTH),
                                 "y": random.uniform(0, HEIGHT), "r": random.uniform(15, 28),
                                 "sp": random.uniform(8, 19), "ph": random.uniform(0, 6)})

        # kaustyka tuz pod powierzchnia
        self.caustics = []
        for i in range(5):
            ln = c.create_line(0, 0, 1, 1, fill="#123", width=2, smooth=True)
            self.to_layer(ln, "L_SHAFT")
            self.caustics.append({"id": ln, "y": 64 + i * 16, "ph": random.uniform(0, 6),
                                  "sp": random.uniform(0.5, 1.2)})

        # ławica ryb w oddali
        self.school = []
        for _ in range(16):
            f = c.create_polygon([0, 0, 1, 1, 2, 2], fill="#123", outline="", smooth=True)
            self.to_layer(f, "L_FAR")
            self.school.append({"id": f, "x": random.uniform(0, WIDTH),
                                "y": random.uniform(90, HEIGHT - 140),
                                "s": random.uniform(5, 10), "sp": random.uniform(34, 62),
                                "ph": random.uniform(0, 6), "amp": random.uniform(8, 24),
                                "dir": random.choice([-1, 1])})

        # koralowce rozgałęzione (każdy to kilka grubych, zaokrąglonych gałęzi)
        self.corals = []
        REEF = ["#E0655A", "#D98A3D", "#B45AD0", "#3FBFA0", "#E06590"]
        for _ in range(9):
            hue = random.choice(REEF)
            cx = random.uniform(0, WIDTH)
            base = HEIGHT - random.uniform(2, 16)
            h = random.uniform(34, 78)
            branches = []
            for bi in range(3):
                lean = random.uniform(-0.55, 0.55) + (bi - 1) * 0.42
                bh = h * random.uniform(0.55, 1.0)
                pts = []
                for k in range(4):
                    f = k / 3.0
                    pts += [cx + lean * bh * f * f + random.uniform(-2, 2),
                            base - bh * f]
                ln = c.create_line(*pts, fill="#123", width=random.uniform(6, 11),
                                   smooth=True, capstyle="round")
                self.to_layer(ln, "L_MID")
                branches.append((ln, hue, 0.0))
                # zakończenie gałęzi
                tip = c.create_oval(pts[-2] - 5, pts[-1] - 5, pts[-2] + 5, pts[-1] + 5,
                                    fill="#123", outline="")
                self.to_layer(tip, "L_MID")
                branches.append((tip, hue, 0.22))
            self.corals.extend(branches)

        # ukwiały z falującymi czułkami
        self.anemones = []
        for _ in range(3):
            hue = random.choice(["#E06590", "#7FD9C6", "#D9A03D"])
            ax = random.uniform(70, WIDTH - 70)
            ay = HEIGHT - random.uniform(14, 30)
            body = c.create_oval(ax - 17, ay - 7, ax + 17, ay + 12, fill="#123", outline="")
            self.to_layer(body, "L_MID")
            tents = []
            for _ in range(9):
                ln = c.create_line(0, 0, 1, 1, fill="#123", width=2, smooth=True,
                                   capstyle="round")
                self.to_layer(ln, "L_MID")
                tents.append(ln)
            self.anemones.append({"x": ax, "y": ay, "body": body, "tent": tents,
                                  "hue": hue, "h": random.uniform(30, 52),
                                  "ph": random.uniform(0, 6)})

        # kamienie i muszle na dnie
        self.pebbles = []
        for _ in range(16):
            px = random.uniform(-20, WIDTH + 20)
            py = HEIGHT - random.uniform(4, 26)
            pr = random.uniform(3, 9)
            item = c.create_oval(px - pr, py - pr * 0.6, px + pr, py + pr * 0.6,
                                 fill="#123", outline="")
            self.to_layer(item, "L_MID")
            self.pebbles.append(item)

        # kaustyka tancząca na dnie
        self.floor_caustics = []
        for i in range(7):
            ln = c.create_line(0, 0, 1, 1, fill="#123", width=3, smooth=True,
                               capstyle="round")
            self.to_layer(ln, "L_MID")
            self.floor_caustics.append({"id": ln, "x": random.uniform(0, WIDTH),
                                        "y": HEIGHT - 32 + (i % 3) * 11,
                                        "w": random.uniform(70, 150),
                                        "drift": random.uniform(-14, 14),
                                        "ph": random.uniform(0, 6),
                                        "sp": random.uniform(0.6, 1.3)})

        # świetlna plama pod graczem
        self.player_light = c.create_oval(0, 0, 1, 1, fill="#123", outline="")
        self.to_layer(self.player_light, "L_MID")

        # banki powietrza
        self.bubbles = []
        for _ in range(34):
            x, y = random.uniform(0, WIDTH), random.uniform(0, HEIGHT)
            s = random.uniform(2.5, 7)
            b = c.create_oval(x, y, x + s, y + s, outline=mix("#9FD8FF", DEEP, 0.55),
                              width=1, fill="")
            self.to_layer(b, "L_MID")
            hi = None
            if s > 4.4:
                hi = c.create_oval(0, 0, 1, 1, fill=mix("#EAF8FF", DEEP, 0.35), outline="")
                self.to_layer(hi, "L_MID")
            self.bubbles.append({"id": b, "hi": hi, "x": x, "y": y, "s": s,
                                 "sp": random.uniform(18, 52), "ph": random.uniform(0, 6)})

        # świetlna fala przejścia między sektorami
        self.sweep = c.create_polygon([0, 0, 1, 1, 2, 2], fill="#123", outline="",
                                      state="hidden")
        self.to_layer(self.sweep, "L_FG")
        self.sweep_t = -1.0

        # winieta
        self.vig = c.create_rectangle(-12, -12, WIDTH + 12, HEIGHT + 12,
                                      outline="#000000", width=64, fill="")
        self.to_layer(self.vig, "L_FG")
        self.vig_flash = 0.0
        self._paint_bands()

        self.fx = Fx(self)

        # postacie
        self.player = Fish(self, 130, HEIGHT / 2, 26, "#FF9F2E", "#FFD86B",
                           is_player=True, trail=7)
        self.enemies = []
        for i in range(2):
            e = Fish(self, WIDTH + 150 + i * 260, random.uniform(80, HEIGHT - 80), 34,
                     "#E0245E", "#FF7AA2")
            e.vx = -random.uniform(90, 130)
            self.enemies.append(e)
        self.enemies_on = False

        self._build_hud()

        # stan rozgrywki
        self.score = 0
        self.combo = 0
        self.combo_timer = 0.0
        self.max_health = 5
        self.health = self.max_health
        self.upgrades = 0
        self.inv = 0.0
        self.shield_ready = False
        self.shield_cd = 0.0
        self.dash_cd = 0.0
        self.dash_t = 0.0
        self.sector_i = 0
        self.sector = None
        self.t = 0.0
        self.run_time = 0.0
        self.sectors = self.roll_sectors()

    def roll_sectors(self):
        """Losuje 5 z 8 sektorów; szósty to zawsze walka z rdzeniem (boss)."""
        pool = [LightSector, SortSector, RhythmSector, SequenceSector, ChemSector,
                NetsSector, CurrentSector, FoodChainSector]
        return random.sample(pool, 5) + [CoreSector]

    # -- HUD --------------------------------------------------------------
    def _build_hud(self):
        c = self.canvas
        self.hud = []

        def add(i):
            self.to_layer(i, "L_HUD")
            self.hud.append(i)
            return i

        self.hud_bar = add(c.create_rectangle(-PAD, -PAD, WIDTH + PAD, 46,
                                              fill=mix(DEEP, "#000000", 0.30), outline=""))
        add(c.create_line(-PAD, 46, WIDTH + PAD, 46, fill=mix(C_TXT, DEEP, 0.72)))
        self.hearts = []
        for i in range(8):
            h = add(c.create_polygon([0, 0, 1, 1, 2, 2], fill="#FF5C7A",
                                     outline="#FFD3DC", width=1, state="hidden", smooth=True))
            self.hearts.append(h)
        self.hud_obj_bg = add(c.create_rectangle(WIDTH / 2 - 268, 7, WIDTH / 2 + 268, 39,
                                                 fill=mix(DEEP, "#FFFFFF", 0.07), outline=""))
        self.hud_obj = add(c.create_text(WIDTH / 2, 23, text="", fill=C_TXT, font=self.f_ui))
        self.hud_score = add(c.create_text(WIDTH - 16, 15, text="0", fill="#FFE066",
                                           font=self.f_ui, anchor="e"))
        self.hud_combo = add(c.create_text(WIDTH - 16, 33, text="", fill=C_OK,
                                           font=self.f_tiny, anchor="e"))
        dx0 = WIDTH - 186
        self.hud_dash_bg = add(c.create_rectangle(dx0, HEIGHT - 26, dx0 + 160, HEIGHT - 14,
                                                  fill=mix(DEEP, "#FFFFFF", 0.10),
                                                  outline=mix(C_TXT, DEEP, 0.7)))
        self.hud_dash = add(c.create_rectangle(dx0 + 2, HEIGHT - 24, dx0 + 158, HEIGHT - 16,
                                               fill=C_OK, outline=""))
        self.hud_dash_t = add(c.create_text(dx0 + 80, HEIGHT - 38, text="KLIK / SPACJA — ZRYW",
                                            fill=mix(C_TXT, DEEP, 0.3), font=self.f_tiny))
        self.pips = []
        for i in range(6):
            p = add(c.create_rectangle(WIDTH / 2 - 96 + i * 33, 38, WIDTH / 2 - 72 + i * 33, 42,
                                       fill=mix(C_TXT, DEEP, 0.8), outline=""))
            self.pips.append(p)

    def _heart_pts(self, x, y, s):
        """Klasyczny kształt serca (krzywa parametryczna)."""
        pts = []
        for k in range(18):
            t = math.tau * k / 18
            hx = 16 * math.sin(t) ** 3
            hy = -(13 * math.cos(t) - 5 * math.cos(2 * t)
                   - 2 * math.cos(3 * t) - math.cos(4 * t))
            pts += [x + hx * s / 15.0, y + hy * s / 15.0]
        return pts

    def update_hud(self):
        c = self.canvas
        menu = self.state == "menu"
        for i in (self.hud_score, self.hud_combo, self.hud_dash, self.hud_dash_bg,
                  self.hud_dash_t):
            c.itemconfigure(i, state="hidden" if menu else "normal")
        if menu:
            for h in self.hearts:
                c.itemconfigure(h, state="hidden")
            for p in self.pips:
                c.itemconfigure(p, fill=mix(C_TXT, DEEP, 0.85))
            return
        for i, h in enumerate(self.hearts):
            if i < self.max_health:
                col = "#FF5C7A" if i < self.health else mix("#FF5C7A", DEEP, 0.78)
                c.coords(h, *self._heart_pts(24 + i * 26, 23, 9))
                c.itemconfigure(h, state="normal", fill=col,
                                outline="#FFD3DC" if i < self.health else mix("#FFD3DC", DEEP, 0.8))
            else:
                c.itemconfigure(h, state="hidden")
        c.itemconfigure(self.hud_score, text="%d PKT" % self.score)
        if self.combo > 1:
            c.itemconfigure(self.hud_combo, text="COMBO x%d  (+%d%%)"
                            % (self.combo, int((self._mult() - 1) * 100)))
        else:
            c.itemconfigure(self.hud_combo, text="")
        k = 1.0 - clamp(self.dash_cd / self._dash_cd_max(), 0, 1)
        c.coords(self.hud_dash, WIDTH - 184, HEIGHT - 24, WIDTH - 184 + 156 * k, HEIGHT - 16)
        c.itemconfigure(self.hud_dash, fill=C_OK if k >= 1 else mix(C_OK, DEEP, 0.55))
        c.itemconfigure(self.hud_obj_bg, state="hidden" if menu else "normal")
        for i, p in enumerate(self.pips):
            if i < self.sector_i:
                col = C_OK
            elif i == self.sector_i and self.state == "play":
                col = "#FFE066"
            else:
                col = mix(C_TXT, DEEP, 0.8)
            c.itemconfigure(p, fill=col)

    # -- tlo --------------------------------------------------------------
    def _paint_bands(self):
        top, bot = self.pal["top"], self.pal["bot"]
        for i, b in enumerate(self.bands):
            t = (i / (NBANDS - 1.0)) ** 1.25
            self.canvas.itemconfigure(b, fill=mix(top, bot, t))
        for s in self.shafts:
            base = self.bg_at(HEIGHT * 0.4)
            self.canvas.itemconfigure(s["id"], fill=mix(base, mix(self.pal["fog"], "#FFFFFF", 0.35), 0.16))
        self.canvas.itemconfigure(self.vig, outline=mix(self.pal["bot"], "#000000", 0.62))
        if getattr(self, "rocks", None):
            base = self.bg_at(HEIGHT - 40)
            for r in self.rocks:
                self.canvas.itemconfigure(r, fill=mix(base, "#000000", 0.50))
            self.canvas.itemconfigure(self.floor_far, fill=mix(base, "#000000", 0.66))
            self.canvas.itemconfigure(self.floor_near, fill=mix(base, "#000000", 0.80))
            for it, hue, lift in self.corals:
                col = mix(mix(hue, base, 0.42), "#FFFFFF", lift)
                self.canvas.itemconfigure(it, fill=mix(col, "#000000", 0.18))
            for it in self.pebbles:
                self.canvas.itemconfigure(it, fill=mix(base, "#000000", 0.42))
            for a in self.anemones:
                self.canvas.itemconfigure(a["body"],
                                          fill=mix(mix(a["hue"], base, 0.45), "#000000", 0.35))

    def bg_at(self, y):
        """Kolor tla na wysokosci y — sluzy do 'wtapiania' poswiat."""
        t = clamp((y + PAD) / (HEIGHT + 2.0 * PAD), 0, 1) ** 1.25
        return mix(self.pal["top"], self.pal["bot"], t)

    def set_palette(self, pal):
        self.pal_from = dict(self.pal)
        self.pal_to = dict(pal)
        self.pal_t = 0.0

    def _ambient(self, dt):
        c = self.canvas
        if self.pal_t < 1.0:
            self.pal_t = min(1.0, self.pal_t + dt / 1.3)
            for k in ("top", "bot", "fog", "acc"):
                self.pal[k] = mix(self.pal_from[k], self.pal_to[k], self.pal_t)
            self._paint_bands()

        for s in self.shafts:
            s["ph"] += dt * 0.35
            x = s["x"] + math.sin(s["ph"]) * s["sp"] * 3
            w = s["w"] * (1 + 0.18 * math.sin(s["ph"] * 1.7))
            c.coords(s["id"], x, -PAD, x + w, -PAD,
                     x + w * 2.6 + 90, HEIGHT + PAD, x + w * 1.5 - 20, HEIGHT + PAD)

        if random.random() < 0.16 and len(self.fx.free) > 40:
            sh = random.choice(self.shafts)
            mx = sh["x"] + random.uniform(0, sh["w"] * 2.2)
            my = random.uniform(0, HEIGHT)
            self.fx.spawn(mx, my, random.uniform(-6, 6), random.uniform(-14, -4),
                          mix(self.bg_at(my), "#FFFFFF", 0.55), 1.8, 1.4)

        for j in self.jellies:
            j["ph"] += dt * 1.7
            j["y"] -= j["sp"] * dt
            if j["y"] < -70:
                j["y"] = HEIGHT + 70
                j["x"] = random.uniform(0, WIDTH)
            jx = j["x"] + math.sin(j["ph"] * 0.6) * 16
            r = j["r"] * (1 + 0.13 * math.sin(j["ph"] * 2))
            pts = []
            for k in range(9):
                a = math.pi + math.pi * k / 8.0
                pts += [jx + math.cos(a) * r, j["y"] + math.sin(a) * r * 1.05]
            pts += [jx + r * 0.55, j["y"] + r * 0.30, jx, j["y"] + r * 0.10,
                    jx - r * 0.55, j["y"] + r * 0.30]
            c.coords(j["bell"], *pts)
            jcol = mix(self.pal["acc"], self.bg_at(j["y"]), 0.80)
            c.itemconfigure(j["bell"], fill=jcol)
            for ti, ln in enumerate(j["tent"]):
                tx = jx - r * 0.5 + ti * (r * 0.33)
                p2 = []
                for k in range(4):
                    f = k / 3.0
                    p2 += [tx + math.sin(j["ph"] * 2.2 + f * 3 + ti) * 7 * f,
                           j["y"] + r * 0.3 + f * r * 1.9]
                c.coords(ln, *p2)
                c.itemconfigure(ln, fill=jcol)

        for cs in self.caustics:
            cs["ph"] += dt * cs["sp"]
            pts = []
            for k in range(9):
                f = k / 8.0
                pts += [-PAD + (WIDTH + 2 * PAD) * f,
                        cs["y"] + math.sin(cs["ph"] + f * 6.0) * 7]
            c.coords(cs["id"], *pts)
            g = 0.10 + 0.07 * math.sin(cs["ph"] * 1.7)
            c.itemconfigure(cs["id"], fill=mix(self.bg_at(cs["y"]), "#DFF6FF", g))

        # ławica: sylwetki ryb sunące w tle
        for f in self.school:
            f["ph"] += dt
            f["x"] += f["dir"] * f["sp"] * dt
            if f["x"] < -60:
                f["x"] = WIDTH + 60
            elif f["x"] > WIDTH + 60:
                f["x"] = -60
            fy = f["y"] + math.sin(self.t * 1.1 + f["ph"]) * f["amp"] * 0.5
            sc, fl = f["s"], f["dir"]
            pts = []
            for lx, ly in ((1.05, 0.0), (0.25, -0.52), (-0.5, -0.38), (-1.25, -0.62),
                           (-0.95, 0.0), (-1.25, 0.62), (-0.5, 0.38), (0.25, 0.52)):
                wag = math.sin(self.t * 7 + f["ph"]) * 0.12 if lx < -0.9 else 0.0
                pts += [f["x"] + lx * sc * fl, fy + (ly + wag) * sc]
            c.coords(f["id"], *pts)
            c.itemconfigure(f["id"], fill=mix(self.bg_at(fy), "#04121C", 0.42))

        # ukwiały
        for a in self.anemones:
            a["ph"] += dt * 1.4
            tcol = mix(mix(a["hue"], self.bg_at(a["y"]), 0.35), "#FFFFFF", 0.12)
            for ti, ln in enumerate(a["tent"]):
                spread = (ti - 4) / 4.0
                bx = a["x"] + spread * 12
                th = a["h"] * (1.0 - 0.30 * abs(spread))
                pts = []
                for k in range(5):
                    fk = k / 4.0
                    sway = math.sin(a["ph"] * 1.9 + ti * 0.8 + fk * 2.6) * 11 * fk
                    pts += [bx + sway + spread * 16 * fk, a["y"] - th * fk]
                c.coords(ln, *pts)
                c.itemconfigure(ln, fill=tcol)

        # kaustyka na dnie
        for fc in self.floor_caustics:
            fc["ph"] += dt * fc["sp"]
            fc["x"] += fc["drift"] * dt
            if fc["x"] < -160:
                fc["x"] = WIDTH + 60
            elif fc["x"] > WIDTH + 160:
                fc["x"] = -60
            pts = []
            for k in range(5):
                fk = k / 4.0
                pts += [fc["x"] + fc["w"] * fk,
                        fc["y"] + math.sin(fc["ph"] * 1.6 + fk * 5.0) * 5]
            c.coords(fc["id"], *pts)
            g = 0.10 + 0.08 * math.sin(fc["ph"] * 2.1)
            c.itemconfigure(fc["id"], fill=mix(mix(self.bg_at(fc["y"]), "#000000", 0.5),
                                               "#DFF6FF", g))

        # świetlna plama pod graczem
        plx = self.player.x
        ply = HEIGHT - 22
        rx = 58 + 10 * math.sin(self.t * 2)
        c.coords(self.player_light, plx - rx, ply - 13, plx + rx, ply + 13)
        c.itemconfigure(self.player_light,
                        fill=mix(self.bg_at(ply), self.player.body_col, 0.10))

        for b in self.bubbles:
            b["ph"] += dt * 2.2
            b["y"] -= b["sp"] * dt
            bx = b["x"] + math.sin(b["ph"]) * 9
            if b["y"] < -20:
                b["y"] = HEIGHT + random.uniform(10, 120)
                b["x"] = random.uniform(0, WIDTH)
            c.coords(b["id"], bx, b["y"], bx + b["s"], b["y"] + b["s"])
            if b["hi"]:
                hr = b["s"] * 0.26
                c.coords(b["hi"], bx + b["s"] * 0.24, b["y"] + b["s"] * 0.20,
                         bx + b["s"] * 0.24 + hr, b["y"] + b["s"] * 0.20 + hr)

        for k in self.kelp:
            pts = []
            for i in range(5):
                f = i / 4.0
                pts += [k["x"] + math.sin(self.t * k["sp"] + f * 2.4 + k["ph"]) * k["amp"] * f,
                        HEIGHT + 12 - f * k["h"]]
            c.coords(k["id"], *pts)

        if abs(self.player.vx) + abs(self.player.vy) > 6:
            dx = -self.player.vx * dt * 0.16
            dy = -self.player.vy * dt * 0.16
            for d in self.dots:
                c.move(d, dx, dy)
                co = c.coords(d)
                if co[0] < -PAD - 6:
                    c.move(d, WIDTH + 2 * PAD, 0)
                elif co[0] > WIDTH + PAD + 6:
                    c.move(d, -(WIDTH + 2 * PAD), 0)
                if co[1] < -PAD - 6:
                    c.move(d, 0, HEIGHT + 2 * PAD)
                elif co[1] > HEIGHT + PAD + 6:
                    c.move(d, 0, -(HEIGHT + 2 * PAD))

        if self.sweep_t >= 0:
            self.sweep_t += dt / 0.75
            if self.sweep_t >= 1.0:
                self.sweep_t = -1.0
                c.itemconfigure(self.sweep, state="hidden")
            else:
                k = self.sweep_t
                x = lerp(-320, WIDTH + 260, k)
                c.coords(self.sweep, x, -PAD, x + 150, -PAD,
                         x + 260, HEIGHT + PAD, x + 110, HEIGHT + PAD)
                fade = math.sin(k * math.pi)
                c.itemconfigure(self.sweep, state="normal",
                                fill=mix(self.bg_at(HEIGHT / 2), self.pal["acc"],
                                         0.32 * fade))

        if self.vig_flash > 0:
            self.vig_flash = max(0.0, self.vig_flash - dt * 2.2)
            c.itemconfigure(self.vig, outline=mix(mix(self.pal["bot"], "#000000", 0.55),
                                                  "#FF2A4A", self.vig_flash))

    # -- pomocnicze -------------------------------------------------------
    def later(self, ms, fn):
        g = self.gen

        def wrap():
            if g == self.gen and not self.paused:
                fn()
            elif g == self.gen:
                self.later(120, fn)
        aid = self.root.after(ms, wrap)
        self.pending.append(aid)
        return aid

    def shake(self, amt):
        self.shake_amt = min(26.0, self.shake_amt + amt)

    def say(self, l1, l2="", color=C_TXT):
        self.lbl1.config(text=l1, fg=color)
        self.lbl2.config(text=l2)

    def objective(self, text):
        self.canvas.itemconfigure(self.hud_obj, text=text)

    def _mult(self):
        return min(3.0, 1.0 + max(0, self.combo - 1) * 0.15)

    def add_score(self, base, x=None, y=None, combo=False, label=None):
        if combo:
            self.combo += 1
            self.combo_timer = 5.0
        pts = int(base * self._mult())
        self.score += pts
        if x is not None:
            self.fx.text(x, y, label or "+%d" % pts,
                         "#FFE066" if not label else C_OK, 0.95)
            if label:
                self.fx.text(x, y + 18, "+%d" % pts, "#FFE066", 0.9)

    def break_combo(self):
        if self.combo > 2:
            self.fx.text(self.player.x, self.player.y - 40, "COMBO ŁAMANE", C_BAD, 0.9)
        self.combo = 0

    def _dash_cd_max(self):
        return 1.5 if self.upgrades >= 2 else 2.2

    def damage(self, n, msg=""):
        if self.inv > 0 or self.state != "play":
            return False
        if self.shield_ready:
            self.shield_ready = False
            self.shield_cd = 11.0
            self.inv = 1.0
            self.fx.ring(self.player.x, self.player.y, C_OK, 30, 130, 0.5, 5)
            self.fx.burst(self.player.x, self.player.y, C_OK, 22, 260, 4, 0.6)
            self.shake(8)
            self.say("🛡 OSŁONA POCHŁONĘŁA CIOS!",
                     "Regeneracja tarczy: 11 s.", C_OK)
            return True
        self.health -= n
        self.inv = 1.5
        self.vig_flash = 1.0
        self.shake(14)
        self.break_combo()
        self.fx.burst(self.player.x, self.player.y, C_BAD, 24, 280, 4, 0.6)
        self.fx.ring(self.player.x, self.player.y, C_BAD, 20, 100, 0.45, 4)
        if msg:
            self.say("❤ -1 ŻYCIE — " + msg,
                     "Pozostało żyć: %d" % max(0, self.health), C_BAD)
        if self.health <= 0:
            self.end_game(False)
        return True

    # -- przeplyw gry -----------------------------------------------------
    def show_menu(self):
        self.state = "menu"
        self.set_palette(MENU_PAL)
        c = self.canvas
        c.delete("overlay")

        def T(x, y, txt, font, fill, anchor="center"):
            i = c.create_text(x, y, text=txt, font=font, fill=fill, anchor=anchor, tags="overlay")
            self.to_layer(i, "L_HUD")
            return i
        box = c.create_rectangle(WIDTH / 2 - 330, 120, WIDTH / 2 + 330, HEIGHT - 90,
                                 fill=mix(DEEP, "#000000", 0.35),
                                 outline=mix(C_OK, DEEP, 0.55), width=2, tags="overlay")
        self.to_layer(box, "L_HUD")
        T(WIDTH / 2, 178, "DEEP CODE", self.f_title, "#4FF3FF")
        T(WIDTH / 2, 224, "S T R A Ż N I K   G Ł Ę B I N", self.f_small, C_TXT)
        T(WIDTH / 2, 276, "Ocean umiera. Jesteś Mikrobą — żywą konsolą naprawczą.",
          self.f_ui, mix(C_TXT, DEEP, 0.2))
        T(WIDTH / 2, 300, "5 losowych sektorów z 8, a na końcu zawsze walka z RDZENIEM.",
          self.f_ui, mix(C_TXT, DEEP, 0.2))
        lines = [
            "MYSZKA            —  Mikroba płynie za kursorem",
            "STRZAŁKI / WASD   —  sterowanie klawiaturą (opcjonalne)",
            "KLIK / SPACJA     —  zryw (dash, krótka nietykalność)",
            "P — pauza          R — restart",
            "Nic nie musisz pisać: wszystko robisz pływaniem i dotykiem.",
        ]
        for i, s in enumerate(lines):
            T(WIDTH / 2 - 250, 344 + i * 26, s, self.f_small, mix(C_OK, DEEP, 0.15), "w")
        btn = c.create_rectangle(WIDTH / 2 - 190, HEIGHT - 172, WIDTH / 2 + 190, HEIGHT - 124,
                                 fill=mix("#FFE066", DEEP, 0.72), outline="#FFE066", width=2,
                                 tags="overlay")
        self.to_layer(btn, "L_HUD")
        T(WIDTH / 2, HEIGHT - 148, "▶   K L I K N I J ,   A B Y   Z A C Z Ą Ć   ◀",
          self.f_ui, "#FFE066")
        self.say("Witaj w głębinach. Kliknij ekran (lub naciśnij ENTER), aby rozpocząć misję.",
                 "Mikroba płynie za kursorem myszy — całą grę obsłużysz samym pływaniem.",
                 C_TXT)
        self.objective("DEEP CODE · MENU GŁÓWNE")
        self.set_console(True, "KLIKNIJ, ABY ZACZĄĆ")

    def set_console(self, on, hint=""):
        """Gra nie wymaga pisania — pole tekstowe zastąpiła kontekstowa podpowiedź."""
        self.hint_lbl.config(text=hint)
        self._last_hint = hint
        self.prompt.config(text="▶ AUTO-KONSOLA", fg=C_OK)
        try:
            self.canvas.focus_set()
        except Exception:
            pass

    def start_run(self):
        self.canvas.delete("overlay")
        self.state = "play"
        self.score = 0
        self.combo = 0
        self.max_health = 5
        self.health = self.max_health
        self.upgrades = 0
        self.inv = 0.0
        self.shield_ready = False
        self.dash_cd = 0.0
        self.sector_i = 0
        self.run_time = 0.0
        self.sectors = self.roll_sectors()
        self.player.x, self.player.y = 130, HEIGHT / 2
        self.player.vx = self.player.vy = 0
        self.player.set_upgrades(0)
        self.enemies_on = True
        self.enter_sector(0)

    def enter_sector(self, i):
        self.sector_i = i
        self.set_palette(PALETTES[i])
        self.sector = self.sectors[i](self)
        self.enemies_on = self.sector.enemies
        self.sector.start()
        self.set_console(self.sector.console, self.sector.hint())
        self.fx.ring(self.player.x, self.player.y, self.pal["acc"], 20, 220, 0.8, 4)
        self.sweep_t = 0.0
        self.cmd("enter_sector(%d)  ▸ %s" % (i + 1, self.sector.name))

    def finish_sector(self):
        if self.state != "play":
            return
        s = self.sector
        s.cleanup()
        self.sector = None
        bonus = 400 * self.health + int(max(0, 1500 - self.run_time * 8))
        self.score += bonus
        self.upgrades += 1
        self.player.set_upgrades(min(3, self.upgrades))
        if self.upgrades == 1:
            self.shield_ready = True
        if self.upgrades == 4:
            self.max_health += 1
            self.health = self.max_health
        self.fx.ring(self.player.x, self.player.y, C_OK, 30, 420, 1.0, 6)
        self.fx.burst(self.player.x, self.player.y, self.pal["acc"], 40, 340, 5, 1.0)
        self.shake(6)
        self.set_console(False, "")
        rew = REWARDS[self.sector_i] if self.sector_i < len(REWARDS) else ""
        self.say("✅ SEKTOR %d (%s) ZALICZONY   (+%d pkt bonusu)"
                 % (self.sector_i + 1, s.name, bonus),
                 ("NOWE ULEPSZENIE: " + rew) if rew else
                 "Trwa ostatnia stabilizacja...", C_OK)
        self.objective("SEKTOR %d ZALICZONY — przygotuj się..." % (self.sector_i + 1))
        if rew:
            self.fx.text(self.player.x, self.player.y - 60, "ULEPSZENIE!", "#FFE066", 1.6, 70,
                         self.f_ui)
        nxt = self.sector_i + 1
        if nxt >= len(self.sectors):
            self.later(1500, lambda: self.end_game(True))
        else:
            self.later(2100, lambda: self.enter_sector(nxt))

    def end_game(self, win):
        if self.state == "over":
            return
        self.state = "over"
        if self.sector:
            self.sector.cleanup()
            self.sector = None
        self.enemies_on = False
        self.set_console(False, "")
        c = self.canvas
        if win:
            self.score += 5000 + 800 * self.health
            self.set_palette({"top": "#0E7C8C", "bot": "#03303A", "fog": "#2FD8E8", "acc": "#FFFFFF"})
            for i in range(26):
                self.later(i * 70, lambda: self.fx.burst(random.uniform(100, WIDTH - 100),
                                                         random.uniform(100, HEIGHT - 100),
                                                         random.choice(["#4FF3FF", "#FFE066", "#7CFFE8"]),
                                                         18, 260, 4, 0.9))
        rank, title = "D", ""
        for th, r, t in RANKS:
            if self.score >= th:
                rank, title = r, t
                break
        box = c.create_rectangle(WIDTH / 2 - 300, 150, WIDTH / 2 + 300, HEIGHT - 120,
                                 fill=mix(DEEP, "#000000", 0.55),
                                 outline=C_OK if win else C_BAD, width=3, tags="overlay")
        self.to_layer(box, "L_HUD")

        def T(y, txt, font, fill):
            i = c.create_text(WIDTH / 2, y, text=txt, font=font, fill=fill, tags="overlay")
            self.to_layer(i, "L_HUD")
        if win:
            T(210, "EKOSYSTEM URATOWANY", self.f_huge, "#4FF3FF")
            T(258, "Rdzeń oceanu bije równym rytmem. Woda znowu świeci.",
              self.f_small, C_TXT)
        else:
            T(210, "MIKROBA ZGINĘŁA", self.f_huge, C_BAD)
            T(258, "Zanieczyszczenie okazało się silniejsze. Ale kod można napisać od nowa.",
              self.f_small, C_TXT)
        T(316, "WYNIK: %d PKT" % self.score, self.f_big, "#FFE066")
        T(360, "SEKTORY: %d / 6      CZAS: %d s" % (self.sector_i + (1 if win else 0),
                                                    int(self.run_time)), self.f_ui, C_TXT)
        T(404, "RANGA  %s  —  %s" % (rank, title), self.f_big, C_OK if win else C_WARN)
        T(HEIGHT - 160, "KLIKNIJ  LUB  NACIŚNIJ  R  —  ZAGRAJ PONOWNIE", self.f_ui, "#FFFFFF")
        self.say("KONIEC GRY — wynik %d pkt, ranga %s." % (self.score, rank),
                 "Kliknij ekran lub naciśnij R, aby zagrać jeszcze raz.", C_OK if win else C_BAD)
        self.objective("KONIEC GRY")

    def hard_reset(self):
        self.gen += 1
        for a in self.pending:
            try:
                self.root.after_cancel(a)
            except Exception:
                pass
        self.pending = []
        if self.sector:
            try:
                self.sector.cleanup()
            except Exception:
                pass
            self.sector = None
        self.canvas.delete("all")
        self.paused = False
        self.build_world()
        self.show_menu()

    # -- sterowanie -------------------------------------------------------
    def _entry_focused(self):
        return False

    def on_motion(self, e):
        self.mouse = (self.canvas.canvasx(e.x), self.canvas.canvasy(e.y))
        self.use_mouse = True

    def on_leave(self, e):
        self.use_mouse = False

    def on_enter(self, e=None):
        if self.state == "menu":
            self.start_run()
        elif self.state == "over":
            self.hard_reset()

    MOVE_KEYS = ("Left", "Right", "Up", "Down", "KP_Left", "KP_Right", "KP_Up", "KP_Down",
                 "w", "a", "s", "d", "W", "A", "S", "D")

    def on_press(self, e):
        k = e.keysym
        self.key_states[k] = True
        if k in self.MOVE_KEYS:
            self.use_mouse = False
        low = k.lower()
        if low == "p" and self.state == "play" and not self._entry_focused():
            self.toggle_pause()
            return
        if low == "r" and self.state == "over":
            self.hard_reset()
            return
        if k == "Escape":
            if self.state == "play":
                self.toggle_pause()
            return
        if k == "space" and self.state == "play" and not self._entry_focused():
            self.try_dash()
            return
        if self.state == "play" and self.sector and not self.paused:
            if not self._entry_focused():
                self.sector.on_key(k)

    def on_release(self, e):
        self.key_states[e.keysym] = False

    def on_click(self, e):
        x, y = self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)
        self.mouse = (x, y)
        self.use_mouse = True
        if self.state == "menu":
            self.start_run()
            return
        if self.state == "over":
            self.hard_reset()
            return
        if self.state == "play" and not self.paused:
            if self.sector:
                self.sector.on_click(x, y)
            self.try_dash()

    def try_dash(self):
        if self.dash_cd > 0 or self.state != "play":
            return
        ix, iy = self._axis()
        if ix == 0 and iy == 0 and self.use_mouse and self.mouse:
            dx = self.mouse[0] - self.player.x
            dy = self.mouse[1] - self.player.y
            if math.hypot(dx, dy) > 12:
                ix, iy = dx, dy
        if ix == 0 and iy == 0:
            ix = math.cos(self.player.angle)
            iy = math.sin(self.player.angle)
        n = math.hypot(ix, iy) or 1
        self.player.vx = ix / n * 900
        self.player.vy = iy / n * 900
        self.dash_cd = self._dash_cd_max()
        self.dash_t = 0.30
        self.inv = max(self.inv, 0.30)
        self.fx.ring(self.player.x, self.player.y, "#FFFFFF", 14, 90, 0.35, 3)
        self.fx.burst(self.player.x, self.player.y, self.pal["acc"], 16, 220, 3, 0.4,
                      base=math.atan2(-iy, -ix), spread=1.4)

    def _axis(self):
        ks = self.key_states
        wasd = True
        ix = iy = 0.0
        if ks.get("Left") or ks.get("KP_Left") or (wasd and ks.get("a")):
            ix -= 1
        if ks.get("Right") or ks.get("KP_Right") or (wasd and ks.get("d")):
            ix += 1
        if ks.get("Up") or ks.get("KP_Up") or (wasd and ks.get("w")):
            iy -= 1
        if ks.get("Down") or ks.get("KP_Down") or (wasd and ks.get("s")):
            iy += 1
        return ix, iy

    def toggle_pause(self):
        self.paused = not self.paused
        c = self.canvas
        if self.paused:
            box = c.create_rectangle(WIDTH / 2 - 200, HEIGHT / 2 - 70, WIDTH / 2 + 200,
                                     HEIGHT / 2 + 70, fill=mix(DEEP, "#000000", 0.5),
                                     outline=C_OK, width=2, tags="pause")
            self.to_layer(box, "L_HUD")
            t1 = c.create_text(WIDTH / 2, HEIGHT / 2 - 14, text="PAUZA", font=self.f_huge,
                               fill=C_OK, tags="pause")
            t2 = c.create_text(WIDTH / 2, HEIGHT / 2 + 34, text="P — powrót do gry",
                               font=self.f_ui, fill=C_TXT, tags="pause")
            self.to_layer(t1, "L_HUD")
            self.to_layer(t2, "L_HUD")
        else:
            c.delete("pause")
            self.last = time.perf_counter()

    # -- gracz ------------------------------------------------------------
    def _update_player(self, dt):
        p = self.player
        ix, iy = self._axis()
        if ix == 0 and iy == 0 and self.use_mouse and self.mouse:
            dx, dy = self.mouse[0] - p.x, self.mouse[1] - p.y
            d = math.hypot(dx, dy)
            if d > 10:
                f = min(1.0, d / 110.0)
                ix, iy = dx / d * f, dy / d * f
        if self.state != "play":
            ix = iy = 0
        accel = 1650 + 220 * (1 if self.upgrades >= 2 else 0)
        vmax = 330 + (55 if self.upgrades >= 2 else 0)
        if ix or iy:
            n = math.hypot(ix, iy)
            p.vx += ix / n * accel * dt
            p.vy += iy / n * accel * dt
        drag = 3.4 if self.dash_t <= 0 else 1.2
        p.vx -= p.vx * drag * dt
        p.vy -= p.vy * drag * dt
        sp = math.hypot(p.vx, p.vy)
        lim = vmax if self.dash_t <= 0 else 950
        if sp > lim:
            p.vx *= lim / sp
            p.vy *= lim / sp
        p.x += p.vx * dt
        p.y += p.vy * dt
        r = p.size * 0.9
        if p.x < r:
            p.x, p.vx = r, abs(p.vx) * 0.3
        if p.x > WIDTH - r:
            p.x, p.vx = WIDTH - r, -abs(p.vx) * 0.3
        if p.y < r + 50:
            p.y, p.vy = r + 50, abs(p.vy) * 0.3
        if p.y > HEIGHT - r:
            p.y, p.vy = HEIGHT - r, -abs(p.vy) * 0.3
        if sp > 12:
            p.face(dt, math.atan2(p.vy, p.vx))
        else:
            p.face(dt)
        p.draw(dt, sp)

        self.dash_cd = max(0.0, self.dash_cd - dt)
        self.dash_t = max(0.0, self.dash_t - dt)
        if self.dash_t > 0 and random.random() < 0.8:
            self.fx.spawn(p.x, p.y, random.uniform(-40, 40), random.uniform(-40, 40),
                          self.pal["acc"], 4, 0.35)
        if self.inv > 0:
            self.inv = max(0.0, self.inv - dt)
            blink = int(self.inv * 14) % 2 == 0
            self.canvas.itemconfigure(p.body, outline="#FFFFFF" if blink else shade(p.body_col, 1.35))
        if self.upgrades >= 1 and not self.shield_ready:
            self.shield_cd -= dt
            if self.shield_cd <= 0:
                self.shield_ready = True
                self.fx.ring(p.x, p.y, C_OK, 20, 70, 0.5, 3)
                self.fx.text(p.x, p.y - 44, "TARCZA GOTOWA", C_OK, 1.0)
        if self.combo_timer > 0:
            self.combo_timer -= dt
            if self.combo_timer <= 0 and self.combo:
                self.combo = 0

    def _update_enemies(self, dt):
        p = self.player
        for e in self.enemies:
            if not self.enemies_on:
                for i in e.parts:
                    self.canvas.itemconfigure(i, state="hidden")
                continue
            for i in e.parts:
                if i not in (e.up_shield, e.up_core, e.up_ant, e.up_ant_d):
                    self.canvas.itemconfigure(i, state="normal")
            dy = p.y - e.y
            e.vy += clamp(dy, -1, 1) * 90 * dt
            e.vy -= e.vy * 1.4 * dt
            e.x += e.vx * dt
            e.y += e.vy * dt
            if e.x < -120:
                e.x = WIDTH + random.uniform(60, 260)
                e.y = random.uniform(90, HEIGHT - 60)
                e.vx = -random.uniform(95, 145)
            e.y = clamp(e.y, 70, HEIGHT - 40)
            e.face(dt, math.atan2(e.vy, e.vx))
            e.draw(dt, abs(e.vx))
            if random.random() < 0.05:
                self.fx.spawn(e.x, e.y, random.uniform(-25, 25), random.uniform(-10, 10),
                              "#E0245E", 2.5, 0.6)
            if self.state == "play" and math.hypot(p.x - e.x, p.y - e.y) < p.size * 0.85 + e.size * 0.8:
                if self.damage(1, "Zderzenie z AWAREM — toksycznym drapieżnikiem!"):
                    a = math.atan2(p.y - e.y, p.x - e.x)
                    p.vx += math.cos(a) * 420
                    p.vy += math.sin(a) * 420

    # -- petla ------------------------------------------------------------
    def update(self, dt):
        self.t += dt
        if self.state == "play":
            self.run_time += dt
        self._ambient(dt)
        self._update_player(dt)
        self._update_enemies(dt)
        if self.state == "play" and self.sector:
            self.sector.update(dt)
        self.fx.update(dt)
        self.update_hud()
        if self.state == "play" and self.sector:
            h = self.sector.hint()
            if h != getattr(self, "_last_hint", None):
                self._last_hint = h
                self.hint_lbl.config(text=h)

        if self.shake_amt > 0.2:
            self.shake_amt *= (1 - 6.0 * dt)
            self.sx = random.uniform(-1, 1) * self.shake_amt
            self.sy = random.uniform(-1, 1) * self.shake_amt
        else:
            self.shake_amt = 0.0
            self.sx = self.sy = 0.0
        self.canvas.xview_moveto((PAD + self.sx) / (WIDTH + 2.0 * PAD))
        self.canvas.yview_moveto((PAD + self.sy) / (HEIGHT + 2.0 * PAD))

    def loop(self):
        now = time.perf_counter()
        dt = now - self.last
        self.last = now
        if dt > 0.06:
            dt = 0.06
        if not self.paused:
            try:
                self.update(dt)
            except tk.TclError:
                return
        self.root.after(FRAME_MS, self.loop)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    Game(root)
    root.mainloop()
