from __future__ import annotations

import pickle
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from domain.day_type import (
    days_since_holiday,
    days_until_holiday,
    is_post_holiday,
    resolve_day_type,
)
from domain.forecast_router import is_weekday_target
from infrastructure.config import ml_inference_mode_fast
from domain.operation_period import (
    SPECIAL_COMMUNICATION_PERIOD_TYPES,
    no_parcel_period_features,
    apply_operation_period_volume_adjustment,
    classify_forecast_period_category,
    get_operation_periods_for_date,
)
from domain.volume_forecast import (
    DAY_TYPE_LABELS,
    WEEKDAY_LABELS,
    _format_forecast_volume_lead,
    apply_post_holiday_adjustment,
    forecast_national_volume,
    forecast_target_note_for,
    format_forecast_adjustment_suffix,
    resolve_forecast_target_date,
)

FEATURE_NAMES = [
    "target_weekday",
    "target_month",
    "prev_day_volume",
    "avg_7d",
    "avg_30d",
    "national_volume",
    "is_holiday",
    "special_communication",
    "lag_same_weekday_1w",
    "lag_same_weekday_2w",
    "lag_same_weekday_4w",
    "rolling_same_weekday_4w",
    "days_since_last_report",
    "national_volume_ratio",
    "post_shopping_discount",
    "special_communication_period",
    "no_parcel_day_index",
    "days_until_period_end",
    "is_post_holiday",
    "days_since_holiday",
    "days_until_holiday",
]

MIN_TRAINING_SAMPLES = 30
HOLDOUT_RATIO = 0.2
BIAS_WINDOW = 14
DEFAULT_ML_BLEND_WEIGHT = 0.45
BLEND_WEIGHT_CANDIDATES = (0.2, 0.35, 0.45, 0.5, 0.6)
NORMAL_SAMPLE_WEIGHT = 1.0
SPECIAL_SAMPLE_WEIGHT = 0.5
NO_PARCEL_SAMPLE_WEIGHT = 0.3

MODEL_LABELS = {
    "linear_regression": "Linear Regression",
    "random_forest": "Random Forest",
    "gradient_boosting": "Gradient Boosting",
    "lightgbm": "LightGBM",
}


@dataclass(frozen=True)
class VolumeMlRow:
    report_date: date
    total_volume: int | None
    national_volume: int | None
    remaining_volume: int | None
    day_type: str | None
    report_format: str | None


@dataclass(frozen=True)
class ModelMetric:
    model_key: str
    model_label: str
    mae: float
    mape: float


@dataclass(frozen=True)
class VolumeMlForecastResult:
    report_date: str
    target_date: str
    target_weekday_label: str
    target_day_type: str
    forecast_target_note: str | None
    forecast_volume: float
    best_model_key: str
    best_model_label: str
    training_samples: int
    model_metrics: tuple[ModelMetric, ...]
    feature_names: tuple[str, ...]
    operation_period_labels: tuple[str, ...] = ()
    method: str = "ml"
    method_label: str = "ML"
    seasonal_naive_4w: float | None = None
    ml_volume: float | None = None
    bias_adjustment: float = 0.0
    forecast_national_volume: float | None = None


class RegressorLike(Protocol):
    def fit(self, X: np.ndarray, y: np.ndarray) -> Any: ...

    def predict(self, X: np.ndarray) -> np.ndarray: ...


def _to_thousand(value: int | float | None) -> float | None:
    if value is None:
        return None
    return round(float(value) / 1000, 1)


def infer_special_communication(
    remaining_volume: int | None,
    day_type: str | None,
    report_format: str | None,
) -> int:
    if (remaining_volume or 0) > 0:
        return 1
    resolved = day_type or "weekday"
    if resolved in {"saturday", "sunday", "holiday"}:
        return 1
    if report_format == "compact":
        return 1
    return 0


