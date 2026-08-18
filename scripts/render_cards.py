#!/usr/bin/env python3
"""
CARD RENDERER — turns the stats the XP engine already fetched into SVG cards
committed to assets/.

Why not github-readme-stats / streak-stats? Those public instances are heavily
rate-limited and fail often ("Failed to retrieve contributions"). We already hold
the data, so we draw it ourselves. No third-party call, no broken images.

Palette: the reference categorical order, stepped for a dark surface and
validated against #0D1117 (lightness band, chroma floor, CVD separation,
normal-vision floor, contrast — all pass). Language segments also carry direct
labels and 2px gaps, so identity is never colour-alone.
"""

from __future__ import annotations

import html
import os

# ── design tokens ─────────────────────────────────────────────────────────────
SURFACE   = "#0D1117"
PANEL     = "#0b1020"
STROKE    = "#1f2a44"
INK       = "#e6edf3"
INK_DIM   = "#8b949e"
INK_MUTE  = "#5b6577"
GOLD      = "#ffb000"
CYAN      = "#22d3ee"
VIOLET    = "#a78bfa"
GREEN     = "#4ade80"
RED       = "#f87171"

# validated categorical order (dark steps) — see module docstring
CAT = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300",
       "#9085e9", "#e66767"]

# sequential amber ramp for the contribution calendar: one hue, light→dark,
# monotonic in lightness, with an explicit "empty" step
HEAT = ["#161b22", "#4a3208", "#8a5c05", "#c98500", "#ffb000"]

MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace"

def esc(s) -> str:
    return html.escape(str(s), quote=True)

def bar(x, y, w, h, frac, color, track="#161b22", r=3) -> str:
    """A thin bar with rounded data-end, anchored to its track."""
    fw = max(0.0, min(1.0, frac)) * w
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{track}"/>']
    if fw > 1:
        out.append(f'<rect x="{x}" y="{y}" width="{fw:.1f}" height="{h}" rx="{r}" fill="{color}"/>')
    return "".join(out)

def txt(x, y, s, size=12, fill=INK, weight="400", anchor="start", ls="0",
        length=None) -> str:
    # textLength pins the run to an exact width, so a card never breaks just
    # because the viewer's monospace font has different metrics than ours.
    extra = f' textLength="{length:.0f}" lengthAdjust="spacingAndGlyphs"' if length else ""
    return (f'<text x="{x}" y="{y}" font-family="{MONO}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" '
            f'letter-spacing="{ls}"{extra}>{esc(s)}</text>')

def frame(w, h, title=None, accent=GOLD) -> str:
    """Card chrome: surface, hairline border, and a corner tab for the title."""
    out = [
        f'<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="10" fill="{SURFACE}" stroke="{STROKE}"/>',
        f'<rect x="0" y="0" width="{w}" height="3" rx="1.5" fill="{accent}" opacity="0.9"/>',
    ]
    if title:
        inner = len(title) * 7.4
        out += [
            f'<rect x="18" y="16" width="{inner + 28:.0f}" height="20" rx="4" fill="{accent}"/>',
            txt(32, 30, title, 11, "#0b0d14", "700", ls="0", length=inner),
        ]
    return "".join(out)

def svg(w, h, body) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" role="img">{body}</svg>')


# ── 1 · HUD / save file ───────────────────────────────────────────────────────
def hud_card(d) -> str:
    W, H = 860, 300
    b = [frame(W, H, "SAVE FILE 01", GOLD)]

    b.append(txt(W-24, 30, "AUTOSAVED " + d["stamp"], 10, INK_MUTE, anchor="end"))

    # identity block
    b.append(txt(28, 74, d["player"], 24, INK, "700", ls="1"))
    b.append(txt(28, 96, d["klass"], 12, VIOLET))
    b.append(txt(28, 116, d["origin"], 11, INK_DIM))

    # level medallion
    cx = W - 92
    b.append(f'<circle cx="{cx}" cy="92" r="40" fill="{PANEL}" stroke="{GOLD}" stroke-width="2"/>')
    b.append(txt(cx, 88, "LV", 10, GOLD, "700", "middle", ls="2"))
    b.append(txt(cx, 116, str(d["level"]), 30, INK, "700", "middle"))

    # bars
    rows = [
        ("HP", d["hp"], 100, GREEN, d["hp_note"]),
        ("MP", d["mp"], 100, CYAN,  d["mp_note"]),
        ("XP", d["xp_into"], d["xp_need"], GOLD,
         f'{d["xp_into"]:,} / {d["xp_need"]:,}  ·  next: LV {d["level"]+1}'),
    ]
    y = 156
    for label, val, total, col, note in rows:
        b.append(txt(28, y+11, label, 11, INK_DIM, "700", ls="1"))
        b.append(bar(58, y, 300, 14, val/total if total else 0, col))
        b.append(txt(370, y+11, f"{val}/{total}" if label != "XP" else f"{val:,}/{total:,}",
                     11, INK, "700"))
        b.append(txt(470, y+11, note, 11, INK_MUTE))
        y += 30

    # footer chips
    chips = [("COMMITS", d["commits"]), ("PRs", d["prs"]), ("REPOS", d["repos"]),
             ("STARS", d["stars"]), ("STREAK", f'{d["streak"]}d'), ("PARTY", d["followers"])]
    x = 28
    for name, val in chips:
        w = max(96, len(f"{name}{val}") * 8 + 26)
        b.append(f'<rect x="{x}" y="252" width="{w}" height="28" rx="6" fill="{PANEL}" stroke="{STROKE}"/>')
        b.append(txt(x+12, 270, name, 9, INK_MUTE, "700", ls="1"))
        b.append(txt(x+w-12, 270, f"{val:,}" if isinstance(val, int) else val, 12, GOLD, "700", anchor="end"))
        x += w + 8

    return svg(W, H, "".join(b))


