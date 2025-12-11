const Employee = {
    currentEmpId: null,


    buildEmployeeRow(emp, prefix = 'user_') {
        const isVacation = emp.vacation.trim() !== '';
        const isIll = Health.isCurrentlyIll(emp);
        const avatarClass = isVacation ? 'vacation' : '';
        let photoSrc = emp.photo ? `/static/avatars/${emp.photo}` : Utils.generateAvatarWithInitials(emp.fio);
        let dots = '';
        if (isVacation) dots += '<div class="vacation-dot"></div>';
        if (isIll) dots += '<i class="bi bi-thermometer-half health-thermometer"></i>';
        
        let row = `
            <tr class="${isVacation ? 'vacation-row' : ''}" style="cursor: pointer;" data-id="${emp.id}">
                <td class="avatar-cell">
                    <div class="avatar-container ${avatarClass}">
                        <img src="${photoSrc}" alt="Фото">
                        ${dots}
                    </div>
                </td>
        `;
        const visibleCols = Columns.getVisibleColumns();
        visibleCols.forEach(col => {
            if (col === 'birth_date') {
                const { age } = Utils.formatDateAndAge(emp.birth_date);
                row += `<td>${age || '—'}</td>`;
            } else if (col === 'phone') {
                const phone = Utils.escapeHtml(emp.phone || '');
                row += `<td>${phone || '—'}</td>`;
            } else if (['building', 'room_number', 'entrance'].includes(col)) {
                let value = emp[col] || '';
                row += `<td>${Utils.escapeHtml(value) || '—'}</td>`;
            } else {
                let value = emp[col] !== undefined ? emp[col] : (emp.extra_data[col] || '—');
                const colType = Columns.colTypes[col];
                if (colType === 'date' && value && value !== '—') {
                    const parts = value.split('-');
                    if (parts.length === 3) {
                        value = `${parts[2]}.${parts[1]}.${parts[0]}`;
                    }
                } else if (colType === 'checkbox') {
                    value = (value === 'true' || value === true || value === '1') ? 'Да' : 'Нет';
                }
                row += `<td>${Utils.escapeHtml(value)}</td>`;
            }
        });
        
        if (prefix === 'admin_') {
            const rating = Utils.calculateProfileRating(emp);
            const ratingColor = rating.percentage >= 80 ? 'success' : rating.percentage >= 50 ? 'warning' : 'danger';
            
            let tooltipHtml = '<div class="rating-tooltip-content">';
            tooltipHtml += `<div class="rating-tooltip-header">Рейтинг заполнения: ${rating.score}/${rating.maxScore} (${rating.percentage}%)</div>`;
            tooltipHtml += '<div class="rating-tooltip-list">';
            rating.details.forEach(detail => {
                const icon = detail.filled ? '✓' : '✗';
                const className = detail.filled ? 'filled' : 'not-filled';
                tooltipHtml += `<div class="rating-tooltip-item ${className}">`;
                tooltipHtml += `<span class="rating-tooltip-icon">${icon}</span>`;
                tooltipHtml += `<span class="rating-tooltip-field">${Utils.escapeHtml(detail.field)}</span>`;
                tooltipHtml += `<span class="rating-tooltip-points">${detail.points} баллов</span>`;
                tooltipHtml += '</div>';
            });
            tooltipHtml += '</div></div>';
            
            row += `<td class="text-center">
                <div class="rating-container" data-rating-details='${Utils.escapeHtml(JSON.stringify(rating.details))}' data-rating-score="${rating.score}" data-rating-max="${rating.maxScore}">
                    <div class="consta-progressspin" data-progressspin="${rating.percentage}" data-size="m" data-color="${ratingColor}"></div>
                    <div class="rating-tooltip">${tooltipHtml}</div>
                </div>
            </td>`;
        }
        
        row += '</tr>';
        return row;
    },

    loadEmployees(search = '', prefix = 'user_') {
        let group = '';
        const groupSelect = $(`.group-filter:visible`);
        if (groupSelect.length) {
            group = groupSelect.val() || '';
        } else {
            const currentFilter = window.currentGroupFilter || '';
            if (Array.isArray(currentFilter) && currentFilter.length > 0) {
                group = currentFilter.join(',');
            } else if (typeof currentFilter === 'string' && currentFilter.trim() !== '') {
                group = currentFilter;
            } else {
                group = '';
            }
        }
        
        
        let status = '';
        if (prefix === 'admin_') {
            // Всегда берем значение напрямую из DOM элемента
            const statusFilterEl = $('#admin_statusFilter');
            if (statusFilterEl.length) {
                status = statusFilterEl.val() || '';
                window.currentStatusFilter = status;
                
                // Инициализируем обработчик только один раз
                if (!window.statusFilterInitialized) {
                    statusFilterEl.off('change').on('change', function() {
                        const statusValue = $(this).val() || '';
                        window.currentStatusFilter = statusValue;
                        Employee.loadEmployees($('#admin_search').val().trim(), 'admin_');
                    });
                    window.statusFilterInitialized = true;
                }
            } else {
                // Если элемент не найден, используем сохраненное значение
                status = window.currentStatusFilter || '';
            }
        } else if (prefix === 'user_') {
            status = '';
        }
        
        
        const params = {
            q: search || '',
            group: group || '',
            status: status || ''
        };
        
        const url = '/api/employees?' + $.param(params);
        
        $.get('/api/employees', params).done(data => {
            const tbody = $(`#${prefix}tableBody`);
            if (!tbody.length) {
                return;
            }
            tbody.empty();
            data.forEach(emp => {
                const rowHtml = this.buildEmployeeRow(emp, prefix);
                tbody.append(rowHtml);
            });
            
            if (typeof initConstaProgressSpins !== 'undefined') {
                const tableBody = tbody[0];
                if (tableBody) {
                    setTimeout(function() {
                        initConstaProgressSpins(tableBody);
                        if (typeof initRatingTooltips !== 'undefined') {
                            initRatingTooltips();
                        }
                    }, 50);
                }
            }
        }).fail(function(xhr, status, error) {
        });
    },

    applyUserFilters(search, group) {
        this.loadEmployees(search, 'user_');
    },

    createEmployee(data) {
        return $.ajax({
            url: '/api/admin/employee',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data)
        }).then(res => {
            if (typeof showSuccess === 'function') {
                showSuccess('Студент создан!');
            } else {
                alert('Студент создан!');
            }
            return res.id;
        });
    },

    updateEmployee(data) {
        if (!this.currentEmpId || this.currentEmpId === null || this.currentEmpId === 'null') {
            alert('Ошибка: ID студента не установлен. Пожалуйста, откройте карточку студента заново.');
            return;
        }
        
        $.ajax({
            url: `/api/admin/employee/${this.currentEmpId}`,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: () => {
                if (typeof showSuccess === 'function') {
                    showSuccess('Сохранено!');
                } else {
                    alert('Сохранено!');
                }
                this.closeAndRefresh();
            },
            error: function(xhr) {
                let errorMsg = 'Ошибка при сохранении';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMsg = xhr.responseJSON.error;
                }
                alert(errorMsg);
            }
        });
    },

    uploadPhoto(file) {
        const formData = new FormData();
        formData.append('photo', file);
        $.ajax({
            url: `/api/admin/photo/${this.currentEmpId}`,
            method: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: res => {
                $('#currentPhoto').attr('src', '/static/avatars/' + res.photo + '?t=' + Date.now());
                this.closeAndRefresh();
            }
        });
    },

    closeAndRefresh() {
        $('#admin_empModal').modal('hide');
        this.loadEmployees($('#admin_search').val().trim(), 'admin_');
        Columns.loadColumns();
    },

    deleteEmployee(id) {
        if (typeof showBannerConfirm !== 'undefined') {
            showBannerConfirm(
                'Вы уверены, что хотите удалить этого студента? Это действие необратимо.',
                () => {
                    $.ajax({
                        url: `/api/admin/employee/${id}`,
                        method: 'DELETE',
                        success: () => this.closeAndRefresh()
                    });
                },
                () => {
                }
            );
        } else {
            if (confirm('Удалить студента?')) {
                $.ajax({
                    url: `/api/admin/employee/${id}`,
                    method: 'DELETE',
                    success: () => this.closeAndRefresh()
                });
            }
        }
    }
};

