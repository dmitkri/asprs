
class ConstaNotifications {
    constructor() {
        this.container = null;
        this.notifications = new Map();
        this.init();
    }

    init() {
        this.container = document.createElement('div');
        this.container.className = 'consta-notifications-container';
        document.body.appendChild(this.container);
    }

    show(message, type = 'info', title = null, duration = 5000) {
        const id = Date.now() + Math.random();
        const notification = this.createNotification(id, message, type, title);
        
        this.container.appendChild(notification);
        this.notifications.set(id, notification);

        if (duration > 0) {
            setTimeout(() => {
                this.hide(id);
            }, duration);
        }

        return id;
    }

    createNotification(id, message, type, title) {
        const notification = document.createElement('div');
        notification.className = `consta-notification consta-notification--${type}`;
        notification.dataset.notificationId = id;

        const icon = this.getIcon(type);
        const displayTitle = title || this.getDefaultTitle(type);

        notification.innerHTML = `
            <div class="consta-notification-icon">
                ${icon}
            </div>
            <div class="consta-notification-content">
                ${displayTitle ? `<div class="consta-notification-title">${this.escapeHtml(displayTitle)}</div>` : ''}
                <div class="consta-notification-message">${this.escapeHtml(message)}</div>
            </div>
            <button type="button" class="consta-notification-close" aria-label="Закрыть">
                <svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 4L4 12M4 4L12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            </button>
        `;

        const closeBtn = notification.querySelector('.consta-notification-close');
        closeBtn.addEventListener('click', () => {
            this.hide(id);
        });

        return notification;
    }

    getIcon(type) {
        const icons = {
            success: `
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M20 6L9 17L4 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            `,
            error: `
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            `,
            warning: `
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 9V13M12 17H12.01M21 12C21 16.9706 16.9706 21 12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            `,
            info: `
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 16V12M12 8H12.01M21 12C21 16.9706 16.9706 21 12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            `
        };
        return icons[type] || icons.info;
    }

    getDefaultTitle(type) {
        const titles = {
            success: 'Успешно',
            error: 'Ошибка',
            warning: 'Внимание',
            info: 'Информация'
        };
        return titles[type] || titles.info;
    }

    hide(id) {
        const notification = this.notifications.get(id);
        if (notification) {
            notification.classList.add('slide-out');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
                this.notifications.delete(id);
            }, 300);
        }
    }

    hideAll() {
        this.notifications.forEach((notification, id) => {
            this.hide(id);
        });
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

let notificationsInstance = null;

function initNotifications() {
    if (!notificationsInstance) {
        notificationsInstance = new ConstaNotifications();
    }
    return notificationsInstance;
}

function showNotification(message, type = 'info', title = null, duration = 5000) {
    const notifications = initNotifications();
    return notifications.show(message, type, title, duration);
}

function showSuccess(message, title = null, duration = 5000) {
    return showNotification(message, 'success', title, duration);
}

function showError(message, title = null, duration = 7000) {
    return showNotification(message, 'error', title, duration);
}

function showWarning(message, title = null, duration = 6000) {
    return showNotification(message, 'warning', title, duration);
}

function showInfo(message, title = null, duration = 5000) {
    return showNotification(message, 'info', title, duration);
}

const originalAlert = window.alert;
window.alert = function(message) {
    if (!message) return;
    
    const msg = String(message).toLowerCase();
    let type = 'info';
    let title = 'Уведомление';
    let duration = 4000;
    
    if (msg.includes('успех') || msg.includes('создан') || msg.includes('сохранено') || 
        msg.includes('загружен') || msg.includes('удален') || msg.includes('обновлен') ||
        msg.includes('добавлен') || msg.includes('выполнено') || msg.includes('отправлено') ||
        msg.includes('выздоровел') || msg.includes('продолжение')) {
        type = 'success';
        title = 'Успешно';
        duration = 4000;
    }
    else if (msg.includes('ошибка') || msg.includes('не удалось') || msg.includes('не найдено') || 
             msg.includes('неверный') || msg.includes('необходимо') || msg.includes('обязательно') ||
             msg.includes('не установлен') || msg.includes('не указан') || msg.includes('не удалось определить')) {
        type = 'error';
        title = 'Ошибка';
        duration = 6000;
    }
    else if (msg.includes('внимание') || msg.includes('предупреждение') || msg.includes('осторожно')) {
        type = 'warning';
        title = 'Внимание';
        duration = 5000;
    }
    
    showNotification(message, type, title, duration);
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNotifications);
} else {
    initNotifications();
}

if (typeof window !== 'undefined') {
    window.ConstaNotifications = ConstaNotifications;
    window.showNotification = showNotification;
    window.showSuccess = showSuccess;
    window.showError = showError;
    window.showWarning = showWarning;
    window.showInfo = showInfo;
    window.initNotifications = initNotifications;
}

