"""
Роутер: управление кошельками
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db, WalletModel
from app.schemas import (
    WalletCreate, WalletFromMnemonic, WalletFromPrivateKey,
    WalletResponse, WalletDetailResponse
)
from app.web3_service import (
    create_wallet, create_wallet_from_mnemonic,
    import_wallet_from_private_key, generate_new_mnemonic
)
from app.crypto_utils import encrypt_private_key, decrypt_private_key

router = APIRouter()


@router.post("/create", response_model=WalletDetailResponse, summary="Создать новый кошелёк")
async def create_new_wallet(data: WalletCreate, db: AsyncSession = Depends(get_db)):
    """
    Генерирует новую пару ключей. Приватный ключ шифруется и сохраняется локально.

    ⚠️ **Сохраните private_key и mnemonic** — они больше не будут показаны!
    """
    mnemonic = generate_new_mnemonic(12)
    wallet_data = create_wallet_from_mnemonic(mnemonic)

    # Проверка дубликата
    existing = await db.execute(select(WalletModel).where(WalletModel.address == wallet_data["address"]))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Кошелёк с таким адресом уже существует")

    wallet = WalletModel(
        name=data.name,
        address=wallet_data["address"],
        encrypted_private_key=encrypt_private_key(wallet_data["private_key"]),
        public_key=wallet_data["public_key"],
        mnemonic_hint=" ".join(mnemonic.split()[:2]) + " ...",
        label=data.label,
    )
    db.add(wallet)
    await db.commit()
    await db.refresh(wallet)

    return WalletDetailResponse(
        id=wallet.id,
        name=wallet.name,
        address=wallet.address,
        label=wallet.label,
        created_at=wallet.created_at,
        is_active=wallet.is_active,
        private_key=wallet_data["private_key"],
        mnemonic=mnemonic,
        public_key=wallet_data["public_key"],
    )


@router.post("/import/mnemonic", response_model=WalletDetailResponse, summary="Импорт через мнемонику")
async def import_from_mnemonic(data: WalletFromMnemonic, db: AsyncSession = Depends(get_db)):
    """Восстанавливает кошелёк из мнемонической фразы (BIP-44, путь m/44'/60'/0'/0/{index})."""
    try:
        wallet_data = create_wallet_from_mnemonic(data.mnemonic, data.account_index)
    except Exception as e:
        raise HTTPException(400, f"Ошибка импорта: {str(e)}")

    existing = await db.execute(select(WalletModel).where(WalletModel.address == wallet_data["address"]))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Кошелёк с таким адресом уже существует")

    wallet = WalletModel(
        name=data.name,
        address=wallet_data["address"],
        encrypted_private_key=encrypt_private_key(wallet_data["private_key"]),
        public_key=wallet_data.get("public_key"),
        mnemonic_hint=" ".join(data.mnemonic.split()[:2]) + " ...",
        label=data.label,
    )
    db.add(wallet)
    await db.commit()
    await db.refresh(wallet)

    return WalletDetailResponse(
        id=wallet.id, name=wallet.name, address=wallet.address,
        label=wallet.label, created_at=wallet.created_at, is_active=wallet.is_active,
        private_key=wallet_data["private_key"],
    )


@router.post("/import/privatekey", response_model=WalletDetailResponse, summary="Импорт по приватному ключу")
async def import_from_private_key(data: WalletFromPrivateKey, db: AsyncSession = Depends(get_db)):
    """Импортирует кошелёк по приватному ключу в hex-формате."""
    try:
        wallet_data = import_wallet_from_private_key(data.private_key)
    except Exception as e:
        raise HTTPException(400, f"Невалидный приватный ключ: {str(e)}")

    existing = await db.execute(select(WalletModel).where(WalletModel.address == wallet_data["address"]))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Кошелёк с таким адресом уже существует")

    wallet = WalletModel(
        name=data.name,
        address=wallet_data["address"],
        encrypted_private_key=encrypt_private_key(wallet_data["private_key"]),
        public_key=wallet_data.get("public_key"),
        label=data.label,
    )
    db.add(wallet)
    await db.commit()
    await db.refresh(wallet)

    return WalletDetailResponse(
        id=wallet.id, name=wallet.name, address=wallet.address,
        label=wallet.label, created_at=wallet.created_at, is_active=wallet.is_active,
    )


@router.get("/", response_model=List[WalletResponse], summary="Список кошельков")
async def list_wallets(db: AsyncSession = Depends(get_db)):
    """Возвращает все активные кошельки (без приватных ключей)."""
    result = await db.execute(select(WalletModel).where(WalletModel.is_active == True))
    return result.scalars().all()


@router.get("/{wallet_id}", response_model=WalletResponse, summary="Информация о кошельке")
async def get_wallet(wallet_id: int, db: AsyncSession = Depends(get_db)):
    wallet = await db.get(WalletModel, wallet_id)
    if not wallet:
        raise HTTPException(404, "Кошелёк не найден")
    return wallet


@router.delete("/{wallet_id}", summary="Удалить кошелёк")
async def delete_wallet(wallet_id: int, db: AsyncSession = Depends(get_db)):
    """Помечает кошелёк как неактивный (soft delete)."""
    wallet = await db.get(WalletModel, wallet_id)
    if not wallet:
        raise HTTPException(404, "Кошелёк не найден")
    wallet.is_active = False
    await db.commit()
    return {"message": f"Кошелёк {wallet.address} деактивирован"}
