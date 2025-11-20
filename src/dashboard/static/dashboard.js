/**
 * Claude Memory Dashboard Client (UX-026 Phase 3)
 */

// API base URL (same origin)
const API_BASE = '';

// Global filter state
const filters = {
    search: '',
    project: '',
    category: '',
    lifecycle: '',
    dateRange: ''
};

// Store original data for client-side filtering
let originalData = {
    projects: [],
    categories: {},
    lifecycleStates: {},
    recentSearches: [],
    recentAdditions: []
};

// Load dashboard data on page load
document.addEventListener('DOMContentLoaded', () => {
    initializeTheme();
    initializeFilters();
    initializeKeyboardShortcuts();
    initializeOfflineDetection();
    loadFiltersFromURL();
    loadData();
    // Auto-refresh every 30 seconds
    setInterval(loadData, 30000);
});

/**
 * Initialize theme on page load
 */
function initializeTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);

    document.getElementById('dark-mode-toggle').addEventListener('click', toggleTheme);
}

/**
 * Toggle between light and dark themes
 */
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
}

/**
 * Set theme and persist to localStorage
 */
function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);

    // Update icon visibility
    document.querySelector('.icon-light').style.display = theme === 'dark' ? 'none' : 'inline';
    document.querySelector('.icon-dark').style.display = theme === 'dark' ? 'inline' : 'none';
}

/**
 * Initialize keyboard shortcuts
 */
function initializeKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ignore if typing in input field or textarea
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return;
        }

        switch (e.key) {
            case '/':
                e.preventDefault();
                document.getElementById('global-search').focus();
                break;
            case 'r':
                e.preventDefault();
                loadData();
                break;
            case 'd':
                e.preventDefault();
                toggleTheme();
                break;
            case 'c':
                e.preventDefault();
                clearFilters();
                break;
            case '?':
                e.preventDefault();
                showKeyboardShortcutsHelp();
                break;
        }
    });
}

/**
 * Show keyboard shortcuts help modal
 */
function showKeyboardShortcutsHelp() {
    const modal = document.getElementById('shortcuts-modal');
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    // Close on Escape key
    document.addEventListener('keydown', handleShortcutsModalEscape);
}

/**
 * Close keyboard shortcuts help modal
 */
function closeShortcutsModal() {
    const modal = document.getElementById('shortcuts-modal');
    modal.style.display = 'none';
    document.body.style.overflow = 'auto';
    document.removeEventListener('keydown', handleShortcutsModalEscape);
}

/**
 * Handle Escape key to close shortcuts modal
 */
function handleShortcutsModalEscape(e) {
    if (e.key === 'Escape') {
        closeShortcutsModal();
    }
}

/**
 * Initialize filter event listeners
 */
function initializeFilters() {
    // Search input with debouncing
    const searchInput = document.getElementById('global-search');
    let searchTimeout;
    searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            filters.search = e.target.value.toLowerCase();
            applyFilters();
        }, 300);
    });

    // Filter dropdowns
    document.getElementById('filter-project').addEventListener('change', (e) => {
        filters.project = e.target.value;
        applyFilters();
    });

    document.getElementById('filter-category').addEventListener('change', (e) => {
        filters.category = e.target.value;
        applyFilters();
    });

    document.getElementById('filter-lifecycle').addEventListener('change', (e) => {
        filters.lifecycle = e.target.value;
        applyFilters();
    });

    document.getElementById('filter-date-range').addEventListener('change', (e) => {
        filters.dateRange = e.target.value;
        applyFilters();
    });

    // Clear filters button
    document.getElementById('clear-filters').addEventListener('click', () => {
        clearFilters();
    });
}

/**
 * Apply current filters to displayed data
 */
