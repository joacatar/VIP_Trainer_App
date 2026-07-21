import io

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Which program days share a PDF page
DAY_PAGE_GROUPS = [
    [0, 1, 2],       # Week 0 — sparse orientation days
    [3, 4],          # Week 0 — dense foundation days
    [5, 6],          # Week 1 — first 2 days
    [7, 8, 9],       # Week 1 — last 3 days
    [10, 11],        # Week 2 — first 2 days
    [12, 13, 14],    # Week 2 — last 3 days
    [15, 16],        # Week 3 — first 2 days
    [17, 18, 19],    # Week 3 — last 3 days
]

CATEGORY_LABELS = {
    "LEADS": "Leads",
    "TRAINER": "Trainer",
    "TRAINEE": "Trainee",
    "ASSIGNMENT": "Assignment",
    "BREAK": "Break",
    "GENERAL": "General",
    "HEADER": "",
}

CATEGORY_COLORS = {
    "LEADS":      colors.HexColor("#FFF3CD"),
    "TRAINER":    colors.HexColor("#D1ECF1"),
    "TRAINEE":    colors.HexColor("#D4EDDA"),
    "ASSIGNMENT": colors.HexColor("#F8D7DA"),
    "BREAK":      colors.HexColor("#E2E3E5"),
    "GENERAL":    colors.white,
}


def _get_page_group(day_no: int) -> tuple:
    for g in DAY_PAGE_GROUPS:
        if day_no in g:
            return tuple(g)
    return (day_no,)


def _day_table(day_data: pd.DataFrame, styles) -> Table:
    """Build a formatted Table for one program day."""
    col_widths = [130, 70, 255, 55]
    rows = [["Time (EST)", "Owner", "Activity", "Hours"]]

    for _, row in day_data.iterrows():
        cat = str(row.get("category") or "GENERAL")
        dur = row.get("duration_hours")
        rows.append([
            Paragraph(str(row.get("time_window") or ""), styles["Normal"]),
            Paragraph(CATEGORY_LABELS.get(cat, cat), styles["Normal"]),
            Paragraph(str(row.get("title") or ""), styles["Normal"]),
            Paragraph("" if pd.isna(dur) else str(dur), styles["Normal"]),
        ])

    table = Table(rows, colWidths=col_widths, repeatRows=1)

    ts = [
        ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#343A40")),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 8),
        ("GRID",         (0, 0), (-1, -1), 0.25, colors.HexColor("#CCCCCC")),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F9FA")]),
    ]
    # Per-row category colour
    for i, row in enumerate(day_data.itertuples(), start=1):
        cat = str(getattr(row, "category", "GENERAL"))
        bg = CATEGORY_COLORS.get(cat, colors.white)
        if bg != colors.white:
            ts.append(("BACKGROUND", (0, i), (-1, i), bg))

    table.setStyle(TableStyle(ts))
    return table


def generate_trainee_pdf(trainee_name: str, start_date: str, schedule: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=30, rightMargin=30,
        topMargin=30,  bottomMargin=30,
    )
    styles = getSampleStyleSheet()
    story = []

    # ── Cover header ────────────────────────────────────────────────────────
    story.append(Paragraph("VIP Training Schedule", styles["Title"]))
    story.append(Paragraph(f"Trainee: <b>{trainee_name}</b>", styles["Normal"]))
    story.append(Paragraph(f"Training Start Date: <b>{start_date}</b>", styles["Normal"]))
    story.append(Paragraph(
        "Times shown are <b>EST</b>. Schedule runs Mon–Fri; weekends and holidays are skipped.",
        styles["Normal"],
    ))
    story.append(PageBreak())

    # ── Determine which page-groups are present in this schedule ─────────────
    present_days = sorted(schedule["day_no"].dropna().astype(int).unique())
    seen_keys: list[tuple] = []
    seen_set: set[tuple] = set()
    for d in present_days:
        key = _get_page_group(d)
        if key not in seen_set:
            seen_set.add(key)
            seen_keys.append(key)

    # ── Render each page group ───────────────────────────────────────────────
    for page_idx, group in enumerate(seen_keys):
        first_on_page = True

        for day_no in group:
            day_data = schedule[schedule["day_no"] == day_no].copy()
            if day_data.empty:
                continue

            week_label     = day_data["week_label"].iloc[0] or ""
            scheduled_date = day_data["scheduled_date_au"].iloc[0]

            # Small spacer between days on the same page (not before the first)
            if not first_on_page:
                story.append(Spacer(1, 12))
            first_on_page = False

            story.append(Paragraph(
                f"<b>{week_label}</b>  |  Program Day {day_no}  |  AU Date: {scheduled_date}",
                styles["Heading3"],
            ))
            story.append(_day_table(day_data, styles))

        # Page break after every group except the last
        if page_idx < len(seen_keys) - 1:
            story.append(PageBreak())

    doc.build(story)
    return buffer.getvalue()
