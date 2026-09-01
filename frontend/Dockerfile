# --- build ---
# Node 22, não 20: o jsdom traz um `undici` que usa `webidl.util.markAsUncloneable`,
# disponível só a partir do Node 21. O desenvolvimento já rodava em 22 — construir em
# 20 era uma divergência silenciosa, e só apareceu quando os testes passaram a rodar
# dentro da imagem.
FROM node:22-alpine AS build
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
