/**
 * Margin Optimizer - Analysis Page JavaScript
 * Handles service analysis and strategy modal
 */

let currentServiceData = null;
let currentServiceId = null;

/**
 * Initialize the analyze form
 */
$(document).ready(() => {
    // Handle form submission
    $('#analyzeForm').on('submit', (e) => {
        e.preventDefault();
        const serviceId = $('#serviceId').val().trim();
        if (serviceId) {
            analyzeService(serviceId);
        }
    });

    // Close modal cleanup
    $('#strategyModal').on('hidden.bs.modal', () => {
        $('#strategyLoading').show();
        $('#strategyContent').hide().html('');
    });
});

/**
 * Analyze a service
 */
async function analyzeService(serviceId) {
    // Reset UI
    Utils.hideError();
    $('#welcomeMessage').hide();
    $('#resultsContainer').hide();
    $('#loadingSpinner').show();
    $('#quickStats').hide();

    currentServiceId = serviceId;

    try {
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ service_id: serviceId })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to analyze service');
        }

        const data = await response.json();
        currentServiceData = data;

        // Display results
        displayResults(data);

    } catch (error) {
        console.error('Error analyzing service:', error);
        Utils.showError(error.message);
        $('#welcomeMessage').show();
    } finally {
        $('#loadingSpinner').hide();
    }
}

/**
 * Display analysis results
 */
function displayResults(data) {
    // Update service info
    $('#infoServiceId').text(data.service.service_id);
    $('#infoCustomer').text(data.service.customer);
    $('#infoBandwidth').text(data.service.bandwidth_display);

    // Show MRC with currency
    let mrcDisplay = `${Utils.formatCurrency(data.service.client_mrc)} ${data.service.currency || ''}`;
    $('#infoClientMrc').html(mrcDisplay);

    $('#infoAddress').text(data.service.address);
    $('#infoCoords').text(`${data.service.latitude}, ${data.service.longitude}`);

    // Update counts
    $('#vqCount').text(data.counts.associated);
    $('#nearbyCount').text(data.counts.nearby || 0);
    $('#vplCount').text(data.counts.vpl);
    $('#statVendorQuotes').text(data.counts.associated);
    $('#statNearbyQuotes').text(data.counts.nearby || 0);
    $('#statVplOptions').text(data.counts.vpl);

    // Display vendor quotes
    displayVendorQuotes(data.vendor_quotes, data.service.client_mrc);

    // Display nearby vendor quotes
    displayNearbyQuotes(data.nearby_quotes || [], data.service.client_mrc);

    // Display VPL options
    displayVPLOptions(data.vpl_options, data.service.client_mrc);

    // Show results
    $('#resultsContainer').fadeIn();
    $('#quickStats').fadeIn();
}

/**
 * Display vendor quotes
 */
