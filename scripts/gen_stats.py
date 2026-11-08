#!/usr/bin/env python3
"""Generate pixel-game style GitHub status cards (stats / languages / streak) as local SVG files.

No third-party service is needed (so nothing can go "invalid" or rate-limited like github-readme-stats).
Only the Python standard library is used.  Data sources:
  * GitHub REST API when GITHUB_TOKEN is available (accurate language bytes + stars)
  * public github.com HTML pages as fallback (profile, repository list, contribution calendar)
Run:  GH_USER=SofyanTauridOdeMadi python scripts/gen_stats.py
"""
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.request

USER = os.environ.get("GH_USER", "SofyanTauridOdeMadi")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
OUT = os.environ.get("OUT_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")

DK = "#160B0B"; MR = "#6B1118"; RD = "#C62828"; CR = "#F5E9E0"
FONT = "'Trebuchet MS','Segoe UI',Verdana,Arial,sans-serif"
LANG_COLORS = {
    "Dart": "#00B4AB", "HTML": "#E34F26", "Java": "#B07219", "Jupyter Notebook": "#DA5B0B", "Kotlin": "#A97BFF",
    "JavaScript": "#F1E05A", "TypeScript": "#3178C6", "PHP": "#4F5D95", "CSS": "#563D7C", "Python": "#3572A5",
    "C": "#555555", "C++": "#F34B7D", "C#": "#178600", "Swift": "#F05138", "Shell": "#89E051", "Blade": "#F7523F",
    "Vue": "#41B883", "SCSS": "#C6538C", "Go": "#00ADD8", "Rust": "#DEA584", "Ruby": "#701516",
}


# ------------------------------------------------------------------ fetching
def get(url, accept=None):
    req = urllib.request.Request(url, headers={"User-Agent": "stom-readme-stats", **({"Accept": accept} if accept else {})})
    if TOKEN and "api.github.com" in url:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def api(path):
    return json.loads(get("https://api.github.com" + path, "application/vnd.github+json"))


def profile_via_api():
    u = api(f"/users/{USER}")
    repos = api(f"/users/{USER}/repos?per_page=100&type=owner")
    langs = {}
    for r in repos:
        if r.get("fork"):
            continue
        try:
            for k, v in api(f"/repos/{r['full_name']}/languages").items():
                langs[k] = langs.get(k, 0) + v
        except Exception:
            if r.get("language"):
                langs[r["language"]] = langs.get(r["language"], 0) + 1
    return dict(repos=u["public_repos"], followers=u["followers"], following=u["following"],
                stars=sum(r["stargazers_count"] for r in repos), langs=langs)


def profile_via_html():
    p = get(f"https://github.com/{USER}")
    r = get(f"https://github.com/{USER}?tab=repositories")
    fol = re.search(r'text-bold color-fg-default">([\d.,k]+)</span>\s*follower', p)
    fing = re.search(r'text-bold color-fg-default">([\d.,k]+)</span>\s*following', p)

    def num(m):
        if not m:
            return 0
        s = m.group(1).lower().replace(",", "")
        return int(float(s[:-1]) * 1000) if s.endswith("k") else int(float(s))

    names = re.findall(r'itemprop="name codeRepository"[^>]*>\s*([^<\s]+)', r)
    langs = {}
    for l in re.findall(r'itemprop="programmingLanguage">([^<]+)<', r):
        langs[l.strip()] = langs.get(l.strip(), 0) + 1
    stars = sum(int(x.replace(",", "")) for x in re.findall(r'/stargazers"[^>]*>\s*(?:<svg.*?</svg>)?\s*([\d,]+)', r, re.S))
    return dict(repos=len(names), followers=num(fol), following=num(fing), stars=stars, langs=langs)


def contributions():
    h = get(f"https://github.com/users/{USER}/contributions")
    cells = re.findall(r'data-date="(\d{4}-\d\d-\d\d)"\s+id="([^"]+)"\s+data-level="(\d)"', h)
    tips = dict(re.findall(r'for="([^"]+)"[^>]*>\s*(No|\d+)\s+contributions?', h))
    days = []
    for date, cid, level in cells:
        m = re.search(r"-(\d+)-(\d+)$", cid)
        row, col = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
        t = tips.get(cid)
        cnt = 0 if t in (None, "No") and int(level) == 0 else (int(t) if t and t != "No" else (1 if int(level) else 0))
        days.append(dict(date=dt.date.fromisoformat(date), level=int(level), count=cnt, row=row, col=col))
    days.sort(key=lambda d: d["date"])
    m = re.search(r'([\d,]+)\s*contributions?\s*in the last year', re.sub(r"\s+", " ", h))
    total = int(m.group(1).replace(",", "")) if m else sum(d["count"] for d in days)
    return days, total


