<!-- qa-coverage
api: GET /saved-searches, POST /saved-searches, DELETE /saved-searches/{search_id}
fe: 10_pdf_layer.jsx, 10b_libmenus.jsx
-->

# ROUTE 21 - Saved searches

**Tier:** 1 local-stateful
**Goal:** Exercise saving / recalling / deleting a named bundle of the existing library facets (q / search_field /
item_type / axis / tag / needs_review / signal / sort) from the **Saved ▾** menu in the library header (inc 208, A1).

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET.** Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** With egress unset, any request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Signal not verdict.** A saved search is a metadata predicate over the existing facets — **distinct from an axis**
  (a semantic lens). It persists/replays filter params; it computes no new claim, rank, or score.
- **Boundary validation.** `POST /saved-searches` stores ONLY the known facet keys (`extra="forbid"`): an unknown key
  → **422**; a blank name → **422**. A stored search that injected arbitrary keys would be a bug.

## Adversarial checklist

- paste ~50KB into the name; submit empty / whitespace-only name
- double-click save; rapid-click; re-save the same name (must upsert, never duplicate)
- POST `params` with an unknown key -> 422; delete a non-existent id -> 404
- resize to `375x812`, hard refresh - no horizontal overflow

## Steps

1. Set some library facets (a search term + a sort + e.g. the Unsorted toggle or an axis/tag filter). Open the
   **Saved ▾** menu and **Save current search…** -> name it. `POST /saved-searches` returns `{id, name, params}` with
   the current facets; the menu now lists it.
2. Clear/change the facets, then **apply** the saved search from the menu. Confirm the search box, scope, sort, and
   filters all restore to the saved set (the list re-queries `GET /papers` with those params).
3. Re-save under the **same name** with different facets -> `GET /saved-searches` shows **one** entry (upsert, same id),
   not a duplicate.
4. `POST /saved-searches {params:{<unknown key>}}` -> **422**; blank name -> **422**.
5. Delete a saved search (the **×** in the menu) -> `DELETE /saved-searches/{id}` 204; it disappears. Deleting a
   non-existent id -> 404.

## Pass criteria

- Save, apply, upsert-by-name, and delete complete through the UI.
- Only known facet keys are stored; unknown keys / blank name fail cleanly (422); unknown delete -> 404.
- 0 console/page errors and 0 genai-host requests.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_21_saved_searches.md` + `screenshots/` (see `_TEMPLATE.md`).