# ── 2 · stat tiles ────────────────────────────────────────────────────────────
def stats_card(d) -> str:
    W, H = 424, 300
    b = [frame(W, H, "SCOREBOARD", CYAN)]
    tiles = [
        ("COMMITS",  d["commits"], GOLD),   ("PULL REQUESTS", d["prs"], VIOLET),
        ("ISSUES",   d["issues"],  CYAN),   ("REVIEWS",       d["reviews"], GREEN),
        ("REPOS",    d["repos"],   GOLD),   ("STARS EARNED",  d["stars"], VIOLET),
        ("FORKS",    d["forks"],   CYAN),   ("FOLLOWERS",     d["followers"], GREEN),
    ]
    x0, y0, cw, ch = 20, 52, 192, 56
    for i, (label, val, col) in enumerate(tiles):
        cx = x0 + (i % 2) * (cw + 8)
        cy = y0 + (i // 2) * (ch + 8)
        b.append(f'<rect x="{cx}" y="{cy}" width="{cw}" height="{ch}" rx="8" fill="{PANEL}" stroke="{STROKE}"/>')
        b.append(f'<rect x="{cx}" y="{cy+8}" width="3" height="{ch-16}" rx="1.5" fill="{col}"/>')
        b.append(txt(cx+16, cy+24, label, 9, INK_MUTE, "700", ls="1"))
        b.append(txt(cx+16, cy+45, f"{val:,}", 20, INK, "700"))
    return svg(W, H, "".join(b))


# ── 3 · languages ─────────────────────────────────────────────────────────────
def languages_card(d) -> str:
    W, H = 424, 300
    b = [frame(W, H, "SPELLBOOK", VIOLET)]
    langs = d["languages"][:6]
    if not langs:
        b.append(txt(W/2, 150, "awaiting first XP Engine run", 12, INK_MUTE, anchor="middle"))
        b.append(txt(W/2, 174, "Actions → XP Engine → Run workflow", 11, INK_MUTE, anchor="middle"))
        return svg(W, H, "".join(b))
    total = sum(v for _, v in langs) or 1
    rest = max(0, d["lang_total"] - total)
    rows = [(n, v) for n, v in langs]
    if rest > 0:
        rows.append(("Other", rest))
        total += rest

    # stacked bar, 2px surface gap between segments (secondary encoding: labels below)
    bx, by, bw, bh = 20, 56, W - 40, 16
    x = bx
    for i, (name, v) in enumerate(rows):
        seg = (v / total) * bw
        seg = max(seg - 2, 2) if i < len(rows) - 1 else max(seg, 2)
        col = CAT[i % len(CAT)] if name != "Other" else "#39414f"
        b.append(f'<rect x="{x:.1f}" y="{by}" width="{seg:.1f}" height="{bh}" rx="3" fill="{col}"/>')
        x += seg + 2

    # direct labels — name, swatch and share, so identity is never colour-alone
    y = 104
    for i, (name, v) in enumerate(rows):
        pct = v / total * 100
        col = CAT[i % len(CAT)] if name != "Other" else "#39414f"
        b.append(f'<rect x="20" y="{y-9}" width="10" height="10" rx="2" fill="{col}"/>')
        b.append(txt(38, y, name[:18], 12, INK))
        b.append(txt(W-20, y, f"{pct:5.1f}%", 12, INK_DIM, anchor="end"))
        y += 26
    return svg(W, H, "".join(b))


# ── 4 · contribution calendar ─────────────────────────────────────────────────
def activity_card(d) -> str:
    W, H = 860, 220
    b = [frame(W, H, "COMMIT HEATMAP", GREEN)]
    weeks = d["weeks"]                       # list[list[int]] — 7 per week
    cell, gap = 12, 3
    ox, oy = 26, 62
    peak = max((c for wk in weeks for c in wk), default=0) or 1

    def step(v):
        if v <= 0: return HEAT[0]
        q = v / peak
        if q <= .25: return HEAT[1]
        if q <= .50: return HEAT[2]
        if q <= .75: return HEAT[3]
        return HEAT[4]

    show = weeks[-53:]
    for wi, wk in enumerate(show):
        for di, c in enumerate(wk):
            x = ox + wi * (cell + gap)
            y = oy + di * (cell + gap)
            b.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2.5" fill="{step(c)}"/>')

    # month ticks, recessive
    for label, wi in d["month_ticks"]:
        x = ox + wi * (cell + gap)
        if x < W - 60:
            b.append(txt(x, oy - 8, label, 9, INK_MUTE))

    # legend + headline numbers
    lx = W - 190
    b.append(txt(lx - 34, H - 22, "less", 9, INK_MUTE, anchor="end"))
    for i, c in enumerate(HEAT):
        b.append(f'<rect x="{lx - 28 + i*15}" y="{H-32}" width="11" height="11" rx="2.5" fill="{c}"/>')
    b.append(txt(lx + 54, H - 22, "more", 9, INK_MUTE))

    stats = [(f'{d["total_year"]:,}', "contributions"),
             (f'{d["streak"]}d', "current streak"),
             (f'{d["best_streak"]}d', "longest streak")]
    x = 26
    for val, label in stats:
        b.append(txt(x, H - 20, val, 14, GOLD, "700"))
        b.append(txt(x + len(val) * 9 + 8, H - 20, label, 11, INK_MUTE))
        x += len(val) * 9 + len(label) * 6.6 + 34
    return svg(W, H, "".join(b))


# ── entry point ───────────────────────────────────────────────────────────────
def pending_card(w, h, title, accent) -> str:
    """Seed state, shipped before the workflow has ever run so the README never
    shows a broken image."""
    b = [frame(w, h, title, accent)]
    b.append(txt(w/2, h/2 - 4, "awaiting first XP Engine run", 12, INK_DIM, anchor="middle"))
    b.append(txt(w/2, h/2 + 18, "Actions → XP Engine → Run workflow", 11, INK_MUTE, anchor="middle"))
    return svg(w, h, "".join(b))


def render_all(d, outdir="assets"):
    os.makedirs(outdir, exist_ok=True)
    if d.get("pending"):
        files = {
            "hud.svg":       pending_card(860, 300, "SAVE FILE 01", GOLD),
            "stats.svg":     pending_card(424, 300, "SCOREBOARD", CYAN),
            "languages.svg": pending_card(424, 300, "SPELLBOOK", VIOLET),
            "activity.svg":  pending_card(860, 220, "COMMIT HEATMAP", GREEN),
        }
    else:
        files = {
            "hud.svg":       hud_card(d),
            "stats.svg":     stats_card(d),
            "languages.svg": languages_card(d),
            "activity.svg":  activity_card(d),
        }
    for name, body in files.items():
        with open(os.path.join(outdir, name), "w", encoding="utf-8") as f:
            f.write(body)
    return list(files)


DEMO = {
    "player": "MD YEASIN ARAFAT",
    "klass": "ML ARCHMAGE / SECURITY ROGUE",
    "origin": "origin: a secondhand laptop with a tired fan",
    "stamp": "18 AUG 2026 · 07:43 UTC",
    "level": 4, "xp_into": 8, "xp_need": 1200,
    "hp": 62, "mp": 73,
    "hp_note": "sleep_scheduler still unpatched",
    "mp_note": "7 languages in the spellbook",
    "commits": 96, "prs": 4, "issues": 0, "reviews": 0,
    "repos": 10, "stars": 1, "forks": 0, "followers": 1,
    "streak": 3, "best_streak": 3, "total_year": 142,
    "languages": [("Python", 52), ("C++", 21), ("TypeScript", 14),
                  ("Java", 9), ("C", 6), ("Kotlin", 4)],
    "lang_total": 112,
    "weeks": [[(i * 7 + j * 3) % 9 - 3 for j in range(7)] for i in range(53)],
    "month_ticks": [("Sep", 0), ("Nov", 9), ("Jan", 18), ("Mar", 27), ("May", 35), ("Jul", 44)],
}

if __name__ == "__main__":
    print("wrote:", render_all(DEMO, os.environ.get("OUTDIR", "assets")))
