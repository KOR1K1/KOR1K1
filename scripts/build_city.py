#!/usr/bin/env python3

import datetime as dt
import hashlib
import json
import math
import os
import sys
import urllib.error
import urllib.request
from html import escape
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]

SX = 10.8
SY = 5.4

COLORS = {
    "background": "#171410",
    "paper": "#efdfbd",
    "muted": "#b59969",
    "quiet": "#8b7960",
    "road": "#25221c",
    "edge": "#4b4030",
    "left": "#8f552f",
    "right": "#603c28",
    "roof": "#c19a63",
    "window": "#ffd38a",
}


def esc(value):
    return escape(str(value), quote=True)


def number(value):
    return f"{int(value):,}".replace(",", " ")


def stable_seed(value):
    digest = hashlib.sha256(str(value).encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def project(x, y, z=0):
    return ((x - y) * SX, (x + y) * SY - z)


def points(coords):
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in coords)


def polygon(coords, fill, stroke=None, width=0.5, extra=""):
    outline = (
        f' stroke="{stroke}" stroke-width="{width}" '
        'stroke-linejoin="round"'
        if stroke
        else ""
    )
    return (
        f'<polygon points="{points(coords)}" fill="{fill}"'
        f'{outline} {extra}/>'
    )


def line(a, b, color, width=1, extra=""):
    return (
        f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" '
        f'x2="{b[0]:.2f}" y2="{b[1]:.2f}" '
        f'stroke="{color}" stroke-width="{width}" '
        f'stroke-linecap="round" {extra}/>'
    )


def ground(x, y, w, d, color, z=0, stroke=None):
    return polygon(
        [
            project(x, y, z),
            project(x + w, y, z),
            project(x + w, y + d, z),
            project(x, y + d, z),
        ],
        color,
        stroke,
    )


def box(
    x, y, w, d, h,
    roof=None, left=None, right=None, z=0,
    roof_class="",
):
    roof = roof or COLORS["roof"]
    left = left or COLORS["left"]
    right = right or COLORS["right"]

    a = project(x, y, z + h)
    b = project(x + w, y, z + h)
    c = project(x + w, y + d, z + h)
    e = project(x, y + d, z + h)

    b0 = project(x + w, y, z)
    c0 = project(x + w, y + d, z)
    e0 = project(x, y + d, z)

    return "".join([
        polygon([b0, c0, c, b], right),
        polygon([e0, c0, c, e], left),
        polygon(
            [a, b, c, e],
            roof,
            "#e1ba7b",
            0.35,
            f'class="{roof_class}"' if roof_class else "",
        ),
    ])


def text(x, y, content, size=12, color=None, weight=500,
         anchor="start", spacing=0, extra=""):
    color = color or COLORS["paper"]
    return (
        f'<text x="{x}" y="{y}" fill="{color}" '
        f'font-size="{size}" font-weight="{weight}" '
        f'text-anchor="{anchor}" letter-spacing="{spacing}" '
        f'{extra}>{esc(content)}</text>'
    )


def path_part(coords):
    return (
        "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in coords) + "Z"
    )


def window_paths(x, y, w, d, h, seed):
    lit = []
    dark = []

    floors = min(7, max(0, int((h - 6) / 7)))

    for level in range(floors):
        z = 5 + level * 7

        front = [
            project(x + w * 0.23, y + d + 0.006, z),
            project(x + w * 0.64, y + d + 0.006, z),
            project(x + w * 0.64, y + d + 0.006, z + 2.2),
            project(x + w * 0.23, y + d + 0.006, z + 2.2),
        ]

        side = [
            project(x + w + 0.006, y + d * 0.25, z),
            project(x + w + 0.006, y + d * 0.64, z),
            project(x + w + 0.006, y + d * 0.64, z + 2.2),
            project(x + w + 0.006, y + d * 0.25, z + 2.2),
        ]

        for face, quad in enumerate((front, side)):
            is_lit = ((seed >> ((level + face * 3) % 24)) & 3) != 0
            (lit if is_lit else dark).append(path_part(quad))

    animation = ' class="twinkle"' if seed % 13 == 0 else ""

    return (
        f'<path d="{" ".join(dark)}" fill="#473525"/>'
        f'<path d="{" ".join(lit)}" fill="#ffd38a"{animation} '
        f'style="animation-delay:-{seed % 9}s"/>'
    )


