# Recipe App — Handoff Spec

## What this app is
A personal recipe app, shared with friends via username-only login (no
password). Each username gets its own **private** recipe library — this is
not a shared/social feed. The app never searches or recommends recipes from
the open web; it only ever works with recipes the user has explicitly saved.

## Decisions

Everything is resolved — nothing here should block the sub-agent from building v1.

**Decided**
- **Pantry items are presence-only, always-stocked.** No quantity tracking at all — if an item is in the active pantry, it's assumed the kitchen always has enough, full stop. A grocery list just drops that ingredient entirely; there's no partial-subtraction logic to build.
- **Manual grocery-list items.** Any grocery list — whether just generated from recipes or already saved — has a simple "add item" input for things that aren't tied to any recipe (paper towels, dish soap, whatever). These go straight onto the list and are **not** checked against the active pantry, since adding one manually is a deliberate override, not something to second-guess.
- **Instagram capture — redesigned.** Primary path is now a Shortcuts share-sheet action, not paste-text. From Instagram's native Share menu, a personal iOS Shortcut sends the Reel's URL straight to the app, authenticated with a personal API token (not a session cookie, since Shortcuts has no browser session). The backend tries to auto-fetch the caption from the post's public page (same fetch logic as website import); if that works, it parses normally. If the account is private or the fetch fails, the recipe is saved as a stub (`needs_review = true`, empty ingredients/steps) rather than lost, and gets finished later from inside the app via paste-text or a screenshot upload. Paste-text and screenshot upload both remain available as direct, synchronous entry points too — not just stub-completion tools. Screenshot upload is new: Claude parses the image directly (vision), no separate OCR step. See Instagram ingestion below for the full design.
- **Friend visibility:** you can see your friends' *core* recipes only — nothing experimental, nothing else. No connection/permission system needed.
- **UI style:** minimal, unstyled-leaning presentation for v1 — plain HTML, super simple pages throughout, focus on making the information clear and usable. No real visual design pass yet; that's a later iteration.
- **"Mark as Core":** two paths, both active. (1) Auto-promotes from `experimental` to `core` once a recipe has been marked "made" 5 times. (2) A manual "Mark as Core" button is always available too, for promoting a recipe immediately if you already know it's a keeper. Requires a `times_made` counter incremented by an "I made this" action (see Core flows).
- **Sharing + notes:** when a recipe is shared to a friend, your notes/tweaks copy over along with it — the friend's copy starts with your notes already there, and they add their own from that point.
- **Username permanence:** first-come, no self-service recovery flow — if someone loses access to their username, you (as the person running the app) can just fix it directly in the database. No stakes, no extra flow needed.
- **Grocery lists persist and can grow.** Not ephemeral, and not one-shot either — a list is saved with checkable items, and you can keep adding to it over time (see "Add a recipe to your current grocery list" in Core flows), not just generate it once and be done.
- **No unit conversion in v1, except vague-quantity phrases via the equivalency table** — see Quantity equivalencies below. Real unit conversion (oz ↔ cups, etc.) is still out of scope; only exact name+unit matches get summed directly.
- **Recipe browsing:** a simple `/recipes` page listing your own recipes (title, status, tags), with basic search-by-title. No tag filtering or fancy sorting in v1 — keep it to a plain list, consistent with the rest of the UI direction.
- **Recipe deletion:** every recipe has a delete button, and a required second "Confirm delete" tap before the row (and its notes) are actually removed. No soft-delete/undo — a real removal.
- **`ingredient_aliases` table is dropped.** It existed to map ingredient-name variants (e.g. "scallion" vs. "green onion") for matching, but nothing in v1 populates or reads it, so it's dead weight — removed from the schema entirely rather than left unused. Revisit if inconsistent naming actually becomes a real problem once the library has some size to it.
- **Parsing failures are surfaced immediately, with a reason.** This matches the real usage loop: find a recipe on Instagram → copy → paste → parse → verify → back to scrolling. The Claude parsing call returns an explicit `{"error": "..."}` when it can't find a usable recipe in the text, and the review screen shows that reason right there so you can either fix the input text and re-parse, or tell it's not worth saving.
- **Grocery lists can be added to, not just generated once.** Beyond the manual-item input, a recipe's ingredients can be merged into your current list later — see "Add a recipe to your current grocery list" in Core flows. If that merge pushes an already-checked-off item's needed amount higher, the item gets automatically unchecked again so you know to double-check you actually have enough before trusting it.

