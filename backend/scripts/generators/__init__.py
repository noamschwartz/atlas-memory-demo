"""
Data generators for demo datasets.

This module provides configurable generators for creating realistic demo data
when existing datasets don't fit requirements.

Available generators:
- ProductGenerator: E-commerce product catalogues
- DocumentGenerator: Documentation, FAQs, support content
- EventGenerator: Security events, logs, observability data
- SupportGenerator: Customer support tickets
- StoreGenerator: Retail store locations with geo data

Usage:
    from generators import ProductGenerator
    
    config = {
        'brands': [...],
        'categories': {...},
        'price_distribution': {...}
    }
    
    generator = ProductGenerator(config)
    generator.to_ndjson(500, 'products.ndjson')
    # or
    generator.to_elasticsearch(500, 'products')
"""

from .base_generator import BaseGenerator
from .product_generator import ProductGenerator
from .document_generator import DocumentGenerator
from .event_generator import EventGenerator
from .support_generator import SupportGenerator
from .store_generator import StoreGenerator
from .banking_event_generator import BankingEventGenerator

__all__ = [
    'BaseGenerator',
    'ProductGenerator',
    'DocumentGenerator',
    'EventGenerator',
    'SupportGenerator',
    'StoreGenerator',
    'BankingEventGenerator',
]
