"""
Product generator for e-commerce demo datasets.

Generates realistic product catalogues with:
- Configurable brands and categories
- Realistic price distributions
- Category-specific attributes
- Consistent image URLs

Example:
    config = {
        'brands': ['Brand A', 'Brand B'],
        'categories': {
            'Electronics': ['Phones', 'Laptops'],
            'Clothing': ['Shirts', 'Pants']
        },
        'price_range': {'min': 10, 'max': 500}
    }
    
    generator = ProductGenerator(config)
    generator.to_ndjson(100, 'products.ndjson')
"""

import random
from typing import Dict, Any, List
from faker import Faker

from .base_generator import BaseGenerator


# Default configuration for product generation
DEFAULT_CONFIG = {
    'seed': 42,
    'brands': [
        'TechPro',
        'ValueMax',
        'PremiumChoice',
        'EcoFriendly',
        'BudgetSmart'
    ],
    'categories': {
        'Electronics': {
            'subcategories': ['Phones', 'Laptops', 'Tablets', 'Accessories'],
            'attributes': ['Screen Size', 'Storage', 'Battery Life', 'Processor']
        },
        'Clothing': {
            'subcategories': ['Shirts', 'Pants', 'Dresses', 'Outerwear'],
            'attributes': ['Size', 'Color', 'Material', 'Fit']
        },
        'Home': {
            'subcategories': ['Furniture', 'Decor', 'Kitchen', 'Garden'],
            'attributes': ['Dimensions', 'Material', 'Style', 'Assembly Required']
        }
    },
    'price_range': {
        'min': 9.99,
        'max': 999.99
    },
    'currency': 'USD',
    'image_template': 'https://picsum.photos/seed/{id}/400/400'
}


