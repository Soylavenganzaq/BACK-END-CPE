import re
from datetime import date
from typing import Any

from models.inventory import (
    AvailableFilters,
    DeliveryBatch,
    EntryBatch,
    OperationReportFilters,
    ValidationError,
)
from repositories.inventory_repository import InventoryRepository


_MAC_SEPARATORS = re.compile(r'[:.\-]')
_MAC_HEX = re.compile(r'^[0-9a-fA-F]{12}$')
_MAX_BATCH_SIZE = 500


def normalize_mac(value: Any) -> str:
    if not isinstance(value, str):
        raise ValidationError('Cada MAC debe ser texto.')
    compact = _MAC_SEPARATORS.sub('', value.strip())
    if not _MAC_HEX.fullmatch(compact):
        raise ValidationError(f'Dirección MAC inválida: {value!r}.')
    octets = compact.upper()
    return ':'.join(octets[index:index + 2] for index in range(0, 12, 2))


def _positive_id(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValidationError(f'{field} debe ser un entero positivo.')
    return value


def _observations(value: Any) -> str | None:
    if value is not None and not isinstance(value, str):
        raise ValidationError('observations debe ser texto o null.')
    return value.strip() or None if value is not None else None


def _mac_batch(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list) or not values:
        raise ValidationError('macs debe ser una lista no vacía.')
    if len(values) > _MAX_BATCH_SIZE:
        raise ValidationError(f'El lote no puede superar {_MAX_BATCH_SIZE} MAC.')
    macs = tuple(normalize_mac(value) for value in values)
    if len(set(macs)) != len(macs):
        raise ValidationError('El lote contiene MAC duplicadas.')
    return macs


def _parse_date(value: Any, field: str) -> date | None:
    if value is None or value == '':
        return None
    if not isinstance(value, str):
        raise ValidationError(f'{field} debe usar formato YYYY-MM-DD.')
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValidationError(f'{field} debe usar formato YYYY-MM-DD.') from error


def _validate_date_range(date_from: date | None, date_to: date | None) -> None:
    if date_from and date_to and date_from > date_to:
        raise ValidationError('date_from no puede ser posterior a date_to.')


class InventoryService:
    def __init__(self, repository: InventoryRepository):
        self.repository = repository

    def register_entries(self, payload: Any, responsible_user_id: int):
        data = _object_payload(payload)
        batch = EntryBatch(
            macs=_mac_batch(data.get('macs')),
            technician_id=_positive_id(data.get('technician_id'), 'technician_id'),
            responsible_user_id=_positive_id(responsible_user_id, 'user_id'),
            equipment_type_id=_positive_id(data.get('equipment_type_id'), 'equipment_type_id'),
            condition_id=_positive_id(data.get('condition_id'), 'condition_id'),
            observations=_observations(data.get('observations')),
        )
        return self.repository.register_entries(batch)

    def register_deliveries(self, payload: Any, responsible_user_id: int):
        data = _object_payload(payload)
        batch = DeliveryBatch(
            macs=_mac_batch(data.get('macs')),
            responsible_user_id=_positive_id(responsible_user_id, 'user_id'),
            condition_id=_positive_id(data.get('condition_id'), 'condition_id'),
            observations=_observations(data.get('observations')),
        )
        return self.repository.register_deliveries(batch)

    def get_history_by_mac(self, mac: Any):
        return self.repository.get_history_by_mac(normalize_mac(mac))

    def list_available(self, query: Any):
        data = query or {}
        mac = data.get('mac')
        filters = AvailableFilters(
            mac=normalize_mac(mac) if mac else None,
            equipment_type_id=(
                _positive_id(_parse_int(data.get('equipment_type_id'), 'equipment_type_id'), 'equipment_type_id')
                if data.get('equipment_type_id') else None
            ),
            date_from=_parse_date(data.get('date_from'), 'date_from'),
            date_to=_parse_date(data.get('date_to'), 'date_to'),
        )
        _validate_date_range(filters.date_from, filters.date_to)
        return self.repository.list_available(filters)

    def list_operations(self, query: Any):
        filters = _report_filters(query)
        return self.repository.list_operations(filters)

    def daily_volume(self, query: Any):
        filters = _report_filters(query)
        return self.repository.daily_volume(filters)


def _object_payload(payload: Any) -> dict:
    if not isinstance(payload, dict):
        raise ValidationError('El cuerpo debe ser un objeto JSON.')
    return payload


def _parse_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValidationError(f'{field} debe ser un entero.')
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValidationError(f'{field} debe ser un entero.') from error


def _report_filters(query: Any) -> OperationReportFilters:
    query = query or {}
    date_from = _parse_date(query.get('date_from'), 'date_from')
    date_to = _parse_date(query.get('date_to'), 'date_to')
    _validate_date_range(date_from, date_to)
    user_id = query.get('user_id')
    return OperationReportFilters(
        date_from=date_from,
        date_to=date_to,
        user_id=_positive_id(_parse_int(user_id, 'user_id'), 'user_id') if user_id else None,
    )