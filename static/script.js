function buildExtraFields(extra, isEdit) {
    if (typeof Columns !== 'undefined' && Columns.customCols) {
        customCols = Columns.customCols;
    }
    
    let html = '';
    if (!customCols || customCols.length === 0) {
        return html;
    }
        
        
    customCols.forEach(col => {
                const rawValue = extra[col.name] || '';
                const label = col.name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                
                if (isEdit) {
            let inputHtml = '';
            if (col.col_type === 'checkbox') {
                const isChecked = rawValue === 'true' || rawValue === true || rawValue === '1';
                const escapedLabel = escapeHtml(label);
                inputHtml = `
                    <div class="col-md-6 mb-3">
                        <div class="form-check">
                            <input type="checkbox" class="form-check-input" id="extra_${col.name}" ${isChecked ? 'checked' : ''}>
                            <label class="form-check-label" for="extra_${col.name}">${escapedLabel}</label>
                        </div>
                    </div>
                `;
            } else if (col.col_type === 'number') {
                const escapedValue = escapeHtml(String(rawValue));
                const escapedLabel = escapeHtml(label);
                inputHtml = `
                    <div class="col-md-6 mb-3">
                        <label class="form-label">${escapedLabel}</label>
                        <input type="number" class="form-control" id="extra_${col.name}" value="${escapedValue}">
                    </div>
                `;
            } else if (col.col_type === 'date') {
                const escapedValue = escapeHtml(String(rawValue));
                const escapedLabel = escapeHtml(label);
                inputHtml = `
                    <div class="col-md-6 mb-3">
                        <label class="form-label">${escapedLabel}</label>
                        <input type="date" class="form-control" id="extra_${col.name}" value="${escapedValue}">
                    </div>
                `;
            } else {
                const escapedValue = escapeHtml(String(rawValue));
                const escapedLabel = escapeHtml(label);
                inputHtml = `
                    <div class="col-md-6 mb-3">
                        <label class="form-label">${escapedLabel}</label>
                        <input type="text" class="form-control" id="extra_${col.name}" value="${escapedValue}">
                    </div>
                `;
            }
                    html += inputHtml;
                } else {
                        let displayValue = rawValue || '—';
                        if (col.col_type === 'date' && displayValue && displayValue !== '—') {
                            const parts = displayValue.split('-');
                            if (parts.length === 3) displayValue = `${parts[2]}.${parts[1]}.${parts[0]}`;
                        } else if (col.col_type === 'checkbox') {
                            displayValue = (rawValue === 'true' || rawValue === true || rawValue === '1') ? 'Да' : 'Нет';
                        }
            const escapedValue = escapeHtml(String(displayValue));
                    const escapedLabel = escapeHtml(label);
                    html += `
                        <div class="col-md-6 mb-3">
                            <label class="form-label">${escapedLabel}</label>
                    <p class="form-control-plaintext">${escapedValue}</p>
                        </div>
                    `;
            }
        });
        return html ? `<div class="row mt-3">${html}</div>` : '';
}

