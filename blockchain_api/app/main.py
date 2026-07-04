"""
Blockchain Wallet API
Курсовая работа: API для работы с блокчейн-кошельками
Web3.py + FastAPI | Ethereum & BSC
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import uvicorn

from app.routers import wallets, transactions, balance, network
from app.database import init_db
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    await init_db()
    yield


app = FastAPI(
    title="Blockchain Wallet API",
    description="""
## 🔗 API для работы с блокчейн-кошельками

**Технологии:** Web3.py + FastAPI + SQLite

### Возможности:
- 🔑 Создание и управление HD-кошельками (BIP-44)
- 💸 Отправка ETH / BNB транзакций
- 📊 Получение баланса и истории транзакций
- 🌐 Поддержка Ethereum Mainnet, Goerli, BSC, BSC Testnet
- 🔒 Локальное хранение зашифрованных ключей
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(wallets.router, prefix="/api/v1/wallets", tags=["Кошельки"])
app.include_router(transactions.router, prefix="/api/v1/transactions", tags=["Транзакции"])
app.include_router(balance.router, prefix="/api/v1/balance", tags=["Баланс"])
app.include_router(network.router, prefix="/api/v1/network", tags=["Сеть"])


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    with open("app/templates/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/health", tags=["Служебные"])
async def health_check():
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
