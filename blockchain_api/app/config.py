"""
Конфигурация приложения
"""
from pydantic_settings import BaseSettings
from typing import Dict


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Blockchain Wallet API"
    SECRET_KEY: str = "super-secret-key-change-in-production-32chars"

    # Ethereum RPC endpoints (публичные узлы — замените на свои для production)
    NETWORKS: Dict[str, Dict] = {
        "ethereum": {
            "name": "Ethereum Mainnet",
            "rpc_url": "https://eth.llamarpc.com",
            "chain_id": 1,
            "symbol": "ETH",
            "explorer": "https://etherscan.io",
            "decimals": 18,
        },
        "goerli": {
            "name": "Goerli Testnet",
            "rpc_url": "https://ethereum-goerli.publicnode.com",
            "chain_id": 5,
            "symbol": "ETH",
            "explorer": "https://goerli.etherscan.io",
            "decimals": 18,
        },
        "bsc": {
            "name": "BNB Smart Chain",
            "rpc_url": "https://bsc-dataseed1.binance.org/",
            "chain_id": 56,
            "symbol": "BNB",
            "explorer": "https://bscscan.com",
            "decimals": 18,
        },
        "bsc_testnet": {
            "name": "BSC Testnet",
            "rpc_url": "https://data-seed-prebsc-1-s1.binance.org:8545/",
            "chain_id": 97,
            "symbol": "tBNB",
            "explorer": "https://testnet.bscscan.com",
            "decimals": 18,
        },
    }

    DEFAULT_NETWORK: str = "goerli"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./wallets.db"

    class Config:
        env_file = ".env"


settings = Settings()
