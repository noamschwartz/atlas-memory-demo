"""
Document generator for FAQ and support content demos.

Generates realistic documentation content with:
- Question/answer pairs
- Category organisation
- Tags and metadata
- Helpful counts and dates

Example:
    config = {
        'topics': ['Installation', 'Configuration', 'Troubleshooting'],
        'product_name': 'MyApp'
    }
    
    generator = DocumentGenerator(config)
    generator.to_ndjson(100, 'faqs.ndjson')
"""

import random
from datetime import datetime, timedelta
from typing import Dict, Any, List

from faker import Faker

from .base_generator import BaseGenerator


# Default configuration for document generation
DEFAULT_CONFIG = {
    'seed': 42,
    'product_name': 'Product',
    'categories': [
        'Getting Started',
        'Installation',
        'Configuration',
        'Troubleshooting',
        'Advanced Features',
        'API Reference',
        'Best Practices',
        'Security'
    ],
    'content_type': 'faq',  # faq, article, or mixed
    'date_range_days': 365
}


class DocumentGenerator(BaseGenerator):
    """Generate realistic documentation and FAQ content.
    
    Supports multiple content types:
    - FAQ: Question/answer format
    - Article: Long-form documentation
    - Mixed: Combination of both
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialise the document generator.
        
        Args:
            config: Generator configuration. Merged with DEFAULT_CONFIG.
        """
        merged_config = {**DEFAULT_CONFIG, **(config or {})}
        super().__init__(merged_config)
        
        self.fake = Faker()
        Faker.seed(self.seed)
        
        self.product_name = self.config['product_name']
        self.categories = self.config['categories']
        self.content_type = self.config['content_type']
        self.date_range_days = self.config['date_range_days']
    
    def generate_record(self, index: int) -> Dict[str, Any]:
        """Generate a single document record.
        
        Args:
            index: Document index (0-based).
            
        Returns:
            Document dictionary with all fields.
        """
        doc_id = f"doc-{index:05d}"
        category = random.choice(self.categories)
        
        if self.content_type == 'faq':
            return self._generate_faq(doc_id, index, category)
        elif self.content_type == 'article':
            return self._generate_article(doc_id, index, category)
        else:
            # Mixed: 70% FAQ, 30% article
            if random.random() < 0.7:
                return self._generate_faq(doc_id, index, category)
            return self._generate_article(doc_id, index, category)
    
    def _generate_faq(self, doc_id: str, index: int, category: str) -> Dict[str, Any]:
        """Generate a FAQ entry."""
        question = self._generate_question(category)
        answer = self._generate_answer(question, category)
        
        return {
            'id': doc_id,
            'type': 'faq',
            'question': question,
            'answer': answer,
            'category': category,
            'tags': self._generate_tags(category),
            'related_topics': self._generate_related_topics(category),
            'helpful_count': random.randint(0, 500),
            'view_count': random.randint(10, 5000),
            'last_updated': self._generate_date(),
            'created': self._generate_date(older=True),
            'author': self.fake.name(),
            'difficulty': random.choice(['beginner', 'intermediate', 'advanced'])
        }
    
    def _generate_article(self, doc_id: str, index: int, category: str) -> Dict[str, Any]:
        """Generate a documentation article."""
        title = self._generate_article_title(category)
        
        return {
            'id': doc_id,
            'type': 'article',
            'title': title,
            'summary': self._generate_summary(title),
            'content': self._generate_article_content(title, category),
            'category': category,
            'tags': self._generate_tags(category),
            'sections': self._generate_sections(),
            'helpful_count': random.randint(0, 300),
            'view_count': random.randint(50, 10000),
            'last_updated': self._generate_date(),
            'created': self._generate_date(older=True),
            'author': self.fake.name(),
            'read_time_minutes': random.randint(3, 15)
        }
    
    def _generate_question(self, category: str) -> str:
        """Generate a realistic FAQ question."""
        question_templates = {
            'Getting Started': [
                f"How do I get started with {self.product_name}?",
                f"What are the system requirements for {self.product_name}?",
                f"Where can I download {self.product_name}?",
                f"Is there a free trial of {self.product_name}?",
                f"What's the quickest way to set up {self.product_name}?"
            ],
            'Installation': [
                f"How do I install {self.product_name} on Windows?",
                f"How do I install {self.product_name} on Mac?",
                f"How do I install {self.product_name} on Linux?",
                f"Can I install {self.product_name} without admin rights?",
                f"How do I upgrade to the latest version?"
            ],
            'Configuration': [
                f"How do I configure {self.product_name} settings?",
                f"Where is the configuration file located?",
                f"How do I set up environment variables?",
                f"Can I import settings from another installation?",
                f"What are the recommended configuration options?"
            ],
            'Troubleshooting': [
                f"Why isn't {self.product_name} starting?",
                f"How do I fix connection errors?",
                f"Why am I getting permission denied errors?",
                f"How do I reset {self.product_name} to default settings?",
                f"Where can I find error logs?"
            ],
            'Advanced Features': [
                f"How do I use advanced filtering in {self.product_name}?",
                f"Can I automate tasks with {self.product_name}?",
                f"How do I set up custom integrations?",
                f"What are the performance tuning options?",
                f"How do I configure high availability?"
            ],
            'API Reference': [
                f"How do I authenticate with the {self.product_name} API?",
                f"What is the rate limit for API calls?",
                f"How do I paginate API results?",
                f"Where can I find the API documentation?",
                f"What response formats does the API support?"
            ],
            'Best Practices': [
                f"What are best practices for using {self.product_name}?",
                f"How should I structure my data?",
                f"What's the recommended backup strategy?",
                f"How often should I update {self.product_name}?",
                f"What are common mistakes to avoid?"
            ],
            'Security': [
                f"How do I enable two-factor authentication?",
                f"What security certifications does {self.product_name} have?",
                f"How is my data encrypted?",
                f"How do I manage user permissions?",
                f"What are the security best practices?"
            ]
        }
        
        templates = question_templates.get(category, [f"How do I use {category}?"])
        return random.choice(templates)
    
    def _generate_answer(self, question: str, category: str) -> str:
        """Generate a helpful answer to the question."""
        intro_phrases = [
            "Great question!",
            "Here's how to do that:",
            "Follow these steps:",
            "This is a common question.",
            ""
        ]
        
        steps = [
            f"First, ensure you have the latest version of {self.product_name} installed.",
            "Navigate to the Settings menu.",
            "Look for the relevant option in the configuration panel.",
            "Make your changes and click Save.",
            "Restart the application if prompted."
        ]
        
        conclusions = [
            f"If you continue to have issues, please contact our support team.",
            "For more details, see our detailed documentation.",
            "This should resolve your issue in most cases.",
            "Feel free to reach out if you need further assistance."
        ]
        
        intro = random.choice(intro_phrases)
        step_text = " ".join(random.sample(steps, random.randint(2, 4)))
        conclusion = random.choice(conclusions)
        
        return f"{intro} {step_text} {conclusion}".strip()
    
    def _generate_article_title(self, category: str) -> str:
        """Generate an article title."""
        title_templates = [
            f"Complete Guide to {category}",
            f"Understanding {category} in {self.product_name}",
            f"{category}: Tips and Tricks",
            f"How to Master {category}",
            f"{category} Deep Dive",
            f"Essential {category} Concepts"
        ]
        return random.choice(title_templates)
    
    def _generate_summary(self, title: str) -> str:
        """Generate a brief summary for an article."""
        return f"This article covers everything you need to know about {title.lower()}. Learn the key concepts, best practices, and common pitfalls to avoid."
    
    def _generate_article_content(self, title: str, category: str) -> str:
        """Generate article content with multiple paragraphs."""
        paragraphs = [
            f"Welcome to our comprehensive guide on {title.lower()}. This documentation will help you understand the key concepts and get the most out of {self.product_name}.",
            self.fake.paragraph(nb_sentences=5),
            self.fake.paragraph(nb_sentences=4),
            f"By following these guidelines, you'll be able to effectively use {category} features in your workflow.",
            self.fake.paragraph(nb_sentences=3),
            f"For additional support, please refer to our community forums or contact our support team."
        ]
        return "\n\n".join(paragraphs)
    
    def _generate_sections(self) -> List[str]:
        """Generate section headings for an article."""
        possible_sections = [
            'Overview',
            'Prerequisites',
            'Step-by-Step Guide',
            'Configuration Options',
            'Common Issues',
            'FAQ',
            'Next Steps',
            'Related Topics',
            'Conclusion'
        ]
        return random.sample(possible_sections, random.randint(3, 6))
    
    def _generate_tags(self, category: str) -> List[str]:
        """Generate relevant tags."""
        general_tags = ['documentation', 'guide', 'tutorial', 'howto']
        category_tags = [category.lower().replace(' ', '-')]
        product_tags = [self.product_name.lower()]
        
        all_tags = general_tags + category_tags + product_tags
        return random.sample(all_tags, random.randint(2, 4))
    
    def _generate_related_topics(self, category: str) -> List[str]:
        """Generate related topic suggestions."""
        other_categories = [c for c in self.categories if c != category]
        return random.sample(other_categories, min(3, len(other_categories)))
    
    def _generate_date(self, older: bool = False) -> str:
        """Generate a realistic date string."""
        days_ago = random.randint(
            self.date_range_days // 2 if older else 0,
            self.date_range_days if older else self.date_range_days // 2
        )
        date = datetime.now() - timedelta(days=days_ago)
        return date.strftime('%Y-%m-%d')


def main():
    """CLI entry point for document generation."""
    import argparse
    import yaml
    
    parser = argparse.ArgumentParser(description='Generate document/FAQ data')
    parser.add_argument('--config', type=str, help='Path to YAML config file')
    parser.add_argument('--count', type=int, default=100, help='Number of documents')
    parser.add_argument('--output', type=str, help='Output NDJSON file path')
    parser.add_argument('--index', type=str, help='Elasticsearch index name')
    parser.add_argument('--type', choices=['faq', 'article', 'mixed'], default='faq')
    
    args = parser.parse_args()
    
    config = {'content_type': args.type}
    if args.config:
        with open(args.config, 'r') as f:
            config = {**config, **yaml.safe_load(f)}
    
    generator = DocumentGenerator(config)
    
    if args.output:
        generator.to_ndjson(args.count, args.output)
    elif args.index:
        generator.to_elasticsearch(args.count, args.index)
    else:
        for i, record in enumerate(generator.generate(5)):
            print(f"Document {i+1}:", record)


if __name__ == '__main__':
    main()
