from datetime import date, timedelta

import numpy as np
import pytest

from app.schemas.rainfall_prediction import RainfallPredictionResponse
from app.services.historical_data import select_nearest_grid_point
from app.services.rainfall_prediction import (
    TEST_END, TEST_START, VALIDATION_END, VALIDATION_START,
    _latest_prediction_features, chronological_split_masks, supervised_features_for_series,
)
from app.services.rainfall_evaluation import (
    calibration_report, persistence_occurrence, regression_error_distribution,
    permute_recent_rainfall_features,
)


def _history(values):
    start = date(2024, 12, 1)
    return [{"date": start + timedelta(days=i), "rainfall_mm": value} for i, value in enumerate(values)]


def test_feature_row_uses_only_observed_history_and_correct_rolling_sums():
    history = _history(list(range(1, 15)))
    features, target_date = _latest_prediction_features(history, 21.0, 74.75)
    assert target_date == date(2024, 12, 15)
    assert features.shape == (1, 12)
    assert features[0, 2:9].tolist() == [14, 13, 12, 8, 39, 77, 105]
    # Mutating the next-day label cannot affect a feature vector: it is not an input.
    history.append({"date": target_date, "rainfall_mm": 9999.0})
    changed, _ = _latest_prediction_features(history[:-1], 21.0, 74.75)
    np.testing.assert_array_equal(features, changed)


def test_recent_missing_data_is_not_imputed():
    history = _history(list(range(1, 14)) + [None])
    with pytest.raises(ValueError, match="missing values"):
        _latest_prediction_features(history, 21.0, 74.75)


def test_supervised_builder_aligns_feature_window_before_next_day_target():
    rainfall = np.arange(20, dtype=np.float32)
    dates = np.arange(np.datetime64("2020-01-01"), np.datetime64("2020-01-21"), dtype="datetime64[D]")
    features, targets, target_dates = supervised_features_for_series(rainfall, dates, 21.0, 74.75)
    assert target_dates[0] == np.datetime64("2020-01-15")
    assert targets[0] == 14
    assert features[0, 2:9].tolist() == [13, 12, 11, 7, 36, 70, 91]
    changed_rainfall = rainfall.copy()
    changed_rainfall[14] = 999
    changed_features, changed_targets, _ = supervised_features_for_series(changed_rainfall, dates, 21.0, 74.75)
    # Target-day value is not among the first row's predictors.
    np.testing.assert_array_equal(features[0], changed_features[0])
    assert changed_targets[0] == 999
    # Once it is observed, that value may legitimately enter the following day's features.
    assert changed_features[1, 2] == 999


def test_calibration_report_brier_and_reliability_bins():
    report = calibration_report(np.asarray([0, 1, 1, 0]), np.asarray([0.1, 0.8, 0.6, 0.4]), bins=2)
    assert report["brier_score"] == pytest.approx(0.0925)
    assert report["expected_calibration_error"] == pytest.approx(0.275)
    assert report["bins"][0]["count"] == 2
    assert report["bins"][1]["observed_positive_rate"] == 1.0


def test_persistence_uses_only_last_observed_rainfall_and_regression_error_distribution():
    features = np.zeros((3, 12), dtype=np.float32)
    features[:, 2] = [0, 0.1, 4.0]
    assert persistence_occurrence(features).tolist() == [0.0, 1.0, 1.0]
    dist = regression_error_distribution(np.asarray([2, 4, 6]), np.asarray([1, 4, 9]))
    assert dist["mean_error_mm_predicted_minus_observed"] == pytest.approx(2 / 3)
    assert dist["median_absolute_error_mm"] == pytest.approx(1)


