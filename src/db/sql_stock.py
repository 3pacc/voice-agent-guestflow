from sqlalchemy import create_engine, Column, Integer, String, Date, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from src.config.settings import settings
import datetime

Base = declarative_base()

class RoomStock(Base):
    __tablename__ = 'room_stock'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    room_type = Column(String(50), nullable=False)
    date = Column(Date, nullable=False)
    available = Column(Boolean, default=True)

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Seed data
    with SessionLocal() as db:
        if db.query(RoomStock).count() == 0:
            today = datetime.date.today()
            for i in range(10):
                day = today + datetime.timedelta(days=i)
                # 5 standard rooms per day
                for _ in range(5):
                    db.add(RoomStock(room_type="standard", date=day, available=True))
                # 2 suites per day
                for _ in range(2):
                    db.add(RoomStock(room_type="suite", date=day, available=True))
            db.commit()


def check_availability(
    check_in: datetime.date,
    check_out: datetime.date,
    room_type: str = "standard"
) -> bool:
    """
    Returns True if at least one room of the given type is available
    for every night between check_in (inclusive) and check_out (exclusive).
    """
    with SessionLocal() as db:
        current = check_in
        while current < check_out:
            count = db.query(RoomStock).filter(
                RoomStock.room_type == room_type,
                RoomStock.date == current,
                RoomStock.available == True,
            ).count()
            if count == 0:
                return False
            current += datetime.timedelta(days=1)
    return True


# Call this on app startup
if __name__ == "__main__":
    init_db()
    print("Database initialized and seeded.")
