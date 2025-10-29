"""
Geocoding Utilities
Converts addresses to coordinates and vice versa
"""
from typing import Optional, Tuple
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError


class GeocodingHelper:
    """Helper for geocoding operations"""

    def __init__(self):
        self.geolocator = Nominatim(user_agent="margin-optimizer")

    def address_to_coords(self, address: str) -> Optional[Tuple[float, float]]:
        """
        Convert address to coordinates

        Args:
            address: Full address string

        Returns:
            Tuple of (latitude, longitude) or None if not found
        """

        try:
            location = self.geolocator.geocode(address, timeout=10)

            if location:
                return (location.latitude, location.longitude)
            else:
                print(f"No se pudo geocodificar la dirección: {address}")
                return None

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"Error en geocodificación: {e}")
            return None

    def coords_to_address(self, lat: float, lon: float) -> Optional[str]:
        """
        Convert coordinates to address (reverse geocoding)

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Address string or None if not found
        """

        try:
            location = self.geolocator.reverse(f"{lat}, {lon}", timeout=10)

            if location:
                return location.address
            else:
                return None

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"Error en geocodificación inversa: {e}")
            return None

    def get_city_coords(self, city: str, country: str) -> Optional[Tuple[float, float]]:
        """
        Get coordinates for a city

        Args:
            city: City name
            country: Country name

        Returns:
            Tuple of (latitude, longitude) or None if not found
        """

        query = f"{city}, {country}"
        return self.address_to_coords(query)
