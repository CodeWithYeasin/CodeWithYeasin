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
    """Triangular curve. Returns (level, xp_into_level, xp_needed_for_level)."""
    lvl, floor_xp = 1, 0
    while True:
        need = 100 * lvl + 50 * lvl * lvl  # cost of lvl -> lvl+1
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

    # ── XP / HP / MP panel ────────────────────────────────────────────────────
    hp_note = "sleep_scheduler still unpatched" if hp < 90 else "fully rested, suspiciously"
    mp_note = f"{len(langs)} languages in the spellbook"
    xp_panel = "\n".join(
        [
            "```text",
            f"   HP  {bar(hp, 100)}  {hp:>3}/100   {hp_note}",
            f"   MP  {bar(mp, 100)}  {mp:>3}/100   {mp_note}",
            f"   XP  {bar(into, need)}  LV {lvl} → {lvl + 1}   ·   {into:,} / {need:,} XP",
            "",
            f"   commits {commits:,}   ·   PRs {prs:,}   ·   issues {issues:,}   ·   "
            f"reviews {reviews:,}",
            f"   repos {repo_count}   ·   stars {stars}   ·   forks {forks}   ·   "
            f"party {followers}",
            f"   best streak {best_streak}d   ·   last 30 days {last_30} contributions",
            "",
            f"   ▸ autosaved {stamp}",
            "```",
        ]
    )

    replacements = {"hud": hud, "xp": xp_panel}

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
