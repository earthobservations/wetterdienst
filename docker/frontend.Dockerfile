# ─── base: node + pnpm ────────────────────────────────────────────────────────
FROM node:25-alpine AS base
WORKDIR /app

RUN rm -f /usr/local/bin/yarn /usr/local/bin/yarnpkg && \
    npm install -g corepack && \
    corepack enable && \
    corepack prepare pnpm@latest --activate

# ─── deps: install node_modules ───────────────────────────────────────────────
FROM base AS deps

COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./

RUN pnpm i

# ─── dev: development server ──────────────────────────────────────────────────
FROM deps AS dev

RUN apk add --no-cache curl

COPY frontend ./

EXPOSE 4000

CMD ["pnpm", "run", "dev"]

# ─── build: production build ──────────────────────────────────────────────────
FROM deps AS build

COPY frontend/app ./app
COPY frontend/public ./public
COPY frontend/server ./server
COPY frontend/nuxt.config.ts ./

RUN pnpm run build

# ─── prod: production runtime ─────────────────────────────────────────────────
FROM node:22-alpine AS prod
WORKDIR /app

RUN apk add --no-cache curl

COPY --from=build /app/.output/ ./

ENV HOST=0.0.0.0
ENV PORT=4000

EXPOSE 4000

CMD ["node", "/app/server/index.mjs"]
