#!/usr/bin/env python3
"""
XP ENGINE — turns real GitHub activity into RPG numbers and writes them back
into the README between <!--START_SECTION:hud--> / <!--START_SECTION:xp--> markers.

Run by .github/workflows/profile-stats.yml. Needs only the default GITHUB_TOKEN.

Env:
  GH_TOKEN / GITHUB_TOKEN   required
  GH_USER                   defaults to the repo owner
  README_FILES              comma-separated, defaults to "README.md,README-game.md"
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

API = "https://api.github.com/graphql"

QUERY = """
query($login: String!) {
  user(login: $login) {
    login
    createdAt
    followers { totalCount }
    following { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      totalPullRequestReviewContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false,
                 orderBy: {field: STARGAZERS, direction: DESC}) {
      totalCount
      nodes {
        name
        stargazerCount
        forkCount
        primaryLanguage { name }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""

# ── XP weights ────────────────────────────────────────────────────────────────
W = {
    "commit": 5,
    "pr": 25,
    "review": 15,
    "issue": 10,
    "star": 20,
    "fork": 12,
    "repo": 30,
    "follower": 8,
    "year": 400,
}


def gql(token: str, login: str) -> dict:
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        API,
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "xp-engine",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]


def level_for(xp: int) -> tuple[int, int, int]:
    """Gentle triangular curve — cumulative XP for level n is 12*n*(n+1), so a
    few years of real student activity lands in the teens rather than at LV 3.
    Returns (level, xp_into_level, xp_needed_for_level)."""
    lvl, floor_xp = 1, 0
    while True:
        need = 24 * lvl                     # cost of lvl -> lvl+1
        if xp < floor_xp + need:
            return lvl, xp - floor_xp, need
        floor_xp += need
        lvl += 1
        if lvl > 999:
            return lvl, 0, need


def bar(value: float, total: float, width: int = 25, full: str = "█", empty: str = "░") -> str:
    if total <= 0:
        return empty * width
    filled = max(0, min(width, round(width * value / total)))
    return full * filled + empty * (width - filled)


def streaks(days: list[dict]) -> tuple[int, int]:
    """(current streak, longest streak) in days, ignoring today if still empty."""
    counts = [d["contributionCount"] for d in days]
    longest = cur = 0
    for c in counts:
        cur = cur + 1 if c > 0 else 0
        longest = max(longest, cur)
    # current streak walks backwards; a zero-count today is allowed as grace
    current, started = 0, False
    for c in reversed(counts):
        if c > 0:
            current += 1
            started = True
        elif started:
            break
        elif current == 0 and not started:
            continue  # grace for today
    return current, longest


def main() -> int:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("::error::GH_TOKEN / GITHUB_TOKEN not set")
        return 1

    login = os.environ.get("GH_USER") or (
        os.environ.get("GITHUB_REPOSITORY", "/").split("/")[0]
    )
    if not login:
        print("::error::could not determine GH_USER")
        return 1

    try:
        u = gql(token, login)
    except urllib.error.HTTPError as e:
        print(f"::error::GitHub API {e.code}: {e.read()[:400]!r}")
        return 1

    cc = u["contributionsCollection"]
    repos = u["repositories"]["nodes"]

    commits = cc["totalCommitContributions"] + cc["restrictedContributionsCount"]
    reviews = cc["totalPullRequestReviewContributions"]
    prs = u["pullRequests"]["totalCount"]
    issues = u["issues"]["totalCount"]
    followers = u["followers"]["totalCount"]
    repo_count = u["repositories"]["totalCount"]
    stars = sum(r["stargazerCount"] for r in repos)
    forks = sum(r["forkCount"] for r in repos)

    created = datetime.fromisoformat(u["createdAt"].replace("Z", "+00:00"))
    years = max(0, (datetime.now(timezone.utc) - created).days // 365)

    xp = (
        commits * W["commit"]
        + prs * W["pr"]
        + reviews * W["review"]
        + issues * W["issue"]
        + stars * W["star"]
        + forks * W["fork"]
        + repo_count * W["repo"]
        + followers * W["follower"]
        + years * W["year"]
    )
    lvl, into, need = level_for(xp)

    days = [
        d
        for w in cc["contributionCalendar"]["weeks"]
        for d in w["contributionDays"]
    ]
    cur_streak, best_streak = streaks(days)
    last_30 = sum(d["contributionCount"] for d in days[-30:])

    # HP = recent momentum (30-day activity, capped). MP = breadth of languages.
    hp = max(35, min(100, 40 + round(last_30 * 1.6)))
    langs = {
        e["node"]["name"]
        for r in repos
        for e in (r.get("languages") or {}).get("edges", [])
    }
    mp = max(40, min(100, 45 + len(langs) * 4))

    stamp = datetime.now(timezone.utc).strftime("%d %b %Y · %H:%M UTC")
    hp_note = "sleep_scheduler still unpatched" if hp < 90 else "fully rested, suspiciously"
    mp_note = f"{len(langs)} languages in the spellbook"

    # ── draw our own SVG cards from this data ────────────────────────────────
    lang_bytes: dict[str, int] = {}
    for r in repos:
        for e in (r.get("languages") or {}).get("edges", []):
            lang_bytes[e["node"]["name"]] = lang_bytes.get(e["node"]["name"], 0) + e["size"]
    ranked = sorted(lang_bytes.items(), key=lambda kv: -kv[1])

    week_cols = [[dd["contributionCount"] for dd in w["contributionDays"]]
                 for w in cc["contributionCalendar"]["weeks"]]
    ticks, seen_months = [], set()
    for wi, w in enumerate(cc["contributionCalendar"]["weeks"]):
        first = w["contributionDays"][0]["date"]
        mon = first[:7]
        if mon not in seen_months:
            seen_months.add(mon)
            label = datetime.fromisoformat(first).strftime("%b")
            if len(ticks) == 0 or wi - ticks[-1][1] >= 4:
                ticks.append((label, wi))

    card_data = {
        "player": os.environ.get("PLAYER_NAME", login.upper()),
        "klass": os.environ.get("PLAYER_CLASS", "ML ARCHMAGE / SECURITY ROGUE"),
        "origin": os.environ.get("PLAYER_ORIGIN", "origin: a secondhand laptop with a tired fan"),
        "stamp": stamp.upper(),
        "level": lvl, "xp_into": into, "xp_need": need,
        "hp": hp, "mp": mp,
        "hp_note": hp_note, "mp_note": mp_note,
        "commits": commits, "prs": prs, "issues": issues, "reviews": reviews,
        "repos": repo_count, "stars": stars, "forks": forks, "followers": followers,
        "streak": cur_streak, "best_streak": best_streak,
        "total_year": cc["contributionCalendar"]["totalContributions"],
        "languages": ranked[:6],
        "lang_total": sum(lang_bytes.values()) or 1,
        "weeks": week_cols,
        "month_ticks": ticks,
    }
    try:
        from render_cards import render_all
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from render_cards import render_all
    written = render_all(card_data, os.environ.get("ASSET_DIR", "assets"))
    print("cards:", written)

    bust = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")

    # ── HUD ───────────────────────────────────────────────────────────────────
    def badge(label: str, value: str, color: str, logo: str = "") -> str:
        safe = lambda s: (
            s.replace("-", "--").replace("_", "__").replace(" ", "_")
        )
        extra = f"&logo={logo}&logoColor=white" if logo else ""
        return (
            f'<img src="https://img.shields.io/badge/{safe(label)}-{safe(value)}-'
            f'{color}?style=for-the-badge&labelColor=0D1117{extra}" alt="{label.lower()}" />'
        )

    hud = "\n".join(
        [
            badge("LV", str(lvl), "FFB000", "gamejolt"),
            badge("XP", f"{xp:,}", "A78BFA"),
            badge("STREAK", f"{cur_streak}d", "F87171", "fireship"),
            badge("QUESTS", str(repo_count), "4ADE80", "github"),
            badge("STARS", str(stars), "22D3EE", "apachespark"),
        ]
    )

    # ── the hero save-file card, and the scoreboard trio ─────────────────────
    save_card = (
        f'<img src="assets/hud.svg?v={bust}" alt="save file — LV {lvl}, '
        f'{xp:,} XP, {cur_streak} day streak" width="100%" />'
    )
    scoreboard = "\n".join([
        f'<img src="assets/stats.svg?v={bust}" alt="scoreboard: {commits:,} commits, '
        f'{prs} pull requests, {repo_count} repos, {stars} stars" width="48%" />',
        f'<img src="assets/languages.svg?v={bust}" alt="languages by share of code" width="48%" />',
        "",
        f'<img src="assets/activity.svg?v={bust}" alt="commit heatmap for the last 12 months — '
        f'{card_data["total_year"]:,} contributions, {cur_streak} day current streak" width="100%" />',
    ])

    replacements = {"hud": hud, "save": save_card, "cards": scoreboard}

    targets = [
        f.strip()
        for f in os.environ.get("README_FILES", "README.md,README-game.md").split(",")
        if f.strip()
    ]

    changed = []
    for path in targets:
        if not os.path.exists(path):
            continue
        text = original = open(path, encoding="utf-8").read()
        for key, value in replacements.items():
            pattern = re.compile(
                rf"(<!--START_SECTION:{key}-->)(.*?)(<!--END_SECTION:{key}-->)",
                re.DOTALL,
            )
            if pattern.search(text):
                text = pattern.sub(
                    lambda m: f"{m.group(1)}\n{value}\n{m.group(3)}", text
                )
        if text != original:
            open(path, "w", encoding="utf-8").write(text)
            changed.append(path)

    print(f"LV {lvl} · {xp:,} XP · streak {cur_streak}d · updated: {changed or 'nothing'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
