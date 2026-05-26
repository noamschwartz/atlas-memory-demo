"""
Event generator for security, observability, and analytics demos.

Generates realistic event data with:
- Time-series patterns
- Configurable anomaly injection
- User sessions and behaviour
- Multiple event types and severities

Example:
    config = {
        'time_range_hours': 24,
        'anomaly_percentage': 5,
        'user_count': 50
    }
    
    generator = EventGenerator(config)
    generator.to_ndjson(5000, 'events.ndjson')
"""

import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
import ipaddress

from faker import Faker

from .base_generator import BaseGenerator


# Default configuration for event generation
DEFAULT_CONFIG = {
    'seed': 42,
    'time_range_hours': 168,  # 1 week
    'user_count': 50,
    'event_types': {
        'login': {'weight': 0.25, 'severities': ['info']},
        'logout': {'weight': 0.15, 'severities': ['info']},
        'access': {'weight': 0.35, 'severities': ['info', 'warning']},
        'alert': {'weight': 0.15, 'severities': ['warning', 'error', 'critical']},
        'error': {'weight': 0.10, 'severities': ['error', 'critical']}
    },
    'anomaly_config': {
        'percentage': 5,
        'types': [
            'brute_force',
            'unusual_time',
            'data_exfiltration',
            'privilege_escalation'
        ]
    },
    'ip_ranges': {
        'internal': ['192.168.1.0/24', '10.0.0.0/8'],
        'external': ['203.0.113.0/24']  # Documentation range
    },
    'resources': [
        '/api/users',
        '/api/products',
        '/api/orders',
        '/api/settings',
        '/api/admin',
        '/dashboard',
        '/reports',
        '/files'
    ]
}


