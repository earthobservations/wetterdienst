FROM node:25-alpine
WORKDIR /app

RUN corepack enable

COPY frontend/package.json frontend/pnpm-lock.yaml ./

RUN pnpm i

COPY frontend ./

EXPOSE 4000

CMD ["pnpm", "run", "dev"]