(function () {
    document.addEventListener('DOMContentLoaded', () => {
        const sidebar = document.getElementById('sidebar');
        const collapseBtn = document.getElementById('sidebar-collapse-btn');
        const mainContent = document.querySelector('.main-content');

        // Initialize state from localStorage
        const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
        if (isCollapsed && sidebar) {
            sidebar.classList.add('collapsed');
        }

        if (collapseBtn && sidebar) {
            // Helper function to update the icon
            const updateIcon = (collapsedState) => {
                const icon = collapseBtn.querySelector('i');
                if (icon) {
                    if (collapsedState) {
                        icon.classList.remove('ph-caret-left');
                        icon.classList.add('ph-caret-right');
                    } else {
                        icon.classList.remove('ph-caret-right');
                        icon.classList.add('ph-caret-left');
                    }
                }
            };

            // Apply initial icon state based on localStorage
            updateIcon(isCollapsed);

            collapseBtn.addEventListener('click', () => {
                sidebar.classList.toggle('collapsed');
                const nowCollapsed = sidebar.classList.contains('collapsed');
                localStorage.setItem('sidebarCollapsed', nowCollapsed);

                // Update toggle icon
                updateIcon(nowCollapsed);
            });

            // Set initial icon
            const initialIcon = collapseBtn.querySelector('i');
            if (initialIcon) {
                initialIcon.className = isCollapsed ? 'ph ph-caret-right' : 'ph ph-caret-left';
            }
        }
    });
})();
