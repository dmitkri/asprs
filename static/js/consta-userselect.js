
class ConstaUserSelect {
    constructor(element, options = {}) {
        this.element = typeof element === 'string' ? document.querySelector(element) : element;
        if (!this.element) {
            return;
        }

        if (!(this.element instanceof HTMLSelectElement)) {
            return;
        }

        this.options = {
            searchable: options.searchable !== undefined ? options.searchable : true,
            placeholder: options.placeholder || 'Выберите студента',
            size: options.size || 'm', // s, m, l
            disabled: options.disabled !== undefined ? options.disabled : this.element.disabled,
            apiUrl: options.apiUrl || '/api/employees/search',
            onChange: options.onChange || null,
            showDetails: options.showDetails !== undefined ? options.showDetails : true, // Показывать корпус, комнату и т.д.
            ...options
        };

        this.isOpen = false;
        this.searchQuery = '';
        this.students = [];
        this.filteredStudents = [];
        this.selectedStudent = null;
        this.init();
    }

    init() {
        this.element.classList.add('consta-userselect-original-select');

        this.wrapper = document.createElement('div');
        this.wrapper.className = 'consta-userselect';
        if (this.options.size !== 'm') {
            this.wrapper.classList.add(`consta-userselect-size-${this.options.size}`);
        }
        this.element.parentNode.insertBefore(this.wrapper, this.element);
        this.wrapper.appendChild(this.element);

        this.buildStructure();

        this.inputWrapper = this.wrapper.querySelector('.consta-userselect-input-wrapper');
        this.input = this.wrapper.querySelector('.consta-userselect-input');
        this.icon = this.wrapper.querySelector('.consta-userselect-icon');
        this.dropdown = this.wrapper.querySelector('.consta-userselect-dropdown');
        this.searchInput = this.wrapper.querySelector('.consta-userselect-search-input');
        this.list = this.wrapper.querySelector('.consta-userselect-list');

        this.attachEventListeners();

        this.loadStudents();
    }

    buildStructure() {
        const searchHtml = this.options.searchable ? `
            <div class="consta-userselect-search">
                <input type="text" class="consta-userselect-search-input" placeholder="Поиск по ФИО...">
            </div>
        ` : '';

        this.wrapper.innerHTML = `
            <div class="consta-userselect-input-wrapper">
                <div class="consta-userselect-input" ${this.options.disabled ? 'disabled' : ''}>
                    <div class="consta-userselect-selected">
                        <span class="consta-userselect-placeholder">${this.options.placeholder}</span>
                    </div>
                </div>
                <div class="consta-userselect-icon">
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M5 7.5L10 12.5L15 7.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </div>
            </div>
            <div class="consta-userselect-dropdown">
                ${searchHtml}
                <ul class="consta-userselect-list"></ul>
            </div>
        `;
    }

    loadStudents(searchQuery = '') {
        const params = { limit: 1000 };
        if (searchQuery) {
            params.q = searchQuery;
        }

        if (typeof $ !== 'undefined') {
            $.get(this.options.apiUrl, params)
                .done((response) => {
                    if (response.success && response.employees) {
                        this.students = response.employees.map(emp => ({
                            id: emp.id,
                            value: emp.id.toString(),
                            label: emp.fio,
                            photo: emp.photo,
                            building: emp.building,
                            entrance: emp.entrance,
                            room_number: emp.room_number,
                            group_name: emp.group_name
                        }));
                        this.renderStudents();
                        if (!searchQuery) {
                            this.updateSelectedValue();
                        }
                    } else {
                        this.students = [];
                        this.renderStudents();
                    }
                })
                .fail(() => {
                    this.students = [];
                    this.renderStudents();
                    if (this.list) {
                        this.list.innerHTML = '<div class="consta-userselect-empty">Ошибка загрузки студентов</div>';
                    }
                });
        } else {
            const url = new URL(this.options.apiUrl, window.location.origin);
            Object.keys(params).forEach(key => url.searchParams.append(key, params[key]));
            
            fetch(url)
                .then(response => response.json())
                .then(data => {
                    if (data.success && data.employees) {
                        this.students = data.employees.map(emp => ({
                            id: emp.id,
                            value: emp.id.toString(),
                            label: emp.fio,
                            photo: emp.photo,
                            building: emp.building,
                            entrance: emp.entrance,
                            room_number: emp.room_number,
                            group_name: emp.group_name
                        }));
                        this.renderStudents();
                        if (!searchQuery) {
                            this.updateSelectedValue();
                        }
                    } else {
                        this.students = [];
                        this.renderStudents();
                    }
                })
                .catch(error => {
                    this.students = [];
                    this.renderStudents();
                    if (this.list) {
                        this.list.innerHTML = '<div class="consta-userselect-empty">Ошибка загрузки студентов</div>';
                    }
                });
        }
    }