function buildHealthSection(emp, isEdit) {
    const health = getHealthInfo(emp);
    const current = health.current;
    
    if (!isEdit) {
        let html = '';
        
        if (current && current.is_ill) {
            const startDate = current.date ? (() => {
                const [y, m, d] = current.date.split('-');
                return `${d}.${m}.${y}`;
            })() : '—';
            html += `
                <div class="alert alert-info mb-2">
                    <strong>Болеет</strong> с ${startDate}
                    ${current.comment ? `<br><small>${escapeHtml(current.comment)}</small>` : ''}
                </div>
            `;
        } else {
            html += '<p class="text-success mb-2"><strong>Здоров</strong></p>';
        }
        
        if (isEdit) {
        const history = health.history || [];
        const historyJson = JSON.stringify(history).replace(/'/g, "&#39;");
        html += `
            <button type="button" class="btn btn-sm btn-outline-info health-history-btn mt-2" data-history='${historyJson}' data-emp-id="${emp.id}">
                <i class="bi bi-clock-history"></i> ${history.length > 0 ? `Показать историю (${history.length})` : 'История здоровья'}
            </button>
        `;
        }
        
        return html;
    } else {
        let html = '';
        if (current && current.is_ill) {
            const startDate = current.date ? (() => {
                const [y, m, d] = current.date.split('-');
                return `${d}.${m}.${y}`;
            })() : '—';
            const continuations = current.continuations || [];
            let continuationsHtml = '';
            if (continuations.length > 0) {
                continuationsHtml = '<div class="mt-2"><small class="text-muted">Продолжения:</small><ul class="mb-0 mt-1 small">';
                continuations.forEach(cont => {
                    const contDate = cont.date ? (() => {
                        const [y, m, d] = cont.date.split('-');
                        return `${d}.${m}.${y}`;
                    })() : '';
                    continuationsHtml += `<li>${contDate}: ${escapeHtml(cont.comment || '')}</li>`;
                });
                continuationsHtml += '</ul></div>';
            }
            html += `
                <div class="alert alert-info mb-2">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <strong>Болеет</strong> с ${startDate}
                            ${current.comment ? `<br><small>${escapeHtml(current.comment)}</small>` : ''}
                            ${continuationsHtml}
                        </div>
                        <div>
                            <button type="button" class="btn btn-sm btn-outline-primary me-1" onclick="editCurrentHealthRecord(${emp.id})" title="Редактировать">
                                <i class="bi bi-pencil"></i>
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-info me-1" onclick="continueHealthRecord(${emp.id})" title="Продолжить запись">
                                <i class="bi bi-plus-circle"></i> Продолжить
                            </button>
                            <button type="button" class="btn btn-sm btn-success" onclick="markRecovered(${emp.id})">
                                <i class="bi bi-check-circle"></i> Отметить выздоровление
                            </button>
                        </div>
                    </div>
                </div>
            `;
        } else {
            html += '<p class="text-success mb-2"><strong>Здоров</strong></p>';
        }
        
        if (isEdit) {
        const history = health.history || [];
        const historyJson = JSON.stringify(history).replace(/'/g, "&#39;");
        html += `
            <button type="button" class="btn btn-sm btn-outline-info mt-2 health-history-btn" data-history='${historyJson}' data-emp-id="${emp.id}">
                <i class="bi bi-clock-history"></i> ${history.length > 0 ? `Показать историю (${history.length})` : 'История здоровья'}
            </button>
        `;
        }
        
        return html;
    }
}

function buildRepresentativesSection(representatives, isEdit) {
    if (!isEdit) {
        if (!representatives || representatives.length === 0) {
            return '<p class="text-muted mb-0">Нет данных</p>';
        }
        let html = '';
        representatives.forEach((rep, idx) => {
            html += `
                <div class="border rounded p-2 mb-2">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <strong>${escapeHtml(rep.fio || '—')}</strong>
                            <div class="small text-muted">${escapeHtml(rep.relation || '—')}</div>
                            <div class="small">${escapeHtml(rep.phone || '—')}</div>
                            ${rep.email ? `<div class="small">${escapeHtml(rep.email)}</div>` : ''}
                        </div>
                    </div>
                </div>
            `;
        });
        return html;
    } else {
        let html = '<div id="representatives-container">';
        if (representatives && representatives.length > 0) {
            representatives.forEach((rep, idx) => {
                html += buildRepresentativeRow(rep, idx);
            });
        }
        html += '</div>';
        html += `<button type="button" class="btn btn-sm btn-outline-success mt-2" onclick="addRepresentativeRow()">
            <i class="bi bi-plus"></i> Добавить представителя
        </button>`;
        return html;
    }
}

function buildRepresentativeRow(rep, idx) {
    rep = rep || { relation: '', fio: '', phone: '', email: '' };
    return `
        <div class="border rounded p-3 mb-2 bg-white rep-row" data-index="${idx}">
            <div class="row g-2">
                <div class="col-md-3">
                    <label class="form-label small">Кем приходится</label>
                    <input type="text" class="form-control form-control-sm" placeholder="Кем приходится" value="${escapeHtml(rep.relation || '')}">
                </div>
                <div class="col-md-3">
                    <label class="form-label small">ФИО</label>
                    <input type="text" class="form-control form-control-sm" placeholder="ФИО" value="${escapeHtml(rep.fio || '')}">
                </div>
                <div class="col-md-3">
                    <label class="form-label small">Телефон</label>
                    <input type="tel" class="form-control form-control-sm" placeholder="Телефон" value="${escapeHtml(rep.phone || '')}">
                </div>
                <div class="col-md-2">
                    <label class="form-label small">Email</label>
                    <input type="email" class="form-control form-control-sm" placeholder="Email" value="${escapeHtml(rep.email || '')}">
                </div>
                <div class="col-md-1 d-flex align-items-end">
                    <button type="button" class="btn btn-danger btn-sm remove-rep w-100">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </div>
        </div>
    `;
}

function addRepresentativeRow() {
    const container = $('#representatives-container');
    const idx = container.find('.rep-row').length;
    const row = $(buildRepresentativeRow({}, idx));
    container.append(row);
    row.find('.remove-rep').off('click').on('click', function() {
        $(this).closest('.rep-row').remove();
    });
}

function showEmployeeModal(emp, isEdit = false) {
    if (typeof Columns !== 'undefined') {
        if (!Columns.customCols || Columns.customCols.length === 0) {
            Columns.loadColumns();
        }
        customCols = Columns.customCols || [];
    }
    
    const adminRole = typeof window !== 'undefined' ? window.adminRole : null;
    if (adminRole === 'razmeshenie') {
        isEdit = false;
    }
    
    if (adminRole === 'audit') {
        const modalId = 'admin_empModal';
        const modalBody = $('#admin_modalBody');
        const footer = $('#admin_modalFooter');
        footer.empty();
        
        const paymentFromScholarship = emp.payment_from_scholarship === 1 || emp.payment_from_scholarship === true;
        
        let html = `
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title mb-4">${escapeHtml(emp.fio)}</h5>
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" id="paymentFromScholarship" ${paymentFromScholarship ? 'checked' : ''}>
                        <label class="form-check-label" for="paymentFromScholarship">
                            Оплата со стипендии
                        </label>
                    </div>
                </div>
            </div>
        `;
        
        modalBody.html(html);
        
        $('#paymentFromScholarship').off('change').on('change', function() {
            const checked = $(this).is(':checked');
            $.ajax({
                url: `/api/employee/${emp.id}/payment_from_scholarship`,
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({
                    payment_from_scholarship: checked
                }),
                success: function(response) {
                    if (response.success) {
                        emp.payment_from_scholarship = checked ? 1 : 0;
                    } else {
                        $('#paymentFromScholarship').prop('checked', !checked);
                        alert('Ошибка: ' + (response.error || 'Не удалось сохранить настройку'));
                    }
                },
                error: function(xhr) {
                    $('#paymentFromScholarship').prop('checked', !checked);
                    let errorMsg = 'Ошибка при сохранении';
                    if (xhr.responseJSON && xhr.responseJSON.error) {
                        errorMsg = xhr.responseJSON.error;
                    }
                    alert(errorMsg);
                }
            });
        });
        
        footer.append(`<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Закрыть</button>`);
        
        const modalTitle = $(`#${modalId} .modal-title`);
        modalTitle.text('Карточка студента');
        
        // Управление aria-hidden для доступности
        const modalElement = $(`#${modalId}`)[0];
        if (modalElement) {
            // Удаляем aria-hidden при открытии модального окна
            $(`#${modalId}`).off('show.bs.modal').on('show.bs.modal', function() {
                this.removeAttribute('aria-hidden');
            });
            
            // Устанавливаем aria-hidden при закрытии модального окна
            $(`#${modalId}`).off('hidden.bs.modal').on('hidden.bs.modal', function() {
                this.setAttribute('aria-hidden', 'true');
            });
            
            // Убеждаемся, что aria-hidden удален после полного открытия
            $(`#${modalId}`).off('shown.bs.modal').on('shown.bs.modal', function() {
                if (this.hasAttribute('aria-hidden')) {
                    this.removeAttribute('aria-hidden');
                }
            });
        }
        
        $(`#${modalId}`).modal('show');
        return;
    }
    
    const modalId = isEdit ? 'admin_empModal' : 'user_empModal';
    const modalBody = $(`#${isEdit ? 'admin' : 'user'}_modalBody`);
    const footer = $('#admin_modalFooter');
    footer.empty();

    let ageDisplay = '—';
    if (emp.birth_date) {
        const { age } = formatDateAndAge(emp.birth_date);
        ageDisplay = age || '—';
    }

    let photoHtml = '';
    if (emp.photo) {
        photoHtml = `<img id="currentPhoto" src="/static/avatars/${emp.photo}?t=${Date.now()}" alt="Фото" class="img-thumbnail" style="width: 150px; height: 150px; object-fit: cover;">`;
    } else {
        const avatarWithInitials = typeof Utils !== 'undefined' && Utils.generateAvatarWithInitials 
            ? Utils.generateAvatarWithInitials(emp.fio) 
            : defaultAvatar;
        photoHtml = `<img src="${avatarWithInitials}" alt="Нет фото" class="img-thumbnail" style="width: 150px; height: 150px; object-fit: cover;">`;
    }

    let vacationHtml = '';
    if (emp.vacation) {
        if (isEdit) {
            vacationHtml = `
                <div class="mt-2">
                    <small class="text-muted">Заявление:</small>
                    <p class="mb-0">${escapeHtml(emp.vacation)}</p>
                </div>
            `;
        } else {
            vacationHtml = `
                <div class="mt-2">
                    <small class="text-muted">Заявление:</small>
                    <p class="mb-0 fw-bold text-danger">${escapeHtml(emp.vacation)}</p>
                </div>
            `;
        }
    }

    const representatives = emp.representatives || [];
    const representativesSection = buildRepresentativesSection(representatives, isEdit);

        let html = `
        <!-- Верх: фото, ФИО, возраст, заявление -->
        <div class="d-flex mb-4 pb-3 border-bottom">
            <div class="me-3">
                ${photoHtml}
            </div>
            <div class="flex-grow-1">
                <h4 class="mb-1">${escapeHtml(emp.fio)}</h4>
                <p class="text-muted mb-1">Возраст: ${ageDisplay}</p>
                ${vacationHtml}
            </div>
        </div>

        <!-- Блок: Контактная информация -->
        <div data-collapse data-label="Контактная информация" data-open="false">
                ${isEdit ? `
                    <div class="row g-2">
                        <div class="col-md-12 mb-3">
                            <label class="form-label small">Фото</label>
                            <div class="consta-dragndrop-container consta-dragndrop-photo">
                                <input type="file" id="photoFile" accept="image/*">
                            </div>
                        </div>
                        <div class="col-md-6">
                            <label class="form-label small">ФИО <span class="text-danger">*</span></label>
                            <input type="text" class="form-control" id="fio" value="${escapeHtml(emp.fio)}" required>
                        </div>
                        <div class="col-md-6">
                            <label class="form-label small">Дата рождения</label>
                            <input type="text" class="form-control" id="birth_date" placeholder="дд.мм.гггг" value="${emp.birth_date ? (() => {
                                const dateStr = String(emp.birth_date).trim();
                                if (!dateStr || dateStr === '') {
                                    return '';
                                }
                                // Проверяем формат YYYY-MM-DD
                                if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
                                    const parts = dateStr.split('-');
                                    if (parts.length === 3) {
                                        const y = parseInt(parts[0], 10);
                                        const m = parseInt(parts[1], 10);
                                        const d = parseInt(parts[2], 10);
                                        // Проверяем валидность даты
                                        if (d >= 1 && d <= 31 && m >= 1 && m <= 12 && y >= 1900 && y <= 2100) {
                                            return `${String(d).padStart(2, '0')}.${String(m).padStart(2, '0')}.${y}`;
                                        }
                                    }
                                }
                                // Если уже в формате дд.мм.гггг, проверяем и возвращаем как есть
                                if (/^\d{1,2}\.\d{1,2}\.\d{4}$/.test(dateStr)) {
                                    return dateStr;
                                }
                                return '';
                            })() : ''}">
                        </div>
                        <div class="col-md-6">
                            <label class="form-label small">Телефон</label>
                            <input type="tel" class="form-control" id="phone" value="${escapeHtml(emp.phone || '')}">
                        </div>
                        <div class="col-md-6">
                            <label class="form-label small">Группа</label>
                            <select class="form-select" id="group_name"></select>
                        </div>
                    </div>
                ` : `
                <div class="row">
                        <div class="col-md-6">
                            <strong>Телефон:</strong> ${emp.phone || '—'}
                </div>
                        <div class="col-md-6">
                            <strong>Группа:</strong> ${emp.group_name || '—'}
                        </div>
                        <div class="col-md-6 mt-2">
                            <strong>Дата рождения:</strong> ${emp.birth_date ? (() => {
                                const { formatted } = formatDateAndAge(emp.birth_date);
                                return formatted;
                            })() : '—'}
                        </div>
                    </div>
                `}
        </div>

        <!-- Блок: Проживание -->
        <div data-collapse data-label="Проживание" data-open="false">
                ${isEdit ? `
                    <div class="row g-2">
                        <div class="col-md-4">
                            <label class="form-label small">Корпус</label>
                            <input type="text" class="form-control" id="building" value="${escapeHtml(emp.building || '')}">
                        </div>
                        <div class="col-md-4">
                            <label class="form-label small">Номер комнаты</label>
                            <input type="text" class="form-control" id="room_number" value="${escapeHtml(emp.room_number || '')}">
                        </div>
                        <div class="col-md-4">
                            <label class="form-label small">Подъезд</label>
                            <input type="text" class="form-control" id="entrance" value="${escapeHtml(emp.entrance || '')}" readonly style="background-color: #e9ecef; cursor: not-allowed;">
                            <small class="form-text text-muted">Заполняется автоматически</small>
                        </div>
                    </div>
                    <div class="row g-2 mt-2">
                        <div class="col-md-6">
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" id="has_own_bed_linen" ${emp.has_own_bed_linen ? 'checked' : ''}>
                                <label class="form-check-label" for="has_own_bed_linen">
                                    Свое постельное белье
                                </label>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" id="is_local" ${emp.is_local ? 'checked' : ''}>
                                <label class="form-check-label" for="is_local">
                                    Местный
                                </label>
                                <small class="form-text text-muted d-block">Местные студенты не включаются в списки на смену белья</small>
                            </div>
                        </div>
                    </div>
                ` : `
                    <div class="row">
                        <div class="col-md-12">
                            <strong>Адрес:</strong> ${(() => {
                                const parts = [];
                                if (emp.building) parts.push(emp.building);
                                if (emp.entrance) parts.push(emp.entrance);
                                if (emp.room_number) parts.push(emp.room_number);
                                return parts.length > 0 ? parts.join('-') : '—';
                            })()}
                        </div>
                        ${emp.has_own_bed_linen ? `
                        <div class="col-md-12 mt-2">
                            <span class="badge bg-info">
                                <i class="bi bi-check-circle"></i> Свое постельное белье
                            </span>
                        </div>
                        ` : ''}
                        ${emp.is_local ? `
                        <div class="col-md-12 mt-2">
                            <span class="badge bg-warning">
                                <i class="bi bi-house"></i> Местный
                            </span>
                        </div>
                        ` : ''}
                    </div>
                `}
        </div>

        <!-- Блок: Соседи по комнате -->
        ${emp.building && emp.entrance && emp.room_number ? `
        <div data-collapse data-label="Соседи по комнате" data-open="false" id="roommates-section-${emp.id}">
                <div id="roommates-list-${emp.id}">
                    <div class="text-center">
                        <div class="spinner-border spinner-border-sm" role="status">
                            <span class="visually-hidden">Загрузка...</span>
                        </div>
                    </div>
                </div>
        </div>
        ` : ''}

        <!-- Блок: Примечания, Выговоры, Акты -->
        <div data-collapse data-label="Дополнительная информация" data-open="false">
                ${isEdit ? `
                    <div class="row g-2">
                        <div class="col-md-4">
                            <label class="form-label small">Примечания</label>
                            <textarea class="form-control" id="notes" rows="3">${escapeHtml(emp.notes || '')}</textarea>
            </div>
                        <div class="col-md-4">
                            <label class="form-label small">Акты</label>
                            <textarea class="form-control" id="absences" rows="3">${escapeHtml(emp.absences || '')}</textarea>
        </div>
                        <div class="col-md-4">
                            <label class="form-label small">Выговоры</label>
                            <textarea class="form-control" id="reprimands" rows="3">${escapeHtml(emp.reprimands || '')}</textarea>
                        </div>
                    </div>
                    ${buildExtraFields(emp.extra_data, isEdit)}
                ` : `
                    <div class="row">
                        <div class="col-md-4">
                            <strong>Примечания:</strong>
                            <p class="text-muted">${escapeHtml(emp.notes || '—')}</p>
                        </div>
                        <div class="col-md-4">
                            <strong>Акты:</strong>
                            <p class="text-muted">${escapeHtml(emp.absences || '—')}</p>
                        </div>
                        <div class="col-md-4">
                            <strong>Выговоры:</strong>
                            <p class="text-muted">${escapeHtml(emp.reprimands || '—')}</p>
                        </div>
                    </div>
                    ${buildExtraFields(emp.extra_data, isEdit)}
                `}
        </div>

        <!-- Блок: Заявление (только для админки) -->
        ${isEdit ? `
            <div data-collapse data-label="Заявление" data-open="false">
                    <div class="input-group mb-2">
                        <input type="text" class="form-control" id="vacation" value="${escapeHtml(emp.vacation || '')}" readonly>
                        ${emp.vacation ? `
                            <button type="button" class="btn btn-outline-primary" onclick="editVacationForm(${emp.id})" title="Редактировать заявление">
                                <i class="bi bi-pencil"></i>
                            </button>
                            <button type="button" class="btn btn-outline-danger" onclick="deleteVacation(${emp.id})" title="Удалить заявление">
                                <i class="bi bi-trash"></i>
                            </button>
                        ` : `
                            <button type="button" class="btn btn-outline-primary" onclick="editVacationForm(${emp.id})" title="Добавить заявление">
                                <i class="bi bi-plus"></i> Добавить
                            </button>
                        `}
                    </div>
            </div>
        ` : ''}

        <!-- Блок: Законные представители -->
        <div data-collapse data-label="Законные представители" data-open="false">
                ${representativesSection}
        </div>

        <!-- Блок: Здоровье -->
        <div data-collapse data-label="Здоровье" data-open="false">
            <div class="d-flex justify-content-between align-items-center mb-2">
                    ${isEdit && (typeof window !== 'undefined' && window.adminRole && window.adminRole !== 'razmeshenie') ? `
                        <button type="button" class="btn btn-sm btn-outline-primary" onclick="showHealthForm(${emp.id})">
                            <i class="bi bi-plus-circle"></i> Добавить запись
                        </button>
                    ` : ''}
            </div>
            ${buildHealthSection(emp, isEdit)}
        </div>

        <!-- Блок: История заявлений (только для админки) -->
        ${isEdit ? `
            <div data-collapse data-label="История заявлений" data-open="false">
                <button type="button" class="btn btn-sm btn-outline-info vacation-history-btn" data-history='${JSON.stringify(emp.vacation_history || []).replace(/'/g, "&#39;")}' data-emp-id="${emp.id}">
                    <i class="bi bi-clock-history"></i> Показать историю${emp.vacation_history && emp.vacation_history.length > 0 ? ` (${emp.vacation_history.length})` : ''}
                </button>
            </div>
        ` : ''}

        <!-- Блок: Отчеты по получению белья -->
        <div data-collapse data-label="Отчеты по получению белья" data-open="false">
            <div id="reports-section-${emp.id}">
                <div class="text-center">
                    <div class="spinner-border spinner-border-sm" role="status">
                        <span class="visually-hidden">Загрузка...</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Блок: Файлы -->
        <div data-collapse data-label="Файлы" data-open="false">
            ${isEdit ? `
                <div class="mb-3">
                    <div class="consta-dragndrop-container">
                        <input type="file" id="employeeFileInput_${emp.id}" accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.gif,.txt,.zip,.rar,.ppt,.pptx,.csv,.odt,.rtf,.7z,.tar.gz" data-emp-id="${emp.id}">
                    </div>
                    <small class="form-text text-muted mt-2 d-block">
                        Разрешенные типы: PDF, DOC, DOCX, XLS, XLSX, JPG, JPEG, PNG, GIF, TXT, ZIP, RAR, PPT, PPTX и другие. Максимальный размер: 50 МБ
                    </small>
                </div>
            ` : ''}
            <div id="files-section-${emp.id}">
                <div class="text-center">
                    <div class="spinner-border spinner-border-sm" role="status">
                        <span class="visually-hidden">Загрузка...</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Блок: История изменений карточки (только для администраторов) -->
        ${isEdit && (typeof window !== 'undefined' && window.adminRole && (window.adminRole === 'admin' || window.adminRole === 'super_admin')) ? `
            <div data-collapse data-label="История изменений" data-open="false">
                <div class="d-flex justify-content-end">
                    <button type="button" class="btn btn-sm btn-outline-info" onclick="showChangesHistoryModal(${emp.id})">
                        <i class="bi bi-clock-history"></i> Показать историю
                    </button>
                </div>
            </div>
        ` : ''}
    `;

    modalBody.html(html);
    
    if (isEdit) {
    loadGroups('group_name', emp.group_name);
        modalBody.find('.remove-rep').off('click').on('click', function() {
            $(this).closest('.rep-row').remove();
        });
        
        window.availableRooms = window.availableRooms || [];
        window.roomsLoaded = false;
        $.get('/api/rooms/list').done(function(data) {
            if (data.success && data.rooms) {
                window.availableRooms = data.rooms;
                window.roomsLoaded = true;
            }
        }).fail(function(xhr) {
            window.roomsLoaded = true; // Помечаем как загруженное, чтобы не блокировать работу
        });
        
        window.validateRoom = function() {
            const building = $('#building').val().trim();
            const entrance = $('#entrance').val().trim();
            const roomNumber = $('#room_number').val().trim();
            
            
            $('#room-validation-error').closest('.col-12').remove();
            
            if (building && entrance && roomNumber) {
                if (!window.roomsLoaded) {
                    return true; // Если список еще не загружен, пропускаем валидацию
                }
                
                const roomExists = (window.availableRooms || []).some(room => {
                    const roomBuilding = (room.building || '').trim();
                    const roomEntrance = (room.entrance || '').trim();
                    const roomRoomNumber = (room.room_number || '').trim();
                    const match = roomBuilding === building && roomEntrance === entrance && roomRoomNumber === roomNumber;
                    if (match) {
                    }
                    return match;
                });
                
                
                if (!roomExists) {
                    const errorHtml = `
                        <div class="col-12">
                            <div id="room-validation-error" class="alert alert-danger mt-2 mb-0" role="alert">
                                <i class="bi bi-exclamation-triangle"></i> 
                                <strong>Ошибка:</strong> Комната ${building}-${entrance}-${roomNumber} не найдена в базе данных. 
                                Пожалуйста, сначала добавьте комнату в разделе "Управление комнатами".
                            </div>
                        </div>
                    `;
                    $('#room-validation-error').closest('.col-12').remove();
                    
                    const entranceField = $('#entrance');
                    const roomRow = entranceField.closest('.row');
                    if (roomRow.length) {
                        roomRow.after(errorHtml);
                    } else {
                        const parentContainer = entranceField.closest('.card-body, .modal-body');
                        if (parentContainer.length) {
                            entranceField.closest('.col-md-4').parent().after(errorHtml);
                        } else {
                            entranceField.closest('.col-md-4').after(errorHtml);
                        }
                    }
                    return false;
                } else {
                }
            }
            return true;
        }
        
        $('#building, #room_number').on('change blur', function() {
            const building = $('#building').val().trim();
            const roomNumber = $('#room_number').val().trim();
            if (building && roomNumber) {
                $.get('/api/get_entrance', {
                    building: building,
                    number: roomNumber
                }).done(function(data) {
                    if (data.entrance) {
                        $('#entrance').val(data.entrance);
                        setTimeout(function() {
                            if (window.validateRoom) {
                                window.validateRoom();
                            }
                        }, 200);
                    }
                }).fail(function() {
                });
            }
        });
        
        $('#building, #entrance, #room_number').on('change blur input', function() {
            setTimeout(function() {
                if (window.validateRoom) {
                    window.validateRoom();
                } else {
                }
            }, 300);
        });
    }

    if (isEdit) {
        const adminRole = typeof window !== 'undefined' ? window.adminRole : null;
        if (adminRole === 'razmeshenie') {
            footer.append(`<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Закрыть</button>`);
        } else {
            let deleteBtn = '';
            $.ajax({
                url: '/api/admin/permissions',
                async: false,
                success: function(data) {
                    if (data.permissions && data.permissions.delete) {
                        deleteBtn = `<button type="button" class="btn btn-danger" onclick="deleteEmployee(${emp.id})">Удалить</button>`;
                    }
                }
            });
            
            footer.append(`
                ${deleteBtn}
                <button type="button" class="btn btn-primary" onclick="saveEmployee()">Сохранить</button>
            `);
            currentEmpId = emp.id;
            if (typeof Employee !== 'undefined') {
                Employee.currentEmpId = emp.id;
            }
        }
    }

    if (isEdit) {
        modalBody.off('click', '.vacation-history-btn').on('click', '.vacation-history-btn', function(e) {
            e.preventDefault();
            e.stopPropagation();
            const button = this;
            
            try {
                if (typeof showVacationHistoryFromButton === 'function') {
                    showVacationHistoryFromButton(button);
                } else if (typeof Vacation !== 'undefined' && typeof Vacation.showHistoryFromButton === 'function') {
                    Vacation.showHistoryFromButton(button);
                } else {
                    alert('Ошибка: функция показа истории заявлений не найдена. Обновите страницу.');
                    
                    if (typeof Vacation !== 'undefined') {
                        try {
                            const historyData = $(button).data('history');
                            Vacation.showHistory(historyData || []);
                        } catch (directError) {
                            alert('Ошибка: функция показа истории заявлений не найдена. Обновите страницу.');
                        }
                    } else {
                        alert('Ошибка: модуль Vacation не загружен. Обновите страницу.');
                    }
                }
            } catch (e) {
                alert('Ошибка при открытии истории заявлений: ' + (e.message || e));
            }
        });
        
        modalBody.off('click', '.health-history-btn').on('click', '.health-history-btn', function(e) {
            e.preventDefault();
            e.stopPropagation();
            const button = this;
            
            try {
                if (typeof showHealthHistoryFromButton === 'function') {
                    showHealthHistoryFromButton(button);
                } else {
                    
                    const historyData = $(button).data('history');
                    const empId = $(button).data('emp-id') || $(button).attr('data-emp-id');
                    
                    if (typeof showHealthHistory === 'function') {
                        showHealthHistory(historyData || [], empId);
                    } else {
                        alert('Ошибка: функция показа истории здоровья не найдена. Обновите страницу.');
                    }
                }
            } catch (e) {
                alert('Ошибка при открытии истории здоровья: ' + (e.message || e));
            }
        });
    }

    loadEmployeeReports(emp.id, isEdit);
    
    loadRoommates(emp.id);
    
    setTimeout(function() {
        try {
            loadEmployeeFiles(emp.id, isEdit);
        } catch (e) {
            const section = $(`#files-section-${emp.id}`);
            if (section.length) {
                section.html('<p class="text-muted mb-0">Ошибка при загрузке файлов</p>');
            }
        }
    }, 100);
    

    if (isEdit) {
        const modalTitle = $(`#${modalId} .modal-title`);
        if (emp.id === 'new') {
            modalTitle.text('Добавление студента в АСПиРС');
        } else {
            modalTitle.text('Редактирование студента');
        }
    }

    // Управление aria-hidden для доступности
    const modalElement = $(`#${modalId}`)[0];
    if (modalElement) {
        // Удаляем aria-hidden при открытии модального окна
        $(`#${modalId}`).on('show.bs.modal', function() {
            this.removeAttribute('aria-hidden');
        });
        
        // Устанавливаем aria-hidden при закрытии модального окна
        $(`#${modalId}`).on('hidden.bs.modal', function() {
            this.setAttribute('aria-hidden', 'true');
        });
    }
    
    $(`#${modalId}`).modal('show');
    
    $(`#${modalId}`).on('shown.bs.modal', function() {
        // Убеждаемся, что aria-hidden удален после открытия
        if (this.hasAttribute('aria-hidden')) {
            this.removeAttribute('aria-hidden');
        }
        
        setTimeout(function() {
            if (typeof initConstaCollapses !== 'undefined') {
                initConstaCollapses($(`#${modalId}`)[0]);
            }
            
            if (typeof initConstaComboboxes !== 'undefined') {
                initConstaComboboxes($(`#${modalId}`)[0]);
            }
            
            if (typeof ConstaDatePicker !== 'undefined') {
                ConstaDatePicker.init();
            }
            
            // Инициализация календаря для поля даты рождения
            // Используем setTimeout для гарантии, что DOM полностью загружен
            setTimeout(() => {
                const birthDateInput = document.getElementById('birth_date');
                if (!birthDateInput) {
                    return;
                }
                
                // Если календарь уже инициализирован, пропускаем
                if (birthDateInput.classList.contains('consta-datepicker-initialized')) {
                    return;
                }
                
                if (typeof flatpickr === 'undefined') {
                    return;
                }
                
                // Инициализируем календарь
                const locale = flatpickr.l10ns?.ru || {
                    firstDayOfWeek: 1,
                    weekdays: {
                        shorthand: ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'],
                        longhand: ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']
                    },
                    months: {
                        shorthand: ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек'],
                        longhand: ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
                    }
                };
                
                let wrapper = birthDateInput.parentElement;
                if (!wrapper.classList.contains('consta-datepicker-wrapper')) {
                    wrapper = document.createElement('div');
                    wrapper.className = 'consta-datepicker-wrapper';
                    birthDateInput.parentNode.insertBefore(wrapper, birthDateInput);
                    wrapper.appendChild(birthDateInput);
                }
                
                const currentValue = birthDateInput.value;
                let defaultDate = null;
                // Инициализируем флаг, что дата была выбрана пользователем (false, так как это загрузка из базы)
                birthDateInput._userSelectedDate = false;
                // Проверяем, что значение действительно есть и не пустое
                if (currentValue && currentValue.trim() && currentValue.trim() !== '') {
                    // Преобразуем дд.мм.гггг в YYYY-MM-DD для flatpickr
                    const match = currentValue.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
                    if (match) {
                        const [, d, m, y] = match;
                        const dayNum = parseInt(d, 10);
                        const monthNum = parseInt(m, 10);
                        const yearNum = parseInt(y, 10);
                        // Проверяем валидность даты
                        if (dayNum >= 1 && dayNum <= 31 && monthNum >= 1 && monthNum <= 12 && yearNum >= 1900 && yearNum <= 2100) {
                            defaultDate = `${yearNum}-${String(monthNum).padStart(2, '0')}-${String(dayNum).padStart(2, '0')}`;
                            // Если дата загружена из базы, отмечаем это
                            birthDateInput._userSelectedDate = true; // Дата из базы считается валидной
                        }
                    } else if (/^\d{4}-\d{2}-\d{2}$/.test(currentValue)) {
                        // Проверяем валидность даты в формате YYYY-MM-DD
                        const parts = currentValue.split('-');
                        if (parts.length === 3) {
                            const y = parseInt(parts[0], 10);
                            const m = parseInt(parts[1], 10);
                            const d = parseInt(parts[2], 10);
                            if (d >= 1 && d <= 31 && m >= 1 && m <= 12 && y >= 1900 && y <= 2100) {
                                defaultDate = currentValue;
                                // Если дата загружена из базы, отмечаем это
                                birthDateInput._userSelectedDate = true; // Дата из базы считается валидной
                            }
                        }
                    }
                }
                
                // Если значение пустое, явно очищаем поле перед инициализацией
                if (!defaultDate) {
                    birthDateInput.value = '';
                    $(birthDateInput).val('');
                    birthDateInput._userSelectedDate = false;
                }
                
                // Определяем, куда прикреплять календарь
                const modalElement = birthDateInput.closest('.modal');
                
                const fpConfig = {
                    dateFormat: 'd.m.Y',
                    locale: locale,
                    allowInput: true,
                    clickOpens: true,
                    animate: true,
                    theme: 'consta-theme',
                    monthSelectorType: 'static',
                    static: false, // Всплывающий календарь
                    appendTo: modalElement || document.body,
                    // Явно указываем, что не нужно устанавливать дату по умолчанию
                    defaultDate: defaultDate || undefined,
                    // Отключаем автоматическую установку сегодняшней даты
                    enableTime: false,
                    // Отключаем автоматическую установку даты при клике
                    noCalendar: false,
                    // Явно указываем, что не нужно устанавливать текущую дату
                    disableMobile: false,
                    onChange: function(selectedDates, dateStr, instance) {
                        // Отмечаем, что дата была выбрана пользователем
                        instance.input._userSelectedDate = true;
                        // Обновляем значение input при изменении
                        if (selectedDates.length > 0 && dateStr) {
                            // dateStr уже в формате d.m.Y благодаря dateFormat
                            instance.input.value = dateStr;
                            // Также обновляем через jQuery для совместимости
                            $(instance.input).val(dateStr);
                            // Сохраняем выбранную дату для последующего использования
                            instance.input._selectedDate = selectedDates[0];
                        } else {
                            instance.input.value = '';
                            $(instance.input).val('');
                            instance.input._selectedDate = null;
                            instance.input._userSelectedDate = false;
                        }
                        // Триггерим событие change для других обработчиков
                        const event = new Event('change', { bubbles: true });
                        birthDateInput.dispatchEvent(event);
                        // Также триггерим через jQuery
                        $(birthDateInput).trigger('change');
                    },
                    onOpen: function(selectedDates, dateStr, instance) {
                        // При открытии календаря устанавливаем правильный z-index
                        const calendar = instance.calendarContainer;
                        if (calendar) {
                            if (modalElement) {
                                calendar.style.zIndex = '10060';
                                calendar.style.position = 'fixed';
                            }
                        }
                    },
                    onReady: function(selectedDates, dateStr, instance) {
                        // Если значение пустое, убеждаемся, что поле остается пустым
                        if (!defaultDate) {
                            // Очищаем выбранные даты
                            if (instance.selectedDates && instance.selectedDates.length > 0) {
                                instance.clear();
                            }
                            // Очищаем значение input
                            instance.input.value = '';
                            $(instance.input).val('');
                            // Дополнительная проверка: если flatpickr установил какую-то дату, очищаем её
                            if (dateStr && dateStr.trim() !== '') {
                                instance.clear();
                                instance.input.value = '';
                                $(instance.input).val('');
                            }
                        } else {
                            // Если есть defaultDate, убеждаемся, что она правильно отображается
                            // flatpickr должен отформатировать defaultDate в формат d.m.Y
                            const expectedDateStr = (() => {
                                const parts = defaultDate.split('-');
                                if (parts.length === 3) {
                                    const d = parseInt(parts[2], 10);
                                    const m = parseInt(parts[1], 10);
                                    const y = parseInt(parts[0], 10);
                                    return `${String(d).padStart(2, '0')}.${String(m).padStart(2, '0')}.${y}`;
                                }
                                return dateStr;
                            })();
                            
                            // Принудительно устанавливаем правильную дату
                            instance.setDate(defaultDate, false);
                            
                            // Устанавливаем правильное значение в input
                            instance.input.value = expectedDateStr;
                            $(instance.input).val(expectedDateStr);
                            
                            // Дополнительная проверка через небольшую задержку
                            setTimeout(() => {
                                const currentValue = instance.input.value.trim();
                                if (currentValue !== expectedDateStr) {
                                    instance.setDate(defaultDate, false);
                                    instance.input.value = expectedDateStr;
                                    $(instance.input).val(expectedDateStr);
                                }
                            }, 10);
                        }
                    }
                };
                
                const fp = flatpickr(birthDateInput, fpConfig);
                
                // Сохраняем ссылку на flatpickr для доступа из других функций
                birthDateInput._birthDatePicker = fp;
                birthDateInput._flatpickr = fp; // Также сохраняем для совместимости
                
                // Если есть defaultDate, принудительно устанавливаем правильную дату
                if (defaultDate) {
                    // Устанавливаем дату через setDate для гарантии правильного формата
                    fp.setDate(defaultDate, false);
                    // Убеждаемся, что значение input правильное
                    const expectedValue = (() => {
                        const parts = defaultDate.split('-');
                        if (parts.length === 3) {
                            const d = parseInt(parts[2], 10);
                            const m = parseInt(parts[1], 10);
                            const y = parseInt(parts[0], 10);
                            return `${String(d).padStart(2, '0')}.${String(m).padStart(2, '0')}.${y}`;
                        }
                        return '';
                    })();
                    if (fp.input && fp.input.value !== expectedValue) {
                        fp.input.value = expectedValue;
                        $(fp.input).val(expectedValue);
                    }
                } else {
                    // Если значение пустое, очищаем поле после инициализации
                    // Очищаем сразу после инициализации
                    fp.clear();
                    if (fp.input) {
                        fp.input.value = '';
                        $(fp.input).val('');
                    }
                    // Убеждаемся, что selectedDates пуст
                    if (fp.selectedDates && fp.selectedDates.length > 0) {
                        fp.selectedDates = [];
                    }
                    
                    // Дополнительная очистка через небольшую задержку на случай, если flatpickr установил значение
                    setTimeout(() => {
                        if (fp) {
                            const currentValue = fp.input ? fp.input.value.trim() : '';
                            // Если значение не пустое и не соответствует исходному, очищаем его
                            if (currentValue && currentValue !== '' && currentValue !== birthDateInput.getAttribute('data-original-value')) {
                                fp.clear();
                                if (fp.input) {
                                    fp.input.value = '';
                                    $(fp.input).val('');
                                }
                            }
                        }
                    }, 50);
                    
                    // Еще одна проверка через большую задержку
                    setTimeout(() => {
                        if (fp && fp.input) {
                            const currentValue = fp.input.value.trim();
                            if (currentValue && currentValue !== '') {
                                fp.clear();
                                fp.input.value = '';
                                $(fp.input).val('');
                            }
                        }
                    }, 200);
                }
                
                // Сохраняем исходное значение для проверки при сохранении
                if (currentValue) {
                    birthDateInput.setAttribute('data-original-value', currentValue || '');
                }
                
                // Обработка для правильного позиционирования календаря в модалке
                if (modalElement) {
                    // При открытии модалки убеждаемся, что календарь правильно позиционирован
                    $(modalElement).on('shown.bs.modal', function() {
                        setTimeout(() => {
                            if (fp && fp.calendarContainer) {
                                fp.calendarContainer.style.zIndex = '10060';
                                fp.calendarContainer.style.position = 'fixed';
                            }
                        }, 50);
                    });
                    
                    // Обработка клика по полю для открытия календаря
                    $(birthDateInput).on('click', function(e) {
                        e.stopPropagation();
                        if (fp && !fp.isOpen) {
                            fp.open();
                            // Устанавливаем правильный z-index после открытия
                            setTimeout(() => {
                                if (fp.calendarContainer) {
                                    fp.calendarContainer.style.zIndex = '10060';
                                    fp.calendarContainer.style.position = 'fixed';
                                }
                            }, 10);
                        }
                    });
                }
                
                birthDateInput.classList.add('consta-datepicker-initialized');
            }, 300); // Задержка для гарантии, что DOM готов и модалка полностью открыта
            
            if (typeof ConstaDragNDropField !== 'undefined') {
                const photoInput = $('#photoFile')[0];
                if (photoInput && !photoInput.classList.contains('consta-dragndrop-initialized')) {
                    const container = photoInput.closest('.consta-dragndrop-container');
                    if (container) {
                        new ConstaDragNDropField(container, {
                            accept: 'image/*',
                            onError: function(message) {
                                alert(message);
                            }
                        });
                        photoInput.classList.add('consta-dragndrop-initialized');
                    }
                }
                
                const fileInput = $(`#employeeFileInput_${emp.id}`)[0];
                if (fileInput) {
                    const container = fileInput.closest('.consta-dragndrop-container');
                    if (container) {
                        const existingWrapper = container.querySelector('.consta-dragndrop-wrapper');
                        if (existingWrapper) {
                            existingWrapper.remove();
                        }
                        
                        if (container._dragNDropFieldInstance) {
                            if (container._dragNDropFieldInstance.wrapper) {
                                container._dragNDropFieldInstance.wrapper.remove();
                            }
                            container._dragNDropFieldInstance = null;
                        }
                        
                        fileInput.classList.remove('consta-dragndrop-initialized');
                        
                        const newInput = fileInput.cloneNode(true);
                        fileInput.parentNode.replaceChild(newInput, fileInput);
                        const cleanFileInput = newInput;
                        
                        const empId = cleanFileInput.dataset.empId || emp.id;
                        
                        const savedEmpId = empId;
                        
                        const onDropCallback = function(files, input) {
                            if (files.length > 0) {
                                const fileEmpId = input.dataset.empId || savedEmpId;
                                if (!fileEmpId) {
                                    if (typeof showBannerError !== 'undefined') {
                                        showBannerError('Ошибка: не удалось определить ID студента');
                                    } else {
                                        alert('Ошибка: не удалось определить ID студента');
                                    }
                                    return;
                                }
                                if (typeof uploadEmployeeFileDirect === 'function') {
                                    uploadEmployeeFileDirect(fileEmpId, files[0], input);
                                } else {
                                    if (typeof showBannerError !== 'undefined') {
                                        showBannerError('Ошибка: функция загрузки файла не найдена');
                                    } else {
                                        alert('Ошибка: функция загрузки файла не найдена');
                                    }
                                }
                            }
                        };
                        
                        const onErrorCallback = function(message) {
                            if (typeof showBannerError !== 'undefined') {
                                showBannerError(message);
                            } else {
                                alert(message);
                            }
                        };
                        const dragNDropField = new ConstaDragNDropField(container, {
                            accept: '.pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.gif,.txt,.zip,.rar,.ppt,.pptx,.csv,.odt,.rtf,.7z,.tar.gz',
                            maxSize: 50 * 1024 * 1024, // 50 МБ
                            onDrop: onDropCallback,
                            onError: onErrorCallback
                        });
                        
                        container._dragNDropFieldInstance = dragNDropField;
                        cleanFileInput.classList.add('consta-dragndrop-initialized');
                    } else {
                    }
                } else {
                }
            }
        }, 100);
    });
}



