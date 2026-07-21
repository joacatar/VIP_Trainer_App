"""
Training APAC Dashboard — main entry point.
All data logic  →  db.py
Schedule seed   →  schedule_data.py
PDF export      →  pdf_export.py
"""
import datetime as dt
import sqlite3

import pandas as pd
import streamlit as st
from zoneinfo import ZoneInfo

from db import (
    get_conn,
    init_db,
    load_holidays,
    load_tasks,
    load_trainees,
    reset_plan_tasks,
    trainee_schedule_df,
)
from pdf_export import generate_trainee_pdf
from schedule_data import DEFAULT_PLAN

AU_TZ = ZoneInfo("Australia/Sydney")
EST_TZ = ZoneInfo("America/New_York")


# ── Helpers ──────────────────────────────────────────────────────────────────

def time_banner():
    now_au = dt.datetime.now(AU_TZ)
    now_est = now_au.astimezone(EST_TZ)
    st.info(
        f"🇦🇺 AU (primary): **{now_au.strftime('%Y-%m-%d %H:%M %Z')}**  |  "
        f"🇺🇸 EST: **{now_est.strftime('%Y-%m-%d %H:%M %Z')}**"
    )


def trainee_label(tid: int, df: pd.DataFrame) -> str:
    name = df.loc[df["id"] == tid, "name"]
    return f"{tid} — {name.iloc[0]}" if not name.empty else str(tid)


# ── Tab: Trainees ─────────────────────────────────────────────────────────────

def tab_trainees(conn: sqlite3.Connection):
    st.subheader("Trainee Management")

    # ── Add form ──
    with st.form("add_trainee", clear_on_submit=True):
        st.markdown("##### Add new trainee")
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Full name *")
        email = c2.text_input("Email")
        start_date = c3.date_input("Start date (AU)", value=dt.date.today())
        c4, c5 = st.columns(2)
        tz_pref = c4.selectbox("Timezone preference", ["Australia/Sydney", "America/New_York"])
        notes = c5.text_input("Notes")
        submitted = st.form_submit_button("➕ Add trainee", type="primary")

    if submitted:
        if name.strip():
            conn.execute(
                "INSERT INTO trainees(name, email, timezone_pref, start_date, notes) VALUES(?,?,?,?,?)",
                (name.strip(), email.strip(), tz_pref, start_date.isoformat(), notes.strip()),
            )
            conn.commit()
            st.success(f"Trainee **{name.strip()}** added.")
            st.rerun()
        else:
            st.error("Name is required.")

    # ── List & edit ──
    trainees_df = load_trainees(conn)
    if trainees_df.empty:
        st.info("No trainees yet — add one above.")
        return

    st.markdown("---")
    st.markdown("##### Existing trainees")
    st.dataframe(
        trainees_df[["id", "name", "email", "start_date", "timezone_pref", "active", "notes"]],
        use_container_width=True,
    )

    st.markdown("##### Edit / delete trainee")
    selected_id = st.selectbox(
        "Select trainee to edit",
        trainees_df["id"].tolist(),
        format_func=lambda x: trainee_label(x, trainees_df),
    )
    sel = conn.execute("SELECT * FROM trainees WHERE id = ?", (selected_id,)).fetchone()

    with st.form("edit_trainee"):
        c1, c2 = st.columns(2)
        ename = c1.text_input("Name", value=sel["name"])
        eemail = c2.text_input("Email", value=sel["email"] or "")
        c3, c4 = st.columns(2)
        estart = c3.date_input("Start date", value=dt.date.fromisoformat(sel["start_date"]))
        eactive = c4.checkbox("Active", value=bool(sel["active"]))
        enotes = st.text_area("Notes", value=sel["notes"] or "")
        csave, cdel = st.columns(2)
        save = csave.form_submit_button("💾 Save changes")
        delete = cdel.form_submit_button("🗑️ Delete trainee")

    if save:
        conn.execute(
            "UPDATE trainees SET name=?, email=?, start_date=?, notes=?, active=? WHERE id=?",
            (ename.strip(), eemail.strip(), estart.isoformat(), enotes.strip(), int(eactive), selected_id),
        )
        conn.commit()
        st.success("Trainee updated.")
        st.rerun()

    if delete:
        conn.execute("DELETE FROM trainees WHERE id = ?", (selected_id,))
        conn.execute("DELETE FROM task_comments WHERE trainee_id = ?", (selected_id,))
        conn.execute("DELETE FROM daily_actions WHERE trainee_id = ?", (selected_id,))
        conn.commit()
        st.warning("Trainee deleted.")
        st.rerun()


# ── Tab: Daily Actions ────────────────────────────────────────────────────────

