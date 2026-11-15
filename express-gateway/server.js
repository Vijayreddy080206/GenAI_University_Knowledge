/**
 * Node.js + Express REST API Gateway Layer (Matches PPTX Slide 5 & Slide 6)
 * Routes client requests and session tokens to the Python FastAPI RAG Orchestrator & PostgreSQL/ChromaDB backend.
 */
const express = require('express');
const cors = require('cors');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();
const PORT = process.env.PORT || 4000;
const PYTHON_RAG_BACKEND = process.env.PYTHON_RAG_BACKEND || 'http://localhost:8000';

app.use(cors());
app.get('/gateway/health', (req, res) => {
  res.json({ status: 'UP', layer: 'Node.js + Express REST API Gateway', target: PYTHON_RAG_BACKEND });
});

app.use('/', createProxyMiddleware({
  target: PYTHON_RAG_BACKEND,
  changeOrigin: true
}));

app.listen(PORT, () => {
  console.log(`NIIT University Express API Gateway listening on http://localhost:${PORT} -> ${PYTHON_RAG_BACKEND}`);
});