def streaks(days):
    today = days[-1]["date"] if days else dt.date.today()
    cur_end = None
    best = (0, None, None)
    run = 0; start = None
    for d in days:
        if d["count"] > 0:
            if run == 0:
                start = d["date"]
            run += 1
            if run > best[0]:
                best = (run, start, d["date"])
        else:
            run = 0
    cur = (0, None, None)
    i = len(days) - 1
    if i >= 0 and days[i]["count"] == 0:
        i -= 1  # today may not have a contribution yet
    end = days[i]["date"] if i >= 0 else None
    n = 0
    while i >= 0 and days[i]["count"] > 0:
        n += 1; st = days[i]["date"]; i -= 1
    if n:
        cur = (n, st, end)
    return cur, best


# ------------------------------------------------------------------ svg helpers
def esc(s):
    return html.escape(str(s), quote=True)


def svg(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img">{body}</svg>')


def R(x, y, w, h, c, extra=""):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{c}" shape-rendering="crispEdges" {extra}/>'


def stepped(x, y, w, h, c, n=4):
    return R(x + n, y, w - 2 * n, h, c) + R(x, y + n, w, h - 2 * n, c)


def T(x, y, txt, size, fill, weight="bold", anchor="start", extra=""):
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}" {extra}>{txt}</text>')


def panel(x, y, w, h, n=4):
    return (stepped(x, y, w, h, DK, n + 2) + stepped(x + 3, y + 3, w - 6, h - 6, RD, n + 1)
            + stepped(x + 6, y + 6, w - 12, h - 12, CR, n))


def ribbon(x, y, w, h, title, icon):
    s = 28
    out = f'<polygon points="{x},{y+h} {x},{y+8} {x+8},{y} {x+w},{y} {x+w-s},{y+h}" fill="{DK}" shape-rendering="crispEdges"/>'
    out += f'<polygon points="{x+4},{y+h-4} {x+4},{y+11} {x+11},{y+4} {x+w-3},{y+4} {x+w-s-3},{y+h-4}" fill="{RD}" shape-rendering="crispEdges"/>'
    out += R(x + 12, y + 6, w - 70, 3, "#EF6C6C")
    out += f'<text x="{x+16}" y="{y+h*0.7}" font-size="{int(h*0.5)}" font-family="{FONT}">{icon}</text>'
    out += T(x + 60, y + h * 0.7 + 2, esc(title), int(h * 0.52), DK) + T(x + 58, y + h * 0.7, esc(title), int(h * 0.52), CR)
    return out


def sprite(rows, x, y, s, color):
    out = []
    for j, row in enumerate(rows):
        i = 0
        while i < len(row):
            if row[i] != "#":
                i += 1; continue
            k = i
            while k < len(row) and row[k] == "#":
                k += 1
            out.append(R(x + i * s, y + j * s, (k - i) * s, s, color)); i = k
    return "".join(out)


BOOK = ["#########", "##.....##", "##.###.##", "##.....##", "##.###.##", "##.....##", "##.###.##", "#########", "..#####.."]
STAR = ["....#....", "....#....", "...###...", "#########", ".#######.", "..#####..", "..##.##..", ".##...##.", ".#.....#."]
PERSON = ["...###...", "..#####..", "..#####..", "...###...", ".#######.", "#########", "#########", "#########", "#########"]
FLAME = ["....#....", "...##....", "..###.#..", "..#####..", ".#######.", ".#######.", ".#######.", "..#####..", "...###..."]
FLAME_BIG = [r.replace("#", "#") for r in FLAME]


def tile(x, y, size, bg, rows, s=3):
    o = (size - 9 * s) // 2
    return stepped(x, y, size, size, DK, 5) + stepped(x + 3, y + 3, size - 6, size - 6, bg, 4) + sprite(rows, x + o, y + o, s, "#fff")


def card(w, h, title, icon, body, rw=270):
    return svg(w, h, panel(0, 38, w, h - 38) + body + ribbon(8, 0, rw, 50, title, icon))


def fmt(n):
    return f"{n:,}".replace(",", ".")


def short(d):
    return f"{d.strftime('%b')} {d.day}, {d.year}" if d else ""


# ------------------------------------------------------------------ cards
def stats_card(p, total_contrib):
    rows = [("Repositories", p["repos"], BOOK, "#2F6BC9"), ("Stars Earned", p["stars"], STAR, "#F5A623"),
            ("Followers", p["followers"], PERSON, "#43A047"), ("Contributions (1 yr)", total_contrib, FLAME, "#C62828")]
    b = ""
    for i, (lab, val, spr, col) in enumerate(rows):
        y = 62 + i * 48
        b += tile(36, y, 40, col, spr)
        b += T(92, y + 27, esc(lab), 17, DK)
        b += T(564, y + 31, fmt(val), 28, RD, anchor="end")
        if i < len(rows) - 1:
            b += f'<line x1="36" y1="{y+44}" x2="564" y2="{y+44}" stroke="#CDB9AA" stroke-width="2" stroke-dasharray="6 5"/>'
    lv, xp = 1 + total_contrib // 20, total_contrib % 20
    b += T(36, 274, f"PLAYER LEVEL {lv}", 15, DK) + T(564, 274, f"XP {xp}/20", 15, "#5A4A44", "normal", "end")
    for k in range(24):
        b += R(36 + k * 22, 284, 20, 18, "#3E8E41" if k < round(xp / 20 * 24) else "#D9C8BA")
    b += f'<rect x="35" y="283" width="530" height="20" fill="none" stroke="{DK}" stroke-width="2" shape-rendering="crispEdges"/>'
    return card(600, 330, "Player Stats", "📊", b, 270)