class ProductGenerator(BaseGenerator):
    """Generate realistic e-commerce product data.
    
    Attributes:
        fake: Faker instance for generating realistic text.
        brands: List of brand names.
        categories: Category hierarchy with subcategories and attributes.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialise the product generator.
        
        Args:
            config: Generator configuration. Merged with DEFAULT_CONFIG.
        """
        # Merge provided config with defaults
        merged_config = {**DEFAULT_CONFIG, **(config or {})}
        super().__init__(merged_config)
        
        self.fake = Faker()
        Faker.seed(self.seed)
        
        self.brands = self.config['brands']
        self.categories = self.config['categories']
        self.price_range = self.config['price_range']
        self.currency = self.config['currency']
        self.image_template = self.config['image_template']
    
    def generate_record(self, index: int) -> Dict[str, Any]:
        """Generate a single product record.
        
        Args:
            index: Product index (0-based).
            
        Returns:
            Product dictionary with all fields.
        """
        product_id = f"prod-{index:05d}"
        
        # Select category and subcategory
        category = random.choice(list(self.categories.keys()))
        cat_config = self.categories[category]
        subcategory = random.choice(cat_config['subcategories'])
        
        # Generate brand and title
        brand = random.choice(self.brands)
        title = self._generate_title(brand, category, subcategory)
        
        # Generate price with slight category bias
        price = self._generate_price(category)
        
        # Generate attributes
        attrs = self._generate_attributes(cat_config.get('attributes', []))
        
        return {
            'id': product_id,
            'title': title,
            'brand': brand,
            'description': self._generate_description(title, category, attrs),
            'price': price,
            'currency': self.currency,
            'image_url': self.image_template.format(id=product_id),
            'categories': [category, subcategory],
            'attrs': attrs,
            'attr_keys': list(attrs.keys()),
            'in_stock': random.random() > 0.1,  # 90% in stock
            'rating': round(random.uniform(3.0, 5.0), 1),
            'review_count': random.randint(0, 500)
        }
    
    def _generate_title(self, brand: str, category: str, subcategory: str) -> str:
        """Generate a realistic product title."""
        adjectives = ['Premium', 'Classic', 'Pro', 'Ultra', 'Essential', 'Advanced']
        adjective = random.choice(adjectives)
        
        # Generate a product-specific noun
        product_nouns = {
            'Phones': ['Smartphone', 'Mobile Phone', 'Device'],
            'Laptops': ['Laptop', 'Notebook', 'Ultrabook'],
            'Tablets': ['Tablet', 'Pad', 'Slate'],
            'Accessories': ['Charger', 'Case', 'Stand', 'Cable'],
            'Shirts': ['Shirt', 'Tee', 'Top', 'Blouse'],
            'Pants': ['Pants', 'Jeans', 'Trousers', 'Chinos'],
            'Dresses': ['Dress', 'Gown', 'Frock'],
            'Outerwear': ['Jacket', 'Coat', 'Hoodie', 'Blazer'],
            'Furniture': ['Chair', 'Table', 'Desk', 'Shelf'],
            'Decor': ['Lamp', 'Vase', 'Mirror', 'Frame'],
            'Kitchen': ['Mixer', 'Blender', 'Toaster', 'Kettle'],
            'Garden': ['Planter', 'Tools Set', 'Hose', 'Light']
        }
        
        noun = random.choice(product_nouns.get(subcategory, ['Product']))
        model = f"{random.choice('ABCDEFGHX')}{random.randint(100, 999)}"
        
        return f"{brand} {adjective} {noun} {model}"
    
    def _generate_description(
        self,
        title: str,
        category: str,
        attrs: Dict[str, str]
    ) -> str:
        """Generate a marketing-style product description."""
        intros = [
            f"Introducing the {title}.",
            f"Discover the all-new {title}.",
            f"Experience excellence with the {title}.",
            f"Meet the {title} - your perfect companion."
        ]
        
        features = [
            f"Features include {', '.join(list(attrs.values())[:2])}.",
            "Designed for maximum performance and style.",
            "Built with premium materials for lasting quality.",
            "Perfect for everyday use and special occasions."
        ]
        
        closings = [
            "Order now and elevate your lifestyle.",
            "Available while supplies last.",
            "Join thousands of satisfied customers today.",
            "The smart choice for discerning buyers."
        ]
        
        return f"{random.choice(intros)} {random.choice(features)} {random.choice(closings)}"
    
    def _generate_price(self, category: str) -> float:
        """Generate a price with category-based distribution."""
        min_price = self.price_range['min']
        max_price = self.price_range['max']
        
        # Category-based price adjustments
        category_multipliers = {
            'Electronics': 1.5,
            'Clothing': 0.8,
            'Home': 1.2
        }
        multiplier = category_multipliers.get(category, 1.0)
        
        # Generate base price with normal distribution
        mean = (min_price + max_price) / 2 * multiplier
        std = (max_price - min_price) / 4
        
        price = random.gauss(mean, std)
        price = max(min_price, min(max_price, price))
        
        # Round to realistic price endings (.99 or .49)
        rounded = round(price)
        if random.random() > 0.3:
            price = rounded - 0.01  # e.g., 29.99
        else:
            price = rounded - 0.51  # e.g., 29.49
        
        # Ensure price never goes below minimum
        return round(max(min_price, price), 2)
    
    def _generate_attributes(self, attribute_names: List[str]) -> Dict[str, str]:
        """Generate category-specific attributes."""
        attrs = {}
        
        attribute_values = {
            'Screen Size': ['5.5"', '6.1"', '6.7"', '13"', '15.6"', '17"'],
            'Storage': ['64GB', '128GB', '256GB', '512GB', '1TB'],
            'Battery Life': ['8 hours', '10 hours', '12 hours', '15 hours'],
            'Processor': ['A15 Bionic', 'Snapdragon 8', 'Intel i5', 'Intel i7', 'M2'],
            'Size': ['XS', 'S', 'M', 'L', 'XL', 'XXL'],
            'Color': ['Black', 'White', 'Navy', 'Grey', 'Red', 'Blue', 'Green'],
            'Material': ['Cotton', 'Polyester', 'Wool', 'Silk', 'Leather', 'Wood', 'Metal'],
            'Fit': ['Slim', 'Regular', 'Relaxed', 'Oversized'],
            'Dimensions': ['Small', 'Medium', 'Large', 'Extra Large'],
            'Style': ['Modern', 'Classic', 'Contemporary', 'Rustic', 'Minimalist'],
            'Assembly Required': ['Yes', 'No', 'Partial']
        }
        
        # Select 2-4 attributes
        selected = random.sample(attribute_names, min(len(attribute_names), random.randint(2, 4)))
        
        for attr in selected:
            if attr in attribute_values:
                attrs[attr] = random.choice(attribute_values[attr])
            else:
                attrs[attr] = self.fake.word().title()
        
        return attrs


def main():
    """CLI entry point for product generation."""
    import argparse
    import yaml
    
    parser = argparse.ArgumentParser(description='Generate product data')
    parser.add_argument('--config', type=str, help='Path to YAML config file')
    parser.add_argument('--count', type=int, default=100, help='Number of products')
    parser.add_argument('--output', type=str, help='Output NDJSON file path')
    parser.add_argument('--index', type=str, help='Elasticsearch index name')
    
    args = parser.parse_args()
    
    config = {}
    if args.config:
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
    
    generator = ProductGenerator(config)
    
    if args.output:
        generator.to_ndjson(args.count, args.output)
    elif args.index:
        generator.to_elasticsearch(args.count, args.index)
    else:
        # Print sample to stdout
        for i, record in enumerate(generator.generate(5)):
            print(f"Product {i+1}:", record)


if __name__ == '__main__':
    main()
