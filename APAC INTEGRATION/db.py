import datetime as dt
import sqlite3
from pathlib import Path

import pandas as pd

from schedule_data import DEFAULT_PLAN

DB_PATH = Path(__file__).parent / "training_dashboard.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Safe init — only creates tables and seeds plan if they don't already exist.
    Never drops data, so adding trainees always persists across reruns."""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS trainees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            timezone_pref TEXT DEFAULT 'Australia/Sydney',
            start_date TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS holidays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            holiday_date TEXT UNIQUE NOT NULL,
            reason TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS plan_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_no INTEGER NOT NULL,
            week_label TEXT,
            time_window TEXT,
            duration_hours REAL,
            title TEXT NOT NULL,
            category TEXT DEFAULT 'GENERAL',
            sort_order INTEGER DEFAULT 0
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS task_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trainee_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            comment TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(trainee_id, task_id),
            FOREIGN KEY(trainee_id) REFERENCES trainees(id),
            FOREIGN KEY(task_id) REFERENCES plan_tasks(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trainee_id INTEGER,
            action_date TEXT NOT NULL,
            title TEXT NOT NULL,
            details TEXT,
            status TEXT DEFAULT 'OPEN',
            owner_type TEXT DEFAULT 'LEADS',
            FOREIGN KEY(trainee_id) REFERENCES trainees(id)
        )
        """
    )

    # Seed plan tasks only if the table is empty
    cur.execute("SELECT COUNT(*) c FROM plan_tasks")
    if cur.fetchone()["c"] == 0:
        cur.executemany(
            """
            INSERT INTO plan_tasks(day_no, week_label, time_window, duration_hours, title, category, sort_order)
            VALUES(:day, :week, :time_window, :duration, :title, :category, :sort)
            """,
            DEFAULT_PLAN,
        )

    conn.commit()
    conn.close()


def reset_plan_tasks():
    """Wipe and re-seed only the plan_tasks table. Trainees and other data are untouched."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM plan_tasks")
    cur.executemany(
        """
        INSERT INTO plan_tasks(day_no, week_label, time_window, duration_hours, title, category, sort_order)
        VALUES(:day, :week, :time_window, :duration, :title, :category, :sort)
        """,
        DEFAULT_PLAN,
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def load_trainees(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM trainees ORDER BY active DESC, name", conn)


def load_tasks(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        """SELECT id, day_no, week_label, time_window, duration_hours, title, category, sort_order
           FROM plan_tasks
           ORDER BY day_no, sort_order, id""",
        conn,
    )


def load_holidays(conn: sqlite3.Connection) -> list:
    return conn.execute("SELECT * FROM holidays ORDER BY holiday_date").fetchall()


def add_workdays(start_date: dt.date, offset: int, holidays: set) -> dt.date:
    current = start_date
    count = 0
    while count < offset:
        current += dt.timedelta(days=1)
        if current.weekday() < 5 and current not in holidays:
            count += 1
    return current


def working_day_map(start_date: dt.date, max_day: int, holidays: set) -> dict:
    return {day: add_workdays(start_date, day, holidays) for day in range(0, max_day + 1)}


def trainee_schedule_df(conn: sqlite3.Connection, trainee_id: int) -> pd.DataFrame:
    tr = conn.execute("SELECT * FROM trainees WHERE id = ?", (trainee_id,)).fetchone()
    if not tr:
        return pd.DataFrame()
    holidays = {dt.date.fromisoformat(r["holiday_date"]) for r in load_holidays(conn)}
    tasks = load_tasks(conn)
    if tasks.empty:
        return tasks
    date_map = working_day_map(
        dt.date.fromisoformat(tr["start_date"]), int(tasks["day_no"].max()), holidays
    )
    comments = pd.read_sql_query(
        "SELECT task_id, comment FROM task_comments WHERE trainee_id = ?",
        conn,
        params=(trainee_id,),
    )
    merged = tasks.copy()
    merged["scheduled_date_au"] = merged["day_no"].map(date_map)
    merged["scheduled_date_au"] = pd.to_datetime(merged["scheduled_date_au"]).dt.date
    merged = merged.merge(comments, left_on="id", right_on="task_id", how="left")
    return merged