function showHealthForm(empId, existingRecord = null, isHistoryEdit = false, historyIndex = null) {
    $.get(`/api/employee/${empId}`).done(emp => {
        const today = new Date().toISOString().split('T')[0];
        
        const dateValue = existingRecord ? existingRecord.date : today;
        const commentValue = existingRecord ? existingRecord.comment : '';
        const recoveredDateValue = existingRecord && existingRecord.recovered_date ? existingRecord.recovered_date : '';
        
        // Преобразуем дату из YYYY-MM-DD в дд.мм.гггг для отображения
        function formatDateForInput(dateStr) {
            if (!dateStr) return '';
            try {
                const parts = dateStr.split('-');
                if (parts.length === 3) {
                    return `${parts[2]}.${parts[1]}.${parts[0]}`;
                }
                return dateStr;
            } catch (e) {
                return dateStr;
            }
        }
        
        // Убеждаемся, что для новой записи используется текущая дата
        let finalDateValue = dateValue;
        if (!existingRecord && (!finalDateValue || finalDateValue === '')) {
            finalDateValue = today;
        }
        
        const dateDisplayValue = formatDateForInput(finalDateValue);
        const recoveredDateDisplayValue = formatDateForInput(recoveredDateValue);
        
        let html = `
            <div class="mb-3">
                <label class="form-label">Дата начала заболевания</label>
                <input type="text" class="form-control" id="health_date" value="${dateDisplayValue}" placeholder="дд.мм.гггг" autocomplete="off">
            </div>
            <div class="mb-3">
                <label class="form-label">Комментарий</label>
                <textarea class="form-control" id="health_comment" rows="3" placeholder="Опишите заболевание, симптомы, назначенное лечение и т.д.">${escapeHtml(commentValue)}</textarea>
            </div>
        `;
        
        if (isHistoryEdit) {
            html += `
                <div class="mb-3">
                    <label class="form-label">Дата выздоровления</label>
                    <input type="text" class="form-control" id="health_recovered_date" value="${recoveredDateDisplayValue}" placeholder="дд.мм.гггг" autocomplete="off">
                    <small class="form-text text-muted">Оставьте пустым, если студент еще не выздоровел</small>
                </div>
            `;
        }
        
        $('#healthFormModal').remove();
        
        const modalTitle = existingRecord ? 'Редактировать запись о здоровье' : 'Добавить запись о здоровье';
        const saveFunction = isHistoryEdit && historyIndex !== null 
            ? `saveHealthHistoryRecord(${empId}, ${historyIndex})`
            : `saveHealthRecord(${empId})`;
        
        const modal = $(`
            <div class="modal" id="healthFormModal" tabindex="-1" style="display: none;">
                <div class="modal-dialog modal-lg" style="max-width: 900px !important; width: 900px !important; margin: 1.75rem auto !important; transform: none !important; transition: none !important;">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">${modalTitle}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">${html}</div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                            <button type="button" class="btn btn-primary" onclick="${saveFunction}">Сохранить</button>
                        </div>
                    </div>
                </div>
            </div>
        `);
        
        $('body').append(modal);
        
        const modalEl = $('#healthFormModal');
        const dialog = modalEl.find('.modal-dialog');
        dialog.css({
            'max-width': '900px !important',
            'width': '900px !important',
            'transform': 'none !important',
            'transition': 'none !important',
            'margin': '1.75rem auto !important'
        });
        
        const dialogEl = modalEl[0].querySelector('.modal-dialog');
        if (dialogEl) {
            dialogEl.style.setProperty('max-width', '900px', 'important');
            dialogEl.style.setProperty('width', '900px', 'important');
            dialogEl.style.setProperty('transform', 'none', 'important');
            dialogEl.style.setProperty('transition', 'none', 'important');
            dialogEl.style.setProperty('margin', '1.75rem auto', 'important');
        }
        
        modalEl.off('show.bs.modal shown.bs.modal hide.bs.modal hidden.bs.modal');
        
        modalEl.on('show.bs.modal', function() {
            const d = $(this).find('.modal-dialog');
            d.css({
                'max-width': '900px !important',
                'width': '900px !important',
                'transform': 'none !important',
                'transition': 'none !important',
                'margin': '1.75rem auto !important'
            });
            
            const dEl = this.querySelector('.modal-dialog');
            if (dEl) {
                dEl.style.setProperty('max-width', '900px', 'important');
                dEl.style.setProperty('width', '900px', 'important');
                dEl.style.setProperty('transform', 'none', 'important');
                dEl.style.setProperty('transition', 'none', 'important');
                dEl.style.setProperty('margin', '1.75rem auto', 'important');
            }
        });
        
        modalEl.on('hide.bs.modal hidden.bs.modal', function() {
            const d = $(this).find('.modal-dialog');
            d.css({
                'max-width': '900px !important',
                'width': '900px !important',
                'transform': 'none !important',
                'transition': 'none !important'
            });
            
            const dEl = this.querySelector('.modal-dialog');
            if (dEl) {
                dEl.style.setProperty('max-width', '900px', 'important');
                dEl.style.setProperty('width', '900px', 'important');
                dEl.style.setProperty('transform', 'none', 'important');
                dEl.style.setProperty('transition', 'none', 'important');
            }
        });
        
        setTimeout(function() {
            modalEl.modal('show');
            
            // Инициализируем flatpickr для полей даты после показа модального окна
            setTimeout(function() {
                if (typeof flatpickr !== 'undefined') {
                    const locale = flatpickr.l10ns?.ru || {
                        firstDayOfWeek: 1,
                        weekdays: { shorthand: ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'], longhand: ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'] },
                        months: { shorthand: ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек'], longhand: ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'] }
                    };
                    
                    // Функция для преобразования дд.мм.гггг в YYYY-MM-DD
                    function parseDateToISO(dateStr) {
                        if (!dateStr || !dateStr.trim()) return null;
                        const match = dateStr.trim().match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
                        if (match) {
                            const [, d, m, y] = match;
                            const dayNum = parseInt(d, 10);
                            const monthNum = parseInt(m, 10);
                            const yearNum = parseInt(y, 10);
                            if (dayNum >= 1 && dayNum <= 31 && monthNum >= 1 && monthNum <= 12 && yearNum >= 1900 && yearNum <= 2100) {
                                return `${yearNum}-${String(monthNum).padStart(2, '0')}-${String(dayNum).padStart(2, '0')}`;
                            }
                        }
                        return null;
                    }
                    
                    const dateConfig = {
                        dateFormat: 'd.m.Y',
                        locale: locale,
                        allowInput: true,
                        static: false,
                        monthSelectorType: 'static', // Статический выбор месяца (не dropdown)
                        appendTo: document.body, // Добавляем календарь в body, чтобы он не скрывался за модальным окном
                        zIndex: 10060, // Высокий z-index для отображения поверх модального окна (Bootstrap modal имеет z-index 1055)
                        onOpen: function(selectedDates, dateStr, instance) {
                            // Убеждаемся, что календарь отображается поверх модального окна
                            const calendar = instance.calendarContainer;
                            if (calendar) {
                                calendar.style.zIndex = '10060';
                                calendar.style.position = 'fixed';
                            }
                        },
                        onChange: function(selectedDates, dateStr, instance) {
                            // Обновляем значение input при изменении
                            if (selectedDates.length > 0 && dateStr) {
                                instance.input.value = dateStr;
                                $(instance.input).val(dateStr);
                            } else {
                                instance.input.value = '';
                                $(instance.input).val('');
                            }
                        }
                    };
                    
                    const healthDateInput = document.getElementById('health_date');
                    if (healthDateInput && !healthDateInput._flatpickr) {
                        // Создаем отдельную копию конфигурации для этого поля
                        const healthDateConfig = { ...dateConfig };
                        
                        const currentValue = healthDateInput.value;
                        let defaultDateValue = null;
                        
                        if (currentValue && currentValue.trim() !== '') {
                            const isoDate = parseDateToISO(currentValue);
                            if (isoDate) {
                                defaultDateValue = isoDate;
                            }
                        }
                        
                        // Если значение пустое или не удалось распарсить, используем текущую дату
                        // Также проверяем, что значение не равно 20.05.2025 (возможная ошибка)
                        if (!defaultDateValue || currentValue === '20.05.2025') {
                            const today = new Date();
                            defaultDateValue = today.getFullYear() + '-' + 
                                String(today.getMonth() + 1).padStart(2, '0') + '-' + 
                                String(today.getDate()).padStart(2, '0');
                            // Обновляем значение в поле ввода текущей датой
                            const formattedDate = defaultDateValue.split('-').reverse().join('.');
                            healthDateInput.value = formattedDate;
                            $(healthDateInput).val(formattedDate);
                        }
                        
                        // Всегда устанавливаем defaultDate для flatpickr
                        healthDateConfig.defaultDate = defaultDateValue;
                        
                        const fp = flatpickr(healthDateInput, healthDateConfig);
                        
                        // Принудительно устанавливаем дату после инициализации
                        if (fp && defaultDateValue) {
                            // Устанавливаем дату сразу
                            fp.setDate(defaultDateValue, false);
                            const formattedDate = defaultDateValue.split('-').reverse().join('.');
                            healthDateInput.value = formattedDate;
                            $(healthDateInput).val(formattedDate);
                            
                            // Дополнительная проверка через небольшую задержку
                            setTimeout(() => {
                                const currentValue = healthDateInput.value.trim();
                                const expectedValue = formattedDate;
                                if (currentValue !== expectedValue && currentValue !== '20.05.2025') {
                                    fp.setDate(defaultDateValue, false);
                                    healthDateInput.value = expectedValue;
                                    $(healthDateInput).val(expectedValue);
                                }
                            }, 50);
                        }
                    }
                    
                    const recoveredDateInput = document.getElementById('health_recovered_date');
                    if (recoveredDateInput && !recoveredDateInput._flatpickr) {
                        // Создаем отдельную копию конфигурации для этого поля
                        const recoveredDateConfig = { ...dateConfig };
                        
                        const currentValue = recoveredDateInput.value;
                        if (currentValue && currentValue.trim() !== '') {
                            const isoDate = parseDateToISO(currentValue);
                            if (isoDate) {
                                recoveredDateConfig.defaultDate = isoDate;
                            }
                        }
                        // Для поля выздоровления не устанавливаем дефолтную дату, если оно пустое
                        flatpickr(recoveredDateInput, recoveredDateConfig);
                    }
                }
            }, 100);
        }, 10);
        
        modalEl.on('hidden.bs.modal', function () { $(this).remove(); });
    });
}

