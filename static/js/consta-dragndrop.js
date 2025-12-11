
class ConstaDragNDropField {
    constructor(element, options = {}) {
        this.element = typeof element === 'string' ? document.querySelector(element) : element;
        if (!this.element) {
            return;
        }

        this.options = {
            accept: '*',
            multiple: false,
            maxSize: null,
            onDrop: null,
            onError: null,
            disabled: false
        };
        
        if (options.accept !== undefined) this.options.accept = options.accept;
        if (options.multiple !== undefined) this.options.multiple = options.multiple;
        if (options.maxSize !== undefined) this.options.maxSize = options.maxSize;
        if (options.onDrop !== undefined && typeof options.onDrop === 'function') {
            this.options.onDrop = options.onDrop;
        }
        if (options.onError !== undefined && typeof options.onError === 'function') {
            this.options.onError = options.onError;
        }
        if (options.disabled !== undefined) this.options.disabled = options.disabled;
        this.isDragging = false;
        this.init();
    }

    init() {
        this.createStructure();
        this.attachEvents();
    }

    createStructure() {
        const originalInput = this.element.querySelector('input[type="file"]');
        if (originalInput) {
            this.originalInput = originalInput;
            this.options.accept = originalInput.accept || this.options.accept;
            this.options.multiple = originalInput.multiple || this.options.multiple;
        } else {
            this.originalInput = document.createElement('input');
            this.originalInput.type = 'file';
            this.originalInput.accept = this.options.accept;
            this.originalInput.multiple = this.options.multiple;
            this.element.appendChild(this.originalInput);
        }

        const wrapper = document.createElement('div');
        wrapper.className = 'consta-dragndrop-wrapper';
        if (this.options.disabled) {
            wrapper.classList.add('consta-dragndrop-disabled');
        }

        const dropZone = document.createElement('div');
        dropZone.className = 'consta-dragndrop-zone';
        dropZone.innerHTML = `
            <div class="consta-dragndrop-content">
                <div class="consta-dragndrop-icon">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M12 5V19M5 12H19" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                    </svg>
                </div>
                <div class="consta-dragndrop-text">
                    <span class="consta-dragndrop-title">Перетащите файл сюда</span>
                    <span class="consta-dragndrop-subtitle">или нажмите для выбора</span>
                </div>
            </div>
            <div class="consta-dragndrop-files"></div>
        `;

        wrapper.appendChild(dropZone);
        
        if (this.originalInput.parentElement !== this.element) {
            this.element.appendChild(this.originalInput);
        }
        
        this.originalInput.style.position = 'absolute';
        this.originalInput.style.width = '1px';
        this.originalInput.style.height = '1px';
        this.originalInput.style.padding = '0';
        this.originalInput.style.margin = '-1px';
        this.originalInput.style.overflow = 'hidden';
        this.originalInput.style.clip = 'rect(0, 0, 0, 0)';
        this.originalInput.style.whiteSpace = 'nowrap';
        this.originalInput.style.borderWidth = '0';
        this.originalInput.style.opacity = '0';
        this.originalInput.style.pointerEvents = 'none';
        this.originalInput.style.visibility = 'hidden';
        
        const existingContent = Array.from(this.element.childNodes);
        existingContent.forEach(node => {
            if (node !== this.originalInput && node.nodeType === 1 && !node.classList?.contains('consta-dragndrop-wrapper')) {
                node.remove();
            }
        });
        
        this.element.appendChild(wrapper);
        
        this.wrapper = wrapper;
        this.dropZone = dropZone;
        this.filesContainer = dropZone.querySelector('.consta-dragndrop-files');
    }