function displayVendorQuotes(vendorQuotes, clientMrc) {
    const container = $('#vendorQuotesContainer');
    container.empty();

    if (!vendorQuotes || vendorQuotes.length === 0) {
        container.html(`
            <div class="alert alert-info">
                <i class="fas fa-info-circle"></i> No vendor quotes found for this service.
            </div>
        `);
        return;
    }

    vendorQuotes.forEach(vq => {
        const gmClass = Utils.getGMCardClass(vq.gm || 0);
        const gmBadgeClass = Utils.getGMStatusClass(vq.gm || 0);
        const gmStatusText = Utils.getGMStatusText(vq.gm || 0);

        let historyBadge = '';
        if (vq.has_negotiation_history) {
            historyBadge = '<span class="badge bg-info ms-2"><i class="fas fa-history"></i> Has History</span>';
        }

        // Add renewal stats badge if available
        let renewalBadge = '';
        if (vq.has_renewal_history && vq.renewal_stats) {
            const rs = vq.renewal_stats;
            // Show badge always when there's renewal history, regardless of discount amount
            const badgeColor = rs.success_rate >= 50 ? 'bg-success' : (rs.success_rate >= 25 ? 'bg-warning' : 'bg-secondary');
            renewalBadge = `<span class="badge ${badgeColor} ms-2" title="Total Renewals: ${rs.total_renewals} | Successful: ${rs.successful_renewals}"><i class="fas fa-sync-alt"></i> Renewals: ${rs.success_rate}% success, ${rs.avg_discount}% avg discount</span>`;
        }

        let projectionHtml = '';
        if (vq.projected_with_negotiation) {
            const proj = vq.projected_with_negotiation;
            const projGmBadge = Utils.getGMStatusClass(proj.gm);
            const bestGmBadge = proj.best_gm ? Utils.getGMStatusClass(proj.best_gm) : '';

            projectionHtml = `
                <div class="projection-card mt-3">
                    <div class="projection-label">
                        <i class="fas fa-chart-line"></i> Projected with Negotiation (Avg: ${proj.avg_discount}% discount)
                    </div>
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="projection-value">${Utils.formatCurrency(proj.mrc)}</div>
                        <span class="badge ${projGmBadge}">GM: ${proj.gm}%</span>
                    </div>
                </div>
                ${proj.best_discount && proj.best_discount > proj.avg_discount ? `
                <div class="projection-card mt-2" style="background-color: #e8f5e9; border-left: 3px solid #4caf50;">
                    <div class="projection-label">
                        <i class="fas fa-star"></i> Best Case Scenario (${proj.best_discount}% discount)
                    </div>
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="projection-value">${Utils.formatCurrency(proj.best_mrc)}</div>
                        <span class="badge ${bestGmBadge}">GM: ${proj.best_gm}%</span>
                    </div>
                </div>
                ` : ''}
            `;
        }

        const card = $(`
            <div class="vendor-quote-card ${gmClass}">
                <div class="row align-items-center">
                    <div class="col-md-8">
                        <h6 class="mb-2">
                            <i class="fas fa-building"></i> ${Utils.escapeHtml(vq.vendor_name)}
                            ${historyBadge}
                            ${renewalBadge}
                        </h6>
                        <div class="row">
                            <div class="col-md-4">
                                <small class="text-muted">MRC:</small>
                                <div class="fw-bold text-currency">
                                    ${Utils.formatCurrency(vq.mrc)} ${vq.mrc_currency || ''}
                                    ${vq.mrc_original ? `<br><small class="text-muted">(${Utils.formatCurrency(vq.mrc_original)} ${vq.mrc_original_currency || 'BRL'})</small>` : ''}
                                </div>
                            </div>
                            <div class="col-md-4">
                                <small class="text-muted">GM:</small>
                                <div>
                                    <span class="badge ${gmBadgeClass} gm-badge">${vq.gm}% - ${gmStatusText}</span>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <small class="text-muted">Bandwidth:</small>
                                <div class="fw-bold">${Utils.escapeHtml(vq.bandwidth)}</div>
                            </div>
                        </div>
                        <div class="row mt-2">
                            <div class="col-md-4">
                                <small class="text-muted">Status:</small>
                                <div><span class="badge bg-secondary">${Utils.escapeHtml(vq.status || 'N/A')}</span></div>
                            </div>
                            <div class="col-md-4">
                                <small class="text-muted">Lead Time:</small>
                                <div>${Utils.escapeHtml(vq.lead_time || 'N/A')} days</div>
                            </div>
                            <div class="col-md-4">
                                <small class="text-muted">QB ID:</small>
                                <div class="small font-monospace">${vq.quickbase_id || 'N/A'}</div>
                            </div>
                        </div>
                        ${vq.has_delivered_services ? `
                        <div class="row mt-2">
                            <div class="col-md-12">
                                <small class="text-muted">Total MRC Delivered:</small>
                                <div class="fw-bold text-primary">$${Utils.formatCurrency(vq.delivered_mrc_total)} USD <span class="text-muted small">(${vq.delivered_count} services)</span></div>
                            </div>
                        </div>
                        ` : ''}
                        ${projectionHtml}
                    </div>
                    <div class="col-md-4 text-end">
                        <button class="btn btn-primary btn-sm w-100 mb-2" onclick="showStrategy('${currentServiceId}', ${vq.quickbase_id})">
                            <i class="fas fa-chess"></i> View Strategy
                        </button>
                        ${vq.has_negotiation_history ? `
                            <div class="small text-muted mt-2">
                                <i class="fas fa-chart-bar"></i> ${vq.negotiation_stats.total_negotiations} negotiations<br>
                                <i class="fas fa-percentage"></i> ${vq.negotiation_stats.success_rate}% success rate
                            </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `);

        container.append(card);
    });
}

/**
 * Display nearby vendor quotes (within 1000m, last 12 months)
 */
function displayNearbyQuotes(nearbyQuotes, clientMrc) {
    const container = $('#nearbyQuotesContainer');
    container.empty();

    if (!nearbyQuotes || nearbyQuotes.length === 0) {
        container.html(`
            <div class="alert alert-info">
                <i class="fas fa-info-circle"></i> No nearby vendor quotes found (within 1000m, last 12 months).
            </div>
        `);
        return;
    }

    nearbyQuotes.forEach(vq => {
        const gmClass = Utils.getGMCardClass(vq.gm || 0);
        const gmBadgeClass = Utils.getGMStatusClass(vq.gm || 0);
        const gmStatusText = Utils.getGMStatusText(vq.gm || 0);

        let historyBadge = '';
        if (vq.has_negotiation_history) {
            historyBadge = '<span class="badge bg-info ms-2"><i class="fas fa-history"></i> Has History</span>';
        }

        // Distance badge
        const distanceMeters = vq.distance_meters || 0;
        const distanceBadge = `<span class="badge bg-warning text-dark ms-2"><i class="fas fa-map-marker-alt"></i> ${distanceMeters}m away</span>`;

        let projectionHtml = '';
        if (vq.projected_with_negotiation) {
            const proj = vq.projected_with_negotiation;
            const projGmBadge = Utils.getGMStatusClass(proj.gm);
            const bestGmBadge = proj.best_gm ? Utils.getGMStatusClass(proj.best_gm) : '';

            projectionHtml = `
                <div class="projection-card mt-3">
                    <div class="projection-label">
                        <i class="fas fa-chart-line"></i> Projected with Negotiation (Avg: ${proj.avg_discount}% discount)
                    </div>
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="projection-value">${Utils.formatCurrency(proj.mrc)}</div>
                        <span class="badge ${projGmBadge}">GM: ${proj.gm}%</span>
                    </div>
                </div>
                ${proj.best_discount && proj.best_discount > proj.avg_discount ? `
                <div class="projection-card mt-2" style="background-color: #e8f5e9; border-left: 3px solid #4caf50;">
                    <div class="projection-label">
                        <i class="fas fa-star"></i> Best Case Scenario (${proj.best_discount}% discount)
                    </div>
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="projection-value">${Utils.formatCurrency(proj.best_mrc)}</div>
                        <span class="badge ${bestGmBadge}">GM: ${proj.best_gm}%</span>
                    </div>
                </div>
                ` : ''}
            `;
        }

        const card = $(`
            <div class="vendor-quote-card ${gmClass}">
                <div class="row align-items-center">
                    <div class="col-md-8">
                        <h6 class="mb-2">
                            <i class="fas fa-building"></i> ${Utils.escapeHtml(vq.vendor_name)}
                            ${distanceBadge}
                            ${historyBadge}
                        </h6>
                        <div class="row">
                            <div class="col-md-4">
                                <small class="text-muted">MRC:</small>
                                <div class="fw-bold text-currency">
                                    ${Utils.formatCurrency(vq.mrc)} ${vq.mrc_currency || ''}
                                    ${vq.mrc_original ? `<br><small class="text-muted">(${Utils.formatCurrency(vq.mrc_original)} ${vq.mrc_original_currency || 'BRL'})</small>` : ''}
                                </div>
                            </div>
                            <div class="col-md-4">
                                <small class="text-muted">GM:</small>
                                <div>
                                    <span class="badge ${gmBadgeClass} gm-badge">${vq.gm}% - ${gmStatusText}</span>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <small class="text-muted">Bandwidth:</small>
                                <div class="fw-bold">${Utils.escapeHtml(vq.bandwidth)}</div>
                            </div>
                        </div>
                        <div class="row mt-2">
                            <div class="col-md-4">
                                <small class="text-muted">Status:</small>
                                <div><span class="badge bg-secondary">${Utils.escapeHtml(vq.status || 'N/A')}</span></div>
                            </div>
                            <div class="col-md-4">
                                <small class="text-muted">Lead Time:</small>
                                <div>${Utils.escapeHtml(vq.lead_time || 'N/A')} days</div>
                            </div>
                            <div class="col-md-4">
                                <small class="text-muted">Date Created:</small>
                                <div class="small">${vq.date_created || 'N/A'}</div>
                            </div>
                        </div>
                        ${projectionHtml}
                    </div>
                    <div class="col-md-4 text-end">
                        <button class="btn btn-primary btn-sm w-100 mb-2" onclick="showStrategy('${currentServiceId}', ${vq.quickbase_id})">
                            <i class="fas fa-chess"></i> View Strategy
                        </button>
                        ${vq.has_negotiation_history ? `
                            <div class="small text-muted mt-2">
                                <i class="fas fa-chart-bar"></i> ${vq.negotiation_stats.total_negotiations} negotiations<br>
                                <i class="fas fa-percentage"></i> ${vq.negotiation_stats.success_rate}% success rate
                            </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `);

        container.append(card);
    });
}

/**
 * Display VPL options
 */
function displayVPLOptions(vplOptions, clientMrc) {
    const container = $('#vplOptionsContainer');
    container.empty();

    if (!vplOptions || vplOptions.length === 0) {
        container.html(`
            <div class="alert alert-info">
                <i class="fas fa-info-circle"></i> No VPL options found for this location.
            </div>
        `);
        return;
    }

    vplOptions.forEach(vendor => {
        let historyHtml = '';
        if (vendor.negotiation_stats) {
            const stats = vendor.negotiation_stats;
            historyHtml = `
                <div class="alert alert-info mb-3">
                    <i class="fas fa-history"></i> <strong>Negotiation History:</strong>
                    ${stats.total_negotiations} negotiations,
                    ${stats.success_rate}% success rate,
                    ${stats.avg_discount}% average discount
                </div>
            `;
        }

        const optionsHtml = vendor.options.map((opt, idx) => {
            const gmBadgeClass = Utils.getGMStatusClass(opt.gm);
            const gmStatusText = Utils.getGMStatusText(opt.gm);

            let projectionHtml = '';
            if (opt.projected_with_negotiation) {
                const proj = opt.projected_with_negotiation;
                const projGmBadge = Utils.getGMStatusClass(proj.gm);
                projectionHtml = `
                    <div class="mt-2 p-2" style="background-color: rgba(13, 110, 253, 0.1); border-radius: 4px;">
                        <small>
                            <i class="fas fa-chart-line"></i> With ${proj.discount}% negotiation:
                            <strong>${Utils.formatCurrency(proj.mrc)}</strong>
                            <span class="badge ${projGmBadge} ms-2">GM: ${proj.gm}%</span>
                        </small>
                    </div>
                `;
            }

            return `
                <div class="vpl-option">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <div class="fw-bold">${opt.bandwidth} ${Utils.escapeHtml(opt.service_type)}</div>
                            <div class="mt-1">
                                <small class="text-muted">MRC:</small>
                                <span class="fw-bold text-currency">${Utils.formatCurrency(opt.mrc)} ${opt.mrc_currency || ''}</span>
                                <small class="text-muted ms-3">NRC:</small>
                                <span class="text-currency">${Utils.formatCurrency(opt.nrc)} ${opt.nrc_currency || ''}</span>
                            </div>
                            ${projectionHtml}
                        </div>
                        <div class="text-end">
                            <span class="badge ${gmBadgeClass} gm-badge">${opt.gm}%</span>
                            <div class="small text-muted mt-1">${gmStatusText}</div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        const vendorGroup = $(`
            <div class="vpl-vendor-group">
                <div class="vpl-vendor-header">
                    <i class="fas fa-building"></i> ${Utils.escapeHtml(vendor.vendor_name)}
                    <span class="badge bg-secondary float-end">${vendor.options.length} options</span>
                </div>
                ${historyHtml}
                ${optionsHtml}
            </div>
        `);

        container.append(vendorGroup);
    });
}

/**
 * Show negotiation strategy for a specific VQ
 */
async function showStrategy(serviceId, vqQbId) {
    const modal = new bootstrap.Modal(document.getElementById('strategyModal'));
    modal.show();

    $('#strategyLoading').show();
    $('#strategyContent').hide().html('');

    try {
        // Send VPL options from the analyze page to ensure consistency
        const vplOptions = currentServiceData ? currentServiceData.vpl_options : [];

        const response = await fetch(`/api/strategy/${serviceId}/${vqQbId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                vpl_options: vplOptions
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to load strategy');
        }

        const data = await response.json();
        displayStrategy(data);

    } catch (error) {
        console.error('Error loading strategy:', error);
        $('#strategyContent').html(`
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle"></i> Error: ${error.message}
            </div>
        `).show();
    } finally {
        $('#strategyLoading').hide();
    }
}

/**
 * Display negotiation strategy
 */
function displayStrategy(data) {
    const gmBadgeClass = Utils.getGMStatusClass(data.vendor_quote.current_gm);
    const gmStatusText = Utils.getGMStatusText(data.vendor_quote.current_gm);

    let html = `
        <!-- Current Situation -->
        <div class="card mb-4">
            <div class="card-header bg-info text-white">
                <h6 class="mb-0"><i class="fas fa-info-circle"></i> Current Situation</h6>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-6">
                        <p class="mb-2"><strong>Service:</strong> ${Utils.escapeHtml(data.service.service_id)}</p>
                        <p class="mb-2"><strong>Customer:</strong> ${Utils.escapeHtml(data.service.customer)}</p>
                        <p class="mb-2"><strong>Bandwidth:</strong> ${Utils.escapeHtml(data.service.bandwidth_display)}</p>
                        <p class="mb-2"><strong>Client MRC:</strong> <span class="text-success fw-bold">${Utils.formatCurrency(data.service.client_mrc)}</span></p>
                    </div>
                    <div class="col-md-6">
                        <p class="mb-2"><strong>Vendor:</strong> ${Utils.escapeHtml(data.vendor_quote.vendor_name)}</p>
                        <p class="mb-2"><strong>VQ QB ID:</strong> ${data.vendor_quote.quickbase_id}</p>
                        <p class="mb-2"><strong>Current MRC:</strong> ${Utils.formatCurrency(data.vendor_quote.current_mrc)}</p>
                        <p class="mb-2">
                            <strong>Current GM:</strong>
                            <span class="badge ${gmBadgeClass} gm-badge">${data.vendor_quote.current_gm}% - ${gmStatusText}</span>
                        </p>
                        <p class="mb-2"><strong>Lead Time:</strong> ${Utils.escapeHtml(data.vendor_quote.lead_time)} days</p>
                        <p class="mb-2"><strong>Status:</strong> <span class="badge bg-secondary">${Utils.escapeHtml(data.vendor_quote.status)}</span></p>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Negotiation History
    if (data.negotiation_history) {
        const hist = data.negotiation_history;
        const projGmBadge = Utils.getGMStatusClass(hist.projected_gm);

        html += `
            <div class="card mb-4">
                <div class="card-header bg-primary text-white">
                    <h6 class="mb-0"><i class="fas fa-history"></i> Negotiation History - ${Utils.escapeHtml(data.vendor_quote.vendor_name)}</h6>
                </div>
                <div class="card-body">
                    <div class="history-stats">
                        <div class="history-stat">
                            <span class="history-stat-label">Total Negotiations:</span>
                            <span class="history-stat-value">${hist.total_negotiations}</span>
                        </div>
                        <div class="history-stat">
                            <span class="history-stat-label">Successful Negotiations:</span>
                            <span class="history-stat-value">${hist.successful_negotiations}</span>
                        </div>
                        <div class="history-stat">
                            <span class="history-stat-label">Success Rate:</span>
                            <span class="history-stat-value text-primary">${hist.success_rate}%</span>
                        </div>
                        <div class="history-stat">
                            <span class="history-stat-label">Average Discount Obtained:</span>
                            <span class="history-stat-value text-success">${hist.avg_discount}%</span>
                        </div>
                    </div>

                    <div class="alert alert-success mt-3">
                        <h6><i class="fas fa-chart-line"></i> Projection with Negotiation</h6>
                        <p class="mb-2">Applying average discount of <strong>${hist.avg_discount}%</strong>:</p>
                        <div class="row">
                            <div class="col-md-6">
                                <div><strong>Projected MRC:</strong> ${Utils.formatCurrency(hist.projected_mrc)}</div>
                            </div>
                            <div class="col-md-6">
                                <div>
                                    <strong>Projected GM:</strong>
                                    <span class="badge ${projGmBadge} ms-2">${hist.projected_gm}%</span>
                                </div>
                            </div>
                        </div>
                        <div class="mt-2">
                            <strong>Probability of Success:</strong> ${hist.success_rate}%
                        </div>
                    </div>
                </div>
            </div>
        `;
    } else {
        html += `
            <div class="alert alert-warning mb-4">
                <i class="fas fa-exclamation-triangle"></i> No negotiation history available for this vendor.
            </div>
        `;
    }

    // Targets
    html += `
        <div class="card mb-4">
            <div class="card-header bg-success text-white">
                <h6 class="mb-0"><i class="fas fa-bullseye"></i> Target Margins</h6>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-6">
                        <div class="target-card">
                            <div class="target-label text-warning">
                                <i class="fas fa-flag"></i> For 40% GM (Minimum Acceptable)
                            </div>
                            <div><strong>Target MRC:</strong> ${Utils.formatCurrency(data.targets.gm_40.target_mrc)}</div>
                            <div><strong>Discount Needed:</strong> <span class="text-primary">${data.targets.gm_40.discount_needed}%</span></div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="target-card border-success">
                            <div class="target-label text-success">
                                <i class="fas fa-star"></i> For 50% GM (Target)
                            </div>
                            <div><strong>Target MRC:</strong> ${Utils.formatCurrency(data.targets.gm_50.target_mrc)}</div>
                            <div><strong>Discount Needed:</strong> <span class="text-success">${data.targets.gm_50.discount_needed}%</span></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Vendor VPL
    if (data.vendor_vpl && data.vendor_vpl.length > 0) {
        html += `
            <div class="card mb-4">
                <div class="card-header text-white" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                    <h6 class="mb-0">
                        <i class="fas fa-star"></i> Vendor Price List (VPL) - STRONGEST ARGUMENT!
                    </h6>
                </div>
                <div class="card-body">
                    <div class="alert alert-info">
                        <i class="fas fa-lightbulb"></i>
                        <strong>Use this as your primary argument!</strong>
                        These are the vendor's own published prices.
                    </div>
        `;

        data.vendor_vpl.forEach((vpl, idx) => {
            const vplGmBadge = Utils.getGMStatusClass(vpl.gm);
            html += `
                <div class="vpl-option mb-3">
                    <div class="row align-items-center">
                        <div class="col-md-6">
                            <div class="fw-bold">${vpl.bandwidth} ${Utils.escapeHtml(vpl.service_type)}</div>
                            <div class="mt-1">
                                <small class="text-muted">MRC:</small> <span class="fw-bold">${Utils.formatCurrency(vpl.mrc)}</span>
                                <small class="text-muted ms-3">NRC:</small> ${Utils.formatCurrency(vpl.nrc)}
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="text-center">
                                <div class="small text-muted">Savings</div>
                                <div class="fw-bold text-success">${Utils.formatCurrency(vpl.savings)}</div>
                                <div class="small text-muted">(${vpl.savings_percent}%)</div>
                            </div>
                        </div>
                        <div class="col-md-3 text-end">
                            <span class="badge ${vplGmBadge} gm-badge">GM: ${vpl.gm}%</span>
                        </div>
                    </div>
                </div>
            `;
        });

        const bestVpl = data.vendor_vpl[0];
        html += `
                    <div class="alert alert-success mt-3">
                        <h6><i class="fas fa-comments"></i> Suggested Argument:</h6>
                        <p class="mb-0">
                            "Your published price list shows <strong>${Utils.formatCurrency(bestVpl.mrc)}</strong> for this service.
                            The current quote is <strong>${Utils.formatCurrency(data.vendor_quote.current_mrc)}</strong>.
                            We'd like to proceed at the published price."
                        </p>
                    </div>
                </div>
            </div>
        `;
    }

    // Alternatives
    if (data.alternatives && data.alternatives.length > 0) {
        html += `
            <div class="card mb-4">
                <div class="card-header bg-warning">
                    <h6 class="mb-0"><i class="fas fa-exchange-alt"></i> Alternative Vendors (Use as Leverage)</h6>
                </div>
                <div class="card-body">
                    <p class="small text-muted mb-3">
                        <i class="fas fa-info-circle"></i> Use these as negotiation leverage, but consider implementation time and SLAs.
                    </p>
        `;

        data.alternatives.forEach((alt, idx) => {
            const altGmBadge = Utils.getGMStatusClass(alt.gm);
            html += `
                <div class="alternative-card">
                    <div>
                        <div class="fw-bold">${Utils.escapeHtml(alt.vendor_name)}</div>
                        <div class="small">${alt.bandwidth} ${Utils.escapeHtml(alt.service_type)}</div>
                        <div class="mt-1"><strong>MRC:</strong> ${Utils.formatCurrency(alt.mrc)}</div>
                    </div>
                    <div class="text-end">
                        <span class="badge ${altGmBadge} gm-badge">GM: ${alt.gm}%</span>
                    </div>
                </div>
            `;
        });

        html += `
                </div>
            </div>
        `;
    }

    // Recommendations
    if (data.recommendations && data.recommendations.length > 0) {
        html += `
            <div class="card mb-4">
                <div class="card-header bg-dark text-white">
                    <h6 class="mb-0"><i class="fas fa-lightbulb"></i> Recommended Strategy</h6>
                </div>
                <div class="card-body">
        `;

        data.recommendations.forEach((rec, idx) => {
            html += `
                <div class="recommendation-card strength-${rec.strength}">
                    <div class="recommendation-title">
                        <span>
                            ${Utils.getPriorityIcon(rec.priority)}
                            ${Utils.escapeHtml(rec.title)}
                        </span>
                        ${Utils.getStrengthBadge(rec.strength)}
                    </div>
                    <ul class="recommendation-actions">
            `;

            rec.actions.forEach(action => {
                html += `<li>${action.text}</li>`;
            });

            html += `
                    </ul>
                </div>
            `;
        });

        html += `
                </div>
            </div>
        `;
    }

    $('#strategyContent').html(html).fadeIn();
}

// Make functions globally accessible
window.showStrategy = showStrategy;
window.analyzeService = analyzeService;
