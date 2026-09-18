# ─── base: node + pnpm ────────────────────────────────────────────────────────
FROM node:26-alpine AS base
WORKDIR /app

RUN rm -f /usr/local/bin/yarn /usr/local/bin/yarnpkg && \
    npm install -g corepack && \
    corepack enable && \
    corepack prepare pnpm@11.22.0 --activate

# ─── deps: install node_modules ───────────────────────────────────────────────
FROM base AS deps

COPY app/package.json app/pnpm-lock.yaml app/pnpm-workspace.yaml ./

RUN pnpm i

# ─── dev: development server ──────────────────────────────────────────────────
FROM deps AS dev

RUN apk add --no-cache curl

COPY app ./

EXPOSE 4000

CMD ["pnpm", "run", "dev"]

# ─── build: production build ──────────────────────────────────────────────────
FROM deps AS build

COPY app/app ./app
COPY app/i18n ./i18n
COPY app/public ./public
COPY app/server ./server
# Seven components import from `shared/`. Every one of those is an `import type`, which the
# transpiler strips before resolving, so the build survives without it -- until the first value
# exported from there turns one of them into a real import and the image stops building.
COPY app/shared ./shared
COPY app/nuxt.config.ts ./

RUN pnpm run build

# ─── prod: production runtime ─────────────────────────────────────────────────
FROM node:26-alpine AS prod
WORKDIR /app

RUN apk add --no-cache curl

COPY --from=build /app/.output/ ./

ENV HOST=0.0.0.0
ENV PORT=4000

EXPOSE 4000

CMD ["node", "/app/server/index.mjs"]
