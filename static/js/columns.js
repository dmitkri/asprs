const Columns = {
    fixedCols: ['fio', 'phone', 'group_name', 'birth_date', 'building', 'room_number', 'entrance'],
    allCols: [],
    customCols: [],
    colTypes: {},
    getVisibleColumns() {
        return this.fixedCols;
    },

    loadColumns() {
        $.get('/api/columns').done(data => {
            this.fixedCols = data.fixed;
            this.customCols = data.custom;
            this.allCols = this.fixedCols.concat(this.customCols.map(c => c.name));
            this.colTypes = {};
            this.customCols.forEach(c => this.colTypes[c.name] = c.col_type);
            
            if (typeof window !== 'undefined') {
                window.fixedCols = this.fixedCols;
                window.customCols = this.customCols;
                window.allCols = this.allCols;
                window.colTypes = this.colTypes;
            }
            
            this.buildTableHead();
            this.buildColumnList();
        });
    },

    buildTableHead() {
        const titles = { 
            'fio': 'ФИО', 
            'phone': 'Телефон', 
            'group_name': 'Группа', 
            'birth_date': 'Возраст',
            'building': 'Корпус',
            'room_number': 'Номер',
            'entrance': 'Подъезд',
            'profile_rating': 'Рейтинг'
        };
        const visibleCols = this.getVisibleColumns();
        
        let adminHead = '<th>Фото</th>';
        visibleCols.forEach(col => {
            let title = titles[col] || col.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            if (col === 'group_name') {
                adminHead += `<th data-filter="group" style="cursor: pointer;">${title} <i class="bi bi-caret-down-fill ms-1"></i></th>`;
            } else {
                adminHead += `<th>${title}</th>`;
            }
        });
        adminHead += '<th class="text-center">Рейтинг</th>';
        $('#admin_tableHead').html(adminHead);
        
        let userHead = '<th>Фото</th>';
        visibleCols.forEach(col => {
            let title = titles[col] || col.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            if (col === 'group_name') {
                userHead += `<th data-filter="group" style="cursor: pointer;">${title} <i class="bi bi-caret-down-fill ms-1"></i></th>`;
            } else {
                userHead += `<th>${title}</th>`;
            }
        });
        $('#user_tableHead').html(userHead);
    },

    buildColumnList() {
        const container = $('#admin_columnList');
        if (!container.length) return;

        let html = '<h6 class="mt-4 mb-3">Блоки в карточке студента</h6>';
        if (this.customCols.length === 0) {
            html += '<p class="text-muted">Нет дополнительных блоков</p>';
        } else {
            this.customCols.forEach(col => {
                html += `
                    <div class="d-flex justify-content-between align-items-center border rounded p-2 mb-2">
                        <span class="text-break">${Utils.escapeHtml(col.name)} (${col.col_type})</span>
                        <button class="btn btn-sm btn-danger delete-col-btn" data-col="${Utils.escapeHtml(col.name)}" title="Удалить блок">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                `;
            });
        }
        container.html(html);

        $('.delete-col-btn').off('click').on('click', function () {
            const colName = $(this).data('col');
            if (confirm(`Удалить блок "${colName}"?\n\nВНИМАНИЕ: Все данные в этом блоке будут УДАЛЕНЫ навсегда!`)) {
                $.ajax({
                    url: '/api/admin/delete_column',
                    method: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify({ name: colName }),
                    success: () => {
                        Columns.loadColumns();
                        alert(`Блок "${colName}" удалён`);
                    },
                    error: (xhr) => {
                        let msg = 'Не удалось удалить блок';
                        if (xhr.responseJSON && xhr.responseJSON.error) {
                            msg = `Ошибка удаления блока: ${xhr.responseJSON.error}`;
                        } else if (xhr.status === 401) {
                            msg = 'Ошибка: У вас нет прав для выполнения этого действия';
                        } else if (xhr.status === 404) {
                            msg = 'Ошибка: Блок не найден';
                        } else if (xhr.status >= 500) {
                            msg = 'Ошибка сервера при удалении блока. Попробуйте позже';
                        }
                        alert(msg);
                    }
                });
            }
        });
    },


    addColumn() {
        const colName = $('#admin_colName').val().trim();
        const colType = $('#admin_colType').val();
        if (!colName) {
            alert('Ошибка: Введите название блока');
            return;
        }
        $.ajax({
            url: '/api/admin/add_column',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ name: colName, type: colType }),
            success: (data) => {
                const normalizedName = data.name || colName;
                $('#admin_colName').val('');
                Columns.loadColumns();
                Columns.buildColumnList();
                alert(`Блок "${normalizedName}" добавлен в карточку студента`);
            },
            error: (xhr) => {
                let msg = 'Не удалось добавить блок';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    msg = `Ошибка добавления блока: ${xhr.responseJSON.error}`;
                } else if (xhr.status === 401) {
                    msg = 'Ошибка: У вас нет прав для добавления блоков';
                } else if (xhr.status >= 500) {
                    msg = 'Ошибка сервера при добавлении блока. Попробуйте позже';
                }
                alert(msg);
            }
        });
    }
};

