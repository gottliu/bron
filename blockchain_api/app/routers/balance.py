"""
Роутер: баланс
"""
from fastapi import APIRouter, HTTPException
from typing import List
from web3 import Web3

from app.schemas import BalanceResponse, MultiBalanceRequest
from app.web3_service import get_balance, validate_address
from app.config import settings

router = APIRouter()


@router.get("/{address}", response_model=BalanceResponse, summary="Баланс адреса")
async def get_address_balance(address: str, network: str = "goerli"):
    """
    Возвращает актуальный баланс адреса в указанной сети.

    Поддерживаемые сети: `ethereum`, `goerli`, `bsc`, `bsc_testnet`
    """
    if not validate_address(address):
        raise HTTPException(400, f"Невалидный адрес: {address}")
    if network not in settings.NETWORKS:
        raise HTTPException(400, f"Неизвестная сеть. Доступные: {list(settings.NETWORKS.keys())}")
    try:
        return get_balance(address, network)
    except Exception as e:
        raise HTTPException(503, f"Ошибка подключения к узлу: {str(e)}")


@router.post("/multi", summary="Баланс нескольких адресов")
async def get_multi_balance(data: MultiBalanceRequest):
    """Получает балансы сразу нескольких адресов в одной сети."""
    results = []
    errors = []
    for addr in data.addresses:
        if not validate_address(addr):
            errors.append({"address": addr, "error": "Невалидный адрес"})
            continue
        try:
            bal = get_balance(addr, data.network)
            results.append(bal)
        except Exception as e:
            errors.append({"address": addr, "error": str(e)})

    return {"results": results, "errors": errors, "count": len(results)}
