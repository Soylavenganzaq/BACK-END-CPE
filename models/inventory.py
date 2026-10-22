from dataclasses import dataclass
from datetime import date


class ValidationError(ValueError):
    pass


class DuplicateActiveEquipment(ValueError):
    pass


class PersistenceNotConfigured(RuntimeError):
    pass


@dataclass(frozen=True)
class EntryBatch:
    macs: tuple[str, ...]
    technician_id: int
    responsible_user_id: int
    equipment_type_id: int
    condition_id: int
    observations: str | None = None


@dataclass(frozen=True)
class DeliveryBatch:
    macs: tuple[str, ...]
    responsible_user_id: int
    condition_id: int
    observations: str | None = None


@dataclass(frozen=True)
class AvailableFilters:
    mac: str | None = None
    equipment_type_id: int | None = None
    date_from: date | None = None
    date_to: date | None = None


@dataclass(frozen=True)
class OperationReportFilters:
    date_from: date | None = None
    date_to: date | None = None
    user_id: int | None = None