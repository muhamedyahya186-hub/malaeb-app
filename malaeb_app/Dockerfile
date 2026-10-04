FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MALAEb_HOST=0.0.0.0 MALAEb_PORT=8000 MALAEb_DB=/data/malaeb.sqlite3
WORKDIR /app
COPY . /app
RUN mkdir -p /data && useradd --system --uid 10001 appuser && chown -R appuser:appuser /app /data
USER appuser
EXPOSE 8000
CMD ["python", "server.py"]
