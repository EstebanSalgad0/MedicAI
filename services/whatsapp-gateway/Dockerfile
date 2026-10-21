# Contexto de build: raíz del repositorio (ver docker-compose.yml)
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=America/Santiago
WORKDIR /app
COPY libs/medicai_common /libs/medicai_common
RUN pip install --no-cache-dir /libs/medicai_common
COPY services/whatsapp-gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/whatsapp-gateway/app ./app
RUN useradd --create-home medicai
USER medicai
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
