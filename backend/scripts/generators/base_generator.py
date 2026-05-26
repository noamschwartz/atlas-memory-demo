"""
Base generator class for data generation.

Provides common functionality for all data generators including:
- Configuration handling
- NDJSON file output
- Direct Elasticsearch indexing
- Seeded random generation for reproducibility
"""

from abc import ABC, abstractmethod
from typing import Generator, Dict, Any, List, Tuple, TypeVar

T = TypeVar('T')
from elasticsearch import Elasticsearch, helpers
import json
import os
import random


class BaseGenerator(ABC):
    """Abstract base class for data generators.
    
    Subclasses must implement generate_record() to define how individual
    records are created.
    
    Example:
        class MyGenerator(BaseGenerator):
            def generate_record(self, index: int) -> Dict[str, Any]:
                return {"id": f"item-{index}", "name": f"Item {index}"}
        
        gen = MyGenerator({"seed": 42})
        gen.to_ndjson(100, "output.ndjson")
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialise the generator with configuration.
        
        Args:
            config: Dictionary containing generator configuration.
                    Should include 'seed' for reproducible generation.
        """
        self.config = config
        self.seed = config.get('seed', 42)
        random.seed(self.seed)
        
    @abstractmethod
    def generate_record(self, index: int) -> Dict[str, Any]:
        """Generate a single record.
        
        Must be implemented by subclasses.
        
        Args:
            index: The index of this record (0-based).
            
        Returns:
            A dictionary representing the generated record.
        """
        pass
    
    def generate(self, count: int) -> Generator[Dict[str, Any], None, None]:
        """Generate multiple records.
        
        Args:
            count: Number of records to generate.
            
        Yields:
            Generated records one at a time.
        """
        for i in range(count):
            yield self.generate_record(i)
    
    def to_list(self, count: int) -> List[Dict[str, Any]]:
        """Generate records and return as a list.
        
        Args:
            count: Number of records to generate.
            
        Returns:
            List of generated records.
        """
        return list(self.generate(count))
    
    def to_ndjson(self, count: int, filepath: str) -> int:
        """Write generated records to NDJSON file.
        
        Args:
            count: Number of records to generate.
            filepath: Path to output file.
            
        Returns:
            Number of records written.
        """
        records_written = 0
        with open(filepath, 'w') as f:
            for record in self.generate(count):
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
                records_written += 1
        
        print(f"Generated {records_written} records to {filepath}")
        return records_written
    
    def to_elasticsearch(
        self,
        count: int,
        index_name: str,
        es_url: str = None,
        api_key: str = None,
        chunk_size: int = 500
    ) -> Tuple[int, List[Dict]]:
        """Index generated records directly to Elasticsearch.
        
        Args:
            count: Number of records to generate and index.
            index_name: Elasticsearch index name.
            es_url: Elasticsearch URL (defaults to ELASTICSEARCH_URL env var).
            api_key: API key (defaults to ELASTIC_API_KEY env var).
            chunk_size: Number of documents per bulk request.
            
        Returns:
            Tuple of (success_count, errors_list).
        """
        es_url = es_url or os.getenv('ELASTICSEARCH_URL')
        api_key = api_key or os.getenv('ELASTIC_API_KEY')
        
        if not es_url or not api_key:
            raise ValueError(
                "Elasticsearch URL and API key required. "
                "Set ELASTICSEARCH_URL and ELASTIC_API_KEY environment variables."
            )
        
        es = Elasticsearch(es_url, api_key=api_key)
        
        def generate_actions():
            for record in self.generate(count):
                yield {
                    "_index": index_name,
                    "_id": record.get('id'),
                    "_source": record
                }
        
        success, errors = helpers.bulk(
            es,
            generate_actions(),
            chunk_size=chunk_size,
            raise_on_error=False
        )
        
        print(f"Indexed {success} documents to '{index_name}', {len(errors)} errors")
        
        if errors:
            print("First error:", errors[0])
        
        return success, errors
    
    def validate_config(self, required_keys: List[str]) -> None:
        """Validate that required configuration keys are present.
        
        Args:
            required_keys: List of keys that must be in config.
            
        Raises:
            ValueError: If a required key is missing.
        """
        missing = [key for key in required_keys if key not in self.config]
        if missing:
            raise ValueError(f"Missing required config keys: {missing}")
    
    @staticmethod
    def weighted_choice(items: List[T], weights: List[float]) -> T:
        """Select an item based on weights.
        
        Args:
            items: List of items to choose from.
            weights: Corresponding weights for each item.
            
        Returns:
            A randomly selected item based on weights.
        """
        total = sum(weights)
        r = random.uniform(0, total)
        cumulative = 0
        
        for item, weight in zip(items, weights):
            cumulative += weight
            if r <= cumulative:
                return item
        
        return items[-1]
