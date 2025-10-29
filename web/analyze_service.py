#!/usr/bin/env python3
"""
Margin Optimizer - Service Analysis Tool
Analyzes vendor quotes and provides negotiation strategies

Usage:
  1. Analyze all options: python analyze_service.py <SERVICE_ID>
  2. Strategy for specific VQ: python analyze_service.py <SERVICE_ID> <VQ_QB_ID>
"""

from connectors.neo4j_client import Neo4jClient
from connectors.quickbase import QuickbaseClient
import sys


def show_negotiation_strategy(service, target_vq_qb_id, all_associated_vqs, all_vpl):
    """Show detailed negotiation strategy for a specific VQ"""

    qb_client = QuickbaseClient()
    neo4j_client = Neo4jClient()

    client_mrc = service['client_mrc']
    service_id = service['service_id']

    # Find the target VQ
    target_vq = None
    for vq in all_associated_vqs:
        if vq.get('quickbase_id') == target_vq_qb_id:
            target_vq = vq
            break

    if not target_vq:
        print(f"\n❌ ERROR: No se encontró el VQ {target_vq_qb_id} asociado al servicio")
        return

    vendor_name = target_vq.get('vendor_name', 'Unknown')
    current_mrc = target_vq.get('mrc', 0)
    current_gm = ((client_mrc - current_mrc) / client_mrc * 100) if client_mrc > 0 else 0

    print('='*80)
    print(f'ESTRATEGIA DE NEGOCIACIÓN - VQ {target_vq_qb_id}')
    print(f'Service ID: {service_id}')
    print('='*80)

    print(f"\n📊 SITUACIÓN ACTUAL:")
    print(f"   Cliente: {service['customer']}")
    print(f"   Client MRC: ${client_mrc:,.2f}")
    print(f"   Ancho de Banda: {service['bandwidth_display']}")
    print(f"   Vendor: {vendor_name}")
    print(f"   Vendor Quote QB ID: {target_vq_qb_id}")
    print(f"   VQ Actual MRC: ${current_mrc:,.2f}")
    print(f"   GM Actual: {current_gm:.1f}% {'❌' if current_gm < 0 else '⚠️' if current_gm < 40 else '⚠️' if current_gm < 50 else '✅'}")
    print(f"   Lead Time: {target_vq.get('lead_time', 'N/A')} días")
    print(f"   Status: {target_vq.get('status', 'N/A')}")

    # Get negotiation history
    print(f"\n📈 HISTORIAL DE NEGOCIACIÓN - {vendor_name}:")
    stats = qb_client.get_vendor_negotiation_stats(vendor_name)

    if stats and stats.get('has_data'):
        print(f"   • Total negociaciones: {stats['total_negotiations']}")
        print(f"   • Negociaciones exitosas: {stats['successful_negotiations']}")
        print(f"   • Tasa de éxito: {stats['success_rate']:.1f}%")
        print(f"   • Descuento promedio obtenido: {stats['avg_discount']:.1f}%")

        if stats['avg_discount'] > 0:
            negotiated_mrc = current_mrc * (1 - stats['avg_discount']/100)
            negotiated_gm = ((client_mrc - negotiated_mrc) / client_mrc * 100) if client_mrc > 0 else 0
            negotiated_status = '✅' if negotiated_gm >= 50 else '⚠️' if negotiated_gm >= 40 else '❌'

            print(f"\n   💡 PROYECCIÓN CON NEGOCIACIÓN:")
            print(f"      Aplicando descuento promedio del {stats['avg_discount']:.1f}%:")
            print(f"      • MRC proyectado: ${negotiated_mrc:,.2f}")
            print(f"      • GM proyectado: {negotiated_gm:.1f}% {negotiated_status}")
            print(f"      • Probabilidad de éxito: {stats['success_rate']:.1f}%")
    else:
        print(f"   ❌ No hay historial de negociación disponible")
        stats = None

    # Check VPL from this vendor
    print(f"\n🔍 VENDOR PRICE LISTS (VPL) - {vendor_name}:")
    vendor_vpl = [v for v in all_vpl if v.get('vendor_name') == vendor_name]

    if vendor_vpl:
        print(f"   ✅ Se encontraron {len(vendor_vpl)} opciones de VPL de este vendor:")

        # Sort by MRC
        vendor_vpl.sort(key=lambda x: x.get('mrc', 0))

        # Verify location match
        import math
        def haversine_distance(lat1, lon1, lat2, lon2):
            R = 6371000
            phi1 = math.radians(float(lat1))
            phi2 = math.radians(float(lat2))
            delta_phi = math.radians(float(lat2) - float(lat1))
            delta_lambda = math.radians(float(lon2) - float(lon1))
            a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            return R * c

        for i, v in enumerate(vendor_vpl, 1):
            vpl_mrc = v.get('mrc', 0)
            vpl_nrc = v.get('nrc', 0)
            gm = ((client_mrc - vpl_mrc) / client_mrc * 100) if client_mrc > 0 and vpl_mrc > 0 else 0
            gm_status = '✅' if gm >= 50 else '⚠️' if gm >= 40 else '❌'

            bw_bps = v.get('bandwidth_bps')
            bw_display = f"{bw_bps / 1_000_000:.0f} Mbps" if bw_bps else v.get('bandwidth', 'N/A')
            service_type = v.get('service_type', 'N/A')

            # Check location
            vpl_lat = v.get('latitude')
            vpl_lon = v.get('longitude')
            distance_m = haversine_distance(service['latitude'], service['longitude'], vpl_lat, vpl_lon)
            location_note = "✅ MISMA UBICACIÓN" if distance_m == 0 else f"⚠️ {distance_m:.0f}m de distancia"

            print(f"\n   Opción {i}:")
            print(f"      Bandwidth: {bw_display} {service_type}")
            print(f"      MRC: ${vpl_mrc:,.2f} | NRC: ${vpl_nrc:,.2f}")
            print(f"      GM: {gm:.1f}% {gm_status}")
            print(f"      Ubicación: {location_note}")

            if stats and stats.get('has_data') and stats['avg_discount'] > 0:
                vpl_negotiated_mrc = vpl_mrc * (1 - stats['avg_discount']/100)
                vpl_negotiated_gm = ((client_mrc - vpl_negotiated_mrc) / client_mrc * 100) if client_mrc > 0 else 0
                vpl_negotiated_status = '✅' if vpl_negotiated_gm >= 50 else '⚠️' if vpl_negotiated_gm >= 40 else '❌'
                print(f"      Con negociación ({stats['avg_discount']:.1f}% desc): ${vpl_negotiated_mrc:,.2f} (GM: {vpl_negotiated_gm:.1f}% {vpl_negotiated_status})")
    else:
        print(f"   ❌ No se encontraron VPLs de {vendor_name}")
        print(f"   El vendor no tiene precios publicados en el sistema VPL")

    # Strategy recommendations
    print(f"\n{'='*80}")
    print(f"💡 ESTRATEGIA RECOMENDADA:")
    print(f"{'='*80}")

    # Calculate target MRC for different GM scenarios
    target_mrc_50 = client_mrc * 0.5  # 50% GM
    target_mrc_40 = client_mrc * 0.6  # 40% GM

    if current_gm < 50:
        if current_gm < 0:
            print(f"\n⚠️ SITUACIÓN CRÍTICA: Margen negativo de {current_gm:.1f}%")
            print(f"   El servicio está perdiendo ${abs(current_mrc - client_mrc):,.2f}/mes")
        else:
            print(f"\n⚠️ MARGEN BAJO: {current_gm:.1f}% (objetivo: 50%+)")

        print(f"\n   ACCIONES RECOMENDADAS:")

        print(f"\n   1️⃣ NEGOCIAR CON {vendor_name}:")
        print(f"      • Precio actual: ${current_mrc:,.2f}")

        if stats and stats.get('has_data'):
            print(f"      • Descuento histórico promedio: {stats['avg_discount']:.1f}% (probabilidad {stats['success_rate']:.1f}%)")
            negotiated_mrc = current_mrc * (1 - stats['avg_discount']/100)
            negotiated_gm = ((client_mrc - negotiated_mrc) / client_mrc * 100) if client_mrc > 0 else 0
            print(f"      • Precio con descuento: ${negotiated_mrc:,.2f} → GM: {negotiated_gm:.1f}%")

            if negotiated_gm < 50:
                print(f"      ⚠️ Incluso con negociación histórica, el GM queda en {negotiated_gm:.1f}%")

        print(f"      • Para GM 40% necesitas: ${target_mrc_40:,.2f} (descuento {((current_mrc - target_mrc_40)/current_mrc*100):.1f}%)")
        print(f"      • Para GM 50% necesitas: ${target_mrc_50:,.2f} (descuento {((current_mrc - target_mrc_50)/current_mrc*100):.1f}%)")

        if vendor_vpl:
            best_vpl = min(vendor_vpl, key=lambda x: x.get('mrc', float('inf')))
            best_vpl_mrc = best_vpl.get('mrc', 0)
            best_vpl_gm = ((client_mrc - best_vpl_mrc) / client_mrc * 100) if client_mrc > 0 else 0

            print(f"\n   2️⃣ USAR VENDOR PRICE LIST (VPL) - ¡ARGUMENTO MÁS FUERTE!")
            print(f"      • Mejor precio VPL: ${best_vpl_mrc:,.2f}")
            print(f"      • GM con VPL: {best_vpl_gm:.1f}%")
            print(f"      • Ahorro vs VQ actual: ${current_mrc - best_vpl_mrc:,.2f}/mes ({((current_mrc - best_vpl_mrc)/current_mrc*100):.1f}%)")
            print(f"      💬 Argumento: 'Ustedes mismos tienen publicado ${best_vpl_mrc:,.2f} en su lista de precios'")
            print(f"      ✅ Este es el argumento más sólido - es SU precio publicado")

        # Find better alternatives from other vendors
        other_vendors_vpl = [v for v in all_vpl if v.get('vendor_name') != vendor_name]
        if other_vendors_vpl:
            other_vendors_vpl.sort(key=lambda x: ((client_mrc - x.get('mrc', 0)) / client_mrc * 100), reverse=True)
            best_alternative = other_vendors_vpl[0]
            alt_mrc = best_alternative.get('mrc', 0)
            alt_gm = ((client_mrc - alt_mrc) / client_mrc * 100)
            alt_vendor = best_alternative.get('vendor_name', 'Unknown')

            print(f"\n   3️⃣ USAR ALTERNATIVAS COMO PALANCA:")
            print(f"      • Mejor opción: {alt_vendor}")
            print(f"      • MRC: ${alt_mrc:,.2f}")
            print(f"      • GM: {alt_gm:.1f}%")
            print(f"      💬 Palanca: 'Tengo oferta de {alt_vendor} por ${alt_mrc:,.2f}'")
            print(f"      ⚠️ Usar solo como herramienta de negociación")

        # Show other associated VQs from same vendor
        same_vendor_vqs = [vq for vq in all_associated_vqs if vq.get('vendor_name') == vendor_name and vq.get('quickbase_id') != target_vq_qb_id]
        if same_vendor_vqs:
            print(f"\n   4️⃣ OTROS VENDOR QUOTES DEL MISMO VENDOR:")
            for vq in same_vendor_vqs[:3]:
                vq_mrc = vq.get('mrc', 0)
                vq_gm = ((client_mrc - vq_mrc) / client_mrc * 100) if client_mrc > 0 else 0
                print(f"      • VQ {vq.get('quickbase_id')}: ${vq_mrc:,.2f} (GM: {vq_gm:.1f}%)")

    else:
        print(f"\n✅ El margen actual es aceptable ({current_gm:.1f}%)")
        print(f"   Sin embargo, siempre se puede optimizar:")

        if vendor_vpl:
            best_vpl = min(vendor_vpl, key=lambda x: x.get('mrc', float('inf')))
            best_vpl_mrc = best_vpl.get('mrc', 0)
            if best_vpl_mrc < current_mrc:
                savings = current_mrc - best_vpl_mrc
                print(f"\n   • El VPL muestra ${best_vpl_mrc:,.2f} (ahorro de ${savings:,.2f}/mes)")
                print(f"   • Considera solicitar ajuste al precio publicado")


