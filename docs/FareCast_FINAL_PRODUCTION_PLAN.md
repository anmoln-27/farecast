# FareCast — FINAL IMPLEMENTATION & PRODUCTION COMPLETION PLAN

## Objective
Make the deployed FareCast application fully functional end-to-end for SIH 26056.

The goal is NOT to redesign the project or add fake/demo observations. Every dashboard metric, graph, filter, API response, index, prediction, anomaly result, and context panel must work from real data or be explicitly labelled unavailable when the underlying source genuinely does not exist.

**Explicit exception:** Direct MakeMyTrip/other protected OTA website scraping is OUT OF SCOPE for this completion pass. Do not bypass CAPTCHA, anti-bot protection, robots.txt, authentication, rate limits, or Terms of Service.

---

## 1. NON-NEGOTIABLE RULES

1. Do not fabricate historical, live, DGCA, CPI, index, prediction, or market-signal observations.
2. Do not hardcode values merely to remove 0/null/—/empty states.
3. Do not silently replace missing data with demo data while UI says HISTORICAL or LIVE.
4. Every displayed number must have a traceable source: historical dataset, live provider/API, calculated analytical result, or explicitly labelled estimate/prototype.
5. Preserve truthful LIVE, HISTORICAL, and DEMO labels.
6. Keep API keys and secrets server-side only.
7. Do not expose secrets in source code, Git, frontend bundles, logs, screenshots, or API responses.
8. Do not remove tests just to make them pass.
9. Do not weaken validation to accept bad data.
10. Do not change SIH scope unnecessarily.
11. Do not implement IP rotation or anti-bot bypassing.
12. Direct MakeMyTrip scraping is the only intentionally incomplete SIH component in this pass.

---

## 2. PRODUCTION DATA — VERIFY AND REPAIR

Production PostgreSQL must contain the complete genuine historical dataset prepared by the project.

Expected package:
- 30,114 genuine historical fare observations
- Kaggle historical airfare data
- GitHub `full_fare.csv` 2022–2023 observations
- Approximately Feb 2022–Jun 2023 coverage
- Multiple domestic routes and airlines
- Genuine advance-window observations where available

Verify:
- `/health`
- `/api/dashboard/summary`
- `/api/fares?limit=10`
- `/api/routes`
- `/api/airlines`
- `/api/fares?data_mode=HISTORICAL&limit=100`
- `/api/fares?origin=DEL&destination=BOM&data_mode=HISTORICAL&limit=1000`
- `/api/fares?origin=BOM&destination=PNQ&data_mode=HISTORICAL&limit=1000`

Record:
- total observation count
- route count
- airline count
- date range
- source distribution
- data mode
- duplicates
- required-field nulls

If production is missing genuine records, repair the import/migration pipeline and load the genuine records. Never generate substitute rows.

---

## 3. FIX FRONTEND/BACKEND DATA CONTRACT

Audit every endpoint used by the frontend.

Check:
- response structures
- `{data,total}` handling
- pagination
- enum serialization
- dates
- Decimal/numeric values
- airline codes
- route codes
- data_mode
- null handling

The frontend must never assume an array when the backend returns an object containing `data`.

Required behavior:
- valid data → return data
- no matching data → truthful empty result + explanation
- server/data error → actual error, not fabricated values
- optional fields may be null only when genuinely unavailable

---

## 4. FIX ALL FILTERS

Every filter must actually change displayed data.

Required:
- Origin
- Destination
- Travel date
- Airline
- Cabin class
- Data mode where applicable

Test:
- DEL-BOM
- BOM-DEL
- DEL-BLR
- BOM-BLR
- BLR-MAA
- HYD-DEL
- All origins/destinations
- each available airline
- Economy/Business
- with/without travel date

If a route genuinely lacks enough observations:
- show actual observation count
- explain the minimum requirement
- optionally suggest routes with sufficient observations
- do not fabricate observations

---

## 5. ROUTE PRICE INDEX / APIx

Make the index pipeline work end-to-end:

`raw fares → cleaning → grouping → baseline → weighted index → API → frontend`

Verify:
- route index
- composite index
- daily index
- weekly index
- monthly index
- baseline
- observation count
- weights
- trend

For sufficient data, the dashboard must display the calculated index.

For insufficient data:
- do not invent an index
- return `insufficient_observations`
- return actual count and minimum required

Keep prototype/research weighting clearly labelled. Never call it an official Government of India index.

---

## 6. FARE MOVEMENT TREND

Connect the chart to genuine historical observations.

It must:
- respond to filters
- use actual observation dates
- aggregate correctly
- show average fare
- handle sparse data
- have loading/error/empty states

Fix date parsing/timezone issues that remove valid records.

---

## 7. AIRLINE FARE COMPARISON

Connect to actual database observations.

For selected scope:
- group by airline
- calculate average fare
- count observations
- display only airlines with observations

Do not populate from the airline master table alone.

---

## 8. ROUTE FARE BENCHMARKS

