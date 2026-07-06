# M2 Fan-out Lane: tweaks

**Read `m2-fanout-playbook.md` first.** Smallest lane — a 1:1 JSON store, targeting-shaped.

**Endpoints:** `GET /tweaks`, `PUT /tweaks`.
**Model:** `UserSettings` (`db/models/user_settings.py`) — 1:1, `user_id` PK, `tweaks` JSONB.
**Contract:** the `Tweaks` shape from `apps/web/src/lib/tweaks-init.ts`
(`{ mstyle, layout, density, accent, font }`) — the API stores/returns this object.
**FE:** `apps/web/src/lib/tweaks.tsx` (`TweaksProvider`) currently persists to
`localStorage` key `specula_tweaks`. Move the source of truth to the server: on load
`GET /tweaks`, on change `PUT /tweaks`. **Keep the pre-paint localStorage read as a cache**
(the `INIT_SCRIPT` FOUC guard in `tweaks-init.ts`) — reconcile with the server value after
mount. Don't remove the FOUC guard.

**Specifics:**
- Clone the targeting 1:1 pattern: `TweaksIn`/`TweaksOut` schema, `upsert_tweaks` keyed on
  `user_id` PK, GET returns the defaults (`TWEAK_DEFAULTS`) when the row is missing.
- Validate the tweak fields to the known enums (mstyle/layout/density/font values,
  accent) so a bad PUT can't poison the store — mirror the unions in `tweaks-init.ts`.

**Tests:** GET defaults for a fresh user, PUT persists/echoes, invalid enum rejected (422),
cross-tenant isolation.
