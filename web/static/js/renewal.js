// Renewal Analysis JavaScript
document.addEventListener('DOMContentLoaded', function() {
    const renewalForm = document.getElementById('analyzeRenewalForm');

    if (renewalForm) {
        renewalForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const serviceId = document.getElementById('renewalServiceId').value.trim();

            if (serviceId) {
                analyzeRenewal(serviceId);
            }
        });
    }
});

function analyzeRenewal(serviceId) {
    // Show loading, hide previous results
    document.getElementById('renewalLoadingSpinner').style.display = 'block';
    document.getElementById('renewalErrorAlert').style.display = 'none';
    document.getElementById('renewalQuickSummary').style.display = 'none';
    document.getElementById('vocLineInfo').style.display = 'none';
    document.getElementById('renewalResults').style.display = 'none';

    // Make API call
    fetch('/api/analyze-renewal', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ service_id: serviceId })
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById('renewalLoadingSpinner').style.display = 'none';

        if (data.error) {
            showRenewalError(data.error);
        } else {
            displayRenewalResults(data);
        }
    })
    .catch(error => {
        document.getElementById('renewalLoadingSpinner').style.display = 'none';
        showRenewalError('Network error: ' + error.message);
    });
}

function showRenewalError(message) {
    document.getElementById('renewalErrorMessage').textContent = message;
    document.getElementById('renewalErrorAlert').style.display = 'block';
}

function displayRenewalResults(data) {
    // Update quick summary
    const currency = data.service.currency || 'USD';
    const isUSD = currency.toUpperCase() === 'USD';

    document.getElementById('currentVendorName').textContent = data.voc_line.vendor_name;

    // Display Vendor MRC in local currency and USD
    if (isUSD) {
        document.getElementById('currentMrc').textContent = '$' + data.voc_line.vendor_mrc_usd.toFixed(2) + ' USD';
    } else {
        document.getElementById('currentMrc').textContent =
            '$' + data.voc_line.vendor_mrc.toFixed(2) + ' ' + currency +
            ' ($' + data.voc_line.vendor_mrc_usd.toFixed(2) + ' USD)';
    }

    document.getElementById('currentGm').textContent = data.voc_line.current_gm_percent.toFixed(1) + '%';
    document.getElementById('renewalQuickSummary').style.display = 'block';

    // Display VOC Line details
    displayVocLineInfo(data);

    // Display vendor statistics
    displayVendorStats(data);

    // Display nearby quotes
    displayNearbyQuotes(data);

    // Display recommendations
    displayRecommendations(data);

    // Display VPL options if available
    if (data.vpl_options && data.vpl_options.length > 0) {
        displayRenewalVplOptions(data);
    }

    // Show results
    document.getElementById('renewalResults').style.display = 'block';
}

function displayVocLineInfo(data) {
    const service = data.service;
    const voc = data.voc_line;
    const currency = service.currency || 'USD';
    const isUSD = currency.toUpperCase() === 'USD';

    const gmClass = voc.current_gm_percent >= 50 ? 'success' :
                   voc.current_gm_percent >= 40 ? 'warning' : 'danger';

    // Format Vendor MRC display
    let vendorMrcDisplay;
    if (isUSD) {
        vendorMrcDisplay = `$${voc.vendor_mrc_usd.toFixed(2)} USD`;
    } else {
        vendorMrcDisplay = `$${voc.vendor_mrc.toFixed(2)} ${currency} <small class="text-muted">($${voc.vendor_mrc_usd.toFixed(2)} USD)</small>`;
    }

    const html = `
        <div class="row">
            <div class="col-md-6">
                <p><strong>Service ID:</strong> ${service.service_id}</p>
                <p><strong>Customer:</strong> ${service.customer}</p>
                <p><strong>Bandwidth:</strong> ${service.bandwidth_display}</p>
                <p><strong>Client MRC:</strong> $${service.client_mrc.toFixed(2)} ${currency}</p>
            </div>
            <div class="col-md-6">
                <p><strong>Current Vendor:</strong> <span class="badge bg-primary">${voc.vendor_name}</span></p>
                <p><strong>Vendor MRC:</strong> ${vendorMrcDisplay}</p>
                <p><strong>Gross Margin:</strong> <span class="badge bg-${gmClass}">${voc.current_gm_percent.toFixed(1)}%</span></p>
                <p><strong>Status:</strong> ${voc.status}</p>
            </div>
        </div>
    `;

    document.getElementById('vocLineInfoContent').innerHTML = html;
    document.getElementById('vocLineInfo').style.display = 'block';
}

