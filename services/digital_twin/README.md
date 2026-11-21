# Digital Twin

See what a proposed rule would have done to **past decisions** before an admin publishes it, and how the platform handles a **scam wave**.
Public API only (admin login). Read-only: it never calls `POST /rules/{id}/versions`; the only write is the backend's own `rule.simulate` audit row.

```
PYTHONPATH=. python -m services.digital_twin.twin --auto-handle-min 0.80 [--ask-more-min 0.60] [--scam-wave] [--seed-history]
```
- It replays only the `decide` step through the backend's `POST /rules/{id}/simulate` (stored inputs of each past AI decision) and turns the result into a verdict:
  - `REVIEW BEFORE PUBLISHING`: some cases would get **less** human oversight (e.g. `ask_more -> auto_handle`).
  - `TIGHTER`: cases go to a human instead (extra officer workload), none lose oversight.
  - `SAFE on history` / `NO DATA` (never claims "safe" when nothing could be replayed).
- `--scam-wave` sends 10 fictional messages (5 scam from lookalike/unknown senders, 5 genuine from official codes) to `POST /messages/check` and reports caught, unsure, missed and genuine-blocked-by-mistake. `unsure` is never counted as a catch.
- `--seed-history` is **opt-in and writes demo data**: files one claim per demo citizen (`s1-clean` ... `s7-autohandle`) so there are decisions to replay.
- Output: a summary on screen and `twin_report.json`. Env: `BASE`, `TWIN_ADMIN`, `TWIN_ADMIN_PASSWORD` (fake demo login).

Limit: the stub AI gives almost every claim the same confidence (0.81), so the demo shows threshold effects sharply; with the real AI the spread is wider. Cases without stored inputs (seeded samples) are skipped and counted.
