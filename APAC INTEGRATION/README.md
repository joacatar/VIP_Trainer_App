# Training APAC Dashboard (Streamlit)

A local-first dashboard to manage trainees, training schedules, reminders/actions, comments, and per-trainee PDF exports.

## Features

- Trainee CRUD (add/edit/remove)
- Start-date based schedule generation
- Weekend skip + configurable holiday skip
- AU primary time with EST secondary display
- Daily actions/reminders (LEADS/TRAINER/TRAINEE/GENERAL)
- Comments on any task section per trainee
- One PDF export per trainee schedule
- Editable plan tasks in app

## Local run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## Notes

- Database file is created automatically as `training_dashboard.db` in project root.
- You can migrate to cloud storage later by replacing SQLite calls with your target backend.

