FROM python:3.12-slim

WORKDIR /app

# Dependências (camada cacheável)
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "fastapi>=0.110" "uvicorn[standard]>=0.27" "httpx>=0.27" \
    "pydantic>=2.6" "pydantic-settings>=2.2" "redis>=5.0"

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
