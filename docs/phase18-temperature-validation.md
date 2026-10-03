# Phase 18 — IMD daily temperature GRD validation preparation

## Status

**Current decoder status: `BLOCKED_FORMAT_FIELDS_UNVERIFIED`.**

No daily Tmax/Tmin GRD payload values have been decoded or integrated.

Phase 18A found no authoritative IMD evidence defining the external numeric
representation, byte order, or mapping from raw I/J indices to geographic
coordinates. The 4-byte value width does not establish IEEE-754, and plausible
decoded values would not resolve these questions. This preparation leaves those
properties unset in the production format specification and makes the decoder
stop before opening payload bytes.

## Audit of the existing implementation

The following implementation and documentation were inspected before changes:

- `backend/app/services/imd_grd_inspection.py`
- `backend/app/services/imd_temperature_pipeline.py`
- `backend/app/services/historical_data.py`
- `backend/app/services/historical_weather_service.py`
- `backend/app/schemas/weather.py` and `backend/app/api/routes/weather.py`
- `backend/tests/test_imd_grd_inspection.py`
- `backend/tests/test_imd_temperature_pipeline.py`
- `backend/tests/test_historical_data.py` and `backend/tests/test_historical_weather.py`
- `docs/phase10-historical-data.md`
- `docs/phase12-historical-climate.md`
- `docs/phase17-climate-analysis.md`
- `data/validation/imd_temperature_grd_validation.json` (existing metadata report)

`imd_grd_inspection.py` checks filename-derived year and file length only. The
temperature pipeline already stopped before decoding, but represented format
gaps as strings and its exception had no machine-readable reason. The generic
historical grid reader previously treated caller-supplied byte order and cell
ordering as sufficient and could read the payload. It now blocks before file
access until an authoritative format spec and a separately validated decoder
exist. Its legacy arguments alone no longer authorize decoding.
`LocalImdGridHistoricalProvider`
continues to read only the normalized rainfall CSV and leaves daily temperature
fields null. The history API labels daily Tmax/Tmin observations unavailable.
The existing climatology service remains a separate source of monthly normals.
Historical metadata previously listed `-999.0` as an additional Tmax/Tmin
missing marker. That marker is not established by the IMD temperature
documentation, so the metadata now uses only the documented 99.9 marker;
unrecognized values such as -999 remain visible for later quality flagging.
The temperature wording in the Phase 10 document was also corrected to call
these four-byte structural lengths, not float32 proof or proof of file framing.

## Proven metadata and existing inventory

The Phase 18A references are the official IMD Tmax and Tmin product pages:

