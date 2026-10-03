"""Reproducible pooled-location one-day rainfall baseline experiments."""
from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import joblib
import numpy as np
from scipy.io import netcdf_file
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, mean_absolute_error,
                             mean_squared_error, precision_score, r2_score, recall_score,
                             roc_auc_score)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.services.historical_data import GridPoint, select_nearest_grid_point

OFFICIAL_TRAINING_YEARS = tuple(range(2013, 2025))
OFFICIAL_ARCHIVE_END = 2024
RAW_FILE = re.compile(r"^RF25_ind(\d{4})_rfp25\.nc$", re.IGNORECASE)
FEATURE_NAMES = [
    "latitude", "longitude", "rainfall_lag_1", "rainfall_lag_2", "rainfall_lag_3",
    "rainfall_lag_7", "rolling_rainfall_3d", "rolling_rainfall_7d", "rolling_rainfall_14d",
    "month", "day_of_year", "season",
]
TRAIN_START = date(2013, 1, 1)
TRAIN_END = date(2020, 12, 31)
VALIDATION_START = date(2021, 1, 1)
VALIDATION_END = date(2022, 12, 31)
TEST_START = date(2023, 1, 1)
TEST_END = date(2024, 12, 31)
SOURCE = "India Meteorological Department (IMD Pune)"
DATASET = "Daily Gridded Rainfall 0.25 degree"


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _days(year: int) -> int:
    return (date(year + 1, 1, 1) - date(year, 1, 1)).days


def _cf_dates(offsets: np.ndarray, units: Any) -> list[date]:
    if isinstance(units, bytes):
        units = units.decode("ascii")
    match = re.fullmatch(r"\s*days\s+since\s+(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}:\d{2}))?\s*", str(units), re.I)
    if not match:
        raise ValueError(f"Unsupported rainfall CF time units: {units!r}")
    base = datetime.fromisoformat(match.group(1) + ("T" + match.group(2) if match.group(2) else "T00:00:00"))
    return [(base + timedelta(days=float(x))).date() for x in offsets]


@dataclass
class RainfallSupervisedDataset:
    features: np.ndarray
    target_occurrence: np.ndarray
    target_amount: np.ndarray
    prediction_dates: np.ndarray
    latitudes: np.ndarray
    longitudes: np.ndarray
    selected_locations: list[dict[str, float]]
    source_daily_records: int
    omitted_missing_supervised_rows: int


