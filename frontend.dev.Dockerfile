FROM node:25-alpine
WORKDIR /app

# Install curl
RUN apk add --no-cache curl

RUN corepack enable

COPY frontend/package.json frontend/pnpm-lock.yaml ./

RUN pnpm i

COPY frontend ./

EXPOSE 4000

CMD ["pnpm", "run", "dev"]