#!/usr/bin/env python3
"""Offline self-test: scene graph integrity + engine simulation + XP panel render."""
import json, os, re, sys, itertools

sys.path.insert(0, os.path.dirname(__file__))
import adventure as adv
import update_stats as xp

S = json.load(open(os.path.join(os.path.dirname(__file__), "adventure_scenes.json")))
N = S["nodes"]
fail = []

# 1. graph integrity
for nid, node in N.items():
    if "ending" in node:
        for k in ("rank", "title", "text"):
            if k not in node["ending"]:
                fail.append(f"{nid}: ending missing {k}")
        continue
    if "options" not in node:
        fail.append(f"{nid}: neither options nor ending")
        continue
    for key, opt in node["options"].items():
        if key not in "ABCD":
            fail.append(f"{nid}: bad option key {key}")
        if opt["next"] not in N:
            fail.append(f"{nid}/{key}: dangling next -> {opt['next']}")

# 2. reachability
seen, stack = set(), [S["start"]]
while stack:
    cur = stack.pop()
    if cur in seen:
        continue
    seen.add(cur)
    for opt in N[cur].get("options", {}).values():
        stack.append(opt["next"])
unreachable = set(N) - seen - {"death"}
if unreachable:
    fail.append(f"unreachable nodes: {sorted(unreachable)}")

endings = {k for k, v in N.items() if "ending" in v}
print(f"nodes={len(N)} reachable={len(seen)} endings={len(endings)}")

# 3. simulate every path (bounded), confirm all terminate
def walk(nid, hp, depth, path):
    if depth > 20:
        fail.append(f"path too deep: {path}")
        return set()
    node = N[nid]
    if "ending" in node:
        return {node["ending"]["title"]}
    out = set()
    for key, opt in node["options"].items():
        nhp = hp + opt.get("hp", 0)
        nxt = "death" if nhp <= 0 else opt["next"]
        out |= walk(nxt, nhp, depth + 1, path + [nid])
    return out

reached = walk(S["start"], S.get("start_hp", 3), 0, [])
print(f"endings reachable by play: {len(reached)} -> {sorted(reached)}")
missing = {N[e]["ending"]["title"] for e in endings} - reached
if missing - {"YOU DIED"}:
    fail.append(f"endings unreachable in play: {missing}")

# 4. choice parser
cases = [
    ("A — Tail the logs anyway.", {"A", "B", "C"}, "A"),
    ("b", {"A", "B", "C"}, "B"),
    ("I'll go with C please", {"A", "B", "C"}, "C"),
    ("> **`A`** — quoted bot text\nB", {"A", "B", "C"}, "B"),
    ("no letters here at all", {"A", "B", "C"}, None),
    ("### Your first move\n\nC — Open the model dashboard.", {"A", "B", "C"}, "C"),
]
for body, valid, want in cases:
    got = adv.parse_choice(body, valid)
    if got != want:
        fail.append(f"parse_choice({body!r}) = {got!r}, want {want!r}")

# 5. state round-trip through a rendered scene
st = {"n": "logs", "hp": 2, "path": ["entrance"]}
rendered = adv.render_scene("logs", N["logs"], st, S)
back = adv.find_state([{"body": rendered}])
if back != st:
    fail.append(f"state round-trip broke: {back}")
if adv.parse_choice(rendered, {"A", "B", "C"}) is None:
    print("note: bot scene text yields no stray choice from quoted lines (fine)")

# ending render smoke test
adv.render_ending(N["goodending_ghost"]["ending"], {"hp": 2, "path": ["entrance", "logs"]}, S, "someone")

# 6. XP maths
for x in (0, 99, 150, 1000, 25000, 500000):
    lvl, into, need = xp.level_for(x)
    if not (0 <= into < need):
        fail.append(f"level_for({x}) bad: {lvl},{into},{need}")
print("level curve:", [(x, xp.level_for(x)[0]) for x in (0, 500, 2500, 10000, 40000, 200000)])

if len(xp.bar(50, 100, 25)) != 25 or xp.bar(0, 100, 10) != "░" * 10:
    fail.append("bar() wrong")

days = [{"contributionCount": c} for c in [0, 3, 2, 0, 1, 1, 1, 1, 0]]
print("streaks:", xp.streaks(days))

# 7. marker replacement against the real README
readme = os.path.join(os.path.dirname(__file__), "..", "README-game.md")
text = open(readme, encoding="utf-8").read()
for key in ("hud", "xp"):
    pat = re.compile(rf"(<!--START_SECTION:{key}-->)(.*?)(<!--END_SECTION:{key}-->)", re.DOTALL)
    if not pat.search(text):
        fail.append(f"README missing marker pair: {key}")
    else:
        new = pat.sub(lambda m: f"{m.group(1)}\nREPLACED\n{m.group(3)}", text)
        if "REPLACED" not in new:
            fail.append(f"marker {key} did not substitute")
print("markers OK")

if fail:
    print("\nFAILURES:")
    for f in fail:
        print("  ✗", f)
    sys.exit(1)
print("\nALL CHECKS PASSED")
