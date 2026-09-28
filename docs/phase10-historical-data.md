# Phase 10 — IMD Historical Dataset Inspection

Inspection was performed on the raw files in place. No raw file was modified, renamed, moved, deleted, or overwritten. No full-grid processing or model work was performed. File sizes below exclude the directory `.gitkeep` placeholders.

## 1. Actual files discovered

There are 40 data files: 13 rainfall NetCDF files (330,822,852 bytes total), 11 maximum-temperature GRD files, and 16 minimum-temperature GRD files (temperature total: 37,909,528 bytes). The temperature file count is 27. Directory totals are 368,732,380 bytes.

All rainfall files have NetCDF classic/CDF-1 signature (`CDF\\x01`) and embedded dimensions/time coordinates. The temperature files are `.GRD` binary. Their sizes align exactly with the IMD-published 31×31 float32 daily-record size for the year named by each file; values were not decoded because byte order is not specified in the official reading examples.

## 2. Rainfall dataset

Product: IMD yearly gridded daily rainfall, variable `RAINFALL`, units `mm`, dimensions `(TIME, LATITUDE, LONGITUDE)`. The actual sample file declares `Conventions=CF-1.0`, rainfall `missing_value` and `_FillValue` of `-999.0`, and time units `days since 1900-12-31 00:00:00`. Values are stored as big-endian float32; coordinate arrays are float64. `scipy.io.netcdf_file` successfully read metadata and the selected local grid sample. xarray and netCDF4 are not installed in this environment.

The embedded coordinate arrays in every annual file inspected contain 129 latitudes from 6.5°N to 38.5°N and 135 longitudes from 66.5°E to 100.0°E, at 0.25° spacing. Each file has 365 or 366 time records. Time coordinates decode to the January 1–December 31 dates named by each file.

| Exact filename | Bytes | Embedded dates | Records |
|---|---:|---|---:|
| `RF25_ind2013_rfp25.nc` | 25,431,832 | 2013-01-01–2013-12-31 | 365 |
| `RF25_ind2014_rfp25.nc` | 25,431,832 | 2014-01-01–2014-12-31 | 365 |
| `RF25_ind2015_rfp25.nc` | 25,431,832 | 2015-01-01–2015-12-31 | 365 |
| `RF25_ind2016_rfp25.nc` | 25,501,500 | 2016-01-01–2016-12-31 | 366 |
| `RF25_ind2017_rfp25.nc` | 25,431,832 | 2017-01-01–2017-12-31 | 365 |
| `RF25_ind2018_rfp25.nc` | 25,431,832 | 2018-01-01–2018-12-31 | 365 |
| `RF25_ind2019_rfp25.nc` | 25,431,832 | 2019-01-01–2019-12-31 | 365 |
| `RF25_ind2020_rfp25.nc` | 25,501,500 | 2020-01-01–2020-12-31 | 366 |
| `RF25_ind2021_rfp25.nc` | 25,431,832 | 2021-01-01–2021-12-31 | 365 |
| `RF25_ind2022_rfp25.nc` | 25,431,832 | 2022-01-01–2022-12-31 | 365 |
| `RF25_ind2023_rfp25.nc` | 25,431,832 | 2023-01-01–2023-12-31 | 365 |
| `RF25_ind2024_rfp25.nc` | 25,501,532 | 2024-01-01–2024-12-31 | 366 |
| `RF25_ind2025_rfp25.nc` | 25,431,832 | 2025-01-01–2025-12-31 | 365 |

The official archive describes the 0.25° product through 2024. The local 2025 file has a complete 2025 time coordinate, but 2025 is outside that published period; its exact download provenance and official status need confirmation. The 2024 file is 32 bytes larger than the other leap-year files while retaining the same inspected dimensions, dates, and variable layout; this inspection did not investigate that small header-size difference.

## 3. Tmax dataset

Product inferred from the exact `Maxtemp_MaxT_YYYY.GRD` names and the official IMD Tmax archive. Published units are °C; published grid is 31×31 at 1° with latitude centers 7.5°N–37.5°N and longitude centers 67.5°E–97.5°E. The official GrADS control example declares undefined value `99.9`. The official read example describes direct-access records of `31 × 31 × 4` bytes and C `float` values, with 365/366 records annually. No explicit byte order is stated in the official examples.

