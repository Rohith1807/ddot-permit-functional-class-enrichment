
"""
Purpose:
Join enriched roadway classifications to individual permit
locations and calculate the highest FHWA functional class
per permit application.

Preserve unresolved locations and clearly identify permits
whose highest classification cannot yet be verified.
"""

from pathlib import Path
import pandas as pd
import argparse

DATA_DIR = Path(__file__).resolve().parents[1] / "data/processed"

PERMITS = DATA_DIR / "2026_utility_permits.csv"
MATCHES = DATA_DIR / "roadway_matches_current.csv"

parser = argparse.ArgumentParser()
parser.add_argument("--mode", choices=["live", "snapshot"], required=True)
args = parser.parse_args()

OUTPUT_DIR = DATA_DIR / args.mode
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT = OUTPUT_DIR / "2026_utility_permits_enriched.csv"
SUMMARY = OUTPUT_DIR / "permit_quality_summary.csv"

permits = pd.read_csv(PERMITS)
matches = pd.read_csv(MATCHES)

assert permits["OBJECTID"].is_unique
assert matches["OBJECTID"].is_unique
assert len(permits) == len(matches)
assert set(permits["OBJECTID"]) == set(matches["OBJECTID"])

# Keep a clean set of enrichment fields.
enrichment_fields = [
    "OBJECTID",
    "RoadName",
    "SubBlockKey",
    "FunctionalClass",
    "ProposedFunctionalClass",
    "DistanceMeters",
    "MatchStatus",
    "ResolutionMethod",
]

enrichment = matches.reindex(columns=enrichment_fields)

df = permits.merge(
    enrichment,
    on="OBJECTID",
    how="left",
    validate="one_to_one",
    indicator=True
)

assert df["_merge"].eq("both").all()
df = df.drop(columns="_merge")

df["FunctionalClass"] = pd.to_numeric(
    df["FunctionalClass"], errors="coerce"
)

assert df["FunctionalClass"].dropna().isin(
    range(1, 8)
).all()

# Determine completeness at the permit application level.
permit_summary = (
    df.groupby("TrackingNumber", dropna=False)
    .agg(
        TotalLocations=("OBJECTID", "size"),
        ClassifiedLocations=("FunctionalClass", "count"),
        HighestObservedClass=("FunctionalClass", "min"),
        HasProvisionalMatch=(
            "MatchStatus",
            lambda statuses: statuses.eq(
                "MATCHED_EXTENDED_PROVISIONAL"
            ).any()
        )
    )
    .reset_index()
)

permit_summary["UnresolvedLocations"] = (
    permit_summary["TotalLocations"]
    - permit_summary["ClassifiedLocations"]
)

permit_summary["PermitClassStatus"] = "INCOMPLETE"

permit_summary.loc[
    permit_summary["UnresolvedLocations"].eq(0),
    "PermitClassStatus"
] = "COMPLETE"

permit_summary.loc[
    permit_summary["UnresolvedLocations"].eq(0)
    & permit_summary["HasProvisionalMatch"],
    "PermitClassStatus"
] = "PROVISIONAL"

# Only fully classified permits receive a final highest class.
# Provisional permits retain a calculated result with a clear flag.
permit_summary["HighestFunctionalClass"] = (
    permit_summary["HighestObservedClass"].where(
        permit_summary["UnresolvedLocations"].eq(0)
    )
)

df = df.merge(
    permit_summary,
    on="TrackingNumber",
    how="left",
    validate="many_to_one"
)

# Use nullable integer values rather than floating-point labels.
for column in [
    "FunctionalClass",
    "ProposedFunctionalClass",
    "HighestObservedClass",
    "HighestFunctionalClass"
]:
    df[column] = pd.to_numeric(
        df[column], errors="coerce"
    ).astype("Int64")

# Sort so all locations associated with a permit appear together.
df = df.sort_values(
    ["Utility", "TrackingNumber", "LocationID"]
)

# Preserve useful business and audit fields.
output_columns = [
    "TrackingNumber",
    "PermitNumber",
    "LocationID",
    "OBJECTID",
    "Utility",
    "ApplicantCompany",
    "EventTypeDescription",
    "StatusDescription",
    "ApplicationDate",
    "IssueDate",
    "WorkLocationFullAddress",
    "Longitude",
    "Latitude",
    "RoadName",
    "SubBlockKey",
    "FunctionalClass",
    "HighestFunctionalClass",
    "HighestObservedClass",
    "TotalLocations",
    "ClassifiedLocations",
    "UnresolvedLocations",
    "PermitClassStatus",
    "MatchStatus",
    "ResolutionMethod",
    "DistanceMeters",
    "ProposedFunctionalClass"
]

df = df.reindex(columns=output_columns)

df.to_csv(OUTPUT, index=False)
permit_summary.to_csv(SUMMARY, index=False)

# Final quality checks.
assert len(df) == len(permits)
assert df["OBJECTID"].is_unique
assert not df.duplicated(
    ["TrackingNumber", "LocationID"]
).any()

assert df["TrackingNumber"].nunique() == permits["TrackingNumber"].nunique()
assert df["FunctionalClass"].notna().sum() + df["FunctionalClass"].isna().sum() == len(df)

# Highest class must be shared by every location of a permit.
assert (
    df.groupby("TrackingNumber")["HighestFunctionalClass"]
    .nunique(dropna=False)
    .le(1)
    .all()
)

# No incomplete permit should have a final highest class.
assert df.loc[
    df["PermitClassStatus"].eq("INCOMPLETE"),
    "HighestFunctionalClass"
].isna().all()

print("\n=== FINAL DATASET ===")
print("Location rows:", len(df))
print("Unique permit applications:", df["TrackingNumber"].nunique())
print("Classified locations:", df["FunctionalClass"].notna().sum())
print("Unresolved locations:", df["FunctionalClass"].isna().sum())

print("\n=== PERMIT CLASSIFICATION STATUS ===")
print(
    permit_summary["PermitClassStatus"]
    .value_counts()
    .to_string()
)

print("\n=== HIGHEST FUNCTIONAL CLASS DISTRIBUTION ===")
print(
    permit_summary["HighestFunctionalClass"]
    .value_counts(dropna=False)
    .sort_index()
    .to_string()
)

print("\n=== LOCATION CONSERVATION ===")
print("Input locations:", len(permits))
print("Output locations:", len(df))
print("Rows lost:", len(permits) - len(df))

print("\nSaved:", OUTPUT)
print("Permit summary:", SUMMARY)
