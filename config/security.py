"""
Security configuration for API authentication
"""
import os
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

# API Key configuration
API_KEY_NAME = "X-API-Key"
API_KEY = os.getenv("MARGIN_OPTIMIZER_API_KEY", "your-secret-api-key-change-in-production")

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)


async def verify_api_key(api_key: str = Security(api_key_header)):
    """
    Verify API Key from request header

    Args:
        api_key: API key from X-API-Key header

    Raises:
        HTTPException: If API key is invalid

    Returns:
        str: The validated API key
    """
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key"
        )
    return api_key
