"""
Neo4j Client
Provides helper methods for querying vendor quotes and related data from Neo4j
Uses real connection based on DH - Quotes Identifier system
"""
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from neo4j import GraphDatabase
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE


class Neo4jClient:
    """Client for Neo4j operations using real database connection"""

    def __init__(self):
        """Initialize Neo4j client with real connection"""
        try:
            self.driver = GraphDatabase.driver(
                NEO4J_URI,
                auth=(NEO4J_USER, NEO4J_PASSWORD)
            )
            self.database = NEO4J_DATABASE
            # Test connection
            with self.driver.session(database=self.database) as session:
                session.run("RETURN 1 as test")
            print(f"✅ Neo4j connected successfully to {NEO4J_URI}")
        except Exception as e:
            print(f"⚠️  Warning: Could not connect to Neo4j: {e}")
            self.driver = None

    def get_service_details(self, service_id: str) -> Dict:
        """
        Get complete service details including bandwidth

        Args:
            service_id: Service ID to lookup

        Returns:
            Dictionary with service details including bandwidth
        """
        if not self.driver:
            return {}

        with self.driver.session(database=self.database) as session:
            # Get basic service info with bandwidth
            result = session.run("""
                MATCH (s:Service {service_id: $service_id})
                OPTIONAL MATCH (s)-[:RELATED_TO]->(q:Quote)
                OPTIONAL MATCH (q)-[:BANDWIDTH_DOWN_OF]->(bw_down:Bandwidth)
                OPTIONAL MATCH (q)-[:BANDWIDTH_UP_OF]->(bw_up:Bandwidth)
                RETURN s.contracted_mrc as mrc,
                       s.customer as customer,
                       s.latitude as lat,
                       s.longitude as lon,
                       s.z_address as address,
                       s.service_id as service_id,
                       q.mrc as quote_mrc,
                       bw_down.bps_amount as bw_down_bps,
                       bw_down.label as bw_down_label,
                       bw_up.bps_amount as bw_up_bps,
                       bw_up.label as bw_up_label
                LIMIT 1
            """, service_id=service_id)

            rec = result.single()
            if not rec:
                return {}

            # Determine bandwidth display
            bandwidth_display = 'N/A'
            bandwidth_bps = None

            if rec['bw_down_label']:
                bandwidth_display = rec['bw_down_label']
                bandwidth_bps = rec['bw_down_bps']

                # If there's also bandwidth up, add it
                if rec['bw_up_label'] and rec['bw_up_label'] != rec['bw_down_label']:
                    bandwidth_display = f"{rec['bw_down_label']} / {rec['bw_up_label']}"
            elif rec['bw_down_bps']:
                # Convert bps to Mbps for display
                mbps = rec['bw_down_bps'] / 1_000_000
                bandwidth_display = f"{mbps:.0f} Mbps"
                bandwidth_bps = rec['bw_down_bps']

            # Get Service MRC from Quickbase (this is the authoritative source)
            from connectors.quickbase import QuickbaseClient
            qb_client = QuickbaseClient()
            qb_mrc_data = qb_client.get_service_mrc(service_id)

            # Use Quickbase MRC if available, otherwise fall back to Neo4j contracted_mrc
            if qb_mrc_data['found'] and qb_mrc_data['mrc'] is not None:
                client_mrc = qb_mrc_data['mrc']
                service_currency = qb_mrc_data['currency']
            else:
                # Fallback to Neo4j data if Quickbase doesn't have the service
                client_mrc = rec['mrc'] or 0
                service_currency = 'USD'  # contracted_mrc is in USD

            service_details = {
                'service_id': rec['service_id'],
                'customer': rec['customer'],
                'client_mrc': client_mrc,
                'service_currency': service_currency,
                'latitude': rec['lat'],
                'longitude': rec['lon'],
                'address': rec['address'],
                'bandwidth_display': bandwidth_display,
                'bandwidth_bps': bandwidth_bps
            }

            return service_details

    def get_vendor_quotes_by_location(
        self,
        lat: float,
        lon: float,
        service_type: str,
        bandwidth_min: int,
        bandwidth_max: int,
        months_back: int = 6,
        exclude_vendor: Optional[str] = None
    ) -> List[Dict]:
        """
        Get vendor quotes near a specific location

        Args:
            lat: Latitude
            lon: Longitude
            service_type: Service type (e.g., 'DIA', 'MPLS')
            bandwidth_min: Minimum bandwidth in bps
            bandwidth_max: Maximum bandwidth in bps
            months_back: How many months to look back
            exclude_vendor: Vendor name to exclude from results

        Returns:
            List of vendor quote dictionaries
        """

        if not self.driver:
            print("[Neo4j] No connection available")
            return []

        cutoff_date = datetime.now() - timedelta(days=months_back * 30)
        cutoff_str = cutoff_date.strftime('%Y-%m-%d')

        # Query para buscar VendorQuotes en Neo4j
        # Exclude Connectbase quotes (identified by 'connectbase' in comments field)
        query = f"""
        MATCH (vq:VendorQuote)
        WHERE vq.service_type = '{service_type}'
          AND vq.bandwidth_bps >= {bandwidth_min}
          AND vq.bandwidth_bps <= {bandwidth_max}
          AND vq.created_at >= date('{cutoff_str}')
          AND (vq.comments IS NULL OR NOT toLower(vq.comments) CONTAINS 'connectbase')
        """

        if exclude_vendor:
            query += f"\n  AND vq.vendor_name <> '{exclude_vendor}'"

        query += """
        RETURN vq.uuid AS uuid,
               vq.vendor_name AS vendor_name,
               vq.mrc AS mrc,
               vq.nrc AS nrc,
               vq.bandwidth_bps AS bandwidth_bps,
               vq.service_type AS service_type,
               vq.created_at AS quote_date,
               vq.status AS status
        ORDER BY vq.mrc ASC
        LIMIT 50
        """

        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query)
                records = [dict(record) for record in result]
                print(f"[Neo4j] Found {len(records)} vendor quotes")
                return records
        except Exception as e:
            print(f"[Neo4j] Error executing query: {e}")
            return []

    def get_vendor_quote_by_id(self, vq_id: str) -> Optional[Dict]:
        """
        Get a specific vendor quote by UUID

        Args:
            vq_id: Vendor Quote UUID

        Returns:
            Vendor quote dictionary or None
        """

        if not self.driver:
            print("[Neo4j] No connection available")
            return None

        query = f"""
        MATCH (vq:VendorQuote {{uuid: '{vq_id}'}})
        OPTIONAL MATCH (vq)-[:LOCATED_IN]->(city:City)
        OPTIONAL MATCH (city)-[:IN_STATE]->(state:State)
        OPTIONAL MATCH (state)-[:IN_COUNTRY]->(country:Country)
        RETURN vq.uuid AS uuid,
               vq.vendor_name AS vendor_name,
               vq.mrc AS mrc,
               vq.nrc AS nrc,
               vq.bandwidth_bps AS bandwidth_bps,
               vq.service_type AS service_type,
               vq.created_at AS quote_date,
               vq.status AS status,
               city.name AS city,
               city.latitude AS lat,
               city.longitude AS lon,
               state.name AS state,
               country.name AS country
        """

        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query)
                record = result.single()
                if record:
                    return dict(record)
                return None
        except Exception as e:
            print(f"[Neo4j] Error executing query: {e}")
            return None

    def get_service_by_id(self, service_id: str) -> Optional[Dict]:
        """
        Get service details by Service ID

        Args:
            service_id: Service ID

        Returns:
            Service dictionary or None
        """

        if not self.driver:
            print("[Neo4j] No connection available")
            return None

        query = f"""
        MATCH (s:Service {{service_id: '{service_id}'}})
        OPTIONAL MATCH (s)-[:LOCATED_AT]->(loc:Location)
        RETURN s.service_id AS service_id,
               s.mrc AS mrc,
               s.service_type AS service_type,
               s.bandwidth_bps AS bandwidth_bps,
               loc.address AS address,
               loc.latitude AS lat,
               loc.longitude AS lon,
               loc.city AS city,
               loc.state AS state,
               loc.country AS country
        """

        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query)
                record = result.single()
                if record:
                    return dict(record)
                return None
        except Exception as e:
            print(f"[Neo4j] Error executing query: {e}")
            return None

    def execute_cypher(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """
        Execute a custom Cypher query

        Args:
            query: Cypher query string
            params: Optional parameters for the query

        Returns:
            List of result dictionaries
        """

        if not self.driver:
            print("[Neo4j] No connection available")
            return []

        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, params or {})
                return [dict(record) for record in result]
        except Exception as e:
            print(f"[Neo4j] Error executing query: {e}")
            return []

    def get_vendor_quotes_for_service(self, service_id: str, include_nearby: bool = True, radius_meters: int = 1000) -> Dict[str, List[Dict]]:
        """
        Get vendor quotes associated with a specific service

        Pattern: Service → Quote → Task (via fk_task_id) ← VendorQuotes
        Also includes nearby VendorQuotes within specified radius (IGIQ data)

        Args:
            service_id: Service identifier (e.g., 'GTT.1340.D002')
            include_nearby: Whether to include nearby VendorQuotes from IGIQ (default: True)
            radius_meters: Search radius in meters for nearby quotes (default: 1000)

        Returns:
            Dict with 'associated' and 'nearby' lists of vendor quote records
        """
        # Get associated VendorQuotes
        # Exclude Connectbase quotes (identified by 'connectbase' in comments field)
        query_associated = """
        MATCH (s:Service {service_id: $service_id})-[:RELATED_TO]->(q:Quote)
        MATCH (q)-[:REQUIRES]->(t:Task)
        MATCH (vq:VendorQuote)
        WHERE vq.fk_task_id = t.id
          AND vq.status IN ['desk_results_feasible', 'site_survey_results_feasible']
          AND vq.mrc IS NOT NULL
          AND (vq.comments IS NULL OR NOT toLower(vq.comments) CONTAINS 'connectbase')
        OPTIONAL MATCH (vq)-[:OF_TYPE]->(st:ServiceType)
        OPTIONAL MATCH (vq)-[:BANDWIDTH_DOWN_OF]->(bw:Bandwidth)
        RETURN vq.id as vq_id,
               vq.quickbase_id as quickbase_id,
               vq.mrc as mrc,
               vq.nrc as nrc,
               vq.exchange_rate as exchange_rate,
               vq.status as status,
               vq.lead_time as lead_time,
               vq.latitude as latitude,
               vq.longitude as longitude,
               vq.date_created as date_created,
               st.name as service_type,
               st.id as service_type_id,
               bw.name as bandwidth,
               bw.id as bandwidth_id,
               t.id as task_id
        ORDER BY vq.mrc ASC
        """

        associated_results = self.execute_cypher(query_associated, {"service_id": service_id})

        # Add vendor info to associated quotes
        if associated_results:
            for vq in associated_results:
                vendor_query = """
                MATCH (vq:VendorQuote {id: $vq_id})<-[:PROVIDED_QUOTE]-(v:Vendor)
                RETURN v.name as vendor_name, v.id as vendor_id
                """
                vendor_result = self.execute_cypher(vendor_query, {"vq_id": vq['vq_id']})
                if vendor_result:
                    vq['vendor_name'] = vendor_result[0]['vendor_name']
                    vq['vendor_id'] = vendor_result[0]['vendor_id']
                else:
                    vq['vendor_name'] = None
                    vq['vendor_id'] = None
                vq['source'] = 'associated'

        nearby_results = []

        if include_nearby:
            # Get service location and characteristics
            service_query = """
            MATCH (s:Service {service_id: $service_id})
            OPTIONAL MATCH (s)-[:OF_TYPE]->(st:ServiceType)
            OPTIONAL MATCH (s)-[:BANDWIDTH_DOWN_OF]->(bw:Bandwidth)
            RETURN s.latitude as lat, s.longitude as lon,
                   st.id as service_type_id, bw.id as bandwidth_id
            """
            service_info = self.execute_cypher(service_query, {"service_id": service_id})

            if service_info and service_info[0]['lat'] and service_info[0]['lon']:
                service_lat = service_info[0]['lat']
                service_lon = service_info[0]['lon']
                service_type_id = service_info[0]['service_type_id']
                bandwidth_id = service_info[0]['bandwidth_id']

                # Calculate bounding box for radius
                import math
                km_per_deg_lat = 111.0
                km_per_deg_lon = 111.0 * math.cos(math.radians(float(service_lat)))

                radius_km = radius_meters / 1000.0
                delta_lat = radius_km / km_per_deg_lat
                delta_lon = radius_km / km_per_deg_lon

                lat_min = float(service_lat) - delta_lat
                lat_max = float(service_lat) + delta_lat
                lon_min = float(service_lon) - delta_lon
                lon_max = float(service_lon) + delta_lon

                # Get nearby VendorQuotes (IGIQ data) from last 12 months
                # Note: Bandwidth filtering happens in Python to allow flexibility
                # Exclude Connectbase quotes (identified by 'connectbase' in comments field)
                query_nearby = f"""
                MATCH (vq:VendorQuote)
                WHERE vq.latitude >= {lat_min} AND vq.latitude <= {lat_max}
                  AND vq.longitude >= {lon_min} AND vq.longitude <= {lon_max}
                  AND vq.status IN ['desk_results_feasible', 'site_survey_results_feasible']
                  AND vq.mrc IS NOT NULL
                  AND vq.date_created >= datetime() - duration({{months: 12}})
                  AND (vq.comments IS NULL OR NOT toLower(vq.comments) CONTAINS 'connectbase')
                OPTIONAL MATCH (vq)-[:OF_TYPE]->(st:ServiceType)
                OPTIONAL MATCH (vq)-[:BANDWIDTH_DOWN_OF]->(bw:Bandwidth)
                WHERE (st.id = {service_type_id} OR {service_type_id} IS NULL)
                RETURN vq.id as vq_id,
                       vq.quickbase_id as quickbase_id,
                       vq.mrc as mrc,
                       vq.nrc as nrc,
                       vq.exchange_rate as exchange_rate,
                       vq.status as status,
                       vq.lead_time as lead_time,
                       vq.latitude as latitude,
                       vq.longitude as longitude,
                       vq.date_created as date_created,
                       st.name as service_type,
                       st.id as service_type_id,
                       bw.name as bandwidth,
                       bw.id as bandwidth_id,
                       bw.bps_amount as bandwidth_bps
                ORDER BY vq.mrc ASC
                LIMIT 50
                """

                nearby_results = self.execute_cypher(query_nearby)

                if nearby_results:
                    # Calculate exact distances and filter
                    def haversine_distance(lat1, lon1, lat2, lon2):
                        R = 6371000  # Earth radius in meters
                        phi1 = math.radians(float(lat1))
                        phi2 = math.radians(float(lat2))
                        delta_phi = math.radians(float(lat2) - float(lat1))
                        delta_lambda = math.radians(float(lon2) - float(lon1))
                        a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
                        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                        return R * c

                    # Get service bandwidth for flexible filtering
                    service_bandwidth_bps = None
                    if bandwidth_id:
                        bw_query = """
                        MATCH (bw:Bandwidth {id: $bandwidth_id})
                        RETURN bw.bps_amount as bps_amount
                        """
                        bw_result = self.execute_cypher(bw_query, {"bandwidth_id": bandwidth_id})
                        if bw_result:
                            service_bandwidth_bps = bw_result[0].get('bps_amount')

                    # Filter by exact distance, bandwidth (flexible), and add vendor info
                    filtered_nearby = []
                    associated_vq_ids = {vq['vq_id'] for vq in associated_results} if associated_results else set()

                    for vq in nearby_results:
                        if vq['vq_id'] not in associated_vq_ids:  # Exclude already associated
                            distance = haversine_distance(
                                service_lat, service_lon,
                                vq['latitude'], vq['longitude']
                            )
                            if distance <= radius_meters:
                                # Bandwidth filter: allow exact match or slightly higher (up to 2x)
                                vq_bandwidth_bps = vq.get('bandwidth_bps')
                                if service_bandwidth_bps and vq_bandwidth_bps:
                                    # Only include if: exact match OR higher but not more than 2x
                                    if vq_bandwidth_bps < service_bandwidth_bps:
                                        continue  # Skip lower bandwidth
                                    if vq_bandwidth_bps > service_bandwidth_bps * 2:
                                        continue  # Skip much higher bandwidth (>2x)

                                vq['distance_meters'] = distance
                                vq['source'] = 'nearby_igiq'

                                # Get vendor info
                                vendor_query = """
                                MATCH (vq:VendorQuote {id: $vq_id})<-[:PROVIDED_QUOTE]-(v:Vendor)
                                RETURN v.name as vendor_name, v.id as vendor_id
                                """
                                vendor_result = self.execute_cypher(vendor_query, {"vq_id": vq['vq_id']})
                                if vendor_result:
                                    vq['vendor_name'] = vendor_result[0]['vendor_name']
                                    vq['vendor_id'] = vendor_result[0]['vendor_id']
                                else:
                                    vq['vendor_name'] = None
                                    vq['vendor_id'] = None

                                filtered_nearby.append(vq)

                    nearby_results = filtered_nearby

        # Get VPL data (Vendor Price Lists from IGIQ API)
        vpl_results = []

        if include_nearby:
            from connectors.vpl_api import VPLAPIClient

            service_info = self.execute_cypher(
                "MATCH (s:Service {service_id: $service_id}) "
                "OPTIONAL MATCH (s)-[:OF_TYPE]->(st:ServiceType) "
                "OPTIONAL MATCH (s)-[:BANDWIDTH_DOWN_OF]->(bw:Bandwidth) "
                "RETURN s.latitude as lat, s.longitude as lon, st.id as service_type_id, bw.id as bandwidth_id",
                {"service_id": service_id}
            )

            if service_info and service_info[0]['lat'] and service_info[0]['lon']:
                try:
                    vpl_client = VPLAPIClient()
                    service_lat = service_info[0]['lat']
                    service_lon = service_info[0]['lon']
                    service_type_id = service_info[0]['service_type_id']

                    # Get bandwidth from service or first associated VQ
                    bandwidth_bps = 100000000  # Default 100Mbps
                    bandwidth_id = service_info[0].get('bandwidth_id')

                    # Try to get from associated VQ first
                    if associated_results and associated_results[0].get('bandwidth_id'):
                        bandwidth_id = associated_results[0].get('bandwidth_id')

                    # Get bandwidth in bps from Neo4j
                    if bandwidth_id:
                        bw_query = f"MATCH (bw:Bandwidth {{id: {bandwidth_id}}}) RETURN bw.bps_amount as bps"
                        bw_result = self.execute_cypher(bw_query)
                        if bw_result and bw_result[0].get('bps'):
                            bandwidth_bps = bw_result[0]['bps']

                    vpl_data = vpl_client.get_prices(
                        lat=float(service_lat),
                        lon=float(service_lon),
                        service_type=service_type_id or 16,  # Default to DIA
                        bandwidth_bps=bandwidth_bps,
                        status='active'
                    )

                    # Process VPL results - filter by similar bandwidth
                    # Allow ±50% bandwidth variance
                    bw_min = bandwidth_bps * 0.5
                    bw_max = bandwidth_bps * 1.5

                    for vpl in vpl_data:
                        vendor_name = vpl.get('vendor', {}).get('name')
                        currency = vpl.get('currency', {})
                        exchange_rate = currency.get('exchange_rate', 1.0)

                        # Process each price in the VPL
                        for price in vpl.get('prices', []):
                            bw_down = price.get('bw_down', {})
                            bw_amount = bw_down.get('bps_amount', 0)

                            # Only include prices with similar bandwidth
                            if bw_amount and bw_min <= bw_amount <= bw_max:
                                vpl_results.append({
                                    'vq_id': None,
                                    'quickbase_id': None,
                                    'mrc': price.get('mrc', 0) / exchange_rate,  # Convert to USD
                                    'nrc': price.get('nrc', 0) / exchange_rate,
                                    'status': vpl.get('status'),
                                    'lead_time': None,
                                    'latitude': service_lat,
                                    'longitude': service_lon,
                                    'date_created': vpl.get('created_at'),
                                    'service_type': vpl.get('service_type', {}).get('label'),
                                    'service_type_id': vpl.get('service_type', {}).get('id'),
                                    'bandwidth': bw_down.get('label'),
                                    'bandwidth_bps': bw_amount,
                                    'bandwidth_id': bw_down.get('bw'),
                                    'vendor_name': vendor_name,
                                    'vendor_id': None,
                                    'source': 'vpl_api',
                                    'currency_code': currency.get('code'),
                                    'exchange_rate': exchange_rate,
                                    'vpl_slug': vpl.get('slug'),
                                    'price_slug': price.get('slug')
                                })
                except Exception as e:
                    print(f"[Neo4j] Warning: Could not fetch VPL data: {e}")

        return {
            'associated': associated_results or [],
            'nearby': nearby_results or [],
            'vpl': vpl_results or []
        }

    def get_vendor_names(self, search_term: str, limit: int = 20) -> List[str]:
        """
        Get list of unique vendor names matching search term for autocomplete

        Args:
            search_term: Partial vendor name to search for
            limit: Maximum number of results to return

        Returns:
            List of vendor names
        """
        if not self.driver:
            return []

        try:
            query = """
                MATCH (v:Vendor)
                WHERE toLower(v.name) CONTAINS toLower($search_term)
                AND v.name IS NOT NULL
                RETURN DISTINCT v.name as vendor_name
                ORDER BY v.name
                LIMIT $limit
            """

            results = self.execute_cypher(query, {"search_term": search_term, "limit": limit})

            vendor_names = [r['vendor_name'] for r in results if r.get('vendor_name')]
            return vendor_names

        except Exception as e:
            print(f"Error getting vendor names: {e}")
            return []

    def get_vendor_contract_history(self, vendor_name: str, limit: int = 500) -> List[Dict]:
        """
        Get new contract history for a vendor (VendorQuotes)

        Args:
            vendor_name: Vendor name to search for
            limit: Maximum number of results to return (default: 500)

        Returns:
            List of contract records with MRC and date information
        """
        if not self.driver:
            return []

        try:
            # Query prioritizes contracts with MRC data, then orders by date
            # Exclude Connectbase quotes (identified by 'connectbase' in comments field)
            query = """
                MATCH (v:Vendor {name: $vendor_name})-[:PROVIDED_QUOTE]->(vq:VendorQuote)
                WHERE (vq.comments IS NULL OR NOT toLower(vq.comments) CONTAINS 'connectbase')
                OPTIONAL MATCH (vq)-[:BANDWIDTH_DOWN_OF]->(bw:Bandwidth)
                WITH vq, bw
                ORDER BY
                    CASE WHEN vq.mrc IS NOT NULL THEN 0 ELSE 1 END,
                    vq.date_created DESC
                LIMIT $limit
                RETURN vq.id as quote_id,
                       vq.date_created as quote_date,
                       vq.fk_task_id as task_id,
                       vq.mrc as mrc,
                       bw.label as bandwidth
            """

            results = self.execute_cypher(query, {"vendor_name": vendor_name, "limit": limit})

            contracts = []
            for r in results:
                # Format date_created if available
                quote_date = r.get('quote_date')
                if quote_date:
                    # Neo4j DateTime object
                    try:
                        quote_date_str = quote_date.isoformat()[:10]  # Get YYYY-MM-DD
                    except:
                        quote_date_str = str(quote_date)[:10]
                else:
                    quote_date_str = 'N/A'

                contracts.append({
                    'quote_id': r.get('quote_id'),
                    'quote_date': quote_date_str,
                    'task_id': r.get('task_id'),
                    'service_id': f"Task-{r.get('task_id')}" if r.get('task_id') else 'N/A',
                    'mrc': r.get('mrc'),
                    'bandwidth': r.get('bandwidth', 'N/A'),
                    'status': 'Quoted'
                })

            return contracts

        except Exception as e:
            print(f"Error getting vendor contract history: {e}")
            return []

    def close(self):
        """Close the Neo4j driver connection"""
        if self.driver:
            self.driver.close()

    def __del__(self):
        """Cleanup on destruction"""
        self.close()
