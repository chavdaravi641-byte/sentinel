# --- Build stage -----------------------------------------------------------
FROM node:22-alpine AS build

WORKDIR /repo
ENV NEXT_TELEMETRY_DISABLED=1

COPY package.json ./
COPY apps/web/package.json apps/web/package.json
COPY packages/shared/package.json packages/shared/package.json
RUN npm install --no-audit --no-fund

COPY apps/web apps/web
COPY packages/shared packages/shared

ARG API_BACKEND_URL=http://localhost:8000
# Used by next.config.ts rewrites at build/eval time.
ENV API_BACKEND_URL=$API_BACKEND_URL

RUN npm run build --workspace=@sentinel/web

# --- Runtime stage ---------------------------------------------------------
FROM node:22-alpine AS runner

WORKDIR /repo
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

COPY --from=build /repo ./

EXPOSE 3000

CMD ["npm", "run", "start", "--workspace=@sentinel/web"]