def house(x, y, day):
    if day is None:
        return ground(
            x, y, 0.73, 0.73, "#302b22", z=1, stroke="#514330"
        )

    date = day["date"]
    count = day["count"]
    seed = stable_seed(date)

    w = 0.70 + (seed % 3) * 0.045
    d = 0.70 + ((seed >> 3) % 3) * 0.045

    h = 3.5 if count == 0 else min(
        72, 9 + 9 * math.log2(count + 1)
    )

    roof_colors = ["#b59969", "#c39e6b", "#d0ac75", "#a88759"]
    roof = "#655640" if count == 0 else roof_colors[seed % 4]
    left = "#554331" if count == 0 else "#8f552f"
    right = "#3e3328" if count == 0 else "#65412c"

    label = f"{date}: {count} contributions"

    out = [
        f'<g class="lot" data-date="{esc(date)}" '
        f'data-count="{count}" tabindex="0" role="img" '
        f'aria-label="{esc(label)}">',
        f"<title>{esc(label)}</title>",
        ground(x + 0.18, y + 0.18, w + 0.18, d + 0.18, "#201c17"),
        box(
            x, y, w, d, h,
            roof=roof, left=left, right=right,
            roof_class="roof",
        ),
    ]

    if count > 0:
        out.append(window_paths(x, y, w, d, h, seed))

        if seed % 4 == 0:
            out.append(box(
                x + 0.18, y + 0.18, 0.25, 0.28, 2.8,
                roof="#b7a17c",
                left="#766047",
                right="#514332",
                z=h,
            ))

        if count >= 10 and seed % 3 == 0:
            a = project(x + w * 0.65, y + d * 0.45, h)
            b = project(x + w * 0.65, y + d * 0.45, h + 10)
            out.append(line(a, b, "#d7b884", 0.8))
            out.append(
                f'<circle cx="{b[0]:.2f}" cy="{b[1]:.2f}" '
                'r="1.1" fill="#ffd38a" class="twinkle"/>'
            )

    out.append("</g>")
    return "".join(out)


def tree(x, y, seed=0):
    h = 8 + seed % 5
    base = project(x, y, 1)
    stem = project(x, y, 5)
    peak = project(x, y, h + 4)

    a = project(x - 0.30, y - 0.30, 5)
    b = project(x + 0.30, y - 0.30, 5)
    c = project(x + 0.30, y + 0.30, 5)
    d = project(x - 0.30, y + 0.30, 5)

    return "".join([
        line(base, stem, "#8c6e48", 1.4),
        polygon([a, b, peak], "#8b8960"),
        polygon([b, c, peak], "#555b40"),
        polygon([c, d, peak], "#73734d"),
        polygon([d, a, peak], "#a29b6a"),
    ])


def lamp(x, y):
    a = project(x, y, 0)
    b = project(x, y, 10)

    return "".join([
        line(a, b, "#9b825a", 0.8),
        f'<circle cx="{b[0]:.2f}" cy="{b[1]:.2f}" '
        'r="3.8" fill="#ffc879" opacity=".08"/>',
        f'<circle cx="{b[0]:.2f}" cy="{b[1]:.2f}" '
        'r="1.15" fill="#ffd694"/>',
    ])


def car_shape(axis, color):
    w, d = (0.88, 0.40) if axis == "x" else (0.40, 0.88)

    return "".join([
        box(-w / 2, -d / 2, w, d, 2.5,
            roof=color, left="#93613c", right="#493729"),
        box(-w / 4, -d / 4, w / 2, d / 2, 1.9,
            roof="#d8bd8c", left="#544b3b", right="#38392f", z=2.5),
    ])