    updateSelectedValue() {
        const selectedValue = this.element.value;
        if (selectedValue) {
            const student = this.students.find(s => s.value === selectedValue);
            if (student) {
                this.selectStudent(student);
            }
        } else {
            this.clearSelection();
        }
    }

    selectStudent(student) {
        this.selectedStudent = student;
        
        const selectedDiv = this.input.querySelector('.consta-userselect-selected');
        const photoUrl = student.photo 
            ? `/static/avatars/${student.photo}` 
            : (typeof Utils !== 'undefined' && Utils.generateAvatarWithInitials 
                ? Utils.generateAvatarWithInitials(student.label) 
                : 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAwIDAgMjQgMjQiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGNpcmNsZSBjeD0iMTIiIGN5PSIxMiIgcj0iMTIiIGZpbGw9IiNGM0Y0RjYiLz48L3N2Zz4=');
        
        selectedDiv.innerHTML = `
            <img src="${photoUrl}" alt="${this.escapeHtml(student.label)}" class="consta-userselect-avatar" onerror="this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAwIDAgMjQgMjQiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGNpcmNsZSBjeD0iMTIiIGN5PSIxMiIgcj0iMTIiIGZpbGw9IiNGM0Y0RjYiLz48L3N2Zz4='">
            <span class="consta-userselect-name">${this.escapeHtml(student.label)}</span>
        `;

        this.element.value = student.value;

        this.close();

        if (this.options.onChange) {
            this.options.onChange(student, this);
        }

        const event = new Event('change', { bubbles: true });
        this.element.dispatchEvent(event);

        this.renderStudents();
    }

    clearSelection() {
        this.selectedStudent = null;
        const selectedDiv = this.input.querySelector('.consta-userselect-selected');
        selectedDiv.innerHTML = `<span class="consta-userselect-placeholder">${this.options.placeholder}</span>`;
        this.element.value = '';
    }

    renderStudents() {
        if (!this.list) return;

        this.filteredStudents = this.students;
        
        if (this.searchQuery && this.searchQuery.length > 0) {
            const query = this.searchQuery.toLowerCase();
            this.filteredStudents = this.students.filter(student => {
                return student.label.toLowerCase().includes(query) ||
                       (student.group_name && student.group_name && student.group_name.toLowerCase().includes(query)) ||
                       (student.building && student.building && student.building.toLowerCase().includes(query)) ||
                       (student.room_number && student.room_number && student.room_number.toLowerCase().includes(query)) ||
                       (student.entrance && student.entrance && student.entrance.toLowerCase().includes(query));
            });
        }

        this.list.innerHTML = '';

        if (this.filteredStudents.length === 0) {
            this.list.innerHTML = '<div class="consta-userselect-empty">Ничего не найдено</div>';
            return;
        }

        this.filteredStudents.forEach(student => {
            const li = document.createElement('li');
            li.className = 'consta-userselect-item';
            
            if (this.selectedStudent && student.value === this.selectedStudent.value) {
                li.classList.add('consta-userselect-selected-item');
            }

            const photoUrl = student.photo 
                ? `/static/avatars/${student.photo}` 
                : (typeof Utils !== 'undefined' && Utils.generateAvatarWithInitials 
                    ? Utils.generateAvatarWithInitials(student.label) 
                    : 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzIiIGhlaWdodD0iMzIiIHZpZXdCb3g9IjAwIDAgMzIgMzIiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGNpcmNsZSBjeD0iMTYiIGN5PSIxNiIgcj0iMTYiIGZpbGw9IiNGM0Y0RjYiLz48L3N2Zz4=');

            let detailsHtml = '';
            if (this.options.showDetails) {
                const details = [];
                if (student.group_name) details.push(`Группа: ${this.escapeHtml(student.group_name)}`);
                if (student.building) {
                    const address = [student.building, student.entrance, student.room_number].filter(Boolean).join('-');
                    if (address) details.push(`Проживание: ${this.escapeHtml(address)}`);
                }
                detailsHtml = details.length > 0 
                    ? `<div class="consta-userselect-item-details">${details.join(' • ')}</div>`
                    : '';
            }

            li.innerHTML = `
                <img src="${photoUrl}" alt="${this.escapeHtml(student.label)}" class="consta-userselect-item-avatar" onerror="this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzIiIGhlaWdodD0iMzIiIHZpZXdCb3g9IjAwIDAgMzIgMzIiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGNpcmNsZSBjeD0iMTYiIGN5PSIxNiIgcj0iMTYiIGZpbGw9IiNGM0Y0RjYiLz48L3N2Zz4='">
                <div class="consta-userselect-item-info">
                    <div class="consta-userselect-item-name">${this.escapeHtml(student.label)}</div>
                    ${detailsHtml}
                </div>
                <div class="consta-userselect-check-icon">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M13.3333 4L6 11.3333L2.66667 8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </div>
            `;

            li.addEventListener('click', () => {
                this.selectStudent(student);
            });

            this.list.appendChild(li);
        });
    }

    attachEventListeners() {
        this.input.addEventListener('click', (e) => {
            if (!this.options.disabled) {
                this.toggle();
            }
        });

        if (this.searchInput) {
            let searchTimeout;
            this.searchInput.addEventListener('input', (e) => {
                const query = e.target.value.trim();
                this.searchQuery = query.toLowerCase();
                
                clearTimeout(searchTimeout);
                
                if (!query) {
                    this.loadStudents('');
                } else {
                    searchTimeout = setTimeout(() => {
                        this.loadStudents(query);
                    }, 300);
                }
            });

            this.searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const firstItem = this.list.querySelector('.consta-userselect-item');
                    if (firstItem) {
                        firstItem.click();
                    }
                } else if (e.key === 'Escape') {
                    this.close();
                }
            });
        }

