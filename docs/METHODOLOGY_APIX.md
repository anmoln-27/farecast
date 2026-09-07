# Econometric & Statistical Methodology: Real-Time Airfare Price Index (APIx)

**Target Audience:** Econometricians, National Statistical Office (NSO / MoSPI), Reserve Bank of India (RBI) Monetary Policy Committee.

---

## 1. Problem Definition & Context

In India's official Consumer Price Index (CPI Base 2012=100), air travel is nested inside the **Transport & Communication** subgroup. However, official CPI numbers suffer from:
1. **Low Frequency & Latency**: Monthly dissemination with a ~12-day reporting lag.
2. **Fixed Sampling Vulnerability**: Relying on static quotes from ticketing counters or manual portal checks that miss real-time dynamic pricing surges.
3. **Advance Purchase Blind Spot**: Airline revenue management algorithms price identical seats with 200%–400% premiums based on purchase lead-time ($T+45 \to T+1$).

The **Real-Time Airfare Price Index (APIx)** resolves these challenges by introducing high-frequency statistical index construction with multi-window stratification and passenger-traffic weighting.

---

## 2. Statistical Formulations

### 2.1 Elementary Route Aggregation (Micro-Level)
At the route-window level, elementary price relatives are aggregated using the **Jevons Geometric Mean** formulation to prevent substitution distortion:

$$P_{r,w,t} = \left( \prod_{i=1}^{N_{r,w}} p_{i,r,w,t} \right)^{\frac{1}{N_{r,w}}}$$

where $p_{i,r,w,t}$ represents the $i$-th observed gross bookable fare on route $r$ in window $w$ at time $t$.

### 2.2 Advance-Purchase Window Stratification
Fares across identical routes exhibit extreme elasticity as the departure date approaches. APIx integrates empirical passenger booking volume weights ($\alpha_w$) established by aviation market studies:

$$\bar{P}_{r,t} = \sum_{w \in W} \alpha_w P_{r,w,t}$$

| Window Bucket | Days to Departure | Booking Share Weight ($\alpha_w$) | Market Segment |
| :--- | :--- | :--- | :--- |
| **T+1** | 1 day | 0.15 | Spot / Urgent / Last-minute business |
| **T+7** | 2 – 7 days | 0.35 | Weekly business / Late leisure |
| **T+15** | 8 – 15 days | 0.25 | Standard planned domestic travel |
| **T+30** | 16 – 30 days | 0.15 | Planned holiday / Leisure |
| **T+45** | > 30 days | 0.10 | Early bird / Promotional saver |

$$\sum_{w \in W} \alpha_w = 0.15 + 0.35 + 0.25 + 0.15 + 0.10 = 1.00$$

### 2.3 Laspeyres Price Index (Headline APIx)
The base-period weighted Laspeyres index formulation applies official DGCA domestic passenger traffic weights ($w_{r,0}$):

$$I_{\text{Laspeyres}, t} = \sum_{r} w_{r,0} \left( \frac{\bar{P}_{r,t}}{\bar{P}_{r,0}} \right) \times 100$$

where:
- $\bar{P}_{r,t}$ is the stratified average fare for route $r$ in period $t$.
- $\bar{P}_{r,0}$ is the baseline average fare for route $r$ during the baseline period ($2022\text{-}01$).
- $w_{r,0}$ is the route's annual passenger traffic weight derived from DGCA domestic scheduled traffic statistics.

### 2.4 Fisher Ideal Price Index
To eliminate upward substitution bias during periods of rapid fare inflation, APIx also computes the **Fisher Ideal Price Index**:

$$I_{\text{Fisher}, t} = \sqrt{I_{\text{Laspeyres}, t} \times I_{\text{Paasche}, t}}$$

where the Paasche component utilizes current-period capacity/traffic distributions.

---

## 3. Official DGCA Route Passenger Traffic Weights ($w_{r,0}$)

The top domestic sectors represent over 65% of India's scheduled domestic passenger throughput:

| Sector Pair | Origin ⇄ Destination | Annual Pax Share ($w_{r,0}$) | Normalised Weight |
| :--- | :--- | :--- | :--- |
| **DEL-BOM** | Delhi ⇄ Mumbai | 18.5% | 0.185 |
| **DEL-BLR** | Delhi ⇄ Bengaluru | 14.2% | 0.142 |
| **BOM-BLR** | Mumbai ⇄ Bengaluru | 10.1% | 0.101 |
| **DEL-CCU** | Delhi ⇄ Kolkata | 8.6% | 0.086 |
| **BLR-HYD** | Bengaluru ⇄ Hyderabad | 7.4% | 0.074 |
| **MAA-DEL** | Chennai ⇄ Delhi | 7.1% | 0.071 |
| **BOM-GOI** | Mumbai ⇄ Goa | 5.8% | 0.058 |
| **DEL-PNQ** | Delhi ⇄ Pune | 5.2% | 0.052 |
| **DEL-AMD** | Delhi ⇄ Ahmedabad | 4.6% | 0.046 |
| **BOM-CCU** | Mumbai ⇄ Kolkata | 4.5% | 0.045 |
| **Other / Regional** | All other domestic city-pairs | 4.0% | 0.040 |
| **Total Basket** | | **100.0%** | **1.000** |

---

## 4. Disaggregated Component Decomposition

Every fare quote is cleansed and disaggregated to provide component-level inflation visibility:

$$\text{Gross Bookable Fare} = \text{Base Tariff} + \text{Taxes \& Surcharges} + \text{Airport UDF} + \text{Convenience Fee}$$

1. **Base Fare**: The unbundled airline seat tariff subject to yield management algorithms.
2. **Taxes & Surcharges**: GST (5% for Economy, 12% for Business) + Aviation Security Fee (ASF: ₹236 flat).
3. **User Development Fee (UDF)**: Airport-specific capital charge fixed by the Airports Economic Regulatory Authority (AERA) (e.g. DEL: ₹300, BLR: ₹350, BOM: ₹275).
4. **Convenience Fee**: Web transaction fee charged by airlines/OTAs (₹350 flat).

This disaggregation allows MoSPI to separate **core carrier pricing power** from regulatory airport fee changes and fuel surcharges.

---

## 5. Frequency Hierarchy

| Index Frequency | Aggregation Period | Use Case |
| :--- | :--- | :--- |
| **Daily APIx** | Rolling 24-hour observation sweep | RBI financial stability monitoring, holiday shock tracking |
| **Weekly APIx** | 7-day volume-weighted moving average | Leading indicator for discretionary transport services inflation |
| **Monthly APIx** | Full calendar month compilation | MoSPI official CPI Transport & Communication benchmarking |
