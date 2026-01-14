/**
 * Shared Dynamic Dropdown Logic
 */

function initCustomDropdown(input, itemsOrFn, wrapperClass) {
    const wrapper = input.closest('.select-wrapper');
    if (input.dataset.dropdownInit) return;
    input.dataset.dropdownInit = 'true';

    let dropdown = wrapper.querySelector('.dropdown-menu');
    if (!dropdown) {
        dropdown = document.createElement('div');
        dropdown.className = 'dropdown-menu';
        dropdown.associatedInput = input;
        document.body.appendChild(dropdown);
    }

    let currentIndex = -1;

    const getItems = () => {
        if (typeof itemsOrFn === 'function') return itemsOrFn();
        return itemsOrFn;
    };

    const updatePosition = () => {
        if (!dropdown.classList.contains('active')) return;
        const rect = input.getBoundingClientRect();
        dropdown.style.minWidth = `${rect.width}px`;
        dropdown.style.width = 'auto';

        let left = rect.left;
        if (left + dropdown.offsetWidth > window.innerWidth) {
            left = window.innerWidth - dropdown.offsetWidth - 10;
        }

        dropdown.style.left = `${Math.max(10, left)}px`;
        dropdown.style.top = `${rect.bottom + 4}px`;
    };

    const renderItems = (filter = '') => {
        const items = getItems();
        if (!items || items.length === 0) {
            dropdown.classList.remove('active');
            return;
        }

        const searchWords = String(filter).toLowerCase().trim().split(/\s+/).filter(word => word.length > 0);

        const filtered = items.filter(item => {
            const itemStr = String(item).toLowerCase();
            return searchWords.every(word => itemStr.includes(word));
        }).slice(0, 50);

        if (filtered.length === 0) {
            dropdown.classList.remove('active');
            return;
        }

        dropdown.innerHTML = filtered.map((item, index) => {
            if (searchWords.length === 0) return `<div class="dropdown-item" data-value="${item}">${item}</div>`;

            // Highlight each word individually
            const escapedWords = searchWords.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
            const regex = new RegExp(`(${escapedWords.join('|')})`, 'gi');
            const highlighted = String(item).replace(regex, '<mark>$1</mark>');

            return `<div class="dropdown-item" data-value="${item}">${highlighted}</div>`;
        }).join('');

        dropdown.classList.add('active');
        updatePosition();
        currentIndex = -1;
    };

    input.addEventListener('input', (e) => renderItems(e.target.value));

    const handleFocusClick = (e) => {
        const val = input.readOnly ? '' : input.value;
        if (!dropdown.classList.contains('active')) renderItems(val);
    };

    input.addEventListener('focus', handleFocusClick);
    input.addEventListener('click', handleFocusClick);

    window.addEventListener('scroll', updatePosition, true);
    window.addEventListener('resize', updatePosition);

    input.addEventListener('keydown', (e) => {
        const results = dropdown.querySelectorAll('.dropdown-item');
        if (!dropdown.classList.contains('active')) {
            if (e.key === 'ArrowDown') renderItems(input.value);
            return;
        }

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            currentIndex = Math.min(currentIndex + 1, results.length - 1);
            updateSelection(results);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            currentIndex = Math.max(currentIndex - 1, -1);
            updateSelection(results);
        } else if (e.key === 'Enter') {
            if (currentIndex >= 0) {
                e.preventDefault();
                selectItem(results[currentIndex]);
            }
        } else if (e.key === 'Escape') {
            dropdown.classList.remove('active');
        }
    });

    const updateSelection = (items) => {
        items.forEach((item, index) => {
            if (index === currentIndex) {
                item.classList.add('selected');
                item.scrollIntoView({ block: 'nearest' });
            } else {
                item.classList.remove('selected');
            }
        });
    };

    const selectItem = (item) => {
        const val = item.dataset.value;
        input.value = val;
        dropdown.classList.remove('active');
        input.dispatchEvent(new Event('change'));
        input.blur();
    };

    dropdown.addEventListener('click', (e) => {
        const item = e.target.closest('.dropdown-item');
        if (item) selectItem(item);
    });
}

// Global click listener to close dropdowns
document.addEventListener('mousedown', (e) => {
    const activeMenus = document.querySelectorAll('.dropdown-menu.active');
    activeMenus.forEach(menu => {
        if (!menu.contains(e.target) && e.target !== menu.associatedInput) {
            menu.classList.remove('active');
        }
    });
});
