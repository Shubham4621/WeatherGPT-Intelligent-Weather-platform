"""Holdout evaluation for the existing rainfall baseline; does not refit models."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.metrics import brier_score_loss, mean_absolute_error

from app.services.rainfall_prediction import (
    TEST_END, TEST_START, _baseline_predict, build_pooled_training_dataset,
    classification_metrics, chronological_split_masks, regression_metrics,
    repository_root,
)

SEASONS = {0: "winter", 1: "pre_monsoon", 2: "monsoon", 3: "post_monsoon"}
RAIN_FEATURE_INDICES = np.arange(2, 9)


def calibration_report(y_true: np.ndarray, probabilities: np.ndarray, bins: int = 10) -> dict[str, Any]:
    """Brier score, equal-width reliability table, and weighted calibration gap."""
    y_true = np.asarray(y_true, dtype=np.int8)
    probabilities = np.asarray(probabilities, dtype=np.float64)
    if y_true.ndim != 1 or probabilities.shape != y_true.shape or not len(y_true):
        raise ValueError("calibration inputs must be non-empty one-dimensional arrays of equal length")
    if not np.isfinite(probabilities).all() or np.any((probabilities < 0) | (probabilities > 1)):
        raise ValueError("probabilities must be finite values in [0, 1]")
    if bins < 1:
        raise ValueError("bins must be positive")
    edges = np.linspace(0.0, 1.0, bins + 1)
    bin_ids = np.minimum((probabilities * bins).astype(int), bins - 1)
    reliability = []
    ece = 0.0
    for index in range(bins):
        selected = bin_ids == index
        count = int(selected.sum())
        mean_probability = float(probabilities[selected].mean()) if count else None
        observed_rate = float(y_true[selected].mean()) if count else None
        if count:
            ece += count / len(y_true) * abs(mean_probability - observed_rate)
        reliability.append({"bin_lower": float(edges[index]), "bin_upper": float(edges[index + 1]),
                            "count": count, "mean_probability": mean_probability,
                            "observed_positive_rate": observed_rate})
    return {"brier_score": float(brier_score_loss(y_true, probabilities)),
            "expected_calibration_error": float(ece), "bins": reliability}


def persistence_occurrence(features: np.ndarray) -> np.ndarray:
    """Predict wet tomorrow iff rainfall at the last observed day was wet."""
    features = np.asarray(features)
    if features.ndim != 2 or features.shape[1] < 3:
        raise ValueError("features must include rainfall_lag_1 at column 2")
    return (features[:, 2] > 0).astype(np.float64)


def permute_recent_rainfall_features(features: np.ndarray, latitudes: np.ndarray,
                                     longitudes: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Shuffle the complete recent-rainfall feature block within cell/month strata."""
    result = np.asarray(features).copy()
    latitudes, longitudes = np.asarray(latitudes), np.asarray(longitudes)
    if result.ndim != 2 or len(result) != len(latitudes) or len(result) != len(longitudes):
        raise ValueError("feature rows and coordinate arrays must have matching lengths")
    strata: dict[tuple[float, float, int], list[int]] = {}
    for index, (latitude, longitude, month) in enumerate(zip(latitudes, longitudes, result[:, 9].astype(int))):
        strata.setdefault((float(latitude), float(longitude), int(month)), []).append(index)
    for indices in strata.values():
        if len(indices) > 1:
            indices_array = np.asarray(indices)
            source_rows = indices_array[rng.permutation(len(indices_array))]
            result[np.ix_(indices_array, RAIN_FEATURE_INDICES)] = result[np.ix_(source_rows, RAIN_FEATURE_INDICES)]
    return result


