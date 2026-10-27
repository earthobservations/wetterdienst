# ─── base: node + pnpm ────────────────────────────────────────────────────────
FROM node:24-alpine@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f AS base
WORKDIR /app

# The corepack that ships with this Node image, not the latest one fetched on every build. It
# provides `pnpm` at the version and hash of `packageManager` in app/package.json, which is
# where that pin lives.
RUN rm -f /usr/local/bin/yarn /usr/local/bin/yarnpkg && \
    corepack enable pnpm

# ─── deps: install node_modules ───────────────────────────────────────────────
FROM base AS deps

# .pnpmfile.cjs changes what the lockfile resolves (GH-3094), so the install needs it too
COPY app/package.json app/pnpm-lock.yaml app/pnpm-workspace.yaml app/.pnpmfile.cjs ./

RUN pnpm install --frozen-lockfile

# ─── dev: development server ──────────────────────────────────────────────────
FROM deps AS dev

RUN apk add --no-cache curl

COPY app ./

# The dev server listens on localhost unless told otherwise, which a published port cannot reach in a
# container. compose.yml publishes it on 127.0.0.1 of the host (GH-3096).
ENV HOST=0.0.0.0

EXPOSE 4000

CMD ["pnpm", "run", "dev"]

# ─── build: production build ──────────────────────────────────────────────────
FROM deps AS build

COPY app/app ./app
COPY app/i18n ./i18n
COPY app/public ./public
COPY app/server ./server
# the module that publishes Swagger UI's two files under /_swagger-ui/ (GH-3094)
COPY app/modules ./modules
# `shared/` holds types the components import, and since GH-3497 values as well (`shared/utils/seo.ts`, which
# the config, the pages and the server routes import): the build fails without it.
COPY app/shared ./shared
COPY app/nuxt.config.ts ./

RUN pnpm run build

# ─── prod: production runtime ─────────────────────────────────────────────────
FROM node:24-alpine@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f AS prod
WORKDIR /app

RUN apk add --no-cache curl

COPY --from=build /app/.output/ ./

ENV HOST=0.0.0.0
ENV PORT=4000

# Run unprivileged, as the backend image does (GH-2770): the server parses what a client sends and proxies it to
# the backend. It writes nothing (the rate limiter keeps its store in memory) and listens above 1024, so it needs
# no more than to read the files above, which `COPY` made world-readable (GH-3091). `node` is in the base image.
USER node

EXPOSE 4000

# The page at `/`: the app's own answer, served from its files, which asks no backend (the app is not
# reported unhealthy while the backend restarts) and is outside the rate limit (`isLimited` counts only
# `/api` and `/mcp`), so a probe every 30 s never counts against a client (GH-3346). The server starts
# in about a second. It asks the port the server listens on (`PORT`). A platform that defines a health check
# of its own replaces this one; where it defines none (Coolify's default), a proxy such as Traefik routes by
# this one, as it sends traffic to containers that are healthy or have no health state.
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --start-interval=1s --retries=3 \
    CMD ["sh", "-c", "curl --fail --silent --output /dev/null http://127.0.0.1:$PORT/"]

CMD ["node", "/app/server/index.mjs"]
