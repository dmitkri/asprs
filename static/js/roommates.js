const Roommates = {
    loadRoommates(empId) {
        $.get(`/api/employee/${empId}/roommates`)
            .done(function(response) {
                let roommates = [];
                if (Array.isArray(response)) {
                    roommates = response;
                } else if (response && response.roommates) {
                    roommates = response.roommates;
                } else if (response && Array.isArray(response)) {
                    roommates = response;
                }
                Roommates.renderRoommates(empId, roommates);
            })
            .fail(function(xhr) {
                $(`#roommates-list-${empId}`).html('<p class="text-muted mb-0">Ошибка загрузки соседей</p>');
            });
    },

    renderRoommates(empId, roommates) {
        const container = $(`#roommates-list-${empId}`);
        
        if (!roommates || roommates.length === 0) {
            container.html('<p class="text-muted mb-0">Нет соседей по комнате</p>');
            return;
        }
        
        let html = '<ul class="list-group list-group-flush">';
        roommates.forEach(function(roommate) {
            html += `
                <li class="list-group-item px-0">
                    <a href="#" class="text-decoration-none text-primary roommate-link" data-id="${roommate.id}" style="cursor: pointer;">
                        <strong>${Utils.escapeHtml(roommate.fio)}</strong>
                        ${roommate.group_name ? `<span class="text-muted ms-2">(${Utils.escapeHtml(roommate.group_name)})</span>` : ''}
                        ${roommate.phone ? `<br><small class="text-muted">${Utils.escapeHtml(roommate.phone)}</small>` : ''}
                    </a>
                </li>
            `;
        });
        html += '</ul>';
        
        container.html(html);
        
        container.find('.roommate-link').on('click', function(e) {
            e.preventDefault();
            const roommateId = $(this).data('id');
            const modalId = $(`#admin_empModal`).length > 0 ? 'admin_empModal' : 'user_empModal';
            const isEdit = modalId === 'admin_empModal';
            
            $(`#${modalId}`).modal('hide');
            
            setTimeout(function() {
                $.get(`/api/employee/${roommateId}`).done(function(emp) {
                    Modals.showEmployeeModal(emp, isEdit);
                }).fail(function(xhr) {
                    let msg = 'Не удалось загрузить карточку студента';
                    if (xhr.status === 404) {
                        msg = 'Ошибка: Студент не найден';
                    } else if (xhr.status >= 500) {
                        msg = 'Ошибка сервера при загрузке карточки студента. Попробуйте позже';
                    } else {
                        msg = 'Ошибка: Не удалось загрузить карточку студента. Проверьте подключение к интернету';
                    }
                    alert(msg);
                });
            }, 300);
        });
    },

    loadEmployeeReports(empId, showButtons = false) {
        const month = new Date().toISOString().slice(0, 7);
        $.get(`/api/employee/${empId}/reports`, { month: month })
            .done(function(data) {
                Roommates.renderReports(empId, data, showButtons);
            })
            .fail(function() {
                $(`#reports-section-${empId}`).html('<p class="text-muted">Ошибка загрузки отчетов</p>');
            });
    },

    markBedLinenReceived(empId, weekNum) {
        const weekLabels = {
            1: '1-й неделе',
            2: '2-й неделе',
            3: '3-й неделе',
            4: '4-й неделе'
        };
        
        const isAdmin = typeof window !== 'undefined' && window.adminRole && window.adminRole !== 'razmeshenie';
        if (isAdmin) {
            const dateInput = prompt(
                `Отметить получение белья на ${weekLabels[weekNum] || weekNum + '-й неделе'}.\n\n` +
                `Введите дату (YYYY-MM-DD) или оставьте пустым для текущей даты:\n` +
                `Пример: 2025-11-15 или 2025-11-15 14:30`,
                new Date().toISOString().slice(0, 10)
            );
            
            if (dateInput === null) {
                return;
            }
            
            const dataToSend = { week: weekNum };
            if (dateInput && dateInput.trim()) {
                dataToSend.date = dateInput.trim();
            }
            
            $.ajax({
                url: `/api/employee/${empId}/mark_bed_linen`,
                method: 'POST',
                data: JSON.stringify(dataToSend),
                contentType: 'application/json',
                success: function(response) {
                    if (response.success) {
                        if (typeof showSuccess === 'function') {
                            showSuccess(response.message || 'Получение белья успешно отмечено!');
                        } else {
                            alert(response.message || 'Получение белья успешно отмечено!');
                        }
                        const monthSelect = $(`#reports-month-${empId}`);
                        const yearSelect = $(`#reports-year-${empId}`);
                        let month;
                        if (monthSelect.length && yearSelect.length) {
                            const monthVal = monthSelect.val();
                            const yearVal = yearSelect.val();
                            month = `${yearVal}-${String(monthVal).padStart(2, '0')}`;
                        } else {
                            month = new Date().toISOString().slice(0, 7);
                        }
                        const isAdmin = typeof window !== 'undefined' && window.adminRole && window.adminRole !== 'razmeshenie';
                        $.get(`/api/employee/${empId}/reports`, { month: month })
                            .done(function(newData) {
                                Roommates.renderReports(empId, newData, isAdmin);
                            });
                    } else {
                        if (typeof showError === 'function') {
                            showError(response.message || 'Ошибка: Не удалось отметить получение белья. Попробуйте позже.');
                        } else {
                            alert(response.message || 'Ошибка: Не удалось отметить получение белья. Попробуйте позже.');
                        }
                    }
                },
                error: function(xhr) {
                    let msg = 'Не удалось отметить получение белья';
                    if (xhr.responseJSON && xhr.responseJSON.message) {
                        msg = xhr.responseJSON.message;
                    } else if (xhr.status === 401) {
                        msg = 'Ошибка: У вас нет прав для выполнения этого действия';
                    } else if (xhr.status === 403) {
                        msg = 'Ошибка: У вас нет прав для отметки получения белья';
                    } else if (xhr.status === 404) {
                        msg = 'Ошибка: Студент не найден';
                    } else if (xhr.status >= 500) {
                        msg = 'Ошибка сервера при отметке получения белья. Попробуйте позже';
                    }
                    if (typeof showError === 'function') {
                        showError(msg);
                    } else {
                        alert(msg);
                    }
                }
            });
        } else {
            if (typeof showWarning === 'function') {
                showWarning('Только администраторы могут отмечать получение белья');
            } else {
                alert('Только администраторы могут отмечать получение белья');
            }
        }
    },

    markBedLinenReceivedByPeriod(empId, periodId, periodLabel) {
        const isAdmin = typeof window !== 'undefined' && window.adminRole && window.adminRole !== 'razmeshenie';
        if (!isAdmin) {
            if (typeof showWarning === 'function') {
                showWarning('Только администраторы могут отмечать получение белья');
            } else {
                alert('Только администраторы могут отмечать получение белья');
            }
            return;
        }
        
        const dateInput = prompt(
            `Отметить получение белья за период: ${periodLabel}\n\n` +
            `Введите дату (YYYY-MM-DD) или оставьте пустым для текущей даты:\n` +
            `Пример: 2025-11-15 или 2025-11-15 14:30`,
            new Date().toISOString().slice(0, 10)
        );
        
        if (dateInput === null) {
            return;
        }
        
        const dataToSend = { period_id: periodId };
        if (dateInput && dateInput.trim()) {
            dataToSend.date = dateInput.trim();
        }
        
        $.ajax({
            url: `/api/employee/${empId}/mark_bed_linen`,
            method: 'POST',
            data: JSON.stringify(dataToSend),
            contentType: 'application/json',
            success: function(response) {
                if (response.success) {
                    if (typeof showSuccess === 'function') {
                        showSuccess(response.message || 'Получение белья успешно отмечено!');
                    } else {
                        alert(response.message || 'Получение белья успешно отмечено!');
                    }
                    const month = $(`#reports-month-${empId}`).val() || new Date().toISOString().slice(0, 7);
                    const isAdmin = typeof window !== 'undefined' && window.adminRole && window.adminRole !== 'razmeshenie';
                    $.get(`/api/employee/${empId}/reports`, { month: month })
                        .done(function(newData) {
                            Roommates.renderReports(empId, newData, isAdmin);
                        });
                } else {
                    if (typeof showError === 'function') {
                        showError(response.message || 'Ошибка: Не удалось отметить получение белья. Попробуйте позже.');
                    } else {
                        alert(response.message || 'Ошибка: Не удалось отметить получение белья. Попробуйте позже.');
                    }
                }
            },
            error: function(xhr) {
                let msg = 'Не удалось отметить получение белья';
                if (xhr.responseJSON && xhr.responseJSON.message) {
                    msg = xhr.responseJSON.message;
                } else if (xhr.status === 401) {
                    msg = 'Ошибка: У вас нет прав для выполнения этого действия';
                } else if (xhr.status === 403) {
                    msg = 'Ошибка: У вас нет прав для отметки получения белья';
                } else if (xhr.status === 404) {
                    msg = 'Ошибка: Студент не найден';
                } else if (xhr.status >= 500) {
                    msg = 'Ошибка сервера при отметке получения белья. Попробуйте позже';
                }
                if (typeof showError === 'function') {
                    showError(msg);
                } else {
                    alert(msg);
                }
            }
        });
    },

    renderReports(empId, data, showButtons = false) {
        const section = $(`#reports-section-${empId}`);
        if (!section.length) return;
        
        // Парсим текущий месяц и год
        let currentMonth = new Date().getMonth() + 1;
        let currentYear = new Date().getFullYear();
        if (data.month && data.month.includes('-')) {
            const parts = data.month.split('-');
            if (parts.length === 2) {
                currentYear = parseInt(parts[0], 10);
                currentMonth = parseInt(parts[1], 10);
            }
        }
        
        // Генерируем опции для месяцев
        const months = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 
                       'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];
        let monthOptions = '';
        months.forEach((monthName, index) => {
            const monthValue = index + 1;
            monthOptions += `<option value="${monthValue}" ${monthValue === currentMonth ? 'selected' : ''}>${monthName}</option>`;
        });
        
        // Генерируем опции для годов (текущий год ± 2 года)
        let yearOptions = '';
        const currentYearNum = new Date().getFullYear();
        for (let year = currentYearNum - 2; year <= currentYearNum + 2; year++) {
            yearOptions += `<option value="${year}" ${year === currentYear ? 'selected' : ''}>${year}</option>`;
        }
        
        let html = `
            <div class="mb-2">
                <label class="form-label small">Месяц:</label>
                <div class="row g-2">
                    <div class="col-8">
                        <select id="reports-month-${empId}" class="form-select form-select-sm">
                            ${monthOptions}
                        </select>
                    </div>
                    <div class="col-4">
                        <select id="reports-year-${empId}" class="form-select form-select-sm">
                            ${yearOptions}
                        </select>
                    </div>
                </div>
            </div>
        `;
        
        if (data.has_own_bed_linen) {
            html += `
                <div class="alert alert-info mb-3">
                    <i class="bi bi-info-circle"></i> У студента свое постельное белье
                </div>
            `;
        }
        
        if (data.dates && data.dates.length > 0) {
            html += `
                <div class="table-responsive">
                    <table class="table table-sm table-bordered">
                        <thead class="table-light">
                            <tr>
                                <th>Дата получения</th>
                                <th>Время</th>
                            </tr>
                        </thead>
                        <tbody>
            `;
            
            data.dates.forEach(function(dateInfo) {
                html += `
                    <tr>
                        <td>${dateInfo.date}</td>
                        <td>${dateInfo.time}</td>
                    </tr>
                `;
            });
            
            html += `
                        </tbody>
                    </table>
                </div>
                <div class="mt-2">
                    <small class="text-muted">
                        Всего получений: ${data.received_count}
                    </small>
                </div>
            `;
        } else {
            html += `
                <div class="alert alert-info">
                    <i class="bi bi-info-circle"></i> В этом месяце нет записей о получении белья
                </div>
            `;
        }
        
        
        section.html(html);
        
        // Функция для загрузки отчетов при изменении месяца или года
        const loadReportsForMonth = function() {
            const month = $(`#reports-month-${empId}`).val();
            const year = $(`#reports-year-${empId}`).val();
            const monthStr = `${year}-${String(month).padStart(2, '0')}`;
            $.get(`/api/employee/${empId}/reports`, { month: monthStr })
                .done(function(newData) {
                    Roommates.renderReports(empId, newData, showButtons);
                });
        };
        
        $(`#reports-month-${empId}, #reports-year-${empId}`).on('change', loadReportsForMonth);
    }
};


