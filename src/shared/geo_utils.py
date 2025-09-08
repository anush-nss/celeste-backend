"""
Geospatial utilities for location-based operations
"""

import math
from typing import Tuple, List
from src.config.constants import (
    EARTH_RADIUS_KM,
    GEOHASH_PRECISION,
    MIN_LATITUDE,
    MAX_LATITUDE,
    MIN_LONGITUDE,
    MAX_LONGITUDE,
)


class GeoUtils:
    """Utility class for geospatial operations"""

    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate the great circle distance between two points on Earth
        using the Haversine formula

        Args:
            lat1, lon1: Latitude and longitude of first point in degrees
            lat2, lon2: Latitude and longitude of second point in degrees

        Returns:
            Distance in kilometers
        """
        # Convert latitude and longitude from degrees to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        print(EARTH_RADIUS_KM * c)

        return EARTH_RADIUS_KM * c

    @staticmethod
    def precise_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate precise distance between two points using Haversine formula
        Sufficient accuracy for store location queries

        Args:
            lat1, lon1: Latitude and longitude of first point in degrees
            lat2, lon2: Latitude and longitude of second point in degrees

        Returns:
            Distance in kilometers
        """
        return GeoUtils.haversine_distance(lat1, lon1, lat2, lon2)

    @staticmethod
    def generate_geohash(
        latitude: float, longitude: float, precision: int = GEOHASH_PRECISION
    ) -> str:
        """
        Generate a geohash for the given coordinates

        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees
            precision: Number of characters in geohash (default: 9)

        Returns:
            Geohash string
        """
        base32 = "0123456789bcdefghjkmnpqrstuvwxyz"

        lat_range = [-90.0, 90.0]
        lon_range = [-180.0, 180.0]

        geohash = []
        bits = 0
        bit = 0
        even_bit = True

        while len(geohash) < precision:
            if even_bit:
                # Process longitude
                mid = (lon_range[0] + lon_range[1]) / 2
                if longitude > mid:
                    bit = (bit << 1) + 1
                    lon_range[0] = mid
                else:
                    bit = bit << 1
                    lon_range[1] = mid
            else:
                # Process latitude
                mid = (lat_range[0] + lat_range[1]) / 2
                if latitude > mid:
                    bit = (bit << 1) + 1
                    lat_range[0] = mid
                else:
                    bit = bit << 1
                    lat_range[1] = mid

            even_bit = not even_bit
            bits += 1

            if bits == 5:
                geohash.append(base32[bit])
                bits = 0
                bit = 0

        return "".join(geohash)

    @staticmethod
    def get_bounding_box(
        latitude: float, longitude: float, radius_km: float
    ) -> Tuple[float, float, float, float]:
        """
        Calculate bounding box for a point and radius

        Args:
            latitude: Center latitude
            longitude: Center longitude
            radius_km: Radius in kilometers

        Returns:
            Tuple of (min_lat, max_lat, min_lon, max_lon)
        """
        # Approximate degree distances
        lat_degree_km = 111.0  # 1 degree latitude ≈ 111 km
        lon_degree_km = 111.0 * math.cos(math.radians(latitude))  # Varies by latitude

        lat_delta = radius_km / lat_degree_km
        lon_delta = radius_km / lon_degree_km

        min_lat = latitude - lat_delta
        max_lat = latitude + lat_delta
        min_lon = longitude - lon_delta
        max_lon = longitude + lon_delta

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
    def get_geohash_neighbors(geohash: str) -> List[str]:
        """
        Get neighboring geohashes for improved area coverage in radius searches

        Args:
            geohash: Base geohash string

        Returns:
            List of neighboring geohash strings including the original
        """
        base32 = "0123456789bcdefghjkmnpqrstuvwxyz"
        neighbors = [geohash]  # Include original

        if len(geohash) > 1:
            prefix = geohash[:-1]
            last_char = geohash[-1]

            if last_char in base32:
                idx = base32.index(last_char)
                # Add adjacent geohashes in all directions (simplified approach)
                for offset in range(-2, 3):  # -2, -1, 0, 1, 2
                    if offset != 0:  # Skip original (already added)
                        new_idx = (idx + offset) % len(base32)
                        neighbors.append(prefix + base32[new_idx])

        return neighbors

    @staticmethod
    def get_geohash_prefixes_for_radius(
        latitude: float, longitude: float, radius_km: float
    ) -> List[str]:
        """
        Get geohash prefixes that cover the search radius efficiently
        Used for optimizing Firestore queries

        Args:
            latitude: Center latitude
            longitude: Center longitude
            radius_km: Search radius in kilometers

        Returns:
            List of geohash prefixes to query
        """
        # Generate base geohash
        base_geohash = GeoUtils.generate_geohash(latitude, longitude)

        # For small radius, use longer prefix; for large radius, use shorter prefix
        if radius_km <= 1:
            prefix_length = GEOHASH_PRECISION
        elif radius_km <= 5:
            prefix_length = GEOHASH_PRECISION - 1
        elif radius_km <= 20:
            prefix_length = GEOHASH_PRECISION - 2
        else:
            prefix_length = GEOHASH_PRECISION - 3

        prefix = base_geohash[:prefix_length]

        # Get neighbor prefixes for better coverage
        neighbors = GeoUtils.get_geohash_neighbors(prefix)
        return list(set(neighbors))  # Remove duplicates

    @staticmethod
    def filter_by_radius(
        stores_with_locations: List[dict],
        center_lat: float,
        center_lon: float,
        radius_km: float,
    ) -> List[dict]:
        """
        Filter stores by actual distance within radius
        Used after geohash-based pre-filtering

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
            print(store)
            if (
                "location" in store
                and "latitude" in store["location"]
                and "longitude" in store["location"]
            ):
                distance = GeoUtils.haversine_distance(
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