def _read_validated_grid(path: Path, year: int, validation_dir: Path):
    report_path = validation_dir / "imd_rainfall" / f"RF25_ind{year}_rfp25.validation.json"
    if not report_path.is_file():
        raise FileNotFoundError(f"Missing validation report for {year}: {report_path}")
    validation = json.loads(report_path.read_text(encoding="utf-8"))
    if validation.get("status") != "PASS" or validation.get("provenance_status") != "OFFICIAL_RANGE_1901_2024":
        raise ValueError(f"Rainfall file {year} is not marked as validated official-period data")
    with netcdf_file(path, "r", mmap=False) as nc:
        vars_by_lower = {name.casefold(): name for name in nc.variables}
        required = {"rainfall", "latitude", "longitude", "time"}
        if not required.issubset(vars_by_lower):
            raise ValueError(f"{path.name} does not have expected rainfall/time/coordinate variables")
        lat = nc.variables[vars_by_lower["latitude"]][:].copy().astype(np.float64)
        lon = nc.variables[vars_by_lower["longitude"]][:].copy().astype(np.float64)
        time_var = nc.variables[vars_by_lower["time"]]
        dates = _cf_dates(time_var[:].copy().reshape(-1), getattr(time_var, "units", b""))
        rain_var = nc.variables[vars_by_lower["rainfall"]]
        dimensions = tuple(name.casefold() for name in rain_var.dimensions)
        if len(dimensions) != 3 or set(dimensions) != {"time", "latitude", "longitude"}:
            raise ValueError(f"Unexpected rainfall dimensions in {path.name}: {rain_var.dimensions}")
        if _days(year) != len(dates) or dates[0] != date(year, 1, 1) or dates[-1] != date(year, 12, 31):
            raise ValueError(f"Incomplete daily calendar coverage in {path.name}")
        if len(set(dates)) != len(dates):
            raise ValueError(f"Duplicate dates in {path.name}")
        if not np.allclose(lat, np.linspace(6.5, 38.5, 129), atol=1e-6, rtol=0):
            raise ValueError(f"Latitude grid validation failed in {path.name}")
        if not np.allclose(lon, np.linspace(66.5, 100.0, 135), atol=1e-6, rtol=0):
            raise ValueError(f"Longitude grid validation failed in {path.name}")
        attrs = getattr(rain_var, "_attributes", {})
        units = attrs.get("units", b"")
        if isinstance(units, bytes):
            units = units.decode("ascii", errors="replace")
        if units.casefold() != "mm":
            raise ValueError(f"Rainfall units are not mm in {path.name}: {units!r}")
        markers = [float(np.asarray(attrs[key]).reshape(-1)[0]) for key in ("missing_value", "_FillValue") if key in attrs]
        if not markers:
            raise ValueError(f"Missing-value convention absent in {path.name}")
        raw = rain_var[:].copy()
        axes = (dimensions.index("time"), dimensions.index("latitude"), dimensions.index("longitude"))
        grid = np.transpose(raw, axes).astype(np.float32, copy=False)
    for marker in markers:
        grid[np.isclose(grid, marker, atol=1e-6, rtol=0)] = np.nan
    if np.any(np.isfinite(grid) & (grid < 0)):
        raise ValueError(f"Negative rainfall encountered in {path.name}")
    return dates, lat, lon, grid


def _sample_grid_locations(latitudes: np.ndarray, longitudes: np.ndarray, axis_points: int = 8):
    if axis_points < 2:
        raise ValueError("axis_points must be at least 2 to sample locations across the grid")
    lat_indices = np.unique(np.linspace(0, len(latitudes) - 1, axis_points, dtype=int))
    lon_indices = np.unique(np.linspace(0, len(longitudes) - 1, axis_points, dtype=int))
    return [(int(i), int(j), float(latitudes[i]), float(longitudes[j]))
            for i in lat_indices for j in lon_indices]


def supervised_features_for_series(rainfall: np.ndarray, dates: np.ndarray,
                                   latitude: float, longitude: float):
    """Construct next-day rows; every rainfall feature ends before its target."""
    rainfall = np.asarray(rainfall, dtype=np.float32)
    dates = np.asarray(dates, dtype="datetime64[D]")
    if rainfall.ndim != 1 or dates.ndim != 1 or len(rainfall) != len(dates):
        raise ValueError("rainfall and dates must be equally sized one-dimensional series")
    if len(rainfall) < 15:
        return (np.empty((0, len(FEATURE_NAMES)), dtype=np.float32),
                np.empty(0, dtype=np.float32), np.empty(0, dtype="datetime64[D]"))
    origins = np.arange(13, len(rainfall) - 1)
    windows = np.lib.stride_tricks.sliding_window_view(rainfall, 14)[:len(origins)]
    targets = rainfall[origins + 1]
    valid = np.isfinite(windows).all(axis=1) & np.isfinite(targets)
    if not valid.any():
        return (np.empty((0, len(FEATURE_NAMES)), dtype=np.float32),
                np.empty(0, dtype=np.float32), np.empty(0, dtype="datetime64[D]"))
    windows = windows[valid]
    prediction_dates = dates[origins[valid] + 1]
    target_amount = targets[valid]
    months = np.asarray([int(str(d)[5:7]) for d in prediction_dates], dtype=np.int16)
    day_of_year = np.asarray([(date.fromisoformat(str(d)) - date(int(str(d)[:4]), 1, 1)).days + 1
                              for d in prediction_dates], dtype=np.int16)
    seasons = np.select([np.isin(months, [12, 1, 2]), np.isin(months, [3, 4, 5]),
                         np.isin(months, [6, 7, 8, 9])], [0, 1, 2], default=3).astype(np.int8)
    features = np.column_stack([
        np.full(len(windows), latitude), np.full(len(windows), longitude),
        windows[:, -1], windows[:, -2], windows[:, -3], windows[:, -7],
        np.sum(windows[:, -3:], axis=1), np.sum(windows[:, -7:], axis=1), np.sum(windows, axis=1),
        months, day_of_year, seasons,
    ]).astype(np.float32)
    return features, target_amount.astype(np.float32), prediction_dates