    attachEvents() {
        this.dropZone.addEventListener('click', (e) => {
            if (this.options.disabled) return;
            if (e.target.closest('.consta-dragndrop-file-item')) return;
            this.originalInput.click();
        });

        this.dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (this.options.disabled) return;
            if (!this.isDragging) {
                this.isDragging = true;
                this.dropZone.classList.add('consta-dragndrop-dragover');
            }
        });

        this.dropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (!this.dropZone.contains(e.relatedTarget)) {
                this.isDragging = false;
                this.dropZone.classList.remove('consta-dragndrop-dragover');
            }
        });

        this.dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.isDragging = false;
            this.dropZone.classList.remove('consta-dragndrop-dragover');

            if (this.options.disabled) return;

            const files = Array.from(e.dataTransfer.files);
            this.handleFiles(files);
        });

        this.originalInput.addEventListener('change', (e) => {
            const files = Array.from(e.target.files);
            this.handleFiles(files);
        });
    }

    handleFiles(files) {
        if (!files || files.length === 0) return;

        if (!this.options.multiple && files.length > 1) {
            this.showError('Можно загрузить только один файл');
            return;
        }

        if (this.options.maxSize) {
            for (const file of files) {
                if (file.size > this.options.maxSize) {
                    this.showError(`Файл "${file.name}" слишком большой. Максимальный размер: ${this.formatFileSize(this.options.maxSize)}`);
                    return;
                }
            }
        }

        if (this.options.accept && this.options.accept !== '*') {
            const acceptTypes = this.options.accept.split(',').map(t => t.trim());
            for (const file of files) {
                const fileType = file.type || '';
                const fileName = file.name.toLowerCase();
                const isAccepted = acceptTypes.some(accept => {
                    if (accept.startsWith('.')) {
                        return fileName.endsWith(accept.toLowerCase());
                    }
                    if (accept.includes('/*')) {
                        const baseType = accept.split('/')[0];
                        return fileType.startsWith(baseType + '/');
                    }
                    return fileType === accept || fileName.endsWith('.' + accept.replace(/^\./, ''));
                });

                if (!isAccepted) {
                    this.showError(`Файл "${file.name}" имеет недопустимый тип. Разрешены: ${this.options.accept}`);
                    return;
                }
            }
        }

        const dataTransfer = new DataTransfer();
        files.forEach(file => dataTransfer.items.add(file));
        this.originalInput.files = dataTransfer.files;

        this.displayFiles(files);
        if (this.options.onDrop && typeof this.options.onDrop === 'function') {
            try {
                this.options.onDrop(files, this.originalInput);
            } catch (e) {
                this.showError('Ошибка при обработке файла: ' + e.message);
            }
        }
    }

    displayFiles(files) {
        this.filesContainer.innerHTML = '';
        
        files.forEach((file, index) => {
            const fileItem = document.createElement('div');
            fileItem.className = 'consta-dragndrop-file-item';
            fileItem.innerHTML = `
                <div class="consta-dragndrop-file-info">
                    <div class="consta-dragndrop-file-icon">
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M4 2H8L10 4H12C12.5523 4 13 4.44772 13 5V12C13 12.5523 12.5523 13 12 13H4C3.44772 13 3 12.5523 3 12V3C3 2.44772 3.44772 2 4 2Z" stroke="currentColor" stroke-width="1.5" fill="none"/>
                        </svg>
                    </div>
                    <div class="consta-dragndrop-file-details">
                        <span class="consta-dragndrop-file-name">${this.escapeHtml(file.name)}</span>
                        <span class="consta-dragndrop-file-size">${this.formatFileSize(file.size)}</span>
                    </div>
                </div>
                <button type="button" class="consta-dragndrop-file-remove" data-index="${index}">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M4 4L12 12M12 4L4 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                    </svg>
                </button>
            `;

            const removeBtn = fileItem.querySelector('.consta-dragndrop-file-remove');
            removeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.removeFile(index);
            });

            this.filesContainer.appendChild(fileItem);
        });
    }

    removeFile(index) {
        const files = Array.from(this.originalInput.files);
        files.splice(index, 1);
        
        const dataTransfer = new DataTransfer();
        files.forEach(file => dataTransfer.items.add(file));
        this.originalInput.files = dataTransfer.files;

        if (files.length === 0) {
            this.filesContainer.innerHTML = '';
        } else {
            this.displayFiles(files);
        }
    }

    showError(message) {
        if (this.options.onError) {
            this.options.onError(message);
        } else {
            alert(message);
        }
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    setDisabled(disabled) {
        this.options.disabled = disabled;
        if (disabled) {
            this.wrapper.classList.add('consta-dragndrop-disabled');
        } else {
            this.wrapper.classList.remove('consta-dragndrop-disabled');
        }
    }

    getFiles() {
        return Array.from(this.originalInput.files);
    }

    clear() {
        const dataTransfer = new DataTransfer();
        this.originalInput.files = dataTransfer.files;
        this.filesContainer.innerHTML = '';
    }
}

function initConstaDragNDropFields() {
    document.querySelectorAll('input[type="file"]:not(.consta-dragndrop-initialized)').forEach(input => {
        if (input.closest('.consta-dragndrop-wrapper')) {
            return;
        }

        let wrapper = input.parentElement;
        if (!wrapper || !wrapper.classList.contains('consta-dragndrop-container')) {
            wrapper = document.createElement('div');
            wrapper.className = 'consta-dragndrop-container';
            input.parentNode.insertBefore(wrapper, input);
            wrapper.appendChild(input);
        }

        const options = {
            accept: input.accept || '*',
            multiple: input.multiple || false
        };

        try {
            new ConstaDragNDropField(wrapper, options);
            input.classList.add('consta-dragndrop-initialized');
        } catch (e) {
        }
    });
}

if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(initConstaDragNDropFields, 100);
        });
    } else {
        setTimeout(initConstaDragNDropFields, 100);
    }

    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            mutation.addedNodes.forEach(function(node) {
                if (node.nodeType === 1) { // Element node
                    if (node.tagName === 'INPUT' && node.type === 'file') {
                        setTimeout(function() {
                            if (typeof initConstaDragNDropFields !== 'undefined') {
                                initConstaDragNDropFields();
                            }
                        }, 50);
                    } else if (node.querySelectorAll) {
                        const fileInputs = node.querySelectorAll('input[type="file"]:not(.consta-dragndrop-initialized)');
                        if (fileInputs.length > 0) {
                            setTimeout(function() {
                                if (typeof initConstaDragNDropFields !== 'undefined') {
                                    initConstaDragNDropFields();
                                }
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
    window.ConstaDragNDropField = ConstaDragNDropField;
    window.initConstaDragNDropFields = initConstaDragNDropFields;
}

