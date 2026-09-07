# NSO & RBI Regulatory Consumption API: Complete Interface Specification

**Base URL:** `http://localhost:8000/api/v1`  
**OpenAPI / Swagger Spec:** `http://localhost:8000/docs`  
**Primary Consumers:** Ministry of Statistics and Programme Implementation (MoSPI / NSO), Reserve Bank of India (RBI) Monetary Policy Department.

---

## 1. Overview

The Regulatory API tier provides specialized RESTful feeds designed to deliver:
1. High-frequency price index series conforming to international statistical formats (SDMX / MoSPI dissemination guidelines).
2. Direct CSV download for integration into NSO econometric pipelines.
3. Macro-prudential inflation indicators and surge alerts for the Monetary Policy Committee (MPC).
4. Continuous 30-day DGCA backtest statistical validation metrics.

---

## 2. Endpoint Specifications

### 2.1 MoSPI / NSO Real-Time Airfare Price Index (APIx) Feed
**Endpoint:** `GET /api/v1/nso/apix`

#### Query Parameters
| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `frequency` | `string` | No | `monthly` | Aggregation cycle: `daily`, `weekly`, or `monthly`. |
| `sub_index` | `string` | No | `COMPOSITE` | Filter sub-index: `COMPOSITE`, `T+1_SPOT`, `T+7_WEEK`, `T+15_STANDARD`, `T+30_PLANNED`, `T+45_EARLY`, or `ALL`. |
| `route` | `string` | No | `None` | Target route code (e.g. `DEL-BOM`) or `AGGREGATE` for national headline index. |
| `period` | `string` | No | `None` | Period label filter (e.g. `2023-05` or `2023-W22`). |

#### Response Schema (`200 OK`)
```json
{
  "institution": "Ministry of Statistics and Programme Implementation (MoSPI / NSO)",
  "index_name": "Real-time Airfare Price Index (APIx)",
  "frequency": "monthly",
  "sub_index": "COMPOSITE",
  "headline_apix": 114.62,
  "base_period": "2022-01",
  "methodology": {
    "formula": "Laspeyres / Fisher Ideal Index",
    "weighting_source": "DGCA Domestic Scheduled Passenger Traffic Basket",
    "advance_windows": ["T+1", "T+7", "T+15", "T+30", "T+45"],
    "disaggregation": [
      "Base Fare",
      "Taxes & Surcharges",
      "UDF (User Development Fee)",
      "Web Convenience Fee"
    ]
  },
  "total_records": 9,
  "data": [
    {
      "route": "AGGREGATE",
      "period": "2023-05",
      "frequency": "monthly",
      "sub_index": "COMPOSITE",
      "index_value": 114.62,
      "current_avg_fare_inr": 5731.0,
      "baseline_fare_inr": 5000.0,
      "dgca_traffic_weight": 1.0,
      "observation_count": 848
    },
    {
      "route": "DEL-BOM",
      "period": "2023-05",
      "frequency": "monthly",
      "sub_index": "COMPOSITE",
      "index_value": 112.45,
      "current_avg_fare_inr": 5454.0,
      "baseline_fare_inr": 4850.0,
      "dgca_traffic_weight": 0.185,
      "observation_count": 182
    }
  ]
}
```

---

### 2.2 MoSPI CSV Dissemination Export
**Endpoint:** `GET /api/v1/nso/apix/export`

Returns a standard CSV file directly downloadable for integration with MoSPI statistical systems.

#### Query Parameters
| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `frequency` | `string` | No | `monthly` | `daily`, `weekly`, or `monthly`. |

#### Response Headers
- `Content-Type`: `text/csv; charset=utf-8`
- `Content-Disposition`: `attachment; filename=mospi_apix_monthly_2026-09-08.csv`

#### CSV Output Columns
`Period, Frequency, Route, Sub_Index, APIx_Index_Value, Current_Avg_Fare_INR, Baseline_Fare_INR, DGCA_Traffic_Weight, Observation_Count, Data_Source`

---

### 2.3 RBI Monetary Policy Macro-Prudential Feed
**Endpoint:** `GET /api/v1/rbi/macro-feed`

Specialized high-frequency feed tailored for central bank economists and the Monetary Policy Committee (MPC) to gauge real-time discretionary services pricing pressure.

#### Response Schema (`200 OK`)
```json
{
  "institution": "Reserve Bank of India (RBI) — Monetary Policy Committee Feed",
  "timestamp": "2026-09-08T00:07:00.000Z",
  "core_indicators": {
    "headline_apix": 114.62,
    "annualized_momentum_pct": 14.62,
    "spot_t1_index": 185.40,
    "planned_t30_index": 108.20,
    "advance_booking_volatility_spread_pct": 71.35,
    "inflation_signal": "MODERATE_ELEVATION",
    "mpc_alert_triggered": false
  },
  "dgca_benchmark_alignment": {
    "pearson_correlation_30d": 0.9687,
    "tracking_error": 1.9308,
    "validation_status": "VALIDATED"
  },
  "sector_hotspots": [
    {
      "sector": "DEL-BOM",
      "surge_status": "ELEVATED",
      "spot_premium_multiplier": 3.1
    },
    {
      "sector": "DEL-BLR",
      "surge_status": "ELEVATED",
      "spot_premium_multiplier": 2.8
    }
  ],
  "policy_brief": "Air travel price volatility serves as an early-cycle proxy for discretionary services pricing power and fuel pass-through elasticity prior to official CPI monthly releases."
}
```

---

### 2.4 30-Day DGCA Backtesting Validation Results
**Endpoint:** `GET /api/v1/analytics/backtest-results`

Returns statistical metrics, tracking error, and daily comparison time-series.

#### Response Schema (`200 OK`)
```json
{
  "status": "success",
  "backtest_window_days": 35,
  "metrics": {
    "pearson_correlation": 0.9687,
    "mape_percent": 1.09,
    "directional_accuracy_percent": 88.2,
    "tracking_error": 1.9308,
    "volatility_ratio": 1.047,
    "benchmark_routes_count": 5
  },
  "validation_status": "VALIDATED",
  "regulatory_compliance": {
    "mospi_standard_aligned": true,
    "rbi_macro_criteria_met": true,
    "notes": "Meets MoSPI CPI Quality Framework criteria for real-time leading indicator."
  },
  "daily_comparison": [
    {
      "date": "2026-09-07",
      "dgca_fare_inr": 4849.0,
      "dgca_index": 103.25,
      "apix_fare_inr": 4825.0,
      "apix_index": 102.75,
      "percentage_error": 0.48
    }
  ]
}
```
