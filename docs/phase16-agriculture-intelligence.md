# Phase 16 — Agriculture Weather Intelligence

## Architecture

`POST /api/v1/agriculture/advice` resolves a city through the existing Phase 13 `LocationService`, validates direct coordinates using the existing coordinate model, or accepts a configured station ID. It then reads available weather inputs from the existing current-weather, operational forecast, GFS/NWP, historical, climatology, and IMD alert services. The deterministic `AgricultureDecisionEngine` evaluates the requested activity and returns a structured recommendation, evidence, source list, confidence/availability, and limitations. The chat agent invokes this same service; the LLM may phrase its returned facts but does not calculate measurements or decision conditions.

Observed current weather, operational forecast, GFS model output, local station observations, historical grid observations, climatology, IMD official warnings, and WeatherGPT agriculture advice retain separate source labels. An agriculture condition is not an IMD warning or an agricultural-department instruction.

## IMD DSP station data

The reusable station catalog is `data/stations/imd_dsp_stations.json`. It contains the supplied metadata for Nashik station **42921** (Nashik district, Maharashtra; 20°02′N, 73°47′E represented at the supplied minute precision; elevation 598.76 m), and references source CSVs by relative path. The parser is generic over catalog station entries and table configuration; the station identity is not embedded in analytical rules.

The raw CSVs and supplied format PDFs are read only. The raw files currently reside under the ignored local path `data/raw/dhule_station/` despite containing station 42921 data. The service never writes normalized rows back to those files. There is no live DSP download/session: results are from the **validated local IMD DSP station dataset**. Deployments need the configured raw files present at the catalog paths if station parsing is required.

### Actual quality report for local files

| Dataset | Rows | Coverage | Duplicate keys | Missing calendar/3-hour slots | Missing values | Invalid values |
|---|---:|---|---:|---:|---|---|
| Surface Table-II / day summary | 6,212 | 2007-01-05 to 2025-12-31 | 0 | 724 dates | MAX 9, MIN 17, RF 16 | 0 in validated numeric fields |
| Surface Table-III / synoptic hour | 52,011 | 2000-06-09 12:00 UTC to 2025-12-31 21:00 UTC | 0 | 22,681 expected 3-hour slots | SLP 4,633; MSLP 15; DBT 2; WBT 6,110; DPT 7; RH 4; VP 6,112; DD 7; FFF 4; AW 42,180; RF 201 | 2 unmapped DD codes |

Coverage gaps are reported, not filled. Table-II MAX/MIN are daily maximum/minimum °C; RF is the 24-hour total in mm ending 08:30 IST. Its normalized timestamp is the corresponding 03:00 UTC time. Table-III DBT/WBT/DPT are °C; RH is percent; SLP/MSLP are retained in hPa as represented by these source rows; FFF is km/h; RF is mm since the previous observation. The parser retains the other supplied fields in its raw-row/quality accounting without using them as agricultural evidence.

Table-III's hour-code convention is decoded using the supplied format: `00,12,24,36,48,60,72,84` map to `00,03,06,09,12,15,18,21 UTC`. Actual HHMM values such as `0300` and `1200` are parsed as UTC clock values. Persisted normalized timestamps are timezone-aware UTC, which avoids inventing a local date at midnight rollover. Unknown direction codes are flagged and not guessed. Empty cells become `null`; other unrecognized/malformed tokens remain quality errors. Duplicate records are retained and flagged by the parser/report rather than silently deduplicated.

`GET /api/v1/agriculture/stations/{station_id}/quality` returns station metadata, per-table row counts, date coverage, gaps, parameter null/invalid counts, duplicate counts, units/missing-value interpretation, and timestamp convention.

## Normalized observation contract

`StationObservation` includes station ID/name, district/state, coordinates, elevation, UTC observation time, source, dataset, optional measurements (temperature and min/max, wet bulb/dew point, RH, pressure, wind speed/direction, rainfall), quality flags, and invalid source values. Missing measurements remain null; no imputation or unit conversion is implicit. Where a derived conversion is used for evidence (provider wind m/s to km/h), the evidence states that conversion.

