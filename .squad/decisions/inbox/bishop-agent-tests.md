# Bishop — Agent real OCR test decisions

## 2026-05-07
- For real OCR agent validation, use `prerequisites/PRUEBA.pdf` as the fallback fixture when no PDF exists under `data/` or `tests/fixtures/`; it is the checked-in real document sample currently available in the repo.
- Gate the live Azure OCR + GPT integration test behind `RUN_AGENT_REAL_INTEGRATION=1` so default pytest runs stay offline-safe.
- Limit the default OCR slice for `tests/integration/test_agent_real.py` to the first page of `PRUEBA.pdf`; the full PDF is a mixed-document batch, while page 1 is a single coherent albarán suitable for stable A1/A2 validation.
- Budget `max_completion_tokens=8000` for GPT-5 extractor runs; smaller budgets were consumed entirely by GPT-5 reasoning tokens and returned empty visible content for structured JSON extraction.
