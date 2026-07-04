"""
База данных — SQLAlchemy async + SQLite
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, Float, Boolean, Text
from datetime import datetime
from app.config import settings


engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class WalletModel(Base):
    """Модель кошелька"""
    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str] = mapped_column(String(42), unique=True, nullable=False, index=True)
    # Зашифрованный приватный ключ (Fernet symmetric encryption)
    encrypted_private_key: Mapped[str] = mapped_column(Text, nullable=False)
    # Публичный ключ — для просмотра, не секретный
    public_key: Mapped[str] = mapped_column(Text, nullable=True)
    mnemonic_hint: Mapped[str] = mapped_column(String(50), nullable=True)  # первые 2 слова
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    label: Mapped[str] = mapped_column(String(200), nullable=True)


class TransactionModel(Base):
    """Модель транзакции"""
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tx_hash: Mapped[str] = mapped_column(String(66), unique=True, nullable=False, index=True)
    from_address: Mapped[str] = mapped_column(String(42), nullable=False)
    to_address: Mapped[str] = mapped_column(String(42), nullable=False)
    value_wei: Mapped[str] = mapped_column(String(50), nullable=False)   # хранить как строку — BigInt
    value_eth: Mapped[float] = mapped_column(Float, nullable=False)
    gas_used: Mapped[int] = mapped_column(nullable=True)
    gas_price_gwei: Mapped[float] = mapped_column(Float, nullable=True)
    network: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")   # pending / success / failed
    block_number: Mapped[int] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    note: Mapped[str] = mapped_column(String(500), nullable=True)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