def resolve_special_communication_flag(
    remaining_volume: int | None,
    day_type: str | None,
    report_format: str | None,
    target_day: date,
    operation_periods: list[dict] | None = None,
) -> int:
    if infer_special_communication(remaining_volume, day_type, report_format):
        return 1
    if not operation_periods:
        return 0
    active = get_operation_periods_for_date(target_day, operation_periods)
    return 1 if any(period["periodType"] in SPECIAL_COMMUNICATION_PERIOD_TYPES for period in active) else 0


def _operation_period_flags(
    target_day: date,
    operation_periods: list[dict] | None,
) -> tuple[int, int]:
    if not operation_periods:
        return 0, 0
    active = get_operation_periods_for_date(target_day, operation_periods)
    post_shopping = int(any(period["periodType"] == "post_shopping_discount" for period in active))
    special = int(any(period["periodType"] == "special_communication" for period in active))
    return post_shopping, special


def _same_weekday_lag(
    volume_by_date: dict[str, float],
    target_day: date,
    weeks_back: int,
) -> float:
    lag_day = target_day - timedelta(days=7 * weeks_back)
    return volume_by_date.get(lag_day.isoformat(), 0.0)


def _rolling_same_weekday_mean(
    volume_by_date: dict[str, float],
    target_day: date,
    weeks: int = 4,
) -> float:
    values = [
        volume_by_date.get((target_day - timedelta(days=7 * offset)).isoformat(), 0.0)
        for offset in range(1, weeks + 1)
    ]
    non_zero = [value for value in values if value > 0]
    if not non_zero:
        return 0.0
    return sum(non_zero) / len(non_zero)


def _days_since_last_report(report_dates: list[date], report_day: date) -> float:
    prior = [value for value in report_dates if value < report_day]
    if not prior:
        return 0.0
    return float((report_day - prior[-1]).days)


