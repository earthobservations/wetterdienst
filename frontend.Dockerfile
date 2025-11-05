# Build Stage 1
FROM node:22-alpine AS build
WORKDIR /app

RUN corepack enable

# Copy package.json and your lockfile, here we add pnpm-lock.yaml for illustration
COPY frontend/package.json frontend/pnpm-lock.yaml ./

# Install dependencies
RUN pnpm i

# Copy the entire project
COPY frontend ./

# Build the project
RUN pnpm run build

# Build Stage 2

FROM node:22-alpine
WORKDIR /app

# Only `.output` folder is needed from the build stage
COPY --from=build /app/.output/ ./

# Change the port and host
ENV HOST=0.0.0.0
ENV PORT=4000

EXPOSE 4000

CMD ["node", "/app/server/index.mjs"]