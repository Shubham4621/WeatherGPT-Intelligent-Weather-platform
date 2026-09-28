# WeatherGPT Rainfall Prediction Baseline

## Purpose and status

This is an experimental one-day **WeatherGPT model prediction** using validated IMD Pune daily 0.25-degree rainfall observations. It is not an official IMD forecast or warning. It does not replace the existing live forecast, alert, advisory, or chat systems. No prediction model is trained at application startup.

## Data and location handling

- Training input: `data/raw/imd_rainfall/RF25_indYYYY_rfp25.nc`, years 2013–2024 only, gated by each year's PASS validation report and official-period provenance marker.
- Excluded: the unverified 2025 rainfall file, all temperature data, and monthly climatology data.
- Native grid: 0.25 degree. A deterministic 8-by-8 spatial sample (64 candidate grid cells) is taken across the documented grid. Cells with incomplete 14-day histories or missing next-day labels are omitted; no values are filled. The initial fit used 12 sampled cells with valid supervised records.
- User location is latitude/longitude. The existing haversine nearest-grid selector chooses its rainfall cell; no Dhule-specific code or geocoder is used.
- Source dates: 2013-01-01 through 2024-12-31. Daily supervised labels begin 2013-01-15 because 14 prior observed days are required.

## Targets and features

Classification target: `rain_tomorrow = 1` when next-day rainfall is greater than 0 mm, otherwise 0. Amount target: next-day rainfall in mm.

Features are latitude, longitude, rainfall lags 1/2/3/7 days before the target, 3/7/14-day rainfall sums ending on the forecast-origin day, and target-date month, day of year, and season code. All rainfall windows end at the day before the target. A window with any missing observation or a missing target is excluded. No future rainfall is used as a feature.

## Models and chronological evaluation

Date partitions are based on target date:

| Partition | Dates |
|---|---|
| Train | 2013-01-15 to 2020-12-31 |
| Validation | 2021-01-01 to 2022-12-31 |
| Test | 2023-01-01 to 2024-12-31 |

Classification comparisons: train-only grid-cell/month historical occurrence rate, Logistic Regression, and Random Forest Classifier. Regression comparisons: train-only grid-cell/month historical amount mean and Random Forest Regressor. The historical tables use a training-only pooled month fallback for unseen grid points. Random Forest models use 100 trees and fixed seed 42; other parameters and all metrics are recorded in `data/models/rainfall_baseline/training_manifest.json`.

The run used 52,428 supervised rows total: 34,896 train, 8,760 validation, and 8,772 test rows. Its test results are:

| Task/model | Accuracy | Precision | Recall | F1 | ROC-AUC | MAE (mm) | RMSE (mm) | R² |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Occurrence seasonal historical baseline | 0.7925 | 0.6939 | 0.6137 | 0.6513 | 0.8392 | — | — | — |
| Occurrence Logistic Regression | 0.7762 | 0.7973 | 0.3906 | 0.5244 | 0.8190 | — | — | — |
| Occurrence Random Forest | 0.8234 | 0.7503 | 0.6606 | 0.7026 | 0.8815 | — | — | — |
| Amount seasonal historical baseline | — | — | — | — | — | 4.1057 | 9.1693 | 0.1376 |
| Amount Random Forest Regressor | — | — | — | — | — | 3.6852 | 8.7266 | 0.2188 |

Confusion matrices, validation metrics, exact coordinates, full precision values, parameters, and library version are in the ignored generated manifest. Scores summarize this spatial sample and are not evidence of calibrated city-level operational forecasts.

## Artifacts and API

Training command from `backend/`: `python -m app.services.rainfall_prediction`. Artifacts are stored under ignored `data/models/rainfall_baseline/` (`rainfall_models.joblib` and `training_manifest.json`); do not commit fitted artifacts unless repository policy is intentionally changed.

`GET /api/v1/weather/rainfall-prediction?lat=<latitude>&lon=<longitude>&horizon=1` returns the requested coordinate, selected rainfall grid point and distance, target date, occurrence probability/threshold decision, amount estimate, model name, and training period. Other horizons are unsupported. The local official-range files end on 2024-12-31, so with this dataset the newest possible target is 2025-01-01; this is a historical-baseline demonstration, not a current forecast. Missing model/data returns a controlled unavailable error; missing recent rainfall is not imputed.

## Limitations and next validation

The deterministic spatial sample is sparse (64 candidates, 12 with usable supervised samples); broad grid-cell coverage and spatial generalization need further evaluation. Rainfall observations alone provide no atmospheric predictors, and the 2024 test period is a single chronological holdout. No temperature predictors, 2025 observations, climatology, station observations, XGBoost, LSTM, or GRU were used. Before operational use, obtain wider validated training coverage, test spatial holdouts and probability calibration, compare with station records, and acquire newer verified observations. This work does not claim an official forecast capability.

