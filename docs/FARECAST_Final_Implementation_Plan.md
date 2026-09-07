# FARECAST — FINAL IMPLEMENTATION PLAN
## SIH 26056 — India Airfare Intelligence Platform

### Objective
Transform the existing FARECAST codebase into a genuinely working, deployable airfare intelligence platform — not a static UI, fake dashboard, or presentation-only demo.

Target architecture:

REAL DATA SOURCES
→ DATA INGESTION / NORMALIZATION
→ POSTGRESQL
→ AIRFARE INDEX + ANALYTICS + ML + ANOMALY DETECTION
→ FASTAPI
→ REACT DASHBOARD
→ VERCEL + RENDER

---

# 1. EXECUTION RULE

First inspect the existing repository and implementation plan. Determine what is already working, what is partially implemented, and what is missing. Then implement the missing functionality yourself.

Do NOT rebuild working functionality unnecessarily.
Do NOT fabricate data.
Do NOT stop at an audit or report.
After implementation, run tests, build the frontend, and verify the complete data flow.

---

# 2. SIH REQUIREMENTS

The platform must address:
- Automated airfare data collection
- Airline and OTA source integration where permitted
- JavaScript-rendered source handling
- Ethical scraping and rate limiting
- Fare cleaning and normalization
- Representative Indian city-pair basket
- DGCA-supported route relevance
- T+1, T+7, T+15, T+30, T+45 advance-purchase windows
- Real-time Airfare Price Index
- Daily, weekly and monthly index analysis
- Base fare/tax/fee handling where source data supports it
- Outlier and missing-data handling
- Cancellation/sold-out handling where source data provides it
- Fare trends
- Sector-wise heatmap
- Lead-time elasticity
- Airline comparisons
- Route comparisons
- ML fare prediction
- Anomaly detection
- API for downstream NSO/RBI consumption
- Documentation
- Automated testing
- 30+ day historical/backtesting capability
- DGCA/reference comparison only where legitimate public fare/reference data exists

Never claim the FARECAST index is an official Government of India statistic.

---

# 3. REAL DATA SOURCES

## 3.1 Kaggle — Primary Historical Airfare Dataset
Source:
https://www.kaggle.com/datasets/shubhambathwal/flight-price-prediction

Existing file:
`data/raw/Clean_Dataset.csv`

Approximately 300k historical Indian airfare observations.

Use this as the primary historical airfare/ML dataset. Load real observations into PostgreSQL through a repeatable ingestion pipeline. Do not keep production analytics limited to the current 9 seeded records.

## 3.2 GitHub — Historical Fare Data
Repository:
https://github.com/Avij112/flight-fare-analysis

Important file:
`full_fare.csv`

Use genuine observed 2022–2023 fare observations where available. Do not treat interpolated/reference years as observed airfare. Maintain source provenance.

## 3.3 Amadeus — Live Airfare
Developer platform:
https://developers.amadeus.com/

Use the existing Flight Offers Search integration.

Architecture:
React → FastAPI → Amadeus → normalized fare response → React

Credentials must remain server-side:
`AMADEUS_CLIENT_ID`
`AMADEUS_CLIENT_SECRET`
`AMADEUS_BASE_URL`

Never expose credentials in frontend code or commit them.

Maintain DEMO_MODE fallback.

Clearly label:
- LIVE = actual Amadeus response
- HISTORICAL = historical dataset
- DEMO/SIMULATION = simulated test data

Do not claim complete Indian airline/route coverage.

## 3.4 DGCA / data.gov.in
Use genuine official DGCA/data.gov.in aviation information for:
- passenger traffic
- flights
- seats/capacity
- load factor
- route relevance
- aviation market context

Use it to support representative route selection and weighting only where the underlying data supports the calculation.

Do not represent traffic/capacity data as airfare observations.
Do not invent DGCA fare values.
If route weights cannot be calculated directly from official data, label them `Prototype Reference Weights`.

## 3.5 MoSPI / CPI
Official reference:
https://cpi.mospi.gov.in/

Use MoSPI/CPI as macroeconomic/reference context. Clearly distinguish FARECAST airfare observations from MoSPI CPI reference data. Do not invent CPI values or official CPI weights. Do not present FARECAST as an official CPI feed.

---

# 4. DATABASE & HISTORICAL DATA

Inspect the existing database schema.

