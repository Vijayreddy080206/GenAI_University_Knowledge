/**
 * NIIT University - Gen AI Knowledge Assistant
 * Node.js + Express REST API Gateway Microservice Tier
 * Routes client requests to Python FastAPI RAG Orchestrator & ChromaDB backend.
 */
const express = require('express');
const cors = require('cors');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();
const PORT = process.env.PORT || 4000;
const PYTHON_RAG_BACKEND = process.env.PYTHON_RAG_BACKEND || 'http://localhost:8000';

app.use(cors());

// Live Request Logger for Docker Desktop Inspection
app.use((req, res, next) => {
  const start = Date.now();
  res.on('finish', () => {
    const duration = Date.now() - start;
    const timestamp = new Date().toISOString().slice(11, 19);
    console.log(`[${timestamp}] [API-GATEWAY] ${req.method} ${req.originalUrl} -> ${PYTHON_RAG_BACKEND} [Status: ${res.statusCode}] (${duration}ms)`);
  });
  next();
});

// Gateway Specific Health Check
app.get('/gateway/health', (req, res) => {
  res.json({
    status: 'UP',
    layer: 'Node.js + Express REST API Gateway (Tier 2)',
    proxy_target: PYTHON_RAG_BACKEND,
    uptime_seconds: Math.floor(process.uptime()),
    timestamp: new Date().toISOString()
  });
});

// Proxy all other routes (/api/*, /docs, /openapi.json, /healthz, /readyz) to FastAPI Backend
app.use('/', createProxyMiddleware({
  target: PYTHON_RAG_BACKEND,
  changeOrigin: true,
  logLevel: 'warn',
  onProxyReq: (proxyReq, req, res) => {
    proxyReq.setHeader('X-Forwarded-Gateway', 'express-api-gateway-v1');
  }
}));

app.listen(PORT, '0.0.0.0', () => {
  console.log(`====================================================================`);
  console.log(`NIIT University Express API Gateway running on port ${PORT}`);
  console.log(`Forwarding API traffic to Python RAG Backend at: ${PYTHON_RAG_BACKEND}`);
  console.log(`====================================================================`);
});