Connect route benchmarks to actual observations.

Show:
- route
- average fare
- observation count

Do not use hardcoded benchmark fares.

---

## 9. LEAD-TIME ELASTICITY / SURGE CURVE

Use genuine observations where available.

Required windows:
- T+45
- T+30
- T+15
- T+7
- T+1

For each:
- average observed fare
- multiplier versus baseline
- observation count

The chart must change with route/filter selection.

Do not present static prototype values as observed data.

If a window genuinely has no data, show that fact rather than inventing a fare.

---

## 10. SECTOR SURGE HEATMAP

Clearly distinguish:
- real calculated historical values
- prototype reference values

If prototype values remain:
- label them `Prototype Reference`
- never call them real-time observed fares
- never imply live airline scraping

Prefer calculated historical values whenever sufficient data exists.

---

## 11. FARE FORECAST

Verify the trained Random Forest model pipeline.

Inputs:
- origin
- destination
- airline
- cabin
- days to flight
- stops

Outputs:
- model estimate
- range/uncertainty

Validate feature mapping against the exact training schema.

Test different routes, airlines, lead times, stops, and cabins.

Never present prediction as an actual booked fare.

If prediction fails, return a clear error rather than 0/null.

---

## 12. MARKET SIGNALS / ANOMALIES

Use actual historical observations.

Verify:
- IQR
- Isolation Forest
- threshold
- contamination
- filters
- signal count

If genuinely zero anomalies exist, `0 Signals Detected` is correct.

But verify zero is not caused by a broken query or empty production dataset.

---

## 13. DGCA CONTEXT

Verify the genuine DGCA/public aviation data pipeline.

If a legitimate dataset exists in the project:
- load it into production
- expose it through API
- connect frontend

Show actual traffic/capacity context where available.

Never invent passenger counts, route weights, or fares.

Keep the distinction:
DGCA aviation statistics describe operational traffic/capacity, not individual ticket-price observations.

---

## 14. MOSPI / CPI REFERENCE

If a legitimate public reference dataset exists:
- load it into production
- expose it through API
- connect frontend

If only methodology/reference information is available:
- show reference context
- clearly label it as macroeconomic context
- do not fabricate flight-level CPI observations

---

## 15. LIVE FLIGHT SEARCH

Ignav is the current live airfare provider.

Verify:

`Frontend → FastAPI → Ignav → normalize → optional persistence → frontend`

Test:
- India market
- INR
- one-way search
- round-trip if implemented
- adults
- cabin
- date
- airline/flight number
- origin/destination
- fare
- duration
- stops

If Ignav fails:
- use truthful fallback
- never show fake LIVE results
- label DEMO only when actually in demo mode

Do not expose the API key.
Do not make unnecessary paid/API requests.

---

## 16. SCRAPER FRAMEWORK — PRESERVE EXISTING IMPLEMENTATION

**IMPORTANT: DO NOT REMOVE, REWRITE, DISABLE, OR SIMPLIFY THE SCRAPER STRUCTURE THAT HAS ALREADY BEEN BUILT.**

The existing scraper architecture, provider adapters, compliance checks, normalization flow, source handling, and related code are part of the project and must remain intact.

Preserve all existing scraper-related:
- classes
- adapters
- provider definitions
- interfaces
- compliance checks
- robots.txt handling
- rate limiting
- anti-bot detection
- CAPTCHA detection
- session handling
- normalization
- source/data-mode labels
- tests
- documentation
- integration points

The current completion pass is focused on making the **existing implementation work correctly and making the rest of the application fully functional**.

Do NOT delete scraper code because a provider is currently unavailable.

Do NOT replace the existing scraper architecture with Ignav.

Do NOT remove provider adapters simply because direct access is currently blocked.

Do NOT add a new MakeMyTrip scraping implementation as part of this completion pass.

The existing ethical behavior must remain:
- respect robots.txt
- respect Terms of Service
- use polite rate limits
- detect CAPTCHA/anti-bot protection
- stop when blocked
- never bypass protection
- never fabricate a scraped result
- never label API data as scraped data

Preserve the existing distinction between:

`DIRECT_SCRAPER`
`IGNAV`
`AMADEUS`
`HISTORICAL`
`DEMO`

The scraper architecture should remain available for authorized/permitted sources and future provider activation.

**Scope boundary for this plan:** Do not add new instructions, implementation work, bypass strategies, or new scraping logic specifically for the MakeMyTrip issue currently under discussion. Simply preserve the existing structure exactly as part of the project.

## 17. DATABASE INTEGRITY

Verify PostgreSQL against SQLAlchemy models.

Check:
- migrations
- columns
- enum types
- sequences
- primary keys
- indexes
- foreign keys
- constraints
- timestamps

Run duplicate and required-field checks.

Remove SQLite-only assumptions from production paths.

---

## 18. FRONTEND RELIABILITY

Audit every React component for:
- missing imports
- undefined hooks
- API URL errors
- response parsing errors
- null property access
- chart data shape errors
- empty-array crashes
- filter bugs
- date formatting
- loading/error states

