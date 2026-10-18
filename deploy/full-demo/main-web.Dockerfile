FROM node:22-bookworm-slim AS build
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ARG SITE_HOST
ENV PHOTOAI_STANDALONE=1 NEXT_TELEMETRY_DISABLED=1
ENV NEXT_PUBLIC_API_MODE=real NEXT_PUBLIC_API_BASE_URL=https://${SITE_HOST} NEXT_PUBLIC_RETOUCH_URL=https://${SITE_HOST}
RUN npm run build

FROM node:22-bookworm-slim
WORKDIR /web
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
COPY --from=build --chown=node:node /web/.next/standalone ./
COPY --from=build --chown=node:node /web/.next/static ./.next/static
COPY --from=build --chown=node:node /web/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
