"""Trainer analytics / forecasting presentation."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ct_training_tracker.analytics import (
    build_training_analytics,
    format_days,
    format_rate,
)
from ct_training_tracker.repository import TrainingRepository
from ct_training_tracker.revisions import section_label


def render_training_analytics(repository: TrainingRepository) -> None:
    st.subheader("Performance & forecast")
    st.caption(
        "Derived from timestamped tracking events and published corrections — "
        "not from mutable status alone."
    )

    try:
        case_rows = repository.list_case_training_metrics()
        section_rows = repository.list_correction_section_stats()
    except Exception as exc:
        st.warning(f"Metrics views are not available yet: {exc}")
        return

    analytics = build_training_analytics(
        case_rows,
        section_rows,
        label_for=section_label,
    )

    with st.container(horizontal=True, gap="small"):
        st.metric(
            "First-pass rate",
            format_rate(analytics.first_pass_rate),
            help=(
                f"{analytics.first_pass_cases} of {analytics.cases_with_submit} "
                "submitted/approved cases closed without replacement or resubmit."
            ),
            border=True,
        )
        st.metric(
            "Published revisions",
            analytics.published_revisions,
            help="Count of revision_published events across all cases.",
            border=True,
        )
        st.metric(
            "Resubmissions",
            analytics.resubmission_events,
            help="Extra package submits after the first submit on a case.",
            border=True,
        )
        st.metric(
            "Trainee turnaround",
            format_days(analytics.avg_trainee_turnaround_days),
            help="Average days from homework assigned to first package submit.",
            border=True,
        )

    with st.container(horizontal=True, gap="small"):
        st.metric(
            "Trainer turnaround",
            format_days(analytics.avg_trainer_turnaround_days),
            help=(
                "Average days from first package submit to first published "
                "review or approval."
            ),
            border=True,
        )
        forecast = analytics.forecast
        st.metric(
            "Est. completion",
            (
                forecast.estimated_date.isoformat()
                if forecast.estimated_date
                else "—"
            ),
            help=forecast.explanation,
            border=True,
        )
        st.metric(
            "Remaining cases",
            forecast.remaining_cases,
            help="Cases not yet approved in the tracked cohort.",
            border=True,
        )
        st.metric(
            "Avg days / case",
            format_days(forecast.avg_days_per_approved_case),
            help="Observed assign→approve (or submit→approve) duration.",
            border=True,
        )

    with st.container(border=True):
        st.markdown("**How the forecast is calculated**")
        st.caption(forecast.explanation)
        if forecast.avg_days_per_approved_case is not None:
            st.caption(
                "Formula: today + (average observed days per approved case × "
                "remaining open cases)."
            )

    if analytics.section_hotspots:
        st.markdown("**Recurring corrections by section**")
        hotspot_frame = pd.DataFrame(
            [
                {
                    "Section": item.label,
                    "Corrections": item.correction_count,
                    "Open": item.open_count,
                    "Rolled forward": item.rolled_forward_count,
                }
                for item in analytics.section_hotspots
            ]
        )
        st.dataframe(hotspot_frame, hide_index=True, width="stretch")
    else:
        st.caption("No published section corrections yet.")

    if analytics.planned_vs_actual:
        with st.expander("Planned vs actual dates", expanded=False):
            plan_frame = pd.DataFrame(analytics.planned_vs_actual).rename(
                columns={
                    "trainee_name": "Trainee",
                    "set_no": "Set",
                    "catalog_label": "Case",
                    "planned_due": "Planned due",
                    "actual_approved": "Approved on",
                    "days_delta": "Delta (days)",
                }
            )
            display_cols = [
                col
                for col in [
                    "Trainee",
                    "Set",
                    "Case",
                    "Planned due",
                    "Approved on",
                    "Delta (days)",
                ]
                if col in plan_frame.columns
            ]
            st.dataframe(
                plan_frame[display_cols],
                hide_index=True,
                width="stretch",
            )
            st.caption(
                "Negative delta means approved earlier than the homework due date."
            )
