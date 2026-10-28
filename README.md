# OpenSky Medallion – Live Flight Data Pipeline

End-to-end data engineering project: live aircraft positions over India from the
OpenSky Network API, processed through **Bronze → Silver → Gold** layers.

**Current stage: Week 1 – Bronze ingestion (local)**

```
OpenSky API ──(every 5 min)──► run_ingest.py ──► data/bronze/opensky/states/date=…/hour=…/run_*.json
                                 │
                                 ├─ OAuth2 token cache + auto-refresh
                                 ├─ retries: 5xx backoff, 429 wait, 401 re-auth
                                 └─ metadata envelope (run_id, record_count, credits left…)
```

## Project structure

```
opensky-medallion/
├── src/
│   ├── common/
│   │   ├── config.py          # settings from .env, India bounding box
│   │   └── logger.py
│   └── ingestion/
│       ├── auth.py            # OAuth2 client-credentials token manager
│       ├── opensky_client.py  # /states/all with retry + rate-limit handling
│       ├── writer.py          # raw JSON → partitioned Bronze folder
│       ├── run_ingest.py      # entry point (once or --loop)
│       └── inspect_bronze.py  # see what landed
├── tests/test_ingestion.py    # mocked API tests, no network needed
├── .env.example
└── requirements.txt
```

---

## Week 1 plan (Oct 29 – Nov 4, 1–2 hrs/day)

### Day 1 – Thu Oct 29: Tools and repo
1. Install **Python 3.11+**, **Git**, **VS Code**, and **Docker Desktop** (Docker is needed from Week 2; install now so it's ready).
2. Create an empty GitHub repo named `opensky-medallion` (public – it's your portfolio).
3. Unzip this project, then:
   ```bash
   cd opensky-medallion
   git init && git add . && git commit -m "Week 1 starter"
   git branch -M main
   git remote add origin https://github.com/<your-username>/opensky-medallion.git
   git push -u origin main
   ```
4. Create a virtual environment and install packages:
   ```bash
   python -m venv .venv
   # Windows:      .venv\Scripts\activate
   # Mac / Linux:  source .venv/bin/activate
   pip install -r requirements.txt
   ```
5. Run the tests – they use fake responses, so they pass without an account:
   ```bash
   pytest -v
   ```
   ✅ Done when: 7 tests pass and the code is on GitHub.

### Day 2 – Fri Oct 30: OpenSky account and token
1. Register at opensky-network.org, then open your **Account** page and create an **API client**. Copy the client ID and secret.
2. `cp .env.example .env` (Windows: `copy .env.example .env`) and paste both values in. `.env` is git-ignored.
3. Get a token by hand once, so you understand OAuth2 client credentials (use Git Bash on Windows):
   ```bash
   curl -s -X POST "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token" \
     -d "grant_type=client_credentials" -d "client_id=YOUR_ID" -d "client_secret=YOUR_SECRET"
   ```
   Note `access_token` and `expires_in` in the reply.
4. Read `src/ingestion/auth.py` and match it to what you just did.
   ✅ Done when: you get a token back, and can explain why we refresh 60s before expiry.

### Day 3 – Sat Oct 31: First real API call
1. Run one ingestion:
   ```bash
   python -m src.ingestion.run_ingest
   ```
2. Open the JSON file it created under `data/bronze/…` and look at `metadata` and `payload.states`.
3. Read `opensky_client.py`. Understand the four cases: 200, 401, 429, 5xx.
   ✅ Done when: a Bronze file exists with a few hundred aircraft in it.

### Day 4 – Sun Nov 1: Understand the Bronze design
1. Read `writer.py`. Write answers in your own notes (interview prep):
   - Why store the payload **untouched**? (replay, audit, schema changes)
   - Why partition by `date=/hour=`? (Spark partition pruning in Week 3)
   - Why write to `.tmp` then rename? (atomic writes – no half-read files)
   - Why a metadata envelope? (lineage: run_id, record_count, credits left)
2. Run `python -m src.ingestion.inspect_bronze` to see the 17 state-vector fields decoded.
   ✅ Done when: you can explain each Bronze design choice in one sentence.

### Day 5 – Mon Nov 2: Failure handling
1. Read the tests in `tests/test_ingestion.py`, one per failure case.
2. Break things on purpose and watch the logs:
   - Put a wrong secret in `.env` → token request fails with a clear error.
   - Set `OPENSKY_API_BASE_URL=https://opensky-network.org/apix` → 404, not retried.
3. Restore `.env`. Add one test of your own (idea: 401 → token refresh → 200).
   ✅ Done when: your new test passes.

### Day 6 – Tue Nov 3: Collect real data
1. Start the loop and leave the laptop on for a few hours:
   ```bash
   python -m src.ingestion.run_ingest --loop
   ```
2. Run `python -m src.ingestion.inspect_bronze`. Check:
   - runs are ~5 minutes apart
   - aircraft count changes by time of day
   - `credits_left` drops by a few per call (you have ~4,000/day)
   ✅ Done when: you have 20+ runs of data saved.

### Day 7 – Wed Nov 4: Document and push
1. Add to this README: one paragraph "What I learned in Week 1" and a screenshot of the logs.
2. Commit and push:
   ```bash
   git add . && git commit -m "Week 1: Bronze ingestion complete" && git push
   ```
   ✅ Done when: the repo on GitHub shows the code, tests and your notes.

---

## Interview talking points from Week 1
- OAuth2 client-credentials flow with proactive token refresh
- Rate-limit handling (credit budget, `429` + `Retry-After`)
- Idempotent, immutable raw layer with lineage metadata
- Hive-style partitioning and atomic file writes
- Testable design: HTTP session and `sleep` injected, so tests run without network

## Next: Week 2
Docker Compose with **MinIO + Airflow**. A `MinioWriter` replaces `LocalBronzeWriter`
(same `write()` method), and an Airflow DAG calls `ingest_once()` every 5 minutes.
