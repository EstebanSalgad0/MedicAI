# Contexto de build: raíz del repositorio
FROM node:22-alpine AS build
WORKDIR /app
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY dashboard/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
RUN printf 'server {\n  listen 80;\n  root /usr/share/nginx/html;\n  location / { try_files $uri /index.html; }\n  location /assets/ { expires 30d; add_header Cache-Control "public, immutable"; }\n}\n' > /etc/nginx/conf.d/default.conf
EXPOSE 80