- [IMD daily 1° Tmax documentation](https://imdpune.gov.in/cmpg/Griddata/Max_1_Bin.html)
- [IMD daily 1° Tmin documentation](https://www.imdpune.gov.in/cmpg/Griddata/Min_1_Bin.html)

The previously generated validation metadata reports 30 annual files and exact
size matches for all listed files. That inventory was read from the existing
JSON report; this phase did not reopen or inspect any raw GRD file.

- Tmax years: 2010–2012 and 2014–2024; 2013 is absent.
- Tmin years: 2010–2025; no gap within that filename range.
- Non-leap year: 365 records × 3,844 bytes = 1,403,060 bytes.
- Leap year: 366 records × 3,844 bytes = 1,406,904 bytes.
- Daily record: 31 × 31 cells, 4 bytes per value, 3,844 bytes total.
- Logical grid centers: longitude 67.5°E–97.5°E and latitude 7.5°N–37.5°N,
  both at 1° spacing.
- Units: °C. Undefined marker: 99.9.
- Calendar convention: records are daily and sequential, beginning on 1 January
  of the filename year and including 29 February in leap years.

The inventory is a structural size check only. It does not validate any cell
values, numeric encoding, raw cell orientation, or dates inside a payload.

## Format configuration and fail-closed policy

`imd_temperature_pipeline.py` now defines a typed `TemperatureGrdFormatSpec`.
The production `IMD_TEMPERATURE_FORMAT` records the established grid shape,
value width, Celsius units, missing marker, and annual date convention.
Its unresolved values remain `None`:

- `numeric_representation`
- `byte_order`
- `raw_ij_mapping` (I/J axis assignment and direction, index origins, and which
  index varies fastest in the stored record)
- `record_framing` (whether the supplied annual files have only the documented
  daily records or any file/record prefix or marker)

Each configured critical property also needs a `TemperatureFormatEvidence` entry
that identifies IMD as the authority and records a source and supporting
statement. The current production spec has no such entries. A syntactically
complete configuration can be validated separately, but that does not make it
authoritative or authorize reading production files.

`read_temperature_grd` first validates configuration and file structure, then
raises `TemperatureDecodeBlocked` with `reason_code` and structured `details`.
With the current production spec the reason is
`BLOCKED_FORMAT_FIELDS_UNVERIFIED`. Invalid values use
`BLOCKED_FORMAT_CONFIGURATION_INVALID`. Even an otherwise evidenced complete
configuration remains blocked with `BLOCKED_DECODER_NOT_IMPLEMENTED` until an
actual decoder is implemented and separately validated. No payload is opened
in this preparation phase.

The shared nearest-grid utility remains the only coordinate selector. The
logical ascending coordinate arrays are available, while the raw I/J mapping
must be supplied by IMD before raw-index extraction can be used. Record number
to date mapping is explicit through `temperature_date_for_record`; this is a
calendar helper and does not inspect data bytes.

## Historical and climate behavior

No API, historical service, schema, frontend, chat, or model behavior changed.
Daily historical Tmax/Tmin observations remain unavailable. Monthly temperature
climatology remains available from the existing IMD climatology service, with
its 1991–2020 baseline; it is not an observation and is not used to fill daily
temperature history. Rainfall extraction and prediction were not changed.

## Validation sequence after IMD clarification

Before any GRD payload is decoded, obtain authoritative, field-specific IMD
clarification for:

1. The external numeric representation, including whether it is IEEE-754 and
   the exact value width/encoding.
2. Byte order for the supplied GRD files.
3. The exact mapping from raw I and J indices to longitude and latitude,
   including each axis direction, index origin, and storage order/fastest index.
4. Confirmation of the framing of these annual files, including any file or
   record prefix/marker. The implementation must not assume headerless files.
5. Confirmation that records map to 1 January onward in calendar order and that
   the 99.9 sentinel is the missing value in the files being supplied.

Record the authoritative source, date, and supporting statement for each
property. Then run the following gates in order, without changing raw files:

1. Check filename/year, exact annual byte size, record count, grid shape, and
   record framing.
2. Test one synthetic representation against the configured parser, then
   decode a limited Tmax and Tmin sample only after authority is established.
3. Validate exact daily record/date counts, leap years, duplicates, missing
   dates, finite values, 99.9 handling, and quality flags without clipping or
   deleting suspicious values.
4. Validate documented coordinate mapping and use the existing haversine grid
   selector for the Nashik request; retain requested and selected coordinates,
   resolution, and distance.
5. Compare grid-cell values with available station 42921 observations only as a
   cross-dataset consistency check, reporting overlap and diagnostic statistics.
   Station and grid observations must remain separately attributed.
6. Expand to the remaining structurally valid annual files only after the
   sample, date, value, coordinate, and provenance checks pass.
7. Integrate normalized observations into the existing historical service only
   after every gate passes. Until then, API and UI temperature-observation
   availability remains unchanged.

No station/grid comparison or climate trend was performed in this preparation
phase. No quality statistics or temperature coverage results are claimed.

## Tests and manual action

The full backend suite passed: **223 passed**. Focused temperature/history tests
passed: **78 passed**. `git diff --check` passed. Tests cover unset numeric
representation, byte order, and I/J mapping; invalid configuration; no payload
reads while blocked in both reader paths; acceptance of a synthetic, explicitly
configured spec without granting decode permission; and the record-to-date
helper. Test payload bytes are synthetic in-memory bytes only. No frontend tests
were run because no frontend or API availability behavior changed.

**Manual action required:** request the unresolved encoding, endianness, raw
I/J orientation, and framing details from IMD in authoritative written
documentation or a source example explicitly tied to these daily temperature
GRD files. Do not enable decoding based on temperature plausibility or station
agreement alone.
