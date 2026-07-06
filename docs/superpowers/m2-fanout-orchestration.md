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

**Use `claude-personal`, not `claude`.** Each window opens in its worktree and boots a
fresh agent sitting at its prompt.

```bash
tmux new-session -d -s specula -n lenses     -c .worktrees/m2-lenses     'claude-personal'
tmux new-window  -t specula   -n candidate   -c .worktrees/m2-candidate   'claude-personal'
tmux new-window  -t specula   -n companies   -c .worktrees/m2-companies   'claude-personal'
tmux new-window  -t specula   -n jobs-state  -c .worktrees/m2-jobs-state  'claude-personal'
tmux new-window  -t specula   -n insights    -c .worktrees/m2-insights    'claude-personal'
tmux new-window  -t specula   -n approvals   -c .worktrees/m2-approvals   'claude-personal'
tmux new-window  -t specula   -n tweaks      -c .worktrees/m2-tweaks      'claude-personal'
tmux attach -t specula
```

Navigation: `Ctrl-b <number>` jump to window · `Ctrl-b n`/`p` next/prev · `Ctrl-b d`
detach (sessions keep running — reattach with `tmux attach -t specula`) · `Ctrl-b w`
list windows. For side-by-side in Ghostty use native splits, or make tmux panes with
`Ctrl-b %` / `Ctrl-b "`.

**Start small.** You don't have to launch all seven at once — try 2–3 first (e.g.
`candidate`, `targeting`-is-done, `companies`) to get the rhythm, then add more.

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
