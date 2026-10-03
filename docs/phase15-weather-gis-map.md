# Phase 15 — Weather GIS map

## Audit

Before Phase 15, the Weather Map route rendered a static unavailable placeholder. No map library or map tiles were installed. The existing backend already exposed Phase 13 city resolution and coordinate-aware current, operational forecast, and Phase 14 GFS endpoints, plus separate IMD district warning and WeatherGPT advisory endpoints.

## Technology and base map

The page uses Leaflet 1.9.4 with React-Leaflet 4.2.1 and `@types/leaflet` 1.9.20. The base map uses the OpenStreetMap raster tile service at `https://tile.openstreetmap.org/{z}/{x}/{y}.png`; it needs internet access and is not offline. Attribution is displayed on the map page. OSM tile service is best-effort and has no SLA; users/operators must comply with its [tile usage policy](https://operations.osmfoundation.org/policies/tiles/). Tile errors are surfaced while the location and weather controls remain usable. The map performs no weather requests during pan/zoom.

## Location and data flow

City queries use the existing `/api/v1/location/resolve` endpoint and Phase 13 `LocationService`, then request data using the resolved coordinates. Users can also enter globally bounded latitude/longitude or click the map; those selections use the existing coordinate-capable current, forecast, and NWP APIs. Map clicks do not reverse-geocode. Current weather is requested when a location is selected; additional products are requested when their layer is enabled or explicitly refreshed.

## Layers

- **Current Weather:** Existing coordinate current-weather endpoint. Shows returned temperature, condition, humidity, wind speed, observation time, source, and one selected-location marker/popup.
- **Operational Forecast:** Existing coordinate forecast endpoint. Shows up to three returned daily summaries for the selected point and its provider attribution.
- **NWP / GFS:** Existing Phase 14 NWP endpoint. Displays returned model/run/retrieval/provenance metadata, resolution, selected model-grid point, grid distance, requested point, and an actual returned valid-time selector. The map distinguishes the selected location from its nearest GFS point.
- **GFS accumulated precipitation:** Uses the NWP point field and labels it as accumulation since model initialization; it is not called a daily total.
- **GFS 10 m wind speed:** Uses the returned point speed only. Wind direction is not available and no direction arrow is drawn.
- **Official IMD warnings:** Reuses the existing verified city/district warning endpoint. Results are shown as a separate district warning card and, when active, a distinct ring marker at the selected city lookup point; the API supplies no polygon geometry, so no warning area is drawn. Coordinate-only selections report the mapping requirement.
- **WeatherGPT Advisory:** Reuses the existing advisory endpoint and is labelled independently from IMD warnings and NWP model output. It is requested only for a resolved city.

There are no temperature, precipitation, wind, historical, climatology, or ML raster/heatmap layers. The available backend results are selected point data, not spatial fields; no interpolation or fabricated polygons are used. Historical/climatology currently do not provide sufficient map-grid layers for this page.

## Provenance and time

Provider names, observation times, forecast generation time, and NWP provider/model/run/valid time come from the corresponding API payloads. Current observation, operational forecast, NWP guidance, official IMD warnings, and WeatherGPT advisory remain separate. NWP timestamps are selected from returned point valid times only; map selection does not invent time steps.

## Validation and limitations

Frontend tests use deterministic fixtures to verify the map workspace, city/coordinate selection, layer requests, GFS grid metadata/time control, and unavailable/provider-error states; these tests do not constitute live validation.

Live validation was run against the existing backend APIs for Nashik. Location resolution returned Nashik, Maharashtra at 20.0112475, 73.7902364 from OpenWeatherMap geocoding. Coordinate current weather returned HTTP 200 with OpenWeatherMap provenance and an observed temperature of 22.75 °C. Operational forecast returned HTTP 200 with five periods. The existing NWP API returned HTTP 200 with real NOAA/NCEP NOMADS GFS 0.25° data: run 2026-09-29 12:00 UTC, selected grid point 20.00, 73.75, 4.386 km from the requested point; the 18:00 UTC valid point included 2 m temperature 21.9362548828 °C, accumulated precipitation since model initialization 0.1875 mm, and 10 m wind speed 0.3184076283 m/s. These are provider-returned point values, not map-wide fields.

The IMD warning endpoint returned HTTP 422 (`UNSUPPORTED_LOCATION`) for Nashik because its verified district mapping is not configured. The page exposes the unavailable/mapping state and does not draw warning geometry. The WeatherGPT advisory endpoint returned HTTP 200. An OpenStreetMap raster tile request returned HTTP 200 (`image/png`); tile availability still depends on external network access and the OSM tile usage policy. No new backend data service, raw data, or warning geometry was added.
