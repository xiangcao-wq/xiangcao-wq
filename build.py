#!/usr/bin/env python3
"""Compile profile.json into README.md and the SVG images in assets/.

Run:  python3 build.py              (art seeded by today's date, UTC)
      python3 build.py 2026-12-25   (art seeded by any string you like)
No dependencies beyond the Python standard library.
"""

import datetime
import glob
import html
import json
import os
import random
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(ROOT, "assets")

MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"

THEMES = {
    "dark": {
        "panel": "#161B22", "stroke": "#30363D", "text": "#E6EDF3", "muted": "#8B949E",
        "name": "#F0F6FC", "title": "#4493F8", "accent": "#FFA657", "pill": "#9198A1",
        "ink": "#EDEBE6",
        "palettes": [("#FF5A36", "#3B5BFF"), ("#FFA657", "#79C0FF"), ("#F778BA", "#7EE787"),
                     ("#FACC15", "#FF5A36"), ("#A371F7", "#FFA657")],
        "tints": ["rgba(121,192,255,0.20)", "rgba(255,166,87,0.20)", "rgba(126,231,135,0.20)",
                  "rgba(210,168,255,0.22)", "rgba(255,123,114,0.20)"],
    },
    "light": {
        "panel": "#F6F8FA", "stroke": "#D1D9E0", "text": "#1F2328", "muted": "#59636E",
        "name": "#1F2328", "title": "#0969DA", "accent": "#BC4C00", "pill": "#59636E",
        "ink": "#1F2328",
        "palettes": [("#D1361A", "#2F4BE0"), ("#BC4C00", "#0969DA"), ("#BF3989", "#1A7F37"),
                     ("#B08800", "#D1361A"), ("#8250DF", "#BC4C00")],
        "tints": ["rgba(9,105,218,0.13)", "rgba(188,76,0,0.13)", "rgba(26,127,55,0.14)",
                  "rgba(130,80,223,0.14)", "rgba(207,34,46,0.12)"],
    },
}

esc = lambda s: html.escape(str(s), quote=True)
pct = lambda t, T: f"{max(0.0, min(100.0, t / T * 100)):.3f}%"


def cells(s):
    """Display width in monospace cells (wide East Asian characters count as 2)."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def tokenize(text):
    """A toy tokenizer: words and punctuation, each carrying its leading space."""
    return re.findall(r"\s?[^\W_]+|\s?'[^\W_]+|\s?[^\s\w]|\s?_", text)


# ---------------------------------------------------------------- generative art

def make_art(seed, cols, rows):
    """Decide the day's tiles once, so light and dark versions show the same piece."""
    rnd = random.Random(seed)
    palette = rnd.randrange(5)
    # Each day gets its own mix of shapes, so pieces differ in mood, not just layout.
    weights = {
        "quarter": rnd.uniform(3, 7), "half": rnd.uniform(0.5, 3),
        "dot": rnd.uniform(0.3, 2), "ring": rnd.uniform(0.2, 1.2), "empty": rnd.uniform(0.8, 2.5),
    }
    accent_rate = rnd.uniform(0.08, 0.18)
    kinds, w = list(weights), list(weights.values())
    tiles = []
    for r in range(rows):
        for c in range(cols):
            kind = rnd.choices(kinds, w)[0]
            roll = rnd.random()
            role = "a1" if roll < accent_rate else "a2" if roll < accent_rate * 1.7 else "ink"
            tiles.append((c, r, kind, rnd.choice([0, 90, 180, 270]), role))
    return palette, tiles


def art_svg(art, s, t):
    palette, tiles = art
    a1, a2 = t["palettes"][palette]
    color = {"ink": t["ink"], "a1": a1, "a2": a2}
    out = []
    for c, r, kind, rot, role in tiles:
        x, y, col = c * s, r * s, color[role]
        cx, cy = x + s / 2, y + s / 2
        tf = f' transform="rotate({rot} {cx} {cy})"' if rot else ""
        if kind == "quarter":
            out.append(f'<path d="M{x} {y}h{s}a{s} {s} 0 0 1 -{s} {s}z" fill="{col}"{tf}/>')
        elif kind == "half":
            out.append(f'<path d="M{x} {y+s}a{s/2} {s/2} 0 0 1 {s} 0z" fill="{col}"{tf}/>')
        elif kind == "dot":
            out.append(f'<circle cx="{cx}" cy="{cy}" r="{s*0.3:.1f}" fill="{col}"/>')
        elif kind == "ring":
            out.append(f'<circle cx="{cx}" cy="{cy}" r="{s*0.27:.1f}" fill="none" stroke="{col}" stroke-width="6"/>')
    return "\n".join(out)


