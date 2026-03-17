import datetime
import sys
from collections import defaultdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import Boolean, Column, Date, DateTime, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config.settings import settings

Base = declarative_base()


class RoomCatalog(Base):
    __tablename__ = 'room_catalog'

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_type = Column(String(50), nullable=False, unique=True)
    capacity = Column(Integer, nullable=False, default=2)
    price_eur = Column(Integer, nullable=False, default=80)
    rooms_per_day = Column(Integer, nullable=False, default=10)
    is_active = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)


class RoomStock(Base):
    __tablename__ = 'room_stock'

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_type = Column(String(50), nullable=False)
    date = Column(Date, nullable=False)
    available = Column(Boolean, default=True)


_SQLITE_ARGS = {'check_same_thread': False} if settings.database_url.startswith('sqlite') else {}
engine = create_engine(settings.database_url, connect_args=_SQLITE_ARGS)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

DEFAULT_ROOM_CATALOG = [
    {'room_type': 'standard', 'capacity': 2, 'price_eur': 80, 'rooms_per_day': 20, 'is_active': True},
    {'room_type': 'deluxe', 'capacity': 2, 'price_eur': 110, 'rooms_per_day': 12, 'is_active': True},
    {'room_type': 'suite', 'capacity': 4, 'price_eur': 150, 'rooms_per_day': 8, 'is_active': True},
    {'room_type': 'familiale', 'capacity': 5, 'price_eur': 130, 'rooms_per_day': 10, 'is_active': True},
]
DEFAULT_HORIZON_DAYS = 180


def _normalize_room_type(room_type: str | None) -> str:
    value = (room_type or 'standard').strip().lower()
    if value in {'family', 'family room'}:
        return 'familiale'
    if value in {'de luxe'}:
        return 'deluxe'
    return value


def _ensure_catalog_seed(db) -> int:
    inserted = 0
    now = datetime.datetime.utcnow()
    for item in DEFAULT_ROOM_CATALOG:
        room_type = item['room_type']
        existing = db.query(RoomCatalog).filter(RoomCatalog.room_type == room_type).first()
        if existing:
            continue
        db.add(
            RoomCatalog(
                room_type=room_type,
                capacity=int(item['capacity']),
                price_eur=int(item['price_eur']),
                rooms_per_day=int(item['rooms_per_day']),
                is_active=bool(item.get('is_active', True)),
                updated_at=now,
            )
        )
        inserted += 1
    if inserted:
        db.commit()
    return inserted