def build_location_dataset(raw_dir: str | Path, latitude: float, longitude: float,
                           *, validation_dir: str | Path | None = None,
                           years: Iterable[int] = OFFICIAL_TRAINING_YEARS) -> list[dict[str, Any]]:
    """Build one generic coordinate's validated chronological 2013-2024 series."""
    raw_dir = Path(raw_dir)
    validation_dir = Path(validation_dir) if validation_dir else repository_root() / "data" / "validation"
    result: list[dict[str, Any]] = []
    expected_years = tuple(years)
    for year in expected_years:
        path = raw_dir / f"RF25_ind{year}_rfp25.nc"
        if not path.is_file():
            raise FileNotFoundError(f"Validated training-year file missing: {path.name}")
        dates, lat, lon, grid = _read_validated_grid(path, year, validation_dir)
        if (latitude < lat[0] - 0.125 or latitude > lat[-1] + 0.125
                or longitude < lon[0] - 0.125 or longitude > lon[-1] + 0.125):
            raise ValueError("coordinates fall outside the IMD 0.25-degree rainfall grid coverage")
        point = select_nearest_grid_point(latitude, longitude, ((float(y), float(x)) for y in lat for x in lon))
        lat_i = int(np.abs(lat - point.grid_latitude).argmin())
        lon_i = int(np.abs(lon - point.grid_longitude).argmin())
        for day, value in zip(dates, grid[:, lat_i, lon_i]):
            rainfall = None if not np.isfinite(value) else float(value)
            result.append({"date": day, "latitude": point.grid_latitude, "longitude": point.grid_longitude,
                           "rainfall_mm": rainfall, "source": SOURCE, "dataset": DATASET,
                           "grid_resolution": 0.25, "distance_km": point.distance_km,
                           "requested_latitude": latitude, "requested_longitude": longitude})
    return result


