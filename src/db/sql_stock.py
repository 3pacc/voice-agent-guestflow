import datetime
import sys
from collections import defaultdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import Boolean, Column, Date, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config.settings import settings

Base = declarative_base()


class RoomStock(Base):
    __tablename__ = 'room_stock'

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_type = Column(String(50), nullable=False)
    date = Column(Date, nullable=False)
    available = Column(Boolean, default=True)


engine = create_engine(settings.database_url, connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

DEFAULT_ROOMS_PER_DAY = {
    'standard': 20,
    'deluxe': 12,
    'suite': 8,
    'familiale': 10,
}
DEFAULT_HORIZON_DAYS = 180


def _normalize_room_type(room_type: str | None) -> str:
    value = (room_type or 'standard').strip().lower()
    if value in {'family', 'family room'}:
        return 'familiale'
    if value in {'de luxe'}:
        return 'deluxe'
    return value


def _ensure_seed_data(
    db,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
    rooms_per_day: dict[str, int] | None = None,
) -> int:
    """Ensure a minimum available stock for each room type/day. Returns inserted rows."""
    rooms = rooms_per_day or DEFAULT_ROOMS_PER_DAY
    today = datetime.date.today()
    inserted = 0

    for offset in range(horizon_days):
        day = today + datetime.timedelta(days=offset)
        for room_type, target in rooms.items():
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


def init_db() -> int:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        inserted = _ensure_seed_data(db)
    return inserted


def check_availability(
    check_in: datetime.date,
    check_out: datetime.date,
    room_type: str = 'standard',
) -> bool:
    """
    Returns True if at least one room of the given type is available
    for every night between check_in (inclusive) and check_out (exclusive).
    """
    normalized = _normalize_room_type(room_type)
    with SessionLocal() as db:
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
            if count == 0:
                return False
            current += datetime.timedelta(days=1)
    return True


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

    grouped: dict[datetime.date, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for day, room_type in rows:
        grouped[day][room_type] += 1

    output = []
    for i in range(days):
        day = today + datetime.timedelta(days=i)
        counts = {rt: grouped[day].get(rt, 0) for rt in DEFAULT_ROOMS_PER_DAY.keys()}
        output.append((day, counts))
    return output


def print_stock_summary(days: int = 14) -> None:
    summary = get_stock_summary(days=days)
    print('Date       | standard | deluxe | suite | familiale')
    print('-----------+----------+--------+-------+----------')
    for day, counts in summary:
        print(
            f"{day.isoformat()} |"
            f" {counts['standard']:>8} |"
            f" {counts['deluxe']:>6} |"
            f" {counts['suite']:>5} |"
            f" {counts['familiale']:>8}"
        )


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
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            inserted = _ensure_seed_data(db, horizon_days=days)
        print(f'Stock ensured for {days} days. Inserted rows: {inserted}')
        print_stock_summary(days=min(14, days))
    elif cmd == 'summary':
        days = _parse_days_arg(sys.argv, 14)
        print_stock_summary(days=days)
    else:
        print('Unknown command. Use: init|seed [days] or summary [days]')
