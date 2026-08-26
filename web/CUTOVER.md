# Cutover checklist — React remake

Do not point real trainees at React until every box below is green.

## Pre-deploy

- [ ] `cd web && npm test && npm run build` pass on `feature/react-remake`
- [ ] `web/.env.local` / Vercel env use **Dev** publishable key only
- [ ] Supabase Auth → Redirect URLs includes the React site URL
- [ ] Trainer + trainee can sign in on the deployed URL

## Smoke (Dev accounts)

- [ ] Trainer dashboard loads progress / needs attention / questions
- [ ] Assign a `not_started` case via Assign → status becomes `assigned`
- [ ] Trainee sees the assigned case; does **not** see other `not_started` cases
- [ ] Trainee saves OneDrive links and submits for review
- [ ] Trainer raises a correction, publishes feedback, approves a package
- [ ] Phase 1 / Live cases selector works when `phase_2_started_on` is set
- [ ] Phase-2 case with null `order_number` does **not** show a phase-1 VIP number

## Cutover

- [ ] Announce React URL to trainer + trainees
- [ ] Keep Streamlit up for 1–2 weeks as fallback
- [ ] Update `docs/environments.md` with the live React URL
- [ ] Mark Streamlit as legacy in `CLAUDE.md` / brain when React is sole client
