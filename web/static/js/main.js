/**
 * Margin Optimizer - Main JavaScript
 * Common functions and utilities
 */

// Utility Functions
const Utils = {
    /**
     * Format currency
     */
    formatCurrency(value) {
        if (value === null || value === undefined) return 'N/A';
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(value);
    },

    /**
     * Format percentage
     */
    formatPercent(value, decimals = 1) {
        if (value === null || value === undefined) return 'N/A';
        return `${value.toFixed(decimals)}%`;
    },

    /**
     * Get GM status badge class
     */
    getGMStatusClass(gm) {
        if (gm >= 50) return 'bg-success';
        if (gm >= 40) return 'bg-warning';
        return 'bg-danger';
    },

    /**
     * Get GM status text
     */
    getGMStatusText(gm) {
        if (gm >= 50) return 'Excellent';
        if (gm >= 40) return 'Acceptable';
        return 'Needs Action';
    },

    /**
     * Get GM card class
     */
    getGMCardClass(gm) {
        if (gm >= 50) return 'gm-success';
        if (gm >= 40) return 'gm-warning';
        return 'gm-danger';
    },

    /**
     * Show error message
     */
    showError(message) {
        $('#errorMessage').text(message);
        $('#errorAlert').fadeIn();
        setTimeout(() => {
            $('#errorAlert').fadeOut();
        }, 5000);
    },

    /**
     * Hide error message
     */
    hideError() {
        $('#errorAlert').fadeOut();
    },

    /**
     * Get strength badge HTML
     */
    getStrengthBadge(strength) {
        const labels = {
            'very_high': 'Very High',
            'high': 'High',
            'medium': 'Medium',
            'low': 'Low'
        };
        return `<span class="strength-badge strength-${strength}">${labels[strength] || strength}</span>`;
    },

    /**
     * Get priority icon
     */
    getPriorityIcon(priority) {
        const icons = {
            1: '<i class="fas fa-star text-warning"></i>',
            2: '<i class="fas fa-star-half-alt text-warning"></i>',
            3: '<i class="far fa-star text-warning"></i>'
        };
        return icons[priority] || '';
    },

    /**
     * Escape HTML
     */
    escapeHtml(text) {
        if (text === null || text === undefined) return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return String(text).replace(/[&<>"']/g, m => map[m]);
    }
};

// Global Error Handler
window.addEventListener('error', (event) => {
    console.error('JavaScript Error:', event.error);
});

// Initialize tooltips and popovers
document.addEventListener('DOMContentLoaded', () => {
    // Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

    // Bootstrap popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(popoverTriggerEl => new bootstrap.Popover(popoverTriggerEl));
});

// Export for use in other files
window.Utils = Utils;
