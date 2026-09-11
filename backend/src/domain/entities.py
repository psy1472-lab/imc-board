from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from typing import Any


@dataclass
class DailySummary:
    report_date: date
    center_name: str | None = None
    national_volume: int | None = None
    total_volume: int | None = None
    dispatch_volume: int | None = None
    arrival_volume: int | None = None
    remaining_volume: int | None = None
    productivity: float | None = None
    ips_rate: float | None = None
    last_operation_time: time | None = None
    communication_status: str = "UNKNOWN"
    raw_values: dict[str, Any] = field(default_factory=dict)


@dataclass
class HourlyThroughput:
    report_date: date
    hour_slot: str
    dispatch_volume: int | None = None
    arrival_volume: int | None = None
    total_volume: int | None = None


@dataclass
class StaffingHour:
    report_date: date
    hour_slot: str
    actual_staff: int | None = None
    productivity: float | None = None
    absence_rate: float | None = None


@dataclass
class QuotaExchange:
    report_date: date
    quarter_standard: int | None = None
    quarter_actual: int | None = None
    quarter_difference: int | None = None
    exchange_standard: int | None = None
    exchange_actual: int | None = None
    exchange_difference: int | None = None
    exchange_remaining: int | None = None


@dataclass
class TransportOffice:
    report_date: date
    office_name: str
    volume: int | None = None
    vehicles_actual: int | None = None
    vehicles_standard: int | None = None
    last_arrival_time: str | None = None
    delay_minutes: int | None = None
    status: str = "UNKNOWN"


@dataclass
class SortingMachine:
    report_date: date
    total_supply: int | None = None
    total_sorted: int | None = None
    sorting_rate: float | None = None
    ips_rate: float | None = None
    reject_rate: float | None = None
    shortcut_rate: float | None = None
    avg_throughput: int | None = None
    peak_throughput: int | None = None
    unread_count: int | None = None
    unread_rate: float | None = None


@dataclass
class MachineSortingLine:
    report_date: date
    stream: str
    deck: int
    volume: int | None = None
    share_rate: float | None = None


@dataclass
class SafetyCategory:
    report_date: date
    category: str
    label: str
    passed_items: int = 0
    total_items: int = 0
    status: str = "UNKNOWN"


@dataclass
class SafetyIncident:
    report_date: date
    department: str | None = None
    victim_name: str | None = None
    gender: str | None = None
    occurrence_time: str | None = None
    injury_type: str | None = None
    description: str | None = None


@dataclass
class Anomaly:
    report_date: date
    category: str
    severity: str
    message: str
    source: str = "rule"


@dataclass
class ParsedReport:
    report_date: date
    center_name: str | None
    report_format: str
    daily_summary: DailySummary
    day_type: str = "weekday"
    hourly_throughput: list[HourlyThroughput] = field(default_factory=list)
    staffing: list[StaffingHour] = field(default_factory=list)
    quota_exchange: QuotaExchange | None = None
    transport_offices: list[TransportOffice] = field(default_factory=list)
    sorting_machine: SortingMachine | None = None
    machine_sorting: list[MachineSortingLine] = field(default_factory=list)
    safety_categories: list[SafetyCategory] = field(default_factory=list)
    safety_incidents: list[SafetyIncident] = field(default_factory=list)
    anomalies: list[Anomaly] = field(default_factory=list)
    validation_logs: list[dict[str, Any]] = field(default_factory=list)
