# 🎮 YEASIN.EXE — setup guide

Everything here goes in the repo **`CodeWithYeasin/CodeWithYeasin`** (public, name
must match your username exactly). Files:

```
game/index.html                     ← THE GAME. one file, no dependencies
game/preview.gif                    ← the animated preview shown in the README
game/test.mjs                       ← Playwright playthrough test (optional)
README-game.md                      ← the profile itself
scripts/update_stats.py             ← XP engine (real GitHub stats → RPG numbers)
scripts/adventure.py                ← the playable game engine
scripts/adventure_scenes.json       ← the story (edit this to change the game)
scripts/selftest.py                 ← offline checks, run before you push
.github/workflows/profile-stats.yml ← runs the XP engine every 6 hours
.github/workflows/adventure.yml     ← runs the game when someone opens an issue
.github/workflows/snake.yml         ← contribution snake (you already had this)
.github/ISSUE_TEMPLATE/play.yml     ← the "New Game" form
.github/ISSUE_TEMPLATE/config.yml   ← issue-page links
```

---

## 0 · Move the workflow files into place

The four `.github` files landed in a staging folder — Windows blocks remote writes
into `.github/` for safety. Move them yourself first:

```powershell
# PowerShell, from D:\CSE465_REPO\CodeWithYeasin
New-Item -ItemType Directory -Force .github\workflows, .github\ISSUE_TEMPLATE
Move-Item _github_setup\workflows\*.yml      .github\workflows\      -Force
Move-Item _github_setup\ISSUE_TEMPLATE\*.yml .github\ISSUE_TEMPLATE\ -Force
Remove-Item _github_setup -Recurse
```

Your existing `.github/workflows/snake.yml` stays where it is.

## 1 · Go live

```bash
# from the repo root
mv README.md README-classic.md      # keep the old one as a backup
mv README-game.md README.md
git add -A
git commit -m "feat: RPG profile + playable adventure"
git push
```

The XP engine looks for markers in **both** `README.md` and `README-game.md`, so it
keeps working whichever name you land on.

## 1.5 · Put the game online (this is the important one)

The game is one self-contained HTML file. To get a real URL:

Repo → **Settings → Pages** → *Source: Deploy from a branch* → branch `main`, folder `/ (root)` → **Save**.

Give it a minute, then it's live at:

```
https://codewithyeasin.github.io/CodeWithYeasin/game/
```

That's the exact URL the README's **▶ PLAY NOW** button already points at. To check
it locally before pushing, just double-click `game/index.html` — it runs off the
filesystem, no server needed.

**What the game is:** a top-down pixel RPG. Five rooms — Origin Wing, Arcane Tower,
Shadow Keep, The Forge, and the Beacon. Every terminal you read tells the visitor
something real about you. Read all three terminals in a wing and its data shard
appears; collect four shards and the north gate opens to the ending screen, which is
where your contact links live. Arrow keys / WASD, `E` to talk, touch controls on phones.

**Where the writing lives:** `game/index.html`, in the `ENTITIES` array — look for the
`✏️ EDIT ME` comment. Each entry has a `name` and a `pages` array; each page is one
dialogue box. `<b>bold</b>` renders gold, `<i>italic</i>` renders cyan. The two
`FORGE — PROJECT` entries are placeholders — put real projects there.

To re-run the automated playthrough after you edit it:

```bash
npm i -D playwright && npx playwright install chromium
node game/test.mjs      # walks the whole game, screenshots each stage
```

## 2 · Turn on the Actions

Repo → **Settings → Actions → General**:

- **Workflow permissions** → *Read and write permissions* ✅
  (the XP engine commits back to the repo; the game engine posts comments)
- **Allow GitHub Actions to create and approve pull requests** — not needed, leave off

Then run each one once by hand: **Actions** tab → pick the workflow → *Run workflow*.

| Workflow | First run does | After that |
|:--|:--|:--|
| ⚡ XP Engine | Rewrites the HUD badges and the HP/MP/XP panel with your real numbers | Every 6 hours, and on every push |
| 🐍 Snake | Creates the `output` branch with `snake.svg` | Daily |
| 🎮 Adventure | Nothing until someone opens a game issue | On every game issue + comment |

## 3 · Unhide the two commented blocks

After the snake workflow has run once, open `README.md` and delete the comment
markers around the snake `<div>` (search for `🐍 THE GRIND`). Same for the
**WakaTime** block if you sign up at [wakatime.com](https://wakatime.com) and make
your profile public.

## 4 · Optional: count private contributions

The XP engine works fine on the default `GITHUB_TOKEN`, but that token can't see
private commits. To include them:

1. Create a fine-grained PAT with **read:user** access
2. Repo → Settings → Secrets and variables → Actions → new secret named **`XP_TOKEN`**

The workflow already prefers `XP_TOKEN` when it exists.

---

## 🎮 How the playable game works

1. Visitor clicks **▶ NEW GAME** → opens an issue from `play.yml` and picks A/B/C
2. `adventure.yml` fires → `adventure.py` renders the next scene as a comment
3. Run state (current node, HP, route taken) is hidden inside the comment as
   `<!--GAMESTATE {...}-->` — no database, no external service
4. Visitor replies with a single letter; repeat
5. On an ending, the bot posts a rank card and closes the issue

**The story:** *THE 3AM INCIDENT* — 17 scenes, 6 endings, 2 lives.
Ranks run `F` → `C` → `B` → `A` → `S` → `S+`. The `S+` route is the one where you
never destroy your own evidence.

### Editing the story

`scripts/adventure_scenes.json` is the whole game. A scene:

```json
"node_id": {
  "art": "SERVER ROOM · 03:04",
  "text": "What the player sees. Markdown works.",
  "options": {
    "A": { "label": "Careful choice", "next": "another_node" },
    "B": { "label": "Reckless choice", "next": "other_node", "hp": -1 }
  }
}
```

An ending instead of options:

```json
"node_id": {
  "ending": { "rank": "S", "title": "ENDING NAME", "text": "The payoff." }
}
```

Before pushing story changes, run:

```bash
python3 scripts/selftest.py
```

It checks every `next` resolves, every node is reachable, every route terminates,
the choice parser handles messy input, and the README markers still match.

---

## ✏️ What to personalise

| Where | What |
|:--|:--|
| **`game/index.html` → `ENTITIES`** | **The game's dialogue. Highest impact — this is what visitors actually read.** |
| `ACT I` | Your real origin story — the specific one, not the generic one |
| `ACT I` base stats | Tune them honestly; honest is more impressive than maxed |
| `ACT II` skill tree | Move nodes between `:::done` / `:::active` / `:::locked` |
| `ACT IV` quest log | **Replace the three placeholder projects with real repos + links** |
| `ACT V` boss fights | Swap in bugs that actually cost you a weekend |
| `ACT VI` achievements | Keep the funny ones, add yours |

The placeholder projects in `ACT IV` are the one thing a recruiter will notice is
fake. Fill those in first.

## 🔧 Troubleshooting

**HUD badges never change** — the workflow needs write permissions (step 2), and
the markers must be intact. Don't edit between `<!--START_SECTION:-->` and
`<!--END_SECTION:-->`; the engine overwrites that region wholesale.

**Game doesn't respond** — the workflow only fires on issues labelled `adventure`
or titled with 🎮. Check the Actions tab for a skipped run.

**Streak card is blank** — `streak-stats.demolab.com` rate-limits. It comes back.
Self-host it if it bothers you.

**Mermaid diagram shows as raw text** — GitHub only renders mermaid in `.md` files
on github.com, not in some third-party viewers. Check on github.com itself.