def _rolling_mean(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    subset = values[-window:]
    return sum(subset) / len(subset)


def build_feature_vector(
    report_day: date,
    target_day: date,
    history_volumes: list[float],
    national_volume: float | None,
    special_communication: int,
    *,
    volume_by_date: dict[str, float] | None = None,
    report_dates: list[date] | None = None,
    operation_periods: list[dict] | None = None,
) -> list[float]:
    prev_day_volume = history_volumes[-1] if history_volumes else 0.0
    avg_7d = _rolling_mean(history_volumes, 7) or prev_day_volume
    avg_30d = _rolling_mean(history_volumes, 30) or avg_7d
    volume_map = volume_by_date or {}
    lag_1w = _same_weekday_lag(volume_map, target_day, 1)
    lag_2w = _same_weekday_lag(volume_map, target_day, 2)
    lag_4w = _same_weekday_lag(volume_map, target_day, 4)
    rolling_4w = _rolling_same_weekday_mean(volume_map, target_day, 4)
    days_since = _days_since_last_report(report_dates or [], report_day)
    national = national_volume if national_volume is not None else 0.0
    ratio = national / prev_day_volume if prev_day_volume > 0 else 0.0
    post_shopping, special_period = _operation_period_flags(target_day, operation_periods)
    no_parcel_index, days_until_end = no_parcel_period_features(target_day, operation_periods)
    return [
        float(target_day.weekday()),
        float(target_day.month),
        prev_day_volume,
        avg_7d,
        avg_30d,
        national,
        1.0 if resolve_day_type(target_day) == "holiday" else 0.0,
        float(special_communication),
        lag_1w,
        lag_2w,
        lag_4w,
        rolling_4w,
        days_since,
        ratio,
        float(post_shopping),
        float(special_period),
        no_parcel_index,
        days_until_end,
        1.0 if is_post_holiday(target_day) else 0.0,
        float(days_since_holiday(target_day)),
        float(days_until_holiday(target_day)),
    ]


def _sample_weight_for_target(
    target_day: date,
    operation_periods: list[dict] | None,
) -> float:
    category = classify_forecast_period_category(target_day, operation_periods or [])
    if category == "no_parcel":
        return NO_PARCEL_SAMPLE_WEIGHT
    if category == "special":
        return SPECIAL_SAMPLE_WEIGHT
    return NORMAL_SAMPLE_WEIGHT


def build_training_dataset(
    rows: list[VolumeMlRow],
    operation_periods: list[dict] | None = None,
    *,
    weekday_only: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[date]]:
    if not rows:
        return (
            np.empty((0, len(FEATURE_NAMES))),
            np.empty((0,)),
            np.empty((0,)),
            [],
        )

    sorted_rows = sorted(rows, key=lambda row: row.report_date)
    volume_by_date: dict[str, float] = {}
    report_dates: list[date] = []
    for row in sorted_rows:
        if row.total_volume is None:
            continue
        key = row.report_date.isoformat()
        volume_by_date[key] = _to_thousand(row.total_volume) or 0.0
        report_dates.append(row.report_date)

    features: list[list[float]] = []
    targets: list[float] = []
    weights: list[float] = []
    target_days: list[date] = []

    history: list[float] = []
    for row in sorted_rows:
        if row.total_volume is None:
            continue
        report_day = row.report_date
        thousand = _to_thousand(row.total_volume) or 0.0
        history.append(thousand)

        if len(history) < 8:
            continue

        target_day = resolve_forecast_target_date(report_day)
        if weekday_only and not is_weekday_target(resolve_day_type(target_day)):
            continue
        target_key = target_day.isoformat()
        if target_key not in volume_by_date:
            continue

        national = _to_thousand(row.national_volume)
        special = resolve_special_communication_flag(
            row.remaining_volume,
            row.day_type or resolve_day_type(report_day),
            row.report_format,
            target_day,
            operation_periods,
        )
        feature_vector = build_feature_vector(
            report_day,
            target_day,
            history,
            national,
            special,
            volume_by_date=volume_by_date,
            report_dates=report_dates,
            operation_periods=operation_periods,
        )
        features.append(feature_vector)
        targets.append(volume_by_date[target_key])
        weights.append(_sample_weight_for_target(target_day, operation_periods))
        target_days.append(target_day)

    if not features:
        return (
            np.empty((0, len(FEATURE_NAMES))),
            np.empty((0,)),
            np.empty((0,)),
            [],
        )

    return (
        np.asarray(features, dtype=float),
        np.asarray(targets, dtype=float),
        np.asarray(weights, dtype=float),
        target_days,
    )


def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = y_true > 0
    if not np.any(mask):
        return 0.0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def _evaluate_model(model: RegressorLike, X_test: np.ndarray, y_test: np.ndarray) -> tuple[float, float]:
    predictions = model.predict(X_test)
    mae = float(np.mean(np.abs(y_test - predictions)))
    mape = _mape(y_test, predictions)
    return mae, mape


def _create_lightgbm_model() -> RegressorLike | None:
    try:
        from lightgbm import LGBMRegressor
    except ImportError:
        return None
    return LGBMRegressor(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
        verbose=-1,
    )


def _create_models() -> dict[str, RegressorLike]:
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
    from sklearn.linear_model import LinearRegression

    models: dict[str, RegressorLike] = {
        "linear_regression": LinearRegression(),
        "random_forest": RandomForestRegressor(
            n_estimators=200,
            max_depth=8,
            min_samples_leaf=2,
            random_state=42,
        ),
        "gradient_boosting": GradientBoostingRegressor(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            random_state=42,
        ),
    }
    lightgbm_model = _create_lightgbm_model()
    if lightgbm_model is not None:
        models["lightgbm"] = lightgbm_model
    return models


def compare_models(
    X: np.ndarray,
    y: np.ndarray,
    sample_weight: np.ndarray | None = None,
) -> tuple[str, tuple[ModelMetric, ...]]:
    if len(y) < MIN_TRAINING_SAMPLES:
        raise ValueError("insufficient training samples")

    split_index = max(int(len(y) * (1 - HOLDOUT_RATIO)), MIN_TRAINING_SAMPLES // 2)
    split_index = min(split_index, len(y) - 5)
    X_train, X_test = X[:split_index], X[split_index:]
    y_train, y_test = y[:split_index], y[split_index:]
    w_train = sample_weight[:split_index] if sample_weight is not None else None

    metrics: list[ModelMetric] = []
    best_key = "linear_regression"
    best_mae = float("inf")

    for key, model in _create_models().items():
        if w_train is not None:
            fitted = model.fit(X_train, y_train, sample_weight=w_train)
        else:
            fitted = model.fit(X_train, y_train)
        mae, mape = _evaluate_model(fitted, X_test, y_test)
        metrics.append(
            ModelMetric(
                model_key=key,
                model_label=MODEL_LABELS[key],
                mae=round(mae, 2),
                mape=round(mape, 2),
            )
        )
        if mae < best_mae:
            best_mae = mae
            best_key = key

    metrics.sort(key=lambda item: item.mae)
    return best_key, tuple(metrics)


def train_best_model(
    X: np.ndarray,
    y: np.ndarray,
    best_key: str,
    sample_weight: np.ndarray | None = None,
) -> RegressorLike:
    model = _create_models()[best_key]
    if sample_weight is not None:
        model.fit(X, y, sample_weight=sample_weight)
    else:
        model.fit(X, y)
    return model


def _baseline_same_weekday_4w(
    volume_by_date: dict[str, float],
    target_day: date,
) -> float | None:
    value = _rolling_same_weekday_mean(volume_by_date, target_day, 4)
    return value if value > 0 else None


def _estimate_rolling_bias(
    rows: list[VolumeMlRow],
    operation_periods: list[dict] | None,
    model: RegressorLike,
    best_key: str,
    *,
    X: np.ndarray | None = None,
    y: np.ndarray | None = None,
    weights: np.ndarray | None = None,
) -> float:
    if X is None or y is None:
        X, y, weights, _ = build_training_dataset(rows, operation_periods, weekday_only=True)
    if len(y) < BIAS_WINDOW:
        return 0.0
    tail = min(BIAS_WINDOW, len(y))
    preds = model.predict(X[-tail:])
    errors = preds - y[-tail:]
    sample_weights = weights[-tail:] if weights is not None else None
    if sample_weights is not None and np.any(sample_weights > 0):
        return float(round(np.average(errors, weights=sample_weights), 1))
    return float(round(np.mean(errors), 1))


def _tune_blend_weight(
    ml_holdout: np.ndarray,
    y_holdout: np.ndarray,
    baseline_4w: float,
    target_days: list[date],
    operation_periods: list[dict] | None,
) -> float:
    normal_mask = np.array(
        [
            classify_forecast_period_category(day, operation_periods or []) == "normal"
            for day in target_days
        ],
        dtype=bool,
    )
    if not np.any(normal_mask):
        return DEFAULT_ML_BLEND_WEIGHT

    y_normal = y_holdout[normal_mask]
    ml_normal = ml_holdout[normal_mask]
    best_weight = DEFAULT_ML_BLEND_WEIGHT
    best_mape = float("inf")
    for candidate in BLEND_WEIGHT_CANDIDATES:
        blended = np.array(
            [blend_with_seasonal_naive(float(ml), baseline_4w, ml_weight=candidate) for ml in ml_normal],
            dtype=float,
        )
        mape = _mape(y_normal, blended)
        if mape < best_mape:
            best_mape = mape
            best_weight = candidate
    return best_weight


def blend_with_seasonal_naive(
    ml_volume: float,
    seasonal_naive_4w: float | None,
    *,
    ml_weight: float = DEFAULT_ML_BLEND_WEIGHT,
) -> float:
    if seasonal_naive_4w is None or seasonal_naive_4w <= 0:
        return ml_volume
    blended = ml_weight * ml_volume + (1.0 - ml_weight) * seasonal_naive_4w
    return round(max(blended, 0.0), 1)


def save_model_cache(
    cache_path: Path,
    *,
    model: RegressorLike,
    best_key: str,
    trained_through: str,
    training_samples: int,
) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": model,
        "best_key": best_key,
        "trained_through": trained_through,
        "training_samples": training_samples,
        "feature_names": FEATURE_NAMES,
    }
    cache_path.write_bytes(pickle.dumps(payload))


def load_model_cache(cache_path: Path, trained_through: str) -> tuple[RegressorLike, str] | None:
    if not cache_path.exists():
        return None
    try:
        payload = pickle.loads(cache_path.read_bytes())
    except (pickle.PickleError, OSError):
        return None
    if payload.get("trained_through") != trained_through:
        return None
    if payload.get("feature_names") != FEATURE_NAMES:
        return None
    model = payload.get("model")
    best_key = payload.get("best_key")
    if model is None or not best_key:
        return None
    return model, best_key


def predict_next_volume(
    rows: list[VolumeMlRow],
    report_date: str,
    operation_periods: list[dict] | None = None,
    historical_no_parcel_avg: float | None = None,
    *,
    feature_anchor_date: str | None = None,
    seasonal_naive_4w: float | None = None,
    cache_path: Path | None = None,
    use_cache: bool = True,
) -> VolumeMlForecastResult | None:
    X, y, sample_weights, target_days = build_training_dataset(rows, operation_periods, weekday_only=True)
    if len(y) < MIN_TRAINING_SAMPLES:
        return None

    sorted_rows = sorted(rows, key=lambda row: row.report_date)
    trained_through = sorted_rows[-1].report_date.isoformat()

    best_key: str
    metrics: tuple[ModelMetric, ...]
    model: RegressorLike

    cached = None
    if cache_path is not None and use_cache:
        cached = load_model_cache(cache_path, trained_through)
    if cached is not None:
        model, best_key = cached
        metrics = (
            ModelMetric(
                model_key=best_key,
                model_label=MODEL_LABELS.get(best_key, best_key),
                mae=0.0,
                mape=0.0,
            ),
        )
    elif ml_inference_mode_fast():
        models = _create_models()
        best_key = "lightgbm" if "lightgbm" in models else "gradient_boosting"
        model = train_best_model(X, y, best_key, sample_weights)
        metrics = (
            ModelMetric(
                model_key=best_key,
                model_label=MODEL_LABELS.get(best_key, best_key),
                mae=0.0,
                mape=0.0,
            ),
        )
        if cache_path is not None and use_cache:
            save_model_cache(
                cache_path,
                model=model,
                best_key=best_key,
                trained_through=trained_through,
                training_samples=len(y),
            )
    else:
        try:
            best_key, metrics = compare_models(X, y, sample_weights)
        except ValueError:
            return None
        model = train_best_model(X, y, best_key, sample_weights)
        if cache_path is not None and use_cache:
            save_model_cache(
                cache_path,
                model=model,
                best_key=best_key,
                trained_through=trained_through,
                training_samples=len(y),
            )

    volume_by_date: dict[str, float] = {}
    national_by_date: dict[str, float] = {}
    report_dates: list[date] = []
    volume_history: list[float] = []
    anchor_row: VolumeMlRow | None = None
    anchor_key = feature_anchor_date or report_date

    for row in sorted_rows:
        if row.total_volume is None:
            continue
        thousand = _to_thousand(row.total_volume) or 0.0
        volume_by_date[row.report_date.isoformat()] = thousand
        if row.national_volume is not None:
            national_thousand = _to_thousand(row.national_volume)
            if national_thousand is not None:
                national_by_date[row.report_date.isoformat()] = national_thousand
        report_dates.append(row.report_date)
        if row.report_date.isoformat() <= anchor_key:
            volume_history.append(thousand)
            if row.report_date.isoformat() == anchor_key:
                anchor_row = row

    if anchor_row is None:
        for row in reversed(sorted_rows):
            if row.total_volume is None:
                continue
            if row.report_date.isoformat() <= anchor_key:
                anchor_row = row
                break

    if anchor_row is None or not volume_history:
        return None

    report_day = date.fromisoformat(report_date)
    target_day = resolve_forecast_target_date(report_day)
    if not is_weekday_target(resolve_day_type(target_day)):
        return None

    baseline_4w = seasonal_naive_4w or _baseline_same_weekday_4w(volume_by_date, target_day)
    national_lag_1w = _same_weekday_lag(national_by_date, target_day, 1)
    national_4w = _baseline_same_weekday_4w(national_by_date, target_day)
    national_baseline = _rolling_same_weekday_mean(national_by_date, target_day, 8) or national_4w
    national_forecast = forecast_national_volume(
        target_day_type=resolve_day_type(target_day),
        seasonal_naive_1w=national_lag_1w if national_lag_1w > 0 else None,
        seasonal_naive_4w=national_4w,
        same_type_baseline=national_baseline if national_baseline else None,
        same_type_avg_7d=national_4w,
        today_volume=_to_thousand(anchor_row.national_volume),
    )
    if national_forecast is not None:
        national_forecast, _ = apply_operation_period_volume_adjustment(
            national_forecast,
            target_day,
            operation_periods or [],
            volume_by_date=national_by_date,
            before_date=target_day,
            include_no_parcel=False,
        )
        national_forecast, _ = apply_post_holiday_adjustment(
            national_forecast,
            target_day,
            national_by_date,
        )
    feature_vector = build_feature_vector(
        anchor_row.report_date,
        target_day,
        volume_history,
        _to_thousand(anchor_row.national_volume),
        resolve_special_communication_flag(
            anchor_row.remaining_volume,
            anchor_row.day_type or resolve_day_type(anchor_row.report_date),
            anchor_row.report_format,
            target_day,
            operation_periods,
        ),
        volume_by_date=volume_by_date,
        report_dates=report_dates,
        operation_periods=operation_periods,
    )
    ml_raw = float(model.predict(np.asarray([feature_vector], dtype=float))[0])
    ml_raw = round(max(ml_raw, 0.0), 1)
    bias = _estimate_rolling_bias(
        rows,
        operation_periods,
        model,
        best_key,
        X=X,
        y=y,
        weights=sample_weights,
    )

    if baseline_4w is not None:
        holdout_start = max(int(len(y) * (1 - HOLDOUT_RATIO)), MIN_TRAINING_SAMPLES // 2)
        holdout_start = min(holdout_start, len(y) - 5)
        holdout_target_days = target_days[holdout_start:]
        holdout_y = y[holdout_start:]
        ml_holdout = model.predict(X[holdout_start:])
        normal_mask = np.array(
            [
                classify_forecast_period_category(day, operation_periods or []) == "normal"
                for day in holdout_target_days
            ],
            dtype=bool,
        )
        if np.any(normal_mask):
            y_normal = holdout_y[normal_mask]
            ml_normal = ml_holdout[normal_mask]
            baseline_preds = np.full(len(y_normal), baseline_4w)
            baseline_mape = _mape(y_normal, baseline_preds)
            ml_mape = _mape(y_normal, ml_normal)
        else:
            baseline_preds = np.full(len(holdout_y), baseline_4w)
            baseline_mape = _mape(holdout_y, baseline_preds)
            ml_mape = _mape(holdout_y, ml_holdout)
        if ml_mape > baseline_mape * 1.02:
            prediction = round(max(baseline_4w - bias, 0.0), 1)
            prediction, period_labels = apply_operation_period_volume_adjustment(
                prediction,
                target_day,
                operation_periods or [],
                historical_no_parcel_avg=historical_no_parcel_avg,
                volume_by_date=volume_by_date,
                before_date=target_day,
            )
            prediction, holiday_labels = apply_post_holiday_adjustment(
                prediction,
                target_day,
                volume_by_date,
            )
            period_labels = period_labels + holiday_labels
            target_idx = target_day.weekday()
            return VolumeMlForecastResult(
                report_date=report_date,
                target_date=target_day.isoformat(),
                target_weekday_label=WEEKDAY_LABELS[target_idx],
                target_day_type=resolve_day_type(target_day),
                forecast_target_note=forecast_target_note_for(report_day, target_day),
                forecast_volume=prediction,
                best_model_key=best_key,
                best_model_label=MODEL_LABELS.get(best_key, best_key),
                training_samples=len(y),
                model_metrics=metrics,
                feature_names=tuple(FEATURE_NAMES),
                operation_period_labels=period_labels,
                method="seasonal_naive_gate",
                method_label="동일요일 4주 평균",
                seasonal_naive_4w=baseline_4w,
                ml_volume=ml_raw,
                bias_adjustment=bias,
                forecast_national_volume=national_forecast,
            )

        ml_weight = _tune_blend_weight(
            ml_holdout,
            holdout_y,
            baseline_4w,
            holdout_target_days,
            operation_periods,
        )
    else:
        ml_weight = DEFAULT_ML_BLEND_WEIGHT

    prediction = blend_with_seasonal_naive(ml_raw, baseline_4w, ml_weight=ml_weight)
    prediction = round(max(prediction - bias, 0.0), 1)
    prediction, period_labels = apply_operation_period_volume_adjustment(
        prediction,
        target_day,
        operation_periods or [],
        historical_no_parcel_avg=historical_no_parcel_avg,
        volume_by_date=volume_by_date,
        before_date=target_day,
    )
    prediction, holiday_labels = apply_post_holiday_adjustment(
        prediction,
        target_day,
        volume_by_date,
    )
    period_labels = period_labels + holiday_labels

    target_idx = target_day.weekday()
    return VolumeMlForecastResult(
        report_date=report_date,
        target_date=target_day.isoformat(),
        target_weekday_label=WEEKDAY_LABELS[target_idx],
        target_day_type=resolve_day_type(target_day),
        forecast_target_note=forecast_target_note_for(report_day, target_day),
        forecast_volume=prediction,
        best_model_key=best_key,
        best_model_label=MODEL_LABELS.get(best_key, best_key),
        training_samples=len(y),
        model_metrics=metrics,
        feature_names=tuple(FEATURE_NAMES),
        operation_period_labels=period_labels,
        method="ml_blend",
        method_label="ML+Seasonal Naive",
        seasonal_naive_4w=baseline_4w,
        ml_volume=ml_raw,
        bias_adjustment=bias,
        forecast_national_volume=national_forecast,
    )


def build_ml_volume_forecast_text(result: VolumeMlForecastResult) -> str:
    day_type_label = DAY_TYPE_LABELS.get(result.target_day_type, result.target_day_type)
    target_hint = (
        f"({result.forecast_target_note}) "
        if result.forecast_target_note
        else ""
    )
    lead = _format_forecast_volume_lead(
        weekday_label=result.target_weekday_label,
        day_type_label=day_type_label,
        target_hint=target_hint,
        forecast_volume=result.forecast_volume,
        forecast_national_volume=result.forecast_national_volume,
    )

    metric_text = ", ".join(
        f"{metric.model_label} MAE {metric.mae:,.1f}천({metric.mape:.1f}%)"
        for metric in result.model_metrics
        if metric.mae > 0
    )
    method_note = result.method_label
    if metric_text:
        model_part = (
            f" {method_note} 모델(학습 {result.training_samples}건, 검증 비교: {metric_text})"
        )
    else:
        model_part = f" {method_note}(학습 {result.training_samples}건)"
    blend_note = ""
    if result.seasonal_naive_4w is not None:
        blend_note = f" 동일 요일 4주 평균 {result.seasonal_naive_4w:,.1f}천개와 블렌드"
    bias_note = ""
    if result.bias_adjustment:
        bias_note = f", 최근 편향 보정 {result.bias_adjustment:+.1f}천"
    return (
        f"{lead}{model_part}{blend_note}{bias_note} 기반 추정치입니다."
        f"{format_forecast_adjustment_suffix(result.operation_period_labels)}"
    )
