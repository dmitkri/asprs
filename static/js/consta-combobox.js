
class ConstaCombobox {
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
            placeholder: options.placeholder || 'Выберите значение',
            size: options.size || 'm', // s, m, l
            disabled: options.disabled !== undefined ? options.disabled : this.element.disabled,
            onChange: options.onChange || null,
            ...options
        };

        this.isOpen = false;
        this.searchQuery = '';
        this.filteredItems = [];
        this.init();
    }

    init() {
        this.element.classList.add('consta-combobox-original-select');

        this.wrapper = document.createElement('div');
        this.wrapper.className = 'consta-combobox';
        if (this.options.size !== 'm') {
            this.wrapper.classList.add(`consta-combobox-size-${this.options.size}`);
        }
        this.element.parentNode.insertBefore(this.wrapper, this.element);
        this.wrapper.appendChild(this.element);

        this.buildStructure();

        this.inputWrapper = this.wrapper.querySelector('.consta-combobox-input-wrapper');
        this.input = this.wrapper.querySelector('.consta-combobox-input');
        this.icon = this.wrapper.querySelector('.consta-combobox-icon');
        this.dropdown = this.wrapper.querySelector('.consta-combobox-dropdown');
        this.searchInput = this.wrapper.querySelector('.consta-combobox-search-input');
        this.list = this.wrapper.querySelector('.consta-combobox-list');

        this.items = this.getItemsFromSelect();

        this.updateInputValue();

        this.attachEventListeners();

        this.renderItems();
    }

    buildStructure() {
        const searchHtml = this.options.searchable ? `
            <div class="consta-combobox-search">
                <input type="text" class="consta-combobox-search-input" placeholder="Поиск...">
            </div>
        ` : '';

        this.wrapper.innerHTML = `
            <div class="consta-combobox-input-wrapper">
                <input type="text" class="consta-combobox-input" 
                       placeholder="${this.options.placeholder}" 
                       readonly
                       ${this.options.disabled ? 'disabled' : ''}>
                <div class="consta-combobox-icon">
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M5 7.5L10 12.5L15 7.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </div>
            </div>
            <div class="consta-combobox-dropdown">
                ${searchHtml}
                <ul class="consta-combobox-list"></ul>
            </div>
        `;
    }

    getItemsFromSelect() {
        const items = [];
        const options = this.element.querySelectorAll('option');
        
        options.forEach((option, index) => {
            items.push({
                value: option.value,
                label: option.textContent.trim(),
                disabled: option.disabled,
                selected: option.selected,
                index: index
            });
        });

        return items;
    }

    updateInputValue() {
        const selectedOption = this.element.options[this.element.selectedIndex];
        if (selectedOption && selectedOption.value !== '') {
            this.input.value = selectedOption.textContent.trim();
        } else {
            this.input.value = '';
        }
    }

    attachEventListeners() {
        this.input.addEventListener('click', (e) => {
            if (!this.options.disabled) {
                this.toggle();
            }
        });

        if (this.searchInput) {
            this.searchInput.addEventListener('input', (e) => {
                this.searchQuery = e.target.value.toLowerCase();
                this.renderItems();
            });

            this.searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const firstItem = this.list.querySelector('.consta-combobox-item:not(.consta-combobox-disabled)');
                    if (firstItem) {
                        firstItem.click();
                    }
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

    renderItems() {
        if (!this.list) return;

        this.filteredItems = this.items.filter(item => {
            if (this.searchQuery) {
                return item.label.toLowerCase().includes(this.searchQuery);
            }
            return true;
        });

        this.list.innerHTML = '';

        if (this.filteredItems.length === 0) {
            this.list.innerHTML = '<div class="consta-combobox-empty">Ничего не найдено</div>';
            return;
        }

        this.filteredItems.forEach(item => {
            const li = document.createElement('li');
            li.className = 'consta-combobox-item';
            
            if (item.disabled) {
                li.classList.add('consta-combobox-disabled');
            }
            
            if (item.value === this.element.value) {
                li.classList.add('consta-combobox-selected');
            }

            li.innerHTML = `
                <div class="consta-combobox-check-icon">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M13.3333 4L6 11.3333L2.66667 8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </div>
                <span>${this.escapeHtml(item.label)}</span>
            `;

            if (!item.disabled) {
                li.addEventListener('click', () => {
                    this.selectItem(item.value);
                });
            }

            this.list.appendChild(li);
        });
    }

    selectItem(value) {
        this.element.value = value;
        
        this.updateInputValue();

        this.close();

        if (this.options.onChange) {
            this.options.onChange(value, this);
        }

        const event = new Event('change', { bubbles: true });
        this.element.dispatchEvent(event);

        this.renderItems();
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
        this.wrapper.classList.add('consta-combobox-open');
        
        if (this.searchInput) {
            setTimeout(() => {
                this.searchInput.focus();
            }, 100);
        }

        this.renderItems();
    }

    close() {
        if (!this.isOpen) return;

        this.isOpen = false;
        this.wrapper.classList.remove('consta-combobox-open');
        
        if (this.searchInput) {
            this.searchQuery = '';
            this.searchInput.value = '';
        }
    }

    focusNextItem() {
        const items = this.list.querySelectorAll('.consta-combobox-item:not(.consta-combobox-disabled)');
        const current = this.list.querySelector('.consta-combobox-item:focus');
        
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
        const items = this.list.querySelectorAll('.consta-combobox-item:not(.consta-combobox-disabled)');
        const current = this.list.querySelector('.consta-combobox-item:focus');
        
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
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    destroy() {
        if (this.wrapper) {
            this.wrapper.remove();
        }
        this.element.classList.remove('consta-combobox-original-select');
    }
}

function initConstaComboboxes(container = document) {
    const selects = container.querySelectorAll('select:not(.consta-combobox-original-select):not(.consta-combobox-initialized)');
    selects.forEach(select => {
        if (select.closest('.modal')) {
            return;
        }
        
        if (select.hasAttribute('data-no-combobox')) {
            return;
        }

        const combobox = new ConstaCombobox(select, {
            searchable: select.hasAttribute('data-searchable') ? select.getAttribute('data-searchable') === 'true' : true,
            placeholder: select.getAttribute('data-placeholder') || 'Выберите значение',
            size: select.getAttribute('data-size') || 'm',
            disabled: select.disabled
        });

        select.classList.add('consta-combobox-initialized');
        select._constaCombobox = combobox;
    });
}

function removeComboboxFromElement(select) {
    if (select._constaCombobox) {
        const wrapper = select.closest('.consta-combobox');
        if (wrapper && wrapper.parentNode) {
            wrapper.parentNode.insertBefore(select, wrapper);
            wrapper.remove();
        }
        select.classList.remove('consta-combobox-initialized', 'consta-combobox-original-select');
        delete select._constaCombobox;
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('select[data-no-combobox="true"]').forEach(select => {
            removeComboboxFromElement(select);
        });
        initConstaComboboxes();
    });
} else {
    document.querySelectorAll('select[data-no-combobox="true"]').forEach(select => {
        removeComboboxFromElement(select);
    });
    initConstaComboboxes();
}

const comboboxObserver = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
            if (node.nodeType === 1) { // Element node
                if (node.tagName === 'SELECT' && node.hasAttribute('data-no-combobox')) {
                    removeComboboxFromElement(node);
                } else if (node.querySelectorAll) {
                    node.querySelectorAll('select[data-no-combobox="true"]').forEach(select => {
                        removeComboboxFromElement(select);
                    });
                }
                
                if (node.tagName === 'SELECT' && !node.classList.contains('consta-combobox-initialized') && !node.hasAttribute('data-no-combobox')) {
                    initConstaComboboxes(node.parentElement || document);
                } else if (node.querySelectorAll) {
                    const selects = node.querySelectorAll('select:not(.consta-combobox-initialized):not([data-no-combobox])');
                    if (selects.length > 0) {
                        initConstaComboboxes(node);
                    }
                }
            }
        });
    });
});

if (document.body) {
    comboboxObserver.observe(document.body, {
        childList: true,
        subtree: true
    });
} else {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            if (document.body) {
                comboboxObserver.observe(document.body, {
                    childList: true,
                    subtree: true
                });
            }
        });
    } else {
        setTimeout(function() {
            if (document.body) {
                comboboxObserver.observe(document.body, {
                    childList: true,
                    subtree: true
                });
            }
        }, 100);
    }
}

if (typeof window !== 'undefined') {
    window.ConstaCombobox = ConstaCombobox;
    window.initConstaComboboxes = initConstaComboboxes;
}


