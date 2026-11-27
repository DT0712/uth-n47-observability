# portal-web (kien-truc-portal.md §2): build React bằng Node, phục vụ bằng Nginx, proxy /api tới portal-api.
# Build từ monitor/docker-compose.yml (context = portal/frontend).
FROM node:22-alpine AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1
