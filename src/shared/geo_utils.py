"""
Geospatial utilities for location-based operations using geopy
"""

from typing import Tuple, List, Optional, Union, Any
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from src.config.constants import (
    MIN_LATITUDE,
    MAX_LATITUDE,
    MIN_LONGITUDE,
    MAX_LONGITUDE,
)


class GeoUtils:
    """Utility class for geospatial operations using geopy"""

    # Initialize geocoder with a user agent for geopy
    _geolocator = Nominatim(user_agent="celeste_ecommerce_app")

    @staticmethod
    def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate the geodesic distance between two points on Earth using geopy

        Args:
            lat1, lon1: Latitude and longitude of first point in degrees
            lat2, lon2: Latitude and longitude of second point in degrees

        Returns:
            Distance in kilometers
        """
        point1 = (lat1, lon1)
        point2 = (lat2, lon2)
        return geodesic(point1, point2).kilometers

    @staticmethod
    def precise_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate precise distance between two points using geodesic calculation
        Sufficient accuracy for store location queries

        Args:
            lat1, lon1: Latitude and longitude of first point in degrees
            lat2, lon2: Latitude and longitude of second point in degrees

        Returns:
            Distance in kilometers
        """
        return GeoUtils.calculate_distance(lat1, lon1, lat2, lon2)

    @staticmethod
    def geocode_address(address: str) -> Tuple[float, float]:
        """
        Convert an address to latitude and longitude coordinates

        Args:
            address: Address string to geocode

        Returns:
            Tuple of (latitude, longitude)

        Raises:
            ValueError: If geocoding fails
        """
        try:
            # Use Any type to avoid async/coroutine type issues
            location: Any = GeoUtils._geolocator.geocode(address)
            if location is not None and hasattr(location, 'latitude') and hasattr(location, 'longitude'):
                return float(location.latitude), float(location.longitude)
            else:
                raise ValueError(f"Could not geocode address: {address}")
        except Exception as e:
            raise ValueError(f"Geocoding failed: {str(e)}")

    @staticmethod
    def reverse_geocode(latitude: float, longitude: float) -> str:
        """
        Convert latitude and longitude to an address

        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees

        Returns:
            Address string

        Raises:
            ValueError: If reverse geocoding fails
        """
        try:
            # Use Any type to avoid async/coroutine type issues
            location: Any = GeoUtils._geolocator.reverse(f"{latitude}, {longitude}")
            if location is not None and hasattr(location, 'address'):
                return str(location.address)
            else:
                raise ValueError(f"Could not reverse geocode coordinates: {latitude}, {longitude}")
        except Exception as e:
            raise ValueError(f"Reverse geocoding failed: {str(e)}")

    @staticmethod
    def get_bounding_box(
        latitude: float, longitude: float, radius_km: float
    ) -> Tuple[float, float, float, float]:
        """
        Calculate bounding box for a point and radius using geopy

        Args:
            latitude: Center latitude
            longitude: Center longitude
            radius_km: Radius in kilometers

        Returns:
            Tuple of (min_lat, max_lat, min_lon, max_lon)
        """
        from geopy import Point
        from geopy.distance import distance
        
        center = Point(latitude, longitude)
        
        # Calculate boundary points
        north = distance(kilometers=radius_km).destination(center, bearing=0)
        south = distance(kilometers=radius_km).destination(center, bearing=180)
        east = distance(kilometers=radius_km).destination(center, bearing=90)
        west = distance(kilometers=radius_km).destination(center, bearing=270)
        
        min_lat = south.latitude
        max_lat = north.latitude
        min_lon = west.longitude
        max_lon = east.longitude

        # Ensure bounds are within valid ranges
        min_lat = max(min_lat, MIN_LATITUDE)
        max_lat = min(max_lat, MAX_LATITUDE)
        min_lon = max(min_lon, MIN_LONGITUDE)
        max_lon = min(max_lon, MAX_LONGITUDE)

        return (min_lat, max_lat, min_lon, max_lon)

    @staticmethod
    def validate_coordinates(latitude: float, longitude: float) -> bool:
        """
        Validate latitude and longitude coordinates

        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees

        Returns:
            True if coordinates are valid, False otherwise
        """
        return (MIN_LATITUDE <= latitude <= MAX_LATITUDE) and (
            MIN_LONGITUDE <= longitude <= MAX_LONGITUDE
        )


    @staticmethod
    def filter_by_radius(
        stores_with_locations: List[dict],
        center_lat: float,
        center_lon: float,
        radius_km: float,
    ) -> List[dict]:
        """
        Filter stores by actual distance within radius

        Args:
            stores_with_locations: List of store dicts with location info
            center_lat: Center latitude
            center_lon: Center longitude
            radius_km: Maximum radius in kilometers

        Returns:
            Filtered list of stores within radius
        """
        filtered_stores = []

        for store in stores_with_locations:
            if (
                "location" in store
                and "latitude" in store["location"]
                and "longitude" in store["location"]
            ):
                distance = GeoUtils.calculate_distance(
                    center_lat,
                    center_lon,
                    store["location"]["latitude"],
                    store["location"]["longitude"],
                )
                if distance <= radius_km:
                    # Add distance to store data for sorting
                    store["distance"] = round(distance, 1)
                    filtered_stores.append(store)

        return filtered_stores
