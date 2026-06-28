# Increment 180 — credit-the-lineage: statcheck in-context credit + a shared credit recipe (backlog #8)

Honors the **credit-the-lineage** values-layer principle (`.claude/CREDIT-THE-LINEAGE.md`): a tool that implements
identifiable scholarly work credits it **in-context** and offers the source paper to the library (one-click).
p-curve (inc 126) and GRIM (inc 127) already did this; **statcheck (inc 95, the oldest method) did not** — this
closes that gap and consolidates the duplicated CSS along the way.

## Implemented
- **`06_methods_statcheck.jsx`** — a `STATCHECK_CSL` const (Nuijten, Hartgerink, van Assen, Epskamp & Wicherts,
  2016, *Behavior Research Methods* 48:1205–1226, DOI 10.3758/s13428-015-0664-2 — verbatim from
  `THIRD-PARTY-NOTICES.md`) + a `StatcheckCredit` component (a `.method-credit` block: the in-context citation + a
  one-click **＋ add to library** via the inc-93 `/library/import`, mirroring GRIM/p-curve) rendered at the bottom
  of `StatcheckSection`. (135 → 174 lines, well under cap.)
- **CSS consolidation (DESIGN Pass-2):** `.grim-credit`/`.grim-credit-sub` and the byte-identical
  `.pcurve-credit`/`.pcurve-credit-sub` were duplicates → replaced by one canonical **`.method-credit`** /
  **`.method-credit-sub`**; `07_methods_grim.jsx` + `29_pcurve.jsx` repointed (className-only, identical styling →
  no visual change; p-curve's `margin-top` shifts 6→8px, imperceptible). Net −2 CSS lines, one recipe for all
  METHODS credit blocks.

## Gates
- Frontend-only; reuses the inc-93 import endpoint (no new endpoint/migration/egress). **Principles:**
  *strengthens* alignment (credit-the-lineage; "credit + library-add the work a tool stands on") — non-triggering
  in the cautionary sense. Surface **121/121 API + 618/618 FE, 0 uncovered** (statcheck's new add-to-library button
  covered by route_33; grim/pcurve buttons unchanged). `test_frontend_assembly` 5/5; pytest **619**; no Python →
  ruff n/a.

## Verification
**Headed, no egress** (`.local/visual/drive_inc180_credit.py`): open METHODS → Statistics check → the statcheck
credit block renders → **＋ add to library → ✓ added**, and the Nuijten et al. (2016) paper is confirmed present
via `GET /papers`; then "Data consistency (GRIM)" → its `.method-credit` still styles after the repoint; 0
console/page/genai.

## Remaining on #8
Other method-implementing surfaces that could carry an in-context credit + add-to-library (retraction → Retraction
Watch / Crossref; the gap-finder → OpenAlex) and the Lane-B software-dependency NOTICE pass + help-doc sync. Left
for a follow-up; the statcheck gap (the conspicuous one) is closed.