def traffic():
    out = []

    for axis in ("x", "y"):
        for i in range(5):
            lane = 3.60 + i * 4

            if axis == "x":
                a = project(0.5, lane, 1)
                b = project(31.4, lane, 1)
            else:
                a = project(lane, 0.5, 1)
                b = project(lane, 27.4, 1)

            if i % 2:
                a, b = b, a

            path = (
                f"M{a[0]:.2f},{a[1]:.2f} "
                f"L{b[0]:.2f},{b[1]:.2f}"
            )

            duration = 23 + i * 4 + (3 if axis == "y" else 0)

            out.append(
                '<g class="moving">'
                f'<animateMotion path="{path}" dur="{duration}s" '
                f'begin="-{i * 7 + 4}s" repeatCount="indefinite"/>'
                f'{car_shape(axis, "#bd8b52" if i % 2 else "#d8c49d")}'
                '</g>'
            )

    return "".join(out)


def headquarters(x, y):
    out = [
        box(x + .25, y + .25, 2.65, 2.65, 8,
            roof="#a9895e", left="#765035", right="#4c3527"),
        box(x + .65, y + .65, 1.85, 1.85, 57,
            roof="#c8ac78", left="#a36a3b", right="#70462b", z=8),
        box(x + .90, y + .90, 1.35, 1.35, 8,
            roof="#ebcd91", left="#ac8050", right="#805731", z=65),
        window_paths(x + .65, y + .65, 1.85, 1.85, 65, 1234567),
    ]

    a = project(x + 1.58, y + 1.58, 73)
    b = project(x + 1.58, y + 1.58, 91)

    out.extend([
        line(a, b, "#e9c68a", 1),
        f'<circle cx="{b[0]:.2f}" cy="{b[1]:.2f}" '
        'r="2" fill="#ffe0a4" class="twinkle"/>',
        text(b[0] + 7, b[1] + 3, "01", 11, "#f3d59a", 800),
    ])

    return "".join(out)


def construction(x, y):
    out = [
        box(x + .35, y + .35, 2.3, 2.3, 5,
            roof="#70614a", left="#695037", right="#473827"),
    ]

    # Steel frame: intentionally a construction site, not activity data.
    for dx in (0.55, 2.25):
        for dy in (0.55, 2.25):
            out.append(line(
                project(x + dx, y + dy, 5),
                project(x + dx, y + dy, 29),
                "#b79258", 1.5,
            ))

    for z in (16, 29):
        out.append(ground(
            x + .55, y + .55, 1.7, 1.7, "#796344",
            z=z, stroke="#c3a16d",
        ))

    foot = project(x + 2.65, y + .45, 0)
    top = project(x + 2.65, y + .45, 68)
    end_a = project(x - .3, y + .45, 68)
    end_b = project(x + 3.3, y + .45, 68)

    out.extend([
        line(foot, top, "#d0a261", 2.2),
        line(end_a, end_b, "#d6ad70", 2),
        line(top, (end_a[0], end_a[1] + 7), "#a88756", .8),
        line(
            end_a,
            project(x - .3, y + .45, 37),
            "#cdb483", .8,
        ),
        text(top[0] + 6, top[1] - 7, "RUST", 8, "#cdb483", 700),
    ])

    return "".join(out)


def utility(x, y):
    out = []

    for i in range(3):
        out.append(box(
            x + .38 + i * .86, y + .50, .58, 2.0, 15 + i * 4,
            roof="#a99872", left="#756345", right="#4d4433",
        ))

    for i in range(3):
        out.append(tree(x + .55 + i * .9, y + 2.9, i))

    return "".join(out)


def plaza(x, y):
    out = [
        ground(x + .3, y + .3, 2.6, 2.6, "#706044", z=1),
        box(x + 1.0, y + 1.0, 1.15, 1.15, 4,
            roof="#d0b581", left="#94734a", right="#674e32"),
    ]

    for dx, dy in ((.6, .6), (2.6, .6), (.6, 2.6), (2.6, 2.6)):
        out.append(tree(x + dx, y + dy, int(dx * 10 + dy)))

    p = project(x + 1.58, y + 1.58, 7)
    out.append(text(p[0], p[1], "K", 13, "#f0d6a0", 900, "middle"))

    return "".join(out)


