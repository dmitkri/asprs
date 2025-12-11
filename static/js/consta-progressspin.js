
class ConstaProgressSpin {
    constructor(element, options = {}) {
        this.element = typeof element === 'string' ? document.querySelector(element) : element;
        if (!this.element) {
            return;
        }
        
        if (!this.element.parentNode && this.element !== document.body) {
        }

        this.options = {
            progress: options.progress || 0, // 0-100
            size: options.size || 'm', // 's', 'm', 'l'
            color: options.color || 'auto', // 'auto', 'success', 'warning', 'danger'
            showText: options.showText !== false, // показывать ли текст внутри
            ...options
        };

        this.progress = Math.max(0, Math.min(100, this.options.progress));
        this.init();
    }

    init() {
        this.createStructure();
        this.updateProgress(this.progress);
    }

    createStructure() {
        this.element.innerHTML = '';
        
        const sizeClass = `consta-progressspin--${this.options.size}`;
        const colorClass = this.getColorClass();
        
        this.element.className = `consta-progressspin ${sizeClass} ${colorClass}`;
        
        const radius = this.getRadius();
        const circumference = 2 * Math.PI * radius;
        
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('viewBox', '0 0 40 40');
        
        const circleBg = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circleBg.setAttribute('cx', '20');
        circleBg.setAttribute('cy', '20');
        circleBg.setAttribute('r', radius.toString());
        circleBg.setAttribute('class', 'consta-progressspin-circle-bg');
        
        const circleProgress = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circleProgress.setAttribute('cx', '20');
        circleProgress.setAttribute('cy', '20');
        circleProgress.setAttribute('r', radius.toString());
        circleProgress.setAttribute('class', 'consta-progressspin-circle-progress');
        circleProgress.setAttribute('stroke-dasharray', circumference.toString());
        circleProgress.setAttribute('stroke-dashoffset', circumference.toString());
        
        svg.appendChild(circleBg);
        svg.appendChild(circleProgress);
        this.element.appendChild(svg);
        
        this.circleProgress = circleProgress;
        this.circumference = circumference;
        
        if (this.options.showText) {
            const text = document.createElement('span');
            text.className = 'consta-progressspin-text';
            text.textContent = Math.round(this.progress);
            this.element.appendChild(text);
            this.textElement = text;
        }
    }

    getRadius() {
        const sizes = {
            's': 13,
            'm': 16,
            'l': 19
        };
        return sizes[this.options.size] || 16;
    }

    getColorClass() {
        if (this.options.color !== 'auto') {
            return `consta-progressspin--${this.options.color}`;
        }
        
        if (this.progress >= 80) {
            return 'consta-progressspin--success';
        } else if (this.progress >= 50) {
            return 'consta-progressspin--warning';
        } else {
            return 'consta-progressspin--danger';
        }
    }

    updateProgress(progress) {
        this.progress = Math.max(0, Math.min(100, progress));
        
        if (this.circleProgress) {
            const offset = this.circumference - (this.progress / 100) * this.circumference;
            this.circleProgress.setAttribute('stroke-dashoffset', offset.toString());
        }
        
        if (this.textElement) {
            this.textElement.textContent = Math.round(this.progress);
        }
        
        if (this.options.color === 'auto') {
            const oldColorClass = this.element.className.match(/consta-progressspin--(success|warning|danger)/);
            if (oldColorClass) {
                this.element.classList.remove(oldColorClass[0]);
            }
            this.element.classList.add(this.getColorClass());
        }
    }

    setProgress(progress) {
        this.updateProgress(progress);
    }
}

function createProgressSpin(container, progress, options = {}) {
    const element = document.createElement('div');
    container.appendChild(element);
    return new ConstaProgressSpin(element, { progress, ...options });
}

function initConstaProgressSpins(container) {
    const searchContainer = container || document;
    const elements = searchContainer.querySelectorAll('[data-progressspin]:not(.consta-progressspin-initialized)');
    
    if (elements.length > 0) {
    }
    
    elements.forEach(element => {
        try {
            const progress = parseFloat(element.dataset.progressspin) || 0;
            const size = element.dataset.size || 'm';
            const color = element.dataset.color || 'auto';
            const showText = element.dataset.showText !== 'false';
            
            
            new ConstaProgressSpin(element, {
                progress,
                size,
                color,
                showText
            });
            
            element.classList.add('consta-progressspin-initialized');
        } catch (e) {
        }
    });
    
    return elements.length;
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        setTimeout(initConstaProgressSpins, 100);
    });
} else {
    setTimeout(initConstaProgressSpins, 100);
}

if (typeof MutationObserver !== 'undefined') {
    const progressSpinObserver = new MutationObserver(function(mutations) {
        let needsInit = false;
        mutations.forEach(function(mutation) {
            mutation.addedNodes.forEach(function(node) {
                if (node.nodeType === 1) { // Element node
                    if (node.hasAttribute && node.hasAttribute('data-progressspin')) {
                        needsInit = true;
                    } else if (node.querySelectorAll && node.querySelectorAll('[data-progressspin]').length > 0) {
                        needsInit = true;
                    }
                }
            });
        });
        
        if (needsInit) {
            setTimeout(function() {
                initConstaProgressSpins();
            }, 10);
        }
    });

    progressSpinObserver.observe(document.body, {
        childList: true,
        subtree: true
    });
}

if (typeof window !== 'undefined') {
    window.ConstaProgressSpin = ConstaProgressSpin;
    window.createProgressSpin = createProgressSpin;
    window.initConstaProgressSpins = initConstaProgressSpins;
}

