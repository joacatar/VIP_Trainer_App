"""Shared APAC catalog labels and VIP order numbers."""

from __future__ import annotations

from typing import Any

# Fallback map when DB rows predate the order_number column.
ORDER_NUMBERS: dict[tuple[int, int], str] = {
    (1, 1): "12-26-02-0002",
    (1, 2): "12-26-02-0004",
    (1, 3): "12-26-02-0008",
    (1, 4): "12-26-02-0010",
    (1, 5): "12-26-02-0012",
    (1, 6): "12-26-02-0014",
    (1, 7): "12-26-02-0016",
    (1, 8): "12-26-02-0018",
    (1, 9): "12-26-02-0020",
    (1, 10): "12-26-02-0022",
    (1, 11): "12-26-02-0024",
    (1, 12): "12-26-02-0028",
    (1, 13): "12-26-02-0032",
    (1, 14): "12-26-02-0034",
    (1, 15): "12-26-02-0036",
    (1, 16): "12-26-02-0038",
    (2, 1): "12-26-02-0003",
    (2, 2): "12-26-02-0005",
    (2, 3): "12-26-02-0009",
    (2, 4): "12-26-02-0011",
    (2, 5): "12-26-02-0013",
    (2, 6): "12-26-02-0015",
    (2, 7): "12-26-02-0017",
    (2, 8): "12-26-02-0019",
    (2, 9): "12-26-02-0021",
    (2, 10): "12-26-02-0023",
    (2, 11): "12-26-02-0025",
    (2, 12): "12-26-02-0029",
    (2, 13): "12-26-02-0033",
    (2, 14): "12-26-02-0035",
    (2, 15): "12-26-02-0037",
    (2, 16): "12-26-02-0039",
}


def case_phase_no(row: dict[str, Any]) -> int:
    """1 = phase-1 catalog case, 2 = simulated live case. Defaults to 1."""
    try:
        return int(row.get("phase_no") or 1)
    except (TypeError, ValueError):
        return 1


def case_catalog_label(row: dict[str, Any]) -> str:
    """APAC list id: 1A–16A (Set 1), 1B–16B (Set 2), L01–L30 (phase 2)."""
    label = row.get("catalog_label")
    if label:
        return str(label)
    case_no = int(row["case_no"])
    if case_phase_no(row) == 2:
        return f"L{case_no:02d}"
    set_no = int(row["set_no"])
    return f"{case_no}{'A' if set_no == 1 else 'B'}"


def case_order_number(row: dict[str, Any]) -> str | None:
    """VIP order number used to open the case in the planning system."""
    order = row.get("order_number")
    if order:
        return str(order)
    # Phase-2 cases reuse set_no 1 with case_no 1-30, so the phase-1 catalog
    # map would hand back an unrelated case's VIP number. Their real numbers
    # come from the database once they are backfilled.
    if case_phase_no(row) != 1:
        return None
    try:
        key = (int(row["set_no"]), int(row["case_no"]))
    except (KeyError, TypeError, ValueError):
        return None
    return ORDER_NUMBERS.get(key)


def case_label(row: dict[str, Any]) -> str:
    """Short label for buttons and compact selectors."""
    order = case_order_number(row)
    prefix = "Live case" if case_phase_no(row) == 2 else "Case"
    label = f"{prefix} {case_catalog_label(row)}"
    return f"{label} · {order}" if order else label


def case_title(row: dict[str, Any]) -> str:
    """Full set + catalog label + VIP order for headers."""
    order = case_order_number(row)
    if case_phase_no(row) == 2:
        title = f"Live case {case_catalog_label(row)}"
    else:
        title = f"Set {row['set_no']} · Case {case_catalog_label(row)}"
    return f"{title} · {order}" if order else title
