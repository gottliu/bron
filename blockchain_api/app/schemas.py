"""
Pydantic-схемы — валидация входных/выходных данных API
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from web3 import Web3


# ──────────────────────────────────────────────
# Кошельки
# ──────────────────────────────────────────────

class WalletCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, example="Мой кошелёк")
    label: Optional[str] = Field(None, max_length=200, example="Для DeFi")


class WalletFromMnemonic(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    mnemonic: str = Field(..., description="12 или 24 слова через пробел")
    account_index: int = Field(0, ge=0, le=100)
    label: Optional[str] = None

    @field_validator("mnemonic")
    @classmethod
    def validate_mnemonic(cls, v):
        words = v.strip().split()
        if len(words) not in (12, 24):
            raise ValueError("Мнемоническая фраза должна содержать 12 или 24 слова")
        return v.strip()


class WalletFromPrivateKey(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    private_key: str = Field(..., description="Приватный ключ в hex (с 0x или без)")
    label: Optional[str] = None

    @field_validator("private_key")
    @classmethod
    def validate_key(cls, v):
        v = v.strip()
        if not v.startswith("0x"):
            v = "0x" + v
        if len(v) != 66:
            raise ValueError("Приватный ключ должен быть 32 байта (64 hex символа)")
        return v


class WalletResponse(BaseModel):
    id: int
    name: str
    address: str
    label: Optional[str]
    created_at: datetime
    is_active: bool

    model_config = {"from_attributes": True}


class WalletDetailResponse(WalletResponse):
    """Расширенный ответ — только для создания (включает приватный ключ!)"""
    private_key: Optional[str] = Field(None, description="Показывается ТОЛЬКО при создании!")
    mnemonic: Optional[str] = Field(None, description="Сохраните надёжно!")
    public_key: Optional[str] = None


# ──────────────────────────────────────────────
# Транзакции
# ──────────────────────────────────────────────

class TransactionSend(BaseModel):
    from_address: str = Field(..., description="Адрес отправителя (должен быть в вашей БД)")
    to_address: str = Field(..., description="Адрес получателя")
    value_eth: float = Field(..., gt=0, description="Сумма в ETH/BNB")
    network: str = Field("goerli", description="Сеть: ethereum, goerli, bsc, bsc_testnet")
    gas_limit: Optional[int] = Field(None, ge=21000)
    gas_price_gwei: Optional[float] = Field(None, gt=0)
    note: Optional[str] = Field(None, max_length=500)

    @field_validator("from_address", "to_address")
    @classmethod
    def validate_address(cls, v):
        if not Web3.is_address(v):
            raise ValueError(f"Невалидный Ethereum-адрес: {v}")
        return Web3.to_checksum_address(v)

    @field_validator("network")
    @classmethod
    def validate_network(cls, v):
        allowed = ["ethereum", "goerli", "bsc", "bsc_testnet"]
        if v not in allowed:
            raise ValueError(f"Допустимые сети: {allowed}")
        return v


class TransactionEstimate(BaseModel):
    from_address: str
    to_address: str
    value_eth: float
    network: str = "goerli"


class TransactionResponse(BaseModel):
    id: int
    tx_hash: str
    from_address: str
    to_address: str
    value_eth: float
    gas_used: Optional[int]
    gas_price_gwei: Optional[float]
    network: str
    status: str
    block_number: Optional[int]
    created_at: datetime
    note: Optional[str]

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Баланс
# ──────────────────────────────────────────────

class BalanceResponse(BaseModel):
    address: str
    balance_wei: str
    balance: float
    symbol: str
    network: str
    network_key: str


class MultiBalanceRequest(BaseModel):
    addresses: List[str] = Field(..., min_length=1, max_length=20)
    network: str = "goerli"


# ──────────────────────────────────────────────
# Сеть
# ──────────────────────────────────────────────

class NetworkInfoResponse(BaseModel):
    network_key: str
    name: str
    chain_id: int
    symbol: str
    explorer: str
    connected: bool
    block_number: Optional[int] = None
    gas_price_gwei: Optional[float] = None
