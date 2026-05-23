# Sample FastAPI Repo (DevPilot demo target)

A minimal product catalog + search API used as an ingestion/agent target for
DevPilot AI.

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
pytest -q
```

Good demo tasks to run against this repo in DevPilot:

- `Add a health check endpoint`
- `Add Redis caching to the product search API`
- `Add input validation to the search endpoint`
- `Add pagination to the product list`
- `Add structured logging`
- `Add error handling to product lookup`
