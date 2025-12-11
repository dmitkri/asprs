const History = {
    showChangesHistoryModal(empId) {
        
        const adminRole = typeof window !== 'undefined' ? window.adminRole : null;
        
        if (!adminRole || (adminRole !== 'admin' && adminRole !== 'super_admin')) {
            alert('Доступ запрещен. Только администраторы могут просматривать историю изменений.');
            return;
        }
        
        const modal = $('#changesHistoryModal');
        if (!modal.length) {
            alert('Ошибка: Модальное окно не найдено. Обновите страницу.');
            return;
        }
        
        const dialog = modal.find('.modal-dialog');
        dialog.css({
            'max-width': '900px !important',
            'width': '900px !important',
            'transform': 'none !important',
            'transition': 'none !important',
            'margin': '1.75rem auto !important'
        });
        
        const dialogEl = modal[0].querySelector('.modal-dialog');
        if (dialogEl) {
            dialogEl.style.setProperty('max-width', '900px', 'important');
            dialogEl.style.setProperty('width', '900px', 'important');
            dialogEl.style.setProperty('transform', 'none', 'important');
            dialogEl.style.setProperty('transition', 'none', 'important');
            dialogEl.style.setProperty('margin', '1.75rem auto', 'important');
        }
        
        modal.off('show.bs.modal shown.bs.modal hide.bs.modal hidden.bs.modal');
        
        modal.on('show.bs.modal', function() {
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
        
        modal.on('hide.bs.modal hidden.bs.modal', function() {
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
            modal.modal('show');
            
            setTimeout(function() {
                History.loadChangesHistory(empId);
            }, 100);
        }, 10);
    },

    loadChangesHistory(empId) {
        const section = $('#changesHistoryModalBody');
        
        section.html(`
            <div class="text-center py-4">
                <div class="spinner-border spinner-border-sm" role="status">
                    <span class="visually-hidden">Загрузка...</span>
                </div>
                <p class="mt-2 text-muted">Загрузка истории изменений...</p>
            </div>
        `);
        
        $.get(`/api/employee/${empId}/changes_history`)
            .done(function(data) {
                if (data.success && data.history && data.history.length > 0) {
                    let historyHtml = '<div class="table-responsive" style="max-height: 500px; overflow-y: auto;">';
                    historyHtml += '<table class="table table-sm table-hover">';
                    historyHtml += '<thead class="table-light sticky-top">';
                    historyHtml += '<tr><th>Дата</th><th>Поле</th><th>Старое значение</th><th>Новое значение</th><th>Изменил</th></tr>';
                    historyHtml += '</thead><tbody>';
                    
                    data.history.forEach(function(change) {
                        const date = new Date(change.changed_at);
                        const dateStr = date.toLocaleString('ru-RU', {
                            year: 'numeric',
                            month: '2-digit',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit'
                        });
                        
                        historyHtml += '<tr>';
                        historyHtml += `<td class="small">${Utils.escapeHtml(dateStr)}</td>`;
                        historyHtml += `<td><strong>${Utils.escapeHtml(change.field_name)}</strong></td>`;
                        historyHtml += `<td class="text-muted">${Utils.escapeHtml(change.old_value || '(пусто)')}</td>`;
                        historyHtml += `<td>${Utils.escapeHtml(change.new_value || '(пусто)')}</td>`;
                        historyHtml += `<td class="small">${Utils.escapeHtml(change.admin_username)}</td>`;
                        historyHtml += '</tr>';
                    });
                    
                    historyHtml += '</tbody></table></div>';
                    section.html(historyHtml);
                } else {
                    section.html('<p class="text-muted text-center py-4 mb-0">История изменений пуста</p>');
                }
            })
            .fail(function(xhr, status, error) {
                let errorMsg = 'Ошибка загрузки истории изменений';
                if (xhr.status === 403) {
                    errorMsg = 'Доступ запрещен. Только администраторы могут просматривать историю изменений.';
                } else if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMsg = xhr.responseJSON.error;
                } else {
                    errorMsg = `${errorMsg}: ${error}`;
                }
                section.html(`<p class="text-danger text-center py-4 mb-0">${errorMsg}</p>`);
            });
    }
};