function applyFilters() {
    // Filter projects
    const filteredProjects = originalData.projects.filter(project => {
        if (filters.project && project.project_name !== filters.project) return false;
        if (filters.search && !project.project_name.toLowerCase().includes(filters.search)) return false;
        return true;
    });

    // Filter categories
    const filteredCategories = {};
    if (filters.category) {
        if (originalData.categories[filters.category]) {
            filteredCategories[filters.category] = originalData.categories[filters.category];
        }
    } else {
        Object.assign(filteredCategories, originalData.categories);
    }

    // Filter lifecycle states
    const filteredLifecycleStates = {};
    if (filters.lifecycle) {
        if (originalData.lifecycleStates[filters.lifecycle]) {
            filteredLifecycleStates[filters.lifecycle] = originalData.lifecycleStates[filters.lifecycle];
        }
    } else {
        Object.assign(filteredLifecycleStates, originalData.lifecycleStates);
    }

    // Filter recent searches
    const filteredSearches = originalData.recentSearches.filter(search => {
        if (filters.search && !search.query.toLowerCase().includes(filters.search)) return false;
        if (filters.project && search.project_name !== filters.project) return false;
        if (filters.dateRange && !isWithinDateRange(search.timestamp, filters.dateRange)) return false;
        return true;
    });

    // Filter recent additions
    const filteredAdditions = originalData.recentAdditions.filter(addition => {
        if (filters.search && !addition.content.toLowerCase().includes(filters.search)) return false;
        if (filters.category && addition.category !== filters.category) return false;
        if (filters.dateRange && !isWithinDateRange(addition.created_at, filters.dateRange)) return false;
        return true;
    });

    // Update display with filtered data
    updateProjects(filteredProjects);
    updateCategories(filteredCategories);
    updateLifecycleStates(filteredLifecycleStates);
    updateRecentSearches(filteredSearches);
    updateRecentAdditions(filteredAdditions);

    // Update filter badge and URL
    updateFilterBadge();
    updateURLParams();
}

/**
 * Check if timestamp is within date range
 */
function isWithinDateRange(timestamp, range) {
    if (!timestamp || !range) return true;

    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;

    switch (range) {
        case '1h':
            return diffMs <= 3600000; // 1 hour
        case '24h':
            return diffMs <= 86400000; // 24 hours
        case '7d':
            return diffMs <= 604800000; // 7 days
        case '30d':
            return diffMs <= 2592000000; // 30 days
        default:
            return true;
    }
}

/**
 * Update filter badge showing active filter count
 */
function updateFilterBadge() {
    const activeFilters = [];
    if (filters.search) activeFilters.push('search');
    if (filters.project) activeFilters.push('project');
    if (filters.category) activeFilters.push('category');
    if (filters.lifecycle) activeFilters.push('lifecycle');
    if (filters.dateRange) activeFilters.push('date');

    const badge = document.getElementById('filter-badge');
    if (activeFilters.length > 0) {
        badge.textContent = `${activeFilters.length} filter${activeFilters.length > 1 ? 's' : ''} active`;
        badge.style.display = 'inline-block';
    } else {
        badge.style.display = 'none';
    }
}

/**
 * Clear all filters
 */
function clearFilters() {
    filters.search = '';
    filters.project = '';
    filters.category = '';
    filters.lifecycle = '';
    filters.dateRange = '';

    document.getElementById('global-search').value = '';
    document.getElementById('filter-project').value = '';
    document.getElementById('filter-category').value = '';
    document.getElementById('filter-lifecycle').value = '';
    document.getElementById('filter-date-range').value = '';

    applyFilters();
}

/**
 * Update URL parameters based on current filters
 */
function updateURLParams() {
    const params = new URLSearchParams();
    if (filters.search) params.set('search', filters.search);
    if (filters.project) params.set('project', filters.project);
    if (filters.category) params.set('category', filters.category);
    if (filters.lifecycle) params.set('lifecycle', filters.lifecycle);
    if (filters.dateRange) params.set('date', filters.dateRange);

    const newURL = params.toString() ? `${window.location.pathname}?${params.toString()}` : window.location.pathname;
    window.history.replaceState({}, '', newURL);
}

/**
 * Load filters from URL parameters
 */
function loadFiltersFromURL() {
    const params = new URLSearchParams(window.location.search);

    filters.search = params.get('search') || '';
    filters.project = params.get('project') || '';
    filters.category = params.get('category') || '';
    filters.lifecycle = params.get('lifecycle') || '';
    filters.dateRange = params.get('date') || '';

    document.getElementById('global-search').value = filters.search;
    document.getElementById('filter-project').value = filters.project;
    document.getElementById('filter-category').value = filters.category;
    document.getElementById('filter-lifecycle').value = filters.lifecycle;
    document.getElementById('filter-date-range').value = filters.dateRange;
}

/**
 * Show toast notification
 */
