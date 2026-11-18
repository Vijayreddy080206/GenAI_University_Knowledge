# ==============================================================================
# NIIT University - REST API Gateway (Node.js + Express)

# ==============================================================================

FROM node:20-alpine
WORKDIR /app

LABEL maintainer="Team-20 NIIT University"
LABEL description="Express API Gateway routing client sessions to RAG Backend"

COPY package*.json ./
RUN npm install --omit=dev

COPY server.js ./

EXPOSE 4000

HEALTHCHECK --interval=20s --timeout=3s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:4000/gateway/health || exit 1

CMD ["node", "server.js"]
