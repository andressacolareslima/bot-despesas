from datetime import date, datetime
from zoneinfo import ZoneInfo
from sqlalchemy import Column, Integer, String, Numeric, Date, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/expenses")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
LOCAL_TIMEZONE = ZoneInfo("America/Sao_Paulo")

class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    sender = Column(String, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    expense_date = Column(
        Date,
        nullable=False,
        default=lambda: datetime.now(LOCAL_TIMEZONE).date(),
    )

class ProcessedMessage(Base):
    __tablename__ = "processed_messages"

    message_id = Column(String, primary_key=True)

Base.metadata.create_all(bind=engine)