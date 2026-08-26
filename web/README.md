# VIP Trainer — React web app

React remake of the CT Planning training tracker. Talks **directly** to
Supabase (Auth + Postgres RLS + RPCs + Storage). The Streamlit app in the
repo root remains the live client until cutover.

## Stack

- Vite + React 19 + TypeScript
- React Router
- TanStack Query
- Tailwind CSS v4
- `@supabase/supabase-js` (publishable key only)

## Setup

```bash
cd web
cp .env.example .env.local
# Set VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY (Dev first)
npm install
npm run dev
```

Open http://localhost:5173

## Scripts

| Command | Purpose |
| --- | --- |
| `npm run dev` | Local Vite server |
| `npm run build` | Production build |
| `npm test` | Vitest (ownership + label domain rules) |
| `npm run preview` | Preview production build |

## Routes

| Path | Role |
| --- | --- |
| `/login` | Public |
| `/trainer`, `/trainer/cases`, `/trainer/cases/:id`, `/trainer/trainees` | Trainer |
| `/trainee`, `/trainee/cases/:id`, `/trainee/questions` | Trainee |

## Domain rules (do not reinvent)

See `.claude/brain/gotchas.md` and `src/lib/domain/`:

- `not_started` is trainer-owned; trainees never see it as work.
- Leave `not_started` only via `assign_homework` RPC.
- Phase-2 VIP fallback must never use the phase-1 order-number map.

## Deploy

Point Vercel/Netlify at `web/` with env vars from Dev. Add the site URL to
Supabase Auth → Redirect URLs. Keep Streamlit running until cutover is
verified.
