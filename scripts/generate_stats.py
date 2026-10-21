#!/usr/bin/env python3
"""
Gera dois SVGs no estilo terminal para o README do perfil do GitHub:
  - assets/contributions.svg  -> heatmap de contribuições do último ano
  - assets/stats.svg          -> streak atual, maior streak, total, dias ativos,
                                 melhor dia, média por dia ativo e gráfico mensal

Só usa a biblioteca padrão do Python (nada para instalar).

Variáveis de ambiente:
  GH_USER      usuário do GitHub (padrão: diogoDev027)
  GH_TOKEN     token para a API GraphQL do GitHub (no Actions: GITHUB_TOKEN)
  PROMPT_NAME  nome que aparece no prompt "nome@github ~ $" (padrão: diogo)
  OUT_DIR      pasta de saída (padrão: assets)
  MOCK_FILE    (opcional) JSON com o contributionCalendar, para testar offline
"""

import json
import os
import urllib.request
from datetime import date
from xml.sax.saxutils import escape

USER = os.environ.get("GH_USER", "diogoDev027")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
PROMPT_NAME = os.environ.get("PROMPT_NAME", "diogo")
OUT_DIR = os.environ.get("OUT_DIR", "assets")

# ---------- tema ----------
BG = "#0d1117"
BAR = "#161b22"
CARD = "#11161d"
BORDER = "#30363d"
TEXT = "#e6edf3"
MUTED = "#7d8590"
GREEN = "#39d353"
LEVELS = {
    "NONE": "#161b22",
    "FIRST_QUARTILE": "#0e4429",
    "SECOND_QUARTILE": "#006d32",
    "THIRD_QUARTILE": "#26a641",
    "FOURTH_QUARTILE": "#39d353",
}
FONT = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date contributionCount contributionLevel weekday }
        }
      }
    }
  }
}
"""


# ---------- dados ----------
def fetch_calendar():
    mock = os.environ.get("MOCK_FILE")
    if mock:
        with open(mock, encoding="utf-8") as f:
            return json.load(f)

    if not TOKEN:
        raise SystemExit("Defina GH_TOKEN (ou GITHUB_TOKEN) para acessar a API do GitHub.")

    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "contributions-svg",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)

    if data.get("errors"):
        raise SystemExit(f"Erro da API do GitHub: {data['errors']}")
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def fmt(d):
    return f"{MONTHS[d.month - 1]} {d.day}" if d else "-"


def compute_stats(cal):
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    counts = [(date.fromisoformat(d["date"]), d["contributionCount"]) for d in days]
    counts.sort(key=lambda x: x[0])

    total = cal["totalContributions"]
    active = sum(1 for _, c in counts if c > 0)
    best_date, best = max(counts, key=lambda x: x[1])
    avg = total / active if active else 0

    # Streak atual: se hoje ainda está zerado, conta a partir de ontem
    i = len(counts) - 1
    if i >= 0 and counts[i][1] == 0:
        i -= 1
    cur, cur_end = 0, (counts[i][0] if i >= 0 else None)
    while i >= 0 and counts[i][1] > 0:
        cur += 1
        i -= 1
    cur_start = counts[i + 1][0] if cur else None
    if not cur:
        cur_end = None

    # Maior streak
    longest, run, start, ls, le = 0, 0, None, None, None
    for d, c in counts:
        if c > 0:
            if run == 0:
                start = d
            run += 1
            if run > longest:
                longest, ls, le = run, start, d
        else:
            run = 0

    # Contribuições por mês (últimos 12 meses)
    last = counts[-1][0]
    keys = []
    y, m = last.year, last.month
    for _ in range(12):
        keys.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    keys.reverse()
    monthly = {k: 0 for k in keys}
    for d, c in counts:
        if (d.year, d.month) in monthly:
            monthly[(d.year, d.month)] += c

    return {
        "total": total,
        "active": active,
        "days": len(counts),
        "best": best,
        "best_date": best_date,
        "avg": avg,
        "cur": cur,
        "cur_range": (cur_start, cur_end),
        "longest": longest,
        "longest_range": (ls, le),
        "monthly": [(MONTHS[m - 1][0], v) for (_, m), v in monthly.items()],
    }


# ---------- SVG helpers ----------
def window(width, height, title):
    dots = "".join(
        f'<circle cx="{18 + i * 16}" cy="15" r="5" fill="{c}"/>'
        for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"])
    )
    return (
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" '
        f'fill="{BG}" stroke="{BORDER}"/>'
        f'<path d="M0.5 30 V10.5 a10 10 0 0 1 10 -10 H{width - 10.5} a10 10 0 0 1 10 10 V30 Z" fill="{BAR}"/>'
        f'<line x1="0.5" y1="30" x2="{width - 0.5}" y2="30" stroke="{BORDER}"/>'
        f"{dots}"
        f'<text x="{width / 2}" y="19" text-anchor="middle" class="muted" font-size="11">{escape(title)}</text>'
    )


def prompt(y, command):
    return (
        f'<text x="20" y="{y}" font-size="14" font-weight="700">'
        f'<tspan fill="{GREEN}" style="fill:{GREEN}">{escape(PROMPT_NAME)}@github</tspan>'
        f'<tspan> ~ $ {escape(command)} </tspan>'
        f'<tspan class="cursor">_</tspan></text>'
    )


def svg_open(width, height, label):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(label)}">'
        f"<style>"
        f"text{{font-family:{FONT};fill:{TEXT}}}"
        f".muted{{fill:{MUTED}}}"
        f"@keyframes blink{{50%{{opacity:0}}}}"
        f".cursor{{animation:blink 1.1s step-end infinite}}"
        f"</style>"
    )


# ---------- heatmap ----------
def build_heatmap(cal):
    weeks = cal["weeks"]
    cell, gap = 11, 3
    step = cell + gap
    left, top = 52, 100
    width = left + len(weeks) * step + 20
    height = top + 7 * step + 46

    parts = [svg_open(width, height, "Contribuições no GitHub"),
             window(width, height, f"{USER}/README.md"),
             prompt(62, "./contributions.sh")]

    # rótulos dos meses
    labels, prev = [], None
    for wi, w in enumerate(weeks):
        first = date.fromisoformat(w["contributionDays"][0]["date"])
        if first.month != prev:
            if labels and wi - labels[-1][0] < 3:
                labels.pop()
            labels.append((wi, first.month))
            prev = first.month
    for wi, m in labels:
        parts.append(f'<text x="{left + wi * step}" y="{top - 8}" font-size="10" class="muted">{MONTHS[m - 1]}</text>')

    # rótulos dos dias
    for wd, name in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        parts.append(f'<text x="{left - 8}" y="{top + wd * step + 9}" text-anchor="end" font-size="10" class="muted">{name}</text>')

    # células
    for wi, w in enumerate(weeks):
        for d in w["contributionDays"]:
            x = left + wi * step
            y = top + d["weekday"] * step
            color = LEVELS.get(d["contributionLevel"], LEVELS["NONE"])
            stroke = ' stroke="#ffffff" stroke-opacity="0.05"' if d["contributionLevel"] == "NONE" else ""
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{color}"{stroke}>'
                f'<title>{d["contributionCount"]} em {d["date"]}</title></rect>'
            )

    # rodapé
    total = cal["totalContributions"]
    fy = top + 7 * step + 24
    parts.append(f'<text x="{left}" y="{fy}" font-size="12" font-weight="700">{total:,} contributions in the last year</text>')
    lx = width - 20 - 5 * step - 34
    parts.append(f'<text x="{lx - 6}" y="{fy}" text-anchor="end" font-size="10" class="muted">Less</text>')
    for i, c in enumerate(LEVELS.values()):
        parts.append(f'<rect x="{lx + i * step}" y="{fy - 10}" width="{cell}" height="{cell}" rx="2" fill="{c}"/>')
    parts.append(f'<text x="{lx + 5 * step + 4}" y="{fy}" font-size="10" class="muted">More</text>')

    parts.append("</svg>")
    return "".join(parts)


# ---------- cards + gráfico ----------
def card(x, y, w, h, label, value, unit, sub, highlight=False):
    color = GREEN if highlight else TEXT
    unit_svg = f'<tspan font-size="12" class="muted" font-weight="400"> {escape(unit)}</tspan>' if unit else ""
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{CARD}" stroke="{BORDER}"/>'
        f'<text x="{x + 14}" y="{y + 20}" font-size="11" class="muted">$ {escape(label)}</text>'
        f'<text x="{x + 14}" y="{y + 50}" font-size="26" font-weight="700" fill="{color}" style="fill:{color}">'
        f"{escape(value)}{unit_svg}</text>"
        f'<text x="{x + 14}" y="{y + h - 12}" font-size="10" class="muted">{escape(sub)}</text>'
    )


def build_stats(s):
    width, pad, gap = 800, 20, 12
    cw = (width - 2 * pad - 2 * gap) / 3
    ch = 86
    r1, r2 = 84, 84 + ch + gap
    chart_y = r2 + ch + gap
    chart_h = 190
    height = chart_y + chart_h + pad

    cs, ce = s["cur_range"]
    ls, le = s["longest_range"]
    cur_sub = f"{fmt(cs)} — {fmt(ce)}" if s["cur"] else "faça um commit hoje :)"
    long_sub = f"{fmt(ls)} — {fmt(le)}" if s["longest"] else "-"
    pct = round(100 * s["active"] / s["days"]) if s["days"] else 0

    parts = [svg_open(width, height, "Estatísticas de contribuição no GitHub"),
             window(width, height, "zsh — whoami"),
             prompt(62, "whoami --stats")]

    cards = [
        ("current streak", str(s["cur"]), "days", cur_sub, True),
        ("longest streak", str(s["longest"]), "days", long_sub, False),
        ("contributions", f'{s["total"]:,}', "", "in the last year", False),
        ("active days", str(s["active"]), f'/ {s["days"]}', f"{pct}% of the year", False),
        ("best day", str(s["best"]), "", fmt(s["best_date"]) if s["best"] else "-", False),
        ("avg / active day", f'{s["avg"]:.1f}', "", "contributions", False),
    ]
    for i, c in enumerate(cards):
        x = pad + (i % 3) * (cw + gap)
        y = r1 if i < 3 else r2
        parts.append(card(round(x, 1), y, round(cw, 1), ch, *c))

    # gráfico mensal
    cx, cwid = pad, width - 2 * pad
    parts.append(f'<rect x="{cx}" y="{chart_y}" width="{cwid}" height="{chart_h}" rx="6" fill="{CARD}" stroke="{BORDER}"/>')
    parts.append(f'<text x="{cx + 14}" y="{chart_y + 20}" font-size="11" class="muted">$ contributions / month</text>')

    monthly = s["monthly"]
    mx = max((v for _, v in monthly), default=0) or 1
    base_y = chart_y + chart_h - 28
    max_bar_h = chart_h - 70
    slot = (cwid - 28) / len(monthly)
    bw = slot * 0.55
    max_idx = max(range(len(monthly)), key=lambda i: monthly[i][1])
    for i, (letter, v) in enumerate(monthly):
        h = max(2, v / mx * max_bar_h) if v else 2
        x = cx + 14 + i * slot + (slot - bw) / 2
        color = GREEN if i == max_idx and v else "#26a641"
        opacity = "1" if v else "0.35"
        parts.append(
            f'<rect x="{x:.1f}" y="{base_y - h:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="2" '
            f'fill="{color}" opacity="{opacity}"><title>{v}</title></rect>'
        )
        parts.append(f'<text x="{x + bw / 2:.1f}" y="{base_y + 16}" text-anchor="middle" font-size="10" class="muted">{letter}</text>')
        if i == max_idx and v:
            parts.append(f'<text x="{x + bw / 2:.1f}" y="{base_y - h - 6:.1f}" text-anchor="middle" font-size="10" font-weight="700">{v:,}</text>')

    parts.append("</svg>")
    return "".join(parts)


def main():
    cal = fetch_calendar()
    stats = compute_stats(cal)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "contributions.svg"), "w", encoding="utf-8") as f:
        f.write(build_heatmap(cal))
    with open(os.path.join(OUT_DIR, "stats.svg"), "w", encoding="utf-8") as f:
        f.write(build_stats(stats))
    print(f"OK — {stats['total']} contribuições, streak atual {stats['cur']} dias.")


if __name__ == "__main__":
    main()
