# Build Stage
FROM node:25-alpine AS build
WORKDIR /app

RUN corepack enable

# Copy package files
COPY frontend/package.json frontend/pnpm-lock.yaml ./

# Install dependencies
RUN pnpm i

# Copy only necessary source files and configs
COPY frontend/app ./app
COPY frontend/public ./public
COPY frontend/server ./server
COPY frontend/nuxt.config.ts ./

# Build the project
RUN pnpm run build

# Production Stage
FROM node:25-alpine
WORKDIR /app

# Only copy the built output
COPY --from=build /app/.output/ ./

# Set environment variables
ENV HOST=0.0.0.0
ENV PORT=4000

EXPOSE 4000

CMD ["node", "/app/server/index.mjs"]
