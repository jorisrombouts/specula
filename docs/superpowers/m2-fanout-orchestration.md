# M2 Fan-out — Parallel Lane Orchestration (tmux + worktrees)

The M2a **Foundation** lane is merged to `main` (`de372e5`). This guide sets up the
parallel **fan-out CRUD lanes**, each in its own git worktree + database, driven by a
separate `claude-personal` CLI session in a tmux window.

## Prerequisites (once)

- Docker running; Postgres up on host port **55432** (`just up`).
- You're on `main` at/after `de372e5` (Foundation merged).

## 1. Create worktrees + per-lane databases

Each lane branches from the merged Foundation and gets an **isolated database** on the
shared Postgres container, so lanes' migrations/seeds/tests never collide.

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
echo ".worktrees/" >> .gitignore   # keep worktrees out of git status noise

for lane in lenses candidate companies jobs-state insights approvals tweaks; do
  git worktree add ".worktrees/m2-$lane" -b "m2-$lane"
  just db-bootstrap "specula_wt_$lane"        # create + migrate + seed that lane's DB
done
```

Then point each worktree's API at its own DB by writing its `.env` (the app reads
`DATABASE_URL` from `apps/api/.env`):

```bash
for lane in lenses candidate companies jobs-state insights approvals tweaks; do
  db="${lane//-/_}"   # jobs-state -> jobs_state
  printf 'DATABASE_URL=postgresql+asyncpg://specula_app:specula@localhost:55432/specula_wt_%s\nAPP_ENV=development\nSERVICE_JWT_SECRET=dev-fanout-secret\n' "$db" \
    > ".worktrees/m2-$lane/apps/api/.env"
done
```

## 2. Launch one `claude-personal` per lane in tmux

**Use `claude-personal`, not `claude`.** Each window opens in its worktree and runs a
fresh agent.

> **Why the obvious one-liner fails.** `claude-personal` is a shell alias/function (in
> your `~/.zshrc`), not a binary on `PATH`. Passing it as the command —
> `tmux new-window … 'claude-personal'` — makes tmux run it via a bare `/bin/sh -c`
> that never loads your zsh config, so it's "command not found", the window's process
> exits, and the window (or whole session) dies instantly. **Fix:** create each window
> with a normal interactive shell (no command argument), then `send-keys` the command
> into it — that runs inside your zsh where the alias exists.

```bash
cd /Users/jorisrombouts/Projects/Personal/specula

# First window CREATES the session (‑d = detached/background). Note: no command arg.
tmux new-session -d -s specula -n lenses -c .worktrees/m2-lenses
tmux send-keys -t specula:lenses 'claude-personal' Enter

# Each additional lane: add a window, then type the command into it.
for lane in candidate companies jobs-state insights approvals tweaks; do
  tmux new-window -t specula -n "$lane" -c ".worktrees/m2-$lane"
  tmux send-keys  -t "specula:$lane" 'claude-personal' Enter
done

# ATTACH — this is what actually puts you *inside* tmux. Until you attach, the
# session runs in the background and the prefix key does nothing.
tmux attach -t specula
```

**You must `tmux attach`.** Creating with `-d` is silent and invisible on purpose. You
are only "in tmux" once you've attached — confirmed by the **status bar at the bottom**
of the window (session name + window list). No status bar = not in tmux = the prefix
key is inert.

Navigation (default prefix is **`Ctrl-b`** — press and *release* it, then the key):
`Ctrl-b <number>` jump to window · `Ctrl-b n`/`p` next/prev · `Ctrl-b w` list windows ·
`Ctrl-b d` detach (session keeps running — reattach with `tmux attach -t specula`).
For side-by-side, use Ghostty's native splits or tmux panes (`Ctrl-b %` / `Ctrl-b "`).

> If `Ctrl-b` seems dead: (1) confirm you're attached (status bar visible) — `tmux ls`
> lists sessions, `tmux list-clients` shows whether anyone is attached; (2) a custom
> `~/.tmux.conf` may remap the prefix — check with `tmux show-options -g prefix`
> (default is `C-b`).

**Start small.** You don't have to launch all seven at once — try 2–3 first (e.g.
`candidate`, `companies`, `tweaks`) to get the rhythm, then add more. To add one later,
just repeat the two-line `new-window` + `send-keys` pair for that lane.

## 3. Drive each lane

Your first message to each `claude-personal` window:

> Read `docs/superpowers/specs/m2-<lane>-brief.md` and implement it end-to-end
> (backend CRUD cloning the targeting template + wire the frontend provider). Use the
> superpowers workflow. Commit on this branch when green.

Each brief is self-contained: the endpoints, the model, the copy-me pattern to clone
(`apps/api/specula_api/{schemas,services,routers}/targeting.py` from Foundation), the
frontend provider to swap, and the definition of done.

## 4. Integrate

When a lane is green on its branch, merge it back:

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
git checkout main && git pull
git merge --no-ff m2-lenses        # repeat per lane; order doesn't matter (independent)
git worktree remove .worktrees/m2-lenses
git branch -d m2-lenses
# drop the lane DB when done:  docker compose exec -T postgres psql -U specula -d specula -c "DROP DATABASE specula_wt_lenses"
```

Rebase a lane on `main` before merging if other lanes landed first. The **Frontend-wiring
lane** (shared `bffFetch` + service-JWT minter) runs last, after the endpoints exist.

## Lanes & endpoints (targeting is already done by Foundation)

| Lane | Endpoints | Model(s) | FE provider |
|---|---|---|---|
| lenses | `GET/POST /lenses`, `PATCH/DELETE /lenses/{id}` | `Lens` | `lib/api/lenses.ts` |
| candidate | `GET/PUT /candidate` | `CandidateProfile` | `lib/api/candidate.ts` |
| companies | `GET /companies`, `PATCH /companies/{id}` | `Company` | `lib/api/companies.ts` |
| jobs-state | `GET /jobs`, `GET /jobs/{id}`, `PATCH /jobs/{id}/state` | `Posting`+`Score`+`PostingState`+`Company` | `lib/api/jobs.ts` |
| insights | `GET /insights?period`, `GET /skills-gap` | read-model over `Posting`/`Score` | `lib/api/insights.ts`,`skills-gap.ts` |
| approvals | `GET /approvals`, `POST /approvals/{id}/decision` | `Approval`(+`Company`) | `lib/api/approvals.ts` |
| tweaks | `GET/PUT /tweaks` | `UserSettings` | `lib/tweaks.tsx` (localStorage→server) |

**jobs-state** owns the shared `services/lens_filter.py` (`lens_where()`) that **lenses**
(derived counts) and **jobs** both use — build it there, or in whichever of the two lands
first; the other rebases. This is the one accepted inter-lane dependency.
