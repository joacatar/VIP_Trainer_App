"""Trainer analytics / forecasting presentation (Feature 7)."""

from __future__ import annotations

from datetime import date
from statistics import mean

import pandas as pd
import streamlit as st

from ct_training_tracker.analytics import format_rate
from ct_training_tracker.case_labels import (
    case_catalog_label,
    case_label,
    case_phase_no,
)
from ct_training_tracker.metrics import (
    avg_days_per_case_by_trainee,
    est_completion_by_trainee,
    first_pass_rate_by_trainee,
    first_pass_trend,
    hardest_cases,
    recurring_issues,
    regression_rate,
    regression_rate_by_trainee,
    section_correction_rates,
)
from ct_training_tracker.repository import TrainingRepository
from ct_training_tracker.revisions import section_label


def render_training_analytics(
    repository: TrainingRepository,
    *,
    include_test: bool = False,
) -> None:
    st.subheader("Performance & forecast")
    st.caption(
        "Coach where it matters — first-pass trend, regressions, and "
        "recurring issues from correction threads."
    )

    try:
        case_rows = repository.list_case_training_metrics()
        threads = repository.list_all_correction_threads()
    except Exception as exc:
        st.warning(f"Metrics views are not available yet: {exc}")
        return

    if not include_test:
        case_rows = [row for row in case_rows if not row.get("trainee_is_test")]
        live_case_ids = {
            str(row.get("case_id") or row.get("id") or "") for row in case_rows
        }
        threads = [
            thread
            for thread in threads
            if str(thread.get("case_id") or "") in live_case_ids
        ]

    # Normalize id field used by metrics helpers.
    cases = [
        {
            **row,
            "id": row.get("case_id") or row.get("id"),
        }
        for row in case_rows
    ]
    trainee_names = {
        str(row.get("trainee_id") or ""): str(row.get("trainee_name") or "Trainee")
        for row in cases
    }

    rates = first_pass_rate_by_trainee(threads, cases)
    trends = first_pass_trend(threads, cases, window=10)
    overall_rate = mean(rates.values()) if rates else None
    # Aggregated sparkline: mean of each window index across trainees.
    spark: list[float] = []
    if trends:
        max_len = max(len(series) for series in trends.values())
        for index in range(max_len):
            points = [
                series[index]
                for series in trends.values()
                if index < len(series)
            ]
            if points:
                spark.append(mean(points))
    delta = None
    if len(spark) >= 2:
        delta = spark[-1] - spark[-2]

    regressions = regression_rate(threads)
    forecasts = est_completion_by_trainee(cases, today=date.today())
    hardest = hardest_cases(threads, cases, top_n=5)
    recurring = recurring_issues(threads, min_cases=3, top_n=10)
    avg_days = avg_days_per_case_by_trainee(cases)
    regressions_by = regression_rate_by_trainee(threads, cases)
    section_rows = section_correction_rates(threads, cases)

    case_label_by_id = {
        str(row.get("id") or ""): (
            f"Set {row.get('set_no')} · Case {case_catalog_label(row)}"
            if row.get("set_no") and case_phase_no(row) == 1
            else case_label(row)
        )
        for row in cases
    }

    top = st.columns(3, gap="medium")
    with top[0]:
        st.metric(
            "First-pass rate",
            format_rate(overall_rate),
            delta=(f"{delta:+.0%}" if delta is not None else None),
            help="Share of cases with zero correction threads ever raised.",
            border=True,
        )
        if spark:
            st.caption("Trend across recent case windows")
            st.line_chart({"First-pass": spark}, height=120)
    with top[1]:
        st.metric(
            "Regression rate",
            format_rate(regressions),
            help=(
                "Share of threads that were resolved, then marked still open "
                "again."
            ),
            border=True,
        )
        st.caption("Reopened after a resolve — coach the fragile ones.")
    with top[2]:
        with st.container(border=True):
            st.markdown("**Est. completion**")
            if not forecasts:
                st.caption("No trainee pace data yet.")
            else:
                for trainee_id, when in sorted(
                    forecasts.items(),
                    key=lambda item: trainee_names.get(item[0], item[0]),
                ):
                    name = trainee_names.get(trainee_id, trainee_id)
                    stamp = when.isoformat() if when else "—"
                    st.markdown(f"{name} · **{stamp}**")

    st.markdown("**Hardest cases**")
    if not hardest:
        st.caption("No correction threads yet.")
    else:
        for index, row in enumerate(hardest, start=1):
            count = int(row["count"])
            if count >= 10:
                color = "red"
            elif count >= 5:
                color = "orange"
            else:
                color = "gray"
            label = case_label_by_id.get(row["case_id"], row["case_id"])
            trainee = row.get("trainee") or "Trainee"
            st.markdown(
                f"{index}. **{label}** · {trainee} · "
                f":{color}-badge[{count} corrections]"
            )

    st.markdown("**Recurring issues across trainees**")
    if not recurring:
        st.caption("No issues shared across 3+ cases yet.")
    else:
        for row in recurring:
            text = str(row["normalized_text"])
            display = text if len(text) <= 60 else text[:57] + "…"
            badge = (
                " · :blue-badge[Resource candidate]"
                if int(row["case_count"]) >= 3
                else ""
            )
            st.markdown(
                f"**{display}** · {row['case_count']} cases{badge}"
            )

    st.markdown("**By trainee**")
    table_rows = []
    for trainee_id, name in sorted(
        trainee_names.items(), key=lambda item: item[1]
    ):
        table_rows.append(
            {
                "Trainee": name,
                "First-pass": format_rate(rates.get(trainee_id)),
                "Avg days/case": (
                    f"{avg_days[trainee_id]:.1f}"
                    if avg_days.get(trainee_id) is not None
                    else "—"
                ),
                "Regression": format_rate(regressions_by.get(trainee_id, 0.0)),
            }
        )
    if table_rows:
        st.dataframe(pd.DataFrame(table_rows), hide_index=True, width="stretch")
    else:
        st.caption("No trainees in this cohort.")

    with st.container(border=True):
        st.markdown("**How the forecast is calculated**")
        st.caption(
            "Per trainee: today + (average observed days per that trainee's "
            "approved cases × their remaining open cases). Uses assign→approve "
            "when available, otherwise submit→approve."
        )

    st.markdown("**Recurring corrections by section**")
    if section_rows and any(row["correction_count"] for row in section_rows):
        hotspot_frame = pd.DataFrame(
            [
                {
                    "Section": section_label(row["section_key"]),
                    "Corrections": row["correction_count"],
                    "Open": row["open_count"],
                    "% of cases": f"{row['case_share']:.0%}",
                }
                for row in section_rows
                if row["correction_count"]
            ]
        )
        st.dataframe(hotspot_frame, hide_index=True, width="stretch")
    else:
        st.caption("No published section corrections yet.")