function saveHealthRecord(empId) {
    let date = $('#health_date').val();
    const comment = $('#health_comment').val().trim();
    
    // Преобразуем дату из дд.мм.гггг в YYYY-MM-DD
    if (date) {
        const match = date.trim().match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
        if (match) {
            const [, d, m, y] = match;
            const dayNum = parseInt(d, 10);
            const monthNum = parseInt(m, 10);
            const yearNum = parseInt(y, 10);
            if (dayNum >= 1 && dayNum <= 31 && monthNum >= 1 && monthNum <= 12 && yearNum >= 1900 && yearNum <= 2100) {
                date = `${yearNum}-${String(monthNum).padStart(2, '0')}-${String(dayNum).padStart(2, '0')}`;
            } else {
                alert('Ошибка: Неверный формат даты. Используйте формат дд.мм.гггг');
                return;
            }
        } else if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
            alert('Ошибка: Неверный формат даты. Используйте формат дд.мм.гггг');
            return;
        }
    }
    
    if (!date) {
        alert('Ошибка: Необходимо указать дату начала заболевания');
        return;
    }
    
    $.get(`/api/employee/${empId}`).done(emp => {
        const extra = emp.extra_data || {};
        const health = extra.health_info || { current: null, history: [] };
        
        health.current = {
            date: date,
            comment: comment,
            is_ill: true
        };
        
        extra.health_info = health;
        
        const payload = {
            fio: emp.fio,
            phone: emp.phone || '',
            group_name: emp.group_name || '',
            birth_date: emp.birth_date || '',
            notes: emp.notes || '',
            absences: emp.absences || '',
            reprimands: emp.reprimands || '',
            vacation: emp.vacation || '',
            extra: extra,
            representatives: emp.representatives || []
        };
        
        $.ajax({
            url: `/api/admin/employee/${empId}`,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(payload),
            success: () => {
                $('#healthFormModal').modal('hide');
                alert('Запись о здоровье сохранена!');
                $.get(`/api/employee/${empId}`).done(emp => {
                    showEmployeeModal(emp, true);
                    loadEmployees($('#admin_search').val().trim(), 'admin_');
                });
            },
            error: (xhr) => {
                let msg = 'Не удалось сохранить запись о здоровье';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    msg = `Ошибка сохранения записи о здоровье: ${xhr.responseJSON.error}`;
                } else if (xhr.status === 401) {
                    msg = 'Ошибка: У вас нет прав для сохранения записей о здоровье';
                } else if (xhr.status === 404) {
                    msg = 'Ошибка: Студент не найден';
                } else if (xhr.status >= 500) {
                    msg = 'Ошибка сервера при сохранении записи о здоровье. Попробуйте позже';
                }
                alert(msg);
            }
        });
    });
}

