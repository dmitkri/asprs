
class ConstaBanner {
    constructor(options = {}) {
        this.options = {
            view: options.view || 'info', // 'info', 'success', 'warning', 'error'
            label: options.label || '',
            text: options.text || '',
            actions: options.actions || [],
            onClose: options.onClose || null,
            duration: options.duration || null, // Автоматическое закрытие через N миллисекунд
            closable: options.closable !== false, // Можно ли закрыть
            ...options
        };
        
        this.element = null;
        this.container = null;
        this.init();
    }

    init() {
        let container = document.getElementById('consta-banners-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'consta-banners-container';
            container.className = 'consta-banners-container';
            document.body.appendChild(container);
        }
        this.container = container;
        
        if (this.container) {
            this.container.style.display = 'flex';
            this.container.style.visibility = 'visible';
            this.container.style.zIndex = '99999';
        }

        this.element = document.createElement('div');
        this.element.className = `consta-banner consta-banner--${this.options.view}`;
        
        this.render();
        
        this.container.appendChild(this.element);
        
        setTimeout(() => {
            this.element.classList.add('consta-banner--visible');
        }, 10);

        if (this.options.duration && this.options.duration > 0) {
            setTimeout(() => {
                this.close();
            }, this.options.duration);
        }
    }

    render() {
        let html = '<div class="consta-banner__content">';
        
        
        html += '<div class="consta-banner__text">';
        if (this.options.label) {
            html += `<div class="consta-banner__label">${this.escapeHtml(this.options.label)}</div>`;
        }
        if (this.options.text) {
            const textContent = (this.options.text.includes('<br>') || this.options.text.includes('<br/>') || this.options.text.includes('<br />')) 
                ? this.options.text 
                : this.escapeHtml(this.options.text);
            html += `<div class="consta-banner__description">${textContent}</div>`;
        }
        html += '</div>';
        
        if (this.options.actions && this.options.actions.length > 0) {
            html += '<div class="consta-banner__actions">';
            this.options.actions.forEach((action, index) => {
                if (typeof action === 'string') {
                    html += `<button class="consta-banner__action-btn" data-action-index="${index}">${this.escapeHtml(action)}</button>`;
                } else if (action && action.text) {
                    html += `<button class="consta-banner__action-btn" data-action-index="${index}">${this.escapeHtml(action.text)}</button>`;
                }
            });
            html += '</div>';
        }
        
        html += '</div>';
        
        if (this.options.closable) {
            html += '<button class="consta-banner__close" onclick="this.closest(\'.consta-banner\').constaBannerInstance.close()">×</button>';
        }
        
        this.element.innerHTML = html;
        
        this.element.constaBannerInstance = this;
        
        this.element.querySelectorAll('.consta-banner__action-btn').forEach((btn) => {
            const actionIndex = btn.getAttribute('data-action-index');
            if (actionIndex !== null && this.options.actions[actionIndex] && this.options.actions[actionIndex].onClick) {
                btn.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.options.actions[actionIndex].onClick();
                });
            }
        });
    }

    getIcon() {
        const icons = {
            info: '<svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="10" cy="10" r="9" stroke="currentColor" stroke-width="2"/><path d="M10 6V10M10 14H10.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
            success: '<svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="10" cy="10" r="9" stroke="currentColor" stroke-width="2"/><path d="M6 10L9 13L14 7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
            warning: '<svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M10 6V10M10 14H10.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M2 16L10 2L18 16H2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
            error: '<svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="10" cy="10" r="9" stroke="currentColor" stroke-width="2"/><path d="M10 6V10M10 14H10.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
        };
        return icons[this.options.view] || icons.info;
    }

    close() {
        if (this.element) {
            this.element.classList.remove('consta-banner--visible');
            this.element.classList.add('consta-banner--closing');
            
            setTimeout(() => {
                if (this.element && this.element.parentNode) {
                    this.element.parentNode.removeChild(this.element);
                }
                if (this.options.onClose) {
                    this.options.onClose();
                }
            }, 300);
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

function showBanner(options) {
    if (typeof options === 'string') {
        options = { text: options };
    }
    return new ConstaBanner(options);
}

function showBannerInfo(text, label = 'Информация', actions = [], duration = 5000) {
    return new ConstaBanner({
        view: 'info',
        label: label,
        text: text,
        actions: actions,
        duration: duration
    });
}

function showBannerSuccess(text, label = 'Успешно', actions = [], duration = 5000) {
    return new ConstaBanner({
        view: 'success',
        label: label,
        text: text,
        actions: actions,
        duration: duration
    });
}

function showBannerWarning(text, label = 'Внимание', actions = [], duration = 6000) {
    return new ConstaBanner({
        view: 'warning',
        label: label,
        text: text,
        actions: actions,
        duration: duration
    });
}

function showBannerError(text, label = 'Ошибка', actions = [], duration = 7000) {
    return new ConstaBanner({
        view: 'error',
        label: label,
        text: text,
        actions: actions,
        duration: duration
    });
}

if (!window._bannerAlertReplaced) {
    window._originalAlert = window.alert;
    window.alert = function(message) {
        const msg = String(message).toLowerCase();
        if (msg.includes('успех') || msg.includes('создан') || msg.includes('сохранено') || msg.includes('загружен') || msg.includes('удален') || msg.includes('обновлен') || msg.includes('добавлен') || msg.includes('выполнено') || msg.includes('отправлено') || msg.includes('выздоровел')) {
            showBannerSuccess(message, 'Успешно');
        } else if (msg.includes('ошибка') || msg.includes('не удалось') || msg.includes('не найдено') || msg.includes('неверный') || msg.includes('необходимо') || msg.includes('обязательно') || msg.includes('не установлен')) {
            showBannerError(message, 'Ошибка');
        } else if (msg.includes('внимание') || msg.includes('предупреждение')) {
            showBannerWarning(message, 'Внимание');
        } else {
            showBannerInfo(message, 'Уведомление');
        }
    };
    window._bannerAlertReplaced = true;
}

if (typeof window.showBannerConfirm === 'undefined') {
window.showBannerConfirm = function(message, onConfirm, onCancel) {
    let bannerInstance = null;
    
    const onConfirmClick = () => {
        if (bannerInstance) {
            bannerInstance.close();
        }
        if (onConfirm) {
            onConfirm();
        }
    };
    
    const onCancelClick = () => {
        if (bannerInstance) {
            bannerInstance.close();
        }
        if (onCancel) {
            onCancel();
        }
    };
    
    const options = {
        view: 'warning',
        label: 'Подтверждение',
        text: message,
        actions: [
            {
                text: 'Да',
                onClick: onConfirmClick
            },
            {
                text: 'Нет',
                onClick: onCancelClick
            }
        ],
        closable: true,
        duration: null // Не закрывается автоматически
    };
    
    bannerInstance = new ConstaBanner(options);
    return bannerInstance;
};
}

if (typeof window !== 'undefined') {
    window.ConstaBanner = ConstaBanner;
    window.showBanner = showBanner;
    window.showBannerInfo = showBannerInfo;
    window.showBannerSuccess = showBannerSuccess;
    window.showBannerWarning = showBannerWarning;
    window.showBannerError = showBannerError;
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            if (!document.getElementById('consta-banners-container')) {
                const container = document.createElement('div');
                container.id = 'consta-banners-container';
                container.className = 'consta-banners-container';
                document.body.appendChild(container);
            }
        });
    } else {
        if (!document.getElementById('consta-banners-container')) {
            const container = document.createElement('div');
            container.id = 'consta-banners-container';
            container.className = 'consta-banners-container';
            document.body.appendChild(container);
        }
    }
}

