"""
Strategy service - Business logic for generating negotiation strategies
"""
from typing import List, Dict, Optional
from connectors.neo4j_client import Neo4jClient
from connectors.quickbase import QuickbaseClient
from models.schemas import (
    StrategyResponse, VendorStrategy, ServiceInfo, VendorQuoteInfo,
    NegotiationHistory, RenewalStats, DeliveredServices, TargetMargins,
    VPLOption, Alternative, Recommendation, RecommendationAction
)


class StrategyService:
    """Service for generating vendor negotiation strategies"""

    def __init__(self):
        self.neo4j_client = Neo4jClient()
        self.qb_client = QuickbaseClient()

    def get_strategies_for_service(self, service_id: str) -> StrategyResponse:
        """
        Get negotiation strategies for all vendors quoting a service

        Args:
            service_id: Service ID (e.g., 'TWS.5511.D011')

        Returns:
            StrategyResponse with strategies for each vendor
        """
        # Get service details
        service = self.neo4j_client.get_service_details(service_id)
        if not service:
            raise ValueError(f"Service {service_id} not found")

        # Get all vendor quotes for this service
        vendor_quotes_data = self.neo4j_client.get_vendor_quotes_for_service(
            service_id,
            include_nearby=False,
            radius_meters=0
        )

        associated_vqs = vendor_quotes_data.get('associated', [])
        vpl_options = vendor_quotes_data.get('vpl', [])

        if not associated_vqs:
            raise ValueError(f"No vendor quotes found for service {service_id}")

        # Build service info
        service_info = ServiceInfo(
            service_id=service['service_id'],
            customer=service['customer'],
            bandwidth_display=service['bandwidth_display'],
            client_mrc=service['client_mrc'],
            currency=service.get('service_currency', 'USD'),
            address=service.get('address'),
            latitude=service.get('latitude'),
            longitude=service.get('longitude')
        )

        # Generate strategy for each vendor
        vendor_strategies = []
        for vq in associated_vqs:
            try:
                strategy = self._generate_vendor_strategy(
                    service, vq, vpl_options
                )
                vendor_strategies.append(strategy)
            except Exception as e:
                print(f"Error generating strategy for vendor {vq.get('vendor_name')}: {e}")
                continue

        return StrategyResponse(
            service_id=service_id,
            service=service_info,
            vendor_strategies=vendor_strategies,
            total_vendors=len(vendor_strategies)
        )

    def _generate_vendor_strategy(
        self,
        service: Dict,
        vq: Dict,
        all_vpl: List[Dict]
    ) -> VendorStrategy:
        """Generate strategy for a single vendor"""

        vendor_name = vq.get('vendor_name', 'Unknown')
        client_mrc = service['client_mrc']
        current_mrc = vq.get('mrc', 0)
        service_currency = service.get('service_currency', 'USD')

        # Calculate current GM
        current_gm = ((client_mrc - current_mrc) / client_mrc * 100) if client_mrc > 0 else 0
        gm_status = 'success' if current_gm >= 50 else 'warning' if current_gm >= 40 else 'danger'

        # Build vendor quote info
        vendor_quote = VendorQuoteInfo(
            vendor_name=vendor_name,
            quickbase_id=vq.get('quickbase_id', 0),
            current_mrc=round(current_mrc, 2),
            mrc_currency=service_currency,
            current_gm=round(current_gm, 1),
            gm_status=gm_status,
            lead_time=vq.get('lead_time'),
            status=vq.get('status'),
            bandwidth=f"{vq.get('bandwidth_bps', 0) / 1_000_000:.0f} Mbps" if vq.get('bandwidth_bps') else None
        )

        # Get negotiation history
        neg_stats = self.qb_client.get_vendor_negotiation_stats(vendor_name)
        negotiation_history = None
        if neg_stats and neg_stats.get('has_data'):
            negotiated_mrc = current_mrc * (1 - neg_stats['avg_discount']/100)
            negotiated_gm = ((client_mrc - negotiated_mrc) / client_mrc * 100) if client_mrc > 0 else 0
            negotiation_history = NegotiationHistory(
                total_negotiations=neg_stats['total_negotiations'],
                successful_negotiations=neg_stats['successful_negotiations'],
                success_rate=round(neg_stats['success_rate'], 1),
                avg_discount=round(neg_stats['avg_discount'], 1),
                projected_mrc=round(negotiated_mrc, 2),
                projected_gm=round(negotiated_gm, 1),
                projected_gm_status='success' if negotiated_gm >= 50 else 'warning' if negotiated_gm >= 40 else 'danger'
            )

        # Get renewal stats
        renewal_stats_data = self.qb_client.get_vendor_renewal_stats(vendor_name)
        renewal_stats = None
        if renewal_stats_data and renewal_stats_data.get('has_data'):
            renewal_stats = RenewalStats(
                total_renewals=renewal_stats_data['total_renewals'],
                successful_renewals=renewal_stats_data['successful_renewals'],
                success_rate=round(renewal_stats_data['success_rate'], 1),
                avg_discount=round(renewal_stats_data['avg_discount'], 1)
            )

        # Get delivered services
        delivered_data = self.qb_client.get_vendor_delivered_mrc_total(vendor_name)
        delivered_services = None
        if delivered_data and delivered_data.get('has_data'):
            delivered_services = DeliveredServices(
                total_mrc_usd=round(delivered_data['total_mrc_usd'], 2),
                delivered_count=delivered_data['delivered_count']
            )

        # Calculate targets
        target_mrc_40 = client_mrc * 0.6  # 40% GM
        target_mrc_50 = client_mrc * 0.5  # 50% GM
        discount_for_40 = ((current_mrc - target_mrc_40) / current_mrc * 100) if current_mrc > 0 else 0
        discount_for_50 = ((current_mrc - target_mrc_50) / current_mrc * 100) if current_mrc > 0 else 0

        targets = TargetMargins(
            gm_40={'target_mrc': round(target_mrc_40, 2), 'discount_needed': round(discount_for_40, 1)},
            gm_50={'target_mrc': round(target_mrc_50, 2), 'discount_needed': round(discount_for_50, 1)}
        )

        # Filter VPL for this vendor
        vendor_vpl_list = []
        vendor_vpl_data = [v for v in all_vpl if v.get('vendor_name') == vendor_name]
        if vendor_vpl_data:
            # Take best option (highest GM)
            vendor_vpl_data.sort(key=lambda x: ((client_mrc - x.get('mrc', 0)) / client_mrc * 100), reverse=True)
            for v in vendor_vpl_data[:3]:  # Top 3
                vpl_mrc = v.get('mrc', 0)
                vpl_gm = ((client_mrc - vpl_mrc) / client_mrc * 100) if client_mrc > 0 else 0
                savings = current_mrc - vpl_mrc

                vendor_vpl_list.append(VPLOption(
                    mrc=round(vpl_mrc, 2),
                    mrc_currency=service_currency,
                    nrc=round(v.get('nrc', 0), 2),
                    nrc_currency=service_currency,
                    gm=round(vpl_gm, 1),
                    gm_status='success' if vpl_gm >= 50 else 'warning' if vpl_gm >= 40 else 'danger',
                    bandwidth=f"{v.get('bandwidth_bps', 0) / 1_000_000:.0f} Mbps" if v.get('bandwidth_bps') else 'N/A',
                    service_type=v.get('service_type', 'N/A'),
                    savings=round(savings, 2),
                    savings_percent=round((savings / current_mrc * 100), 1) if current_mrc > 0 else 0
                ))

        # Get alternatives (other vendors)
        alternatives_list = []
        other_vendors = [v for v in all_vpl if v.get('vendor_name') != vendor_name]
        if other_vendors:
            other_vendors.sort(key=lambda x: ((client_mrc - x.get('mrc', 0)) / client_mrc * 100), reverse=True)
            for v in other_vendors[:5]:  # Top 5
                alt_mrc = v.get('mrc', 0)
                alt_gm = ((client_mrc - alt_mrc) / client_mrc * 100) if client_mrc > 0 else 0

                alternatives_list.append(Alternative(
                    vendor_name=v.get('vendor_name', 'Unknown'),
                    mrc=round(alt_mrc, 2),
                    mrc_currency=service_currency,
                    gm=round(alt_gm, 1),
                    gm_status='success' if alt_gm >= 50 else 'warning' if alt_gm >= 40 else 'danger',
                    bandwidth=f"{v.get('bandwidth_bps', 0) / 1_000_000:.0f} Mbps" if v.get('bandwidth_bps') else 'N/A',
                    service_type=v.get('service_type', 'N/A')
                ))

        # Generate recommendations
        recommendations = self._generate_recommendations(
            current_gm=current_gm,
            current_mrc=current_mrc,
            vendor_name=vendor_name,
            target_mrc_40=target_mrc_40,
            target_mrc_50=target_mrc_50,
            discount_for_40=discount_for_40,
            discount_for_50=discount_for_50,
            negotiation_history=negotiation_history,
            vendor_vpl=vendor_vpl_list,
            alternatives=alternatives_list,
            client_mrc=client_mrc
        )

        return VendorStrategy(
            vendor_name=vendor_name,
            vendor_quote=vendor_quote,
            negotiation_history=negotiation_history,
            renewal_stats=renewal_stats,
            delivered_services=delivered_services,
            targets=targets,
            vendor_vpl=vendor_vpl_list,
            alternatives=alternatives_list,
            recommendations=recommendations
        )

    def _generate_recommendations(
        self,
        current_gm: float,
        current_mrc: float,
        vendor_name: str,
        target_mrc_40: float,
        target_mrc_50: float,
        discount_for_40: float,
        discount_for_50: float,
        negotiation_history: Optional[NegotiationHistory],
        vendor_vpl: List[VPLOption],
        alternatives: List[Alternative],
        client_mrc: float
    ) -> List[Recommendation]:
        """Generate strategic recommendations"""

        recommendations = []

        if current_gm < 50:
            # Recommendation 1: Negotiate with current vendor
            actions = []

            if negotiation_history:
                actions.append(RecommendationAction(
                    text=f"Historical average discount: {negotiation_history.avg_discount}% (success rate: {negotiation_history.success_rate}%)",
                    value=negotiation_history.projected_mrc
                ))

            actions.append(RecommendationAction(
                text=f"For 40% GM: Request ${target_mrc_40:,.2f} ({discount_for_40:.1f}% discount)",
                value=target_mrc_40
            ))
            actions.append(RecommendationAction(
                text=f"For 50% GM: Request ${target_mrc_50:,.2f} ({discount_for_50:.1f}% discount)",
                value=target_mrc_50
            ))

            recommendations.append(Recommendation(
                priority=1,
                title=f"Negotiate with {vendor_name}",
                type="negotiate",
                strength="high" if negotiation_history else "medium",
                actions=actions
            ))

            # Recommendation 2: Use VPL as leverage
            if vendor_vpl:
                best_vpl = min(vendor_vpl, key=lambda x: x.mrc)
                best_vpl_gm = ((client_mrc - best_vpl.mrc) / client_mrc * 100) if client_mrc > 0 else 0
                savings = current_mrc - best_vpl.mrc

                recommendations.append(Recommendation(
                    priority=2,
                    title="Use Vendor Price List (VPL) - STRONGEST ARGUMENT",
                    type="vpl",
                    strength="very_high",
                    actions=[
                        RecommendationAction(
                            text=f"Their published price is ${best_vpl.mrc:,.2f} (GM: {best_vpl_gm:.1f}%)",
                            value=best_vpl.mrc
                        ),
                        RecommendationAction(
                            text=f"Savings vs current quote: ${savings:,.2f}/month ({(savings/current_mrc*100):.1f}%)",
                            value=savings
                        ),
                        RecommendationAction(
                            text=f"Argument: 'Your price list shows ${best_vpl.mrc:,.2f} for this service'",
                            value=None
                        )
                    ]
                ))

            # Recommendation 3: Use alternatives
            if alternatives:
                best_alt = alternatives[0]
                recommendations.append(Recommendation(
                    priority=3,
                    title="Use Alternatives as Leverage",
                    type="alternative",
                    strength="medium",
                    actions=[
                        RecommendationAction(
                            text=f"Best option: {best_alt.vendor_name} at ${best_alt.mrc:,.2f} (GM: {best_alt.gm:.1f}%)",
                            value=best_alt.mrc
                        ),
                        RecommendationAction(
                            text=f"Leverage: 'We have an offer from {best_alt.vendor_name} at ${best_alt.mrc:,.2f}'",
                            value=None
                        ),
                        RecommendationAction(
                            text="Use as negotiation tool, consider implementation time and SLAs",
                            value=None
                        )
                    ]
                ))
        else:
            # Margin is acceptable
            actions = []
            if vendor_vpl:
                best_vpl = min(vendor_vpl, key=lambda x: x.mrc)
                if best_vpl.mrc < current_mrc:
                    savings = current_mrc - best_vpl.mrc
                    actions.append(RecommendationAction(
                        text=f"VPL shows ${best_vpl.mrc:,.2f} (potential savings: ${savings:,.2f}/month)",
                        value=savings
                    ))
                    actions.append(RecommendationAction(
                        text="Consider requesting adjustment to published price",
                        value=None
                    ))

            if not actions:
                actions.append(RecommendationAction(
                    text="Monitor for changes in market pricing",
                    value=None
                ))
                actions.append(RecommendationAction(
                    text="Continue with current vendor at this price",
                    value=None
                ))

            recommendations.append(Recommendation(
                priority=1,
                title=f"Current margin is acceptable ({current_gm:.1f}%)",
                type="maintain",
                strength="low",
                actions=actions
            ))

        return recommendations

    def close(self):
        """Close connections"""
        if self.neo4j_client:
            self.neo4j_client.close()
