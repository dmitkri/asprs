const Vacation = {
    parseVacation(vacationText) {
        if (!vacationText) return { startTime: '', startDate: '', endTime: '', endDate: '' };
        
        const parts = vacationText.split(' - ');
        if (parts.length !== 2) return { startTime: '', startDate: '', endTime: '', endDate: '' };
        
        const parsePart = (part) => {
            const match = part.match(/^(\d{2}:\d{2})\s+(\d{2})\.(\d{2})\.(\d{4})$/);
            if (!match) return { time: '', date: '' };
            const [, time, day, month, year] = match;
            // Возвращаем дату в формате дд.мм.гггг для совместимости с новым форматом
            return { time, date: `${day}.${month}.${year}` };
        };
        
        const start = parsePart(parts[0].trim());
        const end = parsePart(parts[1].trim());
        
        return {
            startTime: start.time,
            startDate: start.date,
            // Формат: дд.мм.гггг чч:мм
            startDateTime: start.time && start.date ? `${start.date} ${start.time}` : '',
            endTime: end.time,
            endDate: end.date,
            // Формат: дд.мм.гггг чч:мм
            endDateTime: end.time && end.date ? `${end.date} ${end.time}` : ''
        };
    },

    formatVacation(startTime, startDate, endTime, endDate) {
        if (!startTime || !startDate || !endTime || !endDate) {
            return '';
        }
        
        const formatDate = (dateStr) => {
            // Если дата уже в формате дд.мм.гггг, возвращаем как есть
            if (dateStr.match(/^\d{2}\.\d{2}\.\d{4}$/)) {
                return dateStr;
            }
            // Если дата в формате гггг-мм-дд, преобразуем в дд.мм.гггг
            if (dateStr.match(/^\d{4}-\d{2}-\d{2}$/)) {
                const [y, m, d] = dateStr.split('-');
                return `${d}.${m}.${y}`;
            }
            // Если формат неизвестен, возвращаем как есть
            return dateStr;
        };
        
        return `${startTime} ${formatDate(startDate)} - ${endTime} ${formatDate(endDate)}`;
    },

    showHistory(history) {
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
            list = '<p class="text-muted">История заявлений пуста</p>';
        } else {
            list = '<ul class="list-group">';
            const reversed = [...history].reverse();
            reversed.forEach((item, index) => {
                list += `<li class="list-group-item">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <strong>Заявление ${history.length - index}:</strong>
                            <p class="mb-0 mt-1">${typeof Utils !== 'undefined' ? Utils.escapeHtml(String(item)) : String(item).replace(/</g, '&lt;').replace(/>/g, '&gt;')}</p>
                        </div>
                    </div>
                </li>`;
            });
            list += '</ul>';
        }

        $('#vacationHistoryModal').remove();

        const modal = $(`
            <div class="modal" id="vacationHistoryModal" tabindex="-1" aria-hidden="true" style="display: none;">
                <div class="modal-dialog modal-lg" style="max-width: 900px !important; width: 900px !important; margin: 1.75rem auto !important; transform: none !important; transition: none !important;">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">История заявлений</h5>
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
        
        const modalEl = $('#vacationHistoryModal');
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
            const modalInstance = new bootstrap.Modal(document.getElementById('vacationHistoryModal'), {});
            modalInstance.show();
        }, 10);
        
        modalEl.on('hidden.bs.modal', function () { 
            $(this).remove(); 
        });
    },

    showHistoryFromButton(button) {
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
            
            if (typeof historyData === 'string') {
                try {
                    const decoded = historyData.replace(/&#39;/g, "'").replace(/&quot;/g, '"');
                    historyData = JSON.parse(decoded);
                } catch (e) {
                    try {
                        historyData = JSON.parse(historyData);
                    } catch (e2) {
                        historyData = [];
                    }
                }
            }
            
            if (!historyData || !Array.isArray(historyData)) {
                historyData = [];
            }
            
            this.showHistory(historyData);
        } catch (e) {
            alert('Ошибка при открытии истории заявлений. Не удалось загрузить данные. Попробуйте позже или обновите страницу.');
        }
    }
};



