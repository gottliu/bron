let selectedSeats = [];
let timerInterval = null;
let remainingTime = 0;

function initBookingSystem(eventId, rows, seatsPerRow, lockTimeout) {
    renderHall(rows, seatsPerRow);
    loadSeatsStatus(eventId);
    
    // Обновляем статус мест каждые 3 секунды
    setInterval(() => loadSeatsStatus(eventId), 3000);
    
    // Обработчик формы бронирования
    const form = document.getElementById('booking-form');
    if (form) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            completeBooрking(eventId);
        });
    }
}

function renderHall(rows, seatsPerRow) {
    const hallGrid = document.getElementById('hall-grid');
    hallGrid.innerHTML = '';
    
    for (let row = 1; row <= rows; row++) {
        const rowDiv = document.createElement('div');
        rowDiv.className = 'hall-row';
        
        // Номер ряда
        const rowLabel = document.createElement('div');
        rowLabel.className = 'row-label';
        rowLabel.textContent = row;
        rowDiv.appendChild(rowLabel);
        
        // Места в ряду
        for (let seat = 1; seat <= seatsPerRow; seat++) {
            const seatDiv = document.createElement('div');
            seatDiv.className = 'seat available';
            seatDiv.dataset.row = row;
            seatDiv.dataset.seat = seat;
            seatDiv.textContent = seat;
            
            seatDiv.addEventListener('click', () => handleSeatClick(row, seat));
            
            rowDiv.appendChild(seatDiv);
        }
        
        hallGrid.appendChild(rowDiv);
    }
}

async function loadSeatsStatus(eventId) {
    try {
        const response = await fetch(`/api/seats/${eventId}`);
        const data = await response.json();
        
        data.seats.forEach(seat => {
            const seatElement = document.querySelector(
                `.seat[data-row="${seat.row}"][data-seat="${seat.seat}"]`
            );
            
            if (seatElement) {
                // Удаляем все классы статуса
                seatElement.classList.remove('available', 'selected', 'locked', 'booked', 'locked_by_me');
                
                // Добавляем новый класс
                if (seat.status === 'locked_by_me') {
                    seatElement.classList.add('selected');
                } else {
                    seatElement.classList.add(seat.status);
                }
            }
        });
    } catch (error) {
        console.error('Ошибка загрузки статуса мест:', error);
    }
}

async function handleSeatClick(row, seat) {
    const seatElement = document.querySelector(
        `.seat[data-row="${row}"][data-seat="${seat}"]`
    );
    
    if (!seatElement) return;
    
    // Если место забронировано или заблокировано другим пользователем
    if (seatElement.classList.contains('booked') || 
        seatElement.classList.contains('locked')) {
        showNotification('Это место недоступно', 'error');
        return;
    }
    
    // Если место уже выбрано нами - снимаем выбор
    if (seatElement.classList.contains('selected')) {
        await unlockSeat(EVENT_ID, row, seat);
        return;
    }
    
    // Пытаемся заблокировать место
    await lockSeat(EVENT_ID, row, seat);
}

async function lockSeat(eventId, row, seat) {
    try {
        const response = await fetch('/api/lock', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                event_id: eventId,
                row: row,
                seat: seat
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            selectedSeats.push({ row, seat });
            updateSelectedSeatsList();
            startTimer(LOCK_TIMEOUT);
            showNotification('Место заблокировано', 'success');
        } else {
            showNotification(data.message || 'Не удалось заблокировать место', 'error');
        }
        
        // Обновляем статус всех мест
        await loadSeatsStatus(eventId);
    } catch (error) {
        console.error('Ошибка блокировки места:', error);
        showNotification('Ошибка соединения', 'error');
    }
}

async function unlockSeat(eventId, row, seat) {
    try {
        const response = await fetch('/api/unlock', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                event_id: eventId,
                row: row,
                seat: seat
            })
        });
        
        if (response.ok) {
            selectedSeats = selectedSeats.filter(s => !(s.row === row && s.seat === seat));
            updateSelectedSeatsList();
            
            if (selectedSeats.length === 0) {
                stopTimer();
            }
        }
        
        // Обновляем статус всех мест
        await loadSeatsStatus(eventId);
    } catch (error) {
        console.error('Ошибка разблокировки места:', error);
    }
}

