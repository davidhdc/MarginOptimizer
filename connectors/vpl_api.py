"""
VPL API Client
Handles connection to Vendor Price List API
"""
import requests
from typing import List, Dict, Optional
from config import VPL_API_BASE_URL, VPL_API_TOKEN, VPL_LIST_ENDPOINT


class VPLAPIClient:
    """Client for interacting with VPL API"""

    def __init__(self, base_url: str = VPL_API_BASE_URL, token: str = VPL_API_TOKEN):
        self.base_url = base_url
        self.token = token
        self.headers = {
            'Authorization': f'Token {self.token}'
        }

    def get_prices(
        self,
        lat: float,
        lon: float,
        service_type: int,
        bandwidth_bps: int,
        vendor_slug: Optional[str] = None,
        vendor_name: Optional[str] = None,
        status: str = 'active'
    ) -> List[Dict]:
        """
        Get vendor price lists for a specific location and service

        Args:
            lat: Latitude
            lon: Longitude
            service_type: Service type ID (e.g., 17 for DIA)
            bandwidth_bps: Bandwidth in bps (e.g., 100000000 for 100Mbps)
            vendor_slug: Optional vendor slug filter
            vendor_name: Optional vendor name filter
            status: Price list status (default: 'active')

        Returns:
            List of price list entries
        """

        params = {
            'service_type': service_type,
            'bps_requested': bandwidth_bps,
            'location': f'lat:{lat},lon:{lon}',
            'status': status
        }

        if vendor_slug:
            params['vendor_slug'] = vendor_slug

        if vendor_name:
            params['vendor_name'] = vendor_name

        try:
            response = requests.get(
                f'{self.base_url}{VPL_LIST_ENDPOINT}',
                headers=self.headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()

            # Extract results (adjust based on actual API response structure)
            if isinstance(data, dict):
                results = data.get('results', [])
            elif isinstance(data, list):
                results = data
            else:
                results = []

            return results

        except requests.exceptions.RequestException as e:
            print(f"Error fetching VPL data: {e}")
            return []

    def get_service_types(self) -> List[Dict]:
        """Get available service types"""

        try:
            response = requests.get(
                f'{self.base_url}/api/procurement/servicetypes/',
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"Error fetching service types: {e}")
            return []
