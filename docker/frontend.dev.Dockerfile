FROM node:25-alpine
WORKDIR /app

# Install curl and corepack (remove existing yarn to avoid conflicts)
RUN apk add --no-cache curl && \
    rm -f /usr/local/bin/yarn /usr/local/bin/yarnpkg && \
    npm install -g corepack && \
    corepack enable && \
    corepack prepare pnpm@latest --activate

COPY frontend/package.json frontend/pnpm-lock.yaml ./

RUN pnpm i

COPY frontend ./

EXPOSE 4000

CMD ["pnpm", "run", "dev"]