"""
Роутер: информация о сетях
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict

from app.web3_service import get_network_info
from app.config import settings

router = APIRouter()


@router.get("/", summary="Список поддерживаемых сетей")
async def list_networks() -> Dict:
    """Возвращает список всех поддерживаемых блокчейн-сетей и их параметры."""
    return {
        "networks": [
            {
                "key": key,
                "name": info["name"],
                "chain_id": info["chain_id"],
                "symbol": info["symbol"],
                "explorer": info["explorer"],
            }
            for key, info in settings.NETWORKS.items()
        ],
        "default": settings.DEFAULT_NETWORK,
    }


@router.get("/{network_key}", summary="Состояние сети")
async def network_status(network_key: str):
    """
    Возвращает текущее состояние сети: подключение, номер блока, цену газа.
    """
    if network_key not in settings.NETWORKS:
        raise HTTPException(404, f"Сеть '{network_key}' не найдена")
    return get_network_info(network_key)


@router.get("/gas/{network_key}", summary="Цена газа")
async def gas_price(network_key: str):
    """Возвращает текущую цену газа в сети."""
    if network_key not in settings.NETWORKS:
        raise HTTPException(404, f"Сеть '{network_key}' не найдена")
    from app.web3_service import get_web3
    w3 = get_web3(network_key)
    gwei = float(w3.from_wei(w3.eth.gas_price, "gwei"))
    return {
        "network": network_key,
        "gas_price_wei": w3.eth.gas_price,
        "gas_price_gwei": gwei,
        "slow_gwei": round(gwei * 0.8, 2),
        "fast_gwei": round(gwei * 1.5, 2),
    }
