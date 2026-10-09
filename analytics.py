"""
analytics.py - The Auto-Analytics Engine (pure Python, no UI code).

Pipeline:
    load_data()  ->  validate_data()
                 ->  detect_trends()             (Part B)
                 ->  detect_outliers()           (Part C)
                 ->  compute_correlation()       (Part D)
                 ->  flag_correlations()
                 ->  detect_threshold_breaches()
                 ->  generate_insights()         (Part E)

Nothing here is specific to any district or month: every number in every
insight is calculated from whatever CSV is loaded.
"""

import io

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
ID_COLUMNS = ["month", "district"]

# Indicators where a HIGHER value is BAD (raw counts of risk).
# Every other numeric column is treated as a "% coverage" where higher = better.
LOWER_IS_BETTER = ["high_risk_cases"]

# Severity tiers. A finding's "ratio" says how many times it exceeds the
# user-configured threshold (e.g. a 18.8% drop with a 10% threshold -> 1.88).
HIGH_MULTIPLIER = 1.5     # ratio >= 1.5  -> High
MEDIUM_MULTIPLIER = 1.25  # ratio >= 1.25 -> Medium, otherwise Low

SEVERITY_ORDER = ["High", "Medium", "Low"]
TYPE_ORDER = ["trend", "outlier", "correlation", "threshold_breach"]
INSIGHT_COLUMNS = ["insight_id", "type", "indicator", "entity", "period", "value",
                   "prev_value", "change_pct", "severity", "explanation"]


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def pretty_name(indicator, capitalize=True):
    """'anc_coverage' -> 'ANC coverage' (short words such as 'anc' become acronyms)."""
    words = [w.upper() if len(w) <= 3 else w for w in indicator.split("_")]
    text = " ".join(words)
    return text[0].upper() + text[1:] if capitalize else text


def fmt_value(indicator, value):
    """Add a % sign for coverage indicators, none for raw counts."""
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return text if indicator in LOWER_IS_BETTER else f"{text}%"


def is_bad_change(indicator, change):
    """True if a change (positive = increase) is a deterioration for this indicator."""
    return change > 0 if indicator in LOWER_IS_BETTER else change < 0


def severity_from_ratio(ratio):
    """Map 'how many times the threshold was exceeded' to Low / Medium / High."""
    if ratio >= HIGH_MULTIPLIER:
        return "High"
    if ratio >= MEDIUM_MULTIPLIER:
        return "Medium"
    return "Low"


def get_indicators(df):
    """All numeric columns except the ID columns are indicators."""
    return [c for c in df.select_dtypes(include="number").columns if c not in ID_COLUMNS]


def to_long(df, indicators):
    """Wide table -> long table with one row per (district, month, indicator)."""
    long = df.melt(id_vars=ID_COLUMNS, value_vars=indicators,
                   var_name="indicator", value_name="value")
    return long.dropna(subset=["value"])


