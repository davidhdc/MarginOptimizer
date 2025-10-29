"""
Margin Optimizer FastAPI Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import strategies

# Create FastAPI app
app = FastAPI(
    title="Margin Optimizer API",
    description="""
    API for generating vendor negotiation strategies based on service analysis.

    ## Features
    - Get negotiation strategies for all vendors quoting a service
    - Historical negotiation performance data
    - Vendor price list (VPL) comparisons
    - Alternative vendor options
    - Prioritized recommendations (1-3 per vendor)

    ## Authentication
    All endpoints require an API key in the `X-API-Key` header.

    ## Example Usage
    ```bash
    curl -X GET "http://localhost:8000/api/v1/strategies/TWS.5511.D011" \\
         -H "X-API-Key: your-api-key-here"
    ```
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(strategies.router)


@app.get("/", tags=["root"])
async def root():
    """Root endpoint"""
    return {
        "message": "Margin Optimizer API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
