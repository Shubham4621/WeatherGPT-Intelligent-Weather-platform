# Phase 8: Historical Weather and Climate Analysis

WeatherGPT historical analysis is based on the available provider dataset. Historical observations use a separate `HistoricalWeatherProvider` contract and never reuse current observations or forecasts. No historical provider is configured in this project; the default adapter returns `status: unavailable` and does not contain sample weather values.

## API

`GET /api/v1/weather/history?city=Dhule&start_date=2025-07-01&end_date=2025-07-31`

Dates are ISO `YYYY-MM-DD` calendar dates. Reversed ranges return HTTP 422. Successful provider results contain status, location, source, retrieval time, covered period and records. Provider absence returns a controlled unavailable object. The route does not treat provider errors or missing records as zero rainfall.

## Data and metrics

Records can carry date, min/max/mean temperature, humidity, rainfall, wind speed, condition, source and retrieval time. Each measurement is optional. Aggregation omits metrics without observations. Temperature average is the arithmetic mean of reported daily mean temperatures; min/max use available reported daily extrema. Rainfall total sums available daily rainfall, average daily rainfall averages reported rainfall observations, and rainy days counts reported rainfall greater than zero. Humidity and wind use arithmetic means.

Monthly summaries group actual observations by calendar year and month. Partial coverage is explicitly marked by comparing returned record count with requested calendar days. Comparison uses `value - baseline`; percentage difference is `(difference / baseline) * 100`, and is null for a zero baseline. A trend requires four values and compares the means of the chronological first and second halves; differences within one percent of the first-half scale are stable. This is a descriptive calculation, not climate attribution.

The service supports provider-injected observations for daily, monthly, yearly and arbitrary date intervals. It does not declare official climate normals. Source metadata and coverage must be supplied by the real provider. Historical chat recognition returns no numeric measurements while a provider is unavailable.

## Limitations and manual tasks

- Configure and verify a reliable historical provider and backend credentials, if required.
- Verify historical dataset coverage and source metadata.
- Human-review historical and climate wording in Marathi and Hindi.
- Add a real provider adapter before expecting historical values or charts.

Current observations, forecasts, alerts, advisories and Phase 7 language selection remain separate features.
