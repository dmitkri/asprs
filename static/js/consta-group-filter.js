
class ConstaGroupFilter {
    constructor(options = {}) {
        this.groups = options.groups || [];
        this.selectedGroups = options.selectedGroups || [];
        this.onApply = options.onApply || null;
        this.onCancel = options.onCancel || null;
        this.modal = null;
        this.filteredGroups = [...this.groups];
        this.searchQuery = '';
    }

    show() {
        this.createModal();
        this.modal.modal('show');
    }

    createModal() {
        $('#constaGroupFilterModal').remove();

        const modalHtml = `
            <div class="modal fade consta-group-filter-modal" id="constaGroupFilterModal" tabindex="-1">
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Фильтр по группам</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="consta-group-filter-search">
                                <div class="consta-group-filter-search-input">
                                    <svg class="search-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                                        <path d="M7.33333 12.6667C10.2789 12.6667 12.6667 10.2789 12.6667 7.33333C12.6667 4.38781 10.2789 2 7.33333 2C4.38781 2 2 4.38781 2 7.33333C2 10.2789 4.38781 12.6667 7.33333 12.6667Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                                        <path d="M14 14L11.1 11.1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                                    </svg>
                                    <input type="text" class="form-control" id="groupFilterSearch" placeholder="Найти в списке">
                                </div>
                            </div>
                            <div class="consta-group-filter-actions">
                                <a href="#" class="select-all" id="selectAllGroups">Выбрать все</a>
                                <a href="#" class="reset" id="resetGroups">Сбросить</a>
                            </div>
                            <div class="consta-group-filter-list" id="groupFilterList">
                                ${this.renderGroups()}
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn-cancel" data-bs-dismiss="modal">Отмена</button>
                            <button type="button" class="btn-apply" id="applyGroupFilter">Применить</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        $('body').append(modalHtml);
        this.modal = $('#constaGroupFilterModal');
        this.attachEvents();
        this.updateSelectAllButton();
    }

    renderGroups() {
        if (this.filteredGroups.length === 0) {
            return '<div class="text-center text-muted p-3">Группы не найдены</div>';
        }

        return this.filteredGroups.map((group, index) => {
            const isChecked = this.selectedGroups.includes(group);
            const safeId = `group_filter_${index}_${group.replace(/[^a-zA-Z0-9]/g, '_')}`;
            return `
                <div class="consta-group-filter-item">
                    <input type="checkbox" id="${safeId}" value="${this.escapeHtml(group)}" ${isChecked ? 'checked' : ''}>
                    <label for="${safeId}">${this.escapeHtml(group)}</label>
                </div>
            `;
        }).join('');
    }

    attachEvents() {
        const self = this;

        $('#groupFilterSearch').on('input', function() {
            self.searchQuery = $(this).val().toLowerCase();
            self.filterGroups();
        });

        $('#selectAllGroups').on('click', function(e) {
            e.preventDefault();
            if ($(this).hasClass('disabled')) return;
            self.selectAll();
        });

        $('#resetGroups').on('click', function(e) {
            e.preventDefault();
            self.reset();
        });

        $('#applyGroupFilter').on('click', function() {
            self.apply();
        });

        this.modal.on('change', '.consta-group-filter-item input[type="checkbox"]', function() {
            const group = $(this).val();
            const isChecked = $(this).is(':checked');
            
            if (isChecked) {
                if (!self.selectedGroups.includes(group)) {
                    self.selectedGroups.push(group);
                }
            } else {
                const index = self.selectedGroups.indexOf(group);
                if (index > -1) {
                    self.selectedGroups.splice(index, 1);
                }
            }
            
            self.updateSelectAllButton();
        });

        this.modal.on('hidden.bs.modal', function() {
            if (self.onCancel) {
                self.onCancel();
            }
            self.modal.remove();
        });
    }

    filterGroups() {
        if (!this.searchQuery) {
            this.filteredGroups = [...this.groups];
        } else {
            this.filteredGroups = this.groups.filter(group => 
                group.toLowerCase().includes(this.searchQuery)
            );
        }
        $('#groupFilterList').html(this.renderGroups());
        this.updateSelectAllButton();
    }

    selectAll() {
        const visibleGroups = this.filteredGroups;
        const allSelected = visibleGroups.every(group => this.selectedGroups.includes(group));
        
        if (allSelected) {
            visibleGroups.forEach(group => {
                const index = this.selectedGroups.indexOf(group);
                if (index > -1) {
                    this.selectedGroups.splice(index, 1);
                }
            });
        } else {
            visibleGroups.forEach(group => {
                if (!this.selectedGroups.includes(group)) {
                    this.selectedGroups.push(group);
                }
            });
        }
        
        $('#groupFilterList').html(this.renderGroups());
        this.updateSelectAllButton();
    }

    reset() {
        this.selectedGroups = [];
        $('#groupFilterList').html(this.renderGroups());
        this.updateSelectAllButton();
    }

    apply() {
        const checkedGroups = [];
        this.modal.find('.consta-group-filter-item input[type="checkbox"]:checked').each(function() {
            checkedGroups.push($(this).val());
        });
        
        this.selectedGroups = checkedGroups;
        
        
        if (this.onApply) {
            this.onApply(this.selectedGroups);
        }
        this.modal.modal('hide');
    }

    updateSelectAllButton() {
        const visibleGroups = this.filteredGroups;
        if (visibleGroups.length === 0) {
            $('#selectAllGroups').addClass('disabled');
            return;
        }
        
        const allSelected = visibleGroups.every(group => this.selectedGroups.includes(group));
        if (allSelected) {
            $('#selectAllGroups').text('Снять выделение');
            $('#selectAllGroups').removeClass('disabled');
        } else {
            $('#selectAllGroups').text('Выбрать все');
            $('#selectAllGroups').removeClass('disabled');
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

if (typeof window !== 'undefined') {
    window.ConstaGroupFilter = ConstaGroupFilter;
}

