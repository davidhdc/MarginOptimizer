/**
 * Vendor Analysis Tab JavaScript
 * Handles vendor search with autocomplete and displays historical data
 */

// Autocomplete functionality
let autocompleteTimeout = null;

document.addEventListener('DOMContentLoaded', function() {
    const vendorInput = document.getElementById('vendorName');
    const autocompleteDiv = document.getElementById('vendorAutocomplete');
    const vendorForm = document.getElementById('analyzeVendorForm');

    if (!vendorInput || !autocompleteDiv || !vendorForm) {
        console.error('Vendor tab elements not found');
        return;
    }

    // Autocomplete on input
    vendorInput.addEventListener('input', function() {
        const searchTerm = this.value.trim();

        // Clear previous timeout
        if (autocompleteTimeout) {
            clearTimeout(autocompleteTimeout);
        }

        if (searchTerm.length < 2) {
            autocompleteDiv.style.display = 'none';
            return;
        }

        // Debounce - wait 300ms after user stops typing
        autocompleteTimeout = setTimeout(() => {
            fetchVendorSuggestions(searchTerm);
        }, 300);
    });

    // Hide autocomplete when clicking outside
    document.addEventListener('click', function(e) {
        if (e.target !== vendorInput && !autocompleteDiv.contains(e.target)) {
            autocompleteDiv.style.display = 'none';
        }
    });

    // Form submit
    vendorForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const vendorName = vendorInput.value.trim();
        if (vendorName) {
            autocompleteDiv.style.display = 'none';
            analyzeVendor(vendorName);
        }
    });
});

/**
 * Fetch vendor name suggestions from API
 */
