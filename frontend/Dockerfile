# ==============================================================================
# NIIT University - Generative AI Knowledge Assistant Frontend
# Multi-stage / Lightweight Production Nginx Container with SSL & HTTP/2
# ==============================================================================

FROM nginx:alpine
LABEL maintainer="Team-20 NIIT University"
LABEL description="Frontend Presentation Web Tier for University Knowledge Assistant"

RUN mkdir -p /etc/nginx/certs

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html

EXPOSE 80 443

HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://127.0.0.1:80/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
