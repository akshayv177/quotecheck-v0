"""
QuoteCheck Backend - FastAPI app (v0)

This module defines the FastAPI application for QuoteCheck.

Block 1:
- Boot spine with a /health endpoint.

Block 1.5:
- Enable CORS so the local frontend (Vite dev server) can call the API.

Endpoints
---------
GET /health
    Simple health check endpoint used to verify the server is running.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="QuoteCheck API", version="0.1.0")

# Local development CORS policy.
# Vite dev server typically runs on http://localhost:5173
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """
    Health check endpoint.

    Returns
    -------
    dict
        A small JSON payload indicating the server is alive.
    """
    return {"status": "ok"}
