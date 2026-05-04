FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e ".[all]"
EXPOSE 8000
CMD ["uvicorn", "src.services.hitl_webform.main:app", "--host", "0.0.0.0", "--port", "8000"]