function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icons = {
        error: '❌',
        warning: '⚠️',
        success: '✅',
        info: 'ℹ️'
    };

    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || icons.info}</span>
        <span class="toast-message">${escapeHtml(message)}</span>
        <button class="toast-close" onclick="this.parentElement.remove()" aria-label="Close notification">×</button>
    `;

    toastContainer.appendChild(toast);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (toast.parentElement) {
            toast.remove();
        }
    }, 5000);
}

/**
 * Fetch with retry logic and exponential backoff
 */
async function fetchWithRetry(url, options = {}, retries = 3) {
    for (let i = 0; i < retries; i++) {
        try {
            const response = await fetch(url, options);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return await response.json();
        } catch (error) {
            if (i === retries - 1) {
                // Last retry failed
                throw error;
            }
            // Wait before retry (exponential backoff: 1s, 2s, 4s)
            const waitTime = 1000 * Math.pow(2, i);
            await new Promise(resolve => setTimeout(resolve, waitTime));

            if (i < retries - 1) {
                showToast(`Retrying... (Attempt ${i + 2}/${retries})`, 'warning');
            }
        }
    }
}

/**
 * Initialize offline detection
 */
function initializeOfflineDetection() {
    window.addEventListener('online', () => {
        showToast('Connection restored. Refreshing data...', 'success');
        loadData();
    });

    window.addEventListener('offline', () => {
        showToast('You are offline. Some features may not work.', 'warning');
    });
}

/**
 * Show skeleton loader in a container
 */
function showSkeletonLoader(containerId, type = 'card') {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (type === 'stat') {
        container.innerHTML = '<div class="skeleton skeleton-stat"></div>';
    } else if (type === 'list') {
        container.innerHTML = `
            <div class="skeleton skeleton-card"></div>
            <div class="skeleton skeleton-card"></div>
            <div class="skeleton skeleton-card"></div>
        `;
    } else {
        container.innerHTML = '<div class="skeleton skeleton-card"></div>';
    }
}

/**
 * Main function to load all dashboard data
 */
async function loadData() {
    // Show skeleton loaders
    showSkeletonLoader('projects-list', 'list');
    showSkeletonLoader('categories-chart', 'list');
    showSkeletonLoader('lifecycle-chart', 'list');
    showSkeletonLoader('recent-searches', 'list');
    showSkeletonLoader('recent-additions', 'list');

    try {
        await Promise.all([
            loadDashboardStats(),
            loadRecentActivity()
        ]);
    } catch (error) {
        console.error('Error loading dashboard data:', error);
    }
}

/**
 * Load dashboard statistics
 */
async function loadDashboardStats() {
    try {
        const data = await fetchWithRetry(`${API_BASE}/api/stats`);

        if (data.status === 'success') {
            // Store original data for filtering
            originalData.projects = data.projects || [];
            originalData.categories = data.categories || {};
            originalData.lifecycleStates = data.lifecycle_states || {};

            // Populate project dropdown
            populateProjectDropdown(originalData.projects);

            // Update display
            updateOverview(data);
            updateProjects(originalData.projects);
            updateCategories(originalData.categories);
            updateLifecycleStates(originalData.lifecycleStates);

            // Apply filters if any are active
            if (filters.search || filters.project || filters.category || filters.lifecycle || filters.dateRange) {
                applyFilters();
            }
        } else {
            showToast(`Failed to load statistics: ${data.error || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        console.error('Error loading stats:', error);
        showToast(`Failed to load statistics: ${error.message}`, 'error');
    }
}

/**
 * Load recent activity
 */
