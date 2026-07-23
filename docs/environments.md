# Dev / Prod Supabase environments

## Active projects

| Role | Supabase name | Project ref | API URL | Status |
|------|---------------|-------------|---------|--------|
| **Dev** | VIP Trainer | `pqwudxopjfkflpzgmvqk` | `https://pqwudxopjfkflpzgmvqk.supabase.co` | ACTIVE |
| **Prod** | CT-Tracker-Prod | `lbieleiwxkbtiqtjrjgd` | `https://lbieleiwxkbtiqtjrjgd.supabase.co` | ACTIVE (empty schema applied) |

Prod has the full CT Tracker schema (12 migrations), `case-files` bucket, and **zero user data**.

## Streamlit secrets

Local development should point at **Dev**. Production Streamlit Cloud apps should point at **Prod**.

### Dev (local / branch `dev`)

```toml
SUPABASE_URL = "https://pqwudxopjfkflpzgmvqk.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "<Dev anon or publishable key from dashboard>"
```

### Prod (Streamlit Cloud app on `main`)

```toml
SUPABASE_URL = "https://lbieleiwxkbtiqtjrjgd.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "<Prod anon or publishable key from dashboard>"
```

Get keys from: Supabase Dashboard → Project Settings → API  
(or MCP `get_publishable_keys`). Prefer the modern `sb_publishable_…` key; legacy `anon` JWT also works.

## Auth note

Dev and Prod have **separate Auth**. Accounts and passwords do not carry over.

1. Create the trainer user in **Prod** Auth (email/password).
2. Promote that user in the Prod SQL editor:

```sql
update public.profiles
set role = 'trainer',
    full_name = 'Your Name'
where id = '<auth-user-uuid>';
```

3. Add real trainees only in Prod. Keep test accounts in Dev.

## Git / Streamlit Cloud mapping (recommended)

| Git branch | Streamlit app | Supabase secrets |
|------------|---------------|------------------|
| `dev` / feature branches | Dev URL | VIP Trainer (Dev) |
| `main` | Prod URL | CT-Tracker-Prod |

## Paused projects (free-tier slot)

To create Prod under the free **2 active projects** limit, **ordenes-medicas**
(`bypjgmnpzxmikiqxqmfs`) was paused. Restore it from the Supabase dashboard when needed.

Other projects were already `INACTIVE` and left as-is.
