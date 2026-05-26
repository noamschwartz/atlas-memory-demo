"""
Store location generator for geo search demos.

Generates realistic store locations with:
- Geo coordinates for major US cities
- Store features and services
- Operating hours
- Ratings and reviews

Example:
    config = {
        'store_types': ['Flagship', 'Mall', 'Outlet'],
        'cities': ['San Francisco', 'New York', 'Chicago']
    }
    
    generator = StoreGenerator(config)
    generator.to_ndjson(100, 'stores.ndjson')
"""

import math
import random
from typing import Dict, Any, List, Tuple

from faker import Faker

from .base_generator import BaseGenerator


# US city coordinates for realistic geo data
US_CITIES = {
    'San Francisco': {'lat': 37.7749, 'lon': -122.4194, 'state': 'CA'},
    'Los Angeles': {'lat': 34.0522, 'lon': -118.2437, 'state': 'CA'},
    'San Diego': {'lat': 32.7157, 'lon': -117.1611, 'state': 'CA'},
    'New York': {'lat': 40.7128, 'lon': -74.0060, 'state': 'NY'},
    'Chicago': {'lat': 41.8781, 'lon': -87.6298, 'state': 'IL'},
    'Houston': {'lat': 29.7604, 'lon': -95.3698, 'state': 'TX'},
    'Phoenix': {'lat': 33.4484, 'lon': -112.0740, 'state': 'AZ'},
    'Philadelphia': {'lat': 39.9526, 'lon': -75.1652, 'state': 'PA'},
    'San Antonio': {'lat': 29.4241, 'lon': -98.4936, 'state': 'TX'},
    'Dallas': {'lat': 32.7767, 'lon': -96.7970, 'state': 'TX'},
    'Austin': {'lat': 30.2672, 'lon': -97.7431, 'state': 'TX'},
    'Jacksonville': {'lat': 30.3322, 'lon': -81.6557, 'state': 'FL'},
    'Columbus': {'lat': 39.9612, 'lon': -82.9988, 'state': 'OH'},
    'Indianapolis': {'lat': 39.7684, 'lon': -86.1581, 'state': 'IN'},
    'Charlotte': {'lat': 35.2271, 'lon': -80.8431, 'state': 'NC'},
    'Seattle': {'lat': 47.6062, 'lon': -122.3321, 'state': 'WA'},
    'Denver': {'lat': 39.7392, 'lon': -104.9903, 'state': 'CO'},
    'Boston': {'lat': 42.3601, 'lon': -71.0589, 'state': 'MA'},
    'Nashville': {'lat': 36.1627, 'lon': -86.7816, 'state': 'TN'},
    'Portland': {'lat': 45.5152, 'lon': -122.6784, 'state': 'OR'},
    'Las Vegas': {'lat': 36.1699, 'lon': -115.1398, 'state': 'NV'},
    'Detroit': {'lat': 42.3314, 'lon': -83.0458, 'state': 'MI'},
    'Memphis': {'lat': 35.1495, 'lon': -90.0490, 'state': 'TN'},
    'Atlanta': {'lat': 33.7490, 'lon': -84.3880, 'state': 'GA'},
    'Miami': {'lat': 25.7617, 'lon': -80.1918, 'state': 'FL'}
}


# Default configuration for store generation
DEFAULT_CONFIG = {
    'seed': 42,
    'brand_name': 'TechStore',
    'store_types': [
        {'type': 'Flagship', 'weight': 0.10},
        {'type': 'Mall', 'weight': 0.30},
        {'type': 'Outlet', 'weight': 0.20},
        {'type': 'Express', 'weight': 0.25},
        {'type': 'Warehouse', 'weight': 0.15}
    ],
    'features': [
        'curbside_pickup',
        'in_store_pickup',
        'same_day_delivery',
        'repair_services',
        'device_trade_in',
        'personal_shopping',
        'cafe',
        'workshop_space',
        'demo_area',
        'accessibility_services'
    ],
    'services': [
        'Tech Support',
        'Device Setup',
        'Data Transfer',
        'Screen Repair',
        'Battery Replacement',
        'Trade-In',
        'Business Solutions',
        'Education Discount'
    ],
    'coordinate_jitter': 0.05,  # Degrees of random offset from city centre
    'delivery_radius_km': {
        'Flagship': 15,
        'Mall': 10,
        'Outlet': 8,
        'Express': 5,
        'Warehouse': 20
    }
}


