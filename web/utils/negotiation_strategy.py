"""
Negotiation Strategy Generator

Generates intelligent negotiation strategies by combining:
1. VQ nearby data (same vendor, nearby locations)
2. Renewal discount history
3. New contract negotiation history
"""

from typing import Dict, List, Optional


def generate_negotiation_strategy(
    vendor_name: str,
    current_mrc: float,
    client_mrc: float,
    nearby_quotes: List[Dict],
    negotiation_stats: Dict,
    renewal_stats: Optional[Dict] = None
) -> Dict:
    """
    Generate intelligent negotiation strategy based on multiple data sources

    Args:
        vendor_name: Vendor name
        current_mrc: Current vendor quote MRC
        client_mrc: Client MRC (service cost)
        nearby_quotes: List of nearby quotes from same vendor
        negotiation_stats: New contract negotiation statistics
        renewal_stats: Renewal negotiation statistics (optional)

    Returns:
        Dict with negotiation strategy recommendations
    """

    current_gm = ((client_mrc - current_mrc) / client_mrc * 100) if client_mrc > 0 else 0

    # Target GMs
    target_mrc_50 = client_mrc * 0.5  # 50% GM
    target_mrc_40 = client_mrc * 0.6  # 40% GM

    # Required discounts to reach targets
    discount_for_40 = ((current_mrc - target_mrc_40) / current_mrc * 100) if current_mrc > 0 else 0
    discount_for_50 = ((current_mrc - target_mrc_50) / current_mrc * 100) if current_mrc > 0 else 0

    # Initialize strategy
    strategy = {
        'vendor_name': vendor_name,
        'current_situation': {
            'current_mrc': round(current_mrc, 2),
            'current_gm': round(current_gm, 1),
            'gm_status': 'success' if current_gm >= 50 else 'warning' if current_gm >= 40 else 'danger'
        },
        'targets': {
            'gm_40': {
                'target_mrc': round(target_mrc_40, 2),
                'discount_needed': round(discount_for_40, 1)
            },
            'gm_50': {
                'target_mrc': round(target_mrc_50, 2),
                'discount_needed': round(discount_for_50, 1)
            }
        },
        'evidence': {
            'nearby_quotes': [],
            'historical_new_contracts': {},
            'historical_renewals': {}
        },
        'recommendations': []
    }

    # 1. Analyze nearby quotes from same vendor
    if nearby_quotes:
        nearby_analysis = []
        lower_prices_count = 0
        avg_nearby_mrc = 0

        for quote in nearby_quotes:
            nearby_mrc = quote.get('mrc', 0)
            nearby_gm = quote.get('gm', 0)
            distance = quote.get('distance_meters', 0)

            if nearby_mrc > 0:
                avg_nearby_mrc += nearby_mrc

                # Check if nearby quote has better pricing
                if nearby_mrc < current_mrc:
                    lower_prices_count += 1
                    discount_vs_current = ((current_mrc - nearby_mrc) / current_mrc * 100)

                    nearby_analysis.append({
                        'service_id': quote.get('service_id', 'N/A'),
                        'distance_km': round(distance / 1000, 2),
                        'mrc': round(nearby_mrc, 2),
                        'gm': round(nearby_gm, 1),
                        'discount_vs_current': round(discount_vs_current, 1),
                        'evidence_type': 'lower_price'
                    })

        if nearby_analysis:
            avg_nearby_mrc = avg_nearby_mrc / len(nearby_quotes)
            strategy['evidence']['nearby_quotes'] = nearby_analysis

            if lower_prices_count > 0:
                best_nearby = min(nearby_analysis, key=lambda x: x['mrc'])
                strategy['recommendations'].append({
                    'type': 'nearby_pricing',
                    'priority': 'high',
                    'title': f'{vendor_name} has {lower_prices_count} nearby quote(s) with lower pricing',
                    'description': f'Best nearby quote: {best_nearby["mrc"]} ({best_nearby["discount_vs_current"]}% lower) at {best_nearby["distance_km"]}km. Strong negotiation leverage - vendor offers better pricing for similar locations.',
                    'target_discount': best_nearby['discount_vs_current'],
                    'confidence': 'high'
                })

    # 2. Analyze historical new contract negotiations
    if negotiation_stats and negotiation_stats.get('has_data'):
        avg_discount = negotiation_stats.get('avg_discount', 0)
        best_discount = negotiation_stats.get('best_discount', 0)
        total_negotiations = negotiation_stats.get('total_negotiations', 0)
        success_rate = negotiation_stats.get('success_rate', 0)

        strategy['evidence']['historical_new_contracts'] = {
            'total_negotiations': total_negotiations,
            'success_rate': round(success_rate, 1),
            'avg_discount': round(avg_discount, 1),
            'best_discount': round(best_discount, 1)
        }

        # Calculate projected MRCs
        projected_avg_mrc = current_mrc * (1 - avg_discount/100)
        projected_best_mrc = current_mrc * (1 - best_discount/100)

        projected_avg_gm = ((client_mrc - projected_avg_mrc) / client_mrc * 100) if client_mrc > 0 else 0
        projected_best_gm = ((client_mrc - projected_best_mrc) / client_mrc * 100) if client_mrc > 0 else 0

        strategy['evidence']['historical_new_contracts']['projected_with_avg'] = {
            'mrc': round(projected_avg_mrc, 2),
            'gm': round(projected_avg_gm, 1),
            'discount': round(avg_discount, 1)
        }

        strategy['evidence']['historical_new_contracts']['projected_with_best'] = {
            'mrc': round(projected_best_mrc, 2),
            'gm': round(projected_best_gm, 1),
            'discount': round(best_discount, 1)
        }

        # Recommendations based on historical new contracts
        if avg_discount > 0:
            confidence = 'high' if total_negotiations >= 10 else 'medium' if total_negotiations >= 5 else 'low'

            # Always recommend negotiation based on historical data
            strategy['recommendations'].append({
                'type': 'historical_new_contract',
                'priority': 'high',
                'title': f'{vendor_name} historically offers {avg_discount:.1f}% average discount on new contracts',
                'description': f'Based on {total_negotiations} negotiations with {success_rate:.1f}% success rate. Best case: {best_discount:.1f}% discount. Projected GM with avg discount: {projected_avg_gm:.1f}%',
                'target_discount': avg_discount,
                'best_case_discount': best_discount,
                'confidence': confidence,
                'sample_size': total_negotiations
            })

            # Always show best case scenario when available
            if best_discount > avg_discount:
                strategy['recommendations'].append({
                    'type': 'best_case_opportunity',
                    'priority': 'high',
                    'title': f'Best historical discount: {best_discount:.1f}% (improve margin to {projected_best_gm:.1f}% GM)',
                    'description': f'{vendor_name} has previously offered up to {best_discount:.1f}% discount. Even if current GM is acceptable, there\'s opportunity for improvement based on vendor history.',
                    'target_discount': best_discount,
                    'confidence': 'medium',
                    'sample_size': total_negotiations
                })

    # 3. Analyze historical renewals
    if renewal_stats and renewal_stats.get('has_data'):
        renewal_avg_discount = renewal_stats.get('avg_discount', 0)
        total_renewals = renewal_stats.get('total_renewals', 0)
        renewal_success_rate = renewal_stats.get('success_rate', 0)

        strategy['evidence']['historical_renewals'] = {
            'total_renewals': total_renewals,
            'success_rate': round(renewal_success_rate, 1),
            'avg_discount': round(renewal_avg_discount, 1)
        }

        if renewal_avg_discount > 0:
            projected_renewal_mrc = current_mrc * (1 - renewal_avg_discount/100)
            projected_renewal_gm = ((client_mrc - projected_renewal_mrc) / client_mrc * 100) if client_mrc > 0 else 0

            confidence = 'high' if total_renewals >= 5 else 'medium' if total_renewals >= 3 else 'low'

            strategy['recommendations'].append({
                'type': 'historical_renewal',
                'priority': 'medium',
                'title': f'{vendor_name} historically offers {renewal_avg_discount:.1f}% average discount on renewals',
                'description': f'Based on {total_renewals} renewals with {renewal_success_rate:.1f}% success rate. Projected GM with discount: {projected_renewal_gm:.1f}%. Negotiate based on vendor\'s proven flexibility.',
                'target_discount': renewal_avg_discount,
                'confidence': confidence,
                'sample_size': total_renewals
            })

    # 4. Combined strategy recommendation
    all_discounts = []

    if negotiation_stats and negotiation_stats.get('avg_discount', 0) > 0:
        all_discounts.append(negotiation_stats['avg_discount'])

    if renewal_stats and renewal_stats.get('avg_discount', 0) > 0:
        all_discounts.append(renewal_stats['avg_discount'])

    if nearby_quotes:
        for quote in nearby_quotes:
            nearby_mrc = quote.get('mrc', 0)
            if nearby_mrc > 0 and nearby_mrc < current_mrc:
                discount = ((current_mrc - nearby_mrc) / current_mrc * 100)
                all_discounts.append(discount)

    if all_discounts:
        recommended_discount = sum(all_discounts) / len(all_discounts)
        max_discount = max(all_discounts)

        recommended_mrc = current_mrc * (1 - recommended_discount/100)
        recommended_gm = ((client_mrc - recommended_mrc) / client_mrc * 100) if client_mrc > 0 else 0

        strategy['overall_recommendation'] = {
            'recommended_discount': round(recommended_discount, 1),
            'max_discount': round(max_discount, 1),
            'recommended_mrc': round(recommended_mrc, 2),
            'projected_gm': round(recommended_gm, 1),
            'gm_status': 'success' if recommended_gm >= 50 else 'warning' if recommended_gm >= 40 else 'danger',
            'data_sources': len(all_discounts),
            'confidence': 'high' if len(all_discounts) >= 3 else 'medium' if len(all_discounts) >= 2 else 'low'
        }

    # Sort recommendations by priority
    priority_order = {'high': 1, 'medium': 2, 'low': 3}
    strategy['recommendations'].sort(key=lambda x: priority_order.get(x.get('priority', 'low'), 3))

    return strategy
