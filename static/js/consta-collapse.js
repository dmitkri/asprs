
class ConstaCollapse {
    constructor(element, options = {}) {
        this.element = typeof element === 'string' ? document.querySelector(element) : element;
        if (!this.element) {
            return;
        }

        this.options = {
            isOpen: options.isOpen !== undefined ? options.isOpen : false,
            size: options.size || 'm', // s, m, l
            divider: options.divider || false,
            disabled: options.disabled || false,
            onToggle: options.onToggle || null,
            ...options
        };

        this.isOpen = this.options.isOpen;
        this.init();
    }

    init() {
        this.element.classList.add('consta-collapse');

        if (!this.element.querySelector('.consta-collapse-header')) {
            this.buildStructure();
        }

        this.header = this.element.querySelector('.consta-collapse-header');
        this.body = this.element.querySelector('.consta-collapse-body');
        this.icon = this.element.querySelector('.consta-collapse-icon');

        if (!this.header || !this.body) {
            return;
        }

        if (this.options.size !== 'm') {
            this.element.classList.add(`consta-collapse-size-${this.options.size}`);
        }

        if (this.options.divider) {
            this.element.classList.add('consta-collapse-divider');
        }

        if (this.options.disabled) {
            this.header.classList.add('consta-collapse-disabled');
        }

        if (this.isOpen) {
            this.element.classList.add('consta-collapse-open');
        }

        this.header.addEventListener('click', () => {
            if (!this.options.disabled) {
                this.toggle();
            }
        });
    }

    buildStructure() {
        const label = this.element.getAttribute('data-label') || 'Заголовок';
        const existingContent = this.element.innerHTML;

        this.element.innerHTML = `
            <div class="consta-collapse-header">
                <div class="consta-collapse-label">${label}</div>
                <div class="consta-collapse-icon">
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M5 7.5L10 12.5L15 7.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </div>
            </div>
            <div class="consta-collapse-body">
                <div class="consta-collapse-content">
                    ${existingContent}
                </div>
            </div>
        `;
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
        this.element.classList.add('consta-collapse-open');

        if (this.options.onToggle) {
            this.options.onToggle(true, this);
        }
    }

    close() {
        if (!this.isOpen || this.options.disabled) return;

        this.isOpen = false;
        this.element.classList.remove('consta-collapse-open');

        if (this.options.onToggle) {
            this.options.onToggle(false, this);
        }
    }

    destroy() {
        if (this.header) {
            this.header.removeEventListener('click', this.toggle);
        }
        this.element.classList.remove('consta-collapse', 'consta-collapse-open', `consta-collapse-size-${this.options.size}`, 'consta-collapse-divider');
    }
}

function initConstaCollapses(container = document) {
    const elements = container.querySelectorAll('[data-collapse]');
    elements.forEach(element => {
        if (element.classList.contains('consta-collapse-initialized')) {
            return;
        }

        const label = element.getAttribute('data-label') || 'Заголовок';
        const isOpen = element.getAttribute('data-open') === 'true';
        const size = element.getAttribute('data-size') || 'm';
        const divider = element.getAttribute('data-divider') === 'true';
        const disabled = element.getAttribute('data-disabled') === 'true';

        const collapse = new ConstaCollapse(element, {
            isOpen: isOpen,
            size: size,
            divider: divider,
            disabled: disabled
        });

        element.classList.add('consta-collapse-initialized');
        element._constaCollapse = collapse;
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        initConstaCollapses();
    });
} else {
    initConstaCollapses();
}

const collapseObserver = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
            if (node.nodeType === 1) { // Element node
                if (node.hasAttribute && node.hasAttribute('data-collapse')) {
                    initConstaCollapses(node.parentElement || document);
                } else if (node.querySelectorAll) {
                    const collapses = node.querySelectorAll('[data-collapse]');
                    if (collapses.length > 0) {
                        initConstaCollapses(node);
                    }
                }
            }
        });
    });
});

collapseObserver.observe(document.body, {
    childList: true,
    subtree: true
});

if (typeof window !== 'undefined') {
    window.ConstaCollapse = ConstaCollapse;
    window.initConstaCollapses = initConstaCollapses;
}








