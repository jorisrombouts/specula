# M5 Fan-out — Parallel Lane Orchestration (you drive the fleet)

The **M5 foundation** is merged to `main` (`6507edc`): `llm_costs`+RLS, `companies.opt_out`,
`runs.cost_usd`/`duration_ms`, the frozen `shared-types` contract, and the `dashboard`/
`account` router + nav stubs. This guide launches the five fan-out **hardening lanes**.

**Setup is already done for you** (by the integrator session): five worktrees under
`.worktrees/m5-<lane>` on branches `m5-<lane>` (off `main@6507edc`), five isolated databases
`specula_wt_<lane>` (migrated to the foundation head + seeded), and each worktree's
`apps/api/.env` pointed at its own DB. You just launch a session per lane and drive it; the
integrator session reviews + merges.

## The five lanes

| Lane | Worktree | DB | Brief | Merges |
|---|---|---|---|---|
| **NET** | `.worktrees/m5-net` | `specula_wt_net` | `docs/superpowers/specs/m5-net-brief.md` | 1st |
| **OBS** | `.worktrees/m5-obs` | `specula_wt_obs` | `docs/superpowers/specs/m5-obs-brief.md` | 2nd |
| **DATA** | `.worktrees/m5-data` | `specula_wt_data` | `docs/superpowers/specs/m5-data-brief.md` | 3rd |
| **DASH** | `.worktrees/m5-dash` | `specula_wt_dash` | `docs/superpowers/specs/m5-dash-brief.md` | 4th |
| **LOAD** | `.worktrees/m5-load` | `specula_wt_load` | `docs/superpowers/specs/m5-load-brief.md` | 5th (last) |

All five can be worked concurrently. The **merge order** (NET→OBS→DATA→DASH→LOAD) is the
integrator's concern, not yours — see "Integrate" below for why.

## 1. Launch a session per lane

**Simplest (no tmux needed):** open one terminal tab/window per lane, `cd` into its
worktree, and start a Claude session there:

```bash
cd /Users/jorisrombouts/Projects/Personal/specula/.worktrees/m5-net && claude-personal
# repeat in new tabs for m5-obs, m5-data, m5-dash, m5-load
```

**Start small** — you don't have to launch all five at once. Try NET + OBS first to get the
rhythm, then add the rest.

**Optional — one-terminal fleet via tmux** (not installed by default; `brew install tmux`
first). `claude-personal` is a shell alias, not a binary on `PATH`, so tmux must open a real
interactive shell and *then* send the command — never pass it as the window command (that
runs under a bare `/bin/sh` with no alias → the window dies instantly):

```bash
cd /Users/jorisrombouts/Projects/Personal/specula
tmux new-session -d -s m5 -n net -c .worktrees/m5-net      # -d = detached; no command arg
tmux send-keys -t m5:net 'claude-personal' Enter
for lane in obs data dash load; do
  tmux new-window -t m5 -n "$lane" -c ".worktrees/m5-$lane"
  tmux send-keys  -t "m5:$lane" 'claude-personal' Enter
done
tmux attach -t m5    # you're only "in" tmux once attached (status bar visible). Ctrl-b <n> to switch.
```

## 2. Drive each lane

First message to each lane session:

> Read `docs/superpowers/specs/m5-fanout-playbook.md` (shared rules) and your brief
> `docs/superpowers/specs/m5-<lane>-brief.md`, then implement it end-to-end using the
> superpowers workflow (TDD). You own only the files your brief lists. Keep
> `.lane-status.md` current and write `.lane-report.md` when green. Commit on this branch
> (`m5-<lane>`) when the full gate is green — do NOT merge to main.

Each brief is self-contained: the files it owns, binary scope rules, the tests to write, and
its definition of done. The playbook carries the hard rules (RLS, `flush()` not `commit()`,
camelCase to the frozen contract, non-superuser DB role, self-reporting).

## 3. When a lane is green → tell the integrator

When a lane reports `.lane-report.md` green on its branch, tell the integrator session
(this one) — e.g. "OBS is green." The integrator does NOT merge on laptop-green alone; it
reviews the branch, runs the full suite on the merge result, and integrates.

## 4. Integrate (the integrator seat — not your job, for reference)

Merge order is **NET → OBS → DATA → DASH → LOAD** and it is *not* arbitrary:
- **NET first** so OBS rebases onto the final `PoliteFetcher` signature (`pipeline/http.py`).
- **OBS before DASH/DATA** so the `llm_costs` ledger is populated + exercised before the
  dashboard reads it and the export/cascade path includes it.
- **LOAD last** — its E2E asserts against NET/OBS/DATA/DASH already on `main`.

Per lane the integrator: reviews the branch (`requesting-code-review`), gates on
**branch-CI-green** + a full-suite run on the merge result, merges `--no-ff`, then tears
down:

```bash
git checkout main && git merge --no-ff m5-<lane>
git worktree remove .worktrees/m5-<lane> && git branch -d m5-<lane>
docker compose exec -T postgres psql -U specula -d specula -c "DROP DATABASE specula_wt_<lane>"
```

A later lane rebases on `main` if an earlier lane changed a file it also touches (rare — the
briefs are disjoint by design; the one soft dependency is NET's `PoliteFetcher` signature,
which NET keeps stable).
