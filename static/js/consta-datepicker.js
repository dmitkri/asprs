
function initConstaDatePickers() {
    if (typeof flatpickr === 'undefined') {
        return;
    }

    let locale = flatpickr.l10ns.ru || {
        firstDayOfWeek: 1,
        weekdays: {
            shorthand: ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'],
            longhand: ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']
        },
        months: {
            shorthand: ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек'],
            longhand: ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
        }
    };

    const constaConfig = {
        dateFormat: 'Y-m-d',
        locale: locale,
        allowInput: true,
        clickOpens: true,
        animate: true,
        theme: 'consta-theme',
        monthSelectorType: 'static',
        static: true
    };

    document.querySelectorAll('input[type="date"]:not(.consta-datepicker-initialized):not([data-no-consta-datepicker])').forEach(input => {
        const originalValue = input.value;
        
        let wrapper = input.parentElement;
        if (!wrapper.classList.contains('consta-datepicker-wrapper')) {
            wrapper = document.createElement('div');
            wrapper.className = 'consta-datepicker-wrapper';
            input.parentNode.insertBefore(wrapper, input);
            wrapper.appendChild(input);
        }

        try {
            const fp = flatpickr(input, {
                ...constaConfig,
                defaultDate: originalValue || undefined,
                appendTo: input.closest('.modal') || document.body,
                onChange: function(selectedDates, dateStr, instance) {
                    const event = new Event('change', { bubbles: true });
                    input.dispatchEvent(event);
                }
            });

            input.classList.add('consta-datepicker-initialized');
        } catch (e) {
        }
    });

    document.querySelectorAll('input[type="month"]:not(.consta-datepicker-initialized):not([data-no-consta-datepicker])').forEach(input => {
        const originalValue = input.value;
        
        let wrapper = input.parentElement;
        if (!wrapper.classList.contains('consta-datepicker-wrapper')) {
            wrapper = document.createElement('div');
            wrapper.className = 'consta-datepicker-wrapper';
            input.parentNode.insertBefore(wrapper, input);
            wrapper.appendChild(input);
        }

        try {
            const fp = flatpickr(input, {
                ...constaConfig,
                dateFormat: 'Y-m',
                defaultDate: originalValue || undefined,
                appendTo: input.closest('.modal') || document.body,
                onChange: function(selectedDates, dateStr, instance) {
                    const event = new Event('change', { bubbles: true });
                    input.dispatchEvent(event);
                }
            });

            input.classList.add('consta-datepicker-initialized');
        } catch (e) {
        }
    });
}

function initConstaDatePicker(selector, options = {}) {
    if (typeof flatpickr === 'undefined') {
        return null;
    }

    const element = typeof selector === 'string' ? document.querySelector(selector) : selector;
    if (!element) return null;

    const defaultConfig = {
        dateFormat: element.type === 'month' ? 'Y-m' : 'Y-m-d',
        locale: {
            firstDayOfWeek: 1,
            weekdays: {
                shorthand: ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'],
                longhand: ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']
            },
            months: {
                shorthand: ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек'],
                longhand: ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
            }
        },
        allowInput: true,
        clickOpens: true,
        animate: true,
        theme: 'consta-theme',
        monthSelectorType: 'static',
        static: true
    };

    const config = { ...defaultConfig, ...options };
    
    if (!element.parentElement.classList.contains('consta-datepicker-wrapper')) {
        const wrapper = document.createElement('div');
        wrapper.className = 'consta-datepicker-wrapper';
        element.parentNode.insertBefore(wrapper, element);
        wrapper.appendChild(element);
    }

    return flatpickr(element, config);
}

if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(initConstaDatePickers, 100);
        });
    } else {
        setTimeout(initConstaDatePickers, 100);
    }

    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            mutation.addedNodes.forEach(function(node) {
                if (node.nodeType === 1) { // Element node
                    if ((node.tagName === 'INPUT' && (node.type === 'date' || node.type === 'month')) && !node.classList.contains('consta-datepicker-initialized') && !node.hasAttribute('data-no-consta-datepicker')) {
                        setTimeout(function() {
                            initConstaDatePicker(node);
                        }, 50);
                    } else if (node.querySelectorAll) {
                        const dateInputs = node.querySelectorAll('input[type="date"]:not(.consta-datepicker-initialized):not([data-no-consta-datepicker]), input[type="month"]:not(.consta-datepicker-initialized):not([data-no-consta-datepicker])');
                        if (dateInputs.length > 0) {
                            setTimeout(function() {
                                initConstaDatePickers();
                            }, 50);
                        }
                    }
                }
            });
        });
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
}

if (typeof window !== 'undefined') {
    window.ConstaDatePicker = {
        init: initConstaDatePickers,
        initElement: initConstaDatePicker
    };
}