def langs_card(langs):
    total = sum(langs.values()) or 1
    items = sorted(langs.items(), key=lambda kv: -kv[1])[:6]
    top_total = sum(v for _, v in items) or 1
    b = f'<rect x="35" y="63" width="530" height="28" fill="none" stroke="{DK}" stroke-width="3" shape-rendering="crispEdges"/>'
    x = 36.0
    for name, v in items:
        w = 528 * v / top_total
        b += R(round(x, 1), 65, round(w, 1), 24, LANG_COLORS.get(name, "#8D6E63"))
        x += w
    if not items:
        b += T(300, 200, "Belum ada data bahasa", 18, DK, anchor="middle")
    for i, (name, v) in enumerate(items):
        y = 114 + i * 34
        col = LANG_COLORS.get(name, "#8D6E63")
        pct = 100 * v / total
        b += stepped(36, y, 20, 20, DK, 3) + R(39, y + 3, 14, 14, col)
        b += T(68, y + 16, esc(name), 17, DK)
        b += R(250, y + 3, 230, 14, "#D9C8BA") + R(250, y + 3, max(2, round(230 * v / top_total)), 14, col)
        b += f'<rect x="249" y="{y+2}" width="232" height="16" fill="none" stroke="{DK}" stroke-width="2" shape-rendering="crispEdges"/>'
        b += T(564, y + 16, f"{pct:.1f}%", 17, RD, anchor="end")
    return card(600, 330, "Top Languages", "💻", b, 270)


def streak_card(days, cur, best, total):
    W, H = 1200, 300
    b = ""
    tiles = [("TOTAL CONTRIBUTIONS", fmt(total), "in the last year", f"{short(days[0]['date'])} - {short(days[-1]['date'])}" if days else "", "#2F6BC9"),
             ("CURRENT STREAK", str(cur[0]), "days", f"{short(cur[1])} - {short(cur[2])}" if cur[0] else "Mulai lagi hari ini!", RD),
             ("LONGEST STREAK", str(best[0]), "days", f"{short(best[1])} - {short(best[2])}" if best[0] else "-", "#3E8E41")]
    for i, (lab, big, unit, rng, col) in enumerate(tiles):
        x = 36 + i * 236
        b += stepped(x, 72, 222, 190, DK, 6) + stepped(x + 3, 75, 216, 184, col, 5) + stepped(x + 7, 79, 208, 176, "#FFF8F0", 4)
        b += T(x + 111, 104, lab, 14, col, anchor="middle")
        b += T(x + 111, 178, big, 62 if len(big) < 5 else 48, DK, anchor="middle")
        b += T(x + 111, 204, unit, 15, "#5A4A44", "normal", "middle")
        b += T(x + 111, 236, esc(rng), 12.5, "#5A4A44", "normal", "middle")
    if cur[0]:
        b += sprite(FLAME, 36 + 236 + 158, 112, 4, "#E53935") + sprite(FLAME, 36 + 236 + 158 + 8, 120, 2, "#FFC107")
    # heatmap, last 22 weeks
    cols = sorted({d["col"] for d in days})[-22:]
    colors = ["#E6D5C8", "#A5D6A7", "#66BB6A", "#3E8E41", "#1B5E20"]
    x0, y0, pitch = 760, 98, 19
    b += T(x0, 84, "LAST 22 WEEKS", 14, DK)
    for d in days:
        if d["col"] in cols:
            cx = x0 + cols.index(d["col"]) * pitch
            b += R(cx, y0 + d["row"] * pitch, 16, 16, colors[d["level"]])
    b += T(x0, 258, "Less", 12.5, "#5A4A44", "normal")
    for k, c in enumerate(colors):
        b += R(x0 + 36 + k * 20, 246, 16, 16, c)
    b += T(x0 + 36 + 5 * 20 + 6, 258, "More", 12.5, "#5A4A44", "normal")
    return card(W, H, "Contribution Streak", "🔥", b, 330)


# ------------------------------------------------------------------ main
def main():
    os.makedirs(OUT, exist_ok=True)
    p = None
    if TOKEN:
        try:
            p = profile_via_api()
        except Exception as e:
            print("API failed, fallback to HTML:", e, file=sys.stderr)
    if p is None:
        p = profile_via_html()
    days, total = contributions()
    cur, best = streaks(days)
    files = {"stats.svg": stats_card(p, total), "langs.svg": langs_card(p["langs"]), "streak.svg": streak_card(days, cur, best, total)}
    for name, content in files.items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(content)
    print("OK", {k: v for k, v in p.items() if k != "langs"}, dict(list(p["langs"].items())[:6]), "total", total, "cur", cur[0], "best", best[0])


if __name__ == "__main__":
    main()