| Exact filename | Bytes | Filename year / expected annual days from official layout |
|---|---:|---|
| `Maxtemp_MaxT_2014.GRD` | 1,403,060 | 2014 / 365 |
| `Maxtemp_MaxT_2015.GRD` | 1,403,060 | 2015 / 365 |
| `Maxtemp_MaxT_2016.GRD` | 1,406,904 | 2016 / 366 |
| `Maxtemp_MaxT_2017.GRD` | 1,403,060 | 2017 / 365 |
| `Maxtemp_MaxT_2018.GRD` | 1,403,060 | 2018 / 365 |
| `Maxtemp_MaxT_2019.GRD` | 1,403,060 | 2019 / 365 |
| `Maxtemp_MaxT_2020.GRD` | 1,406,904 | 2020 / 366 |
| `Maxtemp_MaxT_2021.GRD` | 1,403,060 | 2021 / 365 |
| `Maxtemp_MaxT_2022.GRD` | 1,403,060 | 2022 / 365 |
| `Maxtemp_MaxT_2023.GRD` | 1,403,060 | 2023 / 365 |
| `Maxtemp_MaxT_2024.GRD` | 1,406,904 | 2024 / 366 |

The file sizes equal precisely the official expected number of float32 grid records for those years (including leap days). This supports the documented layout and indicates no additional header bytes, but does not prove byte order or validate the values. Tmax values were not decoded.

## 4. Tmin dataset

Product inferred from the exact `Mintemp_MinT_YYYY.GRD` names and the official IMD Tmin archive. Published units are °C; the published 1° grid is 31×31 with the same coordinates as Tmax. The official Tmin control example declares undefined value `99.9`; official direct-access examples use daily records of `31 × 31 × 4` bytes and 365/366 days annually. Byte order is not explicitly documented. The official published period is 1951–2024.

| Exact filename | Bytes | Filename year / expected annual days from official layout |
|---|---:|---|
| `Mintemp_MinT_2010.GRD` | 1,403,060 | 2010 / 365 |
| `Mintemp_MinT_2011.GRD` | 1,403,060 | 2011 / 365 |
| `Mintemp_MinT_2012.GRD` | 1,406,904 | 2012 / 366 |
| `Mintemp_MinT_2013.GRD` | 1,403,060 | 2013 / 365 |
| `Mintemp_MinT_2014.GRD` | 1,403,060 | 2014 / 365 |
| `Mintemp_MinT_2015.GRD` | 1,403,060 | 2015 / 365 |
| `Mintemp_MinT_2016.GRD` | 1,406,904 | 2016 / 366 |
| `Mintemp_MinT_2017.GRD` | 1,403,060 | 2017 / 365 |
| `Mintemp_MinT_2018.GRD` | 1,403,060 | 2018 / 365 |
| `Mintemp_MinT_2019.GRD` | 1,403,060 | 2019 / 365 |
| `Mintemp_MinT_2020.GRD` | 1,406,904 | 2020 / 366 |
| `Mintemp_MinT_2021.GRD` | 1,403,060 | 2021 / 365 |
| `Mintemp_MinT_2022.GRD` | 1,403,060 | 2022 / 365 |
| `Mintemp_MinT_2023.GRD` | 1,403,060 | 2023 / 365 |
| `Mintemp_MinT_2024.GRD` | 1,406,904 | 2024 / 366 |
| `Mintemp_MinT_2025.GRD` | 1,403,060 | 2025 / 365 |

Sizes exactly match official-layout daily float32 records for the filename year. This is a structural consistency check, not a value decode. The 2010–2013 files predate the official page's stated 1951–2024 span, and the 2025 file extends beyond it; verify those files' download provenance/version before treating their contents as part of this official product.

## 5. Date coverage

Observed from NetCDF time coordinates, rainfall covers **2013-01-01 through 2025-12-31**, continuously by annual files. Temperature year ranges below are filename ranges; the corresponding per-year day counts are byte-length-consistent with the official layout, but dates are not encoded inside the binary files and were not decoded.

- Tmax: annual files 2014–2024.
- Tmin: annual files 2010–2025.
- All three file collections share calendar years **2014–2024** (4,018 expected daily slots, counting leap days), provided the official annual-file convention maps record 1 to January 1 and proceeds one day per record. This date mapping is documented by the official examples but was not value-verified from the GRD contents.

## 6. Spatial coverage and resolution

All grids cover the Dhule coordinate (20.90°N, 74.80°E). Rainfall is 0.25° with 129×135 points. Tmax and Tmin are each 1° with 31×31 points. The NetCDF coordinate arrays were read directly; temperature coverage and centers come from the official archive specifications because GRD files have no self-describing coordinate metadata. These are gridded analysis cells, not station observations.

## 7. Dhule grid-cell selection

For rainfall, the actual NetCDF coordinates give nearest grid center **21.00°N, 74.75°E**, at zero-based array index `(LATITUDE=58, LONGITUDE=33)` in inspected files. Extraction successfully read the cell and its 3×3 neighbors from `RF25_ind2015_rfp25.nc` for **2015-01-01**:

| Latitude \ Longitude | 74.50°E | 74.75°E | 75.00°E |
|---:|---:|---:|---:|
| 20.75°N | 2.5999 mm | 7.1412 mm | 7.0436 mm |
| 21.00°N | 6.2293 mm | **10.0326 mm** | 10.1130 mm |
| 21.25°N | 7.2087 mm | 10.0590 mm | 8.7845 mm |

This is an extraction smoke sample, not a claim of validated climatological quality. At the selected cell in the 2015 file, the 365 readable daily values ranged from 0 to 64.3551 mm; 300 were zero, with no `-999` or negative values at that one cell.

For Tmax/Tmin, using the officially documented coordinate centers, nearest is **20.5°N, 74.5°E** (zero-based `[lat, lon]` grid index `[13, 7]`). The values were intentionally not read because the official documentation does not establish an explicit byte order for these files. Thus binary sample extraction is not yet proven.

## 8. Missing values

- Rainfall NetCDF directly declares `_FillValue=-999.0` and `missing_value=-999.0`.
- Temperature official GrADS examples declare `UNDEF 99.9` for the grid. The GRD values were not decoded to check whether this marker appears in these files.
- No missing-value frequency has been computed across full grids. Rainfall's Dhule cell in the 2015 sample year had zero missing markers.

## 9. Data quality observations

Rainfall files are self-describing and their annual time axes, dimensions, coordinate ranges, variable units, and fill markers were read. The selected 2015 Dhule-neighborhood sample is numeric and plausible in basic form. This is not a full-grid or full-period QC check.

Temperature file lengths are consistent with official daily grid record lengths for the named years, but value ranges, missing-marker frequencies, row/column orientation in these specific downloads, and byte order have not been tested. The temperature 2008-onward archive is based on fewer stations according to IMD. Extra Tmin years 2010–2013 and both datasets' 2025 files require provenance confirmation because they lie outside the official pages' currently described periods.

## 10. Compatibility/alignment of datasets

All three sets have overlapping annual coverage from 2014 through 2024 and expected daily counts, so a date-keyed alignment is feasible for those years once GRD byte order and record orientation are confirmed. Rainfall is at 0.25° while both temperatures are at 1°; their Dhule-nearest centers differ. Keep per-variable coordinates, resolutions, source filenames, and nullable fields/provenance rather than representing their different grid cells as one station coordinate. Do not interpret missing files or missing markers as zero rainfall.

## 11. Problems or unknowns

1. `xarray` and `netCDF4` are unavailable; SciPy successfully read the NetCDF classic files and sample.
2. The official GRD examples establish 31×31, daily, 4-byte float records and `99.9` undefined, but do not state byte order. Temperature values and a Dhule sample therefore remain unread.
3. The official published archive pages describe rainfall/Tmax/Tmin through 2024; local rainfall 2025, Tmax 2014–2024, and Tmin 2010–2025 files need verified download provenance. In particular, Tmin 2010–2013 are outside the published range.
4. No station observation files are present in `data/raw/dhule_station/`; this inspection does not verify station data.
5. No full-grid data-quality statistics were calculated. Rainfall sample-only results must not be generalized to the entire dataset.

## 12. Recommended next step

Confirm the provenance of out-of-published-range files and obtain IMD clarification of GRD byte order and cell order (or official control/sample metadata that explicitly settles them). Then run a read-only, single-cell extraction test for Tmax/Tmin and compare its dates and missing markers against the rainfall series for the verified overlap. Only after that validation should the project create a normalized Dhule extract or compare with separately acquired IMD station records. No `dhule_historical.csv` was created; no ML or prediction phase was started.

## Official metadata references