def render_world(data):
    out = []

    # Floating model base.
    out.append(box(
        -.35, -.35, 32.7, 28.7, 9,
        roof="#302b22", left="#675036", right="#3f3225", z=-10,
    ))

    out.append(ground(0, 0, 32, 28, COLORS["road"]))

    # Road markings. All objects use the same isometric projection.
    for y in [3.58 + 4 * i for i in range(6)]:
        out.append(line(
            project(.2, y, .1), project(31.8, y, .1),
            "#6d5940", .65,
            'stroke-dasharray="3 7" opacity=".65"',
        ))

    for x in [3.58 + 4 * i for i in range(7)]:
        out.append(line(
            project(x, .2, .1), project(x, 27.8, .1),
            "#6d5940", .65,
            'stroke-dasharray="3 7" opacity=".65"',
        ))

    # Raised city blocks.
    for by in range(7):
        for bx in range(8):
            out.append(box(
                bx * 4 + .14, by * 4 + .14, 3.12, 3.12, 1.3,
                roof="#40382a", left="#655239", right="#4c3e2b",
            ))

    out.append(traffic())

    objects = []

    def add(x, y, markup):
        objects.append((x + y, x, markup))

    corners = {(0, 0), (7, 0), (0, 6), (7, 6)}

    # Weeks advance in a serpentine order through the city.
    blocks = []
    for by in range(7):
        columns = range(8) if by % 2 == 0 else range(7, -1, -1)
        for bx in columns:
            if (bx, by) not in corners:
                blocks.append((bx, by))

    slots = [
        (0, 0), (1, 0), (2, 0),
        (0, 1), (2, 1),
        (0, 2), (2, 2),
    ]

    start = dt.date.fromisoformat(data["period"]["from"])
    days = {item["date"]: item for item in data["days"]}

    for week, (bx, by) in enumerate(blocks):
        ox, oy = bx * 4, by * 4

        for weekday, (cx, cy) in enumerate(slots):
            day_date = start + dt.timedelta(days=week * 7 + weekday)
            day = days.get(day_date.isoformat())

            x = ox + .37 + cx * .94
            y = oy + .37 + cy * .94

            add(x + .75, y + .75, house(x, y, day))

        add(ox + 1.68, oy + 1.68, tree(ox + 1.68, oy + 1.68, week))

        if week % 3 == 0:
            add(ox + 2.95, oy + 3.05, lamp(ox + 2.95, oy + 3.05))

        if week % 7 == 0:
            add(
                ox + 1.4, oy + 2.65,
                box(
                    ox + 1.20, oy + 2.48, .50, .22, 2.3,
                    roof="#b39868", left="#79603f", right="#52432d",
                ),
            )

    add(3.2, 3.2, headquarters(0, 0))
    add(31.2, 3.2, utility(28, 0))
    add(3.2, 27.2, construction(0, 24))
    add(31.2, 27.2, plaza(28, 24))

    # Painter's order for static isometric geometry.
    for _, _, markup in sorted(objects, key=lambda item: (item[0], item[1])):
        out.append(markup)

    # Model-base edge highlights.
    out.extend([
        line(project(0, 28, 0), project(32, 28, 0), "#ad8550", .8),
        line(project(32, 0, 0), project(32, 28, 0), "#725334", .8),
    ])

    return "".join(out)


SVG_CSS = """
text {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas,
               "Liberation Mono", monospace;
}
.twinkle {
  animation: window-light 7s ease-in-out infinite;
}
@keyframes window-light {
  0%, 100% { opacity: .95; }
  45% { opacity: .95; }
  55% { opacity: .35; }
  70% { opacity: .8; }
}
.lot { outline: none; }
.lot:hover .roof,
.lot:focus .roof {
  stroke: #fff0ca;
  stroke-width: 1.5;
}
.city {
  transform-box: fill-box;
  transform-origin: center;
}
.still .twinkle {
  animation: none !important;
}
.still .moving {
  display: none;
}
@media (prefers-reduced-motion: reduce) {
  .twinkle { animation: none !important; }
  .moving { display: none; }
}
"""


