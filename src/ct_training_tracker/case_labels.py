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


def case_catalog_label(row: dict[str, Any]) -> str:
    """APAC list id: 1A–16A (Set 1) or 1B–16B (Set 2)."""
    label = row.get("catalog_label")
    if label:
        return str(label)
    set_no = int(row["set_no"])
    case_no = int(row["case_no"])
    return f"{case_no}{'A' if set_no == 1 else 'B'}"


def case_order_number(row: dict[str, Any]) -> str | None:
    """VIP order number used to open the case in the planning system."""
    order = row.get("order_number")
    if order:
        return str(order)
    try:
        key = (int(row["set_no"]), int(row["case_no"]))
    except (KeyError, TypeError, ValueError):
        return None
    return ORDER_NUMBERS.get(key)


def case_label(row: dict[str, Any]) -> str:
    """Short label for buttons and compact selectors."""
    order = case_order_number(row)
    label = f"Case {case_catalog_label(row)}"
    return f"{label} · {order}" if order else label


def case_title(row: dict[str, Any]) -> str:
    """Full set + catalog label + VIP order for headers."""
    order = case_order_number(row)
    title = f"Set {row['set_no']} · Case {case_catalog_label(row)}"
    return f"{title} · {order}" if order else title