def analyze_all_options(service, associated, vpl):
    """Show complete analysis of all VQ and VPL options"""

    qb_client = QuickbaseClient()
    client_mrc = service['client_mrc']

    # Process associated VQ
    print(f"\n{'='*80}")
    print(f"VENDOR QUOTES ASOCIADOS AL SERVICE:")
    print(f"{'='*80}")

    if associated:
        for i, vq in enumerate(associated, 1):
            vendor_name = vq.get('vendor_name', 'Unknown')
            vq_mrc = vq.get('mrc', 0)
            gm = ((client_mrc - vq_mrc) / client_mrc * 100) if client_mrc > 0 else 0
            gm_status = '✅' if gm >= 50 else '⚠️' if gm >= 40 else '❌'

            bw_bps = vq.get('bandwidth_bps')
            bw_display = f"{bw_bps / 1_000_000:.0f} Mbps" if bw_bps else vq.get('bandwidth', 'N/A')

            print(f"\nVQ {i}:")
            print(f"   Vendor: {vendor_name}")
            print(f"   QB ID: {vq.get('quickbase_id')} | Neo4j ID: {vq.get('id')}")
            print(f"   MRC: ${vq_mrc:,.2f} | GM: {gm:.1f}% {gm_status}")
            print(f"   Bandwidth: {bw_display}")
            print(f"   Status: {vq.get('status', 'N/A')}")
            print(f"   Lead Time: {vq.get('lead_time', 'N/A')} días")

            # Get QB stats
            if vendor_name != 'Unknown':
                stats = qb_client.get_vendor_negotiation_stats(vendor_name)
                if stats and stats.get('has_data'):
                    print(f"   📈 Historial: {stats['total_negotiations']} negociaciones, {stats['success_rate']:.1f}% éxito, {stats['avg_discount']:.1f}% descuento")

                    if stats['avg_discount'] > 0:
                        negotiated_mrc = vq_mrc * (1 - stats['avg_discount']/100)
                        negotiated_gm = ((client_mrc - negotiated_mrc) / client_mrc * 100) if client_mrc > 0 else 0
                        negotiated_status = '✅' if negotiated_gm >= 50 else '⚠️' if negotiated_gm >= 40 else '❌'
                        print(f"   💡 Con negociación: ${negotiated_mrc:,.2f} (GM: {negotiated_gm:.1f}% {negotiated_status})")
    else:
        print("\n❌ No se encontraron VendorQuotes asociados")

    # Process VPL results
    print(f"\n{'='*80}")
    print(f"VENDOR PRICE LISTS (VPL API):")
    print(f"{'='*80}")

    if vpl:
        # Group by vendor
        vpl_by_vendor = {}
        for v in vpl:
            vendor_name = v.get('vendor_name', 'Unknown')
            if vendor_name not in vpl_by_vendor:
                vpl_by_vendor[vendor_name] = []
            vpl_by_vendor[vendor_name].append(v)

        for vendor_name, options in vpl_by_vendor.items():
            print(f"\n{vendor_name}:")

            # Get QB stats once per vendor
            stats = None
            if vendor_name != 'Unknown':
                stats = qb_client.get_vendor_negotiation_stats(vendor_name)

            # Show negotiation history
            if stats and stats.get('has_data'):
                print(f"   📈 Historial: {stats['total_negotiations']} negociaciones, {stats['success_rate']:.1f}% éxito, {stats['avg_discount']:.1f}% descuento promedio")
            else:
                print(f"   📈 Sin historial de negociación")

            # Sort options by MRC
            options.sort(key=lambda x: x.get('mrc', 0))

            # Show ALL options for this vendor
            print(f"   Opciones disponibles ({len(options)}):")
            for j, opt in enumerate(options, 1):
                vpl_mrc = opt.get('mrc', 0)
                vpl_nrc = opt.get('nrc', 0)
                gm = ((client_mrc - vpl_mrc) / client_mrc * 100) if client_mrc > 0 and vpl_mrc > 0 else 0
                gm_status = '✅' if gm >= 50 else '⚠️' if gm >= 40 else '❌'

                bw_bps = opt.get('bandwidth_bps')
                bw_display = f"{bw_bps / 1_000_000:.0f} Mbps" if bw_bps else opt.get('bandwidth', 'N/A')

                service_type = opt.get('service_type', 'N/A')

                print(f"      {j}. {bw_display} {service_type} - MRC: ${vpl_mrc:,.2f} | NRC: ${vpl_nrc:,.2f} | GM: {gm:.1f}% {gm_status}")

                if stats and stats.get('has_data') and stats['avg_discount'] > 0:
                    negotiated_mrc = vpl_mrc * (1 - stats['avg_discount']/100)
                    negotiated_gm = ((client_mrc - negotiated_mrc) / client_mrc * 100) if client_mrc > 0 else 0
                    negotiated_status = '✅' if negotiated_gm >= 50 else '⚠️' if negotiated_gm >= 40 else '❌'
                    print(f"         Con negociación ({stats['avg_discount']:.1f}% desc): ${negotiated_mrc:,.2f} (GM: {negotiated_gm:.1f}% {negotiated_status})")
    else:
        print("\n❌ No se encontraron opciones de VPL")

    # Summary
    print(f"\n{'='*80}")
    print(f"RESUMEN:")
    print(f"{'='*80}")
    print(f"Client MRC: ${client_mrc:,.2f}")

    # Find best option overall
    all_options = []
    for vq in associated:
        vq_mrc = vq.get('mrc', 0)
        if vq_mrc > 0:
            gm = ((client_mrc - vq_mrc) / client_mrc * 100) if client_mrc > 0 else 0
            all_options.append({
                'vendor': vq.get('vendor_name', 'Unknown'),
                'mrc': vq_mrc,
                'gm': gm,
                'source': 'VQ Asociado',
                'qb_id': vq.get('quickbase_id')
            })

    for v in vpl:
        vpl_mrc = v.get('mrc', 0)
        if vpl_mrc > 0:
            gm = ((client_mrc - vpl_mrc) / client_mrc * 100)
            all_options.append({
                'vendor': v.get('vendor_name', 'Unknown'),
                'mrc': vpl_mrc,
                'gm': gm,
                'source': 'VPL API'
            })

    if all_options:
        all_options.sort(key=lambda x: x['gm'], reverse=True)
        best = all_options[0]
        print(f"\nMejor opción: {best['vendor']} ({best['source']})")
        print(f"   MRC: ${best['mrc']:,.2f}")
        print(f"   GM: {best['gm']:.1f}%")
        if best.get('qb_id'):
            print(f"   QB ID: {best['qb_id']}")


