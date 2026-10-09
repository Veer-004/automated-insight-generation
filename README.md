# Auto-Analytics Engine — Automated Insight Generation (Assignment 4)

A general-purpose analytics engine plus Streamlit dashboard. It reads a district-level
healthcare CSV and **automatically** finds trends, outliers, correlations and threshold
breaches, then writes human-readable insights. No narrative or number is hardcoded:
everything is calculated from whatever CSV is loaded.

**Stack:** Python · Streamlit · Pandas · NumPy · Plotly (no separate backend/API).

---

## 1. How to run

```bash
# 1. (optional) create a virtual environment
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS/Linux: source .venv/bin/activate)

# 2. install dependencies
pip install -r requirements.txt

# 3. launch the dashboard  ->  opens http://localhost:8501
streamlit run app.py

# 4. (optional) command-line version: prints head()/info()/missing values
#    and writes outputs/insights.csv, outputs/sample_insights.json, outputs/correlation_matrix.csv
python generate_insights.py
python generate_insights.py data/extended_data.csv --threshold 15 --method Z-score --z 2.5
```

---

## 2. Project structure

| File | Purpose |
| :--- | :--- |
| `analytics.py` | **The engine.** All loading, validation, detection and insight logic (no UI). |
| `app.py` | Streamlit dashboard: sidebar filters + sliders, charts, tables, CSV/JSON downloads. |
| `ui.py` | Look-and-feel only: light/dark palettes + theme toggle, CSS, hero/KPI/insight cards, Plotly chart theme, table colouring. |
| `.streamlit/config.toml` | Light theme colours for all Streamlit widgets. |
| `assets/logo.png` | Project logo (shown in the header and sidebar; embedded via a project-relative path). |
| `generate_insights.py` | CLI runner; prints Part A diagnostics and saves output files. |
| `data/sample_data.csv` | The 12-row dataset from the assignment (6 districts × 2 months). |
| `data/extended_data.csv` | Synthetic 40-row dataset (10 districts × 4 months) meeting the recommended size. |
| `outputs/` | Generated `insights.csv`, `sample_insights.json`, `correlation_matrix.csv`. |
| `requirements.txt` | Python dependencies. |

---

## 3. How each part works

### Part A — Loading & validation (`load_data`, `validate_data`)
* Reads the CSV with `skipinitialspace=True` (the sample has `", "` separators), lower-cases headers,
  normalises `month` (`2026-07` or `2026-07-01` → `2026-07`) and coerces indicators to numbers.
* Any numeric column becomes an indicator (`get_indicators`), so new indicators work automatically.
* Validation reports `head()`, `info()`, missing values per column, duplicate (district, month) rows,
  and warns when there are < 3 months per district or < 10 districts.
* UI filters: **district, month, indicator** (multi-select). All results recompute live on the filtered data.

### Part B — Trend detection (`detect_trends`)
* Data is reshaped to long format; for each (district, indicator) the previous month's value is found with `groupby().shift(1)`.
* `pct_change = (current − previous) / previous × 100`
* `is_significant = |pct_change| ≥ threshold` (slider, default **10%**).

### Part C — Outlier detection (`detect_outliers`)
* Per indicator, across all filtered rows. Method is selectable in the UI:
  * **IQR** (default): outlier if `value < Q1 − k·IQR` or `value > Q3 + k·IQR` (k slider, default 1.5).
  * **Z-score**: outlier if `|value − mean| / std ≥ z` (slider, default 3).
* Each outlier lists district, indicator, month, value, mean, z-score and bounds.
* Note: with 12 rows the largest possible |z| is ≈ 3.2, so z = 3 rarely fires on the sample — IQR is the better default for tiny data.

### Part D — Correlation detection (`compute_correlation`, `flag_correlations`)
* Standard `df.corr(method="pearson")` matrix (shown as a heatmap, exported as CSV).
* Pairs with `|r| ≥ threshold` (slider, default **0.70**) are flagged.
* `top_contributor` names the district that drives each correlation most
  (Pearson r is the average of `z_a × z_b`, so the district with the largest product dominates).

