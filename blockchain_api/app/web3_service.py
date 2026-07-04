"""
Web3 сервис — взаимодействие с блокчейном через Web3.py
"""
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
from eth_account.hdaccount import generate_mnemonic
import secrets
from typing import Optional, Dict, Tuple
from app.config import settings


# Включаем поддержку HD-кошельков (BIP-44)
Account.enable_unaudited_hdwallet_features()


def get_web3(network: str = None) -> Web3:
    """Возвращает подключённый экземпляр Web3 для указанной сети."""
    net = network or settings.DEFAULT_NETWORK
    if net not in settings.NETWORKS:
        raise ValueError(f"Неизвестная сеть: {net}. Доступные: {list(settings.NETWORKS.keys())}")

    rpc_url = settings.NETWORKS[net]["rpc_url"]
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 30}))

    # BSC и другие PoA-сети требуют middleware
    if net in ("bsc", "bsc_testnet", "goerli"):
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    return w3


# ──────────────────────────────────────────────
# Создание кошельков
# ──────────────────────────────────────────────

def create_wallet() -> Dict:
    """
    Создаёт новый случайный кошелёк.
    Возвращает: address, private_key, public_key.
    """
    account = Account.create(secrets.token_bytes(32))
    return {
        "address": account.address,
        "private_key": "0x" + account.key.hex(),
        "public_key": "0x" + account._key_obj.public_key.to_hex(),
    }


def create_wallet_from_mnemonic(mnemonic: str, account_index: int = 0) -> Dict:
    """
    Восстанавливает кошелёк из мнемонической фразы (BIP-44).
    derivation path: m/44'/60'/0'/0/{account_index}
    """
    account = Account.from_mnemonic(
        mnemonic,
        account_path=f"m/44'/60'/0'/0/{account_index}"
    )
    return {
        "address": account.address,
        "private_key": account.key.hex(),
        "public_key": "0x" + account._key_obj.public_key.to_hex(),
        "mnemonic": mnemonic,
    }


def generate_new_mnemonic(num_words: int = 12) -> str:
    """Генерирует новую мнемоническую фразу (12 или 24 слова)."""
    strength = 128 if num_words == 12 else 256
    return generate_mnemonic(num_words=num_words, lang="english")


def import_wallet_from_private_key(private_key: str) -> Dict:
    """Импортирует кошелёк из приватного ключа."""
    if not private_key.startswith("0x"):
        private_key = "0x" + private_key
    # Дополняем нулями слева до 32 байт если нужно
    hex_part = private_key[2:].zfill(64)
    private_key = "0x" + hex_part
    account = Account.from_key(private_key)
    return {
        "address": account.address,
        "private_key": "0x" + account.key.hex(),
        "public_key": "0x" + account._key_obj.public_key.to_hex(),
    }


# ──────────────────────────────────────────────
# Баланс
# ──────────────────────────────────────────────

def get_balance(address: str, network: str = None) -> Dict:
    """Возвращает баланс адреса в Wei и в ETH/BNB."""
    w3 = get_web3(network)
    net_key = network or settings.DEFAULT_NETWORK
    net_info = settings.NETWORKS[net_key]

    checksum_address = Web3.to_checksum_address(address)
    balance_wei = w3.eth.get_balance(checksum_address)
    balance_native = w3.from_wei(balance_wei, "ether")

    return {
        "address": checksum_address,
        "balance_wei": str(balance_wei),
        "balance": float(balance_native),
        "symbol": net_info["symbol"],
        "network": net_info["name"],
        "network_key": net_key,
    }


# ──────────────────────────────────────────────
# Транзакции
# ──────────────────────────────────────────────