function displayVendorStats(data) {
    const stats = data.current_vendor_stats;
    let html = '<div class="row">';

    // Renewal Statistics
    if (stats.renewal_stats) {
        const rs = stats.renewal_stats;
        const successClass = rs.success_rate >= 70 ? 'success' :
                            rs.success_rate >= 50 ? 'warning' : 'danger';

        html += `
            <div class="col-md-6 mb-3">
                <div class="card">
                    <div class="card-header bg-info text-white">
                        <i class="fas fa-sync-alt"></i> Renewal History
                    </div>
                    <div class="card-body">
                        <p><strong>Total Renewals:</strong> ${rs.total_renewals}</p>
                        <p><strong>Success Rate:</strong>
                            <span class="badge bg-${successClass}">${rs.success_rate.toFixed(1)}%</span>
                        </p>
                        <p><strong>Average Discount:</strong> ${rs.avg_discount.toFixed(1)}%</p>
                        ${rs.max_discount !== undefined ? `
                            <p><strong>Maximum Discount:</strong> <span class="badge bg-success">${rs.max_discount.toFixed(1)}%</span></p>
                        ` : ''}
                        <p class="text-muted small mb-0">
                            ${rs.successful_renewals} of ${rs.total_renewals} renewals obtained discounts
                        </p>
                    </div>
                </div>
            </div>
        `;
    }

    // Negotiation Statistics (from VQ creation)
    if (stats.negotiation_stats) {
        const ns = stats.negotiation_stats;
        const successClass = ns.success_rate >= 50 ? 'success' :
                            ns.success_rate >= 30 ? 'warning' : 'danger';

        html += `
            <div class="col-md-6 mb-3">
                <div class="card">
                    <div class="card-header bg-primary text-white">
                        <i class="fas fa-handshake"></i> New Contract History
                    </div>
                    <div class="card-body">
                        <p><strong>Total Negotiations:</strong> ${ns.total_negotiations}</p>
                        <p><strong>Success Rate:</strong>
                            <span class="badge bg-${successClass}">${ns.success_rate.toFixed(1)}%</span>
                        </p>
                        <p><strong>Average Discount:</strong> ${ns.avg_discount.toFixed(1)}%</p>
                        <p class="text-muted small mb-0">
                            ${ns.successful_negotiations} of ${ns.total_negotiations} negotiations obtained discounts
                        </p>
                    </div>
                </div>
            </div>
        `;
    }

    html += '</div>';
    document.getElementById('vendorStatsContent').innerHTML = html;
}