function editCurrentHealthRecord(empId) {
    $.get(`/api/employee/${empId}`).done(emp => {
        const extra = emp.extra_data || {};
        const health = extra.health_info || { current: null, history: [] };
        const current = health.current;
        
        if (!current || !current.is_ill) {
            alert('Ошибка: Нет активной записи о заболевании для редактирования. Добавьте запись о здоровье сначала.');
            return;
        }
        
        showHealthForm(empId, current, false, null);
    });
}

function editHealthHistoryRecord(empId, historyIndex) {
    $.get(`/api/employee/${empId}`).done(emp => {
        const extra = emp.extra_data || {};
        const health = extra.health_info || { current: null, history: [] };
        const history = health.history || [];
        
        if (historyIndex < 0 || historyIndex >= history.length) {
            alert('Ошибка: Запись о здоровье не найдена. Возможно, она была удалена.');
            return;
        }
        
        const record = history[historyIndex];
        showHealthForm(empId, record, true, historyIndex);
    });
}

function saveHealthHistoryRecord(empId, historyIndex) {
    let date = $('#health_date').val();
    const comment = $('#health_comment').val().trim();
    let recoveredDate = $('#health_recovered_date').val();
    
    // Преобразуем дату из дд.мм.гггг в YYYY-MM-DD
    if (date) {
        const match = date.trim().match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
        if (match) {
            const [, d, m, y] = match;
            const dayNum = parseInt(d, 10);
            const monthNum = parseInt(m, 10);
            const yearNum = parseInt(y, 10);
            if (dayNum >= 1 && dayNum <= 31 && monthNum >= 1 && monthNum <= 12 && yearNum >= 1900 && yearNum <= 2100) {
                date = `${yearNum}-${String(monthNum).padStart(2, '0')}-${String(dayNum).padStart(2, '0')}`;
            } else {
                alert('Ошибка: Неверный формат даты начала заболевания. Используйте формат дд.мм.гггг');
                return;
            }
        } else if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
            alert('Ошибка: Неверный формат даты начала заболевания. Используйте формат дд.мм.гггг');
            return;
        }
    }
    
    // Преобразуем дату выздоровления из дд.мм.гггг в YYYY-MM-DD
    if (recoveredDate && recoveredDate.trim()) {
        const match = recoveredDate.trim().match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
        if (match) {
            const [, d, m, y] = match;
            const dayNum = parseInt(d, 10);
            const monthNum = parseInt(m, 10);
            const yearNum = parseInt(y, 10);
            if (dayNum >= 1 && dayNum <= 31 && monthNum >= 1 && monthNum <= 12 && yearNum >= 1900 && yearNum <= 2100) {
                recoveredDate = `${yearNum}-${String(monthNum).padStart(2, '0')}-${String(dayNum).padStart(2, '0')}`;
            } else {
                alert('Ошибка: Неверный формат даты выздоровления. Используйте формат дд.мм.гггг');
                return;
            }
        } else if (!/^\d{4}-\d{2}-\d{2}$/.test(recoveredDate)) {
            alert('Ошибка: Неверный формат даты выздоровления. Используйте формат дд.мм.гггг');
            return;
        }
    }
    
    if (!date) {
        alert('Ошибка: Необходимо указать дату начала заболевания');
        return;
    }
    
    $.get(`/api/employee/${empId}`).done(emp => {
        const extra = emp.extra_data || {};
        const health = extra.health_info || { current: null, history: [] };
        
        if (!health.history) {
            health.history = [];
        }
        
        if (historyIndex < 0 || historyIndex >= health.history.length) {
            alert('Ошибка: Запись о здоровье не найдена. Возможно, она была удалена.');
            return;
        }
        
        health.history[historyIndex] = {
            date: date,
            comment: comment,
            recovered_date: recoveredDate || null
        };
        
        extra.health_info = health;
        
        const payload = {
            fio: emp.fio,
            phone: emp.phone || '',
            group_name: emp.group_name || '',
            birth_date: emp.birth_date || '',
            notes: emp.notes || '',
            absences: emp.absences || '',
            reprimands: emp.reprimands || '',
            vacation: emp.vacation || '',
            extra: extra,
            representatives: emp.representatives || []
        };
        
        $.ajax({
            url: `/api/admin/employee/${empId}`,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(payload),
            success: () => {
                $('#healthFormModal').modal('hide');
                $('#healthHistoryModal').modal('hide');
                alert('Запись о здоровье обновлена!');
                $.get(`/api/employee/${empId}`).done(emp => {
                    showEmployeeModal(emp, true);
                    loadEmployees($('#admin_search').val().trim(), 'admin_');
                });
            },
            error: (xhr) => {
                let msg = 'Не удалось сохранить запись о здоровье';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    msg = `Ошибка сохранения записи о здоровье: ${xhr.responseJSON.error}`;
                } else if (xhr.status === 401) {
                    msg = 'Ошибка: У вас нет прав для сохранения записей о здоровье';
                } else if (xhr.status === 404) {
                    msg = 'Ошибка: Студент не найден';
                } else if (xhr.status >= 500) {
                    msg = 'Ошибка сервера при сохранении записи о здоровье. Попробуйте позже';
                }
                alert(msg);
            }
        });
    });
}

function continueHealthRecord(empId) {
    // Создаем кастомное модальное окно вместо системного prompt
    $('#continueHealthModal').remove();
    
    const modal = $(`
        <div class="modal fade" id="continueHealthModal" tabindex="-1" aria-hidden="true">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Продолжить запись о заболевании</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Закрыть"></button>
                    </div>
                    <div class="modal-body">
                        <div class="mb-3">
                            <label class="form-label">Дополнительная информация о заболевании</label>
                            <textarea class="form-control" id="continue_health_comment" rows="4" placeholder="Введите дополнительную информацию о заболевании..."></textarea>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                        <button type="button" class="btn btn-primary" id="continueHealthSaveBtn">Сохранить</button>
                    </div>
                </div>
            </div>
        </div>
    `);
    
    $('body').append(modal);
    
    const modalEl = $('#continueHealthModal');
    const modalInstance = new bootstrap.Modal(modalEl[0], {});
    modalInstance.show();
    
    // Фокус на поле ввода
    setTimeout(() => {
        $('#continue_health_comment').focus();
    }, 300);
    
    // Обработчик сохранения
    $('#continueHealthSaveBtn').off('click').on('click', function() {
        const comment = $('#continue_health_comment').val().trim();
        if (!comment) {
            alert('Ошибка: Необходимо ввести дополнительную информацию о заболевании');
            return;
        }
        
        modalInstance.hide();
        performContinueHealthRecord(empId, comment);
    });
    
    // Обработчик Enter в textarea
    $('#continue_health_comment').off('keydown').on('keydown', function(e) {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            $('#continueHealthSaveBtn').click();
        }
    });
    
    // Удаляем модальное окно после закрытия
    modalEl.on('hidden.bs.modal', function() {
        $(this).remove();
    });
}

function performContinueHealthRecord(empId, comment) {
    
    $.get(`/api/employee/${empId}`).done(emp => {
        const extra = emp.extra_data || {};
        const health = extra.health_info || { current: null, history: [] };
        
        if (!health.current || !health.current.is_ill) {
            alert('Ошибка: Нет активной записи о заболевании для продолжения.');
            return;
        }
        
        if (!health.current.continuations) {
            health.current.continuations = [];
        }
        
        const today = new Date().toISOString().split('T')[0];
        health.current.continuations.push({
            date: today,
            comment: comment.trim()
        });
        
        extra.health_info = health;
        
        const payload = {
            fio: emp.fio,
            phone: emp.phone || '',
            group_name: emp.group_name || '',
            birth_date: emp.birth_date || '',
            notes: emp.notes || '',
            absences: emp.absences || '',
            reprimands: emp.reprimands || '',
            vacation: emp.vacation || '',
            extra: extra,
            representatives: emp.representatives || []
        };
        
        $.ajax({
            url: `/api/admin/employee/${empId}`,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(payload),
            success: () => {
                alert('Продолжение записи добавлено!');
                $.get(`/api/employee/${empId}`).done(emp => {
                    showEmployeeModal(emp, true);
                    loadEmployees($('#admin_search').val().trim(), 'admin_');
                });
            },
            error: (xhr) => {
                let msg = 'Не удалось добавить продолжение записи';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    msg = `Ошибка: ${xhr.responseJSON.error}`;
                }
                alert(msg);
            }
        });
    });
}

function markRecovered(empId) {
    if (typeof showBannerConfirm !== 'undefined') {
        showBannerConfirm(
            'Отметить студента как выздоровевшего?',
            () => {
                performMarkRecovered(empId);
            },
            () => {
            }
        );
    } else {
        // Используем кастомное модальное окно вместо системного confirm
        showBannerConfirm(
            'Отметить студента как выздоровевшего?',
            () => {
                performMarkRecovered(empId);
            }
        );
    }
}