Support, where source data provides them:
- source
- data_mode
- airline
- airline_code
- flight_number
- origin
- destination
- travel_date
- booking/collection date
- departure time
- arrival time
- stops
- duration
- cabin class
- days_left
- advance_purchase_window
- base_fare
- taxes
- UDF
- convenience_fee
- total_fare
- currency
- collected_at

Do not invent unavailable fare components.

## Historical ingestion
Load the real Kaggle dataset through a batch/repeatable process.
Load genuine GitHub 2022–2023 observations where useful.
Add database indexes for origin/destination, travel_date, airline, days_left, advance_purchase_window, data_mode, and source.
Use batching and deduplication.

After ingestion report:
- total records
- source counts
- date range
- routes
- airlines
- data modes

The production database must contain enough REAL historical data for meaningful analytics.

---

# 5. DATA CLEANING

Implement/verify:
- duplicate removal
- missing-value handling
- invalid fare detection
- invalid route/date handling
- airline normalization
- airport/city normalization
- duration normalization
- outlier handling
- cancellation handling where available
- sold-out handling where available

Do not remove legitimate high fares merely because they are expensive.
Keep source provenance.

---

# 6. FARE COMPONENTS

If a source provides base fare, taxes, UDF, convenience charges, and total fare, store the actual values.

If a source only provides total fare:
- preserve actual total fare
- leave unavailable components null

Do NOT present heuristic decomposition as observed source data.

If the existing 72% decomposition model is retained, label it:
`Reference Tariff Decomposition — Estimated`

---

# 7. ADVANCE-PURCHASE WINDOWS

Implement real analysis using `days_left`.

Required:
- T+1
- T+7
- T+15
- T+30
- T+45

Do not merely display labels.

For each window calculate from real observations:
- average fare
- median fare where appropriate
- min/max where appropriate
- observation count
- index/sub-index where sufficient data exists

If a window lacks sufficient observations, show that honestly.

---

# 8. REPRESENTATIVE ROUTE BASKET

Build a transparent basket of relevant domestic routes.

Candidate routes:
- DEL-BOM
- DEL-BLR
- BOM-BLR
- DEL-CCU
- BLR-HYD
- MAA-DEL

and other routes supported by actual aviation data.

Use DGCA traffic information where available to establish route relevance/weights.

If weights are prototype-derived, label them `Prototype Reference Weights`.
Do not claim official government weights.

---

# 9. AIRFARE PRICE INDEX

Implement a transparent, data-driven index.

Baseline concept:
`Index = Current weighted fare / Baseline weighted fare × 100`

Support:
- route-level index
- composite/basket index
- daily frequency
- weekly frequency
- monthly frequency
- baseline period
- current period
- advance-window sub-indices

Where appropriate, support mathematically valid Laspeyres/Fisher methodology.

Do not show hardcoded fallback index values when real data is unavailable.

If insufficient data:
`Index unavailable — insufficient observations`

Dashboard example:
`117.4`
`↑ 17.4% vs baseline`

with a clear prototype disclaimer.

---

# 10. 30+ DAY HISTORICAL TIME SERIES

Use real historical data to create meaningful time-series analysis.

Where source data supports it, provide:
- daily fare series
- daily index
- weekly index
- monthly index

Show actual date coverage and observation counts.
Do not fabricate a 30-day series.

---

# 11. BACKTESTING

The current synthetic benchmark must NOT be presented as official DGCA validation.

First determine whether a legitimate publicly available DGCA fare/reference series exists.

If it exists, compare FARECAST against the actual reference and calculate:
- MAE
- RMSE
- MAPE
- correlation
- directional accuracy
- tracking error

If no valid public DGCA fare-reference series is available, clearly state:
`DGCA fare validation dataset not available in connected public sources.`

The existing synthetic benchmark can remain only as:
`Synthetic Benchmark Simulation — Methodology Demonstration`

Never label synthetic results as official DGCA validation.
Never fabricate government validation metrics.

---

# 12. LEAD-TIME ELASTICITY

Build a real relationship between:
`days_left` and `observed fare`

Visualize:
T+45 → T+30 → T+15 → T+7 → T+1

Use actual observations. Show observation counts and fare movement.

---

# 13. DASHBOARD

Preserve the existing visual design unless changes are necessary.

All analytical values must come from the backend.

## Market Overview
- average fare
- minimum fare
- maximum fare
- observation count
- current index
- baseline comparison

