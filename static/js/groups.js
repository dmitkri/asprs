const Groups = {
    loadGroups(selectId, selected = '') {
        $.get('/api/groups').done(groups => {
            const select = $(`#${selectId}`);
            select.empty().append('<option value="">—</option>');
            groups.forEach(g => {
                const opt = `<option value="${g}" ${g === selected ? 'selected' : ''}>${g}</option>`;
                select.append(opt);
            });
            
            const selectElement = select[0];
            if (selectElement && selectElement._constaCombobox) {
                selectElement._constaCombobox.destroy();
                delete selectElement._constaCombobox;
            }
            if (typeof initConstaComboboxes !== 'undefined') {
                setTimeout(() => {
                    initConstaComboboxes(selectElement.closest('.modal') || document);
                }, 50);
            }
        });
    },

    showGroupFilter(th) {
        if (typeof ConstaGroupFilter === 'undefined') {
            return;
        }

        $.get('/api/groups').done(groups => {
            if (groups.length === 0) return;
            
            const currentFilter = window.currentGroupFilter || '';
            let selectedGroups = [];
            if (currentFilter) {
                if (Array.isArray(currentFilter)) {
                    selectedGroups = currentFilter;
                } else {
                    selectedGroups = [currentFilter];
                }
            }

            const prefix = th.closest('table').attr('id') === 'admin_table' ? 'admin_' : 'user_';
            
            const filter = new ConstaGroupFilter({
                groups: groups,
                selectedGroups: selectedGroups,
                onApply: function(selectedGroups) {
                    
                    if (selectedGroups.length === 0) {
                        window.currentGroupFilter = '';
                    } else if (selectedGroups.length === 1) {
                        window.currentGroupFilter = selectedGroups[0];
                    } else {
                        window.currentGroupFilter = selectedGroups;
                    }
                    
                    
                    const search = $(`#${prefix}search`).val() || $('#admin_search').val() || $('#user_search').val() || '';
                    Employee.loadEmployees(search.trim(), prefix);
                },
                onCancel: function() {
                }
            });

            filter.show();
        });
    }
};

$(document).on('click', 'th[data-filter="group"]', function (e) {
    e.stopPropagation();
    Groups.showGroupFilter($(this));
});


