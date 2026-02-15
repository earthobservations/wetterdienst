# Build Stage
FROM node:25-alpine AS build
WORKDIR /app

# Install corepack and prepare pnpm (remove existing yarn to avoid conflicts)
RUN rm -f /usr/local/bin/yarn /usr/local/bin/yarnpkg && \
    npm install -g corepack && \
    corepack enable && \
    corepack prepare pnpm@latest --activate

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
FROM node:22-alpine
WORKDIR /app

# Install curl
RUN apk add --no-cache curl

# Only copy the built output
COPY --from=build /app/.output/ ./

# Set environment variables
ENV HOST=0.0.0.0
ENV PORT=4000

EXPOSE 4000

CMD ["node", "/app/server/index.mjs"]
