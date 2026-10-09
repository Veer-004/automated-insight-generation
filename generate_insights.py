"""
generate_insights.py - Command-line version of the engine (no UI).

Prints head(), info() and the missing-value report (Part A), then writes:
    outputs/insights.csv             (Section 4.1)
    outputs/sample_insights.json     (deliverable: sample insights JSON)
    outputs/correlation_matrix.csv   (Section 4.2)

Usage:
    python generate_insights.py                          # uses data/sample_data.csv
    python generate_insights.py data/extended_data.csv --threshold 15 --method Z-score
"""

import argparse
from pathlib import Path

import pandas as pd

import analytics as an

pd.set_option("display.width", 200)          # print full tables without "..."
pd.set_option("display.max_columns", 20)

parser = argparse.ArgumentParser(description="Auto-Analytics Engine (CLI)")
parser.add_argument("csv", nargs="?", default="data/sample_data.csv")
parser.add_argument("--threshold", type=float, default=10.0, help="trend threshold in %%")
parser.add_argument("--method", choices=["IQR", "Z-score"], default="IQR")
parser.add_argument("--iqr-k", type=float, default=1.5)
parser.add_argument("--z", type=float, default=3.0)
parser.add_argument("--corr", type=float, default=0.70, help="|r| threshold")
parser.add_argument("--target", type=float, default=80.0, help="coverage target %%")
args = parser.parse_args()

# ---- Part A: load + validate ---------------------------------------------
df = an.load_data(args.csv)
print("=== head() ===\n", df.head(), "\n")
print("=== info() ===")
df.info()
report = an.validate_data(df)
print("\n=== Missing values per column ===\n", report["missing"], "\n")
for w in report["warnings"]:
    print("WARNING:", w)

# ---- Parts B-E: run the engine ----------------------------------------------
indicators = an.get_indicators(df)
results = an.run_pipeline(df, indicators, args.threshold, args.method, args.iqr_k,
                          args.z, args.corr, args.target)
insights = results["insights"]

print(f"\n=== Flagged trends (|change| >= {args.threshold}%) ===")
trends = results["trends"]
print(trends[trends["is_significant"]][["district", "indicator", "month", "prev_value",
                                        "value", "pct_change", "severity"]].to_string(index=False))
print(f"\n=== Outliers ({args.method}) ===")
print(results["outliers"][["district", "indicator", "month", "value", "severity"]].to_string(index=False))
print("\n=== Correlation matrix ===\n", results["corr"])
print(f"\n=== {len(insights)} insights ===")
for row in insights.itertuples():
    print(f"{row.insight_id} [{row.severity:6}] {row.type:16} {row.explanation}")

# ---- Save outputs -----------------------------------------------------------
out = Path("outputs")
out.mkdir(exist_ok=True)
insights.to_csv(out / "insights.csv", index=False)
insights.to_json(out / "sample_insights.json", orient="records", indent=2)
results["corr"].to_csv(out / "correlation_matrix.csv")
print(f"\nSaved insights.csv, sample_insights.json and correlation_matrix.csv to {out.resolve()}")
