# TrialLens — Audit Findings (for Sonnet to fix)

_Read-only audit. Nothing was changed. Prioritized for a fix pass._

## Frontend — HIGH (visible breakage)

1. **GeoPage.tsx:187** — "White-Space Opportunity Analysis" header `text-white` on white card → invisible.
2. **GeoPage.tsx:306** — "Country Rankings" header `text-white` → invisible.
3. **GeoPage.tsx:345** — "Top Markets" sidebar header `text-white` → invisible.
4. **ProtocolPage.tsx:25** — ComplexityGauge track ring `rgba(255,255,255,0.06)` (white-on-white) → gauge background ring invisible.
5. **ProtocolPage.tsx:280–306** — similar-trials query has no `isError`; on API failure shows pulsing skeletons forever, no retry.

## Frontend — MEDIUM

6. **GeoPage.tsx:184,189,197,214,231,331** — `text-emerald-400`/`text-amber-400` (dark-theme shades) fail contrast on white.
7. **GeoPage.tsx:288** — map legend gradient hardcodes OLD palette (blue/cyan/emerald) but choropleth uses IQVIA colors (interpolateColor L50–55) → legend doesn't match map.
8. **ProtocolPage.tsx:163,180** — biomarker chips `text-violet-400`/`text-red-400` poor contrast on light.
9. **ProtocolPage.tsx:96–99** — EligibilityPanel query ignores `isError`; on failure renders blank instead of error state.
10. **GeoPage.tsx:61–65** — world GeoJSON fetched from raw GitHub URL with `.catch(()=>{})`; on failure choropleth silently never renders. External runtime dependency.
11. **DiscoveryPage.tsx:182–184,344–373** — typed country stored in `countryInput` only; `country` (sent to API) set only by clicking a suggestion. Typing "Poland" + search applies NO country filter.
12. **DiscoveryPage.tsx:197–211** — `pageToken` exists in client but no pagination UI; results hard-capped at 25.
13. **GeoPage.tsx:59** — `useRef<L.GeoJSON>` uses `L` namespace without importing leaflet types; brittle. `layerRef` assigned but never used.
14. **TopBar.tsx:14–19** — Help/Bell icon buttons: no aria-label, no functionality (dead UI).

## Frontend — LOW