def build_pooled_training_dataset(raw_dir: str | Path, *, validation_dir: str | Path | None = None,
                                  axis_points: int = 8) -> RainfallSupervisedDataset:
    """Build pooled, spatially distributed training data without using 2025."""
    raw_dir = Path(raw_dir)
    validation_dir = Path(validation_dir) if validation_dir else repository_root() / "data" / "validation"
    years = OFFICIAL_TRAINING_YEARS
    first_path = raw_dir / f"RF25_ind{years[0]}_rfp25.nc"
    if not first_path.is_file():
        raise FileNotFoundError(f"Missing IMD rainfall file: {first_path}")
    with netcdf_file(first_path, "r", mmap=False) as nc:
        variables = {n.casefold(): n for n in nc.variables}
        lat = nc.variables[variables["latitude"]][:].copy().astype(np.float64)
        lon = nc.variables[variables["longitude"]][:].copy().astype(np.float64)
    locations = _sample_grid_locations(lat, lon, axis_points)
    all_dates: list[date] = []
    series_by_location: dict[tuple[int, int], list[np.ndarray]] = {(i, j): [] for i, j, _, _ in locations}
    expected_dates: list[date] | None = None
    for year in years:
        path = raw_dir / f"RF25_ind{year}_rfp25.nc"
        dates, grid_lat, grid_lon, grid = _read_validated_grid(path, year, validation_dir)
        if not np.array_equal(grid_lat, lat) or not np.array_equal(grid_lon, lon):
            raise ValueError(f"Grid coordinates changed in {path.name}")
        if expected_dates is not None and dates[0] != expected_dates[-1] + timedelta(days=1):
            raise ValueError(f"Date sequence is discontinuous before {path.name}")
        expected_dates = dates
        all_dates.extend(dates)
        for i, j, _, _ in locations:
            series_by_location[(i, j)].append(grid[:, i, j].copy())
        del grid

    full_dates = np.asarray(all_dates, dtype="datetime64[D]")
    x_parts: list[np.ndarray] = []
    occurrence_parts: list[np.ndarray] = []
    amount_parts: list[np.ndarray] = []
    date_parts: list[np.ndarray] = []
    latitude_parts: list[np.ndarray] = []
    longitude_parts: list[np.ndarray] = []
    active_coordinates: set[tuple[float, float]] = set()
    total_possible = len(locations) * (len(full_dates) - 14)
    for _, _, site_lat, site_lon in locations:
        rainfall = np.concatenate(series_by_location[(int(np.abs(lat-site_lat).argmin()), int(np.abs(lon-site_lon).argmin()))]).astype(np.float32)
        location_features, target_amount, prediction_dates = supervised_features_for_series(
            rainfall, full_dates, site_lat, site_lon)
        if not len(target_amount):
            continue
        active_coordinates.add((site_lat, site_lon))
        x_parts.append(location_features)
        occurrence_parts.append((target_amount > 0).astype(np.int8))
        amount_parts.append(target_amount.astype(np.float32))
        date_parts.append(prediction_dates)
        latitude_parts.append(np.full(len(location_features), site_lat, dtype=np.float32))
        longitude_parts.append(np.full(len(location_features), site_lon, dtype=np.float32))

    if not x_parts:
        raise ValueError("No complete observed rainfall windows are available for the spatial sample")
    selected = [{"latitude": a, "longitude": b} for a, b in sorted(active_coordinates)]
    features = np.concatenate(x_parts)
    target_occurrence = np.concatenate(occurrence_parts)
    target_amount = np.concatenate(amount_parts)
    prediction_dates = np.concatenate(date_parts).astype("datetime64[D]")
    latitudes = np.concatenate(latitude_parts)
    longitudes = np.concatenate(longitude_parts)
    if np.any(prediction_dates > np.datetime64(TEST_END)):
        raise ValueError("Training builder included dates after the documented 2024 archive period")
    return RainfallSupervisedDataset(features, target_occurrence, target_amount, prediction_dates,
        latitudes, longitudes, selected, len(locations) * len(full_dates), total_possible - len(target_amount))


def chronological_split_masks(prediction_dates: np.ndarray) -> dict[str, np.ndarray]:
    dates = prediction_dates.astype("datetime64[D]")
    return {
        "train": (dates >= np.datetime64(TRAIN_START)) & (dates <= np.datetime64(TRAIN_END)),
        "validation": (dates >= np.datetime64(VALIDATION_START)) & (dates <= np.datetime64(VALIDATION_END)),
        "test": (dates >= np.datetime64(TEST_START)) & (dates <= np.datetime64(TEST_END)),
    }


def _baseline_tables(y_occ: np.ndarray, y_amount: np.ndarray, x: np.ndarray,
                     dates: np.ndarray, train_mask: np.ndarray) -> tuple[dict, dict, dict]:
    # Location/month seasonal rates/means use train data only. Unseen grid cells
    # fall back to the corresponding month pooled across sampled training cells.
    occ: dict[tuple[float, float, int], list[float]] = defaultdict(list)
    amount: dict[tuple[float, float, int], list[float]] = defaultdict(list)
    occ_month: dict[int, list[float]] = defaultdict(list)
    amount_month: dict[int, list[float]] = defaultdict(list)
    for idx in np.flatnonzero(train_mask):
        lat_v, lon_v, month = float(x[idx, 0]), float(x[idx, 1]), int(x[idx, 9])
        key = (lat_v, lon_v, month)
        occ[key].append(float(y_occ[idx])); amount[key].append(float(y_amount[idx]))
        occ_month[month].append(float(y_occ[idx])); amount_month[month].append(float(y_amount[idx]))
    occurrence_table = {k: float(np.mean(v)) for k, v in occ.items()}
    amount_table = {k: float(np.mean(v)) for k, v in amount.items()}
    occurrence_fallback = {k: float(np.mean(v)) for k, v in occ_month.items()}
    amount_fallback = {k: float(np.mean(v)) for k, v in amount_month.items()}
    return occurrence_table, amount_table, {"occurrence": occurrence_fallback, "amount": amount_fallback}