function performMarkRecovered(empId) {
    $.get(`/api/employee/${empId}`).done(emp => {
        const extra = emp.extra_data || {};
        const health = extra.health_info || { current: null, history: [] };
        
        if (health.current && health.current.is_ill) {
            if (!health.history) health.history = [];
            const today = new Date().toISOString().split('T')[0];
            
            const continuations = health.current.continuations || [];
            let fullComment = health.current.comment || '';
            
            if (continuations.length > 0) {
                fullComment += '\n\n';
                continuations.forEach((cont, index) => {
                    const contDate = cont.date ? (() => {
                        const [y, m, d] = cont.date.split('-');
                        return `${d}.${m}.${y}`;
                    })() : '';
                    fullComment += `${contDate}: ${cont.comment}`;
                    if (index < continuations.length - 1) {
                        fullComment += '\n';
                    }
                });
            }
            
            health.history.push({
                date: health.current.date,
                comment: fullComment,
                recovered_date: today,
                continuations: continuations // Сохраняем также для возможного отображения
            });
            
            health.current = null;
            extra.health_info = health;
            
            const payload = {
                fio: emp.fio,
                phone: emp.phone || '',
                group_name: emp.group_name || '',
                birth_date: emp.birth_date || '',
                notes: emp.notes || '',
                absences: emp.absences || '',
                reprimands: emp.reprimands || '',
                vacation: emp.vacation || '',
                extra: extra,
                representatives: emp.representatives || []
            };
            
            $.ajax({
                url: `/api/admin/employee/${empId}`,
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify(payload),
                success: () => {
                    if (typeof showBannerSuccess !== 'undefined') {
                        showBannerSuccess('Студент отмечен как выздоровевший!');
                    } else {
                        alert('Студент отмечен как выздоровевший!');
                    }
                    $.get(`/api/employee/${empId}`).done(emp => {
                        showEmployeeModal(emp, true);
                        loadEmployees($('#admin_search').val().trim(), 'admin_');
                    });
                },
                error: (xhr) => {
                    let msg = 'Не удалось отметить студента как выздоровевшего';
                    if (xhr.responseJSON && xhr.responseJSON.error) {
                        msg = `Ошибка при отметке выздоровления: ${xhr.responseJSON.error}`;
                    } else if (xhr.status === 401) {
                        msg = 'Ошибка: У вас нет прав для выполнения этого действия';
                    } else if (xhr.status === 404) {
                        msg = 'Ошибка: Студент не найден';
                    } else if (xhr.status >= 500) {
                        msg = 'Ошибка сервера при отметке выздоровления. Попробуйте позже';
                    }
                    if (typeof showBannerError !== 'undefined') {
                        showBannerError(msg);
                    } else {
                        alert(msg);
                    }
                }
            });
        }
    });
}

function showHealthHistoryFromButton(button) {
    try {
        
        let historyData = $(button).data('history');
        
        if (!historyData || (typeof historyData === 'string' && historyData.trim() === '')) {
            const historyAttr = $(button).attr('data-history');
            if (historyAttr) {
                try {
                    const decoded = historyAttr.replace(/&#39;/g, "'").replace(/&quot;/g, '"');
                    historyData = JSON.parse(decoded);
                } catch (e) {
                    try {
                        historyData = JSON.parse(historyAttr);
                    } catch (e2) {
                    }
                }
            }
        }
        
        let empId = $(button).data('emp-id') || $(button).data('empId');
        
        if (!empId) {
            const empIdAttr = $(button).attr('data-emp-id');
            if (empIdAttr) {
                empId = parseInt(empIdAttr);
            }
        }
        
        if (typeof historyData === 'string') {
            try {
                historyData = JSON.parse(historyData);
            } catch (e) {
                historyData = [];
            }
        }
        
        if (!historyData || !Array.isArray(historyData)) {
            historyData = [];
        }
        
        
        if (typeof showHealthHistory === 'function') {
            showHealthHistory(historyData, empId);
        } else {
            alert('Ошибка: функция показа истории здоровья не найдена. Обновите страницу.');
        }
    } catch (e) {
        alert('Ошибка при открытии истории здоровья. Не удалось загрузить данные. Попробуйте позже или обновите страницу.');
    }
}

function showHealthHistory(history, empId = null) {
    if (!history || !Array.isArray(history)) {
        if (typeof history === 'string') {
            try {
                history = JSON.parse(history);
            } catch (e) {
                history = [];
            }
        } else {
            history = [];
        }
    }
    
    let list = '';
    if (history.length === 0) {
        list = '<p class="text-muted">История здоровья пуста</p>';
    } else {
        list = '<ul class="list-group">';
        const reversed = [...history].reverse();
        reversed.forEach((item, index) => {
            const startDate = item.date ? (() => {
                const [y, m, d] = item.date.split('-');
                return `${d}.${m}.${y}`;
            })() : '—';
            const recoveredDate = item.recovered_date ? (() => {
                const [y, m, d] = item.recovered_date.split('-');
                return `${d}.${m}.${y}`;
            })() : null;
            
            const originalIndex = history.length - 1 - index;
            const editButton = empId ? `
                <button type="button" class="btn btn-sm btn-outline-primary" onclick="editHealthHistoryRecord(${empId}, ${originalIndex})" title="Редактировать">
                    <i class="bi bi-pencil"></i>
                </button>
            ` : '';
            
            let commentHtml = '';
            if (item.comment) {
                const continuations = item.continuations || [];
                if (continuations.length > 0 && item.comment.includes('\n\n')) {
                    const parts = item.comment.split('\n\n');
                    commentHtml = `<div class="mt-1"><strong>Начальный комментарий:</strong> ${escapeHtml(parts[0])}</div>`;
                    if (parts.length > 1) {
                        commentHtml += `<div class="mt-2"><strong>Продолжения:</strong><ul class="mb-0 mt-1 small">`;
                        continuations.forEach(cont => {
                            const contDate = cont.date ? (() => {
                                const [y, m, d] = cont.date.split('-');
                                return `${d}.${m}.${y}`;
                            })() : '';
                            commentHtml += `<li><strong>${contDate}:</strong> ${escapeHtml(cont.comment || '')}</li>`;
                        });
                        commentHtml += '</ul></div>';
                    }
                } else {
                    commentHtml = `<div class="mt-1"><strong>Комментарий:</strong> ${escapeHtml(String(item.comment))}</div>`;
                }
            }
            
            list += `<li class="list-group-item" data-emp-id="${empId || ''}">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <strong>Заболевание ${history.length - index}:</strong>
                        <div class="mt-2">
                            <div><strong>Начало:</strong> ${startDate}</div>
                            ${recoveredDate ? `<div><strong>Выздоровление:</strong> ${recoveredDate}</div>` : '<div class="text-danger"><strong>Не выздоровел</strong></div>'}
                            ${commentHtml}
                        </div>
                    </div>
                    ${editButton}
                </div>
            </li>`;
        });
        list += '</ul>';
    }
    
    $('#healthHistoryModal').remove();
    
    const modal = $(`
        <div class="modal" id="healthHistoryModal" tabindex="-1" aria-hidden="true" style="display: none;">
            <div class="modal-dialog modal-lg" style="max-width: 900px !important; width: 900px !important; margin: 1.75rem auto !important; transform: none !important; transition: none !important;">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">История здоровья</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Закрыть"></button>
                    </div>
                    <div class="modal-body">${list}</div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Закрыть</button>
                    </div>
                </div>
            </div>
        </div>
    `);
    
    $('body').append(modal);
    
    const modalEl = $('#healthHistoryModal');
    const dialog = modalEl.find('.modal-dialog');
    dialog.css({
        'max-width': '900px !important',
        'width': '900px !important',
        'transform': 'none !important',
        'transition': 'none !important',
        'margin': '1.75rem auto !important'
    });
    
    const dialogEl = modalEl[0].querySelector('.modal-dialog');
    if (dialogEl) {
        dialogEl.style.setProperty('max-width', '900px', 'important');
        dialogEl.style.setProperty('width', '900px', 'important');
        dialogEl.style.setProperty('transform', 'none', 'important');
        dialogEl.style.setProperty('transition', 'none', 'important');
        dialogEl.style.setProperty('margin', '1.75rem auto', 'important');
    }
    
    modalEl.off('show.bs.modal shown.bs.modal hide.bs.modal hidden.bs.modal');
    
    modalEl.on('show.bs.modal', function() {
        const d = $(this).find('.modal-dialog');
        d.css({
            'max-width': '900px !important',
            'width': '900px !important',
            'transform': 'none !important',
            'transition': 'none !important',
            'margin': '1.75rem auto !important'
        });
        
        const dEl = this.querySelector('.modal-dialog');
        if (dEl) {
            dEl.style.setProperty('max-width', '900px', 'important');
            dEl.style.setProperty('width', '900px', 'important');
            dEl.style.setProperty('transform', 'none', 'important');
            dEl.style.setProperty('transition', 'none', 'important');
            dEl.style.setProperty('margin', '1.75rem auto', 'important');
        }
    });
    
    modalEl.on('hide.bs.modal hidden.bs.modal', function() {
        const d = $(this).find('.modal-dialog');
        d.css({
            'max-width': '900px !important',
            'width': '900px !important',
            'transform': 'none !important',
            'transition': 'none !important'
        });
        
        const dEl = this.querySelector('.modal-dialog');
        if (dEl) {
            dEl.style.setProperty('max-width', '900px', 'important');
            dEl.style.setProperty('width', '900px', 'important');
            dEl.style.setProperty('transform', 'none', 'important');
            dEl.style.setProperty('transition', 'none', 'important');
        }
    });
    
    setTimeout(function() {
        const modalInstance = new bootstrap.Modal(document.getElementById('healthHistoryModal'), {});
        modalInstance.show();
    }, 10);
    
    modalEl.on('hidden.bs.modal', function () { 
        $(this).remove(); 
    });
}


function parseDateTimeValue(value) {
    if (!value) {
        return { date: '', time: '' };
    }
    const parts = value.trim().split(/\s+/);
    const date = parts[0] || '';
    const time = parts[1] || '';
    return { date, time };
}

function editVacationForm(empId) {
    $.get(`/api/employee/${empId}`).done(emp => {
        const vacation = emp.vacation || '';
        const parsed = parseVacation(vacation);
        
        const startValue = parsed.startDateTime || '';
        const endValue = parsed.endDateTime || '';
        let html = `
            <div class="row g-3 consta-datetime-grid">
                <div class="col-md-6">
                    <label for="vac_start_datetime" class="form-label">Начало</label>
                    <input type="text" class="form-control consta-datetime-input" id="vac_start_datetime" name="vac_start_datetime" autocomplete="off" placeholder="Выберите дату и время" value="${startValue}" aria-label="Дата и время начала заявления">
                </div>
                <div class="col-md-6">
                    <label for="vac_end_datetime" class="form-label">Окончание</label>
                    <input type="text" class="form-control consta-datetime-input" id="vac_end_datetime" name="vac_end_datetime" autocomplete="off" placeholder="Выберите дату и время" value="${endValue}" aria-label="Дата и время окончания заявления">
                </div>
            </div>
            <div class="mb-3">
                <label for="vac_preview" class="form-label">Предварительный просмотр</label>
                <input type="text" class="form-control" id="vac_preview" name="vac_preview" readonly style="background-color: #f8f9fa;" aria-label="Предварительный просмотр заявления">
            </div>
        `;
        
        const updatePreview = () => {
            const startParts = parseDateTimeValue($('#vac_start_datetime').val());
            const endParts = parseDateTimeValue($('#vac_end_datetime').val());
            const preview = formatVacation(startParts.time, startParts.date, endParts.time, endParts.date);
            $('#vac_preview').val(preview || '(заполните все поля)');
        };
        
        $('#vacationFormModal').remove();
        
        const modal = $(`
            <div class="modal" id="vacationFormModal" tabindex="-1" style="display: none;">
                <div class="modal-dialog modal-xl" style="max-width: 1000px !important; width: 1000px !important; margin: 1.75rem auto !important; transform: none !important; transition: none !important;">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">${vacation ? 'Редактировать' : 'Добавить'} заявление</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">${html}</div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                            <button type="button" class="btn btn-primary" onclick="saveVacation(${empId})">Сохранить</button>
                        </div>
                    </div>
                </div>
            </div>
        `);
        
        $('body').append(modal);
        
        const vacationModalElement = document.getElementById('vacationFormModal');
        const vacationDialog = vacationModalElement.querySelector('.modal-dialog');
        
        if (vacationDialog) {
            vacationDialog.style.setProperty('max-width', '1000px', 'important');
            vacationDialog.style.setProperty('width', '1000px', 'important');
            vacationDialog.style.setProperty('transform', 'none', 'important');
            vacationDialog.style.setProperty('transition', 'none', 'important');
            vacationDialog.style.setProperty('margin', '1.75rem auto', 'important');
        }
        
        $('#vacationFormModal').on('show.bs.modal', function() {
            const dialog = $(this).find('.modal-dialog');
            dialog.css({
                'max-width': '1000px !important',
                'width': '1000px !important',
                'transform': 'none !important',
                'transition': 'none !important',
                'margin': '1.75rem auto !important'
            });
            
            const dialogEl = this.querySelector('.modal-dialog');
            if (dialogEl) {
                dialogEl.style.setProperty('max-width', '1000px', 'important');
                dialogEl.style.setProperty('width', '1000px', 'important');
                dialogEl.style.setProperty('transform', 'none', 'important');
                dialogEl.style.setProperty('transition', 'none', 'important');
                dialogEl.style.setProperty('margin', '1.75rem auto', 'important');
            }
        });
        
        $('#vacationFormModal').on('hide.bs.modal', function() {
            const dialog = $(this).find('.modal-dialog');
            dialog.css({
                'max-width': '1000px !important',
                'width': '1000px !important',
                'transform': 'none !important',
                'transition': 'none !important'
            });
            
            const dialogEl = this.querySelector('.modal-dialog');
            if (dialogEl) {
                dialogEl.style.setProperty('max-width', '1000px', 'important');
                dialogEl.style.setProperty('width', '1000px', 'important');
                dialogEl.style.setProperty('transform', 'none', 'important');
                dialogEl.style.setProperty('transition', 'none', 'important');
            }
        });
        
        $('#vacationFormModal').on('hidden.bs.modal', function() {
            const dialog = $(this).find('.modal-dialog');
            dialog.css({
                'max-width': '1000px !important',
                'width': '1000px !important',
                'transform': 'none !important',
                'transition': 'none !important'
            });
            
            const dialogEl = this.querySelector('.modal-dialog');
            if (dialogEl) {
                dialogEl.style.setProperty('max-width', '1000px', 'important');
                dialogEl.style.setProperty('width', '1000px', 'important');
                dialogEl.style.setProperty('transform', 'none', 'important');
                dialogEl.style.setProperty('transition', 'none', 'important');
            }
        });
        
        $('#vacationFormModal').on('shown.bs.modal', function () {
            const datetimeOptions = {
                enableTime: true,
                dateFormat: 'd.m.Y H:i',
                time_24hr: true,
                allowInput: true,
                minuteIncrement: 5,
                onChange: updatePreview
            };
            if (typeof flatpickr !== 'undefined' && flatpickr.l10ns && flatpickr.l10ns.ru) {
                datetimeOptions.locale = flatpickr.l10ns.ru;
            }
            
            const initDateTimePicker = (selector) => {
                if (window.ConstaDatePicker && window.ConstaDatePicker.initElement) {
                    return ConstaDatePicker.initElement(selector, datetimeOptions);
                }
                if (typeof flatpickr !== 'undefined') {
                    return flatpickr(selector, datetimeOptions);
                }
                return null;
            };
            
            initDateTimePicker('#vac_start_datetime');
            initDateTimePicker('#vac_end_datetime');
            $('#vac_start_datetime, #vac_end_datetime').on('change input', updatePreview);
            updatePreview();
            
            const dialogEl = this.querySelector('.modal-dialog');
            if (dialogEl) {
                dialogEl.style.setProperty('max-width', '1000px', 'important');
                dialogEl.style.setProperty('width', '1000px', 'important');
                dialogEl.style.setProperty('transform', 'none', 'important');
                dialogEl.style.setProperty('transition', 'none', 'important');
            }
        });
        
        $('#vacationFormModal').on('hidden.bs.modal', function () { 
            $(this).remove(); 
        });
        
        setTimeout(() => {
            const vacationModal = new bootstrap.Modal(vacationModalElement, {
                backdrop: 'static',
                keyboard: true
            });
            vacationModal.show();
        }, 10);
    });
}

function saveVacation(empId) {
    const startParts = parseDateTimeValue($('#vac_start_datetime').val());
    const endParts = parseDateTimeValue($('#vac_end_datetime').val());
    
    if (!startParts.time || !startParts.date || !endParts.time || !endParts.date) {
        alert('Ошибка: Заполните все поля формы (время и дата начала и окончания заявления)');
        return;
    }
    
    const vacationText = formatVacation(startParts.time, startParts.date, endParts.time, endParts.date);
    
    if (!vacationText) {
        alert('Ошибка: Не удалось сформировать текст заявления. Проверьте формат даты и времени.\n' +
              `Начало: дата="${startParts.date}", время="${startParts.time}"\n` +
              `Окончание: дата="${endParts.date}", время="${endParts.time}"`);
        return;
    }
    
    $.get(`/api/employee/${empId}`).done(emp => {
        const payload = {
            fio: emp.fio,
            phone: emp.phone || '',
            group_name: emp.group_name || '',
            birth_date: emp.birth_date || '',
            building: emp.building || '',
            room_number: emp.room_number || '',
            entrance: emp.entrance || '',
            notes: emp.notes || '',
            absences: emp.absences || '',
            reprimands: emp.reprimands || '',
            vacation: vacationText,
            extra: emp.extra_data || {},
            representatives: emp.representatives || [],
            education_level: emp.education_level || '',
            has_own_bed_linen: emp.has_own_bed_linen || false
        };
        
        $.ajax({
            url: `/api/admin/employee/${empId}`,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(payload),
            success: () => {
                const vacationModalElement = document.getElementById('vacationFormModal');
                const vacationDialog = vacationModalElement.querySelector('.modal-dialog');
                if (vacationDialog) {
                    vacationDialog.style.setProperty('max-width', '1000px', 'important');
                    vacationDialog.style.setProperty('width', '1000px', 'important');
                    vacationDialog.style.setProperty('transform', 'none', 'important');
                    vacationDialog.style.setProperty('transition', 'none', 'important');
                }
                
                const vacationModal = bootstrap.Modal.getInstance(vacationModalElement);
                if (vacationModal) {
                    vacationModal.hide();
                }
                alert('Заявление сохранено!');
                $.get(`/api/employee/${empId}`).done(emp => {
                    showEmployeeModal(emp, true);
                    loadEmployees($('#admin_search').val().trim(), 'admin_');
                });
            },
            error: (xhr) => {
                let msg = 'Не удалось сохранить заявление';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    msg = `Ошибка сохранения заявления: ${xhr.responseJSON.error}`;
                } else if (xhr.status === 401) {
                    msg = 'Ошибка: У вас нет прав для сохранения заявлений';
                } else if (xhr.status === 404) {
                    msg = 'Ошибка: Студент не найден';
                } else if (xhr.status >= 500) {
                    msg = 'Ошибка сервера при сохранении заявления. Попробуйте позже';
                }
                alert(msg);
            }
        });
    });
}

