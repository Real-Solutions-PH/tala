# Kapiling app image for the cloud demo: bun builds the frontend, then python slim with uv runs the API.
# The model servers (llama.cpp, whisper.cpp) are separate containers; see deploy/compose.yaml.

FROM oven/bun:1 AS web
WORKDIR /src/frontend
COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile
COPY frontend/ ./
# vite.config.ts writes to ../backend/static
RUN mkdir -p /src/backend && bun run build

FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/ ./
COPY --from=web /src/backend/static ./static
ENV HF_HUB_OFFLINE=1 KAPILING_DATA=/data PATH="/app/backend/.venv/bin:$PATH"
EXPOSE 8787
# --proxy-headers: behind Caddy, so the scheme (secure cookies) and host (WebAuthn origin) come from X-Forwarded-*.
CMD ["uvicorn", "kapiling.main:app", "--host", "0.0.0.0", "--port", "8787", "--proxy-headers", "--forwarded-allow-ips", "*"]