class EventGenerator(BaseGenerator):
    """Generate realistic security and observability events.
    
    Creates time-series event data suitable for:
    - Security/SIEM dashboards
    - Anomaly detection demos
    - User behaviour analytics
    - Audit logging demonstrations
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialise the event generator.
        
        Args:
            config: Generator configuration. Merged with DEFAULT_CONFIG.
        """
        # Deep merge nested dicts (anomaly_config, event_types, etc.)
        # so partial overrides don't lose sibling keys
        user_config = config or {}
        merged_config = {**DEFAULT_CONFIG}
        for key, value in user_config.items():
            if key in merged_config and isinstance(merged_config[key], dict) and isinstance(value, dict):
                merged_config[key] = {**merged_config[key], **value}
            else:
                merged_config[key] = value
        super().__init__(merged_config)
        
        self.fake = Faker()
        Faker.seed(self.seed)
        
        self.time_range_hours = self.config['time_range_hours']
        self.user_count = self.config['user_count']
        self.event_types = self.config['event_types']
        self.anomaly_config = self.config['anomaly_config']
        self.ip_ranges = self.config['ip_ranges']
        self.resources = self.config['resources']
        
        # Pre-generate users and their typical IPs
        self.users = self._generate_users()
        
        # Calculate time boundaries (use config base_time for reproducibility)
        self.end_time = self.config.get('base_time') or datetime.now()
        self.start_time = self.end_time - timedelta(hours=self.time_range_hours)
    
    def _generate_users(self) -> List[Dict[str, Any]]:
        """Pre-generate user profiles with typical behaviour."""
        users = []
        for i in range(self.user_count):
            user_id = f"user-{i:04d}"
            users.append({
                'id': user_id,
                'name': self.fake.user_name(),
                'department': random.choice(['Engineering', 'Sales', 'Marketing', 'HR', 'Finance']),
                'role': random.choice(['user', 'user', 'user', 'admin', 'service_account']),
                'typical_ip': self._generate_ip('internal'),
                'typical_hours': (random.randint(7, 10), random.randint(17, 20))  # Work hours
            })
        return users
    
    def _generate_ip(self, ip_type: str = 'internal') -> str:
        """Generate a random IP from configured ranges."""
        ranges = self.ip_ranges.get(ip_type, self.ip_ranges['internal'])
        network = ipaddress.ip_network(random.choice(ranges))
        
        # Generate random IP within network
        network_int = int(network.network_address)
        broadcast_int = int(network.broadcast_address)
        random_ip_int = random.randint(network_int + 1, broadcast_int - 1)
        
        return str(ipaddress.ip_address(random_ip_int))
    
    def generate_record(self, index: int) -> Dict[str, Any]:
        """Generate a single event record.
        
        Args:
            index: Event index (0-based).
            
        Returns:
            Event dictionary with all fields.
        """
        event_id = f"evt-{index:08d}"
        
        # Generate base event
        event = self._generate_normal_event(event_id, index)
        
        # Possibly inject anomaly
        if random.random() < self.anomaly_config['percentage'] / 100:
            event = self._inject_anomaly(event)
        
        return event
    
    def _generate_normal_event(self, event_id: str, index: int) -> Dict[str, Any]:
        """Generate a normal (non-anomalous) event."""
        # Select event type based on weights
        event_type = self.weighted_choice(
            list(self.event_types.keys()),
            [et['weight'] for et in self.event_types.values()]
        )
        type_config = self.event_types[event_type]
        
        # Select user
        user = random.choice(self.users)
        
        # Generate timestamp with business hours bias
        timestamp = self._generate_timestamp(user['typical_hours'])
        
        # Determine outcome
        outcome = 'success' if random.random() > 0.05 else 'failure'
        
        # Select severity
        severity = random.choice(type_config['severities'])
        
        return {
            'id': event_id,
            'timestamp': timestamp.isoformat() + 'Z',
            'event_type': event_type,
            'severity': severity,
            'source_ip': user['typical_ip'] if random.random() > 0.1 else self._generate_ip('internal'),
            'user_id': user['id'],
            'user_name': user['name'],
            'user_role': user['role'],
            'department': user['department'],
            'resource': random.choice(self.resources),
            'action': self._get_action_for_event(event_type),
            'outcome': outcome,
            'message': self._generate_message(event_type, outcome, user['name']),
            'metadata': self._generate_metadata(),
            'is_anomaly': False,
            'anomaly_type': None
        }
    
    def _inject_anomaly(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Inject anomalous behaviour into an event."""
        anomaly_type = random.choice(self.anomaly_config['types'])
        event['is_anomaly'] = True
        event['anomaly_type'] = anomaly_type
        
        if anomaly_type == 'brute_force':
            event['event_type'] = 'login'
            event['outcome'] = 'failure'
            event['severity'] = 'warning'
            event['message'] = f"Failed login attempt for user {event['user_name']}"
            event['metadata']['attempt_count'] = random.randint(5, 50)
            event['source_ip'] = self._generate_ip('external')
            
        elif anomaly_type == 'unusual_time':
            # Generate timestamp outside business hours
            hour = random.choice([0, 1, 2, 3, 4, 5, 22, 23])
            ts = datetime.fromisoformat(event['timestamp'].rstrip('Z'))
            event['timestamp'] = ts.replace(hour=hour).isoformat() + 'Z'
            event['severity'] = 'warning'
            event['message'] = f"Unusual access time detected for {event['user_name']}"
            
        elif anomaly_type == 'data_exfiltration':
            event['event_type'] = 'access'
            event['action'] = 'download'
            event['severity'] = 'error'
            event['message'] = f"Large data download by {event['user_name']}"
            event['metadata']['bytes_transferred'] = random.randint(100_000_000, 10_000_000_000)
            event['resource'] = random.choice(['/files', '/reports', '/api/export'])
            
        elif anomaly_type == 'privilege_escalation':
            event['event_type'] = 'access'
            event['resource'] = '/api/admin'
            event['severity'] = 'critical'
            event['message'] = f"Potential privilege escalation by {event['user_name']}"
            event['metadata']['previous_role'] = 'user'
            event['metadata']['attempted_role'] = 'admin'
        
        return event
    
    def _generate_timestamp(self, typical_hours: Tuple[int, int]) -> datetime:
        """Generate a timestamp with business hours bias."""
        # Random time within range
        total_seconds = self.time_range_hours * 3600
        random_seconds = random.randint(0, total_seconds)
        timestamp = self.start_time + timedelta(seconds=random_seconds)
        
        # 80% chance of being within business hours
        if random.random() < 0.8:
            start_hour, end_hour = typical_hours
            current_hour = timestamp.hour
            
            if current_hour < start_hour or current_hour > end_hour:
                # Adjust to business hours
                new_hour = random.randint(start_hour, end_hour)
                timestamp = timestamp.replace(hour=new_hour)
        
        return timestamp
    
    def _get_action_for_event(self, event_type: str) -> str:
        """Get appropriate action for event type."""
        actions = {
            'login': 'authenticate',
            'logout': 'deauthenticate',
            'access': random.choice(['read', 'write', 'delete', 'execute']),
            'alert': 'notify',
            'error': 'fail'
        }
        return actions.get(event_type, 'unknown')
    
    def _generate_message(self, event_type: str, outcome: str, user_name: str) -> str:
        """Generate human-readable event message."""
        messages = {
            ('login', 'success'): f"User {user_name} logged in successfully",
            ('login', 'failure'): f"Failed login attempt for user {user_name}",
            ('logout', 'success'): f"User {user_name} logged out",
            ('logout', 'failure'): f"Logout failed for user {user_name}",
            ('access', 'success'): f"Resource accessed by {user_name}",
            ('access', 'failure'): f"Access denied for {user_name}",
            ('alert', 'success'): f"Security alert triggered for {user_name}",
            ('alert', 'failure'): f"Alert notification failed",
            ('error', 'success'): f"Error logged for {user_name}",
            ('error', 'failure'): f"Critical error occurred"
        }
        return messages.get((event_type, outcome), f"Event: {event_type} - {outcome}")
    
    def _generate_metadata(self) -> Dict[str, Any]:
        """Generate event metadata."""
        return {
            'browser': random.choice(['Chrome 120', 'Firefox 121', 'Safari 17', 'Edge 120']),
            'os': random.choice(['Windows 11', 'macOS 14', 'Linux', 'iOS', 'Android']),
            'location': random.choice(['US-East', 'US-West', 'EU-West', 'APAC']),
            'session_id': f"sess-{random.randint(10000, 99999)}"
        }
    
def main():
    """CLI entry point for event generation."""
    import argparse
    import yaml
    
    parser = argparse.ArgumentParser(description='Generate event/log data')
    parser.add_argument('--config', type=str, help='Path to YAML config file')
    parser.add_argument('--count', type=int, default=1000, help='Number of events')
    parser.add_argument('--output', type=str, help='Output NDJSON file path')
    parser.add_argument('--index', type=str, help='Elasticsearch index name')
    parser.add_argument('--hours', type=int, default=168, help='Time range in hours')
    parser.add_argument('--anomaly-pct', type=int, default=5, help='Anomaly percentage')
    
    args = parser.parse_args()
    
    config = {
        'time_range_hours': args.hours,
    }

    if args.config:
        with open(args.config, 'r') as f:
            config = {**config, **yaml.safe_load(f)}

    # Deep merge anomaly_pct into anomaly_config to avoid overwriting 'types'
    config.setdefault('anomaly_config', {})['percentage'] = args.anomaly_pct
    
    generator = EventGenerator(config)
    
    if args.output:
        generator.to_ndjson(args.count, args.output)
    elif args.index:
        generator.to_elasticsearch(args.count, args.index)
    else:
        for i, record in enumerate(generator.generate(5)):
            print(f"Event {i+1}:", record)


if __name__ == '__main__':
    main()
