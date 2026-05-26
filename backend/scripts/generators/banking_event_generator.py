"""
Banking / finance event generator for fraud detection and analytics demos.

Generates realistic banking events with:
- Transactions (card payments, transfers, withdrawals)
- Fraud alerts with risk scoring
- Customer logins across channels (web, mobile, ATM)
- Account changes (address, phone, password, email)
- Wire transfers with high-value flagging

Anomaly types:
- unusual_amount   — transaction far above customer's norm
- velocity_breach  — many transactions in a short window
- geo_anomaly      — activity from an unusual region
- dormant_reactivation — long-dormant account suddenly active

Example:
    generator = BankingEventGenerator()
    generator.to_ndjson(5000, 'banking_events.ndjson')
"""

import random
import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
import ipaddress

from faker import Faker

from .base_generator import BaseGenerator


# Minimal defaults — full config lives in config/banking_events.yaml
DEFAULT_CONFIG = {
    'seed': 42,
    'time_range_hours': 168,
    'customer_count': 200,
    'event_types': {
        'transaction': {'weight': 0.35, 'severities': ['info']},
        'fraud_alert': {'weight': 0.10, 'severities': ['warning', 'error', 'critical']},
        'login': {'weight': 0.25, 'severities': ['info']},
        'account_change': {'weight': 0.15, 'severities': ['info', 'warning']},
        'wire_transfer': {'weight': 0.15, 'severities': ['info', 'warning']},
    },
    'anomaly_config': {
        'percentage': 5,
        'types': [
            'unusual_amount',
            'velocity_breach',
            'geo_anomaly',
            'dormant_reactivation',
        ],
    },
    'transaction_types': ['transfer', 'payment', 'withdrawal', 'deposit', 'refund'],
    'currencies': [
        {'code': 'USD', 'weight': 0.50},
        {'code': 'EUR', 'weight': 0.25},
        {'code': 'GBP', 'weight': 0.25},
    ],
    'merchant_categories': [
        {
            'category': 'Grocery Stores',
            'merchants': ['Whole Foods', 'Kroger', 'Safeway'],
            'avg_amount': 85.0,
            'std_amount': 45.0,
        },
        {
            'category': 'Online Retail',
            'merchants': ['Amazon', 'eBay'],
            'avg_amount': 120.0,
            'std_amount': 85.0,
        },
    ],
    'fraud_reasons': [
        'Transaction amount exceeds daily limit',
        'Unusual spending pattern detected',
    ],
    'login_channels': [
        {'channel': 'web', 'weight': 0.50},
        {'channel': 'mobile', 'weight': 0.35},
        {'channel': 'atm', 'weight': 0.15},
    ],
    'account_change_types': [
        {'type': 'address', 'weight': 0.30},
        {'type': 'phone', 'weight': 0.25},
        {'type': 'email', 'weight': 0.20},
        {'type': 'password', 'weight': 0.25},
    ],
    'wire_destinations': [
        {'country': 'US', 'weight': 0.40, 'high_risk': False},
        {'country': 'GB', 'weight': 0.30, 'high_risk': False},
        {'country': 'NG', 'weight': 0.15, 'high_risk': True},
        {'country': 'RU', 'weight': 0.15, 'high_risk': True},
    ],
    'wire_amount': {
        'min': 500.0,
        'max': 500000.0,
        'mean': 25000.0,
        'std': 40000.0,
        'high_value_threshold': 50000.0,
    },
    'banks': ['JPMorgan Chase', 'Bank of America', 'Wells Fargo', 'Citibank'],
    'ip_ranges': {
        'corporate': ['10.0.0.0/8'],
        'vpn': ['198.51.100.0/24'],
        'public': ['203.0.113.0/24'],
    },
    'regions': [
        {'name': 'US-East', 'weight': 0.40},
        {'name': 'EU-West', 'weight': 0.30},
        {'name': 'APAC-East', 'weight': 0.30},
    ],
}


