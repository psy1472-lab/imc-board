"""야간 인력 적정성·잔량 0 목표 인력 추정."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from domain.hour_slots import HOUR_SLOTS, format_hour_label
from domain.volume_forecast import estimate_staff_for_volume

NIGHT_SHIFT_SLOTS = ("18", "19", "20", "21", "22", "23", "00", "01", "02", "03", "04", "05")
PEAK_VOLUME_SLOTS = ("20", "21", "22", "23", "00", "01")
STAFFING_BUFFER_RATIO = 0.10


def _as_positive_float(value: float | int | None) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


@dataclass(frozen=True)
class NightShiftMetrics:
    avg_staff: float | None
    peak_staff: int | None
    avg_productivity: float | None
    total_volume_k: float | None


@dataclass(frozen=True)
class StaffingAdequacyEstimate:
    target_volume_k: float
    night_avg_staff: float | None
    night_peak_staff: float | None
    reference_sample_count: int
    productivity_target: float | None


def _slot_index_map(slots: list[str]) -> dict[str, int]:
    return {slot: idx for idx, slot in enumerate(slots)}


def compute_night_shift_metrics(hourly: dict) -> NightShiftMetrics:
    slots = hourly.get("slots") or list(HOUR_SLOTS)
    staff = hourly.get("staff") or []
    productivity = hourly.get("productivity") or []
    volume = hourly.get("volume") or []
    idx_map = _slot_index_map(slots)

    staff_vals: list[float] = []
    prod_vals: list[float] = []
    vol_sum = 0.0
    peak_staff: int | None = None

    for slot in NIGHT_SHIFT_SLOTS:
        idx = idx_map.get(slot)
        if idx is None:
            continue
        slot_staff = staff[idx] if idx < len(staff) else None
        slot_prod = productivity[idx] if idx < len(productivity) else None
        slot_volume = volume[idx] if idx < len(volume) else None
        if slot_staff is not None:
            staff_vals.append(float(slot_staff))
            peak_staff = max(peak_staff or 0, int(slot_staff))
        if slot_prod is not None:
            prod_vals.append(float(slot_prod))
        if slot_volume is not None:
            vol_sum += float(slot_volume)

    return NightShiftMetrics(
        avg_staff=round(sum(staff_vals) / len(staff_vals), 1) if staff_vals else None,
        peak_staff=peak_staff,
        avg_productivity=round(sum(prod_vals) / len(prod_vals), 1) if prod_vals else None,
        total_volume_k=round(vol_sum, 1) if vol_sum > 0 else None,
    )


def filter_zero_remaining_reference_days(
    reference_days: list[dict],
    target_volume_k: float,
    *,
    min_volume_k: float = 350.0,
    volume_band_ratio: float = 0.15,
) -> list[dict]:
    candidates = [
        day
        for day in reference_days
        if (day.get("remainingVolumeK") or 0) == 0 and (day.get("totalVolumeK") or 0) >= min_volume_k
    ]
    if not candidates:
        return []

    low = target_volume_k * (1 - volume_band_ratio)
    high = target_volume_k * (1 + volume_band_ratio)
    similar = [day for day in candidates if low <= (day.get("totalVolumeK") or 0) <= high]
    if len(similar) >= 3:
        return similar

    high_volume = [
        day for day in candidates if (day.get("totalVolumeK") or 0) >= target_volume_k * 0.85
    ]
    if len(high_volume) >= 3:
        return high_volume
    return candidates[:10]


def estimate_staffing_adequacy(
    target_volume_k: float,
    reference_days: list[dict],
    hourly_pattern: dict | None = None,
    *,
    buffer_ratio: float = STAFFING_BUFFER_RATIO,
) -> StaffingAdequacyEstimate | None:
    target_volume_k = _as_positive_float(target_volume_k)
    if target_volume_k is None:
        return None

    refs = filter_zero_remaining_reference_days(reference_days, target_volume_k)
    if not refs:
        return None

    staff_ratios: list[float] = []
    peak_staffs: list[float] = []
    productivities: list[float] = []
    for day in refs:
        volume_k = day.get("totalVolumeK")
        avg_staff = day.get("nightAvgStaff")
        peak_staff = day.get("nightPeakStaff")
        productivity = day.get("nightAvgProductivity")
        if volume_k and avg_staff:
            staff_ratios.append(float(avg_staff) / float(volume_k))
        if peak_staff:
            peak_staffs.append(float(peak_staff))
        if productivity:
            productivities.append(float(productivity))

    if not staff_ratios:
        return None

    ratio_median = median(staff_ratios)
    night_avg_staff = round(target_volume_k * ratio_median * (1 + buffer_ratio), 1)

    ref_volumes = [float(day["totalVolumeK"]) for day in refs if day.get("totalVolumeK")]
    ref_volume_median = median(ref_volumes) if ref_volumes else target_volume_k
    peak_median = median(peak_staffs) if peak_staffs else None
    night_peak_staff: float | None = None
    if peak_median is not None and ref_volume_median > 0:
        volume_scale = target_volume_k / ref_volume_median
        night_peak_staff = round(peak_median * volume_scale * (1 + buffer_ratio), 1)

    slot_peak = _estimate_peak_from_hourly_pattern(
        target_volume_k,
        hourly_pattern,
        productivities,
        buffer_ratio,
    )
    if slot_peak is not None:
        night_peak_staff = max(night_peak_staff or 0, slot_peak)

    productivity_target = round(median(productivities), 1) if productivities else None
    return StaffingAdequacyEstimate(
        target_volume_k=target_volume_k,
        night_avg_staff=night_avg_staff,
        night_peak_staff=night_peak_staff,
        reference_sample_count=len(refs),
        productivity_target=productivity_target,
    )


def _estimate_peak_from_hourly_pattern(
    target_volume_k: float,
    hourly_pattern: dict | None,
    reference_productivities: list[float],
    buffer_ratio: float,
) -> float | None:
    if not hourly_pattern:
        return None

    avg_volumes = hourly_pattern.get("averageVolume") or []
    slots = hourly_pattern.get("slots") or list(HOUR_SLOTS)
    if not avg_volumes:
        return None

    total_pattern_volume = sum(volume for volume in avg_volumes if volume)
    if total_pattern_volume <= 0:
        return None

    productivity = median(reference_productivities) if reference_productivities else 170.0
    if productivity <= 0:
        return None

    idx_map = _slot_index_map(slots)
    scale = target_volume_k / total_pattern_volume
    peak_required = 0.0
    for slot in PEAK_VOLUME_SLOTS:
        idx = idx_map.get(slot)
        if idx is None or idx >= len(avg_volumes):
            continue
        slot_volume_k = avg_volumes[idx]
        if slot_volume_k is None or slot_volume_k <= 0:
            continue
        required = (slot_volume_k * scale * 1000) / productivity
        peak_required = max(peak_required, required)

    if peak_required <= 0:
        return None
    return round(peak_required * (1 + buffer_ratio), 1)


def diagnose_remaining_volume(
    total_volume_k: float,
    remaining_volume_k: float,
    night_metrics: NightShiftMetrics,
    reference_days: list[dict],
    *,
    exchange_remaining: int | None = None,
) -> str | None:
    if remaining_volume_k <= 0:
        return None

    target_volume_k = total_volume_k + remaining_volume_k
    estimate = estimate_staffing_adequacy(target_volume_k, reference_days)
    if estimate is None:
        return (
            f"발송·소통 잔량 {remaining_volume_k:,.1f}천이 발생했습니다. "
            "과거 무잔량 일자 비교 데이터가 부족해 세부 원인 분리는 어렵습니다."
        )

    parts = [f"발송·소통 잔량 {remaining_volume_k:,.1f}천이 발생했습니다."]
    if exchange_remaining and exchange_remaining > 0:
        parts.append(f"교환 잔량 {exchange_remaining}건이 함께 남았습니다.")

    actual_avg = night_metrics.avg_staff
    actual_peak = night_metrics.peak_staff
    actual_prod = night_metrics.avg_productivity
    staff_gap = (
        estimate.night_avg_staff - actual_avg
        if actual_avg is not None and estimate.night_avg_staff is not None
        else None
    )
    prod_gap = (
        estimate.productivity_target - actual_prod
        if actual_prod is not None and estimate.productivity_target is not None
        else None
    )

    if staff_gap is not None and staff_gap > 8:
        parts.append(
            f"야간(18~05) 평균 인력이 무잔량 패턴 대비 약 {staff_gap:.0f}명 부족할 수 있습니다"
            f"(실제 {actual_avg:.0f}명 vs 참고 {estimate.night_avg_staff:.0f}명)."
        )
    elif (
        staff_gap is not None
        and staff_gap < -5
        and prod_gap is not None
        and prod_gap > 15
        and actual_avg is not None
        and estimate.productivity_target is not None
        and actual_prod is not None
    ):
        parts.append(
            f"야간 인력은 {actual_avg:.0f}명으로 충분했으나 인시당 처리량이 "
            f"무잔량 일 평균({estimate.productivity_target:.0f}개/시)보다 "
            f"약 {prod_gap:.0f}개/시 낮아 생산성 저하 영향이 클 수 있습니다."
        )
    elif (
        prod_gap is not None
        and prod_gap > 20
        and actual_prod is not None
        and estimate.productivity_target is not None
    ):
        parts.append(
            f"야간 인시당 처리량 {actual_prod:.0f}개/시가 "
            f"무잔량 일 평균 {estimate.productivity_target:.0f}개/시 대비 낮아 "
            f"생산성 저하 가능성이 큽니다."
        )
    elif (
        staff_gap is not None
        and staff_gap > 3
        and actual_avg is not None
        and actual_peak is not None
        and estimate.night_avg_staff is not None
        and estimate.night_peak_staff is not None
    ):
        parts.append(
            f"야간 평균 {actual_avg:.0f}명·피크 {actual_peak}명 수준에서 "
            f"무잔량 목표(평균 약 {estimate.night_avg_staff:.0f}명, "
            f"피크 약 {estimate.night_peak_staff:.0f}명)에 근접했으나 "
            f"피크 시간 생산성·물량 집중으로 일부 잔량이 남았을 수 있습니다."
        )
    else:
        parts.append(
            "인력·생산성 모두 평균 범위였으나 피크 시간대 처리능력 부족이 "
            "잔량에 기여했을 수 있습니다."
        )

    peak_text = (
        f", 피크 {estimate.night_peak_staff:.0f}명"
        if estimate.night_peak_staff is not None
        else ""
    )
    productivity_text = (
        f"인시당 {estimate.productivity_target:.0f}개/시 이상 "
        if estimate.productivity_target is not None
        else ""
    )
    parts.append(
        f"동일 물량({target_volume_k:,.1f}천) 무잔량 처리 시 "
        f"야간 평균 {estimate.night_avg_staff:.0f}명{peak_text}과 "
        f"{productivity_text}생산성 유지를 함께 검토할 수 있습니다."
    )
    return " ".join(parts)


def build_tomorrow_staffing_items(
    forecast_volume_k: float | None,
    reference_days: list[dict],
    hourly_pattern: dict | None,
    *,
    legacy_staff: float | None = None,
    legacy_reference_volume: float | None = None,
) -> list[dict[str, str]]:
    forecast_volume_k = _as_positive_float(forecast_volume_k)
    if forecast_volume_k is None:
        if legacy_staff is not None:
            return [
                {
                    "label": "적정인력 참고",
                    "text": f"최근 평균 실근무인력 {legacy_staff}명 수준의 배치를 검토할 수 있습니다.",
                }
            ]
        return []

    estimate = estimate_staffing_adequacy(forecast_volume_k, reference_days, hourly_pattern)
    if estimate is None:
        scaled_staff = estimate_staff_for_volume(
            forecast_volume_k,
            legacy_reference_volume,
            legacy_staff,
        )
        if scaled_staff is not None:
            return [
                {
                    "label": "적정인력 참고",
                    "text": (
                        f"예상 물량과 최근 7업무일 평균 생산성·인력 패턴을 반영하면 "
                        f"실근무인력 약 {scaled_staff}명 배치를 검토할 수 있습니다."
                    ),
                }
            ]
        if legacy_staff is not None:
            return [
                {
                    "label": "적정인력 참고",
                    "text": f"최근 평균 실근무인력 {legacy_staff}명 수준의 배치를 검토할 수 있습니다.",
                }
            ]
        return []

    items: list[dict[str, str]] = [
        {
            "label": "야간 적정인력(평균)",
            "text": (
                f"예상 물량 {forecast_volume_k:,.1f}천 기준, "
                f"최근 무잔량 {estimate.reference_sample_count}일 패턴을 반영하면 "
                f"18~05시 평균 실근무 약 {estimate.night_avg_staff:.0f}명 배치를 검토할 수 있습니다."
            ),
        }
    ]
    if estimate.night_peak_staff is not None:
        productivity_hint = (
            f"(인시당 {estimate.productivity_target:.0f}개/시 유지 가정)"
            if estimate.productivity_target is not None
            else ""
        )
        items.append(
            {
                "label": "야간 적정인력(피크)",
                "text": (
                    f"20~01시 피크 시간대에는 약 {estimate.night_peak_staff:.0f}명이 "
                    f"필요할 수 있습니다{productivity_hint}."
                ),
            }
        )

    peak_text = (
        f", 피크 {estimate.night_peak_staff:.0f}명"
        if estimate.night_peak_staff is not None
        else ""
    )
    productivity_text = (
        f"인시당 {estimate.productivity_target:.0f}개/시 이상 "
        if estimate.productivity_target is not None
        else ""
    )
    items.append(
        {
            "label": "잔량 0 목표 인력",
            "text": (
                f"발송·배분 잔량 없이 처리하려면 야간 평균 {estimate.night_avg_staff:.0f}명"
                f"{peak_text} 수준과 {productivity_text}생산성 유지가 함께 필요할 수 있습니다 "
                f"(최근 무잔량 일자 {estimate.reference_sample_count}일 참조, 10% 여유 반영)."
            ),
        }
    )
    return items


def build_peak_hour_staff_gaps(hourly: dict, *, buffer_ratio: float = STAFFING_BUFFER_RATIO) -> list[str]:
    slots = hourly.get("slots") or list(HOUR_SLOTS)
    staff = hourly.get("staff") or []
    productivity = hourly.get("productivity") or []
    volume = hourly.get("volume") or []
    idx_map = _slot_index_map(slots)

    gaps: list[str] = []
    for slot in PEAK_VOLUME_SLOTS:
        idx = idx_map.get(slot)
        if idx is None:
            continue
        slot_volume_k = volume[idx] if idx < len(volume) else None
        slot_staff = staff[idx] if idx < len(staff) else None
        slot_prod = productivity[idx] if idx < len(productivity) else None
        if slot_volume_k is None or slot_prod in (None, 0):
            continue
        required = (float(slot_volume_k) * 1000 / float(slot_prod)) * (1 + buffer_ratio)
        if slot_staff is None or required <= float(slot_staff):
            continue
        gap = required - float(slot_staff)
        if gap >= 5:
            gaps.append(f"{format_hour_label(slot)} 약 {gap:.0f}명")
    return gaps
