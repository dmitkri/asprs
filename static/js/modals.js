const Modals = {
    showAdminModal(id) {
        const adminRole = typeof window !== 'undefined' ? window.adminRole : null;
        const isEditMode = adminRole !== 'razmeshenie';
        
        if (id === 'new') {
            if (!isEditMode) {
                alert('У вас нет прав для создания новых студентов');
                return;
            }
            if (typeof showEmployeeModal === 'function') {
                showEmployeeModal({
                    id: 'new', fio: '', phone: '', group_name: '', birth_date: '',
                    education_level: '', notes: '', absences: '', reprimands: '', vacation: '',
                    vacation_history: [], extra_data: {}, representatives: []
                }, true);
            }
        } else {
            $.get(`/api/employee/${id}`).done(emp => {
                if (typeof showEmployeeModal === 'function') {
                    showEmployeeModal(emp, isEditMode);
                }
            });
        }
    },

    showEmployeeModal(emp, isEdit = false) {
        if (typeof showEmployeeModal === 'function') {
            showEmployeeModal(emp, isEdit);
        }
    }
};