def _catalog_map(db, include_inactive: bool = False) -> dict[str, dict]:
    query = db.query(RoomCatalog)
    if not include_inactive:
        query = query.filter(RoomCatalog.is_active == True)
    rows = query.all()
    return {
        r.room_type: {
            'room_type': r.room_type,
            'capacity': int(r.capacity),
            'price_eur': int(r.price_eur),
            'rooms_per_day': int(r.rooms_per_day),
            'is_active': bool(r.is_active),
            'updated_at': r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    }


def get_room_catalog(active_only: bool = False) -> list[dict]:
    with SessionLocal() as db:
        rows = db.query(RoomCatalog)
        if active_only:
            rows = rows.filter(RoomCatalog.is_active == True)
        rows = rows.order_by(RoomCatalog.room_type.asc()).all()
    return [
        {
            'room_type': r.room_type,
            'capacity': int(r.capacity),
            'price_eur': int(r.price_eur),
            'rooms_per_day': int(r.rooms_per_day),
            'is_active': bool(r.is_active),
            'updated_at': r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]


def upsert_room_config(payload: dict) -> dict:
    room_type = _normalize_room_type(payload.get('room_type'))
    if not room_type:
        raise ValueError('room_type is required')

    capacity = max(1, int(payload.get('capacity', 2)))
    price_eur = max(1, int(payload.get('price_eur', 80)))
    rooms_per_day = max(0, int(payload.get('rooms_per_day', 0)))
    is_active = bool(payload.get('is_active', True))
    now = datetime.datetime.utcnow()

    with SessionLocal() as db:
        existing = db.query(RoomCatalog).filter(RoomCatalog.room_type == room_type).first()
        if existing:
            existing.capacity = capacity
            existing.price_eur = price_eur
            existing.rooms_per_day = rooms_per_day
            existing.is_active = is_active
            existing.updated_at = now
        else:
            db.add(
                RoomCatalog(
                    room_type=room_type,
                    capacity=capacity,
                    price_eur=price_eur,
                    rooms_per_day=rooms_per_day,
                    is_active=is_active,
                    updated_at=now,
                )
            )
        db.commit()

    ensure_horizon(DEFAULT_HORIZON_DAYS)
    return {
        'room_type': room_type,
        'capacity': capacity,
        'price_eur': price_eur,
        'rooms_per_day': rooms_per_day,
        'is_active': is_active,
        'updated_at': now.isoformat(),
    }


def _ensure_seed_data(db, horizon_days: int = DEFAULT_HORIZON_DAYS) -> int:
    """Ensure a minimum available stock for each active room type/day."""
    catalog = _catalog_map(db)
    if not catalog:
        return 0

    today = datetime.date.today()
    inserted = 0

    for offset in range(horizon_days):
        day = today + datetime.timedelta(days=offset)
        for room_type, conf in catalog.items():
            target = max(0, int(conf['rooms_per_day']))
            available_count = (
                db.query(RoomStock)
                .filter(
                    RoomStock.room_type == room_type,
                    RoomStock.date == day,
                    RoomStock.available == True,
                )
                .count()
            )
            missing = max(0, target - available_count)
            for _ in range(missing):
                db.add(RoomStock(room_type=room_type, date=day, available=True))
                inserted += 1

    if inserted:
        db.commit()
    return inserted


def ensure_horizon(days: int = DEFAULT_HORIZON_DAYS) -> int:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        _ensure_catalog_seed(db)
        inserted = _ensure_seed_data(db, horizon_days=max(1, int(days)))
    return inserted


def init_db() -> int:
    return ensure_horizon(DEFAULT_HORIZON_DAYS)


def get_room_pricing(room_type: str | None) -> dict | None:
    normalized = _normalize_room_type(room_type)
    with SessionLocal() as db:
        row = (
            db.query(RoomCatalog)
            .filter(RoomCatalog.room_type == normalized, RoomCatalog.is_active == True)
            .first()
        )
        if not row:
            return None
        return {
            'room_type': row.room_type,
            'capacity': int(row.capacity),
            'price_eur': int(row.price_eur),
            'rooms_per_day': int(row.rooms_per_day),
            'is_active': bool(row.is_active),
        }


def check_availability_details(
    check_in: datetime.date,
    check_out: datetime.date,
    room_type: str = 'standard',
    guests: int | None = None,
) -> dict:
    normalized = _normalize_room_type(room_type)
    nights = max((check_out - check_in).days, 0)
    if nights <= 0:
        return {
            'room_type': normalized,
            'available': False,
            'nights': nights,
            'requested_guests': guests,
            'capacity': None,
            'price_per_night_eur': None,
            'total_price_eur': None,
            'min_available_rooms': 0,
            'alternatives': [],
            'reason': 'invalid_dates',
        }

    with SessionLocal() as db:
        catalog = _catalog_map(db)
        conf = catalog.get(normalized)
        if not conf:
            alternatives = [v for _, v in sorted(catalog.items())]
            return {
                'room_type': normalized,
                'available': False,
                'nights': nights,
                'requested_guests': guests,
                'capacity': None,
                'price_per_night_eur': None,
                'total_price_eur': None,
                'min_available_rooms': 0,
                'alternatives': alternatives,
                'reason': 'unknown_room_type',
            }

        capacity = int(conf['capacity'])
        if guests and guests > capacity:
            alternatives = [v for _, v in sorted(catalog.items()) if int(v['capacity']) >= int(guests)]
            return {
                'room_type': normalized,
                'available': False,
                'nights': nights,
                'requested_guests': guests,
                'capacity': capacity,
                'price_per_night_eur': int(conf['price_eur']),
                'total_price_eur': int(conf['price_eur']) * nights,
                'min_available_rooms': 0,
                'alternatives': alternatives,
                'reason': 'capacity_exceeded',
            }

        min_rooms = None
        current = check_in
        while current < check_out:
            count = (
                db.query(RoomStock)
                .filter(
                    RoomStock.room_type == normalized,
                    RoomStock.date == current,
                    RoomStock.available == True,
                )
                .count()
            )
            min_rooms = count if min_rooms is None else min(min_rooms, count)
            if count == 0:
                return {
                    'room_type': normalized,
                    'available': False,
                    'nights': nights,
                    'requested_guests': guests,
                    'capacity': capacity,
                    'price_per_night_eur': int(conf['price_eur']),
                    'total_price_eur': int(conf['price_eur']) * nights,
                    'min_available_rooms': 0,
                    'alternatives': [v for _, v in sorted(catalog.items()) if v['room_type'] != normalized],
                    'reason': 'no_stock',
                }
            current += datetime.timedelta(days=1)

        return {
            'room_type': normalized,
            'available': True,
            'nights': nights,
            'requested_guests': guests,
            'capacity': capacity,
            'price_per_night_eur': int(conf['price_eur']),
            'total_price_eur': int(conf['price_eur']) * nights,
            'min_available_rooms': int(min_rooms or 0),
            'alternatives': [v for _, v in sorted(catalog.items()) if v['room_type'] != normalized],
            'reason': 'ok',
        }


def check_availability(check_in: datetime.date, check_out: datetime.date, room_type: str = 'standard') -> bool:
    result = check_availability_details(check_in, check_out, room_type=room_type)
    return bool(result.get('available'))


def get_stock_summary(days: int = 14) -> list[tuple[datetime.date, dict[str, int]]]:
    today = datetime.date.today()
    end = today + datetime.timedelta(days=days)
    rows: list[tuple[datetime.date, str]] = []

    with SessionLocal() as db:
        q = (
            db.query(RoomStock.date, RoomStock.room_type)
            .filter(RoomStock.date >= today, RoomStock.date < end, RoomStock.available == True)
            .all()
        )
        rows.extend(q)
        catalog_keys = [k['room_type'] for k in get_room_catalog(active_only=True)]

    grouped: dict[datetime.date, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for day, room_type in rows:
        grouped[day][room_type] += 1

    output = []
    for i in range(days):
        day = today + datetime.timedelta(days=i)
        counts = {rt: grouped[day].get(rt, 0) for rt in catalog_keys}
        output.append((day, counts))
    return output


def get_month_availability(year: int, month: int) -> dict:
    first_day = datetime.date(year, month, 1)
    if month == 12:
        next_month = datetime.date(year + 1, 1, 1)
    else:
        next_month = datetime.date(year, month + 1, 1)

    with SessionLocal() as db:
        catalog = get_room_catalog(active_only=True)
        room_types = [c['room_type'] for c in catalog]
        rows = (
            db.query(RoomStock.date, RoomStock.room_type)
            .filter(
                RoomStock.date >= first_day,
                RoomStock.date < next_month,
                RoomStock.available == True,
            )
            .all()
        )

    grouped: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for day, room_type in rows:
        grouped[day.isoformat()][room_type] += 1

    day = first_day
    items = []
    while day < next_month:
        key = day.isoformat()
        counts = {rt: grouped[key].get(rt, 0) for rt in room_types}
        items.append({'date': key, 'availability': counts})
        day += datetime.timedelta(days=1)

    return {
        'year': year,
        'month': month,
        'room_types': room_types,
        'items': items,
    }


def print_stock_summary(days: int = 14) -> None:
    summary = get_stock_summary(days=days)
    room_types = [c['room_type'] for c in get_room_catalog(active_only=True)]
    header = 'Date       | ' + ' | '.join(f'{rt[:10]:>10}' for rt in room_types)
    print(header)
    print('-' * len(header))
    for day, counts in summary:
        values = ' | '.join(f"{counts.get(rt, 0):>10}" for rt in room_types)
        print(f"{day.isoformat()} | {values}")


def _parse_days_arg(argv: list[str], default: int) -> int:
    try:
        return int(argv[2]) if len(argv) >= 3 else default
    except ValueError:
        return default


if __name__ == '__main__':
    # Usage:
    #   python src/db/sql_stock.py
    #   python src/db/sql_stock.py summary 30
    #   python src/db/sql_stock.py seed 365
    cmd = sys.argv[1].strip().lower() if len(sys.argv) >= 2 else 'init'

    if cmd in {'init', 'seed'}:
        days = _parse_days_arg(sys.argv, DEFAULT_HORIZON_DAYS)
        inserted = ensure_horizon(days=days)
        print(f'Stock ensured for {days} days. Inserted rows: {inserted}')
        print_stock_summary(days=min(14, days))
    elif cmd == 'summary':
        days = _parse_days_arg(sys.argv, 14)
        print_stock_summary(days=days)
    else:
        print('Unknown command. Use: init|seed [days] or summary [days]')