def analyze_service(service_id: str, vq_qb_id: int = None):
    """
    Analyze a service and provide margin optimization recommendations

    Args:
        service_id: Service ID to analyze
        vq_qb_id: Optional VendorQuote Quickbase ID for targeted strategy
    """

    # Initialize clients
    neo4j_client = Neo4jClient()

    print('='*80)
    print(f'ANÁLISIS DE MARGEN - SERVICE ID: {service_id}')
    print('='*80)

    # Get complete service details
    service = neo4j_client.get_service_details(service_id)

    if not service:
        print(f"❌ Service {service_id} no encontrado")
        neo4j_client.close()
        return

    print(f"\n📍 DETALLES DEL SERVICIO:")
    print(f"   Service ID: {service['service_id']}")
    print(f"   Customer: {service['customer']}")
    print(f"   Ancho de Banda: {service['bandwidth_display']}")
    print(f"   Client MRC: ${service['client_mrc']:,.2f}")
    print(f"   Location: {service['address'][:100] if service['address'] else 'N/A'}")
    print(f"   Coordenadas: {service['latitude']}, {service['longitude']}")

    # Get vendor quotes
    print(f"\n🔍 BUSCANDO VENDOR QUOTES...")
    vendor_quotes = neo4j_client.get_vendor_quotes_for_service(service_id, include_nearby=True, radius_meters=1000)

    associated = vendor_quotes.get('associated', [])
    nearby = vendor_quotes.get('nearby', [])
    vpl = vendor_quotes.get('vpl', [])

    print(f"   ✓ VendorQuotes asociados: {len(associated)}")
    print(f"   ✓ VendorQuotes cercanos (IGIQ): {len(nearby)}")
    print(f"   ✓ VPL API opciones: {len(vpl)}")

    # Decide which analysis to show
    if vq_qb_id:
        # Mode 2: Show negotiation strategy for specific VQ
        show_negotiation_strategy(service, vq_qb_id, associated, vpl)
    else:
        # Mode 1: Show all options and general analysis
        analyze_all_options(service, associated, vpl)

    neo4j_client.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  1. Analyze all options:        python analyze_service.py <SERVICE_ID>")
        print("  2. Strategy for specific VQ:   python analyze_service.py <SERVICE_ID> <VQ_QB_ID>")
        print("\nExamples:")
        print("  python analyze_service.py RNG.5511.D023")
        print("  python analyze_service.py RNG.5511.D023 555506")
        sys.exit(1)

    service_id = sys.argv[1]
    vq_qb_id = int(sys.argv[2]) if len(sys.argv) > 2 else None

    analyze_service(service_id, vq_qb_id)
