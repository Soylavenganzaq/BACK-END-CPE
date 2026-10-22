from typing import Any, Protocol

from models.inventory import (
    AvailableFilters,
    DeliveryBatch,
    EntryBatch,
    OperationReportFilters,
)


class InventoryRepository(Protocol):
    """Persistencia a implementar con las tablas y funciones del SQL oficial."""

    def register_entries(self, batch: EntryBatch) -> Any: ...

    def register_deliveries(self, batch: DeliveryBatch) -> Any: ...

    def get_history_by_mac(self, mac: str) -> Any: ...

    def list_available(self, filters: AvailableFilters) -> Any: ...

    def list_operations(self, filters: OperationReportFilters) -> Any: ...

    def daily_volume(self, filters: OperationReportFilters) -> Any: ...