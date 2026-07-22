FROM node:20-alpine AS base

ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
RUN corepack enable && corepack prepare pnpm@9.15.4 --activate

WORKDIR /app

FROM base AS deps
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

FROM base AS builder
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8010
ARG NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8010
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_WS_BASE_URL=$NEXT_PUBLIC_WS_BASE_URL
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build

FROM base AS runner
ENV NODE_ENV=production
ENV PORT=3100
ENV HOSTNAME=0.0.0.0
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8010
ARG NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8010
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_WS_BASE_URL=$NEXT_PUBLIC_WS_BASE_URL
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules

EXPOSE 3100
CMD ["sh", "-c", "pnpm start -H ${HOSTNAME:-0.0.0.0} -p ${PORT:-3100}"]
