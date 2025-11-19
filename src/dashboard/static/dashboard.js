/**
 * Claude Memory Dashboard Client (UX-026 Phase 3)
 */

// API base URL (same origin)
const API_BASE = '';

// Load dashboard data on page load
document.addEventListener('DOMContentLoaded', () => {
    loadData();
    // Auto-refresh every 30 seconds
    setInterval(loadData, 30000);
});

/**
 * Main function to load all dashboard data
 */
async function loadData() {
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
        const response = await fetch(`${API_BASE}/api/stats`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();

        if (data.status === 'success') {
            updateOverview(data);
            updateProjects(data.projects || []);
            updateCategories(data.categories || {});
            updateLifecycleStates(data.lifecycle_states || {});
        } else {
            showError('stats', data.error || 'Unknown error');
        }
    } catch (error) {
        console.error('Error loading stats:', error);
        showError('stats', error.message);
    }
}

/**
 * Load recent activity
 */
async function loadRecentActivity() {
    try {
        const response = await fetch(`${API_BASE}/api/activity?limit=20`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();

        if (data.status === 'success') {
            updateRecentSearches(data.recent_searches || []);
            updateRecentAdditions(data.recent_additions || []);
        } else {
            showError('activity', data.error || 'Unknown error');
        }
    } catch (error) {
        console.error('Error loading activity:', error);
        showError('activity', error.message);
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
        container.innerHTML = '<p class="loading">No projects found</p>';
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

    container.innerHTML = additions.map(addition => `
        <div class="activity-item">
            <div class="activity-header">
                <span class="activity-title">${escapeHtml(addition.category)}</span>
                <span class="activity-meta">${formatTimestamp(addition.created_at)}</span>
            </div>
            <div class="activity-content">
                ${escapeHtml(addition.content)}
            </div>
        </div>
    `).join('');
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
