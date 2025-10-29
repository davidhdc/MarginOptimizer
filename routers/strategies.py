"""
Strategy endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, status
from models.schemas import StrategyResponse, ErrorResponse
from services.strategy_service import StrategyService
from api_config.security import verify_api_key

router = APIRouter(
    prefix="/api/v1",
    tags=["strategies"]
)


@router.get(
    "/strategies/{service_id}",
    response_model=StrategyResponse,
    dependencies=[Depends(verify_api_key)],
    responses={
        200: {"description": "Strategies generated successfully"},
        401: {"model": ErrorResponse, "description": "Invalid or missing API Key"},
        404: {"model": ErrorResponse, "description": "Service not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Get negotiation strategies for a service",
    description="""
    Get negotiation strategies for all vendors quoting a specific service.

    Returns strategies including:
    - Current vendor quote details
    - Historical negotiation performance
    - Renewal statistics
    - Delivered services summary
    - Target margins (40% and 50%)
    - Vendor price list options
    - Alternative vendors
    - Prioritized recommendations (1-3 strategies per vendor)

    **Authentication:** Requires X-API-Key header
    """
)
async def get_strategies(service_id: str):
    """
    Get negotiation strategies for a service

    Args:
        service_id: Service ID (e.g., 'TWS.5511.D011')

    Returns:
        StrategyResponse with strategies for all vendors
    """
    strategy_service = StrategyService()

    try:
        strategies = strategy_service.get_strategies_for_service(service_id)
        return strategies

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating strategies: {str(e)}"
        )

    finally:
        strategy_service.close()


@router.get(
    "/health",
    tags=["health"],
    summary="Health check",
    description="Check if the API is running and healthy"
)
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Margin Optimizer API"}