class StoreGenerator(BaseGenerator):
    """Generate realistic store location data.
    
    Creates stores suitable for:
    - Store finder applications
    - Geo search demos
    - Location-based filtering
    - Service availability lookups
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialise the store generator.
        
        Args:
            config: Generator configuration. Merged with DEFAULT_CONFIG.
        """
        merged_config = {**DEFAULT_CONFIG, **(config or {})}
        super().__init__(merged_config)
        
        self.fake = Faker()
        Faker.seed(self.seed)
        
        self.brand_name = self.config['brand_name']
        self.store_types = self.config['store_types']
        self.features = self.config['features']
        self.services = self.config['services']
        self.jitter = self.config['coordinate_jitter']
        self.delivery_radius_km = self.config['delivery_radius_km']

        # Pre-compute city list
        self.cities = list(US_CITIES.keys())
    
    def generate_record(self, index: int) -> Dict[str, Any]:
        """Generate a single store location.
        
        Args:
            index: Store index (0-based).
            
        Returns:
            Store dictionary with all fields.
        """
        store_id = f"store-{index:04d}"
        
        # Select city (cycle through to ensure distribution)
        city_name = self.cities[index % len(self.cities)]
        city_data = US_CITIES[city_name]
        
        # Select store type
        store_type = self.weighted_choice(
            [st['type'] for st in self.store_types],
            [st['weight'] for st in self.store_types]
        )
        
        # Generate location with jitter
        lat, lon = self._jitter_coordinates(
            city_data['lat'],
            city_data['lon']
        )
        
        # Generate store name
        name = self._generate_store_name(city_name, store_type, index)
        
        # Generate features based on store type
        store_features = self._generate_features(store_type)
        
        # Generate services
        store_services = self._generate_services(store_type)
        
        # Generate hours
        hours = self._generate_hours(store_type)
        
        # Generate address
        address = self._generate_address(city_name, city_data['state'])

        # Generate delivery zone polygon
        radius_km = self.delivery_radius_km.get(store_type, 10)
        delivery_zone = self._generate_delivery_zone(lat, lon, radius_km)

        return {
            'id': store_id,
            'name': name,
            'type': store_type,
            'location': {
                'lat': round(lat, 6),
                'lon': round(lon, 6)
            },
            'address': address,
            'city': city_name,
            'state': city_data['state'],
            'zip_code': self.fake.zipcode(),
            'phone': self.fake.phone_number(),
            'features': store_features,
            'services': store_services,
            'hours': hours,
            'rating': round(random.uniform(3.5, 5.0), 1),
            'review_count': random.randint(10, 500),
            'is_open_now': random.random() > 0.2,  # 80% chance open
            'delivery_zone': delivery_zone
        }
    
    def _generate_store_name(self, city: str, store_type: str, index: int) -> str:
        """Generate a store name."""
        location_descriptors = [
            'Downtown',
            'Midtown',
            'Uptown',
            'Westside',
            'Eastside',
            'Central',
            'North',
            'South'
        ]
        
        if store_type == 'Flagship':
            return f"{self.brand_name} {city} Flagship"
        elif store_type == 'Mall':
            mall_names = [
                'Galleria',
                'Town Center',
                'Shopping Center',
                'Plaza',
                'Square'
            ]
            return f"{self.brand_name} at {city} {random.choice(mall_names)}"
        elif store_type == 'Outlet':
            return f"{self.brand_name} Outlet - {city}"
        elif store_type == 'Warehouse':
            return f"{self.brand_name} Warehouse {city}"
        else:
            descriptor = random.choice(location_descriptors)
            return f"{self.brand_name} {descriptor} {city}"
    
    def _jitter_coordinates(self, lat: float, lon: float) -> Tuple[float, float]:
        """Add random offset to coordinates."""
        lat_offset = random.uniform(-self.jitter, self.jitter)
        lon_offset = random.uniform(-self.jitter, self.jitter)
        return lat + lat_offset, lon + lon_offset
    
    def _generate_features(self, store_type: str) -> List[str]:
        """Generate store features based on type."""
        # Base features everyone has
        base_features = ['in_store_pickup']
        
        # Type-specific feature likelihood
        type_features = {
            'Flagship': 8,    # Most features
            'Mall': 5,
            'Outlet': 3,
            'Express': 3,
            'Warehouse': 4
        }
        
        num_additional = type_features.get(store_type, 4)
        available = [f for f in self.features if f not in base_features]
        additional = random.sample(available, min(num_additional, len(available)))
        
        return base_features + additional
    
    def _generate_services(self, store_type: str) -> List[str]:
        """Generate available services based on store type."""
        type_services = {
            'Flagship': 6,
            'Mall': 4,
            'Outlet': 2,
            'Express': 2,
            'Warehouse': 3
        }
        
        num_services = type_services.get(store_type, 3)
        return random.sample(self.services, min(num_services, len(self.services)))
    
    def _generate_hours(self, store_type: str) -> Dict[str, str]:
        """Generate operating hours."""
        # Weekday hours
        if store_type == 'Flagship':
            weekday = '9:00 AM - 9:00 PM'
            saturday = '10:00 AM - 8:00 PM'
            sunday = '11:00 AM - 6:00 PM'
        elif store_type == 'Mall':
            weekday = '10:00 AM - 9:00 PM'
            saturday = '10:00 AM - 9:00 PM'
            sunday = '11:00 AM - 7:00 PM'
        elif store_type == 'Warehouse':
            weekday = '10:00 AM - 8:00 PM'
            saturday = '9:00 AM - 8:00 PM'
            sunday = '10:00 AM - 6:00 PM'
        else:
            weekday = '10:00 AM - 8:00 PM'
            saturday = '10:00 AM - 7:00 PM'
            sunday = '12:00 PM - 5:00 PM'
        
        return {
            'monday': weekday,
            'tuesday': weekday,
            'wednesday': weekday,
            'thursday': weekday,
            'friday': weekday,
            'saturday': saturday,
            'sunday': sunday
        }
    
    def _generate_delivery_zone(self, lat: float, lon: float, radius_km: float, num_points: int = 10) -> Dict[str, Any]:
        """Generate a GeoJSON polygon approximating a delivery zone circle.

        Args:
            lat: Centre latitude.
            lon: Centre longitude.
            radius_km: Radius in kilometres.
            num_points: Number of vertices for the polygon.

        Returns:
            GeoJSON-style polygon dict with [lon, lat] coordinate order.
        """
        coords = []
        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            dlat = (radius_km / 111.0) * math.cos(angle)
            dlon = (radius_km / (111.0 * math.cos(math.radians(lat)))) * math.sin(angle)
            jitter = random.uniform(0.9, 1.1)
            coords.append([round(lon + dlon * jitter, 6), round(lat + dlat * jitter, 6)])
        coords.append(coords[0])  # Close the polygon
        return {"type": "polygon", "coordinates": [coords]}

    def _generate_address(self, city: str, state: str) -> str:
        """Generate a street address."""
        return f"{self.fake.street_address()}, {city}, {state}"
    
def main():
    """CLI entry point for store generation."""
    import argparse
    import yaml
    
    parser = argparse.ArgumentParser(description='Generate store location data')
    parser.add_argument('--config', type=str, help='Path to YAML config file')
    parser.add_argument('--count', type=int, default=100, help='Number of stores')
    parser.add_argument('--output', type=str, help='Output NDJSON file path')
    parser.add_argument('--index', type=str, help='Elasticsearch index name')
    parser.add_argument('--brand', type=str, default='TechStore', help='Brand name')
    
    args = parser.parse_args()
    
    config = {'brand_name': args.brand}
    if args.config:
        with open(args.config, 'r') as f:
            config = {**config, **yaml.safe_load(f)}
    
    generator = StoreGenerator(config)
    
    if args.output:
        generator.to_ndjson(args.count, args.output)
    elif args.index:
        generator.to_elasticsearch(args.count, args.index)
    else:
        for i, record in enumerate(generator.generate(3)):
            print(f"Store {i+1}:", record)


if __name__ == '__main__':
    main()
