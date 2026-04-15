# ── Stage 1: Build the React frontend ──────────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /app/ui

# Install dependencies
COPY ui/package*.json ./
RUN npm ci

# Copy source and build
COPY ui/ ./
RUN npm run build

# ── Stage 2: Python backend + serve built frontend ──────────────────────────
FROM python:3.11-slim

WORKDIR /app

# System deps needed by some Python packages (e.g. statsmodels, prophet)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./backend/

# Copy built React app into a 'static' folder the backend will serve
COPY --from=frontend-builder /app/ui/dist ./static

# Copy data CSVs to the backend directory (where the service expects them)
COPY processed_marketing_data.csv ./backend/processed_marketing_data.csv
COPY marketing_campaign_dataset.csv ./backend/marketing_campaign_dataset.csv
COPY revenue_forecast_30_days.csv ./backend/revenue_forecast_30_days.csv

# Expose HF Spaces required port
EXPOSE 7860

# Start FastAPI on port 7860
# --app-dir makes uvicorn resolve modules from /app/backend so `from api.endpoints import ...` works
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", "--app-dir", "/app/backend"]