def build_transaction(
    from_address: str,
    to_address: str,
    value_eth: float,
    network: str = None,
    gas_limit: Optional[int] = None,
    gas_price_gwei: Optional[float] = None,
    nonce: Optional[int] = None,
    data: bytes = b"",
) -> Dict:
    """
    Формирует сырую транзакцию (не отправляет).
    Возвращает параметры tx для подписи.
    """
    w3 = get_web3(network)
    net_key = network or settings.DEFAULT_NETWORK
    net_info = settings.NETWORKS[net_key]

    from_checksum = Web3.to_checksum_address(from_address)
    to_checksum = Web3.to_checksum_address(to_address)

    value_wei = w3.to_wei(value_eth, "ether")

    # Получаем актуальную цену газа, если не указана
    if gas_price_gwei is None:
        gas_price = w3.eth.gas_price
    else:
        gas_price = w3.to_wei(gas_price_gwei, "gwei")

    # Оцениваем лимит газа
    if gas_limit is None:
        try:
            gas_limit = w3.eth.estimate_gas({
                "from": from_checksum,
                "to": to_checksum,
                "value": value_wei,
            })
            gas_limit = int(gas_limit * 1.2)  # +20% запас
        except Exception:
            gas_limit = 21000  # стандартный ETH transfer

    # Nonce
    if nonce is None:
        nonce = w3.eth.get_transaction_count(from_checksum)

    tx = {
        "chainId": net_info["chain_id"],
        "from": from_checksum,
        "to": to_checksum,
        "value": value_wei,
        "gas": gas_limit,
        "gasPrice": gas_price,
        "nonce": nonce,
        "data": data,
    }
    return tx


def sign_and_send_transaction(
    tx: Dict,
    private_key: str,
    network: str = None,
) -> Dict:
    """
    Подписывает и отправляет транзакцию в сеть.
    Возвращает tx_hash и параметры транзакции.
    """
    w3 = get_web3(network)

    signed = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    tx_hash_hex = tx_hash.hex()

    return {
        "tx_hash": tx_hash_hex,
        "from": tx["from"],
        "to": tx["to"],
        "value_wei": str(tx["value"]),
        "value_eth": float(w3.from_wei(tx["value"], "ether")),
        "gas": tx["gas"],
        "gas_price_gwei": float(w3.from_wei(tx["gasPrice"], "gwei")),
        "nonce": tx["nonce"],
        "network": network or settings.DEFAULT_NETWORK,
    }


def get_transaction_receipt(tx_hash: str, network: str = None) -> Optional[Dict]:
    """Получает квитанцию транзакции (None если ещё pending)."""
    w3 = get_web3(network)
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        if receipt is None:
            return None
        return {
            "tx_hash": tx_hash,
            "status": "success" if receipt["status"] == 1 else "failed",
            "block_number": receipt["blockNumber"],
            "gas_used": receipt["gasUsed"],
            "from": receipt["from"],
            "to": receipt["to"],
        }
    except Exception:
        return None


def get_transaction_info(tx_hash: str, network: str = None) -> Optional[Dict]:
    """Получает информацию о транзакции по хешу."""
    w3 = get_web3(network)
    try:
        tx = w3.eth.get_transaction(tx_hash)
        if tx is None:
            return None
        return {
            "tx_hash": tx_hash,
            "from": tx["from"],
            "to": tx["to"],
            "value_wei": str(tx["value"]),
            "value_eth": float(w3.from_wei(tx["value"], "ether")),
            "gas": tx["gas"],
            "gas_price_gwei": float(w3.from_wei(tx["gasPrice"], "gwei")),
            "nonce": tx["nonce"],
            "block_number": tx.get("blockNumber"),
        }
    except Exception:
        return None


# ──────────────────────────────────────────────
# Информация о сети
# ──────────────────────────────────────────────

def get_network_info(network: str = None) -> Dict:
    """Возвращает информацию о состоянии сети."""
    net_key = network or settings.DEFAULT_NETWORK
    w3 = get_web3(net_key)
    net_info = settings.NETWORKS[net_key]

    connected = w3.is_connected()
    result = {
        "network_key": net_key,
        "name": net_info["name"],
        "chain_id": net_info["chain_id"],
        "symbol": net_info["symbol"],
        "explorer": net_info["explorer"],
        "connected": connected,
    }

    if connected:
        try:
            result["block_number"] = w3.eth.block_number
            result["gas_price_gwei"] = float(w3.from_wei(w3.eth.gas_price, "gwei"))
        except Exception:
            result["block_number"] = None
            result["gas_price_gwei"] = None

    return result


def validate_address(address: str) -> bool:
    """Проверяет валидность Ethereum-адреса."""
    return Web3.is_address(address)
