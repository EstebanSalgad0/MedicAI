FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 TZ=America/Santiago
WORKDIR /app
RUN pip install --no-cache-dir httpx==0.27.2
COPY services/scheduler/scheduler.py .
RUN useradd --create-home medicai
USER medicai
CMD ["python", "scheduler.py"]
