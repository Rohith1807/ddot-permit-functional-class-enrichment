# Public Space Occupancy Permit — FHWA Functional Class Enrichment

## 1. Project Overview

This project enriches calendar year 2026 District of Columbia Public Space Occupancy Permit records with Federal Highway Administration (FHWA) roadway functional classifications.

The objective is to support the Public Space Division in determining roadway classifications that influence permitted work hours.

The solution produces a location-level CSV containing:

- Individual permit application locations and their associated roadway functional classes.
- The highest functional class across all locations associated with each permit application.
- Roadway matching and data quality indicators for transparency.

The pipeline was developed through iterative data exploration, validation, and refinement, then consolidated into a reproducible Python workflow.

## 2. Data Sources

The solution uses publicly available DC GIS REST services.

| Source | Purpose |
|---|---|
| [DDOT Occupancy Permit API](https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_APPS/DDOT_TOPS/MapServer/24) | Retrieve permit applications and location information |
| [DDOT Roadway SubBlock API](https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Transportation_WebMercator/MapServer/162) | Retrieve roadway geometry and FHWA functional classifications |

### Filtering Criteria

Permit records are filtered using:

- **Date:** Application or issue date within calendar year 2026.
- **Permit types:** Construction Staging Area and Mobile Crane Work Zone.
- **Utilities:** DC Water, PEPCO, and Washington Gas.

Utility names are standardized using verified `ApplicantCompany` values, including `DCWater/CIP`, `DCWater/OPS`, `Potomac Electric Power Company`, and `Wash Gas & Light Co.`.

Both required permit types are considered. No Mobile Crane Work Zone records matched the selected utility applicant names in the analyzed dataset.

## 3. Methodology

The pipeline follows four primary stages.

**1. Extraction and Filtering**

Retrieve permit records from the ArcGIS REST API, apply the required filters, and preserve individual locations using `TrackingNumber`, `LocationID`, and `OBJECTID`.

**2. Roadway Enrichment**

Query nearby roadway segments using permit coordinates and match candidate roadways through street-name normalization and geometry-based distance evaluation.

- Exclude alleys and roadways without valid FHWA classifications.
- Normalize common roadway abbreviations and supported naming differences.
- Evaluate nearby roadway candidates and conflicting classifications.
- Preserve unresolved and ambiguous results rather than assigning unsupported values.

**3. Permit-Level Aggregation**

Calculate the highest functional class across locations sharing a `TrackingNumber`.

FHWA classes range from 1 (Interstate) to 7 (Local Road). Because lower numeric values indicate higher roadway functional hierarchy, the minimum valid class represents the highest functional class.

For permits with unresolved locations, the final highest class remains blank to avoid reporting an incomplete result as definitive.

**4. Data Quality Validation**

Validate record preservation, location uniqueness, functional class values, permit-level aggregation, and classification statuses.

## 4. Running the Pipeline

### Prerequisites

- Python 3.10 or later
- Internet connectivity for live API execution
- Dependencies listed in `requirements.txt`

From the project root directory:

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

```bash
python -m pip install -r requirements.txt
```

### Live API Execution — Default

```bash
python run_pipeline.py
```

This retrieves current permit data, performs roadway enrichment, calculates permit-level functional classifications, exports the results, and executes quality checks.

**Output:**

`data/processed/live/2026_utility_permits_enriched.csv`

### Snapshot Reproduction — Optional

```bash
python run_pipeline.py --mode snapshot
```

This reproduces the archived analysis using saved permit and roadway data without making new API requests.

**Output:**

`data/processed/snapshot/2026_utility_permits_enriched.csv`

Snapshot mode is provided for reproducibility. Live mode is the primary executable workflow.

## 5. Final Results

The successful live API execution produced the following results:

| Metric | Result |
|---|---:|
| Permit application locations | 4,983 |
| Unique permit applications | 3,129 |
| Locations assigned a functional class | 4,934 |
| Classification coverage | 99.02% |
| Unresolved locations | 49 |
| Complete permit applications | 3,006 |
| Provisional permit applications | 74 |
| Incomplete permit applications | 49 |

### Roadway Match Quality

| Classification status | Locations |
|---|---:|
| Direct roadway matches | 4,798 |
| Normalized roadway-name matches | 62 |
| Provisional extended-radius matches | 74 |
| Street-name review required | 12 |
| Ambiguous matches | 18 |
| Distant matches requiring review | 17 |
| Unmatched locations | 2 |

All 4,983 permit locations were preserved, with no duplicate permit-location combinations.

**All automated data integrity and aggregation quality checks passed.**

## 6. Final CSV Structure

The primary deliverable is:

`data/processed/live/2026_utility_permits_enriched.csv`

Each row represents one permit application location.

| Column | Description |
|---|---|
| `TrackingNumber` | Permit application identifier |
| `PermitNumber` | Issued permit identifier |
| `LocationID` | Individual permit location identifier |
| `Utility` | Standardized utility company |
| `EventTypeDescription` | Permit type |
| `ApplicationDate` / `IssueDate` | Permit application and issuance dates |
| `WorkLocationFullAddress` | Permit work location |
| `Longitude` / `Latitude` | Geographic coordinates |
| `RoadName` | Matched roadway |
| `SubBlockKey` | Roadway segment identifier |
| `FunctionalClass` | FHWA class at the individual location |
| `HighestFunctionalClass` | Highest functional class for the application |
| `PermitClassStatus` | COMPLETE, PROVISIONAL, or INCOMPLETE |
| `MatchStatus` | Roadway matching status |

Additional fields preserve the matching method, candidate classification, and quality information for auditing.

## 7. Limitations and Assumptions

**Utility identification:** The utility filter uses verified applicant-company names. Applications submitted by third-party permitting services without an identifiable target utility may not be included.

**Geospatial matching:** Roadway centerline proximity and street-name agreement provide evidence of a match but do not independently guarantee that every selected roadway is correct.

**Provisional classifications:** The 74 extended-radius matches have assigned classifications but require additional independent verification.

**Unresolved locations:** The 49 remaining locations retain blank functional classes. Applications containing unresolved locations are marked `INCOMPLETE`, and their final highest functional class is left blank.

**Source updates:** Live API data can change. Consequently, rerunning the pipeline may produce different counts or roadway classifications from those included in the submitted CSV.

## 8. Deliverables

The submission ZIP includes:

- Python scripts implementing extraction, filtering, enrichment, export, and validation.
- `run_pipeline.py` as the main execution entry point.
- `requirements.txt` containing required dependencies.
- The final enriched CSV and supporting permit-level quality summary.
- Archived input and roadway data supporting snapshot reproduction.
- This README with execution guidance and documented assumptions.

## 9. Conclusion

The solution provides a reproducible workflow for enriching DC Public Space Occupancy Permits with FHWA functional classifications at both the individual location and permit application levels.

The live execution classified **99.02% of permit locations**, preserved all qualifying location records, and passed automated quality checks. Remaining uncertainties are explicitly retained through classification and review statuses rather than hidden through unsupported assignments.