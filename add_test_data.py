"""
Скрипт для добавления дополнительных тестовых данных в БД
"""
from app import app, db, Hall, Event, Booking
from datetime import datetime, timedelta


def add_sample_bookings():
    """Добавляет несколько тестовых бронирований"""
    with app.app_context():
        event = Event.query.first()
        if not event:
            print("Сначала инициализируйте БД: flask --app app init-db")
            return
        
        # Добавляем несколько забронированных мест для демонстрации
        sample_bookings = [
            Booking(event_id=event.id, row=1, seat=5, customer_name="Тестовый пользователь 1", customer_email="test1@example.com"),
            Booking(event_id=event.id, row=1, seat=6, customer_name="Тестовый пользователь 2", customer_email="test2@example.com"),
            Booking(event_id=event.id, row=3, seat=7, customer_name="Тестовый пользователь 3", customer_email="test3@example.com"),
            Booking(event_id=event.id, row=5, seat=6, customer_name="Тестовый пользователь 4", customer_email="test4@example.com"),
        ]
        
        for booking in sample_bookings:
            try:
                db.session.add(booking)
                db.session.commit()
                print(f"Добавлено бронирование: Ряд {booking.row}, Место {booking.seat}")
            except Exception as e:
                db.session.rollback()
                print(f"Ошибка при добавлении бронирования: {e}")


def add_more_events():
    """Добавляет больше событий для тестирования"""
    with app.app_context():
        halls = Hall.query.all()
        if not halls:
            print("Сначала инициализируйте БД: flask --app app init-db")
            return
        
        new_events = [
            Event(
                title='Вечерний сеанс: Интерстеллар',
                description='Научно-фантастический эпос Кристофера Нолана о путешествии через черную дыру',
                event_type='movie',
                start_time=datetime.now() + timedelta(days=4, hours=19),
                hall_id=halls[0].id
            ),
            Event(
                title='Мастер-класс: Python для анализа данных',
                description='Практический семинар по использованию pandas, numpy и matplotlib',
                event_type='conference',
                start_time=datetime.now() + timedelta(days=6, hours=10),
                hall_id=halls[2].id
            ),
            Event(
                title='Премьера: Дюна',
                description='Эпическая экранизация романа Фрэнка Герберта',
                event_type='movie',
                start_time=datetime.now() + timedelta(days=7, hours=20),
                hall_id=halls[0].id
            ),
        ]
        
        for event in new_events:
            db.session.add(event)
        
        db.session.commit()
        print(f"Добавлено событий: {len(new_events)}")


if __name__ == '__main__':
    print("Добавление тестовых данных...")
    add_sample_bookings()
    add_more_events()
    print("Готово!")