function initRatingTooltips() {
    const containers = document.querySelectorAll('.rating-container');
    containers.forEach(container => {
        const tooltip = container.querySelector('.rating-tooltip');
        if (!tooltip) return;
        
        if (container._tooltipHandler) {
            container.removeEventListener('mouseenter', container._tooltipHandler);
            container.removeEventListener('mouseleave', container._tooltipLeaveHandler);
        }
        
        container._tooltipHandler = function(e) {
            const rect = container.getBoundingClientRect();
            const viewportHeight = window.innerHeight;
            const viewportWidth = window.innerWidth;
            const tooltipWidth = 300; // Примерная ширина tooltip
            const tooltipHeight = 250; // Примерная высота tooltip
            const offset = 8;
            
            tooltip.style.visibility = 'visible';
            tooltip.style.opacity = '1';
            
            const spaceAbove = rect.top;
            const spaceBelow = viewportHeight - rect.bottom;
            
            let top, left;
            
            if (spaceAbove >= tooltipHeight + offset) {
                top = rect.top - tooltipHeight - offset;
                tooltip.classList.remove('rating-tooltip-bottom');
            } else if (spaceBelow >= tooltipHeight + offset) {
                top = rect.bottom + offset;
                tooltip.classList.add('rating-tooltip-bottom');
            } else {
                top = (viewportHeight - tooltipHeight) / 2;
                tooltip.classList.remove('rating-tooltip-bottom');
            }
            
            left = rect.left + (rect.width / 2) - (tooltipWidth / 2);
            
            if (left + tooltipWidth > viewportWidth - 10) {
                left = viewportWidth - tooltipWidth - 10;
            }
            
            if (left < 10) {
                left = 10;
            }
            
            tooltip.style.top = top + 'px';
            tooltip.style.left = left + 'px';
        };
        
        container._tooltipLeaveHandler = function() {
            tooltip.style.visibility = 'hidden';
            tooltip.style.opacity = '0';
        };
        
        container.addEventListener('mouseenter', container._tooltipHandler);
        container.addEventListener('mouseleave', container._tooltipLeaveHandler);
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initRatingTooltips);
} else {
    initRatingTooltips();
}

const ratingTooltipObserver = new MutationObserver(() => {
    initRatingTooltips();
});

ratingTooltipObserver.observe(document.body, {
    childList: true,
    subtree: true
});