function deleteVacation(empId) {
    if (typeof showBannerConfirm !== 'undefined') {
        showBannerConfirm(
            'Удалить текущее заявление? Оно будет добавлено в историю заявлений.',
            () => {
                performDeleteVacation(empId);
            }
        );
    } else {
        // Используем кастомное модальное окно вместо системного confirm
        showBannerConfirm(
            'Удалить текущее заявление? Оно будет добавлено в историю заявлений.',
            () => {
                performDeleteVacation(empId);
            }
        );
    }
}

function performDeleteVacation(empId) {
    
    $.ajax({
        url: `/api/admin/delete_vacation/${empId}`,
        method: 'POST',
        success: () => {
            alert('Заявление удалено и добавлено в историю');
            $.get(`/api/employee/${empId}`).done(emp => {
                showEmployeeModal(emp, true);
                loadEmployees($('#admin_search').val().trim(), 'admin_');
            });
        },
        error: (xhr) => {
            let msg = 'Не удалось удалить заявление';
            if (xhr.responseJSON && xhr.responseJSON.error) {
                msg = `Ошибка удаления заявления: ${xhr.responseJSON.error}`;
            } else if (xhr.status === 401) {
                msg = 'Ошибка: У вас нет прав для удаления заявлений';
            } else if (xhr.status === 404) {
                msg = 'Ошибка: Студент или заявление не найдено';
            } else if (xhr.status >= 500) {
                msg = 'Ошибка сервера при удалении заявления. Попробуйте позже';
            }
            alert(msg);
        }
    });
}



function saveEmployee() {
    if (!currentEmpId || currentEmpId === null) {
        alert('Ошибка: ID студента не установлен. Пожалуйста, откройте карточку студента заново.');
        return;
    }
    
        $.get('/api/columns').done(data => {
            customCols = data.custom;
            
        
        const getCurrentData = (callback) => {
            if (currentEmpId === 'new') {
                callback({ extra_data: {}, representatives: [] });
            } else if (currentEmpId && currentEmpId !== null && currentEmpId !== 'null') {
                $.get(`/api/employee/${currentEmpId}`).done(callback).fail(function(xhr) {
                    callback({ extra_data: {}, representatives: [] });
                });
            } else {
                callback({ extra_data: {}, representatives: [] });
            }
        };
        
        getCurrentData((emp) => {
            const extra = emp.extra_data || {};
            
            
            if (extra.health_info) {
            }
            
            if (!customCols || customCols.length === 0) {
            }
            
            customCols.forEach(col => {
                const input = $(`#extra_${col.name}`);
                
                
                if (input.length) {
                    if (col.col_type === 'checkbox') {
                        const isChecked = input.prop('checked');
                        extra[col.name] = isChecked ? 'true' : 'false';
                    } else if (col.col_type === 'number') {
                        const numValue = input.val().trim();
                        extra[col.name] = numValue ? numValue : '';
                    } else {
                        const textValue = input.val().trim();
                        extra[col.name] = textValue;
                    }
                } else {
                    if (col.col_type === 'checkbox') {
                        extra[col.name] = 'false';
                    } else {
                        extra[col.name] = '';
                    }
                }
            });
            
            
        const reps = [];
        $('.rep-row').each(function () {
            const inputs = $(this).find('input');
            const rep = {
                relation: inputs[0].value.trim(),
                fio: inputs[1].value.trim(),
                phone: inputs[2].value.trim(),
                email: inputs[3].value.trim()
            };
            if (rep.fio) reps.push(rep);
        });
            
        // Преобразование даты рождения из дд.мм.гггг в YYYY-MM-DD
        let birthDate = '';
        const birthDateInput = document.getElementById('birth_date');
        if (birthDateInput) {
            // Получаем значение напрямую из input (используем нативное свойство value для надежности)
            // Также проверяем flatpickr, если он инициализирован
            let inputValue = '';
            const fpInstance = birthDateInput._flatpickr || birthDateInput._birthDatePicker;
            // Проверяем, была ли дата выбрана пользователем
            const userSelected = birthDateInput._userSelectedDate === true;
            
            if (fpInstance && fpInstance.selectedDates && fpInstance.selectedDates.length > 0 && userSelected) {
                // Если flatpickr имеет выбранную дату И она была выбрана пользователем, используем её
                const selectedDate = fpInstance.selectedDates[0];
                const year = selectedDate.getFullYear();
                const month = String(selectedDate.getMonth() + 1).padStart(2, '0');
                const day = String(selectedDate.getDate()).padStart(2, '0');
                birthDate = `${year}-${month}-${day}`;
            } else {
                // Иначе получаем значение из input
                inputValue = (birthDateInput.value || $(birthDateInput).val() || '').trim();
                
                // Если поле пустое или дата не была выбрана пользователем, отправляем пустую строку
                if (!inputValue || inputValue === '' || !userSelected) {
                    birthDate = '';
                } else {
                // Парсим значение в формате дд.мм.гггг
                const match = inputValue.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
                if (match) {
                    const [, d, m, y] = match;
                    // Проверяем, что дата валидна
                    const dayNum = parseInt(d, 10);
                    const monthNum = parseInt(m, 10);
                    const yearNum = parseInt(y, 10);
                    if (dayNum >= 1 && dayNum <= 31 && monthNum >= 1 && monthNum <= 12 && yearNum >= 1900 && yearNum <= 2100) {
                        // Форматируем с ведущими нулями
                        const dayStr = String(dayNum).padStart(2, '0');
                        const monthStr = String(monthNum).padStart(2, '0');
                        birthDate = `${yearNum}-${monthStr}-${dayStr}`;
                    } else {
                        birthDate = '';
                    }
                } else if (/^\d{4}-\d{2}-\d{2}$/.test(inputValue)) {
                    // Если уже в формате YYYY-MM-DD, используем как есть
                    birthDate = inputValue;
                } else {
                    // Если формат не распознан, пытаемся преобразовать
                    const parts = inputValue.split(/[.\-\/]/);
                    if (parts.length === 3) {
                        const day = parts[0].padStart(2, '0');
                        const month = parts[1].padStart(2, '0');
                        const year = parts[2];
                        if (day.length === 2 && month.length === 2 && year.length === 4) {
                            const dayNum = parseInt(day, 10);
                            const monthNum = parseInt(month, 10);
                            const yearNum = parseInt(year, 10);
                            if (dayNum >= 1 && dayNum <= 31 && monthNum >= 1 && monthNum <= 12 && yearNum >= 1900 && yearNum <= 2100) {
                                birthDate = `${year}-${month}-${day}`;
                            } else {
                                birthDate = '';
                            }
                        } else {
                            birthDate = '';
                        }
                    } else {
                        birthDate = '';
                    }
                }
            }
            }
        }
        
        const payload = {
            fio: $('#fio').val().trim(),
            phone: $('#phone').val().trim(),
            group_name: $('#group_name').val(),
            birth_date: birthDate,
            education_level: '', // Уровень образования больше не используется
            building: $('#building').val().trim(),
            room_number: $('#room_number').val().trim(),
            entrance: $('#entrance').val().trim(),
            notes: $('#notes').val(),
            absences: $('#absences').val(),
            reprimands: $('#reprimands').val(),
            vacation: $('#vacation').val().trim(),
            has_own_bed_linen: $('#has_own_bed_linen').is(':checked') ? 1 : 0,
            is_local: $('#is_local').is(':checked') ? 1 : 0,
            extra: extra,
            representatives: reps
        };
        
        if (!payload.fio) {
            alert('Ошибка: Поле "ФИО" обязательно для заполнения');
            return;
        }
        
        if (payload.building && payload.entrance && payload.room_number) {
            
            if (!window.roomsLoaded) {
                $.ajax({
                    url: '/api/rooms/list',
                    async: false,
                    success: function(data) {
                        if (data.success && data.rooms) {
                            window.availableRooms = data.rooms;
                            window.roomsLoaded = true;
                        }
                    }
                });
            }
            
            const roomExists = (window.availableRooms || []).some(room => {
                const roomBuilding = (room.building || '').trim();
                const roomEntrance = (room.entrance || '').trim();
                const roomRoomNumber = (room.room_number || '').trim();
                return roomBuilding === payload.building && 
                       roomEntrance === payload.entrance && 
                       roomRoomNumber === payload.room_number;
            });
            
            
            if (!roomExists) {
                const errorMsg = `Ошибка: Комната ${payload.building}-${payload.entrance}-${payload.room_number} не найдена в базе данных.\n\nПожалуйста, сначала добавьте комнату в разделе "Управление комнатами".`;
                alert(errorMsg);
                $('#room_number').focus();
                if (window.validateRoom) {
                    window.validateRoom();
                }
                return;
            }
        }
            
        const fileInput = $('#photoFile')[0];
        const file = fileInput && fileInput.files[0];
        const saveAction = () => {
            if (!currentEmpId || currentEmpId === null || currentEmpId === 'null') {
                alert('Ошибка: ID студента не установлен. Пожалуйста, откройте карточку студента заново.');
                return;
            }
            
            if (currentEmpId === 'new') {
                Employee.createEmployee(payload).then(id => {
                    currentEmpId = id;
                    Employee.currentEmpId = id; // Синхронизируем с модулем Employee
                    if (file) Employee.uploadPhoto(file); else Employee.closeAndRefresh();
                });
            } else {
                Employee.currentEmpId = currentEmpId;
                Employee.updateEmployee(payload);
                if (file) Employee.uploadPhoto(file); else Employee.closeAndRefresh();
            }
        };
        if (file) {
            Utils.resizeImage(file).then(resizedFile => {
                fileInput.files = Utils.createFileList(resizedFile);
                saveAction();
            });
        } else saveAction();
        });
    });
}