class BankingEventGenerator(BaseGenerator):
    """Generate realistic banking and finance events.

    Creates time-series event data suitable for:
    - Fraud detection dashboards
    - Transaction monitoring
    - Customer login analytics
    - Wire transfer compliance
    - Account activity auditing
    """

    def __init__(self, config: Dict[str, Any] = None):
        merged_config = {**DEFAULT_CONFIG, **(config or {})}
        super().__init__(merged_config)

        self.fake = Faker()
        Faker.seed(self.seed)

        self.time_range_hours = self.config['time_range_hours']
        self.customer_count = self.config['customer_count']
        self.event_types = self.config['event_types']
        self.anomaly_config = self.config['anomaly_config']
        self.ip_ranges = self.config['ip_ranges']

        # Pre-generate customers
        self.customers = self._generate_customers()

        # Time boundaries
        self.end_time = datetime.now()
        self.start_time = self.end_time - timedelta(hours=self.time_range_hours)

    # ------------------------------------------------------------------
    # Customer profiles
    # ------------------------------------------------------------------

    def _generate_customers(self) -> List[Dict[str, Any]]:
        customers = []
        for i in range(self.customer_count):
            cust_id = f"CUST-{i:06d}"
            acct_id = f"ACCT-{random.randint(100000000, 999999999)}"
            customers.append({
                'customer_id': cust_id,
                'account_id': acct_id,
                'name': self.fake.name(),
                'typical_region': self._pick_region(),
                'typical_ip': self._generate_ip('corporate'),
                'typical_hours': (random.randint(7, 10), random.randint(17, 20)),
                'avg_transaction_amount': random.uniform(20.0, 500.0),
                'is_dormant': random.random() < 0.05,  # 5% dormant
                'last_active_days_ago': random.randint(0, 365),
            })
        return customers

    # ------------------------------------------------------------------
    # IP / region helpers
    # ------------------------------------------------------------------

    def _generate_ip(self, ip_type: str = 'corporate') -> str:
        ranges = self.ip_ranges.get(ip_type, self.ip_ranges.get('corporate', ['10.0.0.0/8']))
        network = ipaddress.ip_network(random.choice(ranges))
        net_int = int(network.network_address)
        bcast_int = int(network.broadcast_address)
        if bcast_int - net_int <= 2:
            return str(network.network_address + 1)
        return str(ipaddress.ip_address(random.randint(net_int + 1, bcast_int - 1)))

    def _pick_region(self) -> str:
        regions = self.config['regions']
        return self.weighted_choice(
            [r['name'] for r in regions],
            [r['weight'] for r in regions],
        )

    def _pick_currency(self) -> str:
        currencies = self.config['currencies']
        return self.weighted_choice(
            [c['code'] for c in currencies],
            [c['weight'] for c in currencies],
        )

    def _pick_channel(self) -> str:
        channels = self.config['login_channels']
        return self.weighted_choice(
            [c['channel'] for c in channels],
            [c['weight'] for c in channels],
        )

    def _pick_account_change_type(self) -> str:
        types = self.config['account_change_types']
        return self.weighted_choice(
            [t['type'] for t in types],
            [t['weight'] for t in types],
        )

    def _pick_wire_destination(self) -> Dict[str, Any]:
        dests = self.config['wire_destinations']
        idx = self.weighted_choice(
            list(range(len(dests))),
            [d['weight'] for d in dests],
        )
        return dests[idx]

    # ------------------------------------------------------------------
    # Timestamp generation
    # ------------------------------------------------------------------

    def _generate_timestamp(self, typical_hours: Tuple[int, int]) -> datetime:
        total_seconds = self.time_range_hours * 3600
        random_seconds = random.randint(0, total_seconds)
        timestamp = self.start_time + timedelta(seconds=random_seconds)

        # 80% chance within business hours
        if random.random() < 0.8:
            start_h, end_h = typical_hours
            if timestamp.hour < start_h or timestamp.hour > end_h:
                timestamp = timestamp.replace(hour=random.randint(start_h, end_h))

        return timestamp

    # ------------------------------------------------------------------
    # Record generation
    # ------------------------------------------------------------------

    def generate_record(self, index: int) -> Dict[str, Any]:
        event_id = f"bnk-{index:08d}"
        event = self._generate_normal_event(event_id, index)

        if random.random() < self.anomaly_config['percentage'] / 100:
            event = self._inject_anomaly(event)

        return event

    def _generate_normal_event(self, event_id: str, index: int) -> Dict[str, Any]:
        event_type = self.weighted_choice(
            list(self.event_types.keys()),
            [et['weight'] for et in self.event_types.values()],
        )
        type_config = self.event_types[event_type]
        customer = random.choice(self.customers)
        timestamp = self._generate_timestamp(customer['typical_hours'])
        severity = random.choice(type_config['severities'])

        base = {
            'id': event_id,
            'timestamp': timestamp.isoformat() + 'Z',
            'event_type': event_type,
            'severity': severity,
            'customer_id': customer['customer_id'],
            'account_id': customer['account_id'],
            'customer_name': customer['name'],
            'region': customer['typical_region'],
            'is_anomaly': False,
            'anomaly_type': None,
        }

        # Add event-type-specific fields
        builder = {
            'transaction': self._build_transaction,
            'fraud_alert': self._build_fraud_alert,
            'login': self._build_login,
            'account_change': self._build_account_change,
            'wire_transfer': self._build_wire_transfer,
        }
        builder_fn = builder.get(event_type, self._build_transaction)
        base.update(builder_fn(customer))

        return base

    # ------------------------------------------------------------------
    # Event type builders
    # ------------------------------------------------------------------

    def _build_transaction(self, customer: Dict[str, Any]) -> Dict[str, Any]:
        cat = random.choice(self.config['merchant_categories'])
        merchant = random.choice(cat['merchants'])
        amount = max(0.01, random.gauss(cat['avg_amount'], cat['std_amount']))

        return {
            'amount': round(amount, 2),
            'currency': self._pick_currency(),
            'transaction_type': random.choice(self.config['transaction_types']),
            'merchant': merchant,
            'merchant_category': cat['category'],
            'from_account': customer['account_id'],
            'to_account': f"ACCT-{random.randint(100000000, 999999999)}",
            'message': f"Payment of {amount:.2f} at {merchant}",
        }

    def _build_fraud_alert(self, customer: Dict[str, Any]) -> Dict[str, Any]:
        risk_score = random.randint(30, 100)
        blocked = risk_score > 75
        reason = random.choice(self.config['fraud_reasons'])

        return {
            'risk_score': risk_score,
            'reason': reason,
            'blocked': blocked,
            'transaction_ref': f"bnk-{random.randint(0, 99999999):08d}",
            'message': f"Fraud alert (score={risk_score}): {reason}",
        }

    def _build_login(self, customer: Dict[str, Any]) -> Dict[str, Any]:
        channel = self._pick_channel()
        success = random.random() > 0.08  # 8% failure rate
        ip_type = 'corporate' if channel in ('web', 'phone_banking') else 'public'
        ip_address_str = self._generate_ip(ip_type) if random.random() > 0.1 else customer['typical_ip']

        return {
            'channel': channel,
            'success': success,
            'ip_address': ip_address_str,
            'user_agent': random.choice([
                'Mobile Banking App/3.2 iOS/17',
                'Mobile Banking App/3.1 Android/14',
                'Mozilla/5.0 Chrome/120',
                'Mozilla/5.0 Safari/17',
                'ATM-Client/1.0',
            ]) if channel != 'atm' else 'ATM-Client/1.0',
            'message': f"Login {'succeeded' if success else 'failed'} via {channel}",
        }

    def _build_account_change(self, customer: Dict[str, Any]) -> Dict[str, Any]:
        change_type = self._pick_account_change_type()
        return {
            'change_type': change_type,
            'verified': random.random() > 0.15,  # 85% verified
            'channel': random.choice(['web', 'mobile', 'branch', 'phone']),
            'message': f"Account {change_type} change requested",
        }

    def _build_wire_transfer(self, customer: Dict[str, Any]) -> Dict[str, Any]:
        dest = self._pick_wire_destination()
        wire_cfg = self.config['wire_amount']
        amount = max(wire_cfg['min'], random.gauss(wire_cfg['mean'], wire_cfg['std']))
        amount = min(amount, wire_cfg['max'])
        high_value = amount >= wire_cfg['high_value_threshold']

        return {
            'amount': round(amount, 2),
            'currency': self._pick_currency(),
            'destination_country': dest['country'],
            'destination_bank': random.choice(self.config['banks']),
            'beneficiary': self.fake.name(),
            'high_value': high_value,
            'high_risk_country': dest.get('high_risk', False),
            'reference': f"WIRE-{random.randint(100000, 999999)}",
            'message': f"Wire transfer of {amount:.2f} to {dest['country']}",
        }

    # ------------------------------------------------------------------
    # Anomaly injection
    # ------------------------------------------------------------------

    def _inject_anomaly(self, event: Dict[str, Any]) -> Dict[str, Any]:
        anomaly_type = random.choice(self.anomaly_config['types'])
        event['is_anomaly'] = True
        event['anomaly_type'] = anomaly_type

        injector = {
            'unusual_amount': self._anomaly_unusual_amount,
            'velocity_breach': self._anomaly_velocity_breach,
            'geo_anomaly': self._anomaly_geo,
            'dormant_reactivation': self._anomaly_dormant,
        }
        fn = injector.get(anomaly_type)
        if fn:
            event = fn(event)

        return event

    def _anomaly_unusual_amount(self, event: Dict[str, Any]) -> Dict[str, Any]:
        event['event_type'] = 'transaction'
        customer = self._find_customer(event['customer_id'])
        normal_avg = customer['avg_transaction_amount'] if customer else 100.0
        spike = normal_avg * random.uniform(8, 25)
        event['amount'] = round(spike, 2)
        event['currency'] = self._pick_currency()
        event['transaction_type'] = random.choice(['payment', 'withdrawal'])
        event['merchant'] = random.choice(['Luxury Goods Inc.', 'Electronics Megastore', 'Jewellery Emporium'])
        event['merchant_category'] = 'High Value Retail'
        event['severity'] = 'warning'
        event['message'] = f"Unusual transaction amount: {spike:.2f} (typical avg: {normal_avg:.2f})"
        return event

    def _anomaly_velocity_breach(self, event: Dict[str, Any]) -> Dict[str, Any]:
        event['event_type'] = 'transaction'
        event['severity'] = 'error'
        txn_count = random.randint(8, 30)
        window_minutes = random.randint(2, 10)
        event['velocity_count'] = txn_count
        event['velocity_window_minutes'] = window_minutes
        event['amount'] = round(random.uniform(10, 200), 2)
        event['transaction_type'] = 'payment'
        event['merchant'] = random.choice(self.config['merchant_categories'][0]['merchants'])
        event['message'] = f"Velocity breach: {txn_count} transactions in {window_minutes} minutes"
        return event

    def _anomaly_geo(self, event: Dict[str, Any]) -> Dict[str, Any]:
        customer = self._find_customer(event['customer_id'])
        typical_region = customer['typical_region'] if customer else 'US-East'
        all_regions = [r['name'] for r in self.config['regions']]
        other_regions = [r for r in all_regions if r != typical_region]
        anomalous_region = random.choice(other_regions) if other_regions else 'Unknown'

        event['region'] = anomalous_region
        event['typical_region'] = typical_region
        event['severity'] = 'warning'
        event['ip_address'] = self._generate_ip('public')
        event['message'] = f"Activity from {anomalous_region} (typical: {typical_region})"
        return event

    def _anomaly_dormant(self, event: Dict[str, Any]) -> Dict[str, Any]:
        event['severity'] = 'warning'
        event['dormant_days'] = random.randint(90, 730)
        event['message'] = f"Dormant account reactivated after {event['dormant_days']} days"
        return event

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_customer(self, customer_id: str) -> Dict[str, Any] | None:
        for c in self.customers:
            if c['customer_id'] == customer_id:
                return c
        return None


def main():
    """CLI entry point for banking event generation."""
    import argparse
    import yaml

    parser = argparse.ArgumentParser(description='Generate banking/finance event data')
    parser.add_argument('--config', type=str, help='Path to YAML config file')
    parser.add_argument('--count', type=int, default=1000, help='Number of events')
    parser.add_argument('--output', type=str, help='Output NDJSON file path')
    parser.add_argument('--index', type=str, help='Elasticsearch index name')
    parser.add_argument('--hours', type=int, default=168, help='Time range in hours')
    parser.add_argument('--anomaly-pct', type=int, default=5, help='Anomaly percentage')

    args = parser.parse_args()

    config = {
        'time_range_hours': args.hours,
        'anomaly_config': {'percentage': args.anomaly_pct},
    }

    if args.config:
        with open(args.config, 'r') as f:
            config = {**config, **yaml.safe_load(f)}

    generator = BankingEventGenerator(config)

    if args.output:
        generator.to_ndjson(args.count, args.output)
    elif args.index:
        generator.to_elasticsearch(args.count, args.index)
    else:
        for i, record in enumerate(generator.generate(5)):
            print(f"Event {i + 1}: {record}")


if __name__ == '__main__':
    main()
