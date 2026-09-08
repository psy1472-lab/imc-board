BEFORE_18_SLOT = "~18"

HOUR_SLOTS = [
    BEFORE_18_SLOT,
    "18",
    "19",
    "20",
    "21",
    "22",
    "23",
    "00",
    "01",
    "02",
    "03",
    "04",
    "05",
    "06",
]


def normalize_hour_slot(slot: str) -> str:
    if slot == BEFORE_18_SLOT:
        return BEFORE_18_SLOT
    if slot.isdigit():
        return slot.zfill(2)
    return slot


def hour_slot_order(slot: str) -> int:
    normalized = normalize_hour_slot(slot)
    try:
        return HOUR_SLOTS.index(normalized)
    except ValueError:
        return 999


def format_hour_label(slot: str) -> str:
    """PDF 시간대 열 표기와 동일하게 라벨을 만든다."""
    normalized = normalize_hour_slot(slot)
    if normalized == BEFORE_18_SLOT:
        return "~18"
    return f"{normalized}~"
