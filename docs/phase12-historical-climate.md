# Phase 12 — Historical Weather and Climate Intelligence

## What is available in this checkout

The existing historical endpoint and aggregation utilities were present, but its default provider pointed to the absent `data/processed/dhule_historical.csv`. The repository now contains `data/processed/imd_rainfall_daily_0.25deg.csv`: a validated single-cell daily rainfall extract at 21.00°N, 74.75°E, from 2013-01-01 through 2024-12-31 (4,383 dates). The accompanying validation reports show the annual IMD rainfall files passed structural/time-axis validation for 2013–2024. The separately present 2025 raw rainfall file is outside the validated normalized extract and is not used.

Raw IMD temperature GRD files are present, but their byte order and decoded values remain unverified. They are not treated as observations. There are no station observation series in the repository; `data/raw/dhule_station/` contains DSP reference PDFs only.

The actual climatology folder currently has 60 NetCDF files. Fresh metadata inspection finds all 12 months for rainfall at 0.25° and 1°, and Tmax, Tmin, and Tmean at 0.5°. IMD confirmed the baseline is 1991–2020, rainfall units are mm, and temperature units are °C. The catalog `data/imd_climatology_catalog.json` records file hashes, variables, month coverage, coordinate grids, and provenance metadata. The old catalog was stale and has been regenerated from the files.

## Architecture and interfaces

`LocalImdGridHistoricalProvider` reads only the normalized validated rainfall extract. It validates required fields, finite nonnegative rainfall, one coordinate, unique dates, and date continuity. It returns rainfall observations with temperature fields left null. It never decodes raw GRD files or fills gaps.

`HistoricalWeatherService` remains the provider-independent daily observation contract. The API adds deterministic daily/monthly/yearly summaries, observed extremes, year and date-range comparisons, descriptive trends, monthly climatology, and rainfall anomalies. Coordinates can be supplied as `lat`/`lon`; selection uses the installed point only and returns no data when the nearest cell exceeds 20 km. Named reference coordinates are configurable through `HISTORICAL_LOCATION_COORDINATES`. The current single-cell extract is centered at 21.00°N, 74.75°E; this does not imply coverage elsewhere.

Station series can be added later behind the same `HistoricalWeatherProvider`/`HistoricalDataset` interface with station provenance and coordinates. No station observations are required by the current provider.

## APIs

Backward-compatible daily history request:

`GET /api/v1/weather/history?city=Dhule&start_date=2024-07-01&end_date=2024-07-31`

Coordinate selection:

`GET /api/v1/weather/history?lat=20.9&lon=74.8&start_date=2024-07-01&end_date=2024-07-31`

Optional annual comparison uses `compare_year=2023` to compare that year with the following year. Optional date-range comparison accepts both `compare_start_date` and `compare_end_date`. Existing `records`, `summary`, `monthly`, and `yearly` fields remain; `analysis` adds coverage-aware trend, climatology, anomalies, extremes, and comparisons.

Direct normal lookup:

`GET /api/v1/weather/climatology?month=7&lat=20.9&lon=74.8`

The optional `variable` is `rainfall`, `tmax`, or `tmin`. Missing files, fill values, invalid months, or unsupported variables return explicit statuses/reasons rather than fabricated values.

## Aggregation and anomaly semantics

Daily records retain source, dataset, date, grid center, and native resolution. Monthly and annual rainfall totals sum only actual non-missing daily values. Mean temperature is never calculated from Tmax/Tmin. Monthly/yearly Tmax and Tmin summaries are null until validated daily temperature observations are installed.

For each observation month, rainfall normal is the IMD monthly rainfall climatology total at the matching 0.25° grid. The API labels observed values as `OBSERVATION`, normals as `CLIMATOLOGY`, and differences as `ANOMALY`. Rainfall anomaly is observed monthly total minus normal; percent anomaly is that difference divided by normal times 100. A zero normal yields a null percentage. No daily or annual temperature anomaly is reported because compatible validated temperature observations are unavailable.

The files contain monthly climatological surfaces. Rainfall and temperature normals are selected independently on their native grids (0.25° rainfall; 0.5° temperature). Values are not resampled to one shared grid. Tmean files are inventoried but are not used as observed or Tmax/Tmin values.

## Trend and data-quality limits

Rainfall trends use ordinary least-squares slopes over available annual rainfall totals and require at least eight distinct annual observations. Responses report slope in mm/year, start/end year, observation count, missing years, and the descriptive method. No significance test is performed and no climate claim or forecast is inferred from the slope. Tmax/Tmin trends are unavailable until values are validated.

Duplicate dates, date gaps, invalid/negative rainfall, inconsistent coordinates, missing values, and provenance are not silently repaired. Partial requested periods are marked partial. A period beyond the installed coverage returns no data/insufficient support. Extreme summaries list the largest observed daily values and wettest/driest observed monthly periods; they do not apply an invented hazard threshold.

## Chat and frontend

Historical and climatology questions route to the historical tool. The tool returns structured observations or normals and the agent phrases only those values. Missing records produce a clear unavailable response. Rainfall ML remains a separate prediction system; history means what was observed, climatology means the 1991–2020 normal, and IMD warnings remain official alerts with their separate source and semantics.

The existing Historical page now presents provenance, coverage, monthly normals, rainfall anomaly, and the descriptive rainfall trend, alongside observed rainfall. It labels the separate data types and reports temperature observation limitations. Coordinate fields use the existing generic grid selector.

## Missing inputs and external action

No required monthly climatology files are missing in the current checkout (all months are present for the five inventoried products). Daily Tmax/Tmin observations are still unavailable to analysis because the GRD byte order/value decoding has not been authoritatively validated. Authenticated IMD DSP station readings are also not installed. To add those, supply source files and authoritative format/quality documentation; no external authorization is needed for the currently local rainfall/climatology read paths.

## Limitations

- Historical observations currently cover one rainfall grid cell and 2013–2024 only.
- `Dhule` is the configured named reference location; arbitrary coordinates are supported only when close to that installed cell. Additional cities require usable data coverage and a coordinate mapping.
- Temperature observations, temperature anomalies, and temperature trends are unavailable. Climatological Tmax/Tmin normals are available.
- No missing rainfall observation is interpolated; missing values remain null and make the period partial.
- Trends are descriptive and are not forecasts, warnings, or significance-tested climate attribution.
