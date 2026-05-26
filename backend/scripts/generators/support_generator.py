"""
Support ticket generator for customer service demos.

Generates realistic support tickets with:
- Multiple products and issue types
- Conversation threads
- Priority and status tracking
- Sentiment classification

Example:
    config = {
        'products': ['Cloud Search', 'APM Agent', 'Security SIEM'],
        'avg_messages_per_ticket': 4
    }
    
    generator = SupportGenerator(config)
    generator.to_ndjson(100, 'tickets.ndjson')
"""

import random
from datetime import datetime, timedelta
from typing import Dict, Any, List

from faker import Faker

from .base_generator import BaseGenerator


# Default configuration for support ticket generation
DEFAULT_CONFIG = {
    'seed': 42,
    'products': [
        'Cloud Search',
        'APM Agent',
        'Metricbeat',
        'Security SIEM',
        'Observability Platform',
        'Fleet Server'
    ],
    'issue_types': {
        'Bug Report': {
            'weight': 0.30,
            'priority_bias': ['high', 'medium']
        },
        'Feature Request': {
            'weight': 0.15,
            'priority_bias': ['low', 'medium']
        },
        'Configuration Help': {
            'weight': 0.25,
            'priority_bias': ['medium', 'low']
        },
        'Performance Issue': {
            'weight': 0.20,
            'priority_bias': ['high', 'critical']
        },
        'Documentation': {
            'weight': 0.10,
            'priority_bias': ['low']
        }
    },
    'statuses': ['open', 'in_progress', 'pending_customer', 'resolved', 'closed'],
    'priorities': ['low', 'medium', 'high', 'critical'],
    'sentiments': ['positive', 'neutral', 'negative', 'frustrated'],
    'avg_messages_per_ticket': 4,
    'date_range_days': 90
}