function updateSelectedSeatsList() {
    const listContainer = document.getElementById('selected-seats-list');
    const bookingForm = document.getElementById('booking-form');
    
    if (selectedSeats.length === 0) {
        listContainer.innerHTML = '<p class="empty-message">Выберите места в зале</p>';
        bookingForm.style.display = 'none';
    } else {
        listContainer.innerHTML = '';
        
        selectedSeats.forEach(seat => {
            const item = document.createElement('div');
            item.className = 'selected-seat-item';
            item.innerHTML = `
                <span class="seat-info">Ряд ${seat.row}, Место ${seat.seat}</span>
                <button class="remove-seat" onclick="unlockSeat(${EVENT_ID}, ${seat.row}, ${seat.seat})">×</button>
            `;
            listContainer.appendChild(item);
        });
        
        bookingForm.style.display = 'block';
    }
}

function startTimer(totalSeconds) {
    const timerContainer = document.getElementById('timer-container');
    const timerElement = document.getElementById('timer');
    
    timerContainer.style.display = 'block';
    
    if (timerInterval) {
        clearInterval(timerInterval);
    }
    
    remainingTime = totalSeconds;
    
    timerInterval = setInterval(() => {
        remainingTime--;
        
        const minutes = Math.floor(remainingTime / 60);
        const seconds = remainingTime % 60;
        timerElement.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        
        // Меняем цвет при приближении к концу
        timerElement.classList.remove('warning', 'critical');
        if (remainingTime <= 30) {
            timerElement.classList.add('critical');
        } else if (remainingTime <= 60) {
            timerElement.classList.add('warning');
        }
        
        if (remainingTime <= 0) {
            stopTimer();
            clearAllSeats();
            showNotification('Время истекло. Места были освобождены.', 'error');
        } else if (remainingTime % 30 === 0 && selectedSeats.length > 0) {
            // Продлеваем блокировки каждые 30 секунд
            extendLocks();
        }
    }, 1000);
}

function stopTimer() {
    const timerContainer = document.getElementById('timer-container');
    timerContainer.style.display = 'none';
    
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
}

async function extendLocks() {
    for (const seat of selectedSeats) {
        try {
            await fetch('/api/extend_lock', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    event_id: EVENT_ID,
                    row: seat.row,
                    seat: seat.seat
                })
            });
        } catch (error) {
            console.error('Ошибка продления блокировки:', error);
        }
    }
}

function clearAllSeats() {
    selectedSeats = [];
    updateSelectedSeatsList();
    loadSeatsStatus(EVENT_ID);
}

async function completeBooрking(eventId) {
    const customerName = document.getElementById('customer_name').value;
    const customerEmail = document.getElementById('customer_email').value;
    
    if (!customerName || !customerEmail) {
        showNotification('Заполните все поля', 'error');
        return;
    }
    
    if (selectedSeats.length === 0) {
        showNotification('Выберите хотя бы одно место', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/book', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                event_id: eventId,
                seats: selectedSeats,
                customer_name: customerName,
                customer_email: customerEmail
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            stopTimer();
            showSuccessModal();
        } else {
            showNotification(data.message || 'Ошибка бронирования', 'error');
            // Обновляем статус мест
            await loadSeatsStatus(eventId);
        }
    } catch (error) {
        console.error('Ошибка бронирования:', error);
        showNotification('Ошибка соединения', 'error');
    }
}

function showNotification(message, type = 'info') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = `notification ${type}`;
    notification.style.display = 'block';
    
    setTimeout(() => {
        notification.style.display = 'none';
    }, 3000);
}

function showSuccessModal() {
    const modal = document.getElementById('success-modal');
    modal.classList.add('active');
    
    // Очищаем выбранные места
    selectedSeats = [];
    updateSelectedSeatsList();
}