## Holdout audit and expanded evaluation (2026-09-27)

Evaluation command from `backend/`: `python -m app.services.rainfall_evaluation`. It reloads the saved models, rebuilds the same validated 2013–2024 supervised rows, and evaluates without refitting. Detailed precision metrics and all grouped rows are saved locally to ignored `data/models/rainfall_baseline/evaluation_report.json`.

### Leakage and split checks

The feature builder uses a 14-day window ending at origin day `t`; `rainfall_lag_1` is rainfall on `t`, and target rainfall is at `t+1`. Rolling sums end at `t`. Mutating the target-day value does not change that row's features; the value can enter a later row once it becomes observed. Target-date month/day-of-year/season are calendar-known fields. The chronological target-date masks are mutually exclusive and exhaustive for supervised rows: train 2013-01-15–2020-12-31, validation 2021-01-01–2022-12-31, test 2023-01-01–2024-12-31. Classifiers, regressor, and seasonal tables are fitted on train rows only; the saved models were not refitted in this audit. Earlier rainfall may be used as history for later dates across a split boundary, as it would be observed at prediction time. This is a temporal holdout, not a spatial holdout.

### Class balance and test calibration

| Split | Rows | Rain tomorrow = 1 | Positive rate |
|---|---:|---:|---:|
| Train | 34,896 | 10,642 | 30.50% |
| Validation | 8,760 | 2,837 | 32.39% |
| Test | 8,772 | 2,770 | 31.58% |

Test-set Brier score (lower is better) and ten equal-width-bin expected calibration error (ECE) are:

| Probability source | Brier | ECE |
|---|---:|---:|
| Seasonal historical baseline | 0.14683 | 0.03848 |
| Logistic Regression | 0.15592 | 0.04866 |
| Random Forest classifier | 0.12489 | 0.01456 |
| Persistence (probability 0/1) | 0.18194 | 0.18194 |

Random Forest reliability bins show mean predicted probability against observed positive fraction:

| Probability bin | Rows | Mean predicted | Observed positive rate |
|---|---:|---:|---:|
| 0.0–0.1 | 3,662 | 0.038 | 0.048 |
| 0.1–0.2 | 902 | 0.142 | 0.159 |
| 0.2–0.3 | 623 | 0.250 | 0.271 |
| 0.3–0.4 | 577 | 0.348 | 0.354 |
| 0.4–0.5 | 569 | 0.449 | 0.438 |
| 0.5–0.6 | 541 | 0.548 | 0.540 |
| 0.6–0.7 | 495 | 0.651 | 0.721 |
| 0.7–0.8 | 521 | 0.750 | 0.777 |
| 0.8–0.9 | 588 | 0.848 | 0.852 |
| 0.9–1.0 | 294 | 0.935 | 0.935 |

These are empirical bins on this holdout; they do not establish calibration for another period or location. No plot was added because the numerical reliability table is directly reproducible and avoids introducing a plotting dependency.

### Persistence baseline

Persistence predicts rain tomorrow iff the last observed day (`rainfall_lag_1`) had rain. On the 8,772-row test set: accuracy 0.8181, precision 0.7119, recall 0.7119, F1 0.7119, ROC-AUC 0.7895, Brier 0.18194; confusion matrix `[[5204, 798], [798, 1972]]`.

### Random Forest test performance by season and year

Classification columns are accuracy, precision, recall, F1, and ROC-AUC. Regression columns are Random Forest regressor MAE/RMSE in mm and R². Rain-day percentage is shown to give each group context.

| Group | Rows | Rain % | Accuracy | Precision | Recall | F1 | ROC-AUC | MAE mm | RMSE mm | R² |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Winter (Dec–Feb) | 2,172 | 9.90 | 0.920 | 0.678 | 0.372 | 0.480 | 0.832 | 1.154 | 4.311 | 0.083 |
| Pre-monsoon (Mar–May) | 2,208 | 25.00 | 0.812 | 0.728 | 0.393 | 0.511 | 0.816 | 2.360 | 5.476 | 0.251 |
| Monsoon (Jun–Sep) | 2,928 | 59.87 | 0.734 | 0.767 | 0.798 | 0.782 | 0.794 | 7.106 | 12.796 | 0.164 |
| Post-monsoon (Oct–Nov) | 1,464 | 17.08 | 0.877 | 0.677 | 0.536 | 0.598 | 0.872 | 2.598 | 7.485 | 0.144 |
| 2023 | 4,380 | 32.31 | 0.823 | 0.770 | 0.642 | 0.701 | 0.879 | 3.608 | 8.329 | 0.230 |
| 2024 | 4,392 | 30.85 | 0.824 | 0.732 | 0.680 | 0.705 | 0.884 | 3.762 | 9.106 | 0.209 |

### Regression error distribution and seasonal comparison

