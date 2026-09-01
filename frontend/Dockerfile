# --- build ---
FROM node:20-alpine AS build
WORKDIR /app
# O lockfile ENTRA e o install é `npm ci`. Antes só o package.json era copiado e o
# `npm install` resolvia as versões de novo a cada build: o package-lock.json estava
# commitado e era ignorado, então a produção não era reproduzível.
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Typecheck e testes ANTES do bundle: o build passava por `tsc -b` mas nunca rodava a
# suíte, então um teste vermelho virava imagem publicada.
RUN npm test
RUN npm run build

# --- serve ---
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
