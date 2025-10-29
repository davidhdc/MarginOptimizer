"""
Pydantic models for Margin Optimizer API
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class ServiceInfo(BaseModel):
    """Service information"""
    service_id: str
    customer: str
    bandwidth_display: str
    client_mrc: float
    currency: str
    address: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None


class VendorQuoteInfo(BaseModel):
    """Vendor quote information"""
    vendor_name: str
    quickbase_id: int
    current_mrc: float
    mrc_currency: str
    current_gm: float
    gm_status: str
    lead_time: Optional[str] = None
    status: Optional[str] = None
    bandwidth: Optional[str] = None


class NegotiationHistory(BaseModel):
    """Historical negotiation data"""
    total_negotiations: int
    successful_negotiations: int
    success_rate: float
    avg_discount: float
    projected_mrc: Optional[float] = None
    projected_gm: Optional[float] = None
    projected_gm_status: Optional[str] = None


class RenewalStats(BaseModel):
    """Renewal statistics"""
    total_renewals: int
    successful_renewals: int
    success_rate: float
    avg_discount: float


class DeliveredServices(BaseModel):
    """Delivered services summary"""
    total_mrc_usd: float
    delivered_count: int


class TargetMargins(BaseModel):
    """Target margin calculations"""
    gm_40: dict = Field(description="Target for 40% GM")
    gm_50: dict = Field(description="Target for 50% GM")


class VPLOption(BaseModel):
    """Vendor Price List option"""
    mrc: float
    mrc_currency: str
    nrc: float
    nrc_currency: str
    gm: float
    gm_status: str
    bandwidth: str
    service_type: str
    savings: float
    savings_percent: float


class Alternative(BaseModel):
    """Alternative vendor option"""
    vendor_name: str
    mrc: float
    mrc_currency: str
    gm: float
    gm_status: str
    bandwidth: str
    service_type: str


class RecommendationAction(BaseModel):
    """Individual action within a recommendation"""
    text: str
    value: Optional[float] = None


class Recommendation(BaseModel):
    """Strategy recommendation"""
    priority: int
    title: str
    type: str = Field(description="negotiate, vpl, alternative, or maintain")
    strength: str = Field(description="very_high, high, medium, or low")
    actions: List[RecommendationAction]


class VendorStrategy(BaseModel):
    """Complete strategy for a single vendor"""
    vendor_name: str
    vendor_quote: VendorQuoteInfo
    negotiation_history: Optional[NegotiationHistory] = None
    renewal_stats: Optional[RenewalStats] = None
    delivered_services: Optional[DeliveredServices] = None
    targets: TargetMargins
    vendor_vpl: List[VPLOption] = []
    alternatives: List[Alternative] = []
    recommendations: List[Recommendation]


class StrategyResponse(BaseModel):
    """Complete API response with strategies for all vendors"""
    service_id: str
    service: ServiceInfo
    vendor_strategies: List[VendorStrategy]
    total_vendors: int = Field(description="Number of vendors analyzed")


class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    detail: Optional[str] = None