Pay particular attention to:
- useEffect
- all charts
- heatmap
- elasticity
- index trend
- fare comparison
- forecast
- anomalies
- DGCA
- CPI
- live search

No component may crash because an API field is null.

---

## 19. EVERY GRAPH MUST WORK

Each graph must have:
1. Real API source.
2. Correct transformation.
3. Loading state.
4. Error state.
5. Genuine empty state.
6. Filter response.
7. Correct labels/units.
8. No fabricated fallback values.

Verify:
- Fare Movement Trend
- Prototype Price Index Trend
- Airline Fare Comparison
- Route Fare Benchmarks
- Lead-Time Elasticity / Surge Curve
- Domestic Sector Heatmap
- all additional analytics charts

---

## 20. AUDIT ALL 0/NULL/EMPTY STATES

Search frontend and backend for:
- `null`
- `undefined`
- `—`
- `No observations`
- `No data`
- hardcoded `0`
- fallback constants

For every occurrence determine:
A. legitimate empty state
B. broken API/query
C. missing production data
D. frontend parsing issue
E. hardcoded prototype value

Fix B/C/D.
Keep A.
For E, connect to real data or clearly label as prototype/reference.

Do NOT blindly replace legitimate zeros/nulls.

---

## 21. COMPLETE TEST MATRIX

Backend:
- health
- fares
- routes
- airlines
- index
- route index
- prediction
- anomalies
- DGCA
- DGCA summary
- CPI
- dashboard summary
- elasticity
- live status
- live search

Frontend:
- page load
- every navigation tab
- every filter
- every graph
- prediction
- market signals
- DGCA
- CPI
- live search
- reset filters
- refresh
- direct URL loading
- responsive layout

Data:
- expected historical records in production
- no duplicate imports
- routes populated
- airlines populated
- index records where mathematically valid
- trends populated
- elasticity where data exists
- anomaly pipeline executes
- model loads

---

## 22. AUTOMATED TESTS

Run:

```bash
python -m pytest
```

and:

```bash
npm --prefix frontend run build
```

Both must pass.

Add regression tests for bugs found. Never delete tests just to obtain a passing result.

---

## 23. PRODUCTION SMOKE TEST

After deployment verify:

1. Render health = 200.
2. Expected historical data exists in PostgreSQL.
3. `/api/fares` returns genuine records.
4. DEL-BOM returns genuine historical records.
5. At least one other sufficiently populated route works.
6. Routes API works.
7. Index works where sufficient observations exist.
8. Prediction returns a valid model estimate.
9. Anomaly endpoint executes.
10. Dashboard summary has real metrics where data exists.
11. DGCA/CPI panels accurately reflect actual loading status.
12. Ignav status is truthful.
13. Frontend has no console-breaking JavaScript errors.
14. All graphs render.
15. Filters change results.
16. No secrets appear in frontend/network responses.

---

## 24. FINAL SIH CLAIMS — TRUTHFUL ONLY

After completion, the project may claim:
- working historical airfare intelligence platform
- genuine historical fare database
- automated cleaning/normalization
- prototype Airfare Price Index
- lead-time analysis
- airline/route comparisons
- ML fare prediction
- anomaly detection
- DGCA aviation context where loaded
- MoSPI/CPI reference context
- live airfare integration through Ignav
- ethical scraper architecture
- deployed React + FastAPI + PostgreSQL system

Do NOT claim:
- live MakeMyTrip scraping
- complete live scraping of every listed airline/OTA
- IP rotation
- anti-bot bypass
- official Government of India APIx
- official NSO/RBI production integration unless actually implemented
- official DGCA daily fare observations unless actually available
- 30-day continuous live scraping unless actually executed

---

# 25. DEFINITION OF DONE

The implementation is complete only when:
- production data is accessible
- API responses are correct
- filters work
- index works where mathematically valid
- all charts render
- prediction works
- anomaly detection executes
- DGCA/CPI context works according to available data
- live search works/falls back truthfully
- no frontend runtime errors remain
- no unexplained 0/null/— values remain where data should exist
- full backend tests pass
- frontend build passes
- production smoke test passes
- no fabricated data has been introduced
- no secrets have been exposed

## FINAL INSTRUCTION TO THE IMPLEMENTATION AGENT

Do not stop after finding one issue.

Audit the ENTIRE application against this document and continue fixing every genuine missing connection, broken query, missing import, schema mismatch, frontend parsing bug, chart-data issue, production seeding issue, or deployment issue until the Definition of Done is satisfied.

Do not implement direct MakeMyTrip scraping in this pass.

At the end report:
1. Exact files changed.
2. Exact commits.
3. Production observation count.
4. Route count.
5. Airline count.
6. Index records available.
7. DGCA record count.
8. CPI record count.
9. Live provider status.
10. Full pytest result.
11. Frontend build result.
12. Production smoke-test result.
13. Any remaining limitation, only if genuinely unavoidable.