def regression_error_distribution(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    errors = np.asarray(predicted, dtype=np.float64) - np.asarray(actual, dtype=np.float64)
    absolute = np.abs(errors)
    if not len(errors) or not np.isfinite(errors).all():
        raise ValueError("regression errors must be non-empty and finite")
    return {"mean_error_mm_predicted_minus_observed": float(errors.mean()),
            "median_error_mm_predicted_minus_observed": float(np.median(errors)),
            "error_std_mm": float(errors.std()),
            "median_absolute_error_mm": float(np.median(absolute)),
            "p90_absolute_error_mm": float(np.quantile(absolute, .90)),
            "p95_absolute_error_mm": float(np.quantile(absolute, .95)),
            "max_absolute_error_mm": float(absolute.max())}


def _group_metrics(indices: np.ndarray, y_occ: np.ndarray, y_amount: np.ndarray,
                   probabilities: dict[str, np.ndarray], predictions: dict[str, np.ndarray]) -> dict[str, Any]:
    if not len(indices):
        return {"samples": 0}
    grouped_p = {name: classification_metrics(y_occ[indices], p[indices]) for name, p in probabilities.items()}
    grouped_reg = {name: {**regression_metrics(y_amount[indices], p[indices]),
                          **regression_error_distribution(y_amount[indices], p[indices])}
                   for name, p in predictions.items()}
    return {"samples": int(len(indices)),
            "positive_rain_count": int(y_occ[indices].sum()),
            "positive_rain_percent": float(y_occ[indices].mean() * 100),
            "classification": grouped_p, "regression": grouped_reg}


def _mean_std(values: list[float]) -> dict[str, float]:
    return {"mean": float(np.mean(values)), "std": float(np.std(values))}


def evaluate_existing_rainfall_models(*, artifact_dir: str | Path | None = None,
                                      raw_dir: str | Path | None = None,
                                      validation_dir: str | Path | None = None,
                                      permutation_repeats: int = 10) -> dict[str, Any]:
    """Rebuild the supervised rows and evaluate saved models on existing holdouts only."""
    root = repository_root()
    artifact_dir = Path(artifact_dir) if artifact_dir else root / "data" / "models" / "rainfall_baseline"
    raw_dir = Path(raw_dir) if raw_dir else root / "data" / "raw" / "imd_rainfall"
    validation_dir = Path(validation_dir) if validation_dir else root / "data" / "validation"
    models = joblib.load(artifact_dir / "rainfall_models.joblib")
    ds = build_pooled_training_dataset(raw_dir, validation_dir=validation_dir, axis_points=8)
    masks = chronological_split_masks(ds.prediction_dates)
    if np.any(np.sum(np.column_stack(list(masks.values())), axis=1) != 1):
        raise ValueError("chronological partitions overlap or leave target dates unassigned")
    for name, mask in masks.items():
        if mask.any():
            group_dates = ds.prediction_dates[mask]
            if name == "train" and (group_dates.min() < np.datetime64("2013-01-01") or group_dates.max() > np.datetime64("2020-12-31")):
                raise ValueError("train target date fell outside the documented partition")
            if name == "validation" and (group_dates.min() < np.datetime64("2021-01-01") or group_dates.max() > np.datetime64("2022-12-31")):
                raise ValueError("validation target date fell outside the documented partition")
            if name == "test" and (group_dates.min() < np.datetime64(TEST_START) or group_dates.max() > np.datetime64(TEST_END)):
                raise ValueError("test target date fell outside the documented partition")

    train_mask, validation_mask, test_mask = masks["train"], masks["validation"], masks["test"]
    x_test, y_test, amount_test = ds.features[test_mask], ds.target_occurrence[test_mask], ds.target_amount[test_mask]
    test_dates = ds.prediction_dates[test_mask]
    baseline_p, baseline_amount = _baseline_predict(ds.features, models["seasonal_occurrence_table"],
        models["seasonal_amount_table"], models["seasonal_fallbacks"])
    all_probabilities = {
        "seasonal_historical_baseline": baseline_p[test_mask],
        "logistic_regression": models["logistic_regression"].predict_proba(x_test)[:, 1],
        "random_forest": models["random_forest_classifier"].predict_proba(x_test)[:, 1],
        "persistence_wet_if_today_wet": persistence_occurrence(x_test),
    }
    all_amount_predictions = {
        "seasonal_historical_baseline": baseline_amount[test_mask],
        "random_forest_regressor": models["random_forest_regressor"].predict(x_test),
    }
    positive_balance = {
        name: {"samples": int(mask.sum()), "positive_rain_days": int(ds.target_occurrence[mask].sum()),
               "positive_rain_percent": float(ds.target_occurrence[mask].mean() * 100)}
        for name, mask in masks.items()
    }
    grouped: dict[str, dict[str, Any]] = {"season": {}, "year": {}, "grid_cell": {}}
    test_rows = np.flatnonzero(test_mask)
    month_test = x_test[:, 9].astype(int)
    season_for_month = np.select([np.isin(month_test, [12, 1, 2]), np.isin(month_test, [3, 4, 5]),
                                  np.isin(month_test, [6, 7, 8, 9])], [0, 1, 2], default=3)
    for season, name in SEASONS.items():
        grouped["season"][name] = _group_metrics(np.flatnonzero(season_for_month == season), y_test,
            amount_test, all_probabilities, all_amount_predictions)
    years = test_dates.astype("datetime64[Y]").astype(int) + 1970
    for year in sorted(np.unique(years)):
        grouped["year"][str(int(year))] = _group_metrics(np.flatnonzero(years == year), y_test,
            amount_test, all_probabilities, all_amount_predictions)
    cells = sorted(set(zip(ds.latitudes[test_mask].tolist(), ds.longitudes[test_mask].tolist())))
    for latitude, longitude in cells:
        local = (ds.latitudes[test_mask] == latitude) & (ds.longitudes[test_mask] == longitude)
        key = f"{latitude:.2f},{longitude:.2f}"
        grouped["grid_cell"][key] = _group_metrics(np.flatnonzero(local), y_test, amount_test,
            all_probabilities, all_amount_predictions)

    calibration = {name: calibration_report(y_test, probability) for name, probability in all_probabilities.items()}
    rf_probability = all_probabilities["random_forest"]
    rng = np.random.default_rng(42)
    permuted_auc, permuted_brier, permuted_mae = [], [], []
    rf_auc = classification_metrics(y_test, rf_probability)["roc_auc"]
    rf_brier = calibration["random_forest"]["brier_score"]
    rf_amount = all_amount_predictions["random_forest_regressor"]
    rf_mae = regression_metrics(amount_test, rf_amount)["mae"]
    for _ in range(permutation_repeats):
        shuffled = permute_recent_rainfall_features(x_test, ds.latitudes[test_mask],
            ds.longitudes[test_mask], rng)
        p = models["random_forest_classifier"].predict_proba(shuffled)[:, 1]
        amount_prediction = models["random_forest_regressor"].predict(shuffled)
        permuted_auc.append(float(classification_metrics(y_test, p)["roc_auc"]))
        permuted_brier.append(float(brier_score_loss(y_test, p)))
        permuted_mae.append(float(mean_absolute_error(amount_test, amount_prediction)))
    feature_importance = {name: float(value) for name, value in zip(
        __import__("app.services.rainfall_prediction", fromlist=["FEATURE_NAMES"]).FEATURE_NAMES,
        models["random_forest_classifier"].feature_importances_)}
    report = {
        "label": "WeatherGPT model evaluation; not an official forecast",
        "source_period": "2013-01-01 to 2024-12-31; 2025 excluded",
        "target_date_partitions": {"train": ["2013-01-15", "2020-12-31"],
            "validation": ["2021-01-01", "2022-12-31"], "test": ["2023-01-01", "2024-12-31"]},
        "leakage_audit": {"features_end_on_forecast_origin": True,
            "target_is_next_calendar_day": True, "future_rainfall_features": False,
            "models_and_seasonal_tables_fit_on_train_only": True,
            "partitions_disjoint_and_exhaustive_for_supervised_targets": True,
            "calendar_features_refer_to_target_date": True},
        "class_balance": positive_balance,
        "test_classification": {name: {**classification_metrics(y_test, probability),
            "brier_score": calibration[name]["brier_score"]} for name, probability in all_probabilities.items()},
        "calibration": calibration,
        "test_regression": {name: {**regression_metrics(amount_test, prediction),
            **regression_error_distribution(amount_test, prediction)}
            for name, prediction in all_amount_predictions.items()},
        "grouped_test_metrics": grouped,
        "rainfall_feature_dependence": {
            "rainfall_feature_names": ["rainfall_lag_1", "rainfall_lag_2", "rainfall_lag_3",
                "rainfall_lag_7", "rolling_rainfall_3d", "rolling_rainfall_7d", "rolling_rainfall_14d"],
            "permutation_repeats": permutation_repeats,
            "classifier_baseline_roc_auc": float(rf_auc),
            "classifier_baseline_brier_score": float(rf_brier),
            "classifier_roc_auc_after_group_permutation": _mean_std(permuted_auc),
            "classifier_brier_after_group_permutation": _mean_std(permuted_brier),
            "regressor_baseline_mae_mm": float(rf_mae),
            "regressor_mae_after_group_permutation_mm": _mean_std(permuted_mae),
            "random_forest_classifier_impurity_importance": feature_importance,
            "permutation_stratification": "Recent-rainfall feature blocks were shuffled within selected grid cell and target month, preserving each stratum's marginal distribution and feature-block relationships.",
            "interpretation": "Permutation is a diagnostic sensitivity test, not a causal or operational validity test. Lag and rolling-sum features overlap, so impurity importance is not an independent causal attribution."},
        "note": "All reported grouped metrics use the chronological 2023-2024 test holdout; no model was refit during evaluation.",
    }
    return report


if __name__ == "__main__":
    result = evaluate_existing_rainfall_models()
    output = repository_root() / "data" / "models" / "rainfall_baseline" / "evaluation_report.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report_file": str(output), "class_balance": result["class_balance"],
                      "test_classification": result["test_classification"],
                      "test_regression": result["test_regression"]}, indent=2))
