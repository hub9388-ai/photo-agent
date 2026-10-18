# Build from the pinned upstream plus our reviewable patch; never copy the local checkout.
FROM alpine/git AS source
WORKDIR /source
RUN git clone https://github.com/yuyuanweb/ai-picture-editor.git . && git checkout 49f6ad8c96740a68b7e6228a47e8e2be6876eb34
COPY integrations/retouch-photoai.patch /adapter.patch
RUN git apply --check /adapter.patch && git apply /adapter.patch

FROM node:22-bookworm-slim AS web-build
WORKDIR /web
COPY --from=source /source/frontend/package*.json ./
RUN npm ci
COPY --from=source /source/frontend ./
ARG SITE_HOST
ENV VITE_PHOTOAI_ORIGIN=https://${SITE_HOST}
RUN npm run build

FROM caddy:2 AS web
COPY --from=web-build /web/dist /srv
COPY deploy/full-demo/editor.Caddyfile /etc/caddy/Caddyfile

FROM python:3.13-slim AS backend
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app:/support
WORKDIR /app
COPY deploy/full-demo/requirements-retouch.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
COPY --from=source /source/backend /app
COPY deploy/full-demo/support /support
RUN useradd --uid 10001 --create-home demo && mkdir /limits && chown demo:demo /limits
USER demo
EXPOSE 7302
CMD ["uvicorn", "retouch_entry:app", "--host", "0.0.0.0", "--port", "7302", "--workers", "1"]
