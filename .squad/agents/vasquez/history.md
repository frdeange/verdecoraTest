# Vasquez — History

## Project Context
- **Project:** Sistema Inteligente de Gestión de Albaranes
- **User:** Kiko de Angel
- **Role:** QA Engineer
- **Stack:** Python, pytest, load testing tools, OCR validation
- **PRD:** prerequisites/pliego-tecnico-albaranes.html

## Learnings

- 2026-05-04: Set up pytest defaults so only unit tests run unless `--run-integration` or `--run-e2e` is explicitly passed. Added reusable mocks for BC MCP, Cosmos DB, ACS Email, and Service Bus plus JSON fixtures for albarán and PO payloads.
- 2026-05-05: Added upload-web smoke coverage for health probes, Easy Auth enforcement, authenticated landing pages, and static assets. Introduced reusable `app_client` + mock Easy Auth headers for E2E tests and verified the new suite with `python -m pytest tests\\unit\\test_upload_web_scaffold.py tests\\e2e\\test_upload_web_smoke.py --run-e2e`.
