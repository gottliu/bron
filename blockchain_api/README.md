# ⛓ Blockchain Wallet API

> Курсовой проект: API для работы с блокчейн-кошельками  
> **Стек:** Web3.py · FastAPI · SQLAlchemy async · SQLite · Pydantic v2

---

## 🚀 Быстрый старт

```bash
# 1. Клонировать / распаковать проект
cd blockchain_api

# 2. Создать виртуальное окружение
python -m venv venv
source venv/bin/activate          # Linux/Mac
venv\Scripts\activate             # Windows

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Настроить окружение
cp .env.example .env
# (при желании отредактируйте SECRET_KEY и RPC-адреса)

# 5. Запустить сервер
uvicorn app.main:app --reload --port 8000
```

Открыть в браузере:
- **Дашборд:** http://localhost:8000
- **Swagger UI:** http://localhost:8000/docs

---

## 🧪 Запуск тестов

```bash
pytest tests/ -v
```

---

## 📁 Структура проекта

```
blockchain_api/
├── app/
│   ├── main.py              # FastAPI приложение, маршруты
│   ├── config.py            # Настройки (сети, ключи)
│   ├── database.py          # SQLAlchemy модели + async engine
│   ├── schemas.py           # Pydantic схемы (валидация)
│   ├── web3_service.py      # Web3.py — кошельки, транзакции, баланс
│   ├── crypto_utils.py      # Fernet-шифрование приватных ключей
│   ├── templates/
│   │   └── index.html       # Веб-дашборд
│   └── routers/
│       ├── wallets.py       # CRUD кошельков
│       ├── transactions.py  # Отправка / статус / история
│       ├── balance.py       # Баланс адресов
│       └── network.py       # Информация о сетях
├── tests/
│   └── test_api.py          # Unit + интеграционные тесты
├── requirements.txt
├── pytest.ini
├── .env.example
└── README.md
```

---

## 🔌 API Эндпоинты

### Кошельки `/api/v1/wallets`

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/create` | Создать новый HD-кошелёк (BIP-44) |
| POST | `/import/mnemonic` | Импорт через мнемоническую фразу |
| POST | `/import/privatekey` | Импорт по hex-приватному ключу |
| GET | `/` | Список всех кошельков |
| GET | `/{id}` | Информация о кошельке |
| DELETE | `/{id}` | Деактивировать кошелёк |

### Баланс `/api/v1/balance`

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/{address}?network=goerli` | Баланс адреса |
| POST | `/multi` | Баланс нескольких адресов |

### Транзакции `/api/v1/transactions`

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/send` | Подписать и отправить транзакцию |
| POST | `/estimate` | Оценить стоимость (газ) |
| GET | `/status/{tx_hash}` | Статус транзакции |
| GET | `/info/{tx_hash}` | Детали транзакции |
| GET | `/history/{address}` | История транзакций |

### Сеть `/api/v1/network`

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/` | Список поддерживаемых сетей |
| GET | `/{network_key}` | Статус сети |
| GET | `/gas/{network_key}` | Цена газа |

---

## 🌐 Поддерживаемые сети

| Ключ | Сеть | Chain ID | Символ |
|------|------|----------|--------|
| `ethereum` | Ethereum Mainnet | 1 | ETH |
| `goerli` | Goerli Testnet | 5 | ETH |
| `bsc` | BNB Smart Chain | 56 | BNB |
| `bsc_testnet` | BSC Testnet | 97 | tBNB |

---

## 🔐 Безопасность

- Приватные ключи шифруются **Fernet (AES-128-CBC + HMAC)** перед записью в БД
- Ключ шифрования выводится из `SECRET_KEY` через SHA-256
- Приватный ключ **возвращается только при создании кошелька** — затем недоступен через API
- Soft-delete: кошельки не удаляются физически

---

## 💡 Пример использования

```python
import httpx

BASE = "http://localhost:8000/api/v1"

# Создать кошелёк
r = httpx.post(f"{BASE}/wallets/create", json={"name": "Test"})
wallet = r.json()
print(f"Address: {wallet['address']}")
print(f"Mnemonic: {wallet['mnemonic']}")  # сохраните!

# Проверить баланс
r = httpx.get(f"{BASE}/balance/{wallet['address']}", params={"network": "goerli"})
print(r.json())

# Информация о сети
r = httpx.get(f"{BASE}/network/goerli")
print(r.json())
```

---