- [IMD Pune daily rainfall NetCDF archive](https://imdpune.gov.in/cmpg/Griddata/Rainfall_25_NetCDF.html)
- [IMD Pune daily maximum-temperature binary archive and official read examples](https://imdpune.gov.in/cmpg/Griddata/Max_1_Bin.html)
- [IMD Pune daily minimum-temperature binary archive](https://imdpune.gov.in/cmpg/Griddata/Min_1_Bin.html)

## Generic Location Support

Dhule is a validation location, not a supported-location limit. The grid selection utility accepts any finite latitude/longitude and an iterable of dataset coordinate pairs. It returns the requested point, selected grid point, and great-circle distance in kilometers. The IMD-grid convenience wrapper builds its candidate coordinates from the selected dataset metadata and rejects locations outside that grid's coverage.

Each dataset is selected independently and keeps its own real grid center and resolution:

- Rainfall: 0.25° grid; selection from that product's latitude/longitude centers.
- Tmax: 1° grid; nearest documented center.
- Tmin: 1° grid; nearest documented center.

An extracted series retains the requested coordinate, selected grid latitude/longitude, distance, source, product name, and resolution. Rainfall and temperature are never resampled to one shared artificial resolution. There is no geocoding dependency. A future history API can accept `lat`/`lon` and perform independent per-product selection, but that API query contract is not implemented in this step.

### Official GRD format verification and decode status

The official IMD Tmax example documents 31×31 grid points, 365/366 daily records, a direct-access record length of `31 × 31 × 4` bytes, Fortran values and C `float` values, `UNDEF 99.9`, and GrADS `XDEF` longitudes increasing from 67.5°E by 1° and `YDEF` latitudes increasing from 7.5°N by 1°. Its Fortran sample reads one direct-access record for each day and loops `J` inside `I`; its GrADS sample uses daily `TDEF` beginning 1 January. These support record size and sequential daily records. They do not document explicit byte order or explicitly state in prose that the binary `I/J` axes correspond to latitude/longitude. The X/Y control fields imply longitude is the fast X axis, but that binding has not been confirmed against the downloaded bytes. The example uses 4-byte `float` but does not specify IEEE-754 representation. Tmin's official page publishes the same grid organization and undefined marker; the Tmax page contains the available explicit reader examples.

**GRD values remain undecoded.** No little-endian or big-endian attempt was made, and no temperatures were selected because plausible-looking numbers cannot resolve byte order. The matching file lengths are structural evidence only, not proof of encoding or decoded values. Before decoding one Tmax and one Tmin file, obtain authoritative confirmation of byte order/float representation and binary I/J-to-coordinate mapping, or an official independently verifiable sample/control file tied to these exact products. Until then, range checks and Dhule GRD extraction cannot be claimed as successful.

The generic coordinate-selection tests include Dhule, three hypothetical coordinate sets, a pole/longitude boundary case, dataset-specific resolutions, and distance calculation. They do not read or decode the temperature GRD files.

## Generic Location Support

Dhule is only a validation location. `select_nearest_grid_point(latitude, longitude, dataset_coordinates)` accepts arbitrary finite latitude/longitude values and any supplied iterable of grid coordinate pairs. It returns the request coordinate, the selected coordinate, and haversine distance in kilometers. The IMD-specific wrapper generates candidate coordinate pairs from each grid's own metadata and checks that the request falls within that grid's coverage. No city geocoder is used.

The selectors preserve distinct product geometry: rainfall at 0.25°, Tmax at 1°, and Tmin at 1°. They select each dataset independently. For Dhule, the nearest rainfall point is 21.00°N, 74.75°E at approximately 12.27 km from the request; nearest Tmax/Tmin is 20.5°N, 74.5°E at approximately 54.33 km. Selected records carry requested and selected coordinates, distance, source, dataset, and that product's grid resolution. No common-resolution resampling is applied.

The NetCDF point reader now supports the actual uppercase IMD NetCDF variable/coordinate names and can use SciPy's NetCDF3 reader if xarray is unavailable; this was checked against the local 2015 rainfall file and returned 365 daily Dhule-cell rows, including the documented 2015-01-01 sample. A future `/weather/history?lat=<lat>&lon=<lon>` contract is feasible, but the HTTP API and location geocoding have not been changed in this step.

### GRD decoding remains blocked

The official IMD Tmax page documents 31×31 points, per-day direct-access record length `31 × 31 × 4`, sequential daily records, 4-byte Fortran/C float usage, undefined marker 99.9, longitude centers increasing eastward (`XDEF`) and latitude centers increasing northward (`YDEF`). Its sample read visits `J` inside `I`; the GrADS control example establishes X=longitude and Y=latitude, suggesting longitude-fastest stream layout, but does not explicitly bind the downloaded GRD `I/J` array indexes to geographic axes. The page does **not** state byte order or IEEE representation. The Tmin page publishes the same product grid and undefined marker but no additional verified byte-order detail. Therefore cell-axis binding is still treated as UNKNOWN, as are byte order and exact float representation.

No Tmax or Tmin values were decoded or temperature-range checked. The local annual file sizes match the expected byte counts but cannot establish endian or axis semantics. The binary helper now requires callers to explicitly supply both byte order and the cell-order declaration; it rejects unspecified/unsupported values. This is an API safety gate, not evidence that either option has been verified for these files. A trustworthy Tmax/Tmin extraction test remains blocked until IMD confirms byte order/float representation and the I/J-to-latitude/longitude mapping for these products (or an official control/sample pair tied to these exact files resolves them).

## IMD monthly gridded climatology inventory (2026-09-27)

This metadata-only inventory covers the files currently present under `data/raw/imd_climatology/`. The scanner reads NetCDF headers and coordinate arrays and hashes source files for identity checks; it does not alter raw files. The per-file machine-readable catalog is [`data/imd_climatology_catalog.json`](../data/imd_climatology_catalog.json). Dataset files remain ignored by Git.

All 54 files are readable classic NetCDF (CDF-1). Each has one two-dimensional data variable over `lat` and `lon`; an unused unlimited `time` dimension is declared too. The month attribute is zero-based and agrees with every filename. Rainfall uses variable `rf`, units `mm`, and `_FillValue`/`missing_value` of `-999`. Temperature variables are `tmax`, `tmin`, or `tmean`; no `units` attribute is present, so units remain unknown from the files. Temperature missing/fill marker is approximately `99.9`.

| Parameter/product | Files / unique months | Native grid and coordinate bounds | Units in metadata |
|---|---:|---|---|
| Rainfall, `rf_1deg_*` | 12 / 12 | 1°, 33×35; 6.5–38.5°N, 66.5–100.5°E | mm |
| Rainfall, `rf_p25_*` | 12 / 12 | 0.25°, 129×135; 6.5–38.5°N, 66.5–100.0°E | mm |
| Maximum temperature, `tmax_p5_*` | 6 files / 5 months; June–October | 0.5°, 61×61; 7.5–37.5°N, 67.5–97.5°E | Not encoded |
| Minimum temperature, `tmin_p5_*` | 12 / 12 | 0.5°, 61×61; 7.5–37.5°N, 67.5–97.5°E | Not encoded |
| Mean temperature, `tmean_p5_*` | 12 / 12 | 0.5°, 61×61; 7.5–37.5°N, 67.5–97.5°E | Not encoded |

The variable names, coordinate spacing, dimensions, extents, and rainfall units verify the product labels and resolutions found in the filenames. All products cover the Dhule reference coordinate (20.90°N, 74.80°E). No resampling was performed.

Each variable declares `time_op_ncl = "Climatology: 30 years"`. Rainfall also records `history` as `From rf_1991.grd` or `From ind1991_rfp25.grd`; temperature files do not encode origin/history. The files do not encode the start and end years of the 30-year baseline. Thus the exact 1991–2020 period is **not verified** from the files, despite the rainfall source filename containing 1991. Their metadata identifies NCL climatology processing (`function clmMonTLL: contributed.ncl`) but does not provide the original download URL.

Nearest cells were calculated independently from each file's coordinate arrays using great-circle distance:

| Product | Dhule nearest grid cell (lat, lon) | Distance |
|---|---|---:|
| 1° rainfall | (20.5, 74.5) | 54.333 km |
| 0.25° rainfall | (21.0, 74.75) | 12.272 km |
| 0.5° Tmax, Tmin, Tmean | (21.0, 75.0) | 23.558 km |

These are grid-cell centers, not Dhule station observations. Per-file coordinates, selected cells, distance, size, checksums, dimensions, variable attributes, and provenance fields are in the catalog.

`rf_p25_jan_clm.nc` exists in the rainfall folder; `data/raw/imd_climatology/temperature/rf_p25_jan_clm.nc` does not exist. The file has variable `rf`, rainfall long name, `mm` units, a 0.25° grid, and rainfall processing provenance. It is correctly located in the rainfall folder; no file was moved.

`tmax_p5_jun_clm.nc` and `tmax_p5_jun_clm (1).nc` are byte-for-byte identical: both are 16,515 bytes and share SHA-256 `369b51e1def769fee9b97f67923759d861ad62f9ce5eab403f6cebf6d0e1eb6b`. Neither was deleted.

All 12 months are present for both rainfall resolutions, Tmin, and Tmean. Tmax has five unique months (June–October); June is duplicated. Temperature units and exact baseline period still require authoritative provider documentation or a manifest. This inventory did not extract a processed city dataset, resample grids, or train/predict with ML.

## Follow-up: authoritative climatology metadata review (2026-09-27)

### Baseline

The NetCDF attributes say `Climatology: 30 years`, but do not provide baseline start/end years. Review of the [IMD-DSP Gridded Climatology page](https://dsp.imdpune.gov.in/home_gridded_climatology.php), the [IMD Climate Information maximum-temperature climatology page](https://imdpune.gov.in/climinfo/Max.html), and the [minimum-temperature climatology page](https://imdpune.gov.in/climinfo/Min.html) did not locate a product-specific baseline statement, file manifest, or reference that establishes 1991–2020 for these monthly NetCDFs. The [1991–2020 Climatological Tables](https://www.imdpune.gov.in/library/public/Climatological%20Tables%201991-2020.pdf) are a separate station climatology publication and do not verify this gridded product. The correct catalog status is therefore **unspecified 30-year baseline**; do not describe these products as 1991–2020 normals yet.

### Temperature units

The local `tmax_p5`, `tmin_p5`, and `tmean_p5` NetCDF variables have no `units` attribute. IMD's [1° daily maximum-temperature product page](https://imdpune.gov.in/cmpg/Griddata/Max_1_Bin.html) explicitly gives Celsius, but that describes a distinct 1° daily binary product, not these 0.5° monthly climatology NetCDFs. No reviewed authoritative source tied Celsius to the three exact local products. Catalog units therefore remain `null` / unverified for all three.

### Tmax months and official availability

The local inventory remains five unique Tmax months: **June, July, August, September, October**; June has two byte-identical copies. Searching the complete local climatology NetCDF inventory found no other Tmax months or alternate filename convention.

IMD's public [Climate Information page](https://imdpune.gov.in/climinfo/Max.html) identifies a “Monthly Maximum Temperature Climatology” view, but its accessible content does not enumerate downloadable grids or month files. The official [DSP Gridded Climatology page](https://dsp.imdpune.gov.in/home_gridded_climatology.php) displays two selection controls, but the available options/product metadata are not exposed in the accessible page content. IMD's [Gridded Data Archive index](https://www.imdpune.gov.in/lrfindex.php) lists historical 1° daily Tmax/Tmin binary archives and separate 0.5° real-time daily products; these are not documentation for the local monthly 0.5° climatologies.

Consequently, authoritative public material reviewed here does not establish whether January–May and November–December are absent from IMD's offering, were omitted from the download, or are distributed through another selection/download route. It also does not give a documented reason for the five-month local subset. Do not infer that the official product contains only five months; request the exact file manifest, period, units, and complete month list from the IMD-DSP/CRS Pune gridded-data contact before using these climatologies. No missing month has been fabricated or filled.

The detailed source-review status has been added to `data/imd_climatology_catalog.json`; the per-file `units` values remain unset for temperature, and per-file baseline dates remain unknown.

## Daily Tmax/Tmin GRD structural validation (2026-09-27)

A read-only validator, `backend/app/services/imd_grd_inspection.py`, checks filename/year, actual file size against the documented annual layout, leap-year day count, and expected record dimensions. It does not open or decode the values, change files, infer endianness, or select a spatial cell. Running it against the current directory inspected 27 files: 11 Tmax (2014–2024) and 16 Tmin (2010–2025). **All 27 match the expected byte count exactly.**

| Layout item | Verified status |
|---|---|
| Grid dimensions | 31 × 31 (961 grid values per day) |
| Record size | 31 × 31 × 4 = 3,844 bytes/day |
| Non-leap annual size | 365 records = 1,403,060 bytes |
| Leap annual size | 366 records = 1,406,904 bytes |
| Value width | 4 bytes; IMD examples use C `float` / Fortran values, supporting a 32-bit float width. IEEE-754 representation is not explicitly specified. |
| File size result | Every current file exactly matches its calendar year's expected size; this supports the documented structure but does not prove value encoding or absence of a compensating layout difference. |

The official [IMD Tmax](https://imdpune.gov.in/cmpg/Griddata/Max_1_Bin.html) and [IMD Tmin](https://imdpune.gov.in/cmpg/Griddata/Min_1_Bin.html) annual archive pages state daily 1° products, 31 latitude centers from 7.5°N to 37.5°N, 31 longitude centers from 67.5°E to 97.5°E, leap-year 366-record files, Celsius units, and `UNDEF 99.9`. Their reader examples specify one direct-access record per day with record length `31×31×4`, use a C `float` array, and read/write the float values directly. No scale or offset is documented. The files’ names and exact annual lengths agree with this layout.

The sample Fortran reader processes daily records sequentially, and its GrADS control example gives a daily `TDEF` starting `1JAN1994` with 1-day increments. This supports the documented annual convention of day 1 at January 1 and one sequential record per day, with leap years including February 29. The downloaded annual files contain no embedded date metadata, so this is based on the official product example and year in each filename, not an independently decoded check of each record.

The same IMD control example defines the logical longitude/X axis as 67.5°E increasing by 1° and latitude/Y axis as 7.5°N increasing by 1°. The Fortran sample loops `J` inside `I`, but the official page does not explicitly state which raw index (`I` or `J`) is longitude versus latitude, or tie its array order to the GrADS X/Y axes. Therefore **logical axis direction and extent are verified; raw I/J-to-latitude/longitude mapping remains UNVERIFIED**. Byte order (little/big endian) and explicit IEEE-754 representation also remain **UNVERIFIED**. No endian was chosen based on plausible-looking values, and no raw temperatures were decoded.

Tests cover the documented record-size formula, 365/366-day leap-year behavior, 31×31 dimensions, size mismatch reporting, and explicit `UNVERIFIED` flags for byte order and raw I/J mapping. The test fixtures check byte length only and contain no weather observations. Spatial extraction stays blocked until IMD provides explicit I/J mapping and byte-order/representation confirmation (or a verified sample tied to these exact annual files).

## IMD 0.25-degree daily rainfall extraction (2026-09-27)

The read-only pipeline in `backend/app/services/imd_rainfall_pipeline.py` validates annual IMD RF25 NetCDF files and extracts the nearest grid-cell series for any requested latitude/longitude. It deliberately accepts only the annual `RF25_indYYYY_rfp25.nc` naming pattern, so monthly climatology files cannot enter this daily-observation pipeline. It reuses the generic haversine `select_nearest_grid_point` helper.

### Official definition and validation

IMD's [0.25-degree rainfall NetCDF documentation](https://imdpune.gov.in/cmpg/Griddata/Rainfall_25_NetCDF.html) specifies a daily 0.25° product, rainfall in mm, 135×129 grid points, first point 6.5°N/66.5°E, eastward 0.25° increments and last point 38.5°N/100.0°E. It specifies 365/366 records for common/leap years and describes the archive through 2024.

The pipeline checks each file's annual filename/year, rainfall/time/latitude/longitude variables, exactly three time/latitude/longitude data dimensions, units, missing markers, coordinate arrays and native resolution, expected versus actual time records, complete daily date range, duplicate/missing dates, and negative valid rainfall. It calculates missing-value count and valid min/max across all grid cells and days. A mismatch appears in the per-file report; questionable values are not repaired.

## Safe IMD temperature GRD ingestion foundation (2026-09-27)

This section supersedes the earlier local temperature file counts above. A read-only inventory now finds **14 Tmax files** (2010, 2011, 2012, and 2014-2024) and **16 Tmin files** (2010-2025). Tmax 2013 is absent; it is explicitly recorded as a year gap and no record is synthesized. All 30 files match the annual size calculated from the documented 31 x 31 grid, four bytes per value, and 365/366 days. The output is written to the ignored path `data/validation/imd_temperature_grd_validation.json` by:

```text
cd backend
python -m app.services.imd_temperature_pipeline
```

The directory audit reads filenames and file sizes only. The local `data/raw/imd_temperature/IMD-DSP_temp.pdf` is titled “All India Series Monthly and Seasonal Mean Temperature”; it is a statistical table and does not specify the daily GRD encoding/layout. The official [IMD Tmax archive page](https://imdpune.gov.in/cmpg/Griddata/Max_1_Bin.html) documents the daily 1-degree product through 2024, Celsius, 31 x 31 logical centers (7.5-37.5 N, 67.5-97.5 E), four-byte direct-access record width, sequential daily records, leap-day records, and undefined value 99.9. Its examples do not establish byte order, explicitly specify IEEE-754, document header/prefix semantics, or bind raw I/J array order to latitude/longitude. Consequently, those fields remain **UNVERIFIED**. The logical axes ascend, but raw index-to-coordinate mapping is also **UNVERIFIED**. No endian, cell order, date-to-payload mapping, scale factor, or value range has been inferred from plausible-looking bytes.

The expected per-year date interval is reported from the filename and the official sequential annual archive convention only; it is not payload-verified. File-size agreement is structural evidence, not proof of value encoding or absence of all possible compensating layouts. Filename years 2010-2024 fall within the official page's published period, but each file's download/source chain is unverified. Tmin 2025 is outside that period and is marked accordingly. The Tmax/Tmin overlap comprises 2010-2012 and 2014-2024: **14 filename years / 5,114 expected calendar-day slots**. Matching expected annual sizes are reported as structural alignment only. The actual date-level `Tmin <= Tmax` check and missing-value counts are **NOT RUN** because no payload values have been decoded.

Generic coordinate selection uses the existing historical-data nearest-grid helper and preserves 1-degree temperature resolution. For validation only, Dhule (20.90 N, 74.80 E) selects logical grid center 20.5 N, 74.5 E. This is a gridded cell, not a Dhule station observation, and it is not mapped to a raw byte offset. The normalized schema helper supports separate nullable Tmax/Tmin fields and the documented 99.9 sentinel, but it accepts only an already verified value. It is not connected to a file decoder or production extractor.

The reader `read_temperature_grd` checks the file's documented annual size and coordinate coverage, then raises `TemperatureDecodeBlocked` before reading any GRD bytes. No actual temperature values were decoded and no normalized temperature dataset was generated. Validation JSON marks value QC, missing counts, and Tmin/Tmax physical consistency as blocked/not run, records source URL and filename-level provenance status, and reports annual missing-year gaps. To unblock extraction, obtain authoritative confirmation of byte order, exact scalar representation, header/prefix behavior, and raw I/J-to-geographic mapping for these files (or an official sample whose values and indices are tied to the same format). Do not train or combine temperature with rainfall before that verification.

### Actual local files

Thirteen files were read: **2013–2025**, totaling **4,748 daily grid records** (4,383 records in 2013–2024; 365 in 2025). All 13 passed the structural/data checks: expected records match actual; time coordinates cover January 1–December 31 without duplicate or missing dates; coordinate arrays match 129 latitudes (6.5–38.5°N) and 135 longitudes (66.5–100.0°E) at 0.25°; data variable is `RAINFALL` with dimensions `(TIME, LATITUDE, LONGITUDE)`, units `mm`, and missing marker/fill value `-999`. There were no cross-file duplicate dates and no invalid coordinate values.

Across the full local grids and all 13 files, **59,117,427** values were marked missing/non-finite. Valid local values ranged from 0 to approximately 979.145 mm. These whole-grid diagnostics include the 2025 file, whose official provenance is unconfirmed; they should not be represented as validated official-archive statistics.

### Dhule validation example and outputs

For requested Dhule coordinate (20.90°N, 74.80°E), the nearest coordinate from each file's actual arrays is **21.00°N, 74.75°E**, approximately **12.272 km** away. The extracted point series contains 4,383 rows for 2013–2024 and 365 rows for 2025. No missing rainfall values occurred at this selected cell in these local records; the pipeline still preserves any missing marker or non-finite point value as a nullable `rainfall_mm` (blank field in CSV), without interpolation.

The normalized columns are `date`, `latitude`, `longitude`, `rainfall_mm`, `source`, `dataset`, and `grid_resolution`. Outputs are separate from raw files and climatology:

- `data/processed/imd_rainfall_daily_0.25deg.csv` — extracted rows for 2013–2024.
- `data/processed/imd_rainfall_daily_0.25deg_2025_provenance_unverified.csv` — separate 2025 rows.
- `data/validation/imd_rainfall_0.25deg_validation.json` — aggregate report, including requested/selected coordinates, distance and per-file reports.
- `data/validation/imd_rainfall/` — one JSON validation report for each annual input.

The 2025 file's time range, dimensions and encoding match the annual structure, but IMD's published long-period product description ends at 2024. Its report labels it `UNVERIFIED_BEYOND_OFFICIAL_ARCHIVE_END_2024`; it was kept in its own output and is not counted in the official-period extract. Confirm its source/provenance with IMD before merging or describing it as part of the documented long-period archive. No raw files were changed, no temperature values or climate anomalies were calculated, and no climatology files were read by this pipeline.

## Historical rainfall prediction baseline (2026-09-27)

The experimental one-day rainfall baseline was trained only from the validated 2013–2024 daily IMD 0.25° grids. It never reads the unverified 2025 file, temperature records, or monthly climatology. Training reads raw files read-only and requires each annual `PASS` report with `OFFICIAL_RANGE_1901_2024` provenance. A deterministic 8×8 spatial sample gives 64 candidate cells; 12 had complete observed windows and target labels. Across the 64 candidate series there are 280,512 source daily cells, 52,428 supervised rows, and 227,188 candidate rows omitted because of missing windows/labels. No data was imputed. Each supervised row has next-day target date; the first target is 2013-01-15 after a 14-day observed feature window.

Features: selected grid latitude/longitude; rainfall lags 1, 2, 3, and 7 days; 3-, 7-, and 14-day rainfall sums through the forecast origin; target month, day of year, and season. Classifiers are a train-only same-cell/month seasonal occurrence baseline, Logistic Regression, and Random Forest Classifier. Amount regression compares a train-only same-cell/month historical mean and Random Forest Regressor. No XGBoost dependency was added. The chronological target-date partitions are train 2013-01-15–2020-12-31 (34,896 rows), validation 2021-01-01–2022-12-31 (8,760), and test 2023-01-01–2024-12-31 (8,772). The 2024 test scores and validation scores, confusion matrices, sampled coordinates, feature definitions, parameters, and dependency version are recorded in the generated manifest under ignored `data/models/rainfall_baseline/`.

The additive endpoint is `GET /api/v1/weather/rainfall-prediction?lat=<lat>&lon=<lon>&horizon=1`. It selects a 0.25° cell with the existing generic haversine grid selector and returns a clearly labeled **WeatherGPT model prediction**, not an official IMD forecast or warning. The local validated source ends on 2024-12-31, so its newest possible next-day target is 2025-01-01; this endpoint demonstrates historical one-day prediction from the archive and is not a current live forecast. It returns a controlled unavailable error if the model artifact is absent, and does not fill recent missing observations. Model and evaluation details are in [rainfall-prediction-baseline.md](rainfall-prediction-baseline.md). This is an initial sparse spatial experiment, not a validated operational forecasting product.
