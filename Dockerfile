FROM python:3.12-slim

# System dependencies for Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    git openssh-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir fastapi uvicorn jinja2 supabase python-multipart \
    && playwright install chromium --with-deps

# App code (pipeline + mission control + templates + data)
COPY . .

EXPOSE 8000
CMD ["python3", "mission_control.py"]