def _baseline_predict(x: np.ndarray, occurrence_table: dict, amount_table: dict,
                      fallbacks: dict) -> tuple[np.ndarray, np.ndarray]:
    probabilities, amounts = [], []
    for row in x:
        key = (float(row[0]), float(row[1]), int(row[9]))
        probabilities.append(occurrence_table.get(key, fallbacks["occurrence"].get(key[2], 0.0)))
        amounts.append(amount_table.get(key, fallbacks["amount"].get(key[2], 0.0)))
    return np.asarray(probabilities), np.asarray(amounts)


def classification_metrics(y_true: np.ndarray, probability: np.ndarray) -> dict[str, Any]:
    prediction = (probability >= 0.5).astype(np.int8)
    auc = None
    if len(np.unique(y_true)) == 2:
        auc = float(roc_auc_score(y_true, probability))
    return {"accuracy": float(accuracy_score(y_true, prediction)),
            "precision": float(precision_score(y_true, prediction, zero_division=0)),
            "recall": float(recall_score(y_true, prediction, zero_division=0)),
            "f1": float(f1_score(y_true, prediction, zero_division=0)),
            "roc_auc": auc,
            "confusion_matrix_labels_0_1": confusion_matrix(y_true, prediction, labels=[0, 1]).tolist()}


def regression_metrics(y_true: np.ndarray, prediction: np.ndarray) -> dict[str, float]:
    return {"mae": float(mean_absolute_error(y_true, prediction)),
            "rmse": float(math.sqrt(mean_squared_error(y_true, prediction))),
            "r2": float(r2_score(y_true, prediction))}