function loadEmployeeFiles(empId, isEdit) {
    try {
        const section = $(`#files-section-${empId}`);
        if (!section.length) {
            const modal = $(`.modal:visible`);
            if (modal.length) {
                const altSection = modal.find(`#files-section-${empId}`);
                if (altSection.length) {
                    loadFilesIntoSection(empId, altSection, isEdit);
                    return;
                }
            }
            return;
        }
        
        loadFilesIntoSection(empId, section, isEdit);
    } catch (e) {
    }
}

function loadFilesIntoSection(empId, section, isEdit) {
    $.get(`/api/employee/${empId}/files`)
        .done(function(response) {
            try {
                if (response && response.success) {
                    renderEmployeeFiles(empId, response.files || [], isEdit);
                } else {
                    section.html('<p class="text-muted mb-0">Файлы не загружены</p>');
                }
            } catch (e) {
                section.html('<p class="text-muted mb-0">Ошибка при загрузке файлов</p>');
            }
        })
        .fail(function(xhr) {
            section.html('<p class="text-muted mb-0">Файлы не загружены</p>');
        });
}

function renderEmployeeFiles(empId, files, isEdit) {
    const section = $(`#files-section-${empId}`);
    
    if (!section.length) {
        const modal = $(`.modal:visible`);
        if (modal.length) {
            const altSection = modal.find(`#files-section-${empId}`);
            if (altSection.length) {
                renderFilesIntoSection(empId, altSection, files, isEdit);
                return;
            }
        }
        return;
    }
    
    renderFilesIntoSection(empId, section, files, isEdit);
}

function renderFilesIntoSection(empId, section, files, isEdit) {
    if (!files || files.length === 0) {
        section.html('<p class="text-muted mb-0">Файлы не загружены</p>');
        return;
    }
    
    let html = '<div class="list-group">';
    files.forEach(function(file) {
        const fileSize = formatFileSize(file.file_size);
        const uploadDate = formatDate(file.uploaded_at);
        const description = file.description ? `<small class="text-muted d-block mt-1">${escapeHtml(file.description)}</small>` : '';
        const fileCategory = Utils.getFileCategory(file.original_filename);
        const fileIcon = Utils.getFileIcon(fileCategory.category);
        
        html += `
            <div class="list-group-item">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <div class="d-flex align-items-center gap-2">
                            <div class="consta-file-icon" style="color: ${fileCategory.color}; flex-shrink: 0;">
                                ${fileIcon}
                            </div>
                            <div class="flex-grow-1">
                                <a href="/api/employee/${empId}/files/${file.id}/download" class="text-decoration-none fw-medium" target="_blank">
                                    ${escapeHtml(file.original_filename)}
                                </a>
                                <div class="d-flex align-items-center gap-2 mt-1">
                                    <span class="badge" style="background-color: ${fileCategory.color}; color: white; font-size: 0.7rem; font-weight: 500;">
                                        ${fileCategory.category}
                                    </span>
                                    <small class="text-muted">${fileSize}</small>
                                </div>
                            </div>
                        </div>
                        ${description}
                        <small class="text-muted d-block mt-1">
                            Загружено: ${uploadDate} • ${escapeHtml(file.uploaded_by)}
                        </small>
                    </div>
                    ${isEdit ? `
                        <button type="button" class="btn btn-sm btn-outline-danger ms-2" onclick="deleteEmployeeFile(${empId}, ${file.id})" title="Удалить файл">
                            <i class="bi bi-trash"></i>
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    });
    html += '</div>';
    
    section.html(html);
}

function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function formatDate(dateString) {
    if (!dateString) return '—';
    try {
        const date = new Date(dateString);
        const day = String(date.getDate()).padStart(2, '0');
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const year = date.getFullYear();
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        return `${day}.${month}.${year} ${hours}:${minutes}`;
            } catch (e) {
        return dateString;
    }
}

function showUploadFileModal(empId) {
    const modal = $(`
        <div class="modal fade" id="uploadFileModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Добавить файл</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <form id="uploadFileForm">
                            <div class="mb-3">
                                <div class="consta-dragndrop-container">
                                    <input type="file" id="fileInput" accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.gif,.txt,.zip,.rar" required>
                                </div>
                                <small class="form-text text-muted mt-2 d-block">
                                    Разрешенные типы: PDF, DOC, DOCX, XLS, XLSX, JPG, JPEG, PNG, GIF, TXT, ZIP, RAR. Максимальный размер: 50 МБ
                                </small>
                            </div>
                            <div class="mb-3">
                                <label for="fileDescription" class="form-label">Описание (необязательно)</label>
                                <textarea class="form-control" id="fileDescription" rows="3" maxlength="500" placeholder="Введите описание файла..."></textarea>
                                <small class="form-text text-muted">Максимум 500 символов</small>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                        <button type="button" class="btn btn-primary" onclick="uploadEmployeeFile(${empId})">Добавить</button>
                    </div>
                </div>
            </div>
        </div>
    `);
    
    $('#uploadFileModal').remove();
    
    $('body').append(modal);
    
    const bsModal = new bootstrap.Modal(modal[0]);
    bsModal.show();
    
    modal.on('shown.bs.modal', function() {
        setTimeout(function() {
            if (typeof ConstaDragNDropField !== 'undefined') {
                const fileInput = $('#fileInput')[0];
                if (fileInput && !fileInput.classList.contains('consta-dragndrop-initialized')) {
                    const container = fileInput.closest('.consta-dragndrop-container');
                    if (container) {
                        new ConstaDragNDropField(container, {
                            accept: '.pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.gif,.txt,.zip,.rar',
                            maxSize: 50 * 1024 * 1024, // 50 МБ
                            onError: function(message) {
                                alert(message);
                            }
                        });
                        fileInput.classList.add('consta-dragndrop-initialized');
                    }
                }
            }
        }, 100);
    });
    
    modal.on('hidden.bs.modal', function() {
        modal.remove();
    });
}

function uploadFileToServer(empId, file, description, callback, errorCallback) {
    const formData = new FormData();
    formData.append('file', file);
    if (description) {
        formData.append('description', description);
    }
    
    const uploadBtn = $('#uploadFileModal .btn-primary');
    let originalBtnText = '';
    if (uploadBtn.length > 0) {
        originalBtnText = uploadBtn.html();
        uploadBtn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Загрузка...');
    }
    
    $.ajax({
        url: `/api/employee/${empId}/files`,
        method: 'POST',
        data: formData,
        processData: false,
        contentType: false,
        success: function(response) {
            if (response && response.success) {
                if (callback) {
                    callback();
                } else {
                }
            } else {
                const errorMsg = (response && response.error) || 'Не удалось загрузить файл';
                if (errorCallback) {
                    errorCallback(errorMsg);
                } else {
                    alert('Ошибка: ' + errorMsg);
                }
                if (uploadBtn.length > 0 && originalBtnText) {
                    uploadBtn.prop('disabled', false).html(originalBtnText);
                }
            }
        },
        error: function(xhr) {
            let error = 'Произошла ошибка при загрузке файла';
            if (xhr.responseJSON && xhr.responseJSON.error) {
                error = xhr.responseJSON.error;
            } else if (xhr.status === 401) {
                error = 'Не авторизован. Пожалуйста, войдите в систему.';
            } else if (xhr.status === 403) {
                error = 'Доступ запрещен. Недостаточно прав для загрузки файлов.';
            } else if (xhr.status === 404) {
                error = 'Студент не найден.';
            } else if (xhr.status === 400) {
                error = 'Некорректный запрос. Проверьте формат и размер файла.';
            }
            if (errorCallback) {
                errorCallback(error);
            } else {
                alert('Ошибка: ' + error);
            }
            if (uploadBtn.length > 0 && originalBtnText) {
                uploadBtn.prop('disabled', false).html(originalBtnText);
            }
        }
    });
}

function uploadEmployeeFile(empId) {
    const fileInput = $('#fileInput')[0];
    const description = $('#fileDescription').val().trim();
    
    if (!fileInput.files || fileInput.files.length === 0) {
        alert('Пожалуйста, добавьте файл');
        return;
    }
    
    const file = fileInput.files[0];
    
    uploadFileToServer(empId, file, description, function() {
        const modal = bootstrap.Modal.getInstance($('#uploadFileModal')[0]);
        if (modal) {
            modal.hide();
        }
        $('#uploadFileModal').remove();
        const isEdit = true;
        loadEmployeeFiles(empId, isEdit);
    });
}

function uploadEmployeeFileDirect(empId, file, inputElement) {
    const description = '';
    
    if (!file) {
        alert('Пожалуйста, добавьте файл');
        return;
    }
    
    if (!empId && inputElement) {
        empId = inputElement.dataset.empId;
    }
    
    if (!empId) {
        alert('Ошибка: не указан ID студента');
        return;
    }
    
    if (typeof empId === 'string') {
        empId = parseInt(empId, 10);
        if (isNaN(empId)) {
            alert('Ошибка: неверный ID студента');
            return;
        }
    }
    
    
    const container = inputElement ? inputElement.closest('.consta-dragndrop-container') : null;
    let loadingIndicator = null;
    if (container) {
        const filesContainer = container.querySelector('.consta-dragndrop-files');
        if (filesContainer) {
            loadingIndicator = document.createElement('div');
            loadingIndicator.className = 'text-center p-2';
            loadingIndicator.innerHTML = '<div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">Загрузка...</span></div>';
            filesContainer.appendChild(loadingIndicator);
        }
    }
    
    uploadFileToServer(empId, file, description, function() {
        if (loadingIndicator) {
            loadingIndicator.remove();
        }
        
        if (inputElement) {
            const dataTransfer = new DataTransfer();
            inputElement.files = dataTransfer.files;
            if (container) {
                const filesContainer = container.querySelector('.consta-dragndrop-files');
                if (filesContainer) {
                    filesContainer.innerHTML = '';
                }
            }
        }
        
        setTimeout(function() {
            const isEdit = true;
            loadEmployeeFiles(empId, isEdit);
        }, 300);
    }, function(error) {
        if (loadingIndicator) {
            loadingIndicator.remove();
        }
        alert('Ошибка загрузки файла: ' + error);
    });
}

if (typeof window !== 'undefined') {
    window.uploadEmployeeFileDirect = uploadEmployeeFileDirect;
}

function deleteEmployeeFile(empId, fileId) {
    if (typeof showBannerConfirm !== 'undefined') {
        showBannerConfirm(
            'Вы уверены, что хотите удалить этот файл?',
            () => {
                $.ajax({
                    url: `/api/employee/${empId}/files/${fileId}`,
                    method: 'DELETE',
                    success: function(response) {
                        if (response.success) {
                            const isEdit = typeof window !== 'undefined' && window.adminRole && window.adminRole !== 'razmeshenie';
                            loadEmployeeFiles(empId, isEdit);
                            if (typeof showBannerSuccess !== 'undefined') {
                                showBannerSuccess('Файл удален');
                            }
                        } else {
                            if (typeof showBannerError !== 'undefined') {
                                showBannerError('Ошибка: ' + (response.error || 'Не удалось удалить файл'));
                            } else {
                                alert('Ошибка: ' + (response.error || 'Не удалось удалить файл'));
                            }
                        }
                    },
                    error: function(xhr) {
                        let errorMsg = 'Ошибка при удалении файла';
                        if (xhr.responseJSON && xhr.responseJSON.error) {
                            errorMsg = xhr.responseJSON.error;
                        }
                        if (typeof showBannerError !== 'undefined') {
                            showBannerError(errorMsg);
                        } else {
                            alert(errorMsg);
                        }
                    }
                });
            },
            () => {
            }
        );
    } else {
        // Используем кастомное модальное окно вместо системного confirm
        showBannerConfirm(
            'Вы уверены, что хотите удалить этот файл?',
            () => {
                $.ajax({
                    url: `/api/employee/${empId}/files/${fileId}`,
                    method: 'DELETE',
                    success: function(response) {
                        if (response.success) {
                            const isEdit = typeof window !== 'undefined' && window.adminRole && window.adminRole !== 'razmeshenie';
                            loadEmployeeFiles(empId, isEdit);
                            if (typeof showBannerSuccess !== 'undefined') {
                                showBannerSuccess('Файл удален');
                            } else {
                                alert('Файл удален');
                            }
                        } else {
                            if (typeof showBannerError !== 'undefined') {
                                showBannerError('Ошибка: ' + (response.error || 'Не удалось удалить файл'));
                            } else {
                                alert('Ошибка: ' + (response.error || 'Не удалось удалить файл'));
                            }
                        }
                    },
                    error: function(xhr) {
                        let errorMsg = 'Ошибка при удалении файла';
                        if (xhr.responseJSON && xhr.responseJSON.error) {
                            errorMsg = xhr.responseJSON.error;
                        }
                        if (typeof showBannerError !== 'undefined') {
                            showBannerError(errorMsg);
                        } else {
                            alert(errorMsg);
                        }
                    }
                });
            }
        );
    }
}