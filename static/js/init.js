const Init = {
    initAdminPage() {
        window.currentStatusFilter = '';
        window.statusFilterInitialized = false;
        
        const initStatusFilter = () => {
            const statusFilterEl = $('#admin_statusFilter');
            if (statusFilterEl.length) {
                window.currentStatusFilter = statusFilterEl.val() || '';
                
                statusFilterEl.off('change');
                
                statusFilterEl.on('change', function() {
                    const statusValue = $(this).val() || '';
                    window.currentStatusFilter = statusValue;
                    Employee.loadEmployees($('#admin_search').val().trim(), 'admin_');
                });
                
                window.statusFilterInitialized = true;
                return true;
            } else {
                return false;
            }
        };
        
        if (!initStatusFilter()) {
            setTimeout(() => {
                if (!initStatusFilter()) {
                    setTimeout(() => {
                        if (!initStatusFilter()) {
                        }
                    }, 500);
                }
            }, 100);
        }
        
        Employee.loadEmployees('', 'admin_');
        if ($('#admin_search').length) {
            $('#admin_search').on('input', Utils.debounce(() => Employee.loadEmployees($('#admin_search').val().trim(), 'admin_'), 300));
        }
        if ($('#admin_addBtn').length) {
            $('#admin_addBtn').on('click', () => Modals.showAdminModal('new'));
        }
        if ($('#admin_importBtn').length) {
            $('#admin_importBtn').on('click', () => {
                Import.checkData = null;
                $('#admin_importResult').html('');
                $('#admin_excelFile').val('');
                $('#admin_uploadExcelBtn').prop('disabled', true).html('Импортировать');
                $('#admin_importModal').modal('show');
            });
            $('#admin_importModal').on('hidden.bs.modal', () => {
                Import.checkData = null;
                $('#admin_importResult').html('');
                $('#admin_excelFile').val('');
            });
            $('#admin_excelFile').on('change', () => {
                $('#admin_uploadExcelBtn').prop('disabled', !$('#admin_excelFile')[0].files.length);
                Import.checkData = null;
                $('#admin_importResult').html('');
            });
            $('#admin_uploadExcelBtn').on('click', () => Import.importExcel());
        }
        if ($('#admin_addColBtn').length) {
            $('#admin_addColBtn').on('click', Columns.addColumn);
        }
        $(document).on('click', '#admin_tableBody tr', function () {
            Modals.showAdminModal($(this).data('id'));
        });
        
        this.checkAdminPermissions();
    },

    checkAdminPermissions() {
        $.get('/api/admin/permissions')
            .done(function(data) {
                const perms = data.permissions;
                const role = data.role;
                
                if (!perms.edit) {
                    $('#admin_addBtn').hide();
                }
                if (!perms.import) {
                    $('#admin_importBtn').hide();
                }
                if (!perms.manage_columns) {
                    $('#admin_addColBtn').closest('.card').hide();
                }
            })
            .fail(function() {
            });
    },

    initUserPage() {
        Employee.loadEmployees();
        
        $('#user_search').on('input', Utils.debounce(() => {
            Employee.loadEmployees($('#user_search').val().trim(), 'user_');
        }, 300));
        
        $(document).on('click', '#user_tableBody tr', function () {
            $.get(`/api/employee/${$(this).data('id')}`).done(emp => Modals.showEmployeeModal(emp));
        });
    }
};

