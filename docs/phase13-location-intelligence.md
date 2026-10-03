# Phase 13 — Advanced Location Intelligence

## Architecture

`LocationService` is the shared city-to-coordinate resolver. It uses the OpenWeatherMap Geocoding API with the same configured weather API key and timeout. It returns a typed location with the original query, available city/state/country metadata, coordinates, provider provenance, resolution method, and resolved status. Missing metadata stays null. Empty matches, ambiguous distinct matches, provider failures, and invalid coordinates remain distinct machine-readable outcomes. Provider response bodies and credentials are not returned.

`GET /api/v1/location/resolve?q=...` exposes this structured resolution. Coordinates may also be passed directly and are validated against global latitude and longitude bounds, including the boundary values.

## Weather and forecast

Current weather retains the existing city and coordinate request forms. Forecast now accepts either `city` or a complete `lat`/`lon` pair; city requests preserve the prior contract. OpenWeatherMap remains the source for current observations and operational forecasts. Neither is labeled as an IMD product.

## Historical data and climatology

Historical and climatology city requests first use the existing configured reference-coordinate mapping; other city names use the shared geocoder. The existing nearest-grid selection remains authoritative. Historical results are limited to the installed validated IMD rainfall cell near 21.00°N, 74.75°E and its coverage distance; other places return no coverage rather than receiving that cell's data. Requested coordinates, selected coordinates, distance, dataset resolution, and provenance are carried with available historical records.

Climatology independently selects a point on each file's native grid and returns requested coordinates, selected coordinates, distance, resolution, source, units, and the 1991–2020 baseline. Rainfall grids remain 0.25° or 1°; temperature normals remain 0.5°. Out-of-coverage locations return an explicit no-data reason. The result does not imply that products at different resolutions use the same physical grid cell.

## Rainfall prediction

The existing model remains coordinate-based and uses the shared historical nearest-grid selection function. It reports requested coordinates and selected cell/distance. Coordinates outside validated rainfall-grid coverage fail explicitly; no Dhule fallback is used. The model response remains labeled WeatherGPT model prediction, separate from forecast, observation, warning, and climatology products.

## Advisory and official IMD alerts

Advisory continues to use the existing deterministic forecast and warning inputs and is labeled WeatherGPT guidance. Official IMD warning lookup continues to require the separately configured verified `IMD_DISTRICT_MAPPINGS`/legacy mapping. Generic geocoding never creates or guesses an IMD district ID. Unmapped locations and provider authorization failures remain distinct errors.

## Chat and frontend

Historical observations and climate normals resolve names to coordinates before querying the existing tools. A geocoded but unsupported historical location returns unavailable coverage; values are not substituted from the Dhule reference cell. Chat has no persistent active-location context, so follow-up messages that omit a location request clarification rather than infer memory. Current/forecast city lookup continues through the configured OpenWeatherMap provider. The existing dashboard design is unchanged; the weather search placeholder now describes city search generically.

## Testing and external dependencies

Deterministic tests cover geocoder success, no match, ambiguity, provider failure, coordinate boundaries, coordinate forecast, historical non-fallback, and city-to-climatology grid lookup. Existing tests cover historical coordinate selection, prediction grid selection, IMD mapping separation, and API contracts. Live geocoding/current/forecast calls require a valid `WEATHER_API_KEY`; no successful live lookup is claimed without provider credentials. Installed historical and climatology files can be validated locally without external calls.

## Coverage limitations

The validated observation archive remains a single 0.25° rainfall cell (2013–2024). Climatology files cover their cataloged India grids at their native resolutions. Temperature historical GRDs remain undecoded pending authoritative binary layout details. Future station observations can use the existing historical provider interface; this phase does not add station data.