## Fare Trend
Real historical observations.

## Index Trend
Real calculated index observations.

## Airline Comparison
Real database aggregation.

## Route Comparison
Real database aggregation.

## Sector Heatmap
Real route/window observations.

## Lead-Time Elasticity
Real days_left/fare relationship.

## Market Signals
Real anomaly results.

## Fare Forecast
Real ML output.

## DGCA Context
Official aviation context only.

## MoSPI/CPI
Published CPI reference/context only.

## Live Amadeus
Actual live results when configured.

---

# 14. FILTERS

Ensure these work consistently:
- Origin
- Destination
- Travel Date
- Airline
- Cabin Class
- Advance Purchase Window
- Apply Filters
- Reset

Filters must update all relevant dashboard sections.
Reset must return to the intended default/all-data state.
Do not leave stale route/index state after Reset.

---

# 15. ML MODEL

Preserve the existing genuine Random Forest model.

Verify:
historical dataset → preprocessing → model → saved artifact → backend → prediction API → frontend

Do not retrain unnecessarily.

Ensure prediction displays correct monetary units.

Use:
`Estimated Fare: ₹X`
`Estimated Fare Range: ₹Y — ₹Z`
`Model Uncertainty: ±₹N`

if applicable.

Never display monetary uncertainty as a percentage.
Keep prediction disclaimer.

---

# 16. ANOMALY DETECTION

Preserve/use:
- IQR
- Isolation Forest

Run on actual observations.

Display:
- signal count
- route
- fare
- severity/reason

Do not use hardcoded anomaly results.

---

# 17. SCRAPING ENGINE

Inspect the existing scraper architecture.

Current simulator functionality may be retained for testing, but simulated records MUST be labelled:
`DEMO` or `SIMULATION`

Never `LIVE`.

For sources where automated collection is legally and technically permitted, implement appropriate adapters using tools such as:
- Playwright
- Scrapy

Potential sources:
Airlines:
- IndiGo
- Air India
- Air India Express
- Akasa Air
- SpiceJet

OTAs:
- MakeMyTrip
- Yatra
- EaseMyTrip
- Cleartrip
- Ixigo
- Goibibo

Only implement compliant collection.

Respect:
- robots.txt
- terms of service
- rate limits
- reasonable request frequency
- session handling

Do NOT bypass CAPTCHAs or anti-bot protections.
Do NOT use abusive IP rotation.

If a source cannot be accessed legitimately, label it unavailable rather than pretending it is live.

---

# 18. NSO/RBI API

Preserve the regulatory API architecture.

Potential endpoints:
- `/api/v1/nso/apix`
- `/api/v1/nso/apix/export`
- `/api/v1/rbi/macro-feed`
- `/api/v1/analytics/backtest-results`

Ensure endpoints return real calculated data OR clearly labelled prototype/reference data.

Never make the system appear to be an official MoSPI/RBI feed.
Include clear prototype disclaimers.

---

# 19. API

Preserve and verify:
- `/health`
- `/api/fares`
- `/api/routes`
- `/api/airlines`
- `/api/index`
- `/api/index/{origin}/{destination}`
- `/api/prediction`
- `/api/anomalies`
- `/api/dgca`
- `/api/dgca/summary`
- `/api/cpi`
- `/api/dashboard/summary`
- `/api/live/status`
- `/api/live/search`

Ensure frontend response parsing exactly matches backend schemas.
Do not silently turn API errors into misleading zeros or empty analytics.

---

# 20. DATA MODES

Use:
`LIVE`
`HISTORICAL`
`DEMO`
`REFERENCE`

Examples:
Kaggle → HISTORICAL
GitHub historical → HISTORICAL
Amadeus actual response → LIVE
Simulator → DEMO/SIMULATION
DGCA/MoSPI contextual records → REFERENCE where appropriate

Never mix modes incorrectly.

---

# 21. DEPLOYMENT

Preserve:
Frontend → Vercel
Backend → Render
Database → Render PostgreSQL

Verify:
- frontend/backend connection
- backend/database connection
- backend/model connection
- backend/Amadeus connection
- CORS
- environment variables
- production build

Secrets remain server-side.

Do not commit `.env`, database passwords, Amadeus credentials, or API secrets.

---

# 22. TESTING

Maintain and extend automated tests.