# ---------------------------------------------------------------- banner

def layout_line(tokens, x0, max_x, cw, chip_pad, gap):
    x, row, placed = x0, 0, []
    for tok in tokens:
        core = tok.lstrip(" ")
        lead = len(tok) - len(core)
        w = (lead + cells(core)) * cw + 2 * chip_pad
        if x + w > max_x and x > x0:
            x, row = x0, row + 1
        placed.append((x, row, w, lead, core))
        x += w + gap
    end = (x + 2, row)
    if x + 18 > max_x:
        end = (x0, row + 1)
    return placed, end


def banner_svg(name, tagline, lines, sampling_line, seed, art, t):
    W, pad = 1200, 56
    s, cols, rows = 48, 25, 6
    art_h = s * rows
    cw, chip_pad, gap, row_h, chip_h, fs = 20.4, 5, 3, 60, 46, 34
    # Timing for the loop (seconds)
    step, lead_in, hold, fade, rest = 0.075, 0.35, 2.4, 0.35, 0.3

    name_fs = min(112, int((W - 2 * pad) / (max(len(name), 1) * 0.6)))
    name_y = art_h + 34 + int(name_fs * 0.82)
    tag_y = name_y + 44
    rule1 = tag_y + 34
    label_y = rule1 + 40
    tok_top = label_y + 22
    rule2 = tok_top + 2 * row_h + 12
    foot_y = rule2 + 32
    H = foot_y + 26

    # Plan every line's timeline first: one shared cycle of length T.
    plans, t0 = [], 0.0
    for text in lines:
        toks = tokenize(text)
        placed, end = layout_line(toks, pad, W - pad, cw, chip_pad, gap)
        if max(p[1] for p in placed) > 1 or end[1] > 1:
            sys.exit(f'This banner line is too long to fit on two rows, please shorten it:\n  "{text}"')
        appear = [t0 + lead_in + i * step for i in range(len(toks))]
        done = appear[-1] + hold
        plans.append((placed, end, t0, appear, done))
        t0 = done + fade + rest
    T = t0

    css, body, kf = [], [], 0

    def visible(start, end, fade_out=0.0):
        """A keyframe that is hidden, shows from `start`, hides at `end` (fading over `fade_out`)."""
        nonlocal kf
        kf += 1
        stops = ["0%{opacity:0}"]
        if start > 0:
            stops.append(f"{pct(start - 0.001, T)}{{opacity:0}}")
        stops.append(f"{pct(start, T)}{{opacity:1}}")
        stops.append(f"{pct(end - (0 if fade_out else 0.001), T)}{{opacity:1}}")
        stops.append(f"{pct(end + fade_out, T)}{{opacity:0}}")
        stops.append("100%{opacity:0}")
        css.append(f"@keyframes k{kf}{{{''.join(stops)}}}")
        return f'class="k" style="animation-name:k{kf}"'

    for li, (placed, end, start, appear, done) in enumerate(plans):
        cursor_at = [(pad + 2, 0)] + [(x + w + 2, row) for x, row, w, _, _ in placed]
        times = [start] + appear
        for i, (x, row, w, lead, core) in enumerate(placed):
            y = tok_top + row * row_h
            tint = t["tints"][(i + li) % len(t["tints"])]
            body.append(
                f'<g {visible(appear[i], done, fade)} data-l="{li}">'
                f'<rect x="{x}" y="{y}" width="{w}" height="{chip_h}" rx="6" fill="{tint}"/>'
                f'<text x="{x + chip_pad + lead * cw:.1f}" y="{y + 34}" font-family="{esc(MONO)}" font-size="{fs}" '
                f'font-weight="500" fill="{t["text"]}" textLength="{cells(core) * cw:.1f}" '
                f'lengthAdjust="spacingAndGlyphs">{esc(core)}</text></g>'
            )
        # The cursor rides just ahead of the stream, then blinks while the line holds.
        for i in range(len(times)):
            cx, crow = cursor_at[i] if i < len(placed) else end
            last = i == len(times) - 1
            stop = done if last else times[i + 1]
            y = tok_top + crow * row_h + 4
            rect = f'<rect x="{cx}" y="{y}" width="18" height="38" fill="{t["accent"]}"/>'
            if last:
                rect = f'<g class="blink">{rect}</g>'
            body.append(f'<g {visible(times[i], stop)} data-c="{li}">{rect}</g>')

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="{esc(name + ". " + lines[0])}">',
        "<style>",
        f".k{{opacity:0;animation-duration:{T:.2f}s;animation-iteration-count:infinite;animation-timing-function:linear}}",
        ".blink{animation:blink 1s step-end infinite}@keyframes blink{50%{opacity:0}}",
        *css,
        "@media (prefers-reduced-motion: reduce){.k,.blink{animation:none}"
        '[data-l="0"]{opacity:1}}',
        "</style>",
        f'<defs><clipPath id="clip"><rect width="{W}" height="{H}" rx="16"/></clipPath></defs>',
        f'<g clip-path="url(#clip)">',
        f'<rect width="{W}" height="{H}" fill="{t["panel"]}"/>',
        art_svg(art, s, t),
        f'<line x1="0" y1="{art_h}" x2="{W}" y2="{art_h}" stroke="{t["stroke"]}"/>',
        "</g>",
        f'<text x="{pad - 4}" y="{name_y}" font-family="{esc(SANS)}" font-size="{name_fs}" font-weight="800" '
        f'letter-spacing="{-name_fs * 0.03:.1f}" fill="{t["name"]}">{esc(name)}</text>',
        f'<text x="{pad}" y="{tag_y}" font-family="{esc(MONO)}" font-size="20" fill="{t["muted"]}">{esc(tagline)}</text>',
        f'<line x1="{pad}" y1="{rule1}" x2="{W - pad}" y2="{rule1}" stroke="{t["stroke"]}" stroke-dasharray="5 5"/>',
        f'<text x="{pad}" y="{label_y}" font-family="{esc(MONO)}" font-size="13" letter-spacing="1.4" fill="{t["muted"]}">COMPLETION · STREAMING</text>',
        f'<text x="{W - pad}" y="{label_y}" font-family="{esc(MONO)}" font-size="13" letter-spacing="1.4" fill="{t["muted"]}" text-anchor="end">{len(lines)} SAMPLES · LOOPING</text>',
        *body,
        f'<line x1="{pad}" y1="{rule2}" x2="{W - pad}" y2="{rule2}" stroke="{t["stroke"]}" stroke-dasharray="5 5"/>',
        f'<text x="{pad}" y="{foot_y}" font-family="{esc(MONO)}" font-size="14" fill="{t["muted"]}">art: seed {esc(seed)} · redrawn daily</text>',
        f'<text x="{W - pad}" y="{foot_y}" font-family="{esc(MONO)}" font-size="14" fill="{t["muted"]}" text-anchor="end">{esc(sampling_line)}</text>',
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="16" fill="none" stroke="{t["stroke"]}"/>',
        "</svg>",
    ]
    return "\n".join(out)


