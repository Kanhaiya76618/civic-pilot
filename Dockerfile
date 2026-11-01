# Swayam-sevak: web app + Part 3 executor + sandbox portal in one container.
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
# Pothole detection (optional in the code): YOLO on the CPU-only PyTorch build, not the multi-GB GPU one.
RUN uv pip install --python .venv torch torchvision --index-url https://download.pytorch.org/whl/cpu \
 && uv pip install --python .venv ultralytics==8.4.195 \
 # ultralytics pulls the desktop OpenCV build, which needs GUI libraries: keep only the headless one.
 && uv pip uninstall --python .venv opencv-python \
 && uv pip install --python .venv --reinstall opencv-python-headless==5.0.0.93
# Chromium plus the system libraries it needs.
RUN uv run --no-sync playwright install --with-deps chromium

COPY executor ./executor
COPY server ./server
COPY data ./data
COPY db ./db
COPY pothole_best.pt ./pothole_best.pt
COPY sandbox_portal ./sandbox_portal
COPY registry ./registry
COPY contracts ./contracts
COPY deploy/start.sh ./deploy/start.sh
COPY --from=web /web/dist ./web/dist
# Spaces run the container as a non-root user: it writes route patches/drafts and a local data folder.
# Only those paths: a recursive chmod over /app would copy every file into a new layer (+2 GB).
RUN mkdir -p /app/.data && chmod a+rwX /app /app/.data && chmod -R a+rwX /app/registry

EXPOSE 7860
CMD ["sh", "deploy/start.sh"]