Test:
- data ingestion
- normalization
- cleaning
- database operations
- API endpoints
- filters
- index calculations
- advance windows
- lead-time analysis
- anomaly detection
- ML prediction
- Amadeus error handling
- scraper modes
- backtesting

Run:
`python -m pytest tests/ -q`

and:
`cd frontend && npm run build`

Also run production/API smoke tests.

---

# 23. CURRENT KNOWN ISSUES TO FIX

The verification identified:

1. Only 9 real Kaggle records are currently in the database.
2. ~300k Kaggle historical rows are available locally but not ingested.
3. GitHub fare source needs proper ingestion.
4. Scraper simulators were incorrectly labelled LIVE.
5. DGCA route weights are hardcoded prototype estimates.
6. Synthetic backtest was incorrectly described as DGCA validation.
7. APIx contains hardcoded fallback values.
8. Lead-time/heatmap components contain static arrays.
9. Fare component decomposition is heuristic rather than source-observed.
10. Dashboard previously showed missing fare statistics/charts.
11. ML uncertainty formatting needs correction.
12. Filters and Reset must be fully verified.

Fix these without breaking existing working functionality.

---

# 24. IMPLEMENTATION PRIORITY

## P0 — Critical
1. Real historical data ingestion
2. PostgreSQL performance/indexing
3. Frontend ↔ backend correctness
4. Fare statistics
5. Filters + Reset
6. Real dashboard charts
7. Data-driven APIx
8. Remove hardcoded analytical fallbacks
9. Correct LIVE/DEMO data modes
10. Verify ML production pipeline
11. Correct uncertainty formatting
12. Automated tests/build

## P1 — High Priority SIH Features
13. T+1/T+7/T+15/T+30/T+45
14. 30+ day historical analysis
15. Representative route basket
16. Defensible route weights
17. Daily/weekly/monthly index
18. Lead-time elasticity
19. Sector heatmap
20. Airline comparison
21. Route comparison
22. Real anomaly analytics
23. Real Amadeus integration
24. Legitimate backtesting/reference comparison

## P2 — Important Extensions
25. Real permitted airline/OTA adapters
26. Scheduled ingestion
27. Additional source coverage
28. Advanced data-quality monitoring
29. Richer API/export functionality

## P3 — Production-scale Enhancements
30. Larger-scale scraper orchestration
31. Advanced source/session infrastructure
32. Production scheduling and monitoring
33. Additional forecasting models

---

# 25. FINAL DEFINITION OF DONE

A user must be able to:
1. Open the deployed website.
2. Select an Indian route.
3. Select airline/cabin/date/window.
4. Apply filters.
5. Reset filters.
6. See real historical fare observations.
7. See average/min/max fare.
8. See fare movement over time.
9. Compare airlines.
10. Compare routes.
11. See sector-level fare intensity.
12. Analyze T+1/T+7/T+15/T+30/T+45.
13. See lead-time elasticity.
14. See a real data-driven Airfare Price Index.
15. See index movement against baseline.
16. See anomaly/market signals.
17. Get an actual ML fare estimate.
18. See correct prediction uncertainty/range.
19. See DGCA aviation context.
20. See MoSPI/CPI reference context.
21. Run live Amadeus search when credentials are configured.
22. Clearly distinguish LIVE/HISTORICAL/DEMO/REFERENCE.
23. Access functioning API endpoints.
24. See genuine data provenance.
25. Use the system without relying on hardcoded mock analytical values.

The website must be a real working airfare intelligence platform.

It must never present:
- synthetic data as real
- simulated fares as LIVE
- traffic data as fare data
- estimated fare components as observed components
- prototype weights as official weights
- synthetic backtesting as official DGCA validation
- prototype APIx values as official Government statistics

---

# 26. FINAL REPORT

After implementation report:
- features already present before changes
- features added/fixed
- total real historical fare records loaded
- source breakdown
- date coverage
- route coverage
- airline coverage
- advance-window coverage
- index records
- index methodology
- ML model and genuine metrics
- anomaly status
- Amadeus status
- scraper status
- DGCA data actually used
- MoSPI data actually used
- backtest status
- tests passed
- frontend build status
- deployment status
- remaining external/data limitations

Do not claim a feature is complete unless it is actually connected and verified.

FINAL EXECUTION RULE:

INSPECT → IMPLEMENT → TEST → VERIFY.

Do not stop at the audit.
Do not fabricate data.
Do not rebuild the existing project unnecessarily.