15. **index.css:116** — `.text-gradient` still dark cyan gradient; appears unused.
16. **tailwind.config.js** — `boxShadow.card: rgba(0,0,0,0.4)` + blue glow shadows are dark-theme leftovers.
17. **index.css:58** — class named `input-dark` but styled light (misleading name).
18. **GeoPage.tsx:222** — `placeholder-slate-600` inconsistent with `placeholder-iq-muted` used elsewhere.
19. **GeoPage.tsx:334** — ChevronRight `text-slate-700` (near-black) vs `text-iq-muted` elsewhere.
20. **ProtocolPage.tsx:18,51** — hardcoded generic hex (#10b981,#f59e0b,#ef4444,#3b82f6,#64748b) instead of IQVIA palette.
21. **GeoPage.tsx:102–106** — prevalence query no loading/error indication.
22. **LandscapePage.tsx** — no empty state when `totalCount===0` (renders all-zero cards).
23. **App.tsx:35–45** — `AnimatePresence mode="wait"` without `location`/`key`; exit animations never fire (dead variants).
24. **GeoPage.tsx:70** — `key={JSON.stringify(countryData)}` forces full GeoJSON re-mount + re-serialization each render.
25. **ProtocolPage.tsx:172** — `?.length > 0` yields `undefined > 0`; works via coercion only.
26. **DiscoveryPage.tsx:474–484** — sort `<select>` no label/aria-label.
27. **DiscoveryPage.tsx:154** — sponsor name truncated `max-w-[100px]` no `title` tooltip.
28. **DiscoveryPage.tsx:439** — `hover:chip-active` not a valid variant of an @layer component class; silently no-op.
29. **DiscoveryPage.tsx:363** — `shadow-card-md` not defined in config → dropdown has no shadow.
30. **LandscapePage.tsx:105** — "Top Countries" takes first 10 entries without sorting; relies on backend key order.
31. **GeoPage.tsx:269–271** — site CircleMarkers keyed by array index; stale tooltip risk.
32. **GeoPage.tsx:88** — `leaflet-tooltip-iq` class has no CSS definition; falls back to default styling.

---

## Backend — HIGH

1. **services/prevalence.py:132–140** — Fuzzy fallback matches "first key containing any query word," so "Pancreatic Cancer"/"Gastric Cancer" silently return **breast cancer** numbers with `found:true`. Wrong epi data, no mismatch signal.
2. **routers/similarity.py:9–11** — Dead 404 guard: `ct_gov.get_study()` never returns falsy (missing NCT raises CTGovError). "Study not found" path unreachable; client gets generic message. Also masks real 400s.
3. **services/ct_gov.py:184–188** — `nct_id` interpolated into URL path with no validation (`f"{CT_BASE}/studies/{nct_id}"`); `NCT123?format=csv` or `../studies` alters the upstream request (path/query injection).

## Backend — MEDIUM

4. **services/ct_gov.py:162** — `AREA[StartDate]RANGE[01/01/{from_year},MAX]` uses MM/DD/YYYY; CT.gov v2 documents ISO `YYYY-MM-DD` → risks 400 / misparse.
5. **similarity.py:13,17 + ct_gov.py:122** — `target["conditions"][0]` passed verbatim into `query.cond`; Essie operators/parens (e.g. "Leukemia, Myeloid, Acute (AML)") can 400 or skew. Only `country` is sanitized.
6. **main.py:39** — `asyncio.create_task(_warm_cache())` result not stored; task can be GC'd mid-flight → warm may silently never finish.
7. **services/ct_gov.py:166–171** — Cache-stampede race: key check and population separated by await; N concurrent identical requests (Landscape+Geo fired together pre-warmup) all miss and all hit CT.gov. No per-key lock.
8. **routers/landscape.py:27–28** — `countryCounts` sums **site counts**, while `/geo` counts **trials** per country. Inconsistent semantics under similar names.
9. **routers/landscape.py:11,59** — Landscape/Geo analyze only first 1000 studies in default (relevance) order, no explicit sort; >1000-trial conditions give biased non-deterministic sample. `coverage.isComplete` flags it but distributions still skewed.
10. **routers/studies.py:17 + ct_gov.py:126–127** — `sort` passed to CT.gov unvalidated → invalid value = upstream 400 relayed as misleading "Check the search term." Same for unvalidated `status` values (not checked vs v2 enum).

## Backend — LOW

11. **ct_gov.py:31–32** — 400 and 404 collapse into one message; nonexistent NCT looks like a malformed filter.
12. **ct_gov.py:59–60** — `if gp.get("lat") and gp.get("lon")` drops sites at lat/lon exactly 0.0 (falsy) → undercounts.
13. **studies.py:18** — `pageSize` capped at 100 though v2 allows 1000.
14. **similarity.py:4** — `import numpy as np` dead; also 0.0-score studies still returned (no floor) → pads "similar" list with irrelevant trials.
15. **eligibility_nlp.py:80** — Bullet detection only checks `-`/`•`, but v2 returns markdown `*` bullets → exclusion-bullet complexity component ~always 0.
16. **prevalence.py:117–118,133** — Normalization doesn't strip punctuation: "Alzheimer's Disease" fails to match "alzheimer" key → `found:false` despite data existing.
17. **landscape.py:90–92** — `/eligibility/{nct_id}` returns `extracted:{}` for empty criteria; no flag distinguishing "no criteria on record" vs "extraction found nothing."
18. **main.py:24–27** — `asyncio.gather(..., return_exceptions=True)` discards per-search warm failures without logging; still logs "Cache warm complete."
19. **ct_gov.py:185–186,190** — `get_study` caches under raw `nct_id`, no case normalization; `nct04...` vs `NCT04...` = separate slots, double upstream hits.

**Done right (do not touch):** filter.advanced AREA[] syntax for Phase/StudyType/LeadSponsorClass is correct v2; country quote-stripping blocks obvious Essie injection; `pageToken` in cache key; TTLCache safe under single asyncio loop; Discovery React Query key includes all filter params.