# ---------------------------------------------------------------- cards

def wrap(text, max_px, px_per_char, max_lines):
    words, lines, cur = text.split(), [], ""
    limit = int(max_px / px_per_char)
    for wd in words:
        trial = (cur + " " + wd).strip()
        if len(trial) <= limit:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: max(0, limit - 1)].rstrip() + "…"
    return lines


def card_svg(p, label, t):
    W, H, pad = 440, 200, 24
    title = p["name"] if len(p["name"]) <= 30 else p["name"][:29] + "…"
    desc = wrap(p.get("description", ""), W - 2 * pad, 7.9, 2)
    pills = list(p.get("stack", [])) + (["live demo ↗"] if p.get("demo") else [])
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="{esc(p["name"] + " — " + p.get("description", ""))}">',
        f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="8" fill="{t["panel"]}" stroke="{t["stroke"]}"/>',
        f'<text x="{pad}" y="38" font-family="{esc(MONO)}" font-size="12" fill="{t["accent"]}">{esc(label)}</text>',
        f'<text x="{pad}" y="72" font-family="{esc(SANS)}" font-size="20" font-weight="600" fill="{t["title"]}">{esc(title)}</text>',
    ]
    for i, ln in enumerate(desc):
        out.append(f'<text x="{pad}" y="{102 + i*22}" font-family="{esc(SANS)}" font-size="14.5" fill="{t["pill"]}">{esc(ln)}</text>')
    x = pad
    for pill in pills:
        w = round(len(pill) * 7.3 + 22)
        if x + w > W - pad:
            break
        out.append(f'<rect x="{x+0.5}" y="152.5" width="{w}" height="24" rx="12" fill="none" stroke="{t["stroke"]}"/>')
        out.append(f'<text x="{x + w/2 + 0.5}" y="169" font-family="{esc(MONO)}" font-size="12" fill="{t["pill"]}" text-anchor="middle">{esc(pill)}</text>')
        x += w + 8
    out.append("</svg>")
    return "\n".join(out)


