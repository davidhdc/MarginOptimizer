#!/usr/bin/env python3
"""
Margin Optimizer - Web Interface
Flask application for analyzing vendor quotes and generating negotiation strategies
"""

from flask import Flask, render_template, request, jsonify, session
from datetime import datetime
import traceback
import uuid
from neo4j.time import DateTime as Neo4jDateTime

from connectors.neo4j_client import Neo4jClient
from connectors.quickbase import QuickbaseClient
from analyze_service import analyze_service, show_negotiation_strategy, analyze_all_options

app = Flask(__name__)
app.secret_key = 'margin-optimizer-secret-key-change-in-production'

# Initialize clients globally
neo4j_client = None
qb_client = None


def convert_neo4j_types(obj):
    """
    Recursively convert Neo4j types (DateTime, Date, etc.) to JSON-serializable types
    """
    if obj is None:
        return None

    # Handle Neo4j DateTime explicitly
    if isinstance(obj, Neo4jDateTime):
        return obj.isoformat()

    # Handle other datetime-like objects
    if hasattr(obj, 'isoformat') and callable(getattr(obj, 'isoformat')):
        try:
            return obj.isoformat()
        except:
            pass

    # Handle dictionaries
    if isinstance(obj, dict):
        return {key: convert_neo4j_types(value) for key, value in obj.items()}

    # Handle lists/tuples
    if isinstance(obj, (list, tuple)):
        return [convert_neo4j_types(item) for item in obj]

    # Return as-is for primitives
    return obj


def init_clients():
    """Initialize database clients"""
    global neo4j_client, qb_client
    if neo4j_client is None:
        neo4j_client = Neo4jClient()
    if qb_client is None:
        qb_client = QuickbaseClient()


@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')


