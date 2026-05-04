import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, DateTime, ForeignKey, Numeric, Integer, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("strategies.id"), nullable=True)
    signal_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("signals.id"), nullable=True)
    instrument: Mapped[str] = mapped_column(String(50), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)   # 'long' | 'short'
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    stop_loss: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    target: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    # open | closed | cancelled | killed
    wallet_type: Mapped[str] = mapped_column(String(10), nullable=False)
    broker_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    slippage: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    instrument: Mapped[str] = mapped_column(String(50), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    entry: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    stop_loss: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    target: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    rr_ratio: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    confidence_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    block_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