# ---------------------------------------------------------------- README

def picture(name, alt, width):
    return (f'<picture><source media="(prefers-color-scheme: dark)" srcset="assets/{name}-dark.svg">'
            f'<img src="assets/{name}-light.svg" width="{width}" alt="{esc(alt)}"></picture>')


def build(seed):
    with open(os.path.join(ROOT, "profile.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    name = cfg["name"]
    fill = lambda s: str(s).replace("{name}", name)
    lines = [fill(x) for x in cfg["intros"]]

    os.makedirs(ASSETS, exist_ok=True)
    for old in glob.glob(os.path.join(ASSETS, "card-*.svg")) + glob.glob(os.path.join(ASSETS, "header-*.svg")):
        os.remove(old)

    art = make_art(seed, 25, 6)
    for theme, t in THEMES.items():
        with open(os.path.join(ASSETS, f"banner-{theme}.svg"), "w", encoding="utf-8") as f:
            f.write(banner_svg(name, cfg.get("tagline", ""), lines, cfg.get("sampling_line", ""), seed, art, t))

    projects = cfg.get("projects", [])
    card_html = []
    for i, p in enumerate(projects, 1):
        label = f"sample_{i:02d}" + (f" · {p['label']}" if p.get("label") else "")
        for theme, t in THEMES.items():
            with open(os.path.join(ASSETS, f"card-{i}-{theme}.svg"), "w", encoding="utf-8") as f:
                f.write(card_svg(p, label, t))
        href = p.get("demo") or p.get("repo") or "#"
        card_html.append(f'<a href="{esc(href)}">{picture(f"card-{i}", p["name"] + " — " + p.get("description", ""), "400")}</a>')

    rev = datetime.date.today().strftime("%Y.%m")
    rows = "\n".join(
        f"<tr><td><code>{esc(k)}</code></td><td>{esc(fill(v))}</td></tr>" for k, v in cfg["model_card"]
    )
    contact = " · ".join(f"[{esc(label)}]({url})" for label, url in cfg.get("contact", []))

    md = [
        "<!-- Generated by build.py from profile.json. Edit those files, not this one. -->",
        "",
        picture("banner", f"{name}. {lines[0]}", "100%"),
        "",
        f"## Model card <sub><code>rev. {rev}</code></sub>",
        "",
        "<table>",
        rows,
        "</table>",
        "",
    ]
    if card_html:
        md += [
            f"## Sampled outputs <sub><code>{len(card_html)} completions · pinned</code></sub>",
            "",
            "<p>",
            "\n".join(card_html),
            "</p>",
            "",
        ]
    md += [
        "## System prompt",
        "",
        "```text",
        f"[system] {cfg.get('system_prompt', '')}",
        "```",
        "",
        f"→ {contact}" if contact else "",
        "",
        '<p align="center"><code>&lt;|endoftext|&gt;</code><br>',
        '<sub>compiled from <a href="profile.json">profile.json</a> by <a href="build.py">build.py</a> · '
        "banner art redrawn daily</sub></p>",
        "",
    ]
    with open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"Built README.md, banner (seed {seed}), and {len(card_html)} project cards.")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"))
