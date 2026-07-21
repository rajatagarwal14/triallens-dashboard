# TrialLens — Feature Plan (pre-backfill)

Decisions locked: live search-as-you-type · chart-click jumps to Discovery pre-filtered ·
prevalence = country choropleth toggle · rename is label-only. **Do these before the 121k backfill.**

---

## 1. Discovery — live search-as-you-type (auto-filter)

**Now:** must click "Search"; typed country is only applied on Search (just fixed).

**Change:**
- Debounce the condition input (~400ms) → auto-runs the query once typing pauses (min 2 chars).
- Toggling any filter chip (phase / status / type / sponsor / country / look-back) re-runs immediately — React Query key already includes them, so this is mostly removing the `searched` gate.
- Keep the Search button as an explicit "run now" (harmless).
- Guard: skip the fetch while input < 2 chars; show the empty state.

**Files:** `pages/DiscoveryPage.tsx` (add `useDebounce`, drop the `searched` gate).
**Effort:** Small. No backend change.

---

## 2. Rename Landscape → "Historical" (label only)

**Change:** sidebar label + page `<TopBar title>` → "Historical". Keep `/landscape` route + filenames.

**Files:** `components/Layout/Sidebar.tsx`, `pages/LandscapePage.tsx` (title string).
**Effort:** Trivial.

---

## 3. Historical — richer enrollment velocity + interactive charts

### 3a. Detail the Enrollment Velocity chart
Currently a bare per-year line. Add:
- **Tooltip** with exact count + YoY % change per year.
- **Peak marker** (label the busiest year) and a subtle area gradient under the line.
- **Avg-enrollment overlay** (optional 2nd axis): trials-started vs avg patients/trial, to show whether volume or trial size is driving activity.
- Small caption already exists ("proxy for R&D intensity") — keep.

**Backend:** `yearCounts` already returned. For the avg-enrollment-per-year overlay we'd add `enrollmentByYear` to `/landscape/` (cheap — same loop).

### 3b. Make the 4 charts clickable → jump to Discovery pre-filtered
Clicking a segment navigates to `/` (Discovery) with that filter applied via URL query params, e.g.:
- Phase Distribution slice → `?condition=X&phases=PHASE3`
- Status Breakdown bar → `?condition=X&status=RECRUITING`
- Top Countries row → `?condition=X&country=France`
- Sponsor Type Split row → `?condition=X&sponsorClasses=INDUSTRY`

**Prereq:** Discovery must read initial filters from URL query params (small addition — read `useSearchParams` on mount, seed state, auto-run per feature #1).

**Files:** `pages/LandscapePage.tsx` (onClick handlers + cursor styling), `pages/DiscoveryPage.tsx` (hydrate from URL). No backend change for the click-through itself.
**Effort:** Medium. Recharts segments take `onClick`; the bar/pie already have the data keys needed.

---

## 4. Geo Intelligence — sites, country drill-down, prevalence choropleth

### 4a. Mark sites on the map (enhance existing dots)
Dots already render (capped 300). Enhance:
- Cluster or size dots by site count per city so dense metros read clearly.
- Richer tooltip: facility, city, country (already partial).
- Raise/clarify the cap and label it ("showing 300 of N sites").

### 4b. Top Markets / Country Rankings → clickable
Clicking a country should:
- **Zoom the map** to that country's bounds and highlight its polygon, and
- Filter the visible site dots to that country (+ a "clear" affordance).
Optionally also offer "See trials" → Discovery pre-filtered to that country (reuses #3b machinery).

**Files:** `pages/GeoPage.tsx` (map ref + `flyToBounds`, selected-country state). No backend change.

### 4c. Prevalence choropleth (map mode toggle)
Add a map-mode switch: **Trial Density** (current) ⇄ **Disease Prevalence**.
- Prevalence mode shades each country by `getPrevalence(condition)` values (data already exists, country-level).
- Legend swaps to prevalence scale; countries with no pre-fed data render neutral gray with a "no data" tooltip.
- **White-space insight:** high prevalence + low trial count = opportunity — we can auto-highlight those (this is literally the existing White-Space score, now visualized on the map instead of only in the panel).

**Constraint (why not a blurred point heatmap):** we have NO city/point-level prevalence — only per-country totals. A blurred glow would misrepresent site density as prevalence. Country shading is honest to the data.

**Backend:** none — `/landscape/prevalence` already returns per-country numbers.
**Effort:** Medium.

---

## Suggested build order
1. #2 rename (trivial) →
2. #1 live search + Discovery-reads-URL-params (also unblocks #3b) →
3. #3b chart click-throughs →
4. #3a enrollment velocity detail (needs tiny backend add) →
5. #4b country drill-down →
6. #4c prevalence choropleth →
7. #4a site-dot polish →
8. THEN the 121k full-dataset backfill (makes every chart exact; would also enable true in-place cross-filtering on Historical if we ever want it).

## Backend touchpoints (small)
- `/landscape/` → add `enrollmentByYear` (for 3a overlay). Everything else is frontend-only.
