"""
Quickbase API Client
Handles connection to Quickbase for historical negotiation data
"""
import requests
import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict
from config import QUICKBASE_REALM, QUICKBASE_TOKEN, QUICKBASE_TABLE_ID


class QuickbaseClient:
    """Client for interacting with Quickbase API"""

    def __init__(self, realm: str = QUICKBASE_REALM, token: str = QUICKBASE_TOKEN, table_id: str = QUICKBASE_TABLE_ID):
        self.realm = realm
        self.token = token
        self.table_id = table_id
        self.base_url = 'https://api.quickbase.com/v1'
        self.headers = {
            'QB-Realm-Hostname': self.realm,
            'Authorization': f'QB-USER-TOKEN {self.token}',
            'Content-Type': 'application/json'
        }

    def query_negotiations(
        self,
        vendor_name: Optional[str] = None,
        date_from: Optional[datetime] = None,
        service_type: Optional[str] = None,
        region: Optional[str] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Query negotiation history from Quickbase

        Args:
            vendor_name: Filter by vendor name
            date_from: Filter records after this date
            service_type: Filter by service type
            region: Filter by region
            limit: Maximum records to return

        Returns:
            DataFrame with negotiation history
        """

        # Build query filter
        where_clauses = []

        if vendor_name:
            # Field ID 10 = Vendor Name (adjust based on actual schema)
            where_clauses.append(f"{{10.EX.'{vendor_name}'}}")

        if date_from:
            # Field ID 11 = Date Created (adjust based on actual schema)
            date_str = date_from.strftime('%Y-%m-%d')
            where_clauses.append(f"{{11.OAF.'{date_str}'}}")

        where_clause = "AND".join(where_clauses) if where_clauses else ""

        payload = {
            'from': self.table_id,
            'select': [3, 6, 7, 8, 9, 10, 11],  # Field IDs to select
            'options': {
                'skip': 0,
                'top': limit
            }
        }

        if where_clause:
            payload['where'] = where_clause

        try:
            response = requests.post(
                f'{self.base_url}/records/query',
                json=payload,
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            records = data.get('data', [])

            # Convert to DataFrame
            df = self._records_to_dataframe(records)

            return df

        except requests.exceptions.RequestException as e:
            print(f"Error querying Quickbase: {e}")
            return pd.DataFrame()

    def _records_to_dataframe(self, records: List[Dict]) -> pd.DataFrame:
        """Convert Quickbase records to pandas DataFrame"""

        if not records:
            return pd.DataFrame()

        rows = []
        for record in records:
            row = {}
            for field_id, field_data in record.items():
                if field_id == '3':
                    row['Associated ID'] = field_data.get('value')
                elif field_id == '6':
                    row['Currency'] = field_data.get('value')
                elif field_id == '7':
                    row['Initial MRC + Tax (USD)'] = field_data.get('value')
                elif field_id == '8':
                    row['Initial MRC + Tax (local currency)'] = field_data.get('value')
                elif field_id == '9':
                    row['Final Discount'] = field_data.get('value')
                elif field_id == '10':
                    row['Vendor Name'] = field_data.get('value')
                elif field_id == '11':
                    row['VOC Line Renewal - Date Created'] = field_data.get('value')
            rows.append(row)

        df = pd.DataFrame(rows)

        # Convert date column to datetime
        if 'VOC Line Renewal - Date Created' in df.columns:
            df['VOC Line Renewal - Date Created'] = pd.to_datetime(
                df['VOC Line Renewal - Date Created'],
                errors='coerce'
            )

        # Convert numeric columns
        numeric_cols = ['Initial MRC + Tax (USD)', 'Initial MRC + Tax (local currency)', 'Final Discount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        return df

    def get_table_fields(self) -> List[Dict]:
        """Get field definitions for the table"""

        try:
            response = requests.get(
                f'{self.base_url}/fields',
                headers=self.headers,
                params={'tableId': self.table_id},
                timeout=30
            )
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"Error getting table fields: {e}")
            return []

    def get_vendor_negotiation_stats(self, vendor_name: str) -> Dict:
        """
        Get negotiation statistics for a specific vendor from Vendor Orders & Contract table

        Uses Delta MRC Cost(%) field to determine negotiation success:
        - If Delta MRC Cost(%) > 0, there was a negotiation
        - Only counts "Delivered" status as successful

        Args:
            vendor_name: Vendor name to search for

        Returns:
            Dict with negotiation statistics
        """
        # Use the correct table: Vendor Orders & Contract (bkr26d56f)
        voc_table_id = "bkr26d56f"

        # Build WHERE clause with filters matching Quickbase query 247
        # Filter 1: Vendor Service Type must be one of specific types (case-insensitive variations)
        service_types = [
            'bia', 'BIA',
            'bia 3g/4g', 'BIA 3g/4g',
            'clear channel / iplc', 'Clear Channel / IPLC',
            'dia', 'DIA',
            'ethernet', 'Ethernet', 'ETHERNET',
            'ipvpn', 'IPVPN', 'IP VPN'
        ]
        service_type_filter = "OR".join([f"{{74.EX.'{st}'}}" for st in service_types])

        # Filter 2: Service ID must NOT contain NTL. or IGN.
        service_id_filter = "{234.XCT.'NTL.'}AND{234.XCT.'IGN.'}"

        # Filter 3: Service Support Level must be A, B, or D
        support_level_filter = "{273.EX.'A'}OR{273.EX.'B'}OR{273.EX.'D'}"

        # Combine all filters
        where_clause = f"{{245.CT.'{vendor_name}'}}AND(({service_type_filter})AND({service_id_filter})AND({support_level_filter}))"

        query = {
            'from': voc_table_id,
            'select': [
                3,      # Record ID
                245,    # Vendor name
                254,    # VOC Line Status
                6,      # MRC of Contract
                431,    # Vendor Quote - MRC
                466,    # Delta MRC Cost(%) - The key field!
                74,     # Vendor Service Type - Service
                234,    # Service ID
                273     # Service Support Level
            ],
            'where': where_clause,
            'options': {'skip': 0, 'top': 200}
        }

        try:
            response = requests.post(
                f'{self.base_url}/records/query',
                json=query,
                headers=self.headers,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                records = data.get('data', [])

                if not records:
                    return {
                        'vendor_name': vendor_name,
                        'total_negotiations': 0,
                        'successful_negotiations': 0,
                        'success_rate': 0.0,
                        'avg_discount': 0.0,
                        'best_discount': 0.0,
                        'has_data': False
                    }

                # Count all records that pass filters (total attempts)
                # Then count only those with Delta > 0 (successful negotiations)
                total_attempts = len(records)
                negotiated_records = []

                for r in records:
                    delta_mrc_pct = r.get('466', {}).get('value')
                    mrc_contract = r.get('6', {}).get('value')
                    mrc_quote = r.get('431', {}).get('value')

                    # Only count as successful negotiation if:
                    # 1. Delta > 0 (there was negotiation and discount)
                    # 2. Delta < 1.0 (exclude 100% which indicates missing MRC Contract)
                    # 3. Both MRC Contract and MRC Quote exist
                    if (delta_mrc_pct is not None and
                        delta_mrc_pct > 0 and
                        delta_mrc_pct < 1.0 and
                        mrc_contract is not None and
                        mrc_quote is not None):

                        negotiated_records.append(r)

                total_negotiations = total_attempts  # All records with filters
                successful_negotiations = len(negotiated_records)  # Only those with Delta > 0
                success_rate = (successful_negotiations / total_negotiations * 100) if total_negotiations > 0 else 0.0

                # Calculate average and best (max) discount (from all negotiated records)
                discounts = []
                for r in negotiated_records:
                    delta_pct = r.get('466', {}).get('value')
                    if delta_pct is not None and delta_pct > 0:
                        discounts.append(delta_pct * 100)  # Convert to percentage

                avg_discount = sum(discounts) / len(discounts) if discounts else 0
                best_discount = max(discounts) if discounts else 0

                return {
                    'vendor_name': vendor_name,
                    'total_negotiations': total_negotiations,
                    'successful_negotiations': successful_negotiations,
                    'success_rate': success_rate,
                    'avg_discount': avg_discount,
                    'best_discount': best_discount,
                    'has_data': total_negotiations > 0
                }
            else:
                return {
                    'vendor_name': vendor_name,
                    'total_negotiations': 0,
                    'successful_negotiations': 0,
                    'success_rate': 0.0,
                    'avg_discount': 0.0,
                    'best_discount': 0.0,
                    'has_data': False
                }

        except Exception as e:
            print(f"Error getting vendor stats: {e}")
            return {
                'vendor_name': vendor_name,
                'total_negotiations': 0,
                'successful_negotiations': 0,
                'success_rate': 0.0,
                'avg_discount': 0.0,
                'best_discount': 0.0,
                'has_data': False
            }

    def get_service_mrc(self, service_id: str) -> Dict:
        """
        Get Service MRC and Currency from Quickbase Services table

        Uses table bfwgbisz4 (Services - P&L) with query 313
        Fields:
        - 7: Service ID
        - 329: Maximum Record ID# - New Contracted MRC - USD
        - 481: Maximum Record ID# - MRC - Contracted Currency

        Args:
            service_id: Service ID to search for

        Returns:
            Dict with mrc and currency, or None if not found
        """
        services_table_id = "bfwgbisz4"

        # Build WHERE clause to match Service ID
        where_clause = f"{{7.EX.'{service_id}'}}"

        query = {
            'from': services_table_id,
            'select': [
                7,      # Service ID
                329,    # Maximum Record ID# - New Contracted MRC - USD
                702     # Customer Quote - Currency - Code
            ],
            'where': where_clause,
            'options': {'skip': 0, 'top': 1}
        }

        try:
            response = requests.post(
                f'{self.base_url}/records/query',
                json=query,
                headers=self.headers,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                records = data.get('data', [])

                if records:
                    record = records[0]
                    mrc = record.get('329', {}).get('value')  # New Contracted MRC - USD
                    currency = record.get('702', {}).get('value')  # Customer Quote - Currency - Code

                    # Default to USD if no currency specified (field 329 is in USD)
                    if not currency:
                        currency = 'USD'

                    return {
                        'mrc': mrc,
                        'currency': currency,
                        'found': True
                    }

            return {'mrc': None, 'currency': None, 'found': False}

        except Exception as e:
            print(f"Error getting service MRC from Quickbase: {e}")
            return {'mrc': None, 'currency': None, 'found': False}

    def get_vendor_renewal_stats(self, vendor_name: str) -> Dict:
        """
        Get renewal negotiation statistics for a vendor

        Returns statistics about successful renewal negotiations:
        - Success rate: % of renewals where a discount > 0% was obtained
        - Average discount: Average % discount when discount > 0%
        - Maximum discount: Best (highest) % discount achieved

        Uses table bqrc5mm8e (Renewals) with fields:
        - 14: Vendor name
        - 47: Final Discount (%)
        - 72: VOC Line Renewal - Date Created
        """
        renewals_table_id = "bqrc5mm8e"
        where_clause = f"{{14.EX.'{vendor_name}'}}"

        query = {
            'from': renewals_table_id,
            'select': [14, 47, 72],  # Vendor name, Final Discount, Date Created
            'where': where_clause,
            'options': {'skip': 0, 'top': 1000}
        }

        try:
            response = requests.post(
                f'{self.base_url}/records/query',
                json=query,
                headers=self.headers,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                records = data.get('data', [])

                if not records:
                    return {
                        'has_data': False,
                        'total_renewals': 0,
                        'successful_renewals': 0,
                        'success_rate': 0,
                        'avg_discount': 0,
                        'max_discount': 0
                    }

                # Process renewal records
                total_renewals = len(records)
                renewals_with_discount = []

                for rec in records:
                    discount = rec.get('47', {}).get('value', 0)
                    if discount and discount > 0:
                        renewals_with_discount.append(discount)

                successful_renewals = len(renewals_with_discount)
                success_rate = (successful_renewals / total_renewals * 100) if total_renewals > 0 else 0
                # Quickbase stores discount as decimal (0.24 = 24%), convert to percentage
                avg_discount = (sum(renewals_with_discount) / successful_renewals * 100) if successful_renewals > 0 else 0
                max_discount = (max(renewals_with_discount) * 100) if renewals_with_discount else 0

                return {
                    'has_data': True,
                    'total_renewals': total_renewals,
                    'successful_renewals': successful_renewals,
                    'success_rate': success_rate,
                    'avg_discount': avg_discount,
                    'max_discount': max_discount
                }

            return {
                'has_data': False,
                'total_renewals': 0,
                'successful_renewals': 0,
                'success_rate': 0,
                'avg_discount': 0,
                'max_discount': 0
            }

        except Exception as e:
            print(f"Error getting renewal stats from Quickbase: {e}")
            return {
                'has_data': False,
                'total_renewals': 0,
                'successful_renewals': 0,
                'success_rate': 0,
                'avg_discount': 0,
                'max_discount': 0
            }

    def get_vendor_delivered_mrc_total(self, vendor_name: str) -> Dict:
        """
        Get total MRC (USD) Tax Included for all Delivered VOC Lines for a vendor

        Uses table bkr26d56f (VOC Lines) with fields:
        - 245: Vendor name
        - 135: MRC (USD) Tax Included
        - 254: VOC Line Status
        """
        voc_table_id = "bkr26d56f"
        # Query for vendor + Delivered status
        where_clause = f"{{245.EX.'{vendor_name}'}}AND{{254.EX.'Delivered'}}"

        query = {
            'from': voc_table_id,
            'select': [245, 135, 254],  # Vendor name, MRC USD Tax Included, Status
            'where': where_clause,
            'options': {'skip': 0, 'top': 1000}
        }

        try:
            response = requests.post(
                f'{self.base_url}/records/query',
                json=query,
                headers=self.headers,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                records = data.get('data', [])

                if not records:
                    return {
                        'has_data': False,
                        'total_mrc_usd': 0,
                        'delivered_count': 0
                    }

                # Sum MRC (USD) Tax Included for all delivered VOC Lines
                total_mrc = 0
                for rec in records:
                    mrc = rec.get('135', {}).get('value', 0)
                    if mrc:
                        total_mrc += mrc

                return {
                    'has_data': True,
                    'total_mrc_usd': total_mrc,
                    'delivered_count': len(records)
                }

            return {
                'has_data': False,
                'total_mrc_usd': 0,
                'delivered_count': 0
            }

        except Exception as e:
            print(f"Error getting delivered MRC from Quickbase: {e}")
            return {
                'has_data': False,
                'total_mrc_usd': 0,
                'delivered_count': 0
            }
    def get_voc_line_by_service(self, service_id: str) -> Dict:
        """
        Get VOC Line data for renewal analysis by Service ID

        Uses table bkr26d56f (VOC Lines) to get:
        - Current vendor and MRC
        - Service details
        - Status

        Client MRC is obtained from Field 397 in VOC Lines (primary source).
        Falls back to Services table (bfwgbisz4) if Field 397 is not available.

        Key fields:
        - 234: Service ID
        - 245: Vendor name
        - 135: MRC (USD) Tax Included (Vendor MRC - ALWAYS in USD, needs conversion to local currency)
        - 254: VOC Line Status
        - 397: Client MRC (PRIMARY SOURCE for service MRC - in local currency)
        - 702: Currency (fallback to Services table if null)
        - 136: NRC (USD) Tax Included (ALWAYS in USD, needs conversion to local currency)
        - Many other fields for full context
        """
        voc_table_id = "bkr26d56f"

        # Query for VOC Lines matching this service
        where_clause = f"{{234.EX.'{service_id}'}}"

        try:
            payload = {
                'from': voc_table_id,
                'select': [
                    3,    # Record ID
                    234,  # Service ID
                    245,  # Vendor name
                    135,  # MRC (USD) Tax Included (Vendor MRC)
                    254,  # VOC Line Status
                    246,  # Bandwidth
                    247,  # Service Type
                    248,  # Lead Time
                    136,  # NRC (USD) Tax Included
                    397,  # Client MRC (actual service MRC) - PRIMARY SOURCE
                    702,  # Currency
                ],
                'where': where_clause,
                'sortBy': [{'fieldId': 3, 'order': 'DESC'}]  # Most recent first
            }

            response = requests.post(
                f'{self.base_url}/records/query',
                headers=self.headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                records = data.get('data', [])

                if records:
                    # Get the most recent VOC Line (first in sorted results)
                    voc = records[0]

                    # Field 135: MRC (USD) Tax Included - this is ALWAYS in USD
                    vendor_mrc_usd_value = voc.get('135', {}).get('value')
                    vendor_mrc_usd = float(vendor_mrc_usd_value) if vendor_mrc_usd_value is not None else 0.0

                    # Get Client MRC - PRIMARY SOURCE: Field 397 from VOC Line
                    # This is the actual service MRC that the client pays (in local currency)
                    client_mrc_value = voc.get('397', {}).get('value')
                    client_mrc = float(client_mrc_value) if client_mrc_value is not None else 0.0
                    currency = voc.get('702', {}).get('value')

                    # Fallback: If Field 397 or currency not available, try Services table
                    if (not client_mrc or client_mrc == 0) or not currency:
                        service_data = self.get_service_mrc(service_id)
                        if not client_mrc or client_mrc == 0:
                            client_mrc = service_data.get('mrc', 0)
                        if not currency:
                            currency = service_data.get('currency')

                    # Convert Vendor MRC from USD to local currency if needed
                    vendor_mrc = vendor_mrc_usd  # Default: assume USD
                    client_mrc_usd = client_mrc  # Default: assume USD
                    brl_rate = None

                    if currency and currency.upper() == 'BRL':
                        from utils.currency import get_usd_to_brl_rate
                        brl_rate = get_usd_to_brl_rate()
                        if brl_rate and brl_rate > 0:
                            # Convert Vendor MRC from USD to BRL
                            vendor_mrc = vendor_mrc_usd * brl_rate
                            # Convert Client MRC from BRL to USD
                            client_mrc_usd = client_mrc / brl_rate

                    # Calculate GM dynamically from latest Quickbase data
                    # GM% = ((Client MRC - Vendor MRC) / Client MRC) * 100
                    # Both values must be in the same currency (local currency)
                    gm_percent = 0.0
                    gm_local = 0.0
                    gm_usd = 0.0

                    if client_mrc and client_mrc > 0:
                        gm_local = client_mrc - vendor_mrc
                        gm_percent = (gm_local / client_mrc) * 100
                        # GM in USD
                        if currency and currency.upper() == 'BRL' and brl_rate and brl_rate > 0:
                            gm_usd = gm_local / brl_rate
                        else:
                            gm_usd = gm_local

                    nrc_value = voc.get('136', {}).get('value')
                    nrc_usd = float(nrc_value) if nrc_value is not None else 0.0
                    # Convert NRC from USD to local currency if needed
                    nrc = nrc_usd * brl_rate if (brl_rate and brl_rate > 0) else nrc_usd

                    return {
                        'has_data': True,
                        'record_id': voc.get('3', {}).get('value'),
                        'service_id': voc.get('234', {}).get('value'),
                        'vendor_name': voc.get('245', {}).get('value'),
                        'vendor_mrc': vendor_mrc,  # Vendor MRC in local currency
                        'vendor_mrc_usd': vendor_mrc_usd,  # Vendor MRC in USD
                        'status': voc.get('254', {}).get('value'),
                        'gm_percent': gm_percent,  # Calculated dynamically
                        'gm_local': gm_local,  # GM in local currency
                        'gm_usd': gm_usd,  # GM in USD
                        'bandwidth': voc.get('246', {}).get('value'),
                        'service_type': voc.get('247', {}).get('value'),
                        'lead_time': voc.get('248', {}).get('value'),
                        'nrc': nrc,  # NRC in local currency
                        'nrc_usd': nrc_usd,  # NRC in USD
                        'client_mrc': client_mrc,  # Client MRC in local currency (from Field 397)
                        'client_mrc_usd': client_mrc_usd,  # Client MRC in USD
                        'currency': currency  # Service currency
                    }
                else:
                    return {'has_data': False, 'error': 'No VOC Line found for this service'}
            else:
                print(f"Quickbase API error: {response.status_code}")
                return {'has_data': False, 'error': f'API error: {response.status_code}'}

        except Exception as e:
            print(f"Error getting VOC Line from Quickbase: {e}")
            return {'has_data': False, 'error': str(e)}
    
    def get_renewal_history_by_vendor(self, vendor_name: str, service_id: str = None) -> Dict:
        """
        Get detailed renewal history for a vendor, optionally filtered by service
        
        Uses table bqrc5mm8e (Renewals) with fields:
        - 14: Vendor name
        - 3: Service ID (if filtering)
        - 47: Final Discount (%)
        - 72: VOC Line Renewal - Date Created
        - Additional context fields
        
        Returns list of renewal records with details
        """
        renewals_table_id = "bqrc5mm8e"
        
        # Build query
        if service_id:
            where_clause = f"{{14.EX.'{vendor_name}'}}AND{{3.EX.'{service_id}'}}"
        else:
            where_clause = f"{{14.EX.'{vendor_name}'}}"
        
        try:
            payload = {
                'from': renewals_table_id,
                'select': [
                    3,    # Service ID
                    14,   # Vendor name  
                    47,   # Final Discount (%)
                    72,   # VOC Line Renewal - Date Created
                    45,   # Initial MRC (USD)
                    46,   # Final MRC (USD)
                ],
                'where': where_clause,
                'sortBy': [{'fieldId': 72, 'order': 'DESC'}]  # Most recent first
            }
            
            response = requests.post(
                f'{self.base_url}/records/query',
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                records = data.get('data', [])
                
                renewals = []
                for rec in records:
                    fields = rec.get('fields', {})
                    discount = fields.get('47', {}).get('value', 0)
                    
                    renewals.append({
                        'service_id': fields.get('3', {}).get('value'),
                        'vendor_name': fields.get('14', {}).get('value'),
                        'discount_percent': float(discount) * 100 if discount else 0,  # Convert to %
                        'date_created': fields.get('72', {}).get('value'),
                        'initial_mrc': float(fields.get('45', {}).get('value', 0)),
                        'final_mrc': float(fields.get('46', {}).get('value', 0)),
                        'was_successful': (discount and discount > 0)
                    })
                
                return {
                    'has_data': len(renewals) > 0,
                    'count': len(renewals),
                    'renewals': renewals
                }
            else:
                print(f"Quickbase API error: {response.status_code}")
                return {'has_data': False, 'count': 0, 'renewals': []}
                
        except Exception as e:
            print(f"Error getting renewal history from Quickbase: {e}")
            return {'has_data': False, 'count': 0, 'renewals': []}

    def get_service_bandwidth(self, service_id: str) -> Dict:
        """
        Get service bandwidth from Services table (bfwgbisz4)

        Returns bandwidth information for the service:
        - bandwidth_display: Text description
        - bandwidth_mbps: Numeric value in Mbps
        - bandwidth_bps: Numeric value in bps

        Key fields:
        - 7: Service ID
        - 115: Bandwidth (text)
        - 410: BW DW (bps -> Mbps) - numeric bandwidth
        """
        services_table_id = "bfwgbisz4"

        try:
            where_clause = f"{{7.EX.'{service_id}'}}"

            payload = {
                'from': services_table_id,
                'select': [
                    3,    # Record ID
                    7,    # Service ID
                    115,  # Bandwidth (text)
                    410,  # BW DW (Mbps) - numeric
                ],
                'where': where_clause
            }

            response = requests.post(
                f'{self.base_url}/records/query',
                headers=self.headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                records = data.get('data', [])

                if records:
                    service = records[0]
                    bandwidth_mbps = service.get('410', {}).get('value')
                    bandwidth_text = service.get('115', {}).get('value')

                    # Convert Mbps to bps
                    bandwidth_bps = None
                    if bandwidth_mbps:
                        bandwidth_bps = int(float(bandwidth_mbps) * 1_000_000)

                    # Create display string
                    bandwidth_display = bandwidth_text if bandwidth_text else (f"{int(bandwidth_mbps)} Mbps" if bandwidth_mbps else "N/A")

                    return {
                        'has_data': True,
                        'bandwidth_display': bandwidth_display,
                        'bandwidth_mbps': float(bandwidth_mbps) if bandwidth_mbps else None,
                        'bandwidth_bps': bandwidth_bps
                    }
                else:
                    return {
                        'has_data': False,
                        'bandwidth_display': 'N/A',
                        'bandwidth_mbps': None,
                        'bandwidth_bps': None
                    }
            else:
                print(f"Quickbase API error: {response.status_code}")
                return {
                    'has_data': False,
                    'bandwidth_display': 'N/A',
                    'bandwidth_mbps': None,
                    'bandwidth_bps': None
                }

        except Exception as e:
            print(f"Error getting service bandwidth from Quickbase: {e}")
            return {
                'has_data': False,
                'bandwidth_display': 'N/A',
                'bandwidth_mbps': None,
                'bandwidth_bps': None
            }

    def get_vendor_renewal_history(self, vendor_name: str) -> Dict:
        """
        Get renewal history for a specific vendor from Renewals table

        Args:
            vendor_name: Vendor name to search for

        Returns:
            Dictionary with renewal records
        """
        try:
            renewals_table_id = "bqrc5mm8e"

            # Query renewals table filtering by vendor name (field 39)
            where_clause = f"{{39.CT.'{vendor_name}'}}"

            payload = {
                'from': renewals_table_id,
                'select': [
                    3,    # Record ID
                    234,  # Service ID
                    39,   # Vendor name
                    246,  # Original MRC
                    247,  # Renewed MRC
                    248,  # Discount %
                    136,  # Renewal date
                    135,  # Status
                    180   # Currency
                ],
                'where': where_clause,
                'sortBy': [{'fieldId': 136, 'order': 'DESC'}],  # Sort by renewal date desc
                'options': {
                    'skip': 0,
                    'top': 100  # Limit to 100 most recent
                }
            }

            response = requests.post(
                f'{self.base_url}/records/query',
                headers=self.headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                records = data.get('data', [])

                renewal_records = []
                for record in records:
                    original_mrc = record.get('246', {}).get('value')
                    renewed_mrc = record.get('247', {}).get('value')
                    discount_percent = record.get('248', {}).get('value')

                    renewal_records.append({
                        'record_id': record.get('3', {}).get('value'),
                        'service_id': record.get('234', {}).get('value'),
                        'vendor_name': record.get('39', {}).get('value'),
                        'original_mrc': float(original_mrc) if original_mrc else None,
                        'renewed_mrc': float(renewed_mrc) if renewed_mrc else None,
                        'discount_percent': float(discount_percent) if discount_percent else 0,
                        'renewal_date': record.get('136', {}).get('value'),
                        'status': record.get('135', {}).get('value'),
                        'currency': record.get('180', {}).get('value', 'USD')
                    })

                return {
                    'has_data': True,
                    'count': len(renewal_records),
                    'records': renewal_records
                }
            else:
                print(f"Quickbase API error: {response.status_code}")
                return {
                    'has_data': False,
                    'count': 0,
                    'records': []
                }

        except Exception as e:
            print(f"Error getting vendor renewal history from Quickbase: {e}")
            return {
                'has_data': False,
                'count': 0,
                'records': []
            }

    def get_vendor_names(self, search_term: str) -> List[str]:
        """
        Get unique vendor names from Quickbase tables for autocomplete

        Args:
            search_term: Partial vendor name to search for

        Returns:
            List of unique vendor names
        """
        try:
            vendor_names = set()

            # Query VOC Lines table (bkr26d56f) for vendor names (field 245)
            voc_table_id = "bkr26d56f"
            where_clause_voc = f"{{245.CT.'{search_term}'}}"

            payload_voc = {
                'from': voc_table_id,
                'select': [245],  # Vendor name
                'where': where_clause_voc,
                'options': {
                    'skip': 0,
                    'top': 50
                }
            }

            response_voc = requests.post(
                f'{self.base_url}/records/query',
                headers=self.headers,
                json=payload_voc,
                timeout=30
            )

            if response_voc.status_code == 200:
                data = response_voc.json()
                records = data.get('data', [])
                for record in records:
                    vendor_name = record.get('245', {}).get('value')
                    if vendor_name:
                        vendor_names.add(vendor_name)

            # Query Renewals table (bqrc5mm8e) for vendor names (field 39)
            renewals_table_id = "bqrc5mm8e"
            where_clause_renewals = f"{{39.CT.'{search_term}'}}"

            payload_renewals = {
                'from': renewals_table_id,
                'select': [39],  # Vendor name
                'where': where_clause_renewals,
                'options': {
                    'skip': 0,
                    'top': 50
                }
            }

            response_renewals = requests.post(
                f'{self.base_url}/records/query',
                headers=self.headers,
                json=payload_renewals,
                timeout=30
            )

            if response_renewals.status_code == 200:
                data = response_renewals.json()
                records = data.get('data', [])
                for record in records:
                    vendor_name = record.get('39', {}).get('value')
                    if vendor_name:
                        vendor_names.add(vendor_name)

            return sorted(list(vendor_names))

        except Exception as e:
            print(f"Error getting vendor names from Quickbase: {e}")
            return []
