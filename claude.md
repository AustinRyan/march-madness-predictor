# Project: March Madness Bracket Algorithm

## Prime Directive
Build everything completely and correctly. No shortcuts. No MVP.
No synthetic data. No mock data. No placeholders. No TODOs.
Production-grade system only.

## Data Rules
- ALL data loads from /data/ directory — files are already there
- Historical training: /data/historical/
- 2026 current season: /data/2026/
- Reference data: /data/reference/
- Never substitute fake data. If a file is missing STOP and say so.
- Use Pre-Tournament.AdjEM for historical training, not end-of-season values

## Build Rules
- Build ONE module at a time in spec order
- Test each module with real data before moving on
- Every function fully implemented — no stubs, no TODOs
- All models → /models/
- All outputs → /outputs/
- Never hardcode paths, use pathlib

## When You Hit a Blocker
STOP. Tell the user exactly what the problem is.
Do not silently work around it.
```

---

## Step 3 — Open Claude Code and Paste This
```
Read MARCH_MADNESS_PROMPT_V2.md in full before writing any code.

Then do the following in order:

1. Create a PROJECT_PLAN.md that breaks the full build into phases with
   specific tasks, file names, and dependencies between modules.
   Wait for my approval before proceeding.

2. After I approve, build ONE module at a time in this order:
   data_pipeline.py → features.py → model.py → upset_detector.py →
   pool_equity.py → simulator.py → optimizer.py → backend/app.py → frontend/

3. After completing each module:
   - Write a real test using actual data to verify it runs correctly
   - Show me the output
   - Ask if I want changes before moving to the next module

4. Do not skip ahead or build multiple modules at once.

## HARD RULES — Non-negotiable, override everything else:

- NO synthetic data. NO mock data. NO placeholder data. NO fake records.
  Every data point must come from the real CSV files in /data/.
  If a file is missing or a column doesn't exist, STOP and tell me —
  do not substitute fake data under any circumstance.

- NO shortcuts. NO MVP approach. NO "simplified version for now".
  NO "you can expand this later". Build every feature in the spec
  completely and correctly the first time.

- NO placeholder functions. NO TODO comments left in code.
  Every function must be fully implemented before moving on.

- If you hit a real technical blocker, STOP and tell me exactly what
  the problem is. Do not work around it silently.

Do not write any code yet. Start with PROJECT_PLAN.md only.