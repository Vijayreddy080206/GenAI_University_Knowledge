# ==============================================================================
# NIIT University - Generative AI Knowledge Assistant Frontend
# Multi-stage / Lightweight Production Nginx Container
# ==============================================================================

FROM nginx:alpine
LABEL maintainer="Team-20 NIIT University"
LABEL description="Frontend Presentation Web Tier for University Knowledge Assistant"

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html

EXPOSE 80

HEALTHCHECK --interval=20s --timeout=3s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
