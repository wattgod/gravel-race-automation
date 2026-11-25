FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 mission-control \
    && useradd --uid 10001 --gid 10001 --create-home \
        --home-dir /home/mission-control --shell /usr/sbin/nologin mission-control

COPY mission_control.py .
COPY mission_control/ mission_control/
COPY pipeline/__init__.py pipeline/nutrition.py pipeline/
COPY scripts/jev_client.py scripts/jev_client.py
COPY data/pricing.json data/pricing.json
COPY guide/fonts/ guide/fonts/
COPY templates/emails/ templates/emails/
COPY race-data/*.json race-data/
COPY web/race-index.json web/race-index.json

ENV HOME=/home/mission-control PYTHONDONTWRITEBYTECODE=1
USER 10001:10001

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD ["python3", "-c", "import http.client, os; connection = http.client.HTTPConnection('127.0.0.1', int(os.getenv('PORT', '8000')), timeout=3); connection.request('GET', '/health'); raise SystemExit(connection.getresponse().status != 200)"]
CMD ["python3", "mission_control.py"]
