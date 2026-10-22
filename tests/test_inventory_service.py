import unittest
from datetime import date

from models.inventory import AvailableFilters, DeliveryBatch, EntryBatch, ValidationError
from services.inventory_service import InventoryService, normalize_mac


class FakeInventoryRepository:
    def __init__(self):
        self.entries = []
        self.deliveries = []
        self.filters = None

    def register_entries(self, batch):
        self.entries.append(batch)
        return {'accepted_for_test': len(batch.macs)}

    def list_available(self, filters):
        self.filters = filters
        return []

    def register_deliveries(self, batch):
        self.deliveries.append(batch)
        return {'accepted_for_test': len(batch.macs)}


class InventoryServiceTests(unittest.TestCase):
    def setUp(self):
        self.repository = FakeInventoryRepository()
        self.service = InventoryService(self.repository)

    def test_normalizes_supported_mac_separators(self):
        self.assertEqual(normalize_mac('aabb.ccdd.eeff'), 'AA:BB:CC:DD:EE:FF')
        self.assertEqual(normalize_mac('aa-bb-cc-dd-ee-ff'), 'AA:BB:CC:DD:EE:FF')

    def test_entry_batch_sends_normalized_mac_and_actor(self):
        result = self.service.register_entries({
            'macs': ['aabb.ccdd.eeff'],
            'technician_id': 4,
            'equipment_type_id': 8,
            'condition_id': 2,
            'observations': ' recibido ',
        }, responsible_user_id=12)

        self.assertEqual(result, {'accepted_for_test': 1})
        self.assertEqual(self.repository.entries[0], EntryBatch(
            macs=('AA:BB:CC:DD:EE:FF',),
            technician_id=4,
            responsible_user_id=12,
            equipment_type_id=8,
            condition_id=2,
            observations='recibido',
        ))

    def test_duplicate_normalized_macs_are_rejected_before_repository(self):
        payload = {
            'macs': ['aabb.ccdd.eeff', 'AA:BB:CC:DD:EE:FF'],
            'technician_id': 4,
            'equipment_type_id': 8,
            'condition_id': 2,
        }
        with self.assertRaises(ValidationError):
            self.service.register_entries(payload, responsible_user_id=12)
        self.assertEqual(self.repository.entries, [])

    def test_available_date_filters_are_parsed(self):
        self.service.list_available({'date_from': '2026-10-01', 'date_to': '2026-10-22'})
        self.assertEqual(self.repository.filters, AvailableFilters(
            date_from=date(2026, 10, 1), date_to=date(2026, 10, 22)
        ))

    def test_invalid_date_range_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.service.list_available({'date_from': '2026-10-23', 'date_to': '2026-10-22'})
        self.assertIsNone(self.repository.filters)

    def test_delivery_batch_sends_normalized_mac_and_actor(self):
        result = self.service.register_deliveries({
            'macs': ['aabb.ccdd.eeff'],
            'condition_id': 3,
            'observations': 'entregado',
        }, responsible_user_id=9)

        self.assertEqual(result, {'accepted_for_test': 1})
        self.assertEqual(self.repository.deliveries[0], DeliveryBatch(
            macs=('AA:BB:CC:DD:EE:FF',),
            responsible_user_id=9,
            condition_id=3,
            observations='entregado',
        ))


if __name__ == '__main__':
    unittest.main()