async function loadRecentActivity() {
    try {
        const data = await fetchWithRetry(`${API_BASE}/api/activity?limit=20`);

        if (data.status === 'success') {
            // Store original data for filtering
            originalData.recentSearches = data.recent_searches || [];
            originalData.recentAdditions = data.recent_additions || [];

            // Update display
            updateRecentSearches(originalData.recentSearches);
            updateRecentAdditions(originalData.recentAdditions);

            // Apply filters if any are active
            if (filters.search || filters.project || filters.category || filters.lifecycle || filters.dateRange) {
                applyFilters();
            }
        } else {
            showToast(`Failed to load activity: ${data.error || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        console.error('Error loading activity:', error);
        showToast(`Failed to load activity: ${error.message}`, 'error');
    }
}

/**
 * Populate project dropdown with available projects
 */
function populateProjectDropdown(projects) {
    const dropdown = document.getElementById('filter-project');
    // Keep the "All Projects" option
    const allOption = dropdown.querySelector('option[value=""]');

    // Clear existing options except "All Projects"
    dropdown.innerHTML = '';
    dropdown.appendChild(allOption);

    // Add project options
    projects.forEach(project => {
        const option = document.createElement('option');
        option.value = project.project_name;
        option.textContent = project.project_name;
        dropdown.appendChild(option);
    });

    // Restore selected value if filters are active
    if (filters.project) {
        dropdown.value = filters.project;
    }
}

/**
 * Update overview statistics
 */
function updateOverview(data) {
    document.getElementById('total-memories').textContent =
        formatNumber(data.total_memories || 0);
    document.getElementById('num-projects').textContent =
        formatNumber(data.num_projects || 0);
    document.getElementById('global-memories').textContent =
        formatNumber(data.global_memories || 0);
}

/**
 * Update projects list
 */
function updateProjects(projects) {
    const container = document.getElementById('projects-list');

    if (projects.length === 0) {
        const hasActiveFilters = filters.search || filters.project || filters.category || filters.lifecycle || filters.dateRange;
        if (hasActiveFilters) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">🔍</div>
                    <div class="empty-state-message">No projects match your filters</div>
                    <div class="empty-state-hint">Try adjusting your search criteria</div>
                </div>
            `;
        } else {
            container.innerHTML = '<p class="loading">No projects found</p>';
        }
        return;
    }

    container.innerHTML = projects.map(project => `
        <div class="project-item">
            <div class="project-name">${escapeHtml(project.project_name)}</div>
            <div class="project-stats">
                <span>📝 ${formatNumber(project.total_memories)} memories</span>
                <span>📁 ${formatNumber(project.num_files || 0)} files</span>
                <span>⚙️ ${formatNumber(project.num_functions || 0)} functions</span>
            </div>
        </div>
    `).join('');
}

/**
 * Update categories chart
 */
function updateCategories(categories) {
    const container = document.getElementById('categories-chart');

    const entries = Object.entries(categories).sort((a, b) => b[1] - a[1]);

    if (entries.length === 0) {
        container.innerHTML = '<p class="loading">No categories found</p>';
        return;
    }

    const maxCount = Math.max(...entries.map(e => e[1]));

    container.innerHTML = entries.map(([category, count]) => {
        const percentage = (count / maxCount) * 100;
        return `
            <div class="chart-bar">
                <div class="chart-label">${escapeHtml(category)}</div>
                <div class="chart-value">
                    <div class="chart-bar-fill" style="width: ${percentage}%"></div>
                    <span class="chart-count">${formatNumber(count)}</span>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Update lifecycle states chart
 */
function updateLifecycleStates(states) {
    const container = document.getElementById('lifecycle-chart');

    const entries = Object.entries(states).sort((a, b) => b[1] - a[1]);

    if (entries.length === 0) {
        container.innerHTML = '<p class="loading">No lifecycle data found</p>';
        return;
    }

    const maxCount = Math.max(...entries.map(e => e[1]));

    container.innerHTML = entries.map(([state, count]) => {
        const percentage = (count / maxCount) * 100;
        return `
            <div class="chart-bar">
                <div class="chart-label">${escapeHtml(state)}</div>
                <div class="chart-value">
                    <div class="chart-bar-fill" style="width: ${percentage}%"></div>
                    <span class="chart-count">${formatNumber(count)}</span>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Update recent searches
 */
function updateRecentSearches(searches) {
    const container = document.getElementById('recent-searches');

    if (searches.length === 0) {
        container.innerHTML = '<p class="loading">No recent searches</p>';
        return;
    }

    container.innerHTML = searches.map(search => {
        const rating = search.rating === 'helpful' ?
            '<span class="rating-helpful">✓ Helpful</span>' :
            '<span class="rating-not-helpful">✗ Not helpful</span>';

        return `
            <div class="activity-item">
                <div class="activity-header">
                    <span class="activity-title">${escapeHtml(search.query)}</span>
                    <span class="activity-meta">${formatTimestamp(search.timestamp)}</span>
                </div>
                <div class="activity-content">
                    ${rating} • Project: ${escapeHtml(search.project_name || 'Global')}
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Update recent additions
 */
function updateRecentAdditions(additions) {
    const container = document.getElementById('recent-additions');

    if (additions.length === 0) {
        container.innerHTML = '<p class="loading">No recent additions</p>';
        return;
    }

    container.innerHTML = additions.map((addition, index) => `
        <div class="activity-item" onclick="openMemoryModal(recentAdditionsData[${index}])" style="cursor: pointer;">
            <div class="activity-header">
                <span class="activity-title">${escapeHtml(addition.category)}</span>
                <span class="activity-meta">${formatTimestamp(addition.created_at)}</span>
            </div>
            <div class="activity-content">
                ${escapeHtml(addition.content.substring(0, 100))}${addition.content.length > 100 ? '...' : ''}
            </div>
        </div>
    `).join('');

    // Store full data globally for modal access
    window.recentAdditionsData = additions;
}

/**
 * Show error message
 */
function showError(section, message) {
    console.error(`Error in ${section}:`, message);
    // Could add visual error indicators here
}

/**
 * Format number with commas
 */
function formatNumber(num) {
    return num.toLocaleString();
}

/**
 * Format ISO timestamp to relative time
 */
function formatTimestamp(timestamp) {
    if (!timestamp) return 'Unknown';

    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString();
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = text.toString();
    return div.innerHTML;
}

/**
 * Open memory detail modal with memory data
 */
function openMemoryModal(memory) {
    // Populate metadata
    document.getElementById('modal-category').textContent = memory.category || '-';
    document.getElementById('modal-project').textContent = memory.project_name || 'Global';
    document.getElementById('modal-importance').textContent = memory.importance ?
        `${'★'.repeat(Math.round(memory.importance * 5))}${'☆'.repeat(5 - Math.round(memory.importance * 5))} (${memory.importance.toFixed(1)})` : '-';
    document.getElementById('modal-lifecycle').textContent = memory.lifecycle_state || '-';
    document.getElementById('modal-created').textContent = memory.created_at ?
        new Date(memory.created_at).toLocaleString() : '-';
    document.getElementById('modal-accessed').textContent = memory.last_accessed ?
        formatTimestamp(memory.last_accessed) : '-';

    // Populate content
    const contentElement = document.getElementById('modal-content');
    const codeElement = contentElement.querySelector('code');
    codeElement.textContent = memory.content || '';

    // Apply basic syntax highlighting if content looks like code
    if (memory.category === 'code' && memory.content) {
        highlightCode(codeElement);
    }

    // Populate tags if present
    if (memory.tags && memory.tags.length > 0) {
        const tagsSection = document.getElementById('modal-tags-section');
        const tagsContainer = document.getElementById('modal-tags');
        tagsContainer.innerHTML = memory.tags.map(tag =>
            `<span class="tag">${escapeHtml(tag)}</span>`
        ).join('');
        tagsSection.style.display = 'block';
    } else {
        document.getElementById('modal-tags-section').style.display = 'none';
    }

    // Show modal
    const modal = document.getElementById('memory-modal');
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    // Close on Escape key
    document.addEventListener('keydown', handleModalEscape);
}

/**
 * Close memory detail modal
 */
function closeMemoryModal() {
    const modal = document.getElementById('memory-modal');
    modal.style.display = 'none';
    document.body.style.overflow = 'auto';
    document.removeEventListener('keydown', handleModalEscape);
}

/**
 * Handle Escape key to close modal
 */
function handleModalEscape(e) {
    if (e.key === 'Escape') {
        closeMemoryModal();
    }
}

/**
 * Basic syntax highlighting for code
 */
function highlightCode(codeElement) {
    let code = codeElement.textContent;

    // Simple keyword highlighting (Python/JavaScript common keywords)
    const keywords = ['def', 'class', 'function', 'const', 'let', 'var', 'import', 'from', 'return',
                     'if', 'else', 'elif', 'for', 'while', 'try', 'except', 'catch', 'async', 'await'];

    keywords.forEach(keyword => {
        const regex = new RegExp(`\\b${keyword}\\b`, 'g');
        code = code.replace(regex, `<span style="color: #c678dd; font-weight: bold;">${keyword}</span>`);
    });

    // String highlighting
    code = code.replace(/(['"`])(.*?)\1/g, '<span style="color: #98c379;">$1$2$1</span>');

    // Comment highlighting
    code = code.replace(/(#.*$)/gm, '<span style="color: #5c6370; font-style: italic;">$1</span>');
    code = code.replace(/(\/\/.*$)/gm, '<span style="color: #5c6370; font-style: italic;">$1</span>');

    codeElement.innerHTML = code;
}
