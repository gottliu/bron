# Система бронирования мест

Курсовой проект: Система бронирования мест (кинотеатр, конференция) с временной блокировкой мест.

## Технологии

- **Backend**: Python 3.11+, Flask
- **База данных**: PostgreSQL (транзакции)
- **Кэш/Блокировки**: Redis (временная блокировка мест)
- **Frontend**: HTML, CSS, JavaScript (Vanilla)

## Функциональность

### Основные возможности:
- Просмотр списка событий (фильмы, конференции)
- Визуальный выбор мест в зале
- Временная блокировка мест (5 минут по умолчанию)
- Автоматическое продление блокировки
- Транзакционное бронирование в БД
- Защита от двойного бронирования
- Отображение статуса мест в реальном времени

### Технические особенности:
- **Транзакции БД**: Использование транзакций PostgreSQL для атомарного бронирования
- **Redis**: Временное хранение блокировок с TTL
- **Сессии**: Уникальная идентификация пользователей
- **Конкурентность**: Защита от race conditions

## Установка и запуск

### Требования:
- Python 3.11 или выше
- Docker и Docker Compose (для БД и Redis)
- pip

### Шаг 1: Клонирование и установка зависимостей

```bash
# Переход в директорию проекта
cd cinema_booking

# Создание виртуального окружения
python -m venv venv

# Активация виртуального окружения
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Установка зависимостей
pip install -r requirements.txt
```

### Шаг 2: Запуск PostgreSQL и Redis

```bash
# Запуск контейнеров
docker-compose up -d

# Проверка статуса
docker-compose ps
```

### Шаг 3: Настройка переменных окружения

```bash
# Копирование примера конфигурации
cp .env.example .env

# Редактирование .env (если нужно)
# По умолчанию настройки соответствуют docker-compose.yml
```

Содержимое `.env`:
```
DATABASE_URL=postgresql://cinema_user:cinema_pass@localhost:5432/cinema_booking
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-change-in-production
LOCK_TIMEOUT=300
```

### Шаг 4: Инициализация базы данных

```bash
# Инициализация БД с тестовыми данными
flask --app app init-db
```

Эта команда создаст:
- 3 зала (Большой зал, Малый зал, Конференц-зал A)
- 4 события (2 фильма, 2 конференции)

### Шаг 5: Запуск приложения

```bash
# Запуск Flask-приложения
python app.py
```

Приложение будет доступно по адресу: http://localhost:5000

## Использование

### Для пользователя:

1. Откройте http://localhost:5000
2. Выберите интересующее событие
3. Выберите места в зале (кликните на свободные места)
4. Места будут автоматически заблокированы на 5 минут
5. Заполните форму (имя и email)
6. Нажмите "Забронировать места"
7. Получите подтверждение

### Статусы мест:

- **Свободно** (белый) - можно выбрать
- **Выбрано вами** (синий градиент) - заблокировано вами
- **Занято временно** (голубой) - заблокировано другим пользователем
- **Забронировано** (серый) - окончательно забронировано

## Архитектура

### База данных (PostgreSQL)

**Таблица halls** - залы:
- id
- name (название зала)
- rows (количество рядов)
- seats_per_row (мест в ряду)

**Таблица events** - события:
- id
- title (название)
- description (описание)
- event_type (тип: movie/conference)
- start_time (время начала)
- hall_id (FK на halls)

**Таблица bookings** - бронирования:
- id
- event_id (FK на events)
- row (ряд)
- seat (место)
- customer_name (имя)
- customer_email (email)
- booking_time (время бронирования)
- UNIQUE constraint на (event_id, row, seat)

### Redis

Ключи блокировки:
```
lock:event:{event_id}:row:{row}:seat:{seat} -> session_id
```

TTL: 300 секунд (5 минут)

### Процесс бронирования

1. **Выбор места** → Блокировка в Redis (NX + TTL)
2. **Таймер** → Автопродление каждые 30 секунд
3. **Бронирование** → Транзакция в PostgreSQL:
   - BEGIN
   - Проверка блокировки в Redis
   - INSERT в bookings
   - COMMIT
   - Удаление блокировки из Redis

### API Endpoints

- `GET /` - главная страница
- `GET /event/<id>` - страница выбора мест
- `GET /api/seats/<event_id>` - статус всех мест
- `POST /api/lock` - блокировка места
- `POST /api/unlock` - разблокировка места
- `POST /api/book` - финальное бронирование
- `POST /api/extend_lock` - продление блокировки

## Конфигурация

### Переменные окружения:

- `DATABASE_URL` - URL подключения к PostgreSQL
- `REDIS_URL` - URL подключения к Redis
- `SECRET_KEY` - секретный ключ для сессий
- `LOCK_TIMEOUT` - время блокировки места в секундах (по умолчанию 300)

## Остановка приложения

```bash
# Остановка Flask (Ctrl+C в терминале)

# Остановка Docker контейнеров
docker-compose down

# Остановка с удалением данных
docker-compose down -v
```

## Разработка

### Структура проекта:

```
cinema_booking/
├── app.py                  # Основное приложение Flask
├── requirements.txt        # Зависимости Python
├── docker-compose.yml      # Конфигурация БД и Redis
├── .env.example           # Пример конфигурации
├── templates/             # HTML шаблоны
│   ├── base.html
│   ├── index.html
│   └── event.html
└── static/                # Статические файлы
    ├── css/
    │   └── style.css
    └── js/
        └── booking.js
```

### Добавление новых событий:

```python
from app import db, Event, Hall
from datetime import datetime, timedelta

hall = Hall.query.first()
event = Event(
    title='Новое событие',
    description='Описание',
    event_type='movie',  # или 'conference'
    start_time=datetime.now() + timedelta(days=7),
    hall_id=hall.id
)
db.session.add(event)
db.session.commit()
```

## Особенности реализации

### Защита от race conditions:
- Использование Redis NX (set if not exists)
- PostgreSQL UNIQUE constraint
- Транзакции с ROLLBACK при конфликтах

### Управление сессиями:
- UUID для каждого пользователя
- Привязка блокировок к session_id
- Проверка владельца блокировки

### Автоматическое освобождение:
- TTL в Redis (автоудаление ключей)
- Таймер на клиенте
- Периодическое обновление статуса

## Дизайн

Мягкий, воздушный дизайн в голубых тонах:
- Цветовая палитра: оттенки голубого (#6bb6e8, #a8d5f0, #d4eaf7)
- Градиенты и размытые тени
- Скругленные углы
- Плавные анимации
- Адаптивная верстка
