const Import = {
    checkData: null,

    importExcel() {
        const file = $('#admin_excelFile')[0].files[0];
        if (!file) {
            $('#admin_importResult').html('<div class="alert alert-warning">Добавьте файл для импорта</div>');
            return;
        }
        
        if (this.checkData) {
            this.performImport();
            return;
        }
        
        const formData = new FormData();
        formData.append('file', file);
        
        $('#admin_uploadExcelBtn').prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Проверка...');
        $('#admin_importResult').html('');
        
        $.ajax({
            url: '/api/admin/import_excel/check',
            method: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: res => {
                this.checkData = res;
                
                let resultHtml = '';
                
                if (res.errors && res.errors.length > 0) {
                    resultHtml += '<div class="alert alert-warning">';
                    resultHtml += `<strong>Ошибки валидации:</strong><ul class="mb-0 mt-2">`;
                    res.errors.forEach(error => {
                        resultHtml += `<li class="small">${error}</li>`;
                    });
                    resultHtml += `</ul></div>`;
                }
                
                if (res.matches && res.matches.length > 0) {
                    resultHtml += '<div class="alert alert-info">';
                    resultHtml += `<strong>Найдено совпадений по ФИО: ${res.matches.length}</strong><br>`;
                    resultHtml += '<small>Выберите, какие записи обновить:</small><br><br>';
                    resultHtml += '<div style="max-height: 300px; overflow-y: auto;">';
                    res.matches.forEach((match, idx) => {
                        resultHtml += `<div class="form-check mb-2 p-2 border rounded">`;
                        resultHtml += `<input class="form-check-input" type="checkbox" value="${match.existing_id}" id="match_${idx}" checked>`;
                        resultHtml += `<label class="form-check-label" for="match_${idx}">`;
                        resultHtml += `<strong>Строка ${match.row}: ${match.fio}</strong><br>`;
                        resultHtml += `<small class="text-muted">Текущие данные: Телефон: ${match.existing_phone || '—'}, Дата: ${match.existing_birth_date || '—'}<br>`;
                        resultHtml += `Новые данные: Телефон: ${match.new_phone || '—'}, Дата: ${match.new_birth_date || '—'}</small>`;
                        resultHtml += `</label></div>`;
                    });
                    resultHtml += '</div>';
                    resultHtml += '</div>';
                }
                
                if (res.new_students && res.new_students.length > 0) {
                    resultHtml += `<div class="alert alert-success">`;
                    resultHtml += `<strong>Будет добавлено новых студентов: ${res.new_students.length}</strong>`;
                    resultHtml += `</div>`;
                }
                
                if (res.matches && res.matches.length > 0) {
                    resultHtml += `<button type="button" class="btn btn-primary mt-2" onclick="Import.performImport()">Подтвердить импорт</button>`;
                } else if (res.new_students && res.new_students.length > 0) {
                    this.performImport();
                    return;
                }
                
                $('#admin_importResult').html(resultHtml);
                $('#admin_uploadExcelBtn').prop('disabled', false).html('Импортировать');
            },
            error: (xhr) => {
                const msg = xhr.responseJSON?.error || 'Ошибка проверки файла';
                $('#admin_importResult').html(`<div class="alert alert-danger"><strong>Ошибка:</strong> ${msg}</div>`);
                $('#admin_uploadExcelBtn').prop('disabled', false).html('Импортировать');
                this.checkData = null;
            }
        });
    },

    performImport() {
        if (!this.checkData) return;
        
        const updateIds = [];
        $('.form-check-input:checked').each(function() {
            updateIds.push(parseInt($(this).val()));
        });
        
        $('#admin_uploadExcelBtn').prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Импорт...');
        
        $.ajax({
            url: '/api/admin/import_excel',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                temp_file: this.checkData.temp_file,
                update_ids: updateIds
            }),
            success: res => {
                let resultHtml = '<div class="alert alert-success">';
                resultHtml += `<strong>Импорт завершен!</strong><br><br>`;
                resultHtml += `✅ Добавлено новых: ${res.imported || 0}<br>`;
                resultHtml += `🔄 Обновлено существующих: ${res.updated || 0}<br>`;
                if (res.skipped > 0) {
                    resultHtml += `⏭️ Пропущено: ${res.skipped}<br>`;
                }
                resultHtml += '</div>';
                
                $('#admin_importResult').html(resultHtml);
                Employee.loadEmployees($('#admin_search').val().trim(), 'admin_');
                
                setTimeout(() => {
                    $('#admin_uploadExcelBtn').prop('disabled', false).html('Импортировать');
                    $('#admin_importModal').modal('hide');
                    $('#admin_excelFile').val('');
                    $('#admin_importResult').html('');
                    this.checkData = null;
                }, 3000);
            },
            error: (xhr) => {
                const msg = xhr.responseJSON?.error || 'Ошибка импорта';
                $('#admin_importResult').html(`<div class="alert alert-danger"><strong>Ошибка:</strong> ${msg}</div>`);
                $('#admin_uploadExcelBtn').prop('disabled', false).html('Импортировать');
            }
        });
    }
};


