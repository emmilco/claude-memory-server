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
    initializeTimeRange();
    initializeKeyboardShortcuts();
    initializeOfflineDetection();
    initializeTooltips();
    initializeComparison();
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
 * Initialize time range buttons
 */
function initializeTimeRange() {
    // Load saved time range from localStorage
    const savedRange = localStorage.getItem('dashboard-time-range') || '';

    // Set active button
    document.querySelectorAll('.time-btn').forEach(btn => {
        const range = btn.getAttribute('data-range');
        if (range === savedRange) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    // Sync with dropdown
    const dropdown = document.getElementById('filter-date-range');
    if (dropdown) {
        dropdown.value = savedRange;
    }

    // Add click handlers to time range buttons
    document.querySelectorAll('.time-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const range = btn.getAttribute('data-range');

            // Update button states
            document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Update dropdown
            const dropdown = document.getElementById('filter-date-range');
            if (dropdown) {
                dropdown.value = range;
            }

            // Update filter and save to localStorage
            filters.dateRange = range;
            localStorage.setItem('dashboard-time-range', range);

            // Apply filters
            applyFilters();
        });
    });
}

/**
 * Initialize tooltips with Tippy.js
 */
function initializeTooltips() {
    // Check if Tippy.js is loaded
    if (typeof tippy === 'undefined') {
        console.warn('Tippy.js not loaded, tooltips will not be available');
        return;
    }

    // Initialize tooltips for all elements with data-tippy-content
    tippy('[data-tippy-content]', {
        placement: 'top',
        animation: 'fade',
        theme: 'translucent',
        delay: [300, 0], // Show after 300ms, hide immediately
        arrow: true
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
 * Load health data and update health widget (UX-036)
 */
async function loadHealthData() {
    try {
        const data = await fetchWithRetry(`${API_BASE}/api/health`);

        // Update health score gauge
        const healthScore = data.health_score || 0;
        updateHealthGauge(healthScore);

        // Update performance metrics
        document.getElementById('metric-latency').textContent =
            `${(data.performance_metrics?.search_latency_p95 || 0).toFixed(2)}ms`;
        document.getElementById('metric-cache').textContent =
            `${((data.performance_metrics?.cache_hit_rate || 0) * 100).toFixed(1)}%`;

        // Update alerts
        updateHealthAlerts(data.alerts || []);

    } catch (error) {
        console.error('Error loading health data:', error);
        showToast(`Failed to load health data: ${error.message}`, 'error');

        // Show error state
        document.getElementById('health-score-value').textContent = '--';
        document.getElementById('metric-latency').textContent = '--';
        document.getElementById('metric-cache').textContent = '--';
        document.getElementById('health-alerts').innerHTML =
            '<p class="loading" style="color: var(--warning-color);">Failed to load health data</p>';
    }
}

/**
 * Update health gauge visualization
 */
function updateHealthGauge(score) {
    const gaugeValue = document.getElementById('health-score-value');
    const gaugeFill = document.getElementById('gauge-fill');

    gaugeValue.textContent = Math.round(score);

    // Calculate arc length (semicircle, ~251 units total)
    const arcLength = 251.2;
    const fillLength = (score / 100) * arcLength;

    // Set stroke-dasharray to show the fill
    gaugeFill.style.strokeDasharray = `${fillLength} ${arcLength}`;

    // Set color based on health score
    let color;
    if (score >= 90) {
        color = 'var(--success-color)';
    } else if (score >= 70) {
        color = 'var(--warning-color)';
    } else {
        color = '#f44336';
    }
    gaugeFill.style.stroke = color;
    gaugeValue.style.color = color;
}

/**
 * Update health alerts display
 */
function updateHealthAlerts(alerts) {
    const container = document.getElementById('health-alerts');

    if (!alerts || alerts.length === 0) {
        container.innerHTML = '<p class="no-alerts">✅ No active alerts - system healthy</p>';
        return;
    }

    // Sort alerts by severity
    const severityOrder = { CRITICAL: 0, WARNING: 1, INFO: 2 };
    alerts.sort((a, b) => {
        const severityA = severityOrder[a.severity] ?? 999;
        const severityB = severityOrder[b.severity] ?? 999;
        return severityA - severityB;
    });

    const alertsHTML = alerts.map(alert => {
        const severityClass = alert.severity.toLowerCase();
        const icon = {
            CRITICAL: '🔴',
            WARNING: '⚠️',
            INFO: 'ℹ️'
        }[alert.severity] || 'ℹ️';

        return `
            <div class="alert-item ${severityClass}">
                <span class="alert-icon">${icon}</span>
                <div class="alert-message">${escapeHtml(alert.message)}</div>
            </div>
        `;
    }).join('');

    container.innerHTML = alertsHTML;
}

/**
 * Load insights and recommendations (UX-041)
 */
async function loadInsights() {
    try {
        const data = await fetchWithRetry(`${API_BASE}/api/insights`);
        updateInsights(data.insights || []);
    } catch (error) {
        console.error('Error loading insights:', error);
        showToast(`Failed to load insights: ${error.message}`, 'error');

        // Show error state
        document.getElementById('insights-list').innerHTML =
            '<p class="loading" style="color: var(--warning-color);">Failed to load insights</p>';
    }
}

/**
 * Update insights display
 */
function updateInsights(insights) {
    const container = document.getElementById('insights-list');

    if (!insights || insights.length === 0) {
        container.innerHTML = '<p class="no-insights">✨ No insights available - system running smoothly</p>';
        return;
    }

    const insightsHTML = insights.map(insight => {
        const severityClass = insight.severity.toLowerCase();
        const icon = {
            CRITICAL: '🔴',
            WARNING: '⚠️',
            INFO: '💡'
        }[insight.severity] || '💡';

        const actionHTML = insight.action
            ? `<div class="insight-action">${escapeHtml(insight.action)}</div>`
            : '';

        return `
            <div class="insight-item ${severityClass}">
                <span class="insight-icon">${icon}</span>
                <div class="insight-content">
                    <div style="display: flex; gap: 10px; align-items: center; margin-bottom: 8px;">
                        <div class="insight-title">${escapeHtml(insight.title)}</div>
                        <span class="insight-badge ${insight.type}">${insight.type}</span>
                    </div>
                    <div class="insight-message">${escapeHtml(insight.message)}</div>
                    ${actionHTML}
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = insightsHTML;
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
            loadRecentActivity(),
            loadHealthData(),
            loadInsights(),
            loadTrends()
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

            // Populate comparison selector (UX-040)
            populateComparisonSelector(originalData.projects);

            // Populate action project selectors (UX-042/UX-043)
            populateActionProjectSelectors();

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

/**
 * Initialize project comparison (UX-040)
 */
function initializeComparison() {
    const comparisonSelect = document.getElementById('comparison-projects');
    const compareBtn = document.getElementById('compare-btn');
    const clearBtn = document.getElementById('clear-comparison-btn');

    // Enable/disable compare button based on selection
    comparisonSelect.addEventListener('change', () => {
        const selected = Array.from(comparisonSelect.selectedOptions);
        compareBtn.disabled = selected.length < 2 || selected.length > 4;
    });

    // Handle compare button click
    compareBtn.addEventListener('click', () => {
        const selectedProjects = Array.from(comparisonSelect.selectedOptions).map(opt => opt.value);
        if (selectedProjects.length >= 2 && selectedProjects.length <= 4) {
            renderComparison(selectedProjects);
        }
    });

    // Handle clear button click
    clearBtn.addEventListener('click', () => {
        comparisonSelect.selectedIndex = -1;
        document.getElementById('comparison-results').style.display = 'none';
        document.getElementById('comparison-empty').style.display = 'block';
        clearBtn.style.display = 'none';
        compareBtn.disabled = true;
    });
}

/**
 * Populate comparison project selector
 */
function populateComparisonSelector(projects) {
    const select = document.getElementById('comparison-projects');
    select.innerHTML = '';

    if (!projects || projects.length === 0) {
        select.innerHTML = '<option value="">No projects available</option>';
        return;
    }

    projects.forEach(project => {
        const option = document.createElement('option');
        option.value = project.name;
        option.textContent = `${project.name} (${project.num_memories} memories)`;
        select.appendChild(option);
    });
}

/**
 * Render project comparison table
 */
function renderComparison(projectNames) {
    // Get full project data
    const projects = originalData.projects.filter(p => projectNames.includes(p.name));

    if (projects.length < 2) {
        showToast('Please select at least 2 projects to compare', 'warning');
        return;
    }

    // Define metrics to compare
    const metrics = [
        { key: 'num_memories', label: 'Total Memories', format: (v) => v.toLocaleString(), highlight: 'max' },
        { key: 'num_files', label: 'Files Indexed', format: (v) => v.toLocaleString(), highlight: 'max' },
        { key: 'num_functions', label: 'Functions', format: (v) => v.toLocaleString(), highlight: 'max' },
        { key: 'num_classes', label: 'Classes', format: (v) => v.toLocaleString(), highlight: 'max' },
        { key: 'index_time', label: 'Index Time', format: (v) => `${v.toFixed(2)}s`, highlight: 'min' },
        { key: 'last_indexed', label: 'Last Indexed', format: (v) => new Date(v).toLocaleDateString(), highlight: 'none' }
    ];

    // Build table header
    const thead = document.getElementById('comparison-thead');
    thead.innerHTML = `
        <tr>
            <th>Metric</th>
            ${projects.map(p => `<th>${escapeHtml(p.name)}</th>`).join('')}
        </tr>
    `;

    // Build table body
    const tbody = document.getElementById('comparison-tbody');
    tbody.innerHTML = metrics.map(metric => {
        const values = projects.map(p => p[metric.key] || 0);

        // Determine which value(s) should be highlighted
        let highlightValue = null;
        if (metric.highlight === 'max') {
            highlightValue = Math.max(...values);
        } else if (metric.highlight === 'min') {
            highlightValue = Math.min(...values);
        }

        const cells = projects.map((p, i) => {
            const value = values[i];
            const formatted = metric.format(value);
            const isHighlight = highlightValue !== null && value === highlightValue;
            return `<td class="${isHighlight ? 'highlight' : ''}">${formatted}</td>`;
        }).join('');

        return `
            <tr>
                <td class="metric-label">${metric.label}</td>
                ${cells}
            </tr>
        `;
    }).join('');

    // Show results, hide empty state
    document.getElementById('comparison-results').style.display = 'block';
    document.getElementById('comparison-empty').style.display = 'none';
    document.getElementById('clear-comparison-btn').style.display = 'inline-block';
}

/**
 * Quick Actions Functions (UX-042 / UX-043)
 */

// Populate project dropdowns for create memory and export
function populateActionProjectSelectors() {
    const memoryProjectSelect = document.getElementById('memory-project');
    const exportProjectSelect = document.getElementById('export-project');

    if (memoryProjectSelect && originalData.projects) {
        memoryProjectSelect.innerHTML = '<option value="">Global Memory</option>';
        originalData.projects.forEach(project => {
            const option = document.createElement('option');
            option.value = project.name;
            option.textContent = project.name;
            memoryProjectSelect.appendChild(option);
        });
    }

    if (exportProjectSelect && originalData.projects) {
        exportProjectSelect.innerHTML = '<option value="">All Projects</option>';
        originalData.projects.forEach(project => {
            const option = document.createElement('option');
            option.value = project.name;
            option.textContent = project.name;
            exportProjectSelect.appendChild(option);
        });
    }
}

// Show create memory modal
function showCreateMemoryForm() {
    document.getElementById('create-memory-modal').style.display = 'flex';
    document.getElementById('memory-content').focus();
}

function closeCreateMemoryModal() {
    document.getElementById('create-memory-modal').style.display = 'none';
    document.getElementById('create-memory-form').reset();
}

// Handle create memory form submission
async function handleCreateMemory(event) {
    event.preventDefault();

    const content = document.getElementById('memory-content').value;
    const category = document.getElementById('memory-category').value;
    const projectName = document.getElementById('memory-project').value || null;
    const importance = parseInt(document.getElementById('memory-importance').value);

    try {
        const response = await fetch(`${API_BASE}/api/memories`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                content,
                category,
                project_name: projectName,
                importance
            })
        });

        const result = await response.json();

        if (response.ok) {
            showToast('Memory created successfully!', 'success');
            closeCreateMemoryModal();
            // Reload data to show new memory
            loadData();
        } else {
            showToast(`Failed to create memory: ${result.error || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        showToast(`Error creating memory: ${error.message}`, 'error');
    }
}

// Show index project modal
function showIndexProjectForm() {
    document.getElementById('index-project-modal').style.display = 'flex';
    document.getElementById('project-directory').focus();
}

function closeIndexProjectModal() {
    document.getElementById('index-project-modal').style.display = 'none';
    document.getElementById('index-project-form').reset();
}

// Handle index project form submission
async function handleIndexProject(event) {
    event.preventDefault();

    const directoryPath = document.getElementById('project-directory').value;
    const projectName = document.getElementById('project-name').value;

    try {
        showToast('Starting indexing... This may take a while', 'info');

        const response = await fetch(`${API_BASE}/api/index`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                directory_path: directoryPath,
                project_name: projectName
            })
        });

        const result = await response.json();

        if (response.ok) {
            showToast(`Indexing completed! ${result.stats?.num_functions || 0} functions indexed`, 'success');
            closeIndexProjectModal();
            // Reload data to show new project
            loadData();
        } else {
            showToast(`Indexing failed: ${result.error || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        showToast(`Error indexing project: ${error.message}`, 'error');
    }
}

// Show export modal
function showExportForm() {
    document.getElementById('export-modal').style.display = 'flex';
}

function closeExportModal() {
    document.getElementById('export-modal').style.display = 'none';
    document.getElementById('export-form').reset();
}

// Handle export form submission
async function handleExport(event) {
    event.preventDefault();

    const format = document.getElementById('export-format').value;
    const projectName = document.getElementById('export-project').value || null;

    try {
        showToast('Generating export...', 'info');

        const response = await fetch(`${API_BASE}/api/export`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                format,
                project_name: projectName
            })
        });

        if (response.ok) {
            // Download the file
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `memories_export.${format}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            showToast('Export downloaded successfully!', 'success');
            closeExportModal();
        } else {
            const result = await response.json();
            showToast(`Export failed: ${result.error || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        showToast(`Error exporting data: ${error.message}`, 'error');
    }
}

// Run health check
async function runHealthCheck() {
    try {
        showToast('Running health check...', 'info');
        await loadHealthData();
        showToast('Health check complete! Check the Health widget above', 'success');
    } catch (error) {
        showToast(`Health check failed: ${error.message}`, 'error');
    }
}

/**
 * Trend Charts Functions (UX-038)
 */

// Global chart instances
let memoryTrendChart = null;
let searchTrendChart = null;
let latencyTrendChart = null;

// Load trend data and render charts
async function loadTrends() {
    try {
        const period = document.getElementById('trend-period').value;
        const data = await fetchWithRetry(`${API_BASE}/api/trends?period=${period}`);

        renderTrendCharts(data);
    } catch (error) {
        console.error('Error loading trends:', error);
        showToast(`Failed to load trends: ${error.message}`, 'error');
    }
}

// Render all trend charts with enhanced interactivity (UX-038)
function renderTrendCharts(data) {
    const { dates, metrics } = data;

    // Destroy existing charts
    if (memoryTrendChart) memoryTrendChart.destroy();
    if (searchTrendChart) searchTrendChart.destroy();
    if (latencyTrendChart) latencyTrendChart.destroy();

    // Get current theme for chart colors
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.05)';
    const textColor = isDark ? '#e0e0e0' : '#333333';

    // Enhanced Chart.js config with better interactivity
    const commonOptions = {
        responsive: true,
        maintainAspectRatio: true,
        interaction: {
            mode: 'index',
            intersect: false
        },
        plugins: {
            legend: {
                display: true,
                position: 'top',
                labels: {
                    color: textColor,
                    padding: 15,
                    font: {
                        size: 12,
                        weight: '500'
                    }
                }
            },
            tooltip: {
                enabled: true,
                backgroundColor: isDark ? 'rgba(45, 45, 45, 0.95)' : 'rgba(255, 255, 255, 0.95)',
                titleColor: textColor,
                bodyColor: textColor,
                borderColor: isDark ? '#404040' : '#e0e0e0',
                borderWidth: 1,
                padding: 12,
                displayColors: true,
                callbacks: {
                    title: function(context) {
                        return context[0].label || '';
                    }
                }
            },
            zoom: {
                pan: {
                    enabled: true,
                    mode: 'x'
                },
                zoom: {
                    wheel: {
                        enabled: true
                    },
                    pinch: {
                        enabled: true
                    },
                    mode: 'x'
                }
            }
        },
        scales: {
            x: {
                grid: {
                    color: gridColor,
                    drawBorder: false
                },
                ticks: {
                    color: textColor,
                    maxRotation: 45,
                    minRotation: 0
                }
            },
            y: {
                beginAtZero: true,
                grid: {
                    color: gridColor,
                    drawBorder: false
                },
                ticks: {
                    color: textColor
                }
            }
        }
    };

    // Memory Growth Chart with enhanced visuals
    const memoryCtx = document.getElementById('memory-trend-chart').getContext('2d');
    memoryTrendChart = new Chart(memoryCtx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [{
                label: 'Total Memories',
                data: metrics.memory_count,
                borderColor: '#2196F3',
                backgroundColor: 'rgba(33, 150, 243, 0.15)',
                tension: 0.4,
                fill: true,
                borderWidth: 3,
                pointRadius: 4,
                pointHoverRadius: 6,
                pointBackgroundColor: '#2196F3',
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointHoverBackgroundColor: '#1976D2',
                pointHoverBorderColor: '#fff',
                pointHoverBorderWidth: 3
            }]
        },
        options: {
            ...commonOptions,
            plugins: {
                ...commonOptions.plugins,
                tooltip: {
                    ...commonOptions.plugins.tooltip,
                    callbacks: {
                        label: function(context) {
                            return `Memories: ${formatNumber(context.parsed.y)}`;
                        }
                    }
                }
            }
        }
    });

    // Search Activity Chart with gradient bars
    const searchCtx = document.getElementById('search-trend-chart').getContext('2d');
    const searchGradient = searchCtx.createLinearGradient(0, 0, 0, 400);
    searchGradient.addColorStop(0, 'rgba(76, 175, 80, 0.8)');
    searchGradient.addColorStop(1, 'rgba(76, 175, 80, 0.3)');

    searchTrendChart = new Chart(searchCtx, {
        type: 'bar',
        data: {
            labels: dates,
            datasets: [{
                label: 'Searches per Day',
                data: metrics.search_volume,
                backgroundColor: searchGradient,
                borderColor: '#4CAF50',
                borderWidth: 1,
                borderRadius: 4,
                hoverBackgroundColor: '#66BB6A',
                hoverBorderColor: '#388E3C',
                hoverBorderWidth: 2
            }]
        },
        options: {
            ...commonOptions,
            plugins: {
                ...commonOptions.plugins,
                tooltip: {
                    ...commonOptions.plugins.tooltip,
                    callbacks: {
                        label: function(context) {
                            return `Searches: ${formatNumber(context.parsed.y)}`;
                        }
                    }
                }
            }
        }
    });

    // Performance (Latency) Chart with area fill
    const latencyCtx = document.getElementById('latency-trend-chart').getContext('2d');
    latencyTrendChart = new Chart(latencyCtx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [{
                label: 'Avg Latency (ms)',
                data: metrics.avg_latency,
                borderColor: '#FF9800',
                backgroundColor: 'rgba(255, 152, 0, 0.15)',
                tension: 0.4,
                fill: true,
                borderWidth: 3,
                pointRadius: 4,
                pointHoverRadius: 6,
                pointBackgroundColor: '#FF9800',
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointHoverBackgroundColor: '#F57C00',
                pointHoverBorderColor: '#fff',
                pointHoverBorderWidth: 3
            }]
        },
        options: {
            ...commonOptions,
            scales: {
                ...commonOptions.scales,
                y: {
                    ...commonOptions.scales.y,
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Milliseconds',
                        color: textColor,
                        font: {
                            size: 12,
                            weight: '600'
                        }
                    }
                }
            },
            plugins: {
                ...commonOptions.plugins,
                tooltip: {
                    ...commonOptions.plugins.tooltip,
                    callbacks: {
                        label: function(context) {
                            return `Latency: ${context.parsed.y.toFixed(2)}ms`;
                        },
                        afterLabel: function(context) {
                            const value = context.parsed.y;
                            if (value < 10) return '✓ Excellent';
                            if (value < 20) return '✓ Good';
                            if (value < 50) return '⚠ Fair';
                            return '⚠ Needs optimization';
                        }
                    }
                }
            }
        }
    });
}

