from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FormatProfile:
    name: str
    kpi_pattern: str
    validation_profile: str
    sections_available: frozenset[str]

    @property
    def is_compact(self) -> bool:
        return self.name == "compact"


STANDARD_PROFILE = FormatProfile(
    name="standard",
    kpi_pattern="소통실적",
    validation_profile="standard",
    sections_available=frozenset({"hourly", "quota", "transport", "sorting", "safety", "staffing"}),
)

COMPACT_PROFILE = FormatProfile(
    name="compact",
    kpi_pattern="소통물량",
    validation_profile="compact",
    sections_available=frozenset({"hourly", "sorting"}),
)

PROFILE_BY_NAME = {
    STANDARD_PROFILE.name: STANDARD_PROFILE,
    COMPACT_PROFILE.name: COMPACT_PROFILE,
}