### Threshold breaches (`detect_threshold_breaches`)
* For coverage (%) indicators, each district's **latest** value below the coverage target (slider, default 80%) is flagged.
* `high_risk_cases` is a raw count, so it is covered by trends/outliers instead.

### Part E — Insight generation (`generate_insights`)
Every finding becomes one row with the required fields:

`insight_id, type, indicator, entity, period, value, prev_value, change_pct, severity, explanation`

| type | value | prev_value | change_pct |
| :--- | :--- | :--- | :--- |
| trend | current month | previous month | % change |
| outlier | value | indicator mean | % deviation from mean |
| correlation | r | n/a | n/a |
| threshold_breach | value | target | % gap below target |

Explanations are sentence templates filled with numbers from the data. Insights are sorted High → Low and numbered `INS-0001…`.

### Severity (Low / Medium / High) — derived from the configurable thresholds
Each finding gets a **ratio = how many times it exceeds its configured threshold**:

| Finding | ratio |
| :--- | :--- |
| Trend | `|pct_change| / trend_threshold` |
| Outlier (IQR) | distance beyond the nearest quartile ÷ (k·IQR) — 1.0 = exactly on the fence |
| Outlier (Z) | `|z| / z_threshold` |
| Breach | `gap_pct / trend_threshold` |

`ratio ≥ 1.5 → High`, `ratio ≥ 1.25 → Medium`, otherwise `Low` (constants `HIGH_MULTIPLIER`, `MEDIUM_MULTIPLIER` in `analytics.py`).
Changing a slider therefore changes severities too. **Improvements** (e.g. high-risk cases falling, coverage unusually high)
are reported but always `Low`, because severity means "needs attention".
For correlations, severity reflects where `|r|` sits between the threshold and 1.0 (top third = High, middle = Medium).

### Part F — UI
* KPI cards, **severity bar chart**, insights-by-type chart, top-insight cards, full insight table with severity/type filters.
* **Per-district line chart** (Trends tab), box plot with outliers marked (Outliers tab), **correlation heatmap** (Correlations tab).
* **Light / Dark mode** switch at the top of the sidebar. The choice is kept in `st.session_state`
  and in the URL (`?theme=dark`), so it survives reruns and page refreshes.
* CSV downloads for insights (also JSON), trends, outliers, correlation matrix, flagged pairs and filtered data.

---

## 4. Sample output (generated by `python generate_insights.py`)

From `outputs/insights.csv`, sample data, default thresholds:

| id | type | entity | indicator | value | prev | change % | severity |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: | :--- |
| INS-0002 | trend | Mehsana | anc_coverage | 42 | 84 | −50.0 | High |
| INS-0004 | trend | Ahmedabad | anc_coverage | 69 | 85 | −18.8 | High |
| INS-0006 | outlier | Mehsana | anc_coverage | 42 | 78.3 | −46.4 | High |
| INS-0007 | correlation | All districts | anc_coverage:high_risk_cases | r = −0.93 | | | High |

> "ANC coverage in Ahmedabad dropped by 18.8% compared to the previous month (85% in 2026-07 -> 69% in 2026-08), exceeding the 10% significant-change threshold. This is a deterioration."

> "ANC coverage and high risk cases show a negative correlation (r = -0.93, n = 12 rows) ... Largest contributor: Mehsana."

The full list is in `outputs/sample_insights.json`.

---

## 5. Limitations (stated honestly)
* **Correlation on 12 rows is fragile.** With 2 months × 6 districts, one extreme district (Mehsana) can create a "strong"
  correlation by itself (here r(anc, high_risk) = −0.93, driven largely by Mehsana). Treat flagged pairs as leads, not proof.
  The dashboard shows this warning on the Correlations tab.
* With only 2 months, "trend" means a single month-over-month change, not a sustained trend.
* Outlier statistics are computed on the *filtered* data, so selecting fewer districts changes the mean/IQR (by design).
* Z-score cannot exceed ≈ (n−1)/√n on tiny samples, so the default z = 3 may find nothing; use IQR or lower z.
