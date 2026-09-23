import copy
import json
import unittest
from lab import ROOT, review

class AgentTests(unittest.TestCase):
    def setUp(self):
        self.inventory = json.loads((ROOT / 'fixtures/inventory.json').read_text())
        self.events = json.loads((ROOT / 'fixtures/events.json').read_text())

    def status(self):
        return review(self.inventory, self.events)['results'][0]['status']

    def test_four_scenarios(self):
        self.assertEqual([r['status'] for r in review(self.inventory, self.events)['results']],
                         ['WITHIN_DECLARED_SCOPE', 'OUTSIDE_DECLARED_SCOPE', 'UNKNOWN', 'UNKNOWN'])

    def test_scope_cannot_expand_by_resource(self):
        self.events['events'][0]['resource'] = 'another-catalog'
        self.assertEqual(self.status(), 'OUTSIDE_DECLARED_SCOPE')

    def test_identity_mismatch(self):
        self.events['events'][0]['identity'] = 'another-identity'
        self.assertEqual(self.status(), 'UNKNOWN')

    def test_expired_authority_at_event_time(self):
        self.inventory['agents'][0]['authority']['valid_until'] = '2026-01-15T11:55:00Z'
        self.assertEqual(self.status(), 'UNKNOWN')

    def test_history_uses_event_time_not_review_time(self):
        result = review(self.inventory, self.events, '2026-03-01T12:00:00Z')
        self.assertEqual(result['results'][0]['status'], 'WITHIN_DECLARED_SCOPE')

    def test_future_or_malformed_event(self):
        for value in ['2026-01-15T12:01:00Z', 'bad', '2026-01-15T11:55:00']:
            with self.subTest(value=value):
                self.events['events'][0]['observed_at'] = value
                self.assertEqual(self.status(), 'UNKNOWN')

    def test_owner_required(self):
        self.inventory['agents'][0]['owner'] = ''
        self.assertEqual(self.status(), 'UNKNOWN')

    def test_duplicate_identifiers_rejected(self):
        self.inventory['agents'].append(copy.deepcopy(self.inventory['agents'][0]))
        with self.assertRaises(ValueError): review(self.inventory, self.events)
        self.inventory['agents'].pop()
        self.events['events'].append(copy.deepcopy(self.events['events'][0]))
        with self.assertRaises(ValueError): review(self.inventory, self.events)

    def test_malformed_permissions(self):
        self.inventory['agents'][0]['permissions'] = [{'tool': 'records.search', 'resources': '*'}]
        self.assertEqual(self.status(), 'UNKNOWN')