def train_rainfall_baselines(*, raw_dir: str | Path | None = None,
                             validation_dir: str | Path | None = None,
                             artifact_dir: str | Path | None = None,
                             axis_points: int = 8) -> dict[str, Any]:
    root = repository_root()
    raw_dir = Path(raw_dir) if raw_dir else root / "data" / "raw" / "imd_rainfall"
    validation_dir = Path(validation_dir) if validation_dir else root / "data" / "validation"
    artifact_dir = Path(artifact_dir) if artifact_dir else root / "data" / "models" / "rainfall_baseline"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    ds = build_pooled_training_dataset(raw_dir, validation_dir=validation_dir, axis_points=axis_points)
    splits = chronological_split_masks(ds.prediction_dates)
    train_mask, val_mask, test_mask = splits["train"], splits["validation"], splits["test"]
    if not train_mask.any() or not val_mask.any() or not test_mask.any():
        raise ValueError("Chronological train/validation/test partitions must all contain records")
    x_train, y_train_occ, y_train_amount = ds.features[train_mask], ds.target_occurrence[train_mask], ds.target_amount[train_mask]

    logistic = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, random_state=42))
    logistic.fit(x_train, y_train_occ)
    classifier = RandomForestClassifier(n_estimators=100, max_depth=16, min_samples_leaf=5,
        max_features="sqrt", n_jobs=-1, random_state=42)
    classifier.fit(x_train, y_train_occ)
    regressor = RandomForestRegressor(n_estimators=100, max_depth=18, min_samples_leaf=5,
        max_features=0.8, n_jobs=-1, random_state=42)
    regressor.fit(x_train, y_train_amount)
    occ_table, amount_table, fallbacks = _baseline_tables(ds.target_occurrence, ds.target_amount,
        ds.features, ds.prediction_dates, train_mask)
    models = {"logistic_regression": logistic, "random_forest_classifier": classifier,
              "random_forest_regressor": regressor, "seasonal_occurrence_table": occ_table,
              "seasonal_amount_table": amount_table, "seasonal_fallbacks": fallbacks}

    metrics: dict[str, Any] = {}
    for split_name, mask in (("validation", val_mask), ("test", test_mask)):
        x, y_occ, y_amount = ds.features[mask], ds.target_occurrence[mask], ds.target_amount[mask]
        base_p, base_amount = _baseline_predict(x, occ_table, amount_table, fallbacks)
        metrics[split_name] = {
            "classification": {
                "seasonal_historical_baseline": classification_metrics(y_occ, base_p),
                "logistic_regression": classification_metrics(y_occ, logistic.predict_proba(x)[:, 1]),
                "random_forest": classification_metrics(y_occ, classifier.predict_proba(x)[:, 1]),
            },
            "regression": {
                "seasonal_historical_baseline": regression_metrics(y_amount, base_amount),
                "random_forest_regressor": regression_metrics(y_amount, regressor.predict(x)),
            },
            "samples": int(mask.sum()),
        }

    joblib.dump(models, artifact_dir / "rainfall_models.joblib", compress=3)
    train_dates = ds.prediction_dates[train_mask]
    manifest = {
        "label": "WeatherGPT model prediction",
        "source": SOURCE, "dataset": DATASET, "source_period": "2013-01-01 to 2024-12-31",
        "training_period": {"start": str(train_dates.min()), "end": str(train_dates.max())},
        "validation_period": {"start": str(ds.prediction_dates[val_mask].min()), "end": str(ds.prediction_dates[val_mask].max())},
        "test_period": {"start": str(ds.prediction_dates[test_mask].min()), "end": str(ds.prediction_dates[test_mask].max())},
        "split_rule": "Chronological by next-day target date; no random split.",
        "feature_definitions": {
            "rainfall_lag_1": "rainfall at forecast origin day (the day before target)",
            "rainfall_lag_2": "rainfall two calendar days before target",
            "rainfall_lag_3": "rainfall three calendar days before target",
            "rainfall_lag_7": "rainfall seven calendar days before target",
            "rolling_rainfall_3d": "sum over forecast origin and prior 2 days",
            "rolling_rainfall_7d": "sum over forecast origin and prior 6 days",
            "rolling_rainfall_14d": "sum over forecast origin and prior 13 days",
            "month": "calendar month of target date", "day_of_year": "ordinal day of target date",
            "season": "India season code: winter=0, pre-monsoon=1, monsoon=2, post-monsoon=3",
            "latitude": "selected native grid-cell latitude", "longitude": "selected native grid-cell longitude",
        },
        "feature_names": FEATURE_NAMES,
        "target_definition": {"rain_tomorrow": "1 if next-day rainfall_mm > 0; else 0", "amount": "next-day rainfall_mm"},
        "data": {"candidate_locations_sampled": axis_points ** 2,
                 "locations_with_supervised_samples": len(ds.selected_locations),
                 "source_daily_records": ds.source_daily_records,
                 "supervised_samples": int(len(ds.features)),
                 "candidate_supervised_rows": int(len(ds.features) + ds.omitted_missing_supervised_rows),
                 "omitted_missing_supervised_rows": ds.omitted_missing_supervised_rows,
                 "warmup_days_per_location": 13,
                 "sampling": f"Deterministic {axis_points}x{axis_points} evenly spaced grid-index sample across the national grid; cells without complete observed windows are excluded.",
                 "selected_grid_coordinates": ds.selected_locations,
                 "excludes_years": [2025], "temperature_inputs": False},
        "model_parameters": {"logistic_regression": {"max_iter": 500, "random_state": 42, "scaled": True},
            "random_forest_classifier": {"n_estimators": 100, "max_depth": 16, "min_samples_leaf": 5,
                "max_features": "sqrt", "random_state": 42},
            "random_forest_regressor": {"n_estimators": 100, "max_depth": 18, "min_samples_leaf": 5,
                "max_features": 0.8, "random_state": 42}},
        "metrics": metrics,
        "artifact_file": "rainfall_models.joblib",
        "sklearn_version": __import__("sklearn").__version__,
    }
    (artifact_dir / "training_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _latest_prediction_features(history: list[dict[str, Any]], latitude: float, longitude: float):
    history = sorted(history, key=lambda row: row["date"])
    if len(history) < 14:
        raise ValueError("At least 14 consecutive rainfall observations are required")
    tail = history[-14:]
    if any(row["rainfall_mm"] is None or not math.isfinite(float(row["rainfall_mm"])) for row in tail):
        raise ValueError("Recent rainfall history contains missing values; prediction cannot be made without imputation")
    dates = [row["date"] for row in tail]
    if any(dates[i] + timedelta(days=1) != dates[i + 1] for i in range(len(dates) - 1)):
        raise ValueError("Recent rainfall history is not daily and continuous")
    prediction_date = dates[-1] + timedelta(days=1)
    values = [float(row["rainfall_mm"]) for row in tail]
    month = prediction_date.month
    season = 0 if month in (12, 1, 2) else 1 if month in (3, 4, 5) else 2 if month in (6, 7, 8, 9) else 3
    x = np.asarray([[latitude, longitude, values[-1], values[-2], values[-3], values[-7],
        sum(values[-3:]), sum(values[-7:]), sum(values[-14:]), month,
        prediction_date.timetuple().tm_yday, season]], dtype=np.float32)
    return x, prediction_date


def predict_next_day(latitude: float, longitude: float, horizon: int = 1, *,
                     artifact_dir: str | Path | None = None, raw_dir: str | Path | None = None,
                     validation_dir: str | Path | None = None) -> dict[str, Any]:
    if horizon != 1:
        raise ValueError("Only horizon=1 day is currently supported")
    root = repository_root()
    artifact_dir = Path(artifact_dir) if artifact_dir else root / "data" / "models" / "rainfall_baseline"
    raw_dir = Path(raw_dir) if raw_dir else root / "data" / "raw" / "imd_rainfall"
    validation_dir = Path(validation_dir) if validation_dir else root / "data" / "validation"
    bundle_path = artifact_dir / "rainfall_models.joblib"
    manifest_path = artifact_dir / "training_manifest.json"
    if not bundle_path.is_file() or not manifest_path.is_file():
        raise FileNotFoundError("Rainfall prediction model has not been trained")
    models = joblib.load(bundle_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    history = build_location_dataset(raw_dir, latitude, longitude, validation_dir=validation_dir)
    point = GridPoint(latitude, longitude, history[-1]["latitude"], history[-1]["longitude"], history[-1]["distance_km"])
    x, prediction_date = _latest_prediction_features(history, point.grid_latitude, point.grid_longitude)
    probability = float(models["random_forest_classifier"].predict_proba(x)[0, 1])
    amount = max(0.0, float(models["random_forest_regressor"].predict(x)[0]))
    return {
        "label": "WeatherGPT model prediction",
        "location": {"latitude": latitude, "longitude": longitude},
        "selected_grid_point": {"latitude": point.grid_latitude, "longitude": point.grid_longitude,
                                "distance_km": point.distance_km},
        "dataset": DATASET,
        "grid_resolution_degrees": 0.25,
        "source": SOURCE,
        "prediction_date": prediction_date,
        "rain_probability": probability,
        "rain_expected": probability >= 0.5,
        "predicted_rainfall_mm": amount,
        "model": "Random Forest occurrence classifier + Random Forest rainfall regressor",
        "training_period": manifest["training_period"],
    }


if __name__ == "__main__":
    print(json.dumps(train_rainfall_baselines(), indent=2))