function displayRecommendations(data) {
    const recommendations = data.recommendations;

    if (!recommendations || recommendations.length === 0) {
        document.getElementById('recommendationsList').innerHTML =
            '<div class="alert alert-info">No specific recommendations available.</div>';
        return;
    }

    let html = '';

    recommendations.forEach((rec, index) => {
        const confidenceClass = rec.confidence === 'high' ? 'success' :
                               rec.confidence === 'medium' ? 'warning' : 'secondary';

        html += `
            <div class="card mb-3">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <span>
                        <strong>Recommendation #${rec.priority}</strong>
                    </span>
                    <span class="badge bg-${confidenceClass}">${rec.confidence.toUpperCase()} confidence</span>
                </div>
                <div class="card-body">
                    <h5 class="card-title">
                        <i class="fas fa-arrow-right text-primary"></i> ${rec.strategy}
                    </h5>
                    <p class="card-text">${rec.rationale}</p>
                    ${rec.expected_mrc ? `
                        <div class="row mt-2">
                            <div class="col-md-4">
                                <small class="text-muted">Expected MRC:</small>
                                <div class="fw-bold text-success">$${rec.expected_mrc.toFixed(2)}</div>
                            </div>
                            ${rec.expected_discount ? `
                                <div class="col-md-4">
                                    <small class="text-muted">Expected Discount:</small>
                                    <div class="fw-bold text-info">${rec.expected_discount.toFixed(1)}%</div>
                                </div>
                            ` : ''}
                            ${rec.expected_gm ? `
                                <div class="col-md-4">
                                    <small class="text-muted">Expected GM:</small>
                                    <div class="fw-bold text-primary">${rec.expected_gm.toFixed(1)}%</div>
                                </div>
                            ` : ''}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    });

    document.getElementById('recommendationsList').innerHTML = html;
}

function displayRenewalVplOptions(data) {
    const vplOptions = data.vpl_options;

    if (!vplOptions || vplOptions.length === 0) {
        return;
    }

    // Separate current vendor and alternative vendors
    const currentVendorVpls = vplOptions.filter(v => v.is_current_vendor);
    const alternativeVendorVpls = vplOptions.filter(v => !v.is_current_vendor);

    let html = '';

    // Display current vendor VPLs first
    if (currentVendorVpls.length > 0) {
        html += '<h6 class="mt-3"><i class="fas fa-check-circle text-success"></i> Current Vendor VPL Options</h6>';
        html += '<div class="table-responsive"><table class="table table-hover table-sm">';
        html += `
            <thead class="table-light">
                <tr>
                    <th>Vendor</th>
                    <th>Bandwidth</th>
                    <th>MRC</th>
                    <th>NRC</th>
                    <th>Gross Margin</th>
                    <th>Service Type</th>
                </tr>
            </thead>
            <tbody>
        `;

        currentVendorVpls.forEach(vpl => {
            const gmClass = vpl.gm_status === 'success' ? 'success' :
                           vpl.gm_status === 'warning' ? 'warning' : 'danger';

            html += `
                <tr class="table-success">
                    <td><strong>${vpl.vendor_name}</strong></td>
                    <td><strong>${vpl.bandwidth}</strong></td>
                    <td>${vpl.mrc.toFixed(2)} ${vpl.mrc_currency}</td>
                    <td>${vpl.nrc.toFixed(2)}</td>
                    <td><span class="badge bg-${gmClass}">${vpl.gm.toFixed(1)}%</span></td>
                    <td><small>${vpl.service_type}</small></td>
                </tr>
            `;
        });

        html += '</tbody></table></div>';
    }

    // Display alternative vendor VPLs
    if (alternativeVendorVpls.length > 0) {
        html += '<h6 class="mt-4"><i class="fas fa-exchange-alt text-info"></i> Alternative Vendor VPL Options (Negotiation Leverage)</h6>';
        html += '<div class="alert alert-info"><i class="fas fa-lightbulb"></i> Use these as leverage in renewal negotiations or consider switching vendors for better margins.</div>';
        html += '<div class="table-responsive"><table class="table table-hover table-sm">';
        html += `
            <thead class="table-light">
                <tr>
                    <th>Vendor</th>
                    <th>Bandwidth</th>
                    <th>MRC</th>
                    <th>NRC</th>
                    <th>Gross Margin</th>
                    <th>Service Type</th>
                </tr>
            </thead>
            <tbody>
        `;

        alternativeVendorVpls.forEach(vpl => {
            const gmClass = vpl.gm_status === 'success' ? 'success' :
                           vpl.gm_status === 'warning' ? 'warning' : 'danger';

            html += `
                <tr class="table-info">
                    <td><strong>${vpl.vendor_name}</strong></td>
                    <td><strong>${vpl.bandwidth}</strong></td>
                    <td>${vpl.mrc.toFixed(2)} ${vpl.mrc_currency}</td>
                    <td>${vpl.nrc.toFixed(2)}</td>
                    <td><span class="badge bg-${gmClass}">${vpl.gm.toFixed(1)}%</span></td>
                    <td><small>${vpl.service_type}</small></td>
                </tr>
            `;
        });

        html += '</tbody></table></div>';
    }

    if (html) {
        document.getElementById('renewalVplList').innerHTML = html;
        document.getElementById('renewalVplSection').style.display = 'block';
    }
}

