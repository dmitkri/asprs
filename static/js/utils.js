const Utils = {
    defaultAvatar: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNTAiIGhlaWdodD0iNTAiIHZpZXdCb3g9IjAgMCA1MCA1MCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48Y2lyY2xlIGN4PSIyNSIgY3k9IjI1IiByPSIyNSIgZmlsbD0iI0YzRjRGNiIvPjwvc3ZnPg==',

    calculateProfileRating(emp) {
        let score = 0;
        const maxScore = 100;
        const details = [];

        const hasPhoto = emp.photo && emp.photo.trim() !== '';
        if (hasPhoto) {
            score += 25;
            details.push({ field: 'Фото', points: 25, filled: true });
        } else {
            details.push({ field: 'Фото', points: 25, filled: false });
        }

        const hasFio = emp.fio && emp.fio.trim() !== '';
        if (hasFio) {
            score += 25;
            details.push({ field: 'ФИО', points: 25, filled: true });
        } else {
            details.push({ field: 'ФИО', points: 25, filled: false });
        }

        const hasBirthDate = emp.birth_date && emp.birth_date.trim() !== '';
        if (hasBirthDate) {
            score += 15;
            details.push({ field: 'Дата рождения', points: 15, filled: true });
        } else {
            details.push({ field: 'Дата рождения', points: 15, filled: false });
        }

        const hasPhone = emp.phone && emp.phone.trim() !== '';
        if (hasPhone) {
            score += 5;
            details.push({ field: 'Телефон', points: 5, filled: true });
        } else {
            details.push({ field: 'Телефон', points: 5, filled: false });
        }

        const hasGroup = emp.group_name && emp.group_name.trim() !== '';
        if (hasGroup) {
            score += 5;
            details.push({ field: 'Группа', points: 5, filled: true });
        } else {
            details.push({ field: 'Группа', points: 5, filled: false });
        }

        const hasResidence = emp.building && emp.building.trim() !== '' &&
            emp.entrance && emp.entrance.trim() !== '' &&
            emp.room_number && emp.room_number.trim() !== '';
        if (hasResidence) {
            score += 10;
            details.push({ field: 'Проживание', points: 10, filled: true });
        } else {
            details.push({ field: 'Проживание', points: 10, filled: false });
        }

        let hasRepresentatives = false;
        if (emp.representatives && Array.isArray(emp.representatives) && emp.representatives.length > 0) {
            const hasValidRepresentative = emp.representatives.some(rep => {
                return rep && (
                    (rep.fio && rep.fio.trim() !== '') ||
                    (rep.phone && rep.phone.trim() !== '') ||
                    (rep.relationship && rep.relationship.trim() !== '')
                );
            });
            if (hasValidRepresentative) {
                score += 15;
                hasRepresentatives = true;
            }
        }
        details.push({ field: 'Законные представители', points: 15, filled: hasRepresentatives });

        const percentage = Math.round((score / maxScore) * 100);

        return {
            score: score,
            maxScore: maxScore,
            percentage: percentage,
            details: details
        };
    },

    generateAvatarWithInitials(fio) {
        let initials = '?';
        
        if (fio && typeof fio === 'string' && fio.trim()) {
            const parts = fio.trim().split(/\s+/);
            
            if (parts.length >= 2) {
                const surname = parts[0];
                const name = parts[1];
                initials = (surname[0] || '').toUpperCase() + (name[0] || '').toUpperCase();
            } else if (parts.length === 1 && parts[0].length >= 2) {
                const word = parts[0];
                initials = (word[0] || '').toUpperCase() + (word[1] || '').toUpperCase();
            } else if (parts.length === 1 && parts[0].length === 1) {
                initials = parts[0].toUpperCase() + parts[0].toUpperCase();
            }
        }
        
        let hash = 0;
        for (let i = 0; i < initials.length; i++) {
            hash = initials.charCodeAt(i) + ((hash << 5) - hash);
        }
        const hue = Math.abs(hash % 360);
        const saturation = 15 + (Math.abs(hash) % 20); // 15-35%
        const lightness = 65 + (Math.abs(hash) % 20); // 65-85%
        const bgColor = `hsl(${hue}, ${saturation}%, ${lightness}%)`;
        
        const textColor = `hsl(${hue}, ${Math.min(saturation + 20, 60)}%, ${Math.max(lightness - 40, 20)}%)`;
        
        const svg = `
            <svg width="50" height="50" viewBox="0 0 50 50" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="25" cy="25" r="25" fill="${bgColor}"/>
                <text fill="${textColor}" text-anchor="middle" dy=".35em" font-family="Montserrat, sans-serif" font-size="18" font-weight="600" x="25" y="25">${this.escapeHtml(initials)}</text>
            </svg>
        `.trim();
        
        const encoded = btoa(unescape(encodeURIComponent(svg)));
        return `data:image/svg+xml;base64,${encoded}`;
    },

    getAge(dateStr) {
        if (!dateStr || !/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) return '—';
        const [y, m, d] = dateStr.split('-').map(Number);
        const birthDate = new Date(y, m - 1, d);
        const today = new Date();
        let age = today.getFullYear() - birthDate.getFullYear();
        const monthDiff = today.getMonth() - birthDate.getMonth();
        const dayDiff = today.getDate() - birthDate.getDate();
        if (monthDiff < 0 || (monthDiff === 0 && dayDiff < 0)) age--;
        return `${age} лет`;
    },

    formatDateAndAge(dateStr) {
        if (!dateStr || !/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) return { formatted: '—', age: '' };
        const [y, m, d] = dateStr.split('-').map(Number);
        const formatted = `${d.toString().padStart(2, '0')}.${m.toString().padStart(2, '0')}.${y}`;
        const birthDate = new Date(y, m - 1, d);
        const today = new Date();
        let age = today.getFullYear() - birthDate.getFullYear();
        const monthDiff = today.getMonth() - birthDate.getMonth();
        const dayDiff = today.getDate() - birthDate.getDate();
        if (monthDiff < 0 || (monthDiff === 0 && dayDiff < 0)) age--;
        return { formatted, age: `${age} лет` };
    },

    resizeImage(file, maxSize = 120, quality = 0.85) {
        return new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = e => {
                const img = new Image();
                img.onload = () => {
                    const canvas = document.createElement('canvas');
                    const ctx = canvas.getContext('2d');
                    let w = img.width, h = img.height;
                    if (w > h) { if (w > maxSize) { h *= maxSize / w; w = maxSize; } }
                    else { if (h > maxSize) { w *= maxSize / h; h = maxSize; } }
                    canvas.width = w; canvas.height = h;
                    ctx.drawImage(img, 0, 0, w, h);
                    canvas.toBlob(blob => resolve(new File([blob], file.name, { type: 'image/jpeg' })), 'image/jpeg', quality);
                };
                img.src = e.target.result;
            };
            reader.readAsDataURL(file);
        });
    },

    debounce(func, wait) {
        let timeout;
        return (...args) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => func(...args), wait);
        };
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    createFileList(file) {
        const dt = new DataTransfer();
        dt.items.add(file);
        return dt.files;
    },

    copyToClipboard(text, event) {
        if (event) event.preventDefault();
        navigator.clipboard.writeText(text).then(() => {
            if (event) {
                const btn = event.target;
                const original = btn.textContent;
                btn.textContent = 'Скопировано!';
                setTimeout(() => btn.textContent = original, 2000);
            }
        });
    },

    getFileCategory(fileName) {
        if (!fileName) return { category: 'Другое', color: '#6c757d' };
        
        const ext = fileName.split('.').pop().toLowerCase();
        const categories = {
            'pdf': { category: 'PDF', color: '#dc3545' },
            'doc': { category: 'Word', color: '#0d6efd' },
            'docx': { category: 'Word', color: '#0d6efd' },
            'xls': { category: 'Excel', color: '#198754' },
            'xlsx': { category: 'Excel', color: '#198754' },
            'ppt': { category: 'PowerPoint', color: '#fd7e14' },
            'pptx': { category: 'PowerPoint', color: '#fd7e14' },
            'jpg': { category: 'Изображение', color: '#6f42c1' },
            'jpeg': { category: 'Изображение', color: '#6f42c1' },
            'png': { category: 'Изображение', color: '#6f42c1' },
            'gif': { category: 'Изображение', color: '#6f42c1' },
            'zip': { category: 'Архив', color: '#ffc107' },
            'rar': { category: 'Архив', color: '#ffc107' },
            '7z': { category: 'Архив', color: '#ffc107' },
            'txt': { category: 'Текст', color: '#20c997' },
            'csv': { category: 'CSV', color: '#198754' }
        };
        
        return categories[ext] || { category: 'Другое', color: '#6c757d' };
    },

    getFileIcon(category) {
        const icons = {
            'PDF': '<i class="bi bi-file-pdf"></i>',
            'Word': '<i class="bi bi-file-word"></i>',
            'Excel': '<i class="bi bi-file-excel"></i>',
            'PowerPoint': '<i class="bi bi-file-ppt"></i>',
            'Изображение': '<i class="bi bi-file-image"></i>',
            'Архив': '<i class="bi bi-file-zip"></i>',
            'Текст': '<i class="bi bi-file-text"></i>',
            'CSV': '<i class="bi bi-file-csv"></i>',
            'Другое': '<i class="bi bi-file"></i>'
        };
        
        return icons[category] || icons['Другое'];
    }
};