## Agriculture activities and rules

Supported activities: irrigation, sowing, spraying, harvesting, field operations, heat-stress awareness, heavy-rain awareness, wind risk, and general weather guidance. Inputs are optional; rules only use retrieved fields. Recommendations enumerate evidence and its source/valid time, data availability, and limitations. When required context is unavailable, the condition is `insufficient_data` rather than an estimated value.

WeatherGPT screening thresholds (heuristics, not official warnings or agronomic standards):

- Wind elevated: 20 km/h; high: 35 km/h.
- Air-temperature heat concern: 35 °C elevated; 40 °C high.
- Operational forecast rain signal: precipitation probability at least 60%, or a provider period whose description indicates rain/showers/drizzle.
- GFS accumulated-precipitation concern: 25 mm; high concern: 50 mm. This field is explicitly accumulation since the GFS initialization time through the returned valid time, not a daily amount.
- Local station evidence is excluded from current decision rules if older than 72 hours or quality-flagged; it remains visible as stale/quality-limited context.

Irrigation advice never claims soil moisture or computes evapotranspiration. Sowing is conditional on crop-specific field/soil suitability. Spraying gives weather-only guidance and no chemical dosage or pesticide prescription. Heat text is a weather concern, not a diagnosis. Humidity is contextual and does not diagnose crop disease. Wind rules use speed only; direction is not invented. Crop, growth stage, soil type, and irrigation availability can be submitted as context but no unsupported crop-specific rules are applied.

The response retains separate contexts for OpenWeatherMap current/forecast, NOAA/NCEP NOMADS GFS, local IMD DSP station observations, validated IMD historical grids, 1991–2020 IMD climatology, and the official IMD warning lookup. Historical/climatology context is not used as a forecast. A location without a nearby configured station uses the existing grid/provider inputs; station matching uses actual catalog coordinates and a 50 km radius, never a hard-coded city fallback.

## Chat, frontend, map, and languages

Agriculture chat intent/activity extraction routes to the deterministic agriculture tool. A missing or unresolved location is clarified/reported; the LLM receives the structured advice to phrase, not generate the recommendation's measurements or condition. English, Hindi, and Marathi use the existing localization infrastructure; localized chat keeps source labels, values, dates, and units from the structured result.

The existing Agriculture route/page and WeatherGPT visual system are reused. The page shows location, station metadata when actually matched, source-separated current/forecast/GFS/history/climatology/official-warning context, activity controls, recommendation, evidence, and limitations. It reuses the Phase 15 map canvas to show the selected location and configured station marker; it does not create field boundaries, crop layers, or weather interpolation. UI text uses the existing English/Hindi/Marathi dictionaries.

## Validation and limitations

Live validation in the configured runtime resolved Nashik with LocationService, retrieved OpenWeatherMap current conditions and operational forecast, retrieved real NOAA/NCEP NOMADS GFS 0.25° output, loaded station 42921's validated local CSV observations/quality report, and produced an agriculture recommendation with source-labelled evidence. The station's last local observation is from 2025-12-31 and is therefore stale relative to the 2026 validation run; it was not used as current evidence. The existing IMD alert mapping does not verify Nashik, so its official-warning context reports unresolved mapping; no warning was inferred from weather/model data. Historical context returned no data for the requested recent period; climatology service returned available status.

No live DSP authentication/download is implemented. Station data is limited to the files supplied locally, currently through 2025-12-31. Weather provider and GFS live requests depend on configured provider/network access. Generic agronomic thresholds are not crop-specific guidance; no soil, crop-health, or farm-boundary observations exist. This is weather-based decision support only, not an official agricultural department advisory.

## Tests

Deterministic backend tests cover Table-II and Table-III parsing, metadata/provenance, timestamps, units, nulls, duplicates/quality flags, invalid values, nearest station selection, deterministic activity rules, stale station handling, API validation/quality endpoint, and agriculture chat routing. Frontend tests cover activity submission, station/evidence rendering, loading/unavailable behavior, coordinate input, and translated controls. Live validation is reported separately from fixture-based tests.