function displayNearbyQuotes(data) {
    const container = document.getElementById('renewalNearbyQuotesContainer');
    const section = document.getElementById('renewalNearbyQuotesSection');

    if (!container) return;

    const nearbyQuotes = data.nearby_quotes || [];

    if (nearbyQuotes.length === 0) {
        section.style.display = 'none';
        return;
    }

    const currency = data.service.currency || 'USD';
    const currentVendor = data.voc_line.vendor_name;

    // Sort by distance first, then by MRC
    const sortedQuotes = [...nearbyQuotes].sort((a, b) => {
        // Same vendor quotes first
        if (a.is_same_vendor !== b.is_same_vendor) {
            return b.is_same_vendor - a.is_same_vendor;
        }
        // Then by distance
        return a.distance_meters - b.distance_meters;
    });

    let html = '';

    sortedQuotes.forEach(vq => {
        const gm = vq.gm || 0;
        const gmClass = gm >= 50 ? 'success' : gm >= 40 ? 'warning' : 'danger';
        const distanceKm = ((vq.distance_meters || 0) / 1000).toFixed(1);
        const vendorName = vq.vendor_name || 'Unknown';
        const isSameVendor = vq.is_same_vendor;

        // Different styling for same vendor vs alternative vendors
        const cardClass = isSameVendor ? 'border-success' : 'border-info';
        const vendorBadgeClass = isSameVendor ? 'bg-success' : 'bg-info';
        const vendorLabel = isSameVendor ? '(Current Vendor)' : '(Alternative Vendor)';

        html += `
            <div class="card mb-3 ${cardClass}">
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-12">
                            <h6 class="mb-2">
                                <i class="fas fa-building"></i>
                                <span class="badge ${vendorBadgeClass}">${vendorName}</span>
                                <small class="text-muted ms-2">${vendorLabel}</small>
                                <span class="badge bg-warning text-dark ms-2">
                                    <i class="fas fa-map-marker-alt"></i> ${distanceKm} km away
                                </span>
                            </h6>
                            <div class="row mt-2">
                                <div class="col-md-3">
                                    <small class="text-muted">Service ID:</small>
                                    <div class="fw-bold">${vq.service_id || 'N/A'}</div>
                                </div>
                                <div class="col-md-2">
                                    <small class="text-muted">Bandwidth:</small>
                                    <div class="fw-bold">${vq.bandwidth || 'N/A'}</div>
                                </div>
                                <div class="col-md-2">
                                    <small class="text-muted">Service Type:</small>
                                    <div class="small">${vq.service_type || 'N/A'}</div>
                                </div>
                                <div class="col-md-2">
                                    <small class="text-muted">MRC:</small>
                                    <div class="fw-bold text-success">$${vq.mrc.toFixed(2)} ${currency}</div>
                                </div>
                                <div class="col-md-2">
                                    <small class="text-muted">Potential GM:</small>
                                    <div>
                                        <span class="badge bg-${gmClass}">${gm.toFixed(1)}%</span>
                                    </div>
                                </div>
                            </div>
                            <div class="row mt-2">
                                <div class="col-md-12">
                                    <small class="text-muted">Date Created:</small>
                                    <span class="small ms-2">${vq.date_created || 'N/A'}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
    section.style.display = 'block';
}