def render_svg(data, mobile=False):
    width, height = (560, 700) if mobile else (820, 716)
    prefix = "m" if mobile else "d"

    margin = 30 if mobile else 38
    scale = .73 if mobile else 1
    origin_x = width / 2 - 2 * SX * scale
    origin_y = 302 if mobile else 240

    stats = data["stats"]

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" fill="none" '
        f'role="img" aria-labelledby="{prefix}-title {prefix}-desc">',
        f'<title id="{prefix}-title">KOR1K — contribution city</title>',
        f'<desc id="{prefix}-desc">'
        f'An animated isometric city built from GitHub activity. '
        f'One block per week, one building per day. '
        f'{stats["contributions"]} contributions in the displayed period. '
        f'Updated {esc(data["updated_at"])}.'
        f'</desc>',
        "<defs>",
        f'<radialGradient id="{prefix}-glow">',
        '<stop offset="0" stop-color="#bd8544" stop-opacity=".16"/>',
        '<stop offset="1" stop-color="#bd8544" stop-opacity="0"/>',
        "</radialGradient>",
        f'<pattern id="{prefix}-grain" width="7" height="7" '
        'patternUnits="userSpaceOnUse">',
        '<circle cx="1" cy="1" r=".45" fill="#b59969" opacity=".075"/>',
        "</pattern>",
        "</defs>",
        f"<style>{SVG_CSS}</style>",
        f'<rect width="{width}" height="{height}" rx="5" '
        f'fill="{COLORS["background"]}"/>',
        f'<rect x=".5" y=".5" width="{width - 1}" height="{height - 1}" '
        'rx="5" stroke="#665035" stroke-opacity=".55"/>',
        f'<rect x="1" y="1" width="{width - 2}" height="{height - 2}" '
        f'fill="url(#{prefix}-grain)"/>',
        f'<ellipse cx="{width / 2}" cy="{origin_y + 190 * scale}" '
        f'rx="{width * .47}" ry="{220 * scale}" '
        f'fill="url(#{prefix}-glow)"/>',
    ]

    out.extend([
        text(margin, 52, "KOR1K", 30 if mobile else 34, weight=900,
             spacing=-1),
        text(
            width - margin, 48, "BACKEND DISTRICT",
            10 if mobile else 11,
            COLORS["muted"], 700, "end", 1.1,
        ),
        text(
            margin, 77,
            "A living record. Built one day at a time.",
            11 if mobile else 12, COLORS["muted"],
        ),
        line((margin, 94), (width - margin, 94), "#56432e", .8),
    ])

    metrics = [
        ("CONTRIBUTIONS", stats["contributions"]),
        ("COMMITS", stats["commits"]),
        ("PULL REQUESTS", stats["prs"]),
        ("REPO STARS", stats["stars"]),
    ]

    for i, (label, value) in enumerate(metrics):
        if mobile:
            x = margin + (i % 2) * 267
            y = 130 + (i // 2) * 65
        else:
            x = margin + i * 190
            y = 135

        out.append(text(x, y, number(value), 28, weight=800))
        out.append(text(
            x, y + 19, label, 9,
            COLORS["muted"], 700, spacing=1.15,
        ))

    out.append(
        f'<g transform="translate({origin_x:.2f} {origin_y}) '
        f'scale({scale})"><g class="city">'
    )
    out.append(render_world(data))
    out.append("</g></g>")

    footer = 587 if mobile else 607

    out.append(line(
        (margin, footer - 15),
        (width - margin, footer - 15),
        "#56432e", .8,
    ))

    out.append(text(
        margin, footer + 5,
        "52 BLOCKS / 52 WEEKS",
        12, COLORS["paper"], 800, spacing=.6,
    ))

    out.append(text(
        margin, footer + 25,
        "ONE BUILDING = ONE DAY",
        10, COLORS["muted"], 600, spacing=.6,
    ))

    out.append(text(
        margin, footer + 44,
        "HEIGHT = CONTRIBUTIONS",
        10, COLORS["muted"], 600, spacing=.6,
    ))

    out.append(text(
        width - margin, footer + 5,
        f'{stats["streak"]} DAY STREAK',
        11, COLORS["paper"], 700, "end",
    ))

    out.append(text(
        width - margin, footer + 25,
        f'{stats["repos"]} PUBLIC REPOS',
        10, COLORS["muted"], 500, "end",
    ))

    out.append(text(
        width - margin, footer + 44,
        "01 / CRYPTOBOT CONTEST",
        9, COLORS["muted"], 500, "end",
    ))

    updated = data["updated_at"].replace("T", " ").replace("+00:00", " UTC")

    out.append(text(
        margin, height - 22,
        f"UPDATED {updated}",
        8 if mobile else 9,
        COLORS["quiet"], 500,
    ))

    out.append(text(
        width - margin, height - 22,
        "KOR1K1 / GITHUB",
        8 if mobile else 9,
        COLORS["quiet"], 500, "end",
    ))

    out.append("</svg>")

    result = "".join(out)

    # Catch malformed XML before publishing an image.
    ET.fromstring(result)

    return result


PAGE_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#171410">
<meta name="description"
      content="KOR1K's living GitHub contribution city.">
<title>KOR1K — Contribution City</title>

<style>
:root {
  color-scheme: dark;
  --bg: #100e0b;
  --paper: #efdfbd;
  --muted: #b59969;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--paper);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

main {
  width: min(100% - 28px, 960px);
  margin: 28px auto 36px;
}

header, footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

header { margin: 0 0 18px; }

a {
  color: var(--paper);
  text-underline-offset: 5px;
  text-decoration-color: #8f552f;
}

a:hover { text-decoration-color: #efdfbd; }

button {
  border: 0;
  border-bottom: 1px solid #8f552f;
  border-radius: 0;
  background: transparent;
  padding: 8px 0;
  color: var(--muted);
  font: inherit;
  font-size: 11px;
  cursor: pointer;
}

button:focus-visible, a:focus-visible {
  outline: 2px solid #efdfbd;
  outline-offset: 5px;
}

.stage svg {
  display: block;
  width: 100%;
  height: auto;
}

.stage .lot { cursor: crosshair; }

.mobile { display: none; }

footer {
  margin-top: 18px;
  align-items: flex-start;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.8;
}

footer p { margin: 0; }

#tooltip {
  position: fixed;
  z-index: 10;
  pointer-events: none;
  max-width: calc(100vw - 24px);
  padding: 10px 13px;
  background: #211a12;
  border-left: 2px solid #d9ac6d;
  box-shadow: 0 8px 24px #0006;
  color: #efdfbd;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-line;
}

#tooltip[hidden] { display: none; }

@media (max-width: 600px) {
  main { width: min(100% - 16px, 560px); margin-top: 16px; }
  header { font-size: 12px; padding: 0 6px; }
  .desktop { display: none; }
  .mobile { display: block; }
  footer { display: block; padding: 0 6px; }
  footer p + p { margin-top: 10px; }
}
</style>
</head>

<body>
<main>
  <header>
    <a href="https://github.com/__USER__">KOR1K / GitHub</a>
    <button id="motion" type="button" aria-pressed="false">
      Pause motion
    </button>
  </header>

  <section class="stage" aria-label="Interactive contribution city">
    <div class="desktop">__DESKTOP__</div>
    <div class="mobile">__MOBILE__</div>
  </section>

  <footer>
    <p>
      Hover, tap or focus a building to inspect a day.<br>
      Building height uses a logarithmic contribution scale.<br>
      The four corner landmarks are decorative, not activity.
    </p>
    <p>
      52 calendar weeks, including the current partial week.<br>
      Stars: owned public non-fork repositories.<br>
      <a href="./data.json">Source snapshot</a>
      &nbsp;·&nbsp;
      <a href="https://github.com/__USER__/__USER__">Source code</a>
    </p>
  </footer>
</main>

<div id="tooltip" role="tooltip" hidden></div>

<script>
const stage = document.querySelector(".stage");
const tooltip = document.querySelector("#tooltip");
const button = document.querySelector("#motion");
const reduced = matchMedia("(prefers-reduced-motion: reduce)");

let paused = reduced.matches;
let frame = 0;
let pointer = null;

function resetCamera() {
  stage.querySelectorAll(".city").forEach(city => {
    city.style.transform = "";
  });
}

function applyMotionPreference() {
  stage.querySelectorAll("svg").forEach(svg => {
    svg.classList.toggle("still", paused);
  });

  button.textContent = paused ? "Enable motion" : "Pause motion";
  button.setAttribute("aria-pressed", String(paused));

  if (paused) resetCamera();
}

button.addEventListener("click", () => {
  paused = !paused;
  applyMotionPreference();
});

reduced.addEventListener("change", event => {
  paused = event.matches;
  applyMotionPreference();
});

function showTooltip(lot, x, y) {
  tooltip.textContent =
    `${lot.dataset.date}\n${Number(lot.dataset.count).toLocaleString()} contributions`;

  tooltip.hidden = false;

  const width = tooltip.offsetWidth;
  const height = tooltip.offsetHeight;

  tooltip.style.left =
    `${Math.max(12, Math.min(x + 16, innerWidth - width - 12))}px`;

  tooltip.style.top =
    `${Math.max(12, Math.min(y + 16, innerHeight - height - 12))}px`;
}

function hideTooltip() {
  tooltip.hidden = true;
}

stage.addEventListener("pointermove", event => {
  const lot = event.target.closest(".lot[data-date]");

  if (lot) {
    showTooltip(lot, event.clientX, event.clientY);
  } else {
    hideTooltip();
  }

  if (paused || event.pointerType === "touch") return;

  pointer = {
    x: event.clientX,
    y: event.clientY,
    svg: event.target.closest("svg")
  };

  if (frame) return;

  frame = requestAnimationFrame(() => {
    frame = 0;
    if (!pointer || paused || !pointer.svg) return;

    const bounds = pointer.svg.getBoundingClientRect();
    const x = (pointer.x - bounds.left) / bounds.width - 0.5;
    const y = (pointer.y - bounds.top) / bounds.height - 0.5;
    const city = pointer.svg.querySelector(".city");

    // Subtle model parallax, not a fake freely rotating 3D camera.
    city.style.transform =
      `translate(${x * 5}px, ${y * 3}px) rotate(${x * 0.65}deg)`;
  });
});

stage.addEventListener("pointerleave", () => {
  pointer = null;
  hideTooltip();
  resetCamera();
});

stage.addEventListener("click", event => {
  const lot = event.target.closest(".lot[data-date]");
  if (lot) showTooltip(lot, event.clientX, event.clientY);
});

stage.addEventListener("focusin", event => {
  const lot = event.target.closest(".lot[data-date]");
  if (!lot) return;

  const bounds = lot.getBoundingClientRect();
  showTooltip(lot, bounds.right, bounds.top);
});

stage.addEventListener("focusout", hideTooltip);

document.addEventListener("keydown", event => {
  if (event.key === "Escape") hideTooltip();
});

window.addEventListener("scroll", hideTooltip, { passive: true });
window.addEventListener("resize", () => {
  hideTooltip();
  resetCamera();
});

applyMotionPreference();
</script>
</body>
</html>
"""


def graphql(query, variables, token):
    payload = json.dumps({
        "query": query,
        "variables": variables,
    }).encode("utf-8")

    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": "kor1k-contribution-city",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API HTTP {error.code}: {details[:1200]}"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"GitHub API connection failed: {error.reason}") from error

    if result.get("errors"):
        messages = "; ".join(
            item.get("message", "Unknown GraphQL error")
            for item in result["errors"]
        )
        raise RuntimeError(f"GitHub GraphQL: {messages}")

    if not result.get("data"):
        raise RuntimeError("GitHub API returned no data.")

    return result["data"]


ACTIVITY_QUERY = """
query Activity($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    login
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions

      contributionCalendar {
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""


REPOSITORIES_QUERY = """
query Repositories($login: String!, $cursor: String) {
  user(login: $login) {
    repositories(
      first: 100
      after: $cursor
      ownerAffiliations: [OWNER]
      privacy: PUBLIC
      isFork: false
    ) {
      totalCount
      nodes {
        stargazerCount
      }
      pageInfo {
        hasNextPage
        endCursor
      }
    }
  }
}
"""


def collect_data(user, token):
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    today = now.date()

    # GitHub contribution weeks start on Sunday.
    sunday = today - dt.timedelta(days=(today.weekday() + 1) % 7)
    start = sunday - dt.timedelta(weeks=51)

    from_time = dt.datetime.combine(
        start, dt.time.min, tzinfo=dt.timezone.utc
    )

    result = graphql(
        ACTIVITY_QUERY,
        {
            "login": user,
            "from": from_time.isoformat(),
            "to": now.isoformat(),
        },
        token,
    )

    account = result.get("user")
    if not account:
        raise RuntimeError(f"GitHub user {user!r} was not found.")

    collection = account["contributionsCollection"]
    counts = {}

    for week in collection["contributionCalendar"]["weeks"]:
        for day in week["contributionDays"]:
            date = dt.date.fromisoformat(day["date"])
            if start <= date <= today:
                counts[day["date"]] = int(day["contributionCount"])

    days = []
    date = start

    while date <= today:
        key = date.isoformat()

        # Do not silently turn missing API data into zero activity.
        if key not in counts:
            raise RuntimeError(f"Contribution calendar is missing {key}.")

        days.append({"date": key, "count": counts[key]})
        date += dt.timedelta(days=1)

    stars = 0
    repos = 0
    cursor = None
    seen_cursors = set()

    while True:
        result = graphql(
            REPOSITORIES_QUERY,
            {"login": user, "cursor": cursor},
            token,
        )

        account_repos = result.get("user")
        if not account_repos:
            raise RuntimeError("User disappeared during repository pagination.")

        connection = account_repos["repositories"]
        repos = int(connection["totalCount"])

        stars += sum(
            int(repo["stargazerCount"])
            for repo in connection["nodes"]
            if repo is not None
        )

        page = connection["pageInfo"]
        if not page["hasNextPage"]:
            break

        cursor = page["endCursor"]
        if not cursor or cursor in seen_cursors:
            raise RuntimeError("Invalid repository pagination cursor.")

        seen_cursors.add(cursor)

    # A zero today does not break yesterday's ongoing streak.
    streak = 0
    index = len(days) - 1

    if index >= 0 and days[index]["count"] == 0:
        index -= 1

    while index >= 0 and days[index]["count"] > 0:
        streak += 1
        index -= 1

    return {
        "schema_version": 1,
        "user": account["login"],
        "updated_at": now.isoformat(),
        "period": {
            "from": start.isoformat(),
            "to": today.isoformat(),
            "calendar_weeks": 52,
            "includes_current_partial_week": True,
        },
        "definitions": {
            "height": "9 + 9*log2(daily contributions + 1), capped at 72",
            "zero_day_height": 3.5,
            "stars": "Owned public non-fork repositories, all pages",
            "streak": (
                "Consecutive active days ending today, or yesterday when "
                "today has zero contributions; limited to displayed period"
            ),
            "visibility": (
                "Activity returned by GitHub for the configured token. "
                "Private activity may be omitted or anonymized by GitHub."
            ),
            "landmarks": "Decorative; not contribution data",
        },
        "stats": {
            "contributions": sum(day["count"] for day in days),
            "commits": int(collection["totalCommitContributions"]),
            "prs": int(collection["totalPullRequestContributions"]),
            "issues": int(collection["totalIssueContributions"]),
            "reviews": int(collection["totalPullRequestReviewContributions"]),
            "stars": stars,
            "repos": repos,
            "streak": streak,
        },
        "days": days,
    }


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def main():
    user = os.environ.get("GH_USER", "KOR1K1").strip()
    token = os.environ.get("GH_TOKEN", "").strip()

    if not token:
        raise RuntimeError(
            "GH_TOKEN is missing. Run through GitHub Actions "
            "or provide a GitHub token locally."
        )

    data = collect_data(user, token)

    desktop = render_svg(data, mobile=False)
    mobile = render_svg(data, mobile=True)

    page = (
        PAGE_TEMPLATE
        .replace("__USER__", esc(data["user"]))
        .replace("__DESKTOP__", desktop)
        .replace("__MOBILE__", mobile)
    )

    snapshot = json.dumps(data, ensure_ascii=False, indent=2) + "\n"

    # Build and validate all content before replacing output files.
    outputs = {
        ROOT / "assets" / "city.svg": desktop,
        ROOT / "assets" / "city-mobile.svg": mobile,
        ROOT / "docs" / "index.html": page,
        ROOT / "docs" / "data.json": snapshot,
    }

    for path, content in outputs.items():
        atomic_write(path, content)

    print(
        f"Built city for {data['user']}: "
        f"{data['stats']['contributions']} contributions, "
        f"{len(data['days'])} days, "
        f"{data['stats']['repos']} public non-fork repositories."
    )

    for path in outputs:
        print(f"  {path.relative_to(ROOT)} — {path.stat().st_size:,} bytes")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"City generation failed: {error}", file=sys.stderr)
        sys.exit(1)
