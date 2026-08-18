#!/usr/bin/env python3
"""
ADVENTURE ENGINE — a choose-your-own-adventure that runs entirely on GitHub Issues.

A visitor opens an issue from the `play.yml` form and picks a letter. This script
renders the next scene as a comment, hides the run state inside an HTML comment,
and closes the issue when the run reaches an ending.

Triggered by .github/workflows/adventure.yml. Needs only the default GITHUB_TOKEN
with issues: write.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

STATE_RE = re.compile(r"<!--GAMESTATE\s+(\{.*?\})\s*-->", re.DOTALL)
CHOICE_RE = re.compile(r"(?:^|[^A-Za-z])([A-Da-d])(?:[^A-Za-z]|$)")
SCENES_PATH = os.path.join(os.path.dirname(__file__), "adventure_scenes.json")

API = "https://api.github.com"
RANK_COLOR = {
    "S+": "FFB000",
    "S": "FFB000",
    "A": "4ADE80",
    "B": "22D3EE",
    "C": "A78BFA",
    "F": "F87171",
}


# ── GitHub REST helpers ───────────────────────────────────────────────────────
def call(method: str, path: str, token: str, payload: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "adventure-engine",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
    return json.loads(body) if body else None


# ── rendering ─────────────────────────────────────────────────────────────────
def box(title: str, width: int = 72) -> str:
    title = f" {title} "
    pad = max(0, width - len(title) - 2)
    return f"╭─{title}{'─' * pad}╮"


def render_scene(node_id: str, node: dict, state: dict, scenes: dict) -> str:
    hearts = "❤️ " * state["hp"] + "🖤 " * (scenes.get("start_hp", 3) - state["hp"])
    out = [
        f"### 🎮 `{scenes['title']}`",
        "",
        f"**{node.get('art', node_id.upper())}** &nbsp;·&nbsp; {hearts.strip()} &nbsp;·&nbsp; "
        f"move `{len(state['path'])}`",
        "",
        "> " + node["text"].replace("\n\n", "\n>\n> ").replace("\n", "\n> "),
        "",
        "---",
        "",
        "**What do you do?**",
        "",
    ]
    for key, opt in node["options"].items():
        cost = "  `−1 ❤️`" if opt.get("hp", 0) < 0 else ""
        out.append(f"- **`{key}`** — {opt['label']}{cost}")
    out += [
        "",
        "<sub>▸ Reply to this issue with just the letter — `A`, `B` or `C`. "
        "The engine takes it from there.</sub>",
        "",
        f"<!--GAMESTATE {json.dumps(state, separators=(',', ':'))}-->",
    ]
    return "\n".join(out)


def render_ending(ending: dict, state: dict, scenes: dict, player: str) -> str:
    rank = ending["rank"]
    color = RANK_COLOR.get(rank, "A78BFA")
    trail = " → ".join(f"`{p}`" for p in state["path"]) or "`—`"
    return "\n".join(
        [
            f"### 🏁 `RUN COMPLETE`",
            "",
            f'<img src="https://img.shields.io/badge/RANK-{rank.replace("+", "%2B")}-{color}'
            f'?style=for-the-badge&labelColor=0D1117" alt="rank {rank}" />'
            f' <img src="https://img.shields.io/badge/ENDING-'
            f'{ending["title"].replace(" ", "_").replace("-", "--")}-0D1117'
            f'?style=for-the-badge&labelColor=0D1117" alt="ending" />',
            "",
            f"## {ending['title']}",
            "",
            ending["text"],
            "",
            "---",
            "",
            f"**Player:** @{player} &nbsp;·&nbsp; **Moves:** {len(state['path'])} "
            f"&nbsp;·&nbsp; **HP left:** {state['hp']}/{scenes.get('start_hp', 3)}",
            "",
            f"**Route:** {trail}",
            "",
            "<sub>There are six endings. One of them is `S+`. "
            "[Start another run](../issues/new?template=play.yml) — "
            "or go star something, that's an ending too. ⭐</sub>",
            "",
            "<!--GAMESTATE {\"done\":true}-->",
        ]
    )


# ── engine ────────────────────────────────────────────────────────────────────
def find_state(comments: list[dict]) -> dict | None:
    for c in reversed(comments):
        m = STATE_RE.search(c.get("body") or "")
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
    return None


def parse_choice(body: str, valid: set[str]) -> str | None:
    # strip quoted lines and the state marker so we never read our own text back
    cleaned = STATE_RE.sub("", body or "")
    cleaned = "\n".join(
        ln for ln in cleaned.splitlines() if not ln.lstrip().startswith(">")
    )
    for m in CHOICE_RE.finditer(cleaned):
        letter = m.group(1).upper()
        if letter in valid:
            return letter
    return None


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN")
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not (token and event_path and repo):
        print("::error::missing GITHUB_TOKEN / GITHUB_EVENT_PATH / GITHUB_REPOSITORY")
        return 1

    event = json.load(open(event_path, encoding="utf-8"))
    scenes = json.load(open(SCENES_PATH, encoding="utf-8"))

    issue = event.get("issue") or {}
    number = issue.get("number")
    if not number:
        print("no issue in event; nothing to do")
        return 0

    is_comment = "comment" in event
    actor = (event.get("comment") or issue).get("user", {}).get("login", "player")
    if actor.endswith("[bot]"):
        print("bot comment; ignoring")
        return 0

    body = (event.get("comment") or issue).get("body") or ""

    comments = call("GET", f"/repos/{repo}/issues/{number}/comments?per_page=100", token) or []
    state = find_state(comments)

    if state and state.get("done"):
        print("run already finished")
        return 0

    if state is None:
        # fresh run — the issue body carries the opening choice
        state = {"n": scenes["start"], "hp": scenes.get("start_hp", 3), "path": []}
        node = scenes["nodes"][state["n"]]
        choice = parse_choice(body, set(node.get("options", {})))
        if choice is None:
            # no readable choice: just show the opening scene and wait
            state_out = {"n": state["n"], "hp": state["hp"], "path": state["path"]}
            call(
                "POST",
                f"/repos/{repo}/issues/{number}/comments",
                token,
                {"body": render_scene(state["n"], node, state_out, scenes)},
            )
            try:
                call(
                    "POST",
                    f"/repos/{repo}/issues/{number}/labels",
                    token,
                    {"labels": ["adventure"]},
                )
            except urllib.error.HTTPError:
                pass
            return 0
    else:
        node = scenes["nodes"][state["n"]]
        if "options" not in node:
            print("current node is terminal")
            return 0
        choice = parse_choice(body, set(node["options"]))
        if choice is None:
            if is_comment:
                call(
                    "POST",
                    f"/repos/{repo}/issues/{number}/comments",
                    token,
                    {
                        "body": "```text\n> input not recognised\n```\n"
                        "Reply with a single letter — **`A`**, **`B`** or **`C`** — "
                        "matching one of the options above.",
                    },
                )
            return 0

    # ── advance ──────────────────────────────────────────────────────────────
    opt = node["options"][choice]
    state["path"] = state.get("path", []) + [state["n"]]
    state["hp"] = state.get("hp", 3) + opt.get("hp", 0)
    state["n"] = opt["next"]

    if state["hp"] <= 0:
        state["n"] = "death"

    next_node = scenes["nodes"][state["n"]]

    try:
        call("POST", f"/repos/{repo}/issues/{number}/labels", token, {"labels": ["adventure"]})
    except urllib.error.HTTPError:
        pass

    if "ending" in next_node:
        state["path"].append(state["n"])
        call(
            "POST",
            f"/repos/{repo}/issues/{number}/comments",
            token,
            {"body": render_ending(next_node["ending"], state, scenes, actor)},
        )
        call(
            "PATCH",
            f"/repos/{repo}/issues/{number}",
            token,
            {"state": "closed", "state_reason": "completed"},
        )
        print(f"run finished: {next_node['ending']['title']} ({next_node['ending']['rank']})")
    else:
        call(
            "POST",
            f"/repos/{repo}/issues/{number}/comments",
            token,
            {"body": render_scene(state["n"], next_node, state, scenes)},
        )
        print(f"advanced to {state['n']} (hp {state['hp']})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
