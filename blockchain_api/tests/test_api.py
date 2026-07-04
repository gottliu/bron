"""
Тесты: pytest + pytest-asyncio
Запуск: pytest tests/ -v
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.web3_service import (
    create_wallet, generate_new_mnemonic,
    create_wallet_from_mnemonic, import_wallet_from_private_key,
    validate_address
)
from app.crypto_utils import encrypt_private_key, decrypt_private_key


# ──────────────────────────────────────────────
# Unit-тесты: Web3-сервис
# ──────────────────────────────────────────────

class TestWalletCreation:
    def test_create_wallet_returns_valid_address(self):
        w = create_wallet()
        assert w["address"].startswith("0x")
        assert len(w["address"]) == 42
        assert validate_address(w["address"])

    def test_create_wallet_returns_private_key(self):
        w = create_wallet()
        assert w["private_key"].startswith("0x")
        assert len(w["private_key"]) == 66

    def test_create_wallet_unique(self):
        w1 = create_wallet()
        w2 = create_wallet()
        assert w1["address"] != w2["address"]

    def test_generate_mnemonic_12_words(self):
        m = generate_new_mnemonic(12)
        assert len(m.split()) == 12

    def test_generate_mnemonic_24_words(self):
        m = generate_new_mnemonic(24)
        assert len(m.split()) == 24

    def test_create_from_mnemonic_deterministic(self):
        m = generate_new_mnemonic(12)
        w1 = create_wallet_from_mnemonic(m, 0)
        w2 = create_wallet_from_mnemonic(m, 0)
        assert w1["address"] == w2["address"]

    def test_create_from_mnemonic_different_index(self):
        m = generate_new_mnemonic(12)
        w0 = create_wallet_from_mnemonic(m, 0)
        w1 = create_wallet_from_mnemonic(m, 1)
        assert w0["address"] != w1["address"]

    def test_import_from_private_key(self):
        original = create_wallet()
        imported = import_wallet_from_private_key(original["private_key"])
        assert imported["address"] == original["address"]

    def test_import_private_key_without_0x(self):
        original = create_wallet()
        key_no_prefix = original["private_key"][2:]  # убираем 0x
        imported = import_wallet_from_private_key(key_no_prefix)
        assert imported["address"] == original["address"]


class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        key = "0x" + "ab" * 32
        encrypted = encrypt_private_key(key)
        decrypted = decrypt_private_key(encrypted)
        assert decrypted == key

    def test_encrypted_key_is_different(self):
        key = "0x" + "cd" * 32
        encrypted = encrypt_private_key(key)
        assert encrypted != key

    def test_each_encryption_is_unique(self):
        key = "0x" + "ef" * 32
        enc1 = encrypt_private_key(key)
        enc2 = encrypt_private_key(key)
        # Fernet использует случайный IV, поэтому каждый раз разный
        assert enc1 != enc2
        # Но оба должны расшифровываться в одно и то же значение
        assert decrypt_private_key(enc1) == decrypt_private_key(enc2) == key


class TestAddressValidation:
    def test_valid_address(self):
        w = create_wallet()
        assert validate_address(w["address"]) is True

    def test_invalid_address(self):
        assert validate_address("not_an_address") is False
        assert validate_address("0x1234") is False

    def test_lowercase_address_valid(self):
        w = create_wallet()
        assert validate_address(w["address"].lower()) is True


# ──────────────────────────────────────────────
# Интеграционные тесты: HTTP API
# ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="module")
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as c:
        yield c


@pytest.mark.asyncio
class TestWalletsAPI:
    async def test_create_wallet(self, client):
        resp = await client.post("/api/v1/wallets/create", json={"name": "Test Wallet"})
        assert resp.status_code == 200
        data = resp.json()
        assert "address" in data
        assert "private_key" in data
        assert "mnemonic" in data
        assert data["address"].startswith("0x")

    async def test_list_wallets(self, client):
        resp = await client.get("/api/v1/wallets/")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_create_wallet_missing_name(self, client):
        resp = await client.post("/api/v1/wallets/create", json={})
        assert resp.status_code == 422

    async def test_import_from_mnemonic(self, client):
        mnemonic = generate_new_mnemonic(12)
        resp = await client.post("/api/v1/wallets/import/mnemonic", json={
            "name": "Imported",
            "mnemonic": mnemonic,
            "account_index": 0,
        })
        assert resp.status_code == 200
        assert "address" in resp.json()

    async def test_import_invalid_mnemonic(self, client):
        resp = await client.post("/api/v1/wallets/import/mnemonic", json={
            "name": "Bad",
            "mnemonic": "word1 word2 word3",  # только 3 слова
        })
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestNetworkAPI:
    async def test_list_networks(self, client):
        resp = await client.get("/api/v1/network/")
        assert resp.status_code == 200
        data = resp.json()
        assert "networks" in data
        assert len(data["networks"]) >= 4

    async def test_invalid_network(self, client):
        resp = await client.get("/api/v1/network/nonexistent")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestBalanceAPI:
    async def test_invalid_address_balance(self, client):
        resp = await client.get("/api/v1/balance/not-an-address")
        assert resp.status_code == 400

    async def test_valid_address_format(self, client):
        # Валидный адрес — сеть может не ответить, но формат корректен
        resp = await client.get(
            "/api/v1/balance/0x742d35Cc6634C0532925a3b8D4C9D8f2e9f2A25E",
            params={"network": "goerli"}
        )
        # 200 или 503 (если нет соединения) — главное не 400
        assert resp.status_code in (200, 503)


@pytest.mark.asyncio
class TestTransactionEstimate:
    async def test_estimate_invalid_addresses(self, client):
        resp = await client.post("/api/v1/transactions/estimate", json={
            "from_address": "bad",
            "to_address": "also_bad",
            "value_eth": 0.001,
            "network": "goerli",
        })
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestHealthCheck:
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
