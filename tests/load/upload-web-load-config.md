# Upload Web — Load Test Configuration

## Overview

Load test targeting 30 RPS sustained for 30 minutes against the Upload Web
API.  Each virtual user executes the full upload flow (session → 3 files →
preflight → confirm).

## How to Run

```bash
# Start a local instance (or point to staging)
export UPLOAD_WEB_HOST=http://localhost:8000

# Run headless with 30 concurrent users, ramp-up of 5/s
locust -f tests/load/upload_web_locustfile.py --headless \
       -u 30 -r 5 --run-time 30m \
       --host $UPLOAD_WEB_HOST \
       --csv results/upload-web-load

# With web UI (interactive)
locust -f tests/load/upload_web_locustfile.py --host $UPLOAD_WEB_HOST
```

## Expected Thresholds

| Metric | Target | Failure Threshold |
|---|---|---|
| **RPS** | ≥ 30 sustained | < 25 sustained |
| **p50 response time** | < 200 ms | > 500 ms |
| **p95 response time** | < 500 ms | > 1 500 ms |
| **p99 response time** | < 1 000 ms | > 3 000 ms |
| **Error rate** | < 0.1 % | > 1 % |
| **SAS generation p95** | < 300 ms | > 800 ms |
| **Preflight p95** | < 2 000 ms | > 5 000 ms |

## Test Flow per User

1. `POST /api/sessions` — create upload session
2. `POST /api/sessions/{id}/sas?filename=…` × 3 — generate SAS URLs
3. `POST /api/sessions/{id}/files` × 3 — register file metadata
4. `POST /api/sessions/{id}/preflight` — run preflight check
5. `POST /api/sessions/{id}/confirm` — confirm and publish

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `UPLOAD_WEB_HOST` | `http://localhost:8000` | Target host |
| `UPLOAD_WEB_AUTH_TOKEN` | `Bearer test.jwt.token` | Auth header value |
| `UPLOAD_WEB_CSRF_TOKEN` | `test-csrf-token` | CSRF token for POST requests |

## Notes

- All endpoints are mocked when running locally (no real Azure calls).
- Results CSV files are written to `results/upload-web-load-*.csv`.
- For CI, use `--check-fail-ratio 0.01 --check-avg-response-time 500`.