For the test set, Random Forest prediction-minus-observation error has mean +0.422 mm, median +0.354 mm, standard deviation 8.716 mm; absolute-error median 1.018 mm, 90th percentile 9.470 mm, 95th percentile 16.027 mm, maximum 181.999 mm. Seasonal amount results, including the training-only seasonal baseline:

| Season | Rows | Baseline MAE | Baseline RMSE | Baseline R² | RF MAE | RF RMSE | RF R² | RF mean error | RF abs error p90 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Winter | 2,172 | 1.096 | 4.339 | 0.071 | 1.154 | 4.311 | 0.083 | +0.221 | 2.871 |
| Pre-monsoon | 2,208 | 2.447 | 5.713 | 0.185 | 2.360 | 5.476 | 0.251 | +0.417 | 5.841 |
| Monsoon | 2,928 | 8.186 | 13.579 | 0.059 | 7.106 | 12.796 | 0.164 | +0.581 | 16.294 |
| Post-monsoon | 1,464 | 2.911 | 7.606 | 0.116 | 2.598 | 7.485 | 0.144 | +0.409 | 6.679 |

### Per-grid-cell test metrics

All rows below are the 2023–2024 holdout; they report each usable sampled cell without choosing or ranking a city. RF classification columns are accuracy, precision, recall, F1, and ROC-AUC. RF amount columns are MAE/RMSE in mm and R².

| Grid cell (lat, lon) | Rows | Rain % | Accuracy | Precision | Recall | F1 | ROC-AUC | MAE mm | RMSE mm | R² |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 11.00, 76.00 | 731 | 47.7 | 0.825 | 0.851 | 0.768 | 0.807 | 0.903 | 7.201 | 15.056 | 0.164 |
| 15.50, 76.00 | 731 | 30.8 | 0.777 | 0.670 | 0.542 | 0.600 | 0.861 | 2.430 | 5.369 | 0.018 |
| 20.00, 76.00 | 731 | 31.5 | 0.866 | 0.827 | 0.726 | 0.773 | 0.915 | 2.671 | 6.209 | 0.125 |
| 20.00, 80.75 | 731 | 30.6 | 0.845 | 0.773 | 0.701 | 0.735 | 0.903 | 4.145 | 11.250 | 0.292 |
| 20.00, 85.50 | 731 | 31.1 | 0.806 | 0.720 | 0.612 | 0.662 | 0.853 | 4.150 | 9.324 | 0.113 |
| 24.75, 71.25 | 731 | 14.4 | 0.893 | 0.671 | 0.505 | 0.576 | 0.866 | 2.267 | 8.423 | 0.189 |
| 24.75, 76.00 | 731 | 25.2 | 0.855 | 0.753 | 0.630 | 0.686 | 0.898 | 2.841 | 6.855 | 0.156 |
| 24.75, 80.75 | 731 | 25.0 | 0.839 | 0.727 | 0.568 | 0.638 | 0.844 | 2.718 | 5.746 | 0.217 |
| 24.75, 85.50 | 731 | 24.2 | 0.848 | 0.712 | 0.627 | 0.667 | 0.880 | 3.107 | 6.841 | 0.138 |
| 29.25, 76.00 | 731 | 15.7 | 0.837 | 0.473 | 0.304 | 0.370 | 0.779 | 1.558 | 3.643 | -0.101 |
| 29.25, 95.00 | 731 | 59.2 | 0.782 | 0.806 | 0.834 | 0.820 | 0.858 | 7.940 | 12.646 | 0.208 |
| 33.75, 76.00 | 731 | 43.5 | 0.707 | 0.679 | 0.619 | 0.648 | 0.775 | 3.195 | 5.945 | 0.125 |

The observed test-cell metric ranges are accuracy 0.707–0.893, recall 0.304–0.834, ROC-AUC 0.775–0.915, and regression R² -0.101–0.292. The per-cell values demonstrate spatial variation in this sample; they do not establish a location ranking or unseen-location performance.

### Dependence on recent rainfall features

The Random Forest classifier's impurity importance values sum to 0.856 across the seven recent-rainfall lag/rolling features; these overlapping features make individual impurity importances unsuitable as independent attributions. A separate 10-repeat grouped permutation shuffled all seven rainfall features together within each grid-cell/target-month stratum. Test ROC-AUC changed from 0.8815 to 0.8146 ± 0.0023; Brier score from 0.1249 to 0.1631 ± 0.0011; Random Forest regression MAE from 3.6852 to 4.2940 ± 0.0298 mm. The sensitivity indicates the model uses recent rainfall information; the size alone does not define whether dependence is excessive. Permutation results are diagnostic and not causal.

No API, frontend, raw file, model fitting, or model artifact was changed by this evaluation. The existing API remains labeled **WeatherGPT model prediction**, not an official IMD forecast. Sparse spatial sampling, rainfall-only inputs, overlapping lag/rolling features, a two-year test window, absent spatial holdout/station comparison, and the 2024 archive end remain material limitations.
