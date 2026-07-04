"""
Роутер: транзакции
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime

from app.database import get_db, WalletModel, TransactionModel
from app.schemas import TransactionSend, TransactionEstimate, TransactionResponse
from app.web3_service import (
    build_transaction, sign_and_send_transaction,
    get_transaction_receipt, get_transaction_info, get_web3
)
from app.crypto_utils import decrypt_private_key
from app.config import settings

router = APIRouter()


@router.post("/send", response_model=TransactionResponse, summary="Отправить транзакцию")
async def send_transaction(data: TransactionSend, db: AsyncSession = Depends(get_db)):
    """
    Подписывает и отправляет транзакцию в сеть.

    - Отправитель должен быть сохранён в базе данных
    - Для тестов используйте `goerli` или `bsc_testnet`
    - ⚠️ В mainnet расходуются реальные средства!
    """
    # Получаем кошелёк из БД
    result = await db.execute(
        select(WalletModel).where(
            WalletModel.address == data.from_address,
            WalletModel.is_active == True
        )
    )
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(404, f"Кошелёк {data.from_address} не найден в базе данных")

    # Расшифровываем приватный ключ
    private_key = decrypt_private_key(wallet.encrypted_private_key)

    # Строим транзакцию
    try:
        tx = build_transaction(
            from_address=data.from_address,
            to_address=data.to_address,
            value_eth=data.value_eth,
            network=data.network,
            gas_limit=data.gas_limit,
            gas_price_gwei=data.gas_price_gwei,
        )
    except Exception as e:
        raise HTTPException(400, f"Ошибка построения транзакции: {str(e)}")

    # Отправляем
    try:
        result_tx = sign_and_send_transaction(tx, private_key, data.network)
    except Exception as e:
        err_str = str(e)
        if "insufficient funds" in err_str.lower():
            raise HTTPException(400, "Недостаточно средств для транзакции и оплаты газа")
        raise HTTPException(400, f"Ошибка отправки транзакции: {err_str}")

    # Сохраняем в БД
    db_tx = TransactionModel(
        tx_hash=result_tx["tx_hash"],
        from_address=result_tx["from"],
        to_address=result_tx["to"],
        value_wei=result_tx["value_wei"],
        value_eth=result_tx["value_eth"],
        gas_price_gwei=result_tx["gas_price_gwei"],
        network=data.network,
        status="pending",
        note=data.note,
    )
    db.add(db_tx)
    await db.commit()
    await db.refresh(db_tx)
    return db_tx


@router.post("/estimate", summary="Оценить стоимость транзакции")
async def estimate_transaction(data: TransactionEstimate):
    """
    Рассчитывает примерную стоимость транзакции (газ × цена) без отправки.
    """
    try:
        w3 = get_web3(data.network)
        net_info = settings.NETWORKS[data.network]

        from web3 import Web3
        from_checksum = Web3.to_checksum_address(data.from_address)
        to_checksum = Web3.to_checksum_address(data.to_address)
        value_wei = w3.to_wei(data.value_eth, "ether")

        gas_estimate = w3.eth.estimate_gas({
            "from": from_checksum,
            "to": to_checksum,
            "value": value_wei,
        })
        gas_price = w3.eth.gas_price
        fee_wei = gas_estimate * gas_price
        fee_eth = float(w3.from_wei(fee_wei, "ether"))

        return {
            "gas_limit": gas_estimate,
            "gas_price_gwei": float(w3.from_wei(gas_price, "gwei")),
            "estimated_fee": fee_eth,
            "estimated_fee_usd_approx": None,  # можно добавить через CoinGecko API
            "symbol": net_info["symbol"],
            "total_cost": data.value_eth + fee_eth,
        }
    except Exception as e:
        raise HTTPException(400, f"Ошибка оценки: {str(e)}")


@router.get("/status/{tx_hash}", summary="Статус транзакции")
async def transaction_status(tx_hash: str, network: str = "goerli", db: AsyncSession = Depends(get_db)):
    """
    Проверяет статус транзакции в блокчейне и обновляет БД.
    """
    receipt = get_transaction_receipt(tx_hash, network)

    # Обновляем статус в БД если есть
    result = await db.execute(select(TransactionModel).where(TransactionModel.tx_hash == tx_hash))
    db_tx = result.scalar_one_or_none()

    if receipt and db_tx:
        db_tx.status = receipt["status"]
        db_tx.block_number = receipt["block_number"]
        db_tx.gas_used = receipt["gas_used"]
        db_tx.confirmed_at = datetime.utcnow()
        await db.commit()

    if receipt:
        return {**receipt, "source": "blockchain"}
    elif db_tx:
        return {"tx_hash": tx_hash, "status": db_tx.status, "source": "database"}
    else:
        return {"tx_hash": tx_hash, "status": "unknown", "source": "not_found"}


@router.get("/info/{tx_hash}", summary="Информация о транзакции")
async def transaction_info(tx_hash: str, network: str = "goerli"):
    """Получает полную информацию о транзакции из блокчейна."""
    info = get_transaction_info(tx_hash, network)
    if not info:
        raise HTTPException(404, "Транзакция не найдена в сети")
    return info


@router.get("/history/{address}", response_model=List[TransactionResponse], summary="История транзакций")
async def transaction_history(
    address: str,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Возвращает историю транзакций адреса из локальной БД."""
    from web3 import Web3
    if not Web3.is_address(address):
        raise HTTPException(400, "Невалидный адрес")
    checksum = Web3.to_checksum_address(address)

    result = await db.execute(
        select(TransactionModel)
        .where(
            (TransactionModel.from_address == checksum) |
            (TransactionModel.to_address == checksum)
        )
        .order_by(TransactionModel.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()