class SupportGenerator(BaseGenerator):
    """Generate realistic customer support tickets.
    
    Creates tickets suitable for:
    - Support queue dashboards
    - Sentiment analysis demos
    - Agent productivity metrics
    - Customer satisfaction tracking
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialise the support generator.
        
        Args:
            config: Generator configuration. Merged with DEFAULT_CONFIG.
        """
        merged_config = {**DEFAULT_CONFIG, **(config or {})}
        super().__init__(merged_config)
        
        self.fake = Faker()
        Faker.seed(self.seed)
        
        self.products = self.config['products']
        self.issue_types = self.config['issue_types']
        self.statuses = self.config['statuses']
        self.priorities = self.config['priorities']
        self.sentiments = self.config['sentiments']
        self.avg_messages = self.config['avg_messages_per_ticket']
        self.date_range_days = self.config['date_range_days']
    
    def generate_record(self, index: int) -> Dict[str, Any]:
        """Generate a single support ticket.
        
        Args:
            index: Ticket index (0-based).
            
        Returns:
            Support ticket dictionary with all fields.
        """
        ticket_id = f"ticket-{index:05d}"
        
        # Select issue type based on weights
        issue_type = self.weighted_choice(
            list(self.issue_types.keys()),
            [it['weight'] for it in self.issue_types.values()]
        )
        type_config = self.issue_types[issue_type]
        
        # Select product
        product = random.choice(self.products)
        
        # Generate priority with bias from issue type
        priority = random.choice(type_config['priority_bias'])
        
        # Generate status (weighted toward open/in_progress)
        status = self.weighted_choice(
            self.statuses,
            [0.25, 0.30, 0.15, 0.20, 0.10]
        )
        
        # Generate dates
        created_at = self._generate_date()
        updated_at = self._generate_update_date(created_at, status)
        
        # Generate subject and description
        subject = self._generate_subject(issue_type, product)
        description = self._generate_description(issue_type, product)
        
        # Generate conversation
        conversation = self._generate_conversation(status, issue_type)
        
        # Determine sentiment based on issue type and status
        sentiment = self._determine_sentiment(issue_type, status, priority)
        
        # Customer info
        customer_name = self.fake.name()
        customer_email = self.fake.email()
        
        return {
            'id': ticket_id,
            'subject': subject,
            'description': description,
            'product': product,
            'issue_type': issue_type,
            'status': status,
            'priority': priority,
            'sentiment': sentiment,
            'customer_name': customer_name,
            'customer_email': customer_email,
            'assigned_to': self.fake.name() if status != 'open' else None,
            'conversation': conversation,
            'message_count': len(conversation),
            'created_at': created_at,
            'updated_at': updated_at,
            'resolved_at': updated_at if status in ['resolved', 'closed'] else None,
            'tags': self._generate_tags(issue_type, product, priority),
            'satisfaction_score': random.randint(1, 5) if status == 'closed' else None
        }
    
    def _generate_subject(self, issue_type: str, product: str) -> str:
        """Generate a realistic ticket subject."""
        subjects = {
            'Bug Report': [
                f"{product} crashes on startup",
                f"Error in {product} when processing data",
                f"{product} memory leak issue",
                f"Unexpected behaviour in {product}",
                f"{product} failing with timeout errors"
            ],
            'Feature Request': [
                f"Request: Add export functionality to {product}",
                f"Feature: Better filtering in {product}",
                f"Enhancement: {product} dashboard improvements",
                f"Suggestion: {product} API enhancement"
            ],
            'Configuration Help': [
                f"How to configure {product} for production?",
                f"Need help setting up {product}",
                f"{product} configuration best practices",
                f"Integration setup for {product}"
            ],
            'Performance Issue': [
                f"{product} is running slowly",
                f"Performance degradation in {product}",
                f"{product} high CPU usage",
                f"Memory issues with {product}"
            ],
            'Documentation': [
                f"Documentation unclear for {product}",
                f"Missing docs for {product} feature",
                f"Need examples for {product} API"
            ]
        }
        return random.choice(subjects.get(issue_type, [f"Issue with {product}"]))
    
    def _generate_description(self, issue_type: str, product: str) -> str:
        """Generate a detailed ticket description."""
        intros = [
            f"I'm experiencing an issue with {product}.",
            f"We've encountered a problem using {product}.",
            f"Our team has been working with {product} and found the following:"
        ]
        
        details = {
            'Bug Report': [
                "When trying to perform the operation, the application crashes.",
                "We see error messages in the logs that indicate a null pointer exception.",
                "This started happening after the latest update.",
                "The issue is reproducible on multiple machines."
            ],
            'Feature Request': [
                "It would be helpful if we could export data in CSV format.",
                "We need better integration with our existing tools.",
                "The current workflow requires too many manual steps.",
                "Other similar products offer this functionality."
            ],
            'Configuration Help': [
                "We're trying to set up a production environment.",
                "The documentation doesn't cover our specific use case.",
                "We need guidance on the recommended settings.",
                "Our current configuration isn't working as expected."
            ],
            'Performance Issue': [
                "Response times have increased significantly.",
                "We're seeing high resource utilisation.",
                "The system becomes unresponsive during peak hours.",
                "Performance metrics show concerning patterns."
            ],
            'Documentation': [
                "The documentation doesn't explain this feature clearly.",
                "We couldn't find examples for this use case.",
                "The API reference seems incomplete."
            ]
        }
        
        environments = [
            "Environment: Production cluster on AWS.",
            "Running on Kubernetes with 3 nodes.",
            "Version: Latest stable release.",
            "OS: Ubuntu 22.04 LTS."
        ]
        
        intro = random.choice(intros)
        detail = random.choice(details.get(issue_type, ["We need assistance."]))
        env = random.choice(environments)
        
        return f"{intro}\n\n{detail}\n\n{env}\n\nPlease advise on next steps."
    
    def _generate_conversation(self, status: str, issue_type: str) -> List[Dict[str, Any]]:
        """Generate a conversation thread for the ticket."""
        messages = []
        
        # Determine number of messages based on status
        if status == 'open':
            num_messages = 1
        elif status == 'closed':
            num_messages = random.randint(3, 8)
        else:
            num_messages = random.randint(1, self.avg_messages + 2)
        
        base_time = (self.config.get('base_time') or datetime.now()) - timedelta(days=random.randint(1, 30))
        
        # Pre-generate sorted time offsets to ensure chronological order
        time_offsets = sorted([random.randint(1, 8) * (i + 1) for i in range(num_messages)])
        
        for i in range(num_messages):
            is_customer = i % 2 == 0
            
            if is_customer:
                content = self._generate_customer_message(i, issue_type)
                sender_type = 'customer'
            else:
                content = self._generate_agent_message(i, issue_type, status)
                sender_type = 'agent'
            
            messages.append({
                'index': i,
                'sender_type': sender_type,
                'sender_name': self.fake.name(),
                'content': content,
                'timestamp': (base_time + timedelta(hours=time_offsets[i])).isoformat() + 'Z'
            })
        
        return messages
    
    def _generate_customer_message(self, index: int, issue_type: str) -> str:
        """Generate a customer message."""
        if index == 0:
            return "Initial ticket description - see above."
        
        messages = [
            "Any update on this?",
            "We're still experiencing this issue.",
            "Thanks for looking into this.",
            "Could you provide more details on the solution?",
            "We tried the suggested steps but the problem persists.",
            "Is there a workaround we can use in the meantime?",
            "This is becoming urgent for our team."
        ]
        return random.choice(messages)
    
    def _generate_agent_message(self, index: int, issue_type: str, status: str) -> str:
        """Generate a support agent message."""
        if status in ['resolved', 'closed'] and index > 2:
            messages = [
                "I'm glad we could resolve this for you!",
                "The fix has been deployed. Please verify on your end.",
                "This should now be working as expected.",
                "Please let us know if you encounter any further issues."
            ]
        else:
            messages = [
                "Thank you for reaching out. Let me investigate this.",
                "I've reproduced the issue and am working on a solution.",
                "Could you please provide the log files?",
                "I've escalated this to our engineering team.",
                "Here's a workaround you can try in the meantime:",
                "This is a known issue that will be fixed in the next release.",
                "Let me check the configuration settings with you."
            ]
        return random.choice(messages)
    
    def _determine_sentiment(self, issue_type: str, status: str, priority: str) -> str:
        """Determine ticket sentiment based on context."""
        if status == 'closed':
            return random.choices(
                ['positive', 'neutral', 'negative'],
                weights=[0.6, 0.3, 0.1]
            )[0]
        
        if priority == 'critical':
            return random.choices(
                ['frustrated', 'negative', 'neutral'],
                weights=[0.5, 0.3, 0.2]
            )[0]
        
        if issue_type == 'Bug Report':
            return random.choices(
                ['negative', 'frustrated', 'neutral'],
                weights=[0.4, 0.3, 0.3]
            )[0]
        
        return random.choices(
            ['neutral', 'positive', 'negative'],
            weights=[0.5, 0.3, 0.2]
        )[0]
    
    def _generate_tags(self, issue_type: str, product: str, priority: str) -> List[str]:
        """Generate relevant tags for the ticket."""
        tags = [
            issue_type.lower().replace(' ', '-'),
            product.lower().replace(' ', '-')
        ]
        
        if priority in ['high', 'critical']:
            tags.append('urgent')
        
        additional_tags = ['needs-review', 'customer-impact', 'regression', 'enhancement']
        tags.extend(random.sample(additional_tags, random.randint(0, 2)))
        
        return tags
    
    def _generate_date(self) -> str:
        """Generate a creation date."""
        days_ago = random.randint(0, self.date_range_days)
        date = (self.config.get('base_time') or datetime.now()) - timedelta(days=days_ago)
        return date.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    def _generate_update_date(self, created_at: str, status: str) -> str:
        """Generate an update date after creation."""
        created = datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%SZ')
        
        if status == 'open':
            return created_at
        
        hours_later = random.randint(1, 168)  # Up to 1 week
        updated = created + timedelta(hours=hours_later)
        
        # Don't go into the future
        if updated > datetime.now():
            updated = datetime.now()
        
        return updated.strftime('%Y-%m-%dT%H:%M:%SZ')
    
def main():
    """CLI entry point for support ticket generation."""
    import argparse
    import yaml
    
    parser = argparse.ArgumentParser(description='Generate support ticket data')
    parser.add_argument('--config', type=str, help='Path to YAML config file')
    parser.add_argument('--count', type=int, default=100, help='Number of tickets')
    parser.add_argument('--output', type=str, help='Output NDJSON file path')
    parser.add_argument('--index', type=str, help='Elasticsearch index name')
    
    args = parser.parse_args()
    
    config = {}
    if args.config:
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
    
    generator = SupportGenerator(config)
    
    if args.output:
        generator.to_ndjson(args.count, args.output)
    elif args.index:
        generator.to_elasticsearch(args.count, args.index)
    else:
        for i, record in enumerate(generator.generate(3)):
            print(f"Ticket {i+1}:", record)


if __name__ == '__main__':
    main()
