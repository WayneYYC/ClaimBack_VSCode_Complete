# ClaimBack coding instructions

- This is a fictional sample-data fintech hackathon product. Do not add real card/payment transfer operations or submit real chargebacks.
- Prioritize a running FastAPI + static web frontend with `./run.sh` over complex deployment stacks. Use no frontend build tools.
- Both modes must work: Demo must run offline with templates; Live must call Nicrron and optionally upload PRISM traces. Never label Demo runs as real sponsor usage.
- PRISM code lives in `backend/prism.py`; it sends observed step spans and a session trace via documented PRISM HTTP API. Do not synthesize success or claim a Root Cause cluster without checking the real PRISM dashboard.
- Keep credentials only in `.env`; never write them into browser JS or versioned files.
- A deliberately failing v1 for missing tracking fields exists solely to demonstrate regression and root-cause analysis. v2 must handle missing evidence conservatively.
- Run `python -m pytest -q tests` and check `node --check frontend/app.js` after editing.