def tab_daily_actions(conn: sqlite3.Connection):
    st.subheader("Daily Actions & Reminders")
    trainees_df = load_trainees(conn)
    t_options = [None] + (trainees_df["id"].tolist() if not trainees_df.empty else [])

    with st.form("add_action", clear_on_submit=True):
        st.markdown("##### Add action / reminder")
        c1, c2, c3, c4 = st.columns(4)
        tr_id = c1.selectbox(
            "Trainee (optional)",
            t_options,
            format_func=lambda x: "— General —" if x is None else trainee_label(x, trainees_df),
        )
        action_date = c2.date_input("Action date", dt.date.today())
        owner = c3.selectbox("Owner", ["LEADS", "TRAINER", "TRAINEE", "GENERAL"])
        status = c4.selectbox("Status", ["OPEN", "DONE", "BLOCKED"])
        title = st.text_input("Title *")
        details = st.text_area("Details")
        submitted = st.form_submit_button("➕ Add action", type="primary")

    if submitted:
        if title.strip():
            conn.execute(
                "INSERT INTO daily_actions(trainee_id, action_date, title, details, status, owner_type)"
                " VALUES(?,?,?,?,?,?)",
                (tr_id, action_date.isoformat(), title.strip(), details.strip(), status, owner),
            )
            conn.commit()
            st.success("Action added.")
            st.rerun()
        else:
            st.error("Title is required.")

    st.markdown("---")
    actions = pd.read_sql_query(
        """SELECT a.id, a.action_date, a.owner_type, a.title, a.details, a.status,
                  t.name AS trainee_name
           FROM daily_actions a
           LEFT JOIN trainees t ON t.id = a.trainee_id
           ORDER BY a.action_date DESC, a.status""",
        conn,
    )
    if actions.empty:
        st.info("No actions yet.")
        return

    today_str = dt.datetime.now(AU_TZ).date().isoformat()
    today_rows = actions[actions["action_date"] == today_str]

    if not today_rows.empty:
        st.markdown("#### 📅 Today (AU)")
        st.dataframe(today_rows, use_container_width=True)

    st.markdown("#### All actions")
    # Quick status update
    with st.expander("Update action status"):
        aid = st.selectbox("Action ID", actions["id"].tolist())
        new_status = st.selectbox("New status", ["OPEN", "DONE", "BLOCKED"], key="upd_status")
        if st.button("Update status"):
            conn.execute("UPDATE daily_actions SET status=? WHERE id=?", (new_status, aid))
            conn.commit()
            st.success("Status updated.")
            st.rerun()

    st.dataframe(actions, use_container_width=True)


# ── Tab: Schedule ─────────────────────────────────────────────────────────────

def tab_schedule(conn: sqlite3.Connection):
    st.subheader("Trainee Schedule")
    trainees_df = load_trainees(conn)
    if trainees_df.empty:
        st.info("Add a trainee first.")
        return

    selected_id = st.selectbox(
        "Select trainee",
        trainees_df["id"].tolist(),
        key="sched_trainee",
        format_func=lambda x: trainee_label(x, trainees_df),
    )
    sched = trainee_schedule_df(conn, selected_id)
    if sched.empty:
        st.warning("No schedule tasks found.")
        return

    sched["scheduled_date_est"] = pd.to_datetime(sched["scheduled_date_au"]).apply(
        lambda d: d.tz_localize(AU_TZ).tz_convert(EST_TZ).date()
    )

    # Filter by week
    weeks = ["All"] + sorted(sched["week_label"].dropna().unique().tolist())
    selected_week = st.selectbox("Filter by week", weeks)
    view = sched if selected_week == "All" else sched[sched["week_label"] == selected_week]

    st.dataframe(
        view[["week_label", "day_no", "scheduled_date_au", "scheduled_date_est",
              "time_window", "category", "title", "duration_hours", "comment"]],
        use_container_width=True,
    )

    st.markdown("---")
    tr_row = trainees_df.loc[trainees_df["id"] == selected_id].iloc[0]
    tr_name = tr_row["name"]
    tr_start = tr_row["start_date"]

    pdf_bytes = generate_trainee_pdf(tr_name, tr_start, sched)
    st.download_button(
        label="⬇️ Export full schedule PDF",
        data=pdf_bytes,
        file_name=f"{tr_name.replace(' ', '_')}_schedule.pdf",
        mime="application/pdf",
    )


# ── Tab: Comments ─────────────────────────────────────────────────────────────

def tab_comments(conn: sqlite3.Connection):
    st.subheader("Task Comments")
    trainees_df = load_trainees(conn)
    tasks = load_tasks(conn)

    if trainees_df.empty or tasks.empty:
        st.info("Need both trainees and tasks before adding comments.")
        return

    c1, c2 = st.columns(2)
    tr_id = c1.selectbox(
        "Trainee",
        trainees_df["id"].tolist(),
        key="comment_tr",
        format_func=lambda x: trainee_label(x, trainees_df),
    )
    task_id = c2.selectbox(
        "Task",
        tasks["id"].tolist(),
        format_func=lambda x: (
            f"Day {int(tasks.loc[tasks['id']==x, 'day_no'].iloc[0])} — "
            f"{tasks.loc[tasks['id']==x, 'title'].iloc[0]}"
        ),
    )

    existing = conn.execute(
        "SELECT comment FROM task_comments WHERE trainee_id=? AND task_id=?",
        (tr_id, task_id),
    ).fetchone()

    comment = st.text_area("Comment", value=existing["comment"] if existing else "", height=120)

    if st.button("💾 Save comment", type="primary"):
        conn.execute(
            """INSERT INTO task_comments(trainee_id, task_id, comment) VALUES(?,?,?)
               ON CONFLICT(trainee_id, task_id)
               DO UPDATE SET comment=excluded.comment, updated_at=CURRENT_TIMESTAMP""",
            (tr_id, task_id, comment.strip()),
        )
        conn.commit()
        st.success("Comment saved.")

    # Show all comments for this trainee
    st.markdown("---")
    st.markdown("##### All comments for selected trainee")
    all_comments = pd.read_sql_query(
        """SELECT tc.task_id, pt.day_no, pt.title, tc.comment, tc.updated_at
           FROM task_comments tc
           JOIN plan_tasks pt ON pt.id = tc.task_id
           WHERE tc.trainee_id = ?
           ORDER BY pt.day_no, pt.sort_order""",
        conn,
        params=(tr_id,),
    )
    if all_comments.empty:
        st.info("No comments yet for this trainee.")
    else:
        st.dataframe(all_comments, use_container_width=True)


# ── Tab: Admin / Holidays ─────────────────────────────────────────────────────

def tab_admin(conn: sqlite3.Connection):
    st.subheader("Admin & Holidays")

    # ── Holidays ──
    st.markdown("##### Holidays")
    st.caption("Weekends are always skipped. Add dates here to skip additional days.")

    with st.form("holiday_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        hdate = c1.date_input("Holiday date (AU)", value=dt.date.today())
        reason = c2.text_input("Reason")
        if st.form_submit_button("➕ Add holiday"):
            try:
                conn.execute(
                    "INSERT INTO holidays(holiday_date, reason) VALUES(?,?)",
                    (hdate.isoformat(), reason.strip()),
                )
                conn.commit()
                st.success("Holiday added.")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("That date is already marked as a holiday.")

    holidays_df = pd.read_sql_query("SELECT * FROM holidays ORDER BY holiday_date", conn)
    if not holidays_df.empty:
        st.dataframe(holidays_df, use_container_width=True)
        hid = st.selectbox("Select holiday to delete", holidays_df["id"].tolist(),
                           format_func=lambda x: holidays_df.loc[holidays_df["id"]==x, "holiday_date"].iloc[0])
        if st.button("🗑️ Delete holiday"):
            conn.execute("DELETE FROM holidays WHERE id=?", (hid,))
            conn.commit()
            st.warning("Holiday removed.")
            st.rerun()

    st.markdown("---")

    # ── Plan tasks viewer + add ──
    st.markdown("##### Plan Tasks")
    plan_df = load_tasks(conn)
    st.dataframe(plan_df, use_container_width=True)

    with st.expander("➕ Add custom plan task"):
        with st.form("add_plan_task", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            day_no = c1.number_input("Day number", min_value=0, value=0, step=1)
            week_label = c2.text_input("Week label", "Week X")
            category = c3.selectbox(
                "Category",
                ["GENERAL", "LEADS", "TRAINER", "TRAINEE", "ASSIGNMENT", "BREAK"],
            )
            c4, c5, c6 = st.columns(3)
            ptitle = c4.text_input("Task title")
            duration = c5.text_input("Duration hours")
            time_window = c6.text_input("Time window (e.g. 6:00 PM - 7:00 PM)")
            sort_order = st.number_input("Sort order", min_value=0, value=1, step=1)
            if st.form_submit_button("Add task"):
                dur = float(duration) if duration.strip() else None
                conn.execute(
                    "INSERT INTO plan_tasks(day_no, week_label, time_window, duration_hours, title, category, sort_order)"
                    " VALUES(?,?,?,?,?,?,?)",
                    (int(day_no), week_label.strip(), time_window.strip(), dur,
                     ptitle.strip(), category, int(sort_order)),
                )
                conn.commit()
                st.success("Task added.")
                st.rerun()

    st.markdown("---")
    st.markdown("##### Danger Zone")
    if st.button("🔄 Reset default schedule (plan tasks only — trainees kept)"):
        reset_plan_tasks()
        st.success("Default schedule restored. Trainee data is untouched.")
        st.rerun()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(page_title="Training APAC Dashboard", layout="wide")
    init_db()  # safe — never wipes data
    conn = get_conn()

    st.title("🏋️ Training APAC Dashboard")
    time_banner()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "👤 Trainees",
        "📋 Daily Actions",
        "📅 Schedule",
        "💬 Comments",
        "⚙️ Admin / Holidays",
    ])

    with tab1:
        tab_trainees(conn)
    with tab2:
        tab_daily_actions(conn)
    with tab3:
        tab_schedule(conn)
    with tab4:
        tab_comments(conn)
    with tab5:
        tab_admin(conn)

    conn.close()


if __name__ == "__main__":
    main()

