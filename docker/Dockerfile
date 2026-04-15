FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY cucm_exporter/ ./cucm_exporter/
COPY config/ ./config/

EXPOSE 9100

ENTRYPOINT ["python", "-m", "cucm_exporter.main"]
CMD ["--config", "/app/config/exporter_config.yaml"]
