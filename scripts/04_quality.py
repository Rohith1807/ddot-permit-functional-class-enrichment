
"""
Purpose:
Independently validate the ready CSV for completeness,
uniqueness, functional-class aggregation, and status consistency.
"""

from pathlib import Path
import argparse
import pandas as pd

parser = argparse.ArgumentParser()
parser.add_argument("--mode", choices=["live", "snapshot"], required=True)
args = parser.parse_args()

FILE = (Path(__file__).resolve().parents[1] / "data" / "processed"
        / args.mode / "2026_utility_permits_enriched.csv")
df = pd.read_csv(FILE)

print("\n=== 1. LOCATION INTEGRITY ===")

assert len(df) > 0
assert df["OBJECTID"].notna().all() and df["OBJECTID"].is_unique
assert df["LocationID"].notna().all()
assert not df.duplicated(["TrackingNumber", "LocationID"]).any()
assert df["TrackingNumber"].notna().all()

print(f"All {len(df):,} output locations have unique identifiers.")
print(f"Found {df.TrackingNumber.nunique():,} permit applications.")
print("No duplicate permit-location combinations.")

print("\n=== 2. FUNCTIONAL CLASS VALIDITY ===")

for col in ["FunctionalClass", "HighestFunctionalClass"]:
    assert df[col].dropna().isin(range(1, 8)).all()

print("All populated FHWA classes are within 1–7.")

print("\n=== 3. PERMIT-LEVEL AGGREGATION ===")

errors = []

for permit_id, group in df.groupby("TrackingNumber"):
    observed = group["FunctionalClass"].dropna()
    highest = group["HighestFunctionalClass"].dropna()

    if observed.empty:
        expected = None
    else:
        expected = int(observed.min())

    status = group["PermitClassStatus"].iloc[0]

    if group["PermitClassStatus"].nunique() != 1:
        errors.append((permit_id, "Inconsistent permit status"))
        continue

    if status == "INCOMPLETE":
        if not highest.empty:
            errors.append((permit_id, "Incomplete with final class"))
        if group["FunctionalClass"].notna().all():
            errors.append((permit_id, "Incorrect incomplete status"))
    else:
        if group["FunctionalClass"].isna().any():
            errors.append((permit_id, "Missing location class"))
        if highest.nunique() != 1:
            errors.append((permit_id, "Inconsistent highest class"))
        elif expected is None or int(highest.iloc[0]) != expected:
            errors.append((permit_id, "Incorrect highest class"))

        has_provisional = group["MatchStatus"].eq(
            "MATCHED_EXTENDED_PROVISIONAL"
        ).any()

        expected_status = (
            "PROVISIONAL" if has_provisional else "COMPLETE"
        )

        if status != expected_status:
            errors.append((permit_id, "Incorrect permit status"))

assert not errors, f"Aggregation errors: {errors[:10]}"

print("Highest functional class calculated correctly.")
print("Permit classification statuses are consistent.")

print("\n=== 4. DATA QUALITY SUMMARY ===")

print("\nLocation match status:")
print(df["MatchStatus"].value_counts().to_string())

print("\nPermit classification status:")
print(
    df.groupby("TrackingNumber")["PermitClassStatus"]
    .first()
    .value_counts()
    .to_string()
)

print("\n=== 5. FINAL VERDICT ===")
print("ALL PROGRAMMATIC QUALITY CHECKS PASSED")
print("Manual review and documented limitations still apply.")