        document.addEventListener('click', (e) => {
            if (!this.wrapper.contains(e.target)) {
                this.close();
            }
        });

        this.input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                if (!this.isOpen) {
                    this.open();
                }
            } else if (e.key === 'Escape') {
                this.close();
            } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (!this.isOpen) {
                    this.open();
                } else {
                    this.focusNextItem();
                }
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                this.focusPreviousItem();
            }
        });
    }

    toggle() {
        if (this.isOpen) {
            this.close();
        } else {
            this.open();
        }
    }

    open() {
        if (this.isOpen || this.options.disabled) return;

        this.isOpen = true;
        this.wrapper.classList.add('consta-userselect-open');
        
        if (this.searchInput) {
            setTimeout(() => {
                this.searchInput.focus();
            }, 100);
        }

        this.renderStudents();
    }

    close() {
        if (!this.isOpen) return;

        this.isOpen = false;
        this.wrapper.classList.remove('consta-userselect-open');
        
        if (this.searchInput) {
            this.searchQuery = '';
            this.searchInput.value = '';
        }
    }

    focusNextItem() {
        const items = this.list.querySelectorAll('.consta-userselect-item');
        const current = this.list.querySelector('.consta-userselect-item:focus');
        
        if (items.length === 0) return;

        if (!current) {
            items[0].focus();
        } else {
            const currentIndex = Array.from(items).indexOf(current);
            const nextIndex = (currentIndex + 1) % items.length;
            items[nextIndex].focus();
        }
    }

    focusPreviousItem() {
        const items = this.list.querySelectorAll('.consta-userselect-item');
        const current = this.list.querySelector('.consta-userselect-item:focus');
        
        if (items.length === 0) return;

        if (!current) {
            items[items.length - 1].focus();
        } else {
            const currentIndex = Array.from(items).indexOf(current);
            const prevIndex = (currentIndex - 1 + items.length) % items.length;
            items[prevIndex].focus();
        }
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    destroy() {
        if (this.wrapper) {
            this.wrapper.remove();
        }
        this.element.classList.remove('consta-userselect-original-select');
    }
}

function initConstaUserSelects(container = document) {
    const selects = container.querySelectorAll('select[data-userselect]:not(.consta-userselect-original-select):not(.consta-userselect-initialized)');
    selects.forEach(select => {
        const searchable = select.getAttribute('data-searchable') !== 'false';
        const placeholder = select.getAttribute('data-placeholder') || 'Выберите студента';
        const size = select.getAttribute('data-size') || 'm';
        const apiUrl = select.getAttribute('data-api-url') || '/api/employees/search';
        const showDetails = select.getAttribute('data-show-details') !== 'false';

        const userSelect = new ConstaUserSelect(select, {
            searchable: searchable,
            placeholder: placeholder,
            size: size,
            disabled: select.disabled,
            apiUrl: apiUrl,
            showDetails: showDetails
        });

        select.classList.add('consta-userselect-initialized');
        select._constaUserSelect = userSelect;
    });
}

if (typeof window !== 'undefined') {
    window.ConstaUserSelect = ConstaUserSelect;
    window.initConstaUserSelects = initConstaUserSelects;
}

