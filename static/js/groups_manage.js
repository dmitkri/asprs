$(document).ready(function() {
    let currentEditId = null;

    // Загрузка списка групп
    function loadGroups() {
        $.ajax({
            url: '/api/admin/groups',
            method: 'GET',
            success: function(response) {
                if (response.success) {
                    renderGroups(response.groups);
                } else {
                    console.error('Ошибка загрузки групп:', response.error);
                    $('#groupsTableBody').html('<tr><td colspan="5" class="text-center text-danger">Ошибка загрузки групп</td></tr>');
                }
            },
            error: function(xhr) {
                console.error('Ошибка загрузки групп:', xhr);
                let errorMsg = 'Ошибка загрузки групп';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMsg = xhr.responseJSON.error;
                } else if (xhr.status === 401) {
                    errorMsg = 'Ошибка: Необходима авторизация';
                } else if (xhr.status === 403) {
                    errorMsg = 'Ошибка: У вас нет прав для просмотра групп';
                } else if (xhr.status >= 500) {
                    errorMsg = 'Ошибка сервера при загрузке групп';
                }
                $('#groupsTableBody').html(`<tr><td colspan="5" class="text-center text-danger">${errorMsg}</td></tr>`);
            }
        });
    }

    // Отображение групп в таблице
    function renderGroups(groups) {
        const tbody = $('#groupsTableBody');
        if (groups.length === 0) {
            tbody.html('<tr><td colspan="5" class="text-center text-muted">Группы не найдены</td></tr>');
            return;
        }

        tbody.empty();
        groups.forEach(function(group) {
            const row = `
                <tr>
                    <td>${group.id}</td>
                    <td>${escapeHtml(group.name)}</td>
                    <td>${formatDate(group.created_at)}</td>
                    <td>${formatDate(group.updated_at)}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-primary edit-group-btn" data-id="${group.id}" data-name="${escapeHtml(group.name)}">
                            <i class="bi bi-pencil"></i> Редактировать
                        </button>
                        <button class="btn btn-sm btn-outline-danger delete-group-btn" data-id="${group.id}" data-name="${escapeHtml(group.name)}">
                            <i class="bi bi-trash"></i> Удалить
                        </button>
                    </td>
                </tr>
            `;
            tbody.append(row);
        });
    }

    // Форматирование даты
    function formatDate(dateStr) {
        if (!dateStr) return '-';
        try {
            const date = new Date(dateStr);
            return date.toLocaleDateString('ru-RU', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (e) {
            return dateStr;
        }
    }

    // Экранирование HTML
    function escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, function(m) { return map[m]; });
    }

    // Добавление группы
    $('#saveGroupBtn').on('click', function() {
        const name = $('#groupName').val().trim();
        if (!name) {
            alert('Введите название группы');
            return;
        }

        $.ajax({
            url: '/api/admin/groups',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ name: name }),
            success: function(response) {
                if (response.success) {
                    $('#addGroupModal').modal('hide');
                    $('#addGroupForm')[0].reset();
                    loadGroups();
                    if (typeof showBannerSuccess !== 'undefined') {
                        showBannerSuccess('Группа успешно добавлена');
                    } else {
                        alert('Группа успешно добавлена');
                    }
                } else {
                    alert('Ошибка: ' + (response.error || 'Не удалось добавить группу'));
                }
            },
            error: function(xhr) {
                let errorMsg = 'Ошибка при добавлении группы';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMsg = xhr.responseJSON.error;
                }
                alert(errorMsg);
            }
        });
    });

    // Редактирование группы
    $(document).on('click', '.edit-group-btn', function() {
        const id = $(this).data('id');
        const name = $(this).data('name');
        currentEditId = id;
        $('#editGroupId').val(id);
        $('#editGroupName').val(name);
        $('#editGroupModal').modal('show');
    });

    $('#updateGroupBtn').on('click', function() {
        const id = currentEditId;
        const name = $('#editGroupName').val().trim();
        if (!name) {
            alert('Введите название группы');
            return;
        }

        $.ajax({
            url: `/api/admin/groups/${id}`,
            method: 'PUT',
            contentType: 'application/json',
            data: JSON.stringify({ name: name }),
            success: function(response) {
                if (response.success) {
                    $('#editGroupModal').modal('hide');
                    loadGroups();
                    if (typeof showBannerSuccess !== 'undefined') {
                        showBannerSuccess('Группа успешно обновлена');
                    } else {
                        alert('Группа успешно обновлена');
                    }
                } else {
                    alert('Ошибка: ' + (response.error || 'Не удалось обновить группу'));
                }
            },
            error: function(xhr) {
                let errorMsg = 'Ошибка при обновлении группы';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMsg = xhr.responseJSON.error;
                }
                alert(errorMsg);
            }
        });
    });

    // Удаление группы
    $(document).on('click', '.delete-group-btn', function() {
        const id = $(this).data('id');
        const name = $(this).data('name');
        
        if (typeof showBannerConfirm !== 'undefined') {
            showBannerConfirm(
                `Вы уверены, что хотите удалить группу "${name}"?`,
                function() {
                    performDeleteGroup(id);
                }
            );
        } else {
            if (confirm(`Вы уверены, что хотите удалить группу "${name}"?`)) {
                performDeleteGroup(id);
            }
        }
    });

    function performDeleteGroup(id) {
        $.ajax({
            url: `/api/admin/groups/${id}`,
            method: 'DELETE',
            success: function(response) {
                if (response.success) {
                    loadGroups();
                    if (typeof showBannerSuccess !== 'undefined') {
                        showBannerSuccess('Группа успешно удалена');
                    } else {
                        alert('Группа успешно удалена');
                    }
                } else {
                    alert('Ошибка: ' + (response.error || 'Не удалось удалить группу'));
                }
            },
            error: function(xhr) {
                let errorMsg = 'Ошибка при удалении группы';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMsg = xhr.responseJSON.error;
                }
                alert(errorMsg);
            }
        });
    }

    // Сброс формы при закрытии модального окна
    $('#addGroupModal').on('hidden.bs.modal', function() {
        $('#addGroupForm')[0].reset();
    });

    $('#editGroupModal').on('hidden.bs.modal', function() {
        $('#editGroupForm')[0].reset();
        currentEditId = null;
    });

    // Загрузка групп при загрузке страницы
    loadGroups();
});

