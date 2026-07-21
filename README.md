# CT Initial Training Tracker

Streamlit and Supabase foundation for CT disposition and CT planning training.

## Project structure

```text
ct_training_tracker/
├── app.py                         # Thin Streamlit entrypoint
├── pyproject.toml                 # Package and tool configuration
├── src/ct_training_tracker/
│   ├── application.py             # Application orchestration
│   ├── auth.py                    # Authentication/session lifecycle
│   ├── config.py                  # Typed configuration
│   ├── metrics.py                 # Pure metric calculations
│   ├── models.py                  # Shared application types
│   ├── repository.py              # Supabase data-access boundary
│   └── views/                     # Trainer, trainee, and login UI
└── tests/                         # Unit tests
```

Streamlit views do not issue database queries directly. Data access stays behind
`TrainingRepository`, while reusable business calculations remain independent of
Streamlit and Supabase.

## Milestones

1. **Foundation (current):** authentication, roles, trainees, 32 scheduled cases,
   three independent file requirements per case, dashboard metrics, and audit events.
2. **Homework and submissions:** assign homework, upload/version the two PDFs and OV,
   accept files independently, and request targeted replacements.
3. **Reviews and corrections:** revision history, the eight fixed review sections,
   correction roll-forward, and pasted screenshots.
4. **Questions:** trainee case threads, trainer queue, screenshot attachments, and
   resolved/unresolved tracking.
5. **Metrics and forecasting:** turnaround times, first-pass acceptance, recurring
   corrections, workload, and estimated completion.
6. **Optional notebook and assistant:** trainee notes first; an assistant can later
   use approved training material and trainer-reviewed answers.

## Supabase setup

1. Create a Supabase project.
2. Apply `supabase/migrations/20260721021500_create_ct_training_foundation.sql`.
3. Create the first account in Supabase Auth.
4. Promote that account once in the SQL editor:

   ```sql
   update public.profiles
   set role = 'trainer'
   where id = '<auth-user-id>';
   ```

   New accounts default to `trainee`; application users cannot promote themselves.

5. Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` and enter the
   project URL and publishable key. Never put a secret or service-role key in the app.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

For development:

```bash
pip install -r requirements-dev.txt
ruff check .
pytest
```

Creating a trainee automatically creates:

- Set 1, cases 1–16
- Set 2, cases 1–16
- Two PDF requirements and one OV requirement for each case
- Due dates derived from the APAC training day and adjusted for weekends and holidays

The trainee portal becomes available after the trainer links a trainee row to that
person's Supabase Auth user ID. Account invitation/linking UI is planned for the next
milestone.
