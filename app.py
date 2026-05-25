from flask import Flask, render_template, request, jsonify, session, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import redis
import os
import uuid
from dotenv import load_dotenv
from functools import wraps
import hashlib

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost:5432/cinema_booking')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

db = SQLAlchemy(app)
redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))

LOCK_TIMEOUT = int(os.getenv('LOCK_TIMEOUT', 300))  # 5 минут по умолчанию

# Конфигурация для админки
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD_HASH = hashlib.sha256(os.getenv('ADMIN_PASSWORD', 'admin123').encode()).hexdigest()


# Модели БД
class Hall(db.Model):
    __tablename__ = 'halls'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    rows = db.Column(db.Integer, nullable=False)
    seats_per_row = db.Column(db.Integer, nullable=False)
    events = db.relationship('Event', backref='hall', lazy=True)


class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    event_type = db.Column(db.String(50), nullable=False)  # 'movie' или 'conference'
    start_time = db.Column(db.DateTime, nullable=False)
    hall_id = db.Column(db.Integer, db.ForeignKey('halls.id'), nullable=False)
    bookings = db.relationship('Booking', backref='event', lazy=True)


class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    row = db.Column(db.Integer, nullable=False)
    seat = db.Column(db.Integer, nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_email = db.Column(db.String(100), nullable=False)
    booking_time = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('event_id', 'row', 'seat', name='unique_seat_booking'),
    )


# Декоратор для проверки авторизации админа
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect('/admin/login')
        return f(*args, **kwargs)
    return decorated_function


# Функции для работы с Redis (временная блокировка мест)
def lock_seat(event_id, row, seat, session_id):
    """Блокирует место на время"""
    key = f"lock:event:{event_id}:row:{row}:seat:{seat}"
    return redis_client.set(key, session_id, ex=LOCK_TIMEOUT, nx=True)


def unlock_seat(event_id, row, seat, session_id):
    """Разблокирует место"""
    key = f"lock:event:{event_id}:row:{row}:seat:{seat}"
    stored_session = redis_client.get(key)
    if stored_session and stored_session.decode() == session_id:
        redis_client.delete(key)
        return True
    return False


def is_seat_locked(event_id, row, seat):
    """Проверяет, заблокировано ли место"""
    key = f"lock:event:{event_id}:row:{row}:seat:{seat}"
    return redis_client.exists(key)


def get_seat_lock_owner(event_id, row, seat):
    """Возвращает ID сессии, которая заблокировала место"""
    key = f"lock:event:{event_id}:row:{row}:seat:{seat}"
    owner = redis_client.get(key)
    return owner.decode() if owner else None


def extend_lock(event_id, row, seat, session_id):
    """Продлевает блокировку места"""
    key = f"lock:event:{event_id}:row:{row}:seat:{seat}"
    stored_session = redis_client.get(key)
    if stored_session and stored_session.decode() == session_id:
        redis_client.expire(key, LOCK_TIMEOUT)
        return True
    return False


# Маршруты пользовательской части
@app.route('/')
def index():
    """Главная страница со списком событий"""
    events = Event.query.order_by(Event.start_time).all()
    return render_template('index.html', events=events)


@app.route('/event/<int:event_id>')
def event_detail(event_id):
    """Страница выбора мест для события"""
    event = Event.query.get_or_404(event_id)
    
    # Создаем ID сессии, если его нет
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    return render_template('event.html', event=event)


@app.route('/api/seats/<int:event_id>')
def get_seats_status(event_id):
    """API для получения статуса всех мест"""
    event = Event.query.get_or_404(event_id)
    hall = event.hall
    session_id = session.get('session_id')
    
    seats = []
    for row in range(1, hall.rows + 1):
        for seat in range(1, hall.seats_per_row + 1):
            # Проверяем, забронировано ли место в БД
            booking = Booking.query.filter_by(
                event_id=event_id,
                row=row,
                seat=seat
            ).first()
            
            if booking:
                status = 'booked'
            elif is_seat_locked(event_id, row, seat):
                lock_owner = get_seat_lock_owner(event_id, row, seat)
                if lock_owner == session_id:
                    status = 'locked_by_me'
                else:
                    status = 'locked'
            else:
                status = 'available'
            
            seats.append({
                'row': row,
                'seat': seat,
                'status': status
            })
    
    return jsonify({'seats': seats})


@app.route('/api/lock', methods=['POST'])
def lock_seats():
    """API для блокировки места"""
    data = request.json
    event_id = data.get('event_id')
    row = data.get('row')
    seat = data.get('seat')
    session_id = session.get('session_id')
    
    if not all([event_id, row, seat, session_id]):
        return jsonify({'success': False, 'message': 'Недостаточно данных'}), 400
    
    # Проверяем, не забронировано ли уже место
    booking = Booking.query.filter_by(
        event_id=event_id,
        row=row,
        seat=seat
    ).first()
    
    if booking:
        return jsonify({'success': False, 'message': 'Место уже забронировано'}), 409
    
    # Пытаемся заблокировать место
    if lock_seat(event_id, row, seat, session_id):
        return jsonify({'success': True, 'message': 'Место заблокировано'})
    else:
        return jsonify({'success': False, 'message': 'Место занято другим пользователем'}), 409


@app.route('/api/unlock', methods=['POST'])
def unlock_seats():
    """API для разблокировки места"""
    data = request.json
    event_id = data.get('event_id')
    row = data.get('row')
    seat = data.get('seat')
    session_id = session.get('session_id')
    
    if unlock_seat(event_id, row, seat, session_id):
        return jsonify({'success': True, 'message': 'Место разблокировано'})
    else:
        return jsonify({'success': False, 'message': 'Не удалось разблокировать место'}), 400


@app.route('/api/book', methods=['POST'])
def book_seats():
    """API для окончательного бронирования мест (транзакция в БД)"""
    data = request.json
    event_id = data.get('event_id')
    seats_data = data.get('seats', [])
    customer_name = data.get('customer_name')
    customer_email = data.get('customer_email')
    session_id = session.get('session_id')
    
    if not all([event_id, seats_data, customer_name, customer_email, session_id]):
        return jsonify({'success': False, 'message': 'Недостаточно данных'}), 400
    
    try:
        # Начинаем транзакцию
        db.session.begin_nested()
        
        created_bookings = []
        
        for seat_info in seats_data:
            row = seat_info.get('row')
            seat = seat_info.get('seat')
            
            # Проверяем, что место заблокировано этой сессией
            lock_owner = get_seat_lock_owner(event_id, row, seat)
            if lock_owner != session_id:
                db.session.rollback()
                return jsonify({
                    'success': False,
                    'message': f'Место {row}-{seat} не заблокировано вами'
                }), 409
            
            # Создаем бронирование
            booking = Booking(
                event_id=event_id,
                row=row,
                seat=seat,
                customer_name=customer_name,
                customer_email=customer_email
            )
            db.session.add(booking)
            created_bookings.append((row, seat))
        
        # Фиксируем транзакцию
        db.session.commit()
        
        # Снимаем блокировки в Redis
        for row, seat in created_bookings:
            unlock_seat(event_id, row, seat, session_id)
        
        return jsonify({
            'success': True,
            'message': f'Успешно забронировано мест: {len(created_bookings)}'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Ошибка бронирования: {str(e)}'}), 500


@app.route('/api/extend_lock', methods=['POST'])
def extend_seat_lock():
    """API для продления блокировки места"""
    data = request.json
    event_id = data.get('event_id')
    row = data.get('row')
    seat = data.get('seat')
    session_id = session.get('session_id')
    
    if extend_lock(event_id, row, seat, session_id):
        return jsonify({'success': True})
    else:
        return jsonify({'success': False}), 400


# Маршруты админ-панели
@app.route('/admin/login')
def admin_login():
    """Страница входа в админ-панель"""
    return render_template('admin/login.html')


@app.route('/admin/api/login', methods=['POST'])
def admin_api_login():
    """API для входа в админ-панель"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    if username == ADMIN_USERNAME and password_hash == ADMIN_PASSWORD_HASH:
        session['admin_logged_in'] = True
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'message': 'Неверный логин или пароль'}), 401


@app.route('/admin/logout')
def admin_logout():
    """Выход из админ-панели"""
    session.pop('admin_logged_in', None)
    return redirect('/admin/login')


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Главная страница админ-панели с дашбордом"""
    # Статистика
    total_events = Event.query.count()
    total_bookings = Booking.query.count()
    total_halls = Hall.query.count()
    
    # Заполняемость
    all_seats = sum(h.rows * h.seats_per_row for h in Hall.query.all())
    occupancy_rate = (total_bookings / all_seats * 100) if all_seats > 0 else 0
    
    # Последние бронирования
    recent_bookings = Booking.query.order_by(Booking.booking_time.desc()).limit(10).all()
    
    # Популярные события
    popular_events = []
    for event in Event.query.all():
        booking_count = len(event.bookings)
        total_seats = event.hall.rows * event.hall.seats_per_row
        occupancy = (booking_count / total_seats * 100) if total_seats > 0 else 0
        popular_events.append({
            'id': event.id,
            'title': event.title,
            'event_type': event.event_type,
            'booking_count': booking_count,
            'occupancy_percentage': occupancy
        })
    popular_events.sort(key=lambda x: x['booking_count'], reverse=True)
    
    stats = {
        'total_events': total_events,
        'total_bookings': total_bookings,
        'total_halls': total_halls,
        'occupancy_rate': occupancy_rate
    }
    
    return render_template('admin/dashboard.html', 
                         stats=stats, 
                         recent_bookings=recent_bookings,
                         popular_events=popular_events[:5])


@app.route('/admin/events')
@admin_required
def admin_events():
    """Страница управления событиями"""
    events = Event.query.all()
    halls = Hall.query.all()
    return render_template('admin/events.html', events=events, halls=halls)


@app.route('/admin/halls')
@admin_required
def admin_halls():
    """Страница управления залами"""
    halls = Hall.query.all()
    return render_template('admin/halls.html', halls=halls)


@app.route('/admin/bookings')
@admin_required
def admin_bookings():
    """Страница управления бронированиями"""
    bookings = Booking.query.order_by(Booking.booking_time.desc()).all()
    events = Event.query.all()
    return render_template('admin/bookings.html', bookings=bookings, events=events)


# API для админки
@app.route('/admin/api/events', methods=['POST'])
@admin_required
def admin_create_event():
    """Создание нового события"""
    data = request.json
    try:
        event = Event(
            title=data['title'],
            description=data.get('description', ''),
            event_type=data['event_type'],
            hall_id=data['hall_id'],
            start_time=datetime.fromisoformat(data['start_time'])
        )
        db.session.add(event)
        db.session.commit()
        return jsonify({'success': True, 'id': event.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/admin/api/events/<int:event_id>', methods=['GET'])
@admin_required
def admin_get_event(event_id):
    """Получение информации о событии"""
    event = Event.query.get_or_404(event_id)
    return jsonify({
        'id': event.id,
        'title': event.title,
        'description': event.description,
        'event_type': event.event_type,
        'hall_id': event.hall_id,
        'start_time': event.start_time.isoformat()
    })


@app.route('/admin/api/events/<int:event_id>', methods=['PUT'])
@admin_required
def admin_update_event(event_id):
    """Обновление события"""
    event = Event.query.get_or_404(event_id)
    data = request.json
    try:
        event.title = data['title']
        event.description = data.get('description', '')
        event.event_type = data['event_type']
        event.hall_id = data['hall_id']
        event.start_time = datetime.fromisoformat(data['start_time'])
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/admin/api/events/<int:event_id>', methods=['DELETE'])
@admin_required
def admin_delete_event(event_id):
    """Удаление события"""
    event = Event.query.get_or_404(event_id)
    try:
        # Удаляем связанные блокировки в Redis
        for booking in event.bookings:
            key = f"lock:event:{event_id}:row:{booking.row}:seat:{booking.seat}"
            redis_client.delete(key)
        db.session.delete(event)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/admin/api/halls', methods=['POST'])
@admin_required
def admin_create_hall():
    """Создание нового зала"""
    data = request.json
    try:
        hall = Hall(
            name=data['name'],
            rows=data['rows'],
            seats_per_row=data['seats_per_row']
        )
        db.session.add(hall)
        db.session.commit()
        return jsonify({'success': True, 'id': hall.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/admin/api/halls/<int:hall_id>', methods=['PUT'])
@admin_required
def admin_update_hall(hall_id):
    """Обновление зала"""
    hall = Hall.query.get_or_404(hall_id)
    data = request.json
    try:
        hall.name = data['name']
        hall.rows = data['rows']
        hall.seats_per_row = data['seats_per_row']
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/admin/api/halls/<int:hall_id>', methods=['DELETE'])
@admin_required
def admin_delete_hall(hall_id):
    """Удаление зала"""
    hall = Hall.query.get_or_404(hall_id)
    if hall.events:
        return jsonify({'success': False, 'message': 'Невозможно удалить зал с существующими событиями'}), 400
    try:
        db.session.delete(hall)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/admin/api/halls/<int:hall_id>', methods=['GET'])
@admin_required
def admin_get_hall(hall_id):
    """Получение информации о зале"""
    hall = Hall.query.get_or_404(hall_id)
    return jsonify({
        'id': hall.id,
        'name': hall.name,
        'rows': hall.rows,
        'seats_per_row': hall.seats_per_row
    })

@app.route('/admin/api/bookings/<int:booking_id>', methods=['DELETE'])
@admin_required
def admin_delete_booking(booking_id):
    """Удаление бронирования"""
    booking = Booking.query.get_or_404(booking_id)
    try:
        db.session.delete(booking)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/admin/api/bookings/filter', methods=['POST'])
@admin_required
def admin_filter_bookings():
    """Фильтрация бронирований"""
    data = request.json
    query = Booking.query
    
    if data.get('event_id'):
        query = query.filter_by(event_id=data['event_id'])
    if data.get('customer_name'):
        query = query.filter(Booking.customer_name.ilike(f"%{data['customer_name']}%"))
    if data.get('customer_email'):
        query = query.filter(Booking.customer_email.ilike(f"%{data['customer_email']}%"))
    
    bookings = query.order_by(Booking.booking_time.desc()).all()
    
    return jsonify([{
        'id': b.id,
        'event_title': b.event.title,
        'row': b.row,
        'seat': b.seat,
        'customer_name': b.customer_name,
        'customer_email': b.customer_email,
        'booking_time': b.booking_time.isoformat()
    } for b in bookings])


# Инициализация БД и тестовые данные
@app.cli.command()
def init_db():
    """Инициализирует БД и добавляет тестовые данные"""
    db.create_all()
    
    # Создаем залы
    if not Hall.query.first():
        hall1 = Hall(name='Большой зал', rows=10, seats_per_row=12)
        hall2 = Hall(name='Малый зал', rows=6, seats_per_row=8)
        hall3 = Hall(name='Конференц-зал A', rows=8, seats_per_row=10)
        
        db.session.add_all([hall1, hall2, hall3])
        db.session.commit()
        
        # Создаем события
        event1 = Event(
            title='Премьера: Космическая одиссея',
            description='Захватывающий научно-фантастический фильм о путешествии в далекие галактики',
            event_type='movie',
            start_time=datetime.now() + timedelta(days=1),
            hall_id=hall1.id
        )
        
        event2 = Event(
            title='Классика: Криминальное чтиво',
            description='Легендарный фильм Квентина Тарантино',
            event_type='movie',
            start_time=datetime.now() + timedelta(days=2),
            hall_id=hall2.id
        )
        
        event3 = Event(
            title='Конференция: Будущее технологий 2024',
            description='Международная конференция по искусственному интеллекту и машинному обучению',
            event_type='conference',
            start_time=datetime.now() + timedelta(days=3),
            hall_id=hall3.id
        )
        
        event4 = Event(
            title='Семинар: Эффективное управление проектами',
            description='Практический семинар для менеджеров и руководителей проектов',
            event_type='conference',
            start_time=datetime.now() + timedelta(days=5),
            hall_id=hall3.id
        )
        
        db.session.add_all([event1, event2, event3, event4])
        db.session.commit()
        
        print('База данных инициализирована с тестовыми данными!')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
