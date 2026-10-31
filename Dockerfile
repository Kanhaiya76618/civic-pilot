# Civic Pulse: web app + Part 3 executor + sandbox portal in one container.
# Hugging Face Spaces (Docker SDK) or Render: one public port ($PORT, default 7860).

# 1. Build the React app (web/) into static files.
FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# 2. Python runtime with Chromium; FastAPI serves the built app.
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    CIVIC_DATA_DIR=/tmp/civic-data \
    CIVIC_HEADLESS=1 \
    SANDBOX_URL=http://127.0.0.1:7861 \
    PORT=7860

WORKDIR /app
RUN pip install uv==0.12.1
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
# Chromium plus the system libraries it needs.
RUN uv run --no-sync playwright install --with-deps chromium

COPY executor ./executor
COPY sandbox_portal ./sandbox_portal
COPY registry ./registry
COPY contracts ./contracts
COPY deploy/start.sh ./deploy/start.sh
COPY --from=web /web/dist ./web/dist
# Spaces run the container as a non-root user: the app must be able to write patches and drafts.
RUN chmod -R a+rwX /app /ms-playwright

EXPOSE 7860
CMD ["sh", "deploy/start.sh"]
