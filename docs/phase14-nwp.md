# Phase 14 — NWP integration

## Architecture and data source

The NWP path is an independent provider and normalized response, separate from operational OpenWeatherMap forecasts, IMD observations and warnings, climatology, WeatherGPT rainfall ML, and WeatherGPT advisories. `NwpService` delegates to the `NwpProvider` protocol; `GfsNomadsProvider` retrieves coordinate-centered GRIB2 subsets from NOAA/NCEP's public NOMADS GFS 0.25-degree filter service. The GRIB decoder uses ECMWF ecCodes. A later WRF provider can implement the same provider interface without changing API or frontend response contracts.

Provider references: [NOMADS GFS 0.25-degree filter](https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl), [NCEP NOMADS documentation](https://nomads.ncep.noaa.gov/info.php?page=opendap_grib_migration), and [ecCodes Python bindings](https://github.com/ecmwf/eccodes-python).

## Fields and times

The initial normalized fields are 2 m air temperature (Kelvin converted to °C), surface accumulated precipitation since model initialization (kg m⁻² converted to mm water equivalent), and 10 m wind speed (u/v components in m/s combined to speed). Wind direction, humidity, pressure, cloud cover, and precipitation probability are not returned. Precipitation is cumulative since run initialization and is not a daily total. Forecast point requests are sampled at six-hour leads through a maximum 120 hours; only provider-returned leads are reported. The response identifies model initialization separately from each valid time and API retrieval time. NOAA NOMADS documents GFS 0.25° forecast intervals typically as hourly for early leads or every three hours thereafter; this integration deliberately requests six-hour samples. GFS model cycles are probed on the six-hour UTC cycle, up to the latest nine candidate cycles.

Native model grid metadata is 0.25°; selected grid coordinates and great-circle distance to the requested coordinates are returned from the actual GRIB grid. Coordinates use latitude and longitude degrees, and longitude is normalized for grid selection. Requests whose small bounding box crosses the 0°/360° seam are fetched as two subsets and the decoder selects the nearest real grid point from both. No IMD grid is used for NWP selection.

## Location and API

`GET /api/v1/weather/nwp` accepts either `city` or `lat` plus `lon`, and `days` from 1 to 5. City resolution reuses Phase 13 `LocationService`; configured historical reference aliases are used only if the location provider is unavailable. Numeric coordinates are validated globally to latitude [-90, 90] and longitude [-180, 180]. The response carries requested/resolved location, provider/model, initialization/retrieval times, valid-time points, units, model resolution, selected grid, provenance, and status. Existing current and operational forecast endpoints are unchanged.

Machine-readable unavailable/error reasons include location errors, `grib_decoder_unavailable`, `nwp_timeout`, `nwp_provider_unavailable`, `nwp_invalid_response`, provider run/lead availability, and malformed GRIB/field/unit conditions. No substitute forecast or fabricated values are returned. Successful and partial point responses are cached for 10 minutes by coordinate/horizon; cached payloads retain their run and retrieval metadata. Errors are not cached.

## Chat and frontend

NWP/GFS phrases are classified to an NWP intent and routed to the NWP tool after city/location resolution. The tool response is attached as structured `nwp_data`; unavailable results remain explicit. The deterministic response names GFS and states that it is model guidance, not an observation, official warning, operational forecast, or WeatherGPT prediction. NWP values are not computed by the LLM.

The existing NWP page is reused with a compact city/coordinate search, run/valid-time/provider/grid metadata, and a time series table for returned variables. It has loading, provider-error, and explicit unavailable/error states. The separate operational forecast page is untouched. No map, model comparison, or unprovided variable is represented.

## Access, limits, and validation

NOMADS public access needs no API key. The application uses a 12-second per-request timeout and does not retry indefinitely; it checks recent six-hour model cycles when a lead is absent. The reviewed source documentation does not establish an application-specific request quota; callers should respect the public NOMADS service policies. ecCodes Python is Apache-2.0 licensed and declared as `eccodes==2.48.0`; deployments must install backend requirements. On 2026-09-29, a read-only request for the 2026-09-29 12Z GFS f006 product over the configured Dhule reference area returned HTTP 200 and a 1,144-byte GRIB payload. A separate real f006 probe across the prime meridian returned two GRIB subsets (1,136 and 1,137 bytes), validating the split-window source request. The normalized live fields were not decoded in this environment because ecCodes is not installed here. Unit tests use deterministic provider/response fixtures and do not represent live NWP values.

## Limitations and future extension

Coverage and available leads depend on NOMADS run publication and public access. There is no multi-model comparison, WRF data, NWP-driven advisory, or NWP-to-ML integration. The model output is guidance, not a guarantee or warning. Future station or model sources must preserve source/model/run/valid-time/provenance metadata and implement the provider interface.