@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    """API endpoint to analyze a service"""
    try:
        data = request.json
        service_id = data.get('service_id', '').strip()
        vq_qb_id = data.get('vq_qb_id', '').strip()

        if not service_id:
            return jsonify({'error': 'Service ID is required'}), 400

        # Initialize clients
        init_clients()

        # Get service details
        service = neo4j_client.get_service_details(service_id)

        if not service:
            return jsonify({'error': f'Service {service_id} not found'}), 404

        # Get vendor quotes
        vendor_quotes = neo4j_client.get_vendor_quotes_for_service(
            service_id,
            include_nearby=True,
            radius_meters=2000  # 2km radius for nearby quotes
        )

        associated = vendor_quotes.get('associated', [])
        nearby = vendor_quotes.get('nearby', [])
        vpl = vendor_quotes.get('vpl', [])

        # Get Client MRC from VOC Lines (accurate source)
        voc_line = qb_client.get_voc_line_by_service(service_id)
        if voc_line.get('has_data'):
            client_mrc = voc_line.get('client_mrc', 0)
            service_currency = voc_line.get('currency') or service.get('service_currency', 'USD')
        else:
            # Fallback to Neo4j if no VOC Line found
            client_mrc = service.get('client_mrc', 0)
            service_currency = service.get('service_currency', 'USD')

        service_is_usd = (service_currency == 'USD')

        # Prepare response
        response = {
            'service': {
                'service_id': service['service_id'],
                'customer': service['customer'],
                'bandwidth_display': service['bandwidth_display'],
                'client_mrc': client_mrc,
                'currency': service_currency,
                'address': service['address'][:100] if service['address'] else 'N/A',
                'latitude': service['latitude'],
                'longitude': service['longitude']
            },
            'counts': {
                'associated': len(associated),
                'nearby': len(nearby),
                'vpl': len(vpl)
            },
            'vendor_quotes': [],
            'nearby_quotes': [],
            'vpl_options': []
        }

        # Process associated vendor quotes
        for vq in associated:
            vendor_name = vq.get('vendor_name', 'Unknown')
            vq_mrc_raw = vq.get('mrc', 0)
            vq_exchange_rate = vq.get('exchange_rate', 1.0)

            # Convert VQ to service currency
            if service_is_usd and vq_exchange_rate and vq_exchange_rate > 1:
                # VQ is in local currency (BRL), service is in USD - convert to USD
                vq_mrc = vq_mrc_raw / vq_exchange_rate
            else:
                # Both in same currency or no conversion needed
                vq_mrc = vq_mrc_raw

            gm = ((client_mrc - vq_mrc) / client_mrc * 100) if client_mrc > 0 else 0

            bw_bps = vq.get('bandwidth_bps')
            bw_display = f"{bw_bps / 1_000_000:.0f} Mbps" if bw_bps else vq.get('bandwidth', 'N/A')

            # Get negotiation stats (for VQ creation)
            stats = qb_client.get_vendor_negotiation_stats(vendor_name)

            # Get renewal stats (for renewals)
            renewal_stats = qb_client.get_vendor_renewal_stats(vendor_name)

            # Get delivered MRC total for this vendor
            delivered_mrc_stats = qb_client.get_vendor_delivered_mrc_total(vendor_name)

            vq_data = {
                'vendor_name': vendor_name,
                'quickbase_id': vq.get('quickbase_id'),
                'neo4j_id': vq.get('id'),
                'mrc': round(vq_mrc, 2),
                'mrc_currency': service_currency,
                'mrc_original': round(vq_mrc_raw, 2) if vq_mrc_raw != vq_mrc else None,
                'mrc_original_currency': 'BRL' if (vq_mrc_raw != vq_mrc and vq_exchange_rate and vq_exchange_rate > 1) else None,
                'exchange_rate': vq_exchange_rate if vq_exchange_rate and vq_exchange_rate > 1 else None,
                'gm': round(gm, 1),
                'gm_status': 'success' if gm >= 50 else 'warning' if gm >= 40 else 'danger',
                'bandwidth': bw_display,
                'status': vq.get('status', 'N/A'),
                'lead_time': vq.get('lead_time', 'N/A'),
                'has_negotiation_history': stats and stats.get('has_data', False),
                'negotiation_stats': None,
                'projected_with_negotiation': None,
                'has_renewal_history': renewal_stats and renewal_stats.get('has_data', False),
                'renewal_stats': None,
                'has_delivered_services': delivered_mrc_stats and delivered_mrc_stats.get('has_data', False),
                'delivered_mrc_total': round(delivered_mrc_stats.get('total_mrc_usd', 0), 2) if delivered_mrc_stats else 0,
                'delivered_count': delivered_mrc_stats.get('delivered_count', 0) if delivered_mrc_stats else 0
            }

            if stats and stats.get('has_data'):
                vq_data['negotiation_stats'] = {
                    'total_negotiations': stats['total_negotiations'],
                    'successful_negotiations': stats['successful_negotiations'],
                    'success_rate': round(stats['success_rate'], 1),
                    'avg_discount': round(stats['avg_discount'], 1),
                    'best_discount': round(stats['best_discount'], 1)
                }

                if stats['avg_discount'] > 0:
                    negotiated_mrc = vq_mrc * (1 - stats['avg_discount']/100)
                    negotiated_gm = ((client_mrc - negotiated_mrc) / client_mrc * 100) if client_mrc > 0 else 0

                    vq_data['projected_with_negotiation'] = {
                        'mrc': round(negotiated_mrc, 2),
                        'gm': round(negotiated_gm, 1),
                        'gm_status': 'success' if negotiated_gm >= 50 else 'warning' if negotiated_gm >= 40 else 'danger',
                        'avg_discount': round(stats['avg_discount'], 1),
                        'best_discount': round(stats['best_discount'], 1)
                    }

                    # Also calculate with best discount
                    if stats['best_discount'] > 0:
                        best_negotiated_mrc = vq_mrc * (1 - stats['best_discount']/100)
                        best_negotiated_gm = ((client_mrc - best_negotiated_mrc) / client_mrc * 100) if client_mrc > 0 else 0

                        vq_data['projected_with_negotiation']['best_mrc'] = round(best_negotiated_mrc, 2)
                        vq_data['projected_with_negotiation']['best_gm'] = round(best_negotiated_gm, 1)
                        vq_data['projected_with_negotiation']['best_gm_status'] = 'success' if best_negotiated_gm >= 50 else 'warning' if best_negotiated_gm >= 40 else 'danger'

            # Add renewal stats if available
            if renewal_stats and renewal_stats.get('has_data'):
                vq_data['renewal_stats'] = {
                    'total_renewals': renewal_stats['total_renewals'],
                    'successful_renewals': renewal_stats['successful_renewals'],
                    'success_rate': round(renewal_stats['success_rate'], 1),
                    'avg_discount': round(renewal_stats['avg_discount'], 1)
                }

            response['vendor_quotes'].append(vq_data)

        # Process nearby vendor quotes (within 2000m, last 12 months)
        # Convert Neo4j types first
        nearby = convert_neo4j_types(nearby)

        for vq in nearby:
            # Filter by distance: only include quotes within 2000 meters (2km)
            distance_meters = vq.get('distance_meters', 0)
            if distance_meters > 2000:
                continue  # Skip this quote if it's too far

            vendor_name = vq.get('vendor_name', 'Unknown')
            vq_mrc_raw = vq.get('mrc', 0)
            vq_exchange_rate = vq.get('exchange_rate', 1.0)

            # Convert VQ to service currency
            if service_is_usd and vq_exchange_rate and vq_exchange_rate > 1:
                # VQ is in local currency (BRL), service is in USD - convert to USD
                vq_mrc = vq_mrc_raw / vq_exchange_rate
            else:
                # Both in same currency or no conversion needed
                vq_mrc = vq_mrc_raw

            gm = ((client_mrc - vq_mrc) / client_mrc * 100) if client_mrc > 0 else 0

            bw_bps = vq.get('bandwidth_bps')
            bw_display = f"{bw_bps / 1_000_000:.0f} Mbps" if bw_bps else vq.get('bandwidth', 'N/A')

            # Get negotiation stats
            stats = qb_client.get_vendor_negotiation_stats(vendor_name)

            vq_data = {
                'vendor_name': vendor_name,
                'quickbase_id': vq.get('quickbase_id'),
                'neo4j_id': vq.get('vq_id'),
                'mrc': round(vq_mrc, 2),
                'mrc_currency': service_currency,
                'mrc_original': round(vq_mrc_raw, 2) if vq_mrc_raw != vq_mrc else None,
                'mrc_original_currency': 'BRL' if (vq_mrc_raw != vq_mrc and vq_exchange_rate and vq_exchange_rate > 1) else None,
                'exchange_rate': vq_exchange_rate if vq_exchange_rate and vq_exchange_rate > 1 else None,
                'gm': round(gm, 1),
                'gm_status': 'success' if gm >= 50 else 'warning' if gm >= 40 else 'danger',
                'bandwidth': bw_display,
                'status': vq.get('status', 'N/A'),
                'lead_time': vq.get('lead_time', 'N/A'),
                'distance_meters': round(vq.get('distance_meters', 0)),
                'date_created': vq.get('date_created', 'N/A'),
                'has_negotiation_history': stats and stats.get('has_data', False),
                'negotiation_stats': None,
                'projected_with_negotiation': None
            }

            if stats and stats.get('has_data'):
                vq_data['negotiation_stats'] = {
                    'total_negotiations': stats['total_negotiations'],
                    'successful_negotiations': stats['successful_negotiations'],
                    'success_rate': round(stats['success_rate'], 1),
                    'avg_discount': round(stats['avg_discount'], 1),
                    'best_discount': round(stats['best_discount'], 1)
                }

                if stats['avg_discount'] > 0:
                    negotiated_mrc = vq_mrc * (1 - stats['avg_discount']/100)
                    negotiated_gm = ((client_mrc - negotiated_mrc) / client_mrc * 100) if client_mrc > 0 else 0

                    vq_data['projected_with_negotiation'] = {
                        'mrc': round(negotiated_mrc, 2),
                        'gm': round(negotiated_gm, 1),
                        'gm_status': 'success' if negotiated_gm >= 50 else 'warning' if negotiated_gm >= 40 else 'danger',
                        'avg_discount': round(stats['avg_discount'], 1),
                        'best_discount': round(stats['best_discount'], 1)
                    }

                    # Also calculate with best discount
                    if stats['best_discount'] > 0:
                        best_negotiated_mrc = vq_mrc * (1 - stats['best_discount']/100)
                        best_negotiated_gm = ((client_mrc - best_negotiated_mrc) / client_mrc * 100) if client_mrc > 0 else 0

                        vq_data['projected_with_negotiation']['best_mrc'] = round(best_negotiated_mrc, 2)
                        vq_data['projected_with_negotiation']['best_gm'] = round(best_negotiated_gm, 1)
                        vq_data['projected_with_negotiation']['best_gm_status'] = 'success' if best_negotiated_gm >= 50 else 'warning' if best_negotiated_gm >= 40 else 'danger'

            response['nearby_quotes'].append(vq_data)

        # Process VPL options grouped by vendor
        # Filter to show only most relevant bandwidth options per vendor
        service_bw = service.get('bandwidth_bps')

        # Get exchange rate for VPL conversion (if needed)
        vpl_exchange_rate = None
        if not service_is_usd:
            # Service is in local currency, need exchange rate to convert VPL from USD to BRL
            # Use live exchange rate from Google/API
            from utils.currency import get_usd_to_brl_rate
            vpl_exchange_rate = get_usd_to_brl_rate()

        vpl_by_vendor = {}
        for v in vpl:
            vendor_name = v.get('vendor_name', 'Unknown')
            if vendor_name not in vpl_by_vendor:
                vpl_by_vendor[vendor_name] = {
                    'vendor_name': vendor_name,
                    'all_options': [],
                    'options': [],
                    'negotiation_stats': None
                }

            # VPL comes in USD from Neo4j (already converted from local currency)
            # Now we need to match the service currency
            vpl_mrc_usd = v.get('mrc', 0)  # This is already in USD

            if service_is_usd:
                # Service is in USD, use VPL as-is (USD)
                vpl_mrc = vpl_mrc_usd
            else:
                # Service is in local currency, convert VPL from USD to local
                vpl_mrc = vpl_mrc_usd * vpl_exchange_rate

            gm = ((client_mrc - vpl_mrc) / client_mrc * 100) if client_mrc > 0 and vpl_mrc > 0 else 0

            bw_bps = v.get('bandwidth_bps')
            bw_display = f"{bw_bps / 1_000_000:.0f} Mbps" if bw_bps else v.get('bandwidth', 'N/A')

            vpl_nrc_usd = v.get('nrc', 0)

            if service_is_usd:
                # Service is in USD, use VPL NRC as-is (USD)
                vpl_nrc = vpl_nrc_usd
            else:
                # Service is in local currency, convert VPL NRC from USD to local
                vpl_nrc = vpl_nrc_usd * vpl_exchange_rate

            option = {
                'mrc': round(vpl_mrc, 2),
                'mrc_currency': service_currency,
                'mrc_usd': round(vpl_mrc_usd, 2) if not service_is_usd else None,  # Only show USD ref if service is not in USD
                'nrc': round(vpl_nrc, 2),
                'nrc_currency': service_currency,
                'nrc_usd': round(vpl_nrc_usd, 2) if not service_is_usd else None,  # Only show USD ref if service is not in USD
                'gm': round(gm, 1),
                'gm_status': 'success' if gm >= 50 else 'warning' if gm >= 40 else 'danger',
                'bandwidth': bw_display,
                'bandwidth_bps': bw_bps,
                'service_type': v.get('service_type', 'N/A')
            }
            vpl_by_vendor[vendor_name]['all_options'].append(option)

        # Filter options per vendor to show only most relevant by bandwidth
        for vendor_name, vendor_data in vpl_by_vendor.items():
            all_opts = vendor_data['all_options']

            if not all_opts:
                continue

            # Sort by bandwidth
            all_opts.sort(key=lambda x: x.get('bandwidth_bps') or 0)

            if service_bw:
                # Find exact match
                exact_match = [o for o in all_opts if o.get('bandwidth_bps') == service_bw]

                if exact_match:
                    # If multiple exact matches, keep only one (best GM)
                    exact_match.sort(key=lambda x: x['gm'], reverse=True)
                    vendor_data['options'].append(exact_match[0])
                else:
                    # Find closest higher bandwidth
                    higher = [o for o in all_opts if o.get('bandwidth_bps', 0) > service_bw]
                    if higher:
                        vendor_data['options'].append(higher[0])  # First one (smallest higher)
                    else:
                        # No higher, use closest lower
                        lower = [o for o in all_opts if o.get('bandwidth_bps', 0) < service_bw]
                        if lower:
                            vendor_data['options'].append(lower[-1])  # Last one (largest lower)
            else:
                # No service bandwidth, show only best GM option
                all_opts.sort(key=lambda x: x['gm'], reverse=True)
                if all_opts:
                    vendor_data['options'].append(all_opts[0])

            # Remove temporary all_options
            del vendor_data['all_options']

        # Add negotiation stats to VPL vendors
        for vendor_name, vendor_data in vpl_by_vendor.items():
            stats = qb_client.get_vendor_negotiation_stats(vendor_name)
            if stats and stats.get('has_data'):
                vendor_data['negotiation_stats'] = {
                    'total_negotiations': stats['total_negotiations'],
                    'success_rate': round(stats['success_rate'], 1),
                    'avg_discount': round(stats['avg_discount'], 1),
                    'best_discount': round(stats['best_discount'], 1)
                }

                # Add projected prices with negotiation for each option
                if stats['avg_discount'] > 0:
                    for option in vendor_data['options']:
                        # Average discount projection
                        negotiated_mrc = option['mrc'] * (1 - stats['avg_discount']/100)
                        negotiated_gm = ((client_mrc - negotiated_mrc) / client_mrc * 100) if client_mrc > 0 else 0
                        option['projected_with_negotiation'] = {
                            'mrc': round(negotiated_mrc, 2),
                            'gm': round(negotiated_gm, 1),
                            'gm_status': 'success' if negotiated_gm >= 50 else 'warning' if negotiated_gm >= 40 else 'danger',
                            'avg_discount': round(stats['avg_discount'], 1),
                            'best_discount': round(stats['best_discount'], 1)
                        }

                        # Best discount projection
                        if stats['best_discount'] > 0:
                            best_negotiated_mrc = option['mrc'] * (1 - stats['best_discount']/100)
                            best_negotiated_gm = ((client_mrc - best_negotiated_mrc) / client_mrc * 100) if client_mrc > 0 else 0

                            option['projected_with_negotiation']['best_mrc'] = round(best_negotiated_mrc, 2)
                            option['projected_with_negotiation']['best_gm'] = round(best_negotiated_gm, 1)
                            option['projected_with_negotiation']['best_gm_status'] = 'success' if best_negotiated_gm >= 50 else 'warning' if best_negotiated_gm >= 40 else 'danger'

        response['vpl_options'] = list(vpl_by_vendor.values())

        return jsonify(response)

    except Exception as e:
        print(f"Error in api_analyze: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500



@app.route('/api/analyze-renewal', methods=['POST'])
def api_analyze_renewal():
    """API endpoint to analyze a service for renewal negotiation"""
    try:
        data = request.json
        service_id = data.get('service_id', '').strip()

        if not service_id:
            return jsonify({'error': 'Service ID is required'}), 400

        # Initialize clients
        init_clients()

        # Get service details from Neo4j
        service = neo4j_client.get_service_details(service_id)

        if not service:
            return jsonify({'error': f'Service {service_id} not found'}), 404

        # Get VOC Line data (current vendor and margin)
        voc_line = qb_client.get_voc_line_by_service(service_id)
        
        if not voc_line.get('has_data'):
            return jsonify({'error': f'No VOC Line found for service {service_id}'}), 404

        current_vendor = voc_line['vendor_name']
        current_mrc = voc_line['mrc_usd']
        current_gm = voc_line['gm_percent']

        # Get client MRC and currency from VOC Line (accurate source)
        client_mrc = voc_line.get('client_mrc', 0)
        service_currency = voc_line.get('currency') or service.get('service_currency', 'USD')
        
        # Get renewal statistics for current vendor
        renewal_stats = qb_client.get_vendor_renewal_stats(current_vendor)
        
        # Get detailed renewal history for this vendor
        renewal_history = qb_client.get_renewal_history_by_vendor(current_vendor, service_id)
        
        # Get negotiation stats for current vendor (from VQ creation)
        negotiation_stats = qb_client.get_vendor_negotiation_stats(current_vendor)
        
        # Get vendor quotes (nearby and VPL options)
        vendor_quotes = neo4j_client.get_vendor_quotes_for_service(
            service_id,
            include_nearby=True,
            radius_meters=10000
        )
        
        nearby = vendor_quotes.get('nearby', [])
        vpl = vendor_quotes.get('vpl', [])

        # Get service bandwidth in bps for filtering
        # Try Neo4j first, then fallback to Quickbase services table
        service_bandwidth_bps = service.get('bandwidth_bps')
        service_bandwidth_display = service.get('bandwidth_display', 'N/A')

        if not service_bandwidth_bps or service_bandwidth_display == 'N/A':
            # Bandwidth not in Neo4j, try Quickbase services table
            qb_bandwidth = qb_client.get_service_bandwidth(service_id)
            if qb_bandwidth.get('has_data'):
                service_bandwidth_bps = qb_bandwidth.get('bandwidth_bps')
                service_bandwidth_display = qb_bandwidth.get('bandwidth_display', 'N/A')

        # Build response
        response = {
            'service': {
                'service_id': service['service_id'],
                'customer': service['customer'],
                'bandwidth_display': service_bandwidth_display,
                'bandwidth_bps': service_bandwidth_bps,
                'client_mrc': client_mrc,
                'currency': service_currency,
                'address': service['address'][:100] if service['address'] else 'N/A',
                'latitude': service['latitude'],
                'longitude': service['longitude']
            },
            'voc_line': {
                'record_id': voc_line['record_id'],
                'vendor_name': current_vendor,
                'current_mrc': current_mrc,
                'current_gm_percent': current_gm,
                'current_gm_usd': voc_line['gm_usd'],
                'status': voc_line['status'],
                'bandwidth': voc_line['bandwidth'],
                'service_type': voc_line['service_type'],
                'lead_time': voc_line['lead_time'],
                'nrc_usd': voc_line['nrc_usd']
            },
            'current_vendor_stats': {
                'renewal_stats': None,
                'negotiation_stats': None,
                'renewal_history': []
            },
            'nearby_quotes': [],
            'vpl_options': [],
            'recommendations': []
        }
        
        # Add renewal stats if available
        if renewal_stats and renewal_stats.get('has_data'):
            response['current_vendor_stats']['renewal_stats'] = {
                'total_renewals': renewal_stats['total_renewals'],
                'successful_renewals': renewal_stats['successful_renewals'],
                'success_rate': round(renewal_stats['success_rate'], 1),
                'avg_discount': round(renewal_stats['avg_discount'], 1)
            }
        
        # Add negotiation stats if available
        if negotiation_stats and negotiation_stats.get('has_data'):
            response['current_vendor_stats']['negotiation_stats'] = {
                'total_negotiations': negotiation_stats['total_negotiations'],
                'successful_negotiations': negotiation_stats['successful_negotiations'],
                'success_rate': round(negotiation_stats['success_rate'], 1),
                'avg_discount': round(negotiation_stats['avg_discount'], 1)
            }
        
        # Add renewal history
        if renewal_history.get('has_data'):
            response['current_vendor_stats']['renewal_history'] = renewal_history['renewals'][:10]  # Last 10
        
        # Process nearby quotes (same vendor, different services)
        nearby = convert_neo4j_types(nearby)
        for vq in nearby:
            if vq.get('distance_meters', 0) > 2000:  # 2km for renewals
                continue
            
            if vq.get('vendor_name') != current_vendor:
                continue  # Only show same vendor
            
            vq_mrc = vq.get('mrc', 0)
            gm = ((client_mrc - vq_mrc) / client_mrc * 100) if client_mrc > 0 else 0
            
            response['nearby_quotes'].append({
                'service_id': vq.get('service_id'),
                'mrc': round(vq_mrc, 2),
                'gm': round(gm, 1),
                'distance_meters': round(vq.get('distance_meters', 0)),
                'date_created': vq.get('date_created')
            })
        
        # Process VPL options - filter by service bandwidth
        service_is_usd = (service_currency == 'USD')
        if not service_is_usd:
            from utils.currency import get_usd_to_brl_rate
            vpl_exchange_rate = get_usd_to_brl_rate()
        else:
            vpl_exchange_rate = None

        # First pass: collect VPLs with exact bandwidth match
        exact_match_vpls = []
        higher_bw_vpls = []

        for v in vpl:
            vpl_bw_bps = v.get('bandwidth_bps')

            # Skip VPLs without bandwidth info
            if not vpl_bw_bps:
                continue

            # Categorize by bandwidth
            if service_bandwidth_bps:
                if vpl_bw_bps == service_bandwidth_bps:
                    exact_match_vpls.append(v)
                elif vpl_bw_bps > service_bandwidth_bps:
                    higher_bw_vpls.append(v)
            else:
                # If service has no bandwidth, include all VPLs
                exact_match_vpls.append(v)

        # Determine which VPLs to show
        if service_bandwidth_bps:
            # Service has bandwidth defined
            if exact_match_vpls:
                # Show VPLs with exact bandwidth match
                vpls_to_show = exact_match_vpls
            elif higher_bw_vpls:
                # No exact match, show next higher bandwidth
                higher_bw_vpls.sort(key=lambda x: x.get('bandwidth_bps', float('inf')))
                next_higher_bw = higher_bw_vpls[0].get('bandwidth_bps')
                vpls_to_show = [v for v in higher_bw_vpls if v.get('bandwidth_bps') == next_higher_bw]
            else:
                vpls_to_show = []
        else:
            # Service has NO bandwidth - show only most cost-effective bandwidth
            if exact_match_vpls:
                from collections import defaultdict
                bw_groups = defaultdict(list)
                for v in exact_match_vpls:
                    bw_bps = v.get('bandwidth_bps')
                    if bw_bps:
                        bw_groups[bw_bps].append(v.get('mrc', float('inf')))

                if bw_groups:
                    # Find bandwidth with lowest average MRC
                    best_bw = min(bw_groups.keys(),
                                key=lambda bw: sum(bw_groups[bw]) / len(bw_groups[bw]) if bw_groups[bw] else float('inf'))
                    # Show all VPLs with that bandwidth
                    vpls_to_show = [v for v in exact_match_vpls if v.get('bandwidth_bps') == best_bw]
                else:
                    vpls_to_show = []
            else:
                vpls_to_show = []

        # Process selected VPLs
        for v in vpls_to_show:
            vpl_mrc_usd = v.get('mrc', 0)

            if service_is_usd:
                vpl_mrc = vpl_mrc_usd
            else:
                vpl_mrc = vpl_mrc_usd * vpl_exchange_rate

            gm = ((client_mrc - vpl_mrc) / client_mrc * 100) if client_mrc > 0 and vpl_mrc > 0 else 0

            bw_bps = v.get('bandwidth_bps')
            bw_display = f"{bw_bps / 1_000_000:.0f} Mbps" if bw_bps else v.get('bandwidth', 'N/A')

            response['vpl_options'].append({
                'vendor_name': v.get('vendor_name', 'N/A'),
                'bandwidth': bw_display,
                'bandwidth_bps': bw_bps,
                'mrc': round(vpl_mrc, 2),
                'mrc_currency': service_currency,
                'nrc': v.get('nrc', 0),
                'gm': round(gm, 1),
                'gm_status': 'success' if gm >= 50 else 'warning' if gm >= 40 else 'danger',
                'service_type': v.get('service_type', 'N/A'),
                'is_current_vendor': v.get('vendor_name') == current_vendor
            })
        
        # Generate renewal recommendations
        recommendations = []

        # Convert current_mrc to service currency for fair comparisons with VPLs
        if service_is_usd:
            current_mrc_in_service_currency = current_mrc
        else:
            current_mrc_in_service_currency = current_mrc * vpl_exchange_rate

        # Recommendation 1: Based on renewal history success rate
        if renewal_stats and renewal_stats.get('has_data'):
            if renewal_stats['success_rate'] >= 50:
                expected_discount = renewal_stats['avg_discount']
                expected_mrc = current_mrc * (1 - expected_discount/100)
                expected_gm = ((client_mrc - expected_mrc) / client_mrc * 100) if client_mrc > 0 else 0
                
                recommendations.append({
                    'priority': 1,
                    'strategy': f"Negotiate renewal with {current_vendor}",
                    'rationale': f"High renewal success rate ({renewal_stats['success_rate']:.1f}%) with average {renewal_stats['avg_discount']:.1f}% discount",
                    'expected_discount': round(expected_discount, 1),
                    'expected_mrc': round(expected_mrc, 2),
                    'expected_gm': round(expected_gm, 1),
                    'confidence': 'high' if renewal_stats['success_rate'] >= 70 else 'medium'
                })
            else:
                recommendations.append({
                    'priority': 1,
                    'strategy': f"Consider alternative vendors",
                    'rationale': f"Low renewal success rate with {current_vendor} ({renewal_stats['success_rate']:.1f}%)",
                    'confidence': 'medium'
                })
        
        # Recommendation 2: Based on VPL availability from current vendor
        current_vendor_vpls = [v for v in response['vpl_options'] if v['is_current_vendor']]
        if current_vendor_vpls:
            best_current_vpl = min(current_vendor_vpls, key=lambda x: x['mrc'])
            if best_current_vpl['mrc'] < current_mrc_in_service_currency:
                savings = current_mrc_in_service_currency - best_current_vpl['mrc']
                savings_pct = (savings / current_mrc_in_service_currency * 100) if current_mrc_in_service_currency > 0 else 0

                recommendations.append({
                    'priority': 2,
                    'strategy': f"Request VPL pricing from {current_vendor}",
                    'rationale': f"VPL available at {best_current_vpl['mrc']:.2f} {service_currency} ({best_current_vpl['bandwidth']}) - {savings_pct:.1f}% lower than current MRC",
                    'expected_mrc': best_current_vpl['mrc'],
                    'expected_gm': best_current_vpl['gm'],
                    'confidence': 'high',
                    'vendor_name': current_vendor
                })

        # Recommendation 3: Based on alternative vendor VPLs at same location
        alternative_vendor_vpls = [v for v in response['vpl_options'] if not v['is_current_vendor']]
        if alternative_vendor_vpls:
            # Find best alternative VPL
            best_alt_vpl = min(alternative_vendor_vpls, key=lambda x: x['mrc'])
            if best_alt_vpl['mrc'] < current_mrc_in_service_currency:
                savings = current_mrc_in_service_currency - best_alt_vpl['mrc']
                savings_pct = (savings / current_mrc_in_service_currency * 100) if current_mrc_in_service_currency > 0 else 0

                recommendations.append({
                    'priority': 3,
                    'strategy': f"Leverage {best_alt_vpl['vendor_name']} VPL as negotiation leverage",
                    'rationale': f"Alternative vendor VPL at {best_alt_vpl['mrc']:.2f} {service_currency} ({best_alt_vpl['bandwidth']}) - {savings_pct:.1f}% lower. Use as leverage with {current_vendor} or consider switching",
                    'expected_mrc': best_alt_vpl['mrc'],
                    'expected_gm': best_alt_vpl['gm'],
                    'confidence': 'medium',
                    'vendor_name': best_alt_vpl['vendor_name'],
                    'alternative_vendor': True
                })
        
        # Recommendation 4: Market comparison - low margin alert
        if current_gm < 40 and not alternative_vendor_vpls:
            recommendations.append({
                'priority': 4,
                'strategy': "Evaluate alternative vendors",
                'rationale': f"Current gross margin ({current_gm:.1f}%) is below target (40%). No VPL alternatives found at this location.",
                'confidence': 'medium'
            })
        
        response['recommendations'] = sorted(recommendations, key=lambda x: x['priority'])
        
        return jsonify(response)

    except Exception as e:
        print(f"Error in api_analyze_renewal: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/strategy/<service_id>/<int:vq_qb_id>', methods=['GET', 'POST'])
def api_strategy(service_id, vq_qb_id):
    """API endpoint to get negotiation strategy for specific VQ"""
    try:
        # Initialize clients
        init_clients()

        # Get service details
        service = neo4j_client.get_service_details(service_id)

        if not service:
            return jsonify({'error': f'Service {service_id} not found'}), 404

        # Get VPL options from request body (if provided via POST)
        vpl_options_from_analyze = None
        if request.method == 'POST':
            request_data = request.get_json() or {}
            vpl_options_from_analyze = request_data.get('vpl_options', [])

        # Get vendor quotes
        vendor_quotes = neo4j_client.get_vendor_quotes_for_service(
            service_id,
            include_nearby=True,
            radius_meters=2000  # 2km radius for nearby quotes
        )

        associated = vendor_quotes.get('associated', [])
        vpl = vendor_quotes.get('vpl', [])

        # Find target VQ
        target_vq = None
        for vq in associated:
            if vq.get('quickbase_id') == vq_qb_id:
                target_vq = vq
                break

        if not target_vq:
            return jsonify({'error': f'VQ {vq_qb_id} not found for service'}), 404

        # Get Client MRC from VOC Lines (accurate source)
        voc_line = qb_client.get_voc_line_by_service(service_id)
        if voc_line.get('has_data'):
            client_mrc = voc_line.get('client_mrc', 0)
            service_currency = voc_line.get('currency') or service.get('service_currency', 'USD')
        else:
            # Fallback to Neo4j if no VOC Line found
            client_mrc = service.get('client_mrc', 0)
            service_currency = service.get('service_currency', 'USD')

        vendor_name = target_vq.get('vendor_name', 'Unknown')
        current_mrc = target_vq.get('mrc', 0)
        current_gm = ((client_mrc - current_mrc) / client_mrc * 100) if client_mrc > 0 else 0

        # Get negotiation history
        stats = qb_client.get_vendor_negotiation_stats(vendor_name)

        # Calculate targets
        target_mrc_50 = client_mrc * 0.5  # 50% GM
        target_mrc_40 = client_mrc * 0.6  # 40% GM

        discount_for_40 = ((current_mrc - target_mrc_40) / current_mrc * 100) if current_mrc > 0 else 0
        discount_for_50 = ((current_mrc - target_mrc_50) / current_mrc * 100) if current_mrc > 0 else 0

        response = {
            'service': {
                'service_id': service['service_id'],
                'customer': service['customer'],
                'bandwidth_display': service['bandwidth_display'],
                'client_mrc': client_mrc,
                'currency': service_currency
            },
            'vendor_quote': {
                'vendor_name': vendor_name,
                'quickbase_id': vq_qb_id,
                'current_mrc': current_mrc,
                'current_gm': round(current_gm, 1),
                'gm_status': 'success' if current_gm >= 50 else 'warning' if current_gm >= 40 else 'danger',
                'lead_time': target_vq.get('lead_time', 'N/A'),
                'status': target_vq.get('status', 'N/A')
            },
            'negotiation_history': None,
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
            'vendor_vpl': [],
            'alternatives': [],
            'recommendations': []
        }

        # Add negotiation history
        if stats and stats.get('has_data'):
            negotiated_mrc = current_mrc * (1 - stats['avg_discount']/100)
            negotiated_gm = ((client_mrc - negotiated_mrc) / client_mrc * 100) if client_mrc > 0 else 0

            response['negotiation_history'] = {
                'total_negotiations': stats['total_negotiations'],
                'successful_negotiations': stats['successful_negotiations'],
                'success_rate': round(stats['success_rate'], 1),
                'avg_discount': round(stats['avg_discount'], 1),
                'projected_mrc': round(negotiated_mrc, 2),
                'projected_gm': round(negotiated_gm, 1),
                'projected_gm_status': 'success' if negotiated_gm >= 50 else 'warning' if negotiated_gm >= 40 else 'danger'
            }

        # Add vendor VPL options - use pre-calculated VPL options from analyze if available
        if vpl_options_from_analyze:
            # Use VPL options from the analyze endpoint (already filtered and currency-converted)
            for vpl_vendor in vpl_options_from_analyze:
                if vpl_vendor.get('vendor_name') == vendor_name:
                    # This is the current vendor - add all their options
                    for opt in vpl_vendor.get('options', []):
                        vpl_mrc = opt.get('mrc', 0)
                        vpl_gm = opt.get('gm', 0)
                        savings = current_mrc - vpl_mrc

                        response['vendor_vpl'].append({
                            'mrc': vpl_mrc,
                            'mrc_currency': opt.get('mrc_currency', 'USD'),
                            'nrc': opt.get('nrc', 0),
                            'nrc_currency': opt.get('nrc_currency', 'USD'),
                            'gm': vpl_gm,
                            'gm_status': 'success' if vpl_gm >= 50 else 'warning' if vpl_gm >= 40 else 'danger',
                            'bandwidth': opt.get('bandwidth', 'N/A'),
                            'service_type': opt.get('service_type', 'N/A'),
                            'savings': round(savings, 2),
                            'savings_percent': round((savings / current_mrc * 100), 1) if current_mrc > 0 else 0
                        })
                else:
                    # Alternative vendors - add top option from each
                    for opt in vpl_vendor.get('options', [])[:1]:  # Just the first option
                        response['alternatives'].append({
                            'vendor_name': vpl_vendor.get('vendor_name', 'Unknown'),
                            'mrc': opt.get('mrc', 0),
                            'mrc_currency': opt.get('mrc_currency', 'USD'),
                            'gm': opt.get('gm', 0),
                            'gm_status': 'success' if opt.get('gm', 0) >= 50 else 'warning' if opt.get('gm', 0) >= 40 else 'danger',
                            'bandwidth': opt.get('bandwidth', 'N/A'),
                            'service_type': opt.get('service_type', 'N/A')
                        })
        else:
            # Fallback: Use original VPL logic if no pre-calculated options provided
            vendor_vpl = [v for v in vpl if v.get('vendor_name') == vendor_name]
            if vendor_vpl:
                # Filter to show only most relevant bandwidth option
                service_bw = service.get('bandwidth_bps')

                if service_bw:
                    # Find exact match
                    exact_match = [v for v in vendor_vpl if v.get('bandwidth_bps') == service_bw]

                    if exact_match:
                        # If multiple, keep best GM
                        vendor_vpl_filtered = sorted(exact_match, key=lambda x: ((client_mrc - x.get('mrc', 0)) / client_mrc * 100), reverse=True)[:1]
                    else:
                        # Find closest higher bandwidth
                        vendor_vpl.sort(key=lambda x: x.get('bandwidth_bps') or 0)
                        higher = [v for v in vendor_vpl if v.get('bandwidth_bps', 0) > service_bw]
                        if higher:
                            vendor_vpl_filtered = [higher[0]]
                        else:
                            # No higher, use closest lower
                            lower = [v for v in vendor_vpl if v.get('bandwidth_bps', 0) < service_bw]
                            vendor_vpl_filtered = [lower[-1]] if lower else []
                else:
                    # No service bandwidth, show best GM option
                    vendor_vpl_filtered = sorted(vendor_vpl, key=lambda x: ((client_mrc - x.get('mrc', 0)) / client_mrc * 100), reverse=True)[:1]

                for v in vendor_vpl_filtered:
                    vpl_mrc = v.get('mrc', 0)
                    vpl_gm = ((client_mrc - vpl_mrc) / client_mrc * 100) if client_mrc > 0 else 0
                    savings = current_mrc - vpl_mrc

                    bw_bps = v.get('bandwidth_bps')
                    bw_display = f"{bw_bps / 1_000_000:.0f} Mbps" if bw_bps else v.get('bandwidth', 'N/A')

                    response['vendor_vpl'].append({
                        'mrc': vpl_mrc,
                        'nrc': v.get('nrc', 0),
                        'gm': round(vpl_gm, 1),
                        'gm_status': 'success' if vpl_gm >= 50 else 'warning' if vpl_gm >= 40 else 'danger',
                        'bandwidth': bw_display,
                        'service_type': v.get('service_type', 'N/A'),
                        'savings': round(savings, 2),
                        'savings_percent': round((savings / current_mrc * 100), 1) if current_mrc > 0 else 0
                    })

            # Add alternatives from other vendors
            other_vendors_vpl = [v for v in vpl if v.get('vendor_name') != vendor_name]
            if other_vendors_vpl:
                other_vendors_vpl.sort(key=lambda x: ((client_mrc - x.get('mrc', 0)) / client_mrc * 100), reverse=True)

                for v in other_vendors_vpl[:5]:  # Top 5 alternatives
                    alt_mrc = v.get('mrc', 0)
                    alt_gm = ((client_mrc - alt_mrc) / client_mrc * 100)

                    bw_bps = v.get('bandwidth_bps')
                    bw_display = f"{bw_bps / 1_000_000:.0f} Mbps" if bw_bps else v.get('bandwidth', 'N/A')

                    response['alternatives'].append({
                        'vendor_name': v.get('vendor_name', 'Unknown'),
                        'mrc': alt_mrc,
                        'gm': round(alt_gm, 1),
                        'gm_status': 'success' if alt_gm >= 50 else 'warning' if alt_gm >= 40 else 'danger',
                        'bandwidth': bw_display,
                        'service_type': v.get('service_type', 'N/A')
                    })

        # Generate recommendations
        if current_gm < 50:
            # Recommendation 1: Negotiate with current vendor
            rec1 = {
                'priority': 1,
                'title': f'Negotiate with {vendor_name}',
                'type': 'negotiate',
                'strength': 'high' if stats and stats.get('has_data') else 'medium',
                'actions': []
            }

            if stats and stats.get('has_data'):
                rec1['actions'].append({
                    'text': f"Historical average discount: {stats['avg_discount']:.1f}% (success rate: {stats['success_rate']:.1f}%)",
                    'value': round(current_mrc * (1 - stats['avg_discount']/100), 2)
                })

            rec1['actions'].append({
                'text': f"For 40% GM: Request ${target_mrc_40:,.2f} ({discount_for_40:.1f}% discount)",
                'value': target_mrc_40
            })
            rec1['actions'].append({
                'text': f"For 50% GM: Request ${target_mrc_50:,.2f} ({discount_for_50:.1f}% discount)",
                'value': target_mrc_50
            })

            response['recommendations'].append(rec1)

            # Recommendation 2: Use VPL as leverage
            if response['vendor_vpl']:
                best_vpl = min(response['vendor_vpl'], key=lambda x: x.get('mrc', float('inf')))
                best_vpl_mrc = best_vpl.get('mrc', 0)
                best_vpl_gm = ((client_mrc - best_vpl_mrc) / client_mrc * 100)
                savings = current_mrc - best_vpl_mrc

                rec2 = {
                    'priority': 2,
                    'title': 'Use Vendor Price List (VPL) - STRONGEST ARGUMENT',
                    'type': 'vpl',
                    'strength': 'very_high',
                    'actions': [
                        {
                            'text': f"Their published price is ${best_vpl_mrc:,.2f} (GM: {best_vpl_gm:.1f}%)",
                            'value': best_vpl_mrc
                        },
                        {
                            'text': f"Savings vs current quote: ${savings:,.2f}/month ({(savings/current_mrc*100):.1f}%)",
                            'value': savings
                        },
                        {
                            'text': f"Argument: 'Your price list shows ${best_vpl_mrc:,.2f} for this service'",
                            'value': None
                        }
                    ]
                }
                response['recommendations'].append(rec2)

            # Recommendation 3: Use alternatives as leverage
            if response['alternatives']:
                best_alt = response['alternatives'][0]
                rec3 = {
                    'priority': 3,
                    'title': 'Use Alternatives as Leverage',
                    'type': 'alternative',
                    'strength': 'medium',
                    'actions': [
                        {
                            'text': f"Best option: {best_alt['vendor_name']} at ${best_alt['mrc']:,.2f} (GM: {best_alt['gm']:.1f}%)",
                            'value': best_alt['mrc']
                        },
                        {
                            'text': f"Leverage: 'We have an offer from {best_alt['vendor_name']} at ${best_alt['mrc']:,.2f}'",
                            'value': None
                        },
                        {
                            'text': "Use as negotiation tool, consider implementation time and SLAs",
                            'value': None
                        }
                    ]
                }
                response['recommendations'].append(rec3)
        else:
            # Margin is acceptable
            rec = {
                'priority': 1,
                'title': f"Current margin is acceptable ({current_gm:.1f}%)",
                'type': 'maintain',
                'strength': 'low',
                'actions': []
            }

            if response['vendor_vpl']:
                best_vpl = min(response['vendor_vpl'], key=lambda x: x.get('mrc', float('inf')))
                best_vpl_mrc = best_vpl.get('mrc', 0)
                if best_vpl_mrc < current_mrc:
                    savings = current_mrc - best_vpl_mrc
                    rec['actions'].append({
                        'text': f"VPL shows ${best_vpl_mrc:,.2f} (potential savings: ${savings:,.2f}/month)",
                        'value': savings
                    })
                    rec['actions'].append({
                        'text': "Consider requesting adjustment to published price",
                        'value': None
                    })

            if not rec['actions']:
                rec['actions'].append({
                    'text': "No immediate action needed, monitor market prices",
                    'value': None
                })

            response['recommendations'].append(rec)

        return jsonify(response)

    except Exception as e:
        print(f"Error in api_strategy: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/vendor-autocomplete', methods=['GET'])
def api_vendor_autocomplete():
    """API endpoint to get vendor name suggestions for autocomplete"""
    try:
        init_clients()

        search_term = request.args.get('q', '').strip()
        if not search_term or len(search_term) < 2:
            return jsonify({'vendors': []})

        # Get unique vendor names from Neo4j
        neo4j_vendors = neo4j_client.get_vendor_names(search_term)

        # Get vendor names from Quickbase (VOC Lines and Renewals tables)
        qb_vendors = qb_client.get_vendor_names(search_term)

        # Combine and deduplicate
        all_vendors = set(neo4j_vendors + qb_vendors)
        vendor_list = sorted(list(all_vendors))[:20]  # Limit to 20 results

        return jsonify({'vendors': vendor_list})

    except Exception as e:
        print(f"Error in api_vendor_autocomplete: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyze-vendor', methods=['POST'])
def api_analyze_vendor():
    """API endpoint to get vendor historical data (renewals + new contracts)"""
    try:
        init_clients()

        vendor_name = request.json.get('vendor_name', '').strip()
        if not vendor_name:
            return jsonify({'error': 'Vendor name is required'}), 400

        # Get renewal history from Quickbase
        renewal_history = qb_client.get_vendor_renewal_history(vendor_name)

        # Get new contract history from Neo4j (VendorQuotes)
        new_contract_history = neo4j_client.get_vendor_contract_history(vendor_name)

        # Calculate statistics
        total_renewals = len(renewal_history.get('records', []))
        total_new_contracts = len(new_contract_history)

        # Calculate renewal stats
        successful_renewals = 0
        total_discount = 0
        discount_count = 0

        for renewal in renewal_history.get('records', []):
            if renewal.get('status') in ['Renewed', 'Active']:
                successful_renewals += 1

            discount = renewal.get('discount_percent')
            if discount is not None:
                total_discount += discount
                discount_count += 1

        avg_discount = (total_discount / discount_count) if discount_count > 0 else 0
        success_rate = (successful_renewals / total_renewals * 100) if total_renewals > 0 else 0

        response = {
            'vendor_name': vendor_name,
            'summary': {
                'total_renewals': total_renewals,
                'total_new_contracts': total_new_contracts,
                'avg_discount': round(avg_discount, 1),
                'success_rate': round(success_rate, 1),
                'successful_renewals': successful_renewals
            },
            'renewal_history': renewal_history.get('records', []),
            'new_contract_history': new_contract_history
        }

        return jsonify(response)

    except Exception as e:
        print(f"Error in api_analyze_vendor: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/health')
def health():
    """Health check endpoint"""
    try:
        init_clients()
        return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "="*70)
    print("  MARGIN OPTIMIZER - WEB INTERFACE")
    print("="*70)
    print("\n  Starting server...")
    print("  Access the application at: http://localhost:5000")
    print("\n  Press CTRL+C to stop the server")
    print("="*70 + "\n")

    app.run(debug=True, host='0.0.0.0', port=5000)