**Deferred — already decided as "later," no action needed now**
- Internet-search suggestion toggle — v2, needs real search integration, off by default.
- Ingredient quantity/scaling math for the "what can I make" matcher — v2 (separate from the grocery-list quantity summing above, which is v1).

## Stack decisions
- **Backend:** Flask (Python 3.11+), Jinja2 server-rendered templates
- **DB:** Neon (serverless Postgres), accessed via SQLAlchemy
- **Hosting:** Render Web Service, deployed from a GitHub repo, `gunicorn` as WSGI server
- **Recipe parsing:** Anthropic API (Claude), used server-side via the `anthropic` Python SDK
- **Auth:** username-only, no password — see Auth section below
- **UI:** minimal, unstyled-leaning — plain HTML with little to no CSS for v1, vanilla JS only where needed, no frontend framework. Clarity over polish; a visual pass can come later.

## Auth flow
1. `/login` — text input for username only.
2. If username exists → set a signed session cookie (Flask's built-in `session`, using `SECRET_KEY`) → redirect to `/recipes`.
3. If username doesn't exist → create the user row → same cookie flow.
4. All recipe routes require a valid session; scope every query by `owner_id`. One exception: `POST /api/ingest` (the Instagram Shortcut endpoint) authenticates via the `api_token` bearer header instead, since it's called from outside the browser — see Instagram ingestion.

## Data model (Postgres via SQLAlchemy)
```
users
  id (pk)
  username (unique, not null)
  api_token           # random string, nullable until first generated — used to authenticate the Instagram Shortcut, separate from session-cookie login. Viewable/regenerable from a settings page.
  created_at

recipes
  id (pk)
  owner_id (fk -> users.id)
  title
  status              # 'experimental' (default) | 'core' — auto-promoted at 5 times_made, or manually via a "Mark as Core" button anytime
  times_made          # int, default 0 — incremented by an "I made this" action; hitting 5 triggers auto-promote to core
  servings            # int, nullable — parsed from source if stated; null means "unknown," grocery-list builder defaults to 1x scale when unknown
  source_type        # 'manual' | 'instagram' | 'website'
  source_url         # nullable, for instagram/website
  raw_text           # original pasted/fetched text, kept for re-parsing later
  raw_image          # nullable, stores a screenshot's image bytes when that was the source instead of/alongside text — same "kept permanently as source of truth" principle as raw_text. No dedicated file storage in this stack, so this lives directly in Postgres; fine at this app's scale, revisit if it ever needs to be bigger.
  needs_review        # boolean, default false — true for anything created asynchronously via the Instagram Shortcut (whether the caption auto-fetch succeeded or not), since nobody was looking at a screen to confirm it at share-time. Cleared the first time the recipe is opened and saved/confirmed. If ingredients/steps are still empty, the recipe page shows "needs caption" messaging; if they're populated, it shows "needs review" messaging instead — same flag, different message depending on what's actually missing.
  ingredients         # JSONB: [{name, quantity, unit}]
  steps               # JSONB: ordered list of strings
  tags                # JSONB: list of strings
  shared_from_user_id    # nullable fk -> users.id — set when this row originated as a share from a friend
  shared_from_recipe_id  # nullable fk -> recipes.id — the original recipe this was copied from
  created_at
  updated_at

recipe_notes
  id (pk)
  recipe_id (fk -> recipes.id)
  owner_id (fk -> users.id)
  note_text
  created_at          # notes are timestamped entries, not one editable field —
                       # so tweaks accumulate as a history, most recent first

quantity_equivalencies    # global, not per-user — maps vague quantity phrases to a real number+unit, purely for grocery-list math — recipe display is never rewritten
  id (pk)
  phrase                 # normalized text, e.g. "pinch", "to taste", "dash"
  quantity                # numeric, e.g. 1
  unit                    # e.g. "tablespoon"

pantries
  id (pk)
  owner_id (fk -> users.id)
  name                 # e.g. "Home", "Cabin", "Office kitchen"
  created_at

pantry_items
  id (pk)
  pantry_id (fk -> pantries.id)
  name                 # ingredient name, normalized the same way as recipe ingredients
  added_at

# users gets one more column:
# users.active_pantry_id   nullable fk -> pantries.id — which pantry is "on" right now, switchable any time

grocery_lists
  id (pk)
  owner_id (fk -> users.id)
  pantry_id_used       # nullable fk -> pantries.id — which pantry was subtracted at generation time (nullable if none was active)
  created_at

grocery_list_recipes    # which meals + how scaled went into a given list
  id (pk)
  grocery_list_id (fk -> grocery_lists.id)
  recipe_id (fk -> recipes.id)
  scale                # float, e.g. 1.0, 2.0, 0.5 — multiplier applied to that recipe's ingredient quantities

grocery_list_items
  id (pk)
  grocery_list_id (fk -> grocery_lists.id)
  name                 # combined/normalized ingredient name
  quantity             # nullable — combined only when name+unit matched exactly across recipes
  unit                 # nullable
  source               # 'recipe' (default, came from a selected meal) | 'manual' (added directly, e.g. paper towels)
  checked              # boolean, default false — for checking off while actually shopping
```

## Core flows
1. **Add recipe manually** — form: title, ingredients (one per line, freeform), steps (freeform), tags.
2. **Add recipe from website** — user pastes a URL → server fetches the page → try JSON-LD `Recipe` schema first → if absent, send raw page text to Claude with a strict structured-JSON extraction prompt → show the parsed result to the user for a quick review/edit before saving (parsing won't be perfect, always confirm before commit).
3. **Add recipe from Instagram** — three paths, see Instagram ingestion for full detail: (a) share the Reel from Instagram's Share Sheet via a personal Shortcut, token-authenticated, lands as a recipe flagged `needs_review`; (b) paste the caption text into a form; (c) upload a screenshot, parsed by Claude as an image. (b) and (c) also double as how a `needs_review` stub gets finished.
4. **Fix a parsing mistake anytime** — every imported recipe (website or Instagram) keeps its `raw_text` stored alongside the parsed fields, permanently. An "Edit" screen shows both side by side: parsed fields are directly editable for a manual fix, plus an optional "Re-parse from raw text" button to give Claude another shot after tweaking wording. This isn't just a save-time check — it's available on any recipe, anytime.
5. **Add notes/tweaks** — free-text entries on a recipe, appended over time, shown newest-first. This is how "recipes I've made and tweaked and liked" accumulates.
6. **"I made this"** — button on a recipe increments `times_made`. Hitting 5 auto-promotes `status` from `experimental` to `core`. A separate "Mark as Core" button is always available too, for promoting immediately without waiting to hit 5.
7. **"What can I make?"** — user enters ingredients they currently have (pre-filled from the active pantry, still editable) and picks which source toggles are on (Core / Experimental / Friends / Internet — Core+Experimental on by default) → normalize both pantry and recipe ingredient names → score every recipe in the selected pool(s) by ingredient overlap → return ranked list, each showing what's missing and which library it came from (e.g. "Garlic Butter Pasta (yours) — 5/6 matched, missing: parmesan" / "Weeknight Tacos (from @sam) — 4/5 matched"). This is also the in-store flow: standing in front of a protein or item, just add it to the (already pantry-prefilled) input and search — same screen, no separate feature needed.
8. **Share a recipe to a friend's library** — from any recipe, "Send to..." → pick a username → copies title/ingredients/steps/tags **and notes/tweaks** into the friend's library as a new row (new `recipe_notes` rows owned by the recipient, content copied over), `status` reset to `experimental`, `times_made` reset to 0, `shared_from_user_id`/`shared_from_recipe_id` set for lineage. The friend can keep adding their own notes on top from there.
9. **Manage pantries** — create/rename/delete a pantry; add or remove items in a pantry (freeform ingredient names, normalized like recipe ingredients); switch which pantry is "active" via a simple selector (updates `users.active_pantry_id`). Auto-create a "Home" pantry the first time a user touches this feature so they're never starting from zero.
10. **Generate a grocery list** — pick 1–4 recipes from your own library → set a scale per recipe (defaults to 1x, or to a desired serving count if the recipe's `servings` is known) → combine ingredients across the selected recipes (sum quantity when name+unit match exactly, resolve vague quantities via the equivalency table — see Quantity equivalencies — otherwise list separately) → drop anything whose normalized name matches an item in the currently active pantry → show the result as a checkable list, with an additional one-off "I already have this" checkbox per item for anything not worth adding to the pantry permanently → save it (`grocery_lists` + `grocery_list_items`). This always starts a brand-new list.
11. **Add a manual item to a grocery list** — a plain text input on the grocery list screen, available anytime. Appends a `grocery_list_items` row with `source = manual`. Skips pantry matching entirely — it's on the list because you said so.
12. **Add a recipe's ingredients to your current grocery list** — available from any recipe page (button: "Add to grocery list"), and from "What can I make?" results (so the in-store scenario is: search → pick a result → tap this). "Current list" = your most recently created `grocery_lists` row; if none exists yet, this creates one. Merge logic per ingredient (after pantry subtraction, same as generation): if the ingredient isn't already on the list, add it unchecked; if it's already on the list and unchecked, sum the quantity in place; if it's already on the list and **checked**, sum the quantity and flip it back to unchecked — since a bigger need means the earlier checkmark can no longer be trusted, and this is the signal to look at it again.
13. **Browse recipes** — a plain `/recipes` list of your own recipes (title, status, tags), with basic search-by-title. Recipes with `needs_review = true` get a visible badge so stubs and unconfirmed Shortcut imports are easy to spot and finish. No filtering beyond search in v1.
14. **Delete a recipe** — a delete button on the recipe page, followed by a required second "Confirm delete" tap. Removes the recipe and cascades to delete its notes.
15. **Manage quantity equivalencies** — a simple settings list of `phrase → quantity + unit` rows (add/edit/remove), used automatically whenever a grocery list is generated or added to. See Quantity equivalencies below.
16. **View/regenerate your API token** — a settings page showing the current `api_token` (or generating one on first visit if none exists), with a regenerate button. This is what gets pasted once into the Instagram Shortcut's header configuration — regenerating invalidates the old one, so the Shortcut would need updating too if that's ever used.

## Pantries
A pantry is a named set of ingredients the user has on hand in one physical location — "Home," "Cabin," "Office kitchen," whatever. Users can have several, but only one is **active** at a time (`users.active_pantry_id`), switched with a simple dropdown. Items are presence-only for v1 (see Decisions) — adding "garlic" to a pantry means "I always have garlic here," not "I have exactly 3 cloves."

Natural connection to the existing "What can I make?" flow: default that flow's ingredient input to pre-fill from the active pantry (still freely editable before searching) rather than starting from a blank box every time. Same normalization logic serves both features.

## Grocery lists
Two ways to build one: (1) **Generate** — pick 1–4 recipes and a scale for each (default 1x, or match desired servings against the recipe's known `servings` if present), the app expands and combines ingredients, drops active-pantry items, and saves a brand-new list. (2) **Add to current** — from any single recipe, or right after a "What can I make?" search, merge that recipe's ingredients into whichever list you most recently created — this is what makes the in-store "found an item, want a recipe, don't lose my list" scenario work. Vague quantities ("a pinch") get resolved through the equivalency table where possible; everything else is checkable, persists, and can keep growing over multiple store trips. See Core flows #10–12 and #15, and Decisions for the presence-only-pantry and no-unit-conversion scope calls.

## Quantity equivalencies
Recipe ingredient quantities are often vague ("a pinch," "to taste") rather than a clean number, but grocery lists need real, summable amounts. The `quantity_equivalencies` table bridges this — purely for grocery-list math, never rewriting how a recipe itself displays its ingredients.

When building or adding to a grocery list, for any ingredient whose quantity isn't a plain number (or simple fraction):
1. Normalize the phrase and look it up in `quantity_equivalencies` (e.g. "pinch" → 1 tablespoon).
2. **Found** → treat it as that real quantity+unit from here on: scales with the recipe's multiplier and sums normally with other exact name+unit matches.
3. **Not found** → can't be converted, so instead of guessing: keep the original descriptive text, prefix it with the scale as a plain multiplier (e.g. `2x` next to "a squeeze of lemon"), and set `unit` to the literal flag `"Conor fix this"` so it's obviously unresolved at a glance on the list.

A small settings screen lets equivalencies be added/edited/removed (`phrase`, `quantity`, `unit`) — the intended workflow is noticing a "Conor fix this" flag on a real shopping trip, then adding the equivalency afterward so it's resolved automatically next time. No fuzzy matching in v1 — exact normalized-phrase match only, grown manually over time. Table is shared across all users rather than personal to each — these are basically universal cooking conventions ("a pinch") not individual preferences, so one person fixing "Conor fix this" once benefits everyone. Cheap to change to per-user later if that turns out wrong.

## Instagram ingestion
Three ways a recipe can come in from Instagram, in order of how often each should get used:

**1. Share Sheet → Shortcut (primary path, built by the user in the iOS Shortcuts app, not by the sub-agent).** From Instagram's native Share menu, a personal Shortcut sends the shared Reel URL to `POST /api/ingest`, authenticated with the user's `api_token` as a bearer header (no session cookie exists in this context). This is the only route into the app that uses token auth instead of session auth — everything else stays cookie-based.

Backend handling for this endpoint:
1. Try fetching the post's public page (same fetch logic as website import) and look for the caption in page metadata.
2. **Caption found** → send it to Claude for parsing exactly like any other import.
3. **Not found** (private account, fetch blocked, etc.) → save a stub instead of failing: `title` gets a placeholder like "New Instagram recipe," `ingredients`/`steps` stay empty.
4. Either way, the new recipe is saved with `needs_review = true` — nobody was looking at a screen to confirm it when it came in via Shortcut, so it waits in that state until the user opens it.

**2. Paste-text (fallback / direct entry).** Unchanged from the original design: paste the caption into a form, Claude parses it, goes through the normal synchronous review-before-save screen. `needs_review` is never set true here — the review screen itself is the confirmation.

**3. Screenshot upload (fallback / direct entry, new).** For posts where copying text doesn't work and the auto-fetch can't reach the caption either (private accounts especially). Upload the image through the app; instead of `raw_text`, the image goes into `raw_image` and gets sent to Claude as an image content block in the same parsing call — Claude reads the on-screen text directly, no separate OCR step needed. Same synchronous review-before-save screen as paste-text.

Stub and needs-review recipes get finished using paths 2 or 3 — open the recipe, and instead of a normal edit view it shows "needs caption" (empty fields) or "needs review" (populated but unconfirmed) messaging with a way to paste text or upload a screenshot right there. Saving clears `needs_review`.

`raw_text` (or `raw_image`) is kept permanently either way — that's what makes "fix it if the parse is wrong" available anytime, not just at save time.

## Suggestion sources (toggles)
"What can I make?" is scoped by up to four toggleable, combinable pools:
- **Core** — the user's own recipes marked `status = core` (made, tweaked, liked)
- **Experimental/New** — the user's own recipes still at `status = experimental`
- **Friends** — other users' `core` recipes only (never their experimental/in-progress ones)
- **Internet** — off by default; when on, runs a live web search for recipes matching the given ingredients and parses top results the same way as a website import. Heavier lift than the other three (needs real search integration) — treat as v2/fast-follow rather than blocking v1.

Default on first load: Core + Experimental on, Friends + Internet off.

## Recipe parsing (Claude prompt shape)
System prompt instructs Claude to return **only** valid JSON, no commentary. Two possible shapes:
```json
{"title": "...", "servings": null, "ingredients": [{"name": "...", "quantity": "...", "unit": "..."}], "steps": ["...", "..."]}
```
or, if no usable recipe can be found in the input:
```json
{"error": "Couldn't find any ingredients or steps in this text."}
```
`servings` should be a number if the source states one (e.g. "serves 4"), otherwise `null` — don't guess. The backend checks for an `error` key first; if present, the review screen shows that message directly (with the raw text still visible and editable) instead of a blank form, so the reason for the failure is obvious immediately, not something to guess at.
Always route successful parses through a review/edit screen before saving too — don't trust auto-parse blindly, especially for Instagram captions which are often messy/conversational.

**Screenshot uploads work the same way, just with an image content block instead of text** in the Claude call — same JSON output shape, same error handling, same review screen. No separate OCR step; Claude reads on-screen text directly from the image.

## Ingredient matching (v1 — keep it simple)
- Normalize ingredient names on both sides (strip quantities, units, punctuation, lowercase).
- `score = (# recipe ingredients present in pantry) / (# total recipe ingredients)`
- Sort descending, surface top matches, list what's missing for each.
- Quantities are stored on the recipe but not used in scoring yet — v1 is names-only matching.

## Deployment steps
1. **Neon:** create a project, copy the pooled connection string.
2. **Render:** new Web Service from the GitHub repo.
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`
3. **Env vars on Render:** `DATABASE_URL` (from Neon), `SECRET_KEY` (Flask session signing), `ANTHROPIC_API_KEY`
4. **Migrations:** use Alembic via Flask-Migrate from the start, even though the app is small — avoids manual SQL later when the schema changes.

## Explicit non-goals for v1
- No password / email / OAuth login
- Internet-sourced suggestions exist as a toggle but are off by default — fine to treat as v2 if the search integration adds too much scope
- No commenting/discussion on shared recipes — sharing is a one-way copy into the friend's library, not a live shared object
- No mobile app / PWA

All decisions are locked in — see the **Decisions** section at the top of this doc.