def test_rainfall_permutation_keeps_cell_month_and_feature_block_together():
    features = np.zeros((4, 12), dtype=np.float32)
    features[:, 0] = [10, 10, 20, 20]
    features[:, 1] = [70, 70, 80, 80]
    features[:, 9] = [6, 6, 6, 6]
    features[:, 2:9] = np.asarray([[1, 1, 1, 1, 3, 7, 14], [2, 2, 2, 2, 6, 14, 28],
                                   [3, 3, 3, 3, 9, 21, 42], [4, 4, 4, 4, 12, 28, 56]])
    changed = permute_recent_rainfall_features(features, features[:, 0], features[:, 1], np.random.default_rng(4))
    np.testing.assert_array_equal(changed[:, [0, 1, 9]], features[:, [0, 1, 9]])
    for row_indexes in ([0, 1], [2, 3]):
        np.testing.assert_array_equal(np.sort(changed[row_indexes, 2]), np.sort(features[row_indexes, 2]))
        original_blocks = {tuple(row) for row in features[row_indexes, 2:9]}
        assert {tuple(row) for row in changed[row_indexes, 2:9]} == original_blocks


def test_chronological_split_has_disjoint_date_ranges():
    dates = np.asarray(["2020-12-31", "2021-01-01", "2022-12-31", "2023-01-01", "2024-12-31"], dtype="datetime64[D]")
    masks = chronological_split_masks(dates)
    assert dates[masks["train"]].tolist() == [np.datetime64("2020-12-31")]
    assert dates[masks["validation"]].tolist() == [np.datetime64("2021-01-01"), np.datetime64("2022-12-31")]
    assert dates[masks["test"]].tolist() == [np.datetime64("2023-01-01"), np.datetime64("2024-12-31")]
    assert VALIDATION_START == date(2021, 1, 1) and VALIDATION_END == date(2022, 12, 31)
    assert TEST_START == date(2023, 1, 1) and TEST_END == date(2024, 12, 31)


@pytest.mark.parametrize("coordinate, expected", [
    ((20.9, 74.8), (21.0, 74.75)),
    ((28.6, 77.2), (28.5, 77.25)),
    ((12.97, 77.59), (13.0, 77.5)),
])
def test_generic_nearest_grid_selection(coordinate, expected):
    result = select_nearest_grid_point(*coordinate, [(21.0, 74.75), (28.5, 77.25), (13.0, 77.5)])
    assert (result.grid_latitude, result.grid_longitude) == expected
    assert result.distance_km > 0
    assert (result.requested_latitude, result.requested_longitude) == coordinate


def test_prediction_response_schema_and_model_label():
    response = RainfallPredictionResponse.model_validate({
        "label": "WeatherGPT model prediction",
        "location": {"latitude": 19.0, "longitude": 73.0},
        "selected_grid_point": {"latitude": 19.0, "longitude": 73.0, "distance_km": 0.0},
        "prediction_date": "2025-01-01", "rain_probability": 0.2,
        "rain_expected": False, "predicted_rainfall_mm": 0.1,
        "model": "Random Forest", "training_period": {"start": "2013-01-15", "end": "2020-12-31"},
    })
    assert response.label == "WeatherGPT model prediction"
    assert response.prediction_date == date(2025, 1, 1)
    with pytest.raises(ValueError):
        RainfallPredictionResponse.model_validate({**response.model_dump(), "rain_probability": 1.1})


@pytest.mark.anyio
async def test_prediction_api_returns_generic_model_response(client, monkeypatch):
    from app.services import rainfall_prediction

    monkeypatch.setattr(rainfall_prediction, "predict_next_day", lambda lat, lon, horizon: {
        "label": "WeatherGPT model prediction",
        "location": {"latitude": lat, "longitude": lon},
        "selected_grid_point": {"latitude": 19.0, "longitude": 73.0, "distance_km": 17.2},
        "prediction_date": "2025-01-01", "rain_probability": 0.4,
        "rain_expected": False, "predicted_rainfall_mm": 0.8,
        "model": "Random Forest", "training_period": {"start": "2013-01-15", "end": "2020-12-31"},
    })
    response = await client.get("/api/v1/weather/rainfall-prediction?lat=19&lon=73&horizon=1")
    assert response.status_code == 200
    assert response.json()["location"] == {"latitude": 19.0, "longitude": 73.0}
    assert response.json()["label"] == "WeatherGPT model prediction"


@pytest.mark.anyio
async def test_prediction_api_rejects_unsupported_horizon(client):
    response = await client.get("/api/v1/weather/rainfall-prediction?lat=19&lon=73&horizon=2")
    assert response.status_code == 422
