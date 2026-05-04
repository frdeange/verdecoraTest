FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e ".[all]"
CMD ["python", "-m", "src.services.flow0_dedup.main"]
