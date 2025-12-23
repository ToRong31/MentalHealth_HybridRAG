# syntax=docker/dockerfile:1.6

############################
# Build stage
############################
FROM node:20-alpine AS build
WORKDIR /app

COPY package*.json ./

# Reproducible + nhẹ hơn npm install
RUN npm ci

COPY . .

ARG VITE_API_URL=
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

############################
# Runtime stage
############################
FROM nginx:alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# nginx:alpine có busybox wget -> dùng cái này cho chắc
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
