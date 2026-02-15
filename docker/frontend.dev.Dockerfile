FROM node:25-alpine
WORKDIR /app

# Install curl and corepack
RUN apk add --no-cache curl && \
    npm install -g corepack && \
    corepack enable && \
    corepack prepare pnpm@latest --activate

COPY frontend/package.json frontend/pnpm-lock.yaml ./

RUN pnpm i

COPY frontend ./

EXPOSE 4000

CMD ["pnpm", "run", "dev"]