function fetchVendorSuggestions(searchTerm) {
    const autocompleteDiv = document.getElementById('vendorAutocomplete');

    fetch(`/api/vendor-autocomplete?q=${encodeURIComponent(searchTerm)}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error('Autocomplete error:', data.error);
                return;
            }

            const vendors = data.vendors || [];

            if (vendors.length === 0) {
                autocompleteDiv.innerHTML = '<div class="list-group-item text-muted">No vendors found</div>';
                autocompleteDiv.style.display = 'block';
                return;
            }

            // Build autocomplete list
            let html = '';
            vendors.forEach(vendor => {
                html += `<a href="#" class="list-group-item list-group-item-action vendor-suggestion" data-vendor="${vendor}">${vendor}</a>`;
            });

            autocompleteDiv.innerHTML = html;
            autocompleteDiv.style.display = 'block';

            // Add click handlers to suggestions
            document.querySelectorAll('.vendor-suggestion').forEach(item => {
                item.addEventListener('click', function(e) {
                    e.preventDefault();
                    const vendorName = this.getAttribute('data-vendor');
                    document.getElementById('vendorName').value = vendorName;
                    autocompleteDiv.style.display = 'none';
                    analyzeVendor(vendorName);
                });
            });
        })
        .catch(error => {
            console.error('Error fetching vendor suggestions:', error);
        });
}

/**
 * Analyze vendor and display historical data
 */
function analyzeVendor(vendorName) {
    // Show loading
    document.getElementById('vendorLoadingSpinner').style.display = 'block';
    document.getElementById('vendorErrorAlert').style.display = 'none';
    document.getElementById('vendorWelcomeMessage').style.display = 'none';
    document.getElementById('vendorResults').style.display = 'none';

    fetch('/api/analyze-vendor', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ vendor_name: vendorName })
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById('vendorLoadingSpinner').style.display = 'none';

        if (data.error) {
            showVendorError(data.error);
            return;
        }

        displayVendorResults(data);
    })
    .catch(error => {
        document.getElementById('vendorLoadingSpinner').style.display = 'none';
        showVendorError('Failed to analyze vendor: ' + error.message);
    });
}

/**
 * Show error message
 */
function showVendorError(message) {
    document.getElementById('vendorErrorMessage').textContent = message;
    document.getElementById('vendorErrorAlert').style.display = 'block';
}

/**
 * Display vendor analysis results
 */
function displayVendorResults(data) {
    const summary = data.summary || {};
    const renewalHistory = data.renewal_history || [];
    const newContractHistory = data.new_contract_history || [];

    // Update quick summary
    document.getElementById('statRenewals').textContent = summary.total_renewals || 0;
    document.getElementById('statNewContracts').textContent = summary.total_new_contracts || 0;
    document.getElementById('statAvgDiscount').textContent = (summary.avg_discount || 0).toFixed(1) + '%';

    // Update header
    document.getElementById('vendorDisplayName').textContent = data.vendor_name;
    document.getElementById('totalRenewals').textContent = summary.total_renewals || 0;
    document.getElementById('totalNewContracts').textContent = summary.total_new_contracts || 0;
    document.getElementById('avgDiscountRate').textContent = (summary.avg_discount || 0).toFixed(1) + '%';
    document.getElementById('successRate').textContent = (summary.success_rate || 0).toFixed(1) + '%';

    // Display renewal history
    displayRenewalHistory(renewalHistory);

    // Display new contract history
    displayNewContractHistory(newContractHistory);

    // Show results
    document.getElementById('vendorQuickSummary').style.display = 'block';
    document.getElementById('vendorResults').style.display = 'block';
}

/**
 * Display renewal history table
 */
function displayRenewalHistory(renewals) {
    const container = document.getElementById('renewalHistoryContainer');
    document.getElementById('renewalHistoryCount').textContent = renewals.length;

    if (renewals.length === 0) {
        container.innerHTML = '<div class="alert alert-info">No renewal history found for this vendor</div>';
        return;
    }

    let html = '<div class="table-responsive"><table class="table table-hover table-sm">';
    html += '<thead class="table-light">';
    html += '<tr>';
    html += '<th>Service ID</th>';
    html += '<th>Date</th>';
    html += '<th>Original MRC</th>';
    html += '<th>Renewed MRC</th>';
    html += '<th>Discount</th>';
    html += '<th>Status</th>';
    html += '</tr>';
    html += '</thead>';
    html += '<tbody>';

    renewals.forEach(renewal => {
        const discount = renewal.discount_percent || 0;
        const discountClass = discount > 15 ? 'success' : discount > 5 ? 'info' : 'secondary';

        html += '<tr>';
        html += `<td><strong>${renewal.service_id || 'N/A'}</strong></td>`;
        html += `<td>${renewal.renewal_date || 'N/A'}</td>`;
        html += `<td>${renewal.original_mrc ? renewal.original_mrc.toFixed(2) + ' ' + (renewal.currency || 'USD') : 'N/A'}</td>`;
        html += `<td>${renewal.renewed_mrc ? renewal.renewed_mrc.toFixed(2) + ' ' + (renewal.currency || 'USD') : 'N/A'}</td>`;
        html += `<td><span class="badge bg-${discountClass}">${discount.toFixed(1)}%</span></td>`;
        html += `<td>${renewal.status || 'N/A'}</td>`;
        html += '</tr>';
    });

    html += '</tbody></table></div>';
    container.innerHTML = html;
}

/**
 * Display new contract history table
 */
function displayNewContractHistory(contracts) {
    const container = document.getElementById('newContractHistoryContainer');
    document.getElementById('newContractHistoryCount').textContent = contracts.length;

    if (contracts.length === 0) {
        container.innerHTML = '<div class="alert alert-info">No new contract history found for this vendor</div>';
        return;
    }

    let html = '<div class="table-responsive"><table class="table table-hover table-sm">';
    html += '<thead class="table-light">';
    html += '<tr>';
    html += '<th>Quote ID</th>';
    html += '<th>Date</th>';
    html += '<th>Service ID</th>';
    html += '<th>Bandwidth</th>';
    html += '<th>MRC</th>';
    html += '<th>Status</th>';
    html += '</tr>';
    html += '</thead>';
    html += '<tbody>';

    contracts.forEach(contract => {
        html += '<tr>';
        html += `<td><strong>${contract.quote_id || 'N/A'}</strong></td>`;
        html += `<td>${contract.quote_date || 'N/A'}</td>`;
        html += `<td>${contract.service_id || 'N/A'}</td>`;
        html += `<td>${contract.bandwidth || 'N/A'}</td>`;
        html += `<td>${contract.mrc ? contract.mrc.toFixed(2) + ' USD' : 'N/A'}</td>`;
        html += `<td><span class="badge bg-primary">${contract.status || 'Active'}</span></td>`;
        html += '</tr>';
    });

    html += '</tbody></table></div>';
    container.innerHTML = html;
}