# --------------------------------------------------------------------------
# Part A - Loading & validation
# --------------------------------------------------------------------------
def load_data(source):
    """Read a CSV (path or uploaded file) and clean it into a tidy DataFrame."""
    df = pd.read_csv(source, skipinitialspace=True)      # sample CSV has ", " separators
    df.columns = df.columns.str.strip().str.lower()

    missing = [c for c in ID_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing required column(s): {missing}")

    df["district"] = df["district"].astype(str).str.strip()
    # Accept "2026-07" or "2026-07-01" and normalise both to "2026-07"
    df["month"] = pd.to_datetime(df["month"].astype(str).str.strip(),
                                 format="mixed").dt.strftime("%Y-%m")

    # Every other column should be numeric; bad values become NaN (reported as missing)
    for col in df.columns.difference(ID_COLUMNS):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.sort_values(["district", "month"]).reset_index(drop=True)


def get_info_text(df):
    """Capture df.info() output as a string (it normally prints to stdout)."""
    buffer = io.StringIO()
    df.info(buf=buffer)
    return buffer.getvalue()


def validate_data(df):
    """Run data-quality checks and return a report dictionary."""
    indicators = get_indicators(df)
    months_per_district = df.groupby("district")["month"].nunique()
    duplicates = int(df.duplicated(subset=ID_COLUMNS).sum())

    warnings = []
    if duplicates:
        warnings.append(f"{duplicates} duplicate (district, month) rows found.")
    if months_per_district.min() < 3:
        warnings.append(f"Some districts have fewer than 3 months of data "
                        f"(min = {months_per_district.min()}); trends are month-over-month only.")
    if df["district"].nunique() < 10:
        warnings.append(f"Only {df['district'].nunique()} districts (< 10 recommended); "
                        f"correlations will be unstable.")
    if not indicators:
        warnings.append("No numeric indicator columns found.")

    return {
        "rows": len(df),
        "districts": df["district"].nunique(),
        "months": df["month"].nunique(),
        "indicators": indicators,
        "missing": df.isna().sum().rename("missing_values").to_frame(),
        "duplicates": duplicates,
        "warnings": warnings,
    }


# --------------------------------------------------------------------------
# Part B - Trend detection
# --------------------------------------------------------------------------
def detect_trends(df, indicators, threshold):
    """
    Month-over-month % change for every (district, indicator) pair.
    pct_change = (current - previous) / previous * 100
    is_significant = |pct_change| >= threshold
    """
    long = to_long(df, indicators).sort_values(["district", "indicator", "month"])
    groups = long.groupby(["district", "indicator"])
    long["prev_value"] = groups["value"].shift(1)
    long["prev_month"] = groups["month"].shift(1)

    trends = long.dropna(subset=["prev_value"])
    trends = trends[trends["prev_value"] != 0].copy()          # avoid division by zero
    if trends.empty:
        return trends.assign(pct_change=[], is_significant=[], is_deterioration=[], severity=[])

    trends["pct_change"] = (trends["value"] - trends["prev_value"]) / trends["prev_value"] * 100
    trends["is_significant"] = trends["pct_change"].abs() >= threshold
    trends["is_deterioration"] = [is_bad_change(i, c) for i, c in
                                  zip(trends["indicator"], trends["pct_change"])]

    # Severity: improvements are always Low; deteriorations scale with |change| / threshold
    trends["severity"] = [
        severity_from_ratio(abs(c) / threshold) if bad else "Low"
        for c, bad in zip(trends["pct_change"], trends["is_deterioration"])
    ]
    trends["pct_change"] = trends["pct_change"].round(1)
    return trends.reset_index(drop=True)


# --------------------------------------------------------------------------
# Part C - Outlier detection
# --------------------------------------------------------------------------
def detect_outliers(df, indicators, method="IQR", iqr_k=1.5, z_threshold=3.0):
    """
    Flag unusual values for each indicator (compared with all rows of that indicator).
      IQR:     outlier if value > Q3 + k*IQR  or  value < Q1 - k*IQR
      Z-score: outlier if |value - mean| / std >= z_threshold
    'score' = how far past the rule the value is (1.0 = exactly on the boundary).
    """
    results = []
    for indicator, grp in to_long(df, indicators).groupby("indicator"):
        values = grp["value"]
        mean, std = values.mean(), values.std()
        if len(values) < 3 or not std > 0:                     # not enough spread to judge
            continue
        z = (values - mean) / std

        if method == "IQR":
            q1, q3 = values.quantile(0.25), values.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue
            lower, upper = q1 - iqr_k * iqr, q3 + iqr_k * iqr
            is_outlier = (values < lower) | (values > upper)
            # distance beyond the nearest quartile, measured in units of k*IQR
            distance = np.where(values < q1, q1 - values, np.where(values > q3, values - q3, 0))
            score = distance / (iqr_k * iqr)
        else:
            lower, upper = mean - z_threshold * std, mean + z_threshold * std
            is_outlier = z.abs() >= z_threshold
            score = z.abs() / z_threshold

        found = grp[is_outlier].copy()
        found["mean"] = mean
        found["z_score"] = z[is_outlier]
        found["lower_bound"] = lower
        found["upper_bound"] = upper
        found["score"] = np.asarray(score)[is_outlier.to_numpy()]
        results.append(found)

    if not results:
        return pd.DataFrame(columns=["district", "month", "indicator", "value", "mean",
                                     "z_score", "lower_bound", "upper_bound", "score",
                                     "deviation_pct", "severity"])

    out = pd.concat(results, ignore_index=True)
    out["deviation_pct"] = (out["value"] - out["mean"]) / out["mean"] * 100
    # Outliers in the "good" direction (e.g. very high coverage) are Low severity
    out["severity"] = [
        severity_from_ratio(s) if is_bad_change(i, d) else "Low"
        for s, i, d in zip(out["score"], out["indicator"], out["deviation_pct"])
    ]
    return out.round({"mean": 1, "z_score": 2, "lower_bound": 2, "upper_bound": 2,
                      "score": 2, "deviation_pct": 1})


# --------------------------------------------------------------------------
# Part D - Correlation detection
# --------------------------------------------------------------------------
def compute_correlation(df, indicators):
    """Standard Pearson correlation matrix across indicators (pandas .corr())."""
    return df[indicators].corr(method="pearson").round(3)


def top_contributor(df, a, b, r):
    """
    Which district pushes the correlation hardest? Pearson r is the average of
    z_a * z_b, so the district with the largest product (same sign as r) drives it.
    """
    z_a = (df[a] - df[a].mean()) / df[a].std()
    z_b = (df[b] - df[b].mean()) / df[b].std()
    contribution = (z_a * z_b * np.sign(r)).groupby(df["district"]).sum()
    return contribution.idxmax() if not contribution.empty else "n/a"


def flag_correlations(df, corr, threshold):
    """List indicator pairs with |r| >= threshold (upper triangle only, no duplicates)."""
    pairs = []
    cols = list(corr.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = corr.iloc[i, j]
            if pd.isna(r) or abs(r) < threshold:
                continue
            # Severity: how far |r| sits between the threshold and a perfect 1.0
            position = (abs(r) - threshold) / (1 - threshold) if threshold < 1 else 1
            severity = "High" if position >= 2 / 3 else "Medium" if position >= 1 / 3 else "Low"
            pairs.append({
                "indicator_1": cols[i], "indicator_2": cols[j], "r": round(r, 3),
                "direction": "positive" if r > 0 else "negative",
                "top_contributor": top_contributor(df, cols[i], cols[j], r),
                "severity": severity,
            })
    return pd.DataFrame(pairs, columns=["indicator_1", "indicator_2", "r", "direction",
                                        "top_contributor", "severity"])


# --------------------------------------------------------------------------
# Threshold breaches (coverage below a target)
# --------------------------------------------------------------------------
def detect_threshold_breaches(df, indicators, target, gap_threshold):
    """
    For coverage indicators, flag each district's LATEST value below the target.
    gap_pct = (target - value) / target * 100; severity = gap_pct / gap_threshold.
    """
    coverage = [i for i in indicators if i not in LOWER_IS_BETTER]
    latest = to_long(df, coverage).sort_values("month").groupby(["district", "indicator"]).tail(1)
    breaches = latest[latest["value"] < target].copy()
    breaches["target"] = target
    breaches["gap_pct"] = ((target - breaches["value"]) / target * 100).round(1)
    breaches["severity"] = [severity_from_ratio(g / gap_threshold) for g in breaches["gap_pct"]]
    return breaches.reset_index(drop=True)


# --------------------------------------------------------------------------
# Part E - Automated insight generation
# --------------------------------------------------------------------------
def generate_insights(df, trends, outliers, corr_pairs, breaches, trend_threshold,
                      outlier_method, z_threshold=3.0):
    """Turn every finding into a structured insight row with an auto-written sentence."""
    rows = []

    # 1) Significant trends
    for t in trends[trends["is_significant"]].itertuples() if not trends.empty else []:
        verb = "rose" if t.pct_change > 0 else "dropped"
        effect = "a deterioration" if t.is_deterioration else "an improvement"
        rows.append({
            "type": "trend", "indicator": t.indicator, "entity": t.district, "period": t.month,
            "value": t.value, "prev_value": t.prev_value, "change_pct": t.pct_change,
            "severity": t.severity,
            "explanation": (f"{pretty_name(t.indicator)} in {t.district} {verb} by "
                            f"{abs(t.pct_change):.1f}% compared to the previous month "
                            f"({fmt_value(t.indicator, t.prev_value)} in {t.prev_month} -> "
                            f"{fmt_value(t.indicator, t.value)} in {t.month}), exceeding the "
                            f"{trend_threshold:g}% significant-change threshold. This is {effect}."),
        })

    # 2) Outliers
    for o in outliers.itertuples():
        side = "above" if o.value > o.mean else "below"
        rule = (f"outside the IQR range [{o.lower_bound:g}, {o.upper_bound:g}]"
                if outlier_method == "IQR" else f"beyond the |z| >= {z_threshold:g} limit")
        rows.append({
            "type": "outlier", "indicator": o.indicator, "entity": o.district, "period": o.month,
            "value": o.value, "prev_value": o.mean, "change_pct": o.deviation_pct,
            "severity": o.severity,
            "explanation": (f"{o.district}'s {pretty_name(o.indicator, False)} of "
                            f"{fmt_value(o.indicator, o.value)} in {o.month} is "
                            f"{abs(o.z_score):.2f} standard deviations {side} the mean "
                            f"({fmt_value(o.indicator, o.mean)}), {rule}; flagging for review."),
        })

    # 3) Correlations
    period = f"{df['month'].min()}..{df['month'].max()}"
    for c in corr_pairs.itertuples():
        follow = "rise" if c.direction == "positive" else "fall"
        rows.append({
            "type": "correlation", "indicator": f"{c.indicator_1}:{c.indicator_2}",
            "entity": "All districts", "period": period, "value": c.r,
            "prev_value": None, "change_pct": None, "severity": c.severity,
            "explanation": (f"{pretty_name(c.indicator_1)} and {pretty_name(c.indicator_2, False)} "
                            f"show a {c.direction} correlation (r = {c.r:.2f}, n = {len(df)} rows): "
                            f"when one rises the other tends to {follow}. "
                            f"Largest contributor: {c.top_contributor}. "
                            f"Small sample - treat as a lead, not proof."),
        })

    # 4) Threshold breaches
    for b in breaches.itertuples():
        rows.append({
            "type": "threshold_breach", "indicator": b.indicator, "entity": b.district,
            "period": b.month, "value": b.value, "prev_value": b.target,
            "change_pct": -b.gap_pct, "severity": b.severity,
            "explanation": (f"{pretty_name(b.indicator)} in {b.district} is "
                            f"{fmt_value(b.indicator, b.value)} in {b.month}, "
                            f"{b.target - b.value:g} percentage points ({b.gap_pct:.1f}%) below the "
                            f"{b.target:g}% target."),
        })

    insights = pd.DataFrame(rows, columns=INSIGHT_COLUMNS[1:])
    if insights.empty:
        return pd.DataFrame(columns=INSIGHT_COLUMNS)

    # Most important first: High -> Low, then by insight type, then biggest change
    insights["_sev"] = insights["severity"].map(SEVERITY_ORDER.index)
    insights["_type"] = insights["type"].map(TYPE_ORDER.index)
    insights["_abs"] = pd.to_numeric(insights["change_pct"], errors="coerce").abs()
    insights = insights.sort_values(["_sev", "_type", "_abs"], ascending=[True, True, False])
    insights = insights.drop(columns=["_sev", "_type", "_abs"]).reset_index(drop=True)

    insights.insert(0, "insight_id", [f"INS-{i:04d}" for i in range(1, len(insights) + 1)])
    return insights


def run_pipeline(df, indicators, trend_threshold=10.0, outlier_method="IQR", iqr_k=1.5,
                 z_threshold=3.0, corr_threshold=0.70, coverage_target=80.0):
    """Run every analysis step once and return all results in a dictionary."""
    trends = detect_trends(df, indicators, trend_threshold)
    outliers = detect_outliers(df, indicators, outlier_method, iqr_k, z_threshold)
    corr = compute_correlation(df, indicators) if len(indicators) >= 2 else pd.DataFrame()
    corr_pairs = flag_correlations(df, corr, corr_threshold) if len(df) >= 3 and not corr.empty \
        else flag_correlations(df, pd.DataFrame(), corr_threshold)
    breaches = detect_threshold_breaches(df, indicators, coverage_target, trend_threshold)
    insights = generate_insights(df, trends, outliers, corr_pairs, breaches,
                                 trend_threshold, outlier_method, z_threshold)
    return {"trends": trends, "outliers": outliers, "corr": corr,
            "corr_pairs": corr_pairs, "breaches": breaches, "insights": insights}
