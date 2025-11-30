// Scenario Comparison Module - Compare multiple routes side-by-side
(function() {
    'use strict';

    let selectedRoutes = new Set();
    let allRoutes = [];
    let comparisonChart = null;

    // Listen for alternative routes events
    window.addEventListener('routes:alternatives', (e) => {
        const data = e.detail;
        allRoutes = data?.allAlternatives || [];
        
        // Render alternatives panel with selection checkboxes
        renderAlternativesPanel(allRoutes);
        
        // Update scenario panel
        renderScenarioPanel(data);
    });

    function renderAlternativesPanel(routes) {
        const panel = document.getElementById('alternativesPanel');
        if (!panel) return;

        if (!routes || routes.length === 0) {
            panel.innerHTML = '<p class="text-muted small">No alternatives available.</p>';
            return;
        }

        let html = '<div class="list-group list-group-flush">';
        routes.forEach((route, idx) => {
            const isSelected = selectedRoutes.has(route.id);
            html += `
                <div class="list-group-item px-2 py-2">
                    <div class="form-check">
                        <input class="form-check-input route-compare-checkbox" 
                               type="checkbox" 
                               value="${route.id}" 
                               id="route-check-${route.id}"
                               ${isSelected ? 'checked' : ''}>
                        <label class="form-check-label w-100" for="route-check-${route.id}">
                            <div class="d-flex justify-content-between align-items-center">
                                <div style="flex: 1;">
                                    <strong>${route.name || `Route ${idx + 1}`}</strong>
                                    <div class="small text-muted">
                                        ${route.distance_km?.toFixed(2) || route.lengthKm?.toFixed(2) || 'N/A'} km • 
                                        ${route.travel_time_min || 'N/A'} min
                                    </div>
                                </div>
                                <div class="text-end">
                                    <small class="badge bg-${route.rank === 1 ? 'success' : route.rank === 2 ? 'info' : 'secondary'}">
                                        Rank ${route.rank}
                                    </small>
                                </div>
                            </div>
                        </label>
                    </div>
                </div>
            `;
        });
        html += '</div>';
        panel.innerHTML = html;

        // Attach event listeners to checkboxes
        panel.querySelectorAll('.route-compare-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', handleRouteSelection);
        });
    }

    function handleRouteSelection(e) {
        const routeId = e.target.value;
        
        if (e.target.checked) {
            selectedRoutes.add(routeId);
        } else {
            selectedRoutes.delete(routeId);
        }

        updateComparisonView();
    }

    function renderScenarioPanel(data) {
        const panel = document.getElementById('scenarioPanel');
        if (!panel) return;

        const recommendedId = data?.recommendedAlternativeId ?? '-';
        const altCount = data?.allAlternatives?.length ?? 0;

        panel.innerHTML = `
            <div class="small">
                <div class="mb-2">
                    <strong>Routes Available:</strong> ${altCount}
                </div>
                <div class="mb-2">
                    <strong>Selected:</strong> ${selectedRoutes.size}
                </div>
                <button class="btn btn-sm btn-primary w-100" 
                        id="compareRoutesBtn"
                        ${selectedRoutes.size < 2 ? 'disabled' : ''}>
                    <i class="bi bi-bar-chart"></i> Compare Selected
                </button>
                <button class="btn btn-sm btn-outline-secondary w-100 mt-2" 
                        id="clearSelectionBtn"
                        ${selectedRoutes.size === 0 ? 'disabled' : ''}>
                    Clear Selection
                </button>
            </div>
        `;

        const compareBtn = document.getElementById('compareRoutesBtn');
        const clearBtn = document.getElementById('clearSelectionBtn');

        if (compareBtn) {
            compareBtn.addEventListener('click', showComparisonModal);
        }

        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                selectedRoutes.clear();
                renderAlternativesPanel(allRoutes);
                renderScenarioPanel({ allAlternatives: allRoutes });
            });
        }
    }

    function updateComparisonView() {
        renderScenarioPanel({ allAlternatives: allRoutes });
    }

    function showComparisonModal() {
        if (selectedRoutes.size < 2) {
            alert('Please select at least 2 routes to compare');
            return;
        }

        const modal = createComparisonModal();
        document.body.appendChild(modal);

        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();

        modal.addEventListener('hidden.bs.modal', function() {
            modal.remove();
            if (comparisonChart) {
                comparisonChart.destroy();
                comparisonChart = null;
            }
        });

        // Render comparison
        renderComparison();
    }

    function createComparisonModal() {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = 'comparisonModal';
        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Route Comparison</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-12 mb-3">
                                <canvas id="comparisonChart" height="80"></canvas>
                            </div>
                            <div class="col-12">
                                <div id="comparisonTable"></div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        `;
        return modal;
    }

    function renderComparison() {
        const selectedRoutesList = allRoutes.filter(r => selectedRoutes.has(r.id));
        
        if (selectedRoutesList.length === 0) return;

        // Render chart
        renderComparisonChart(selectedRoutesList);
        
        // Render table
        renderComparisonTable(selectedRoutesList);
    }

    function renderComparisonChart(routes) {
        const ctx = document.getElementById('comparisonChart');
        if (!ctx) return;

        const labels = routes.map(r => r.name || `Route ${r.rank}`);
        const distances = routes.map(r => r.distance_km || r.lengthKm || 0);
        const times = routes.map(r => r.travel_time_min || 0);
        const emissions = routes.map(r => r.emission_g || 0);

        if (comparisonChart) {
            comparisonChart.destroy();
        }

        comparisonChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Distance (km)',
                        data: distances,
                        backgroundColor: 'rgba(59, 130, 246, 0.5)',
                        borderColor: 'rgb(59, 130, 246)',
                        borderWidth: 1,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Travel Time (min)',
                        data: times,
                        backgroundColor: 'rgba(16, 185, 129, 0.5)',
                        borderColor: 'rgb(16, 185, 129)',
                        borderWidth: 1,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Emissions (g CO₂)',
                        data: emissions,
                        backgroundColor: 'rgba(239, 68, 68, 0.5)',
                        borderColor: 'rgb(239, 68, 68)',
                        borderWidth: 1,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Distance (km) / Time (min)'
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Emissions (g CO₂)'
                        },
                        grid: {
                            drawOnChartArea: false
                        }
                    }
                }
            }
        });
    }

    function renderComparisonTable(routes) {
        const tableContainer = document.getElementById('comparisonTable');
        if (!tableContainer) return;

        let html = `
            <table class="table table-sm table-striped">
                <thead>
                    <tr>
                        <th>Route</th>
                        <th>Distance</th>
                        <th>Time</th>
                        <th>Avg Speed</th>
                        <th>Traffic Score</th>
                        <th>Emissions</th>
                    </tr>
                </thead>
                <tbody>
        `;

        routes.forEach(route => {
            const distance = route.distance_km || route.lengthKm || 0;
            const time = route.travel_time_min || 0;
            const avgSpeed = time > 0 ? (distance / time * 60).toFixed(0) : 'N/A';
            const trafficScore = route.traffic_score ? (route.traffic_score * 100).toFixed(0) : 'N/A';
            const emissions = route.emission_g || 0;

            html += `
                <tr>
                    <td><strong>${route.name || `Route ${route.rank}`}</strong></td>
                    <td>${distance.toFixed(2)} km</td>
                    <td>${time} min</td>
                    <td>${avgSpeed} km/h</td>
                    <td><span class="badge bg-${trafficScore > 70 ? 'success' : trafficScore > 40 ? 'warning' : 'danger'}">${trafficScore}%</span></td>
                    <td>${emissions} g</td>
                </tr>
            `;
        });

        html += `
                </tbody>
            </table>
            <div class="alert alert-info mt-3" role="alert">
                <small><strong>Best Choice:</strong> ${getBestRouteRecommendation(routes)}</small>
            </div>
        `;

        tableContainer.innerHTML = html;
    }

    function getBestRouteRecommendation(routes) {
        if (routes.length === 0) return 'No routes to compare';

        const fastestRoute = routes.reduce((prev, curr) => 
            (curr.travel_time_min || Infinity) < (prev.travel_time_min || Infinity) ? curr : prev
        );

        const shortestRoute = routes.reduce((prev, curr) => 
            (curr.distance_km || curr.lengthKm || Infinity) < (prev.distance_km || prev.lengthKm || Infinity) ? curr : prev
        );

        const cleanestRoute = routes.reduce((prev, curr) => 
            (curr.emission_g || Infinity) < (prev.emission_g || Infinity) ? curr : prev
        );

        return `Fastest: ${fastestRoute.name}, Shortest: ${shortestRoute.name}, Cleanest: ${cleanestRoute.name}`;
    }

    // Expose for external access
    window.ScenarioCompare = {
        clearSelection: () => {
            selectedRoutes.clear();
            renderAlternativesPanel(allRoutes);
            renderScenarioPanel({ allAlternatives: allRoutes });
        },
        selectAll: () => {
            allRoutes.forEach(r => selectedRoutes.add(r.id));
            renderAlternativesPanel(allRoutes);
            renderScenarioPanel({ allAlternatives: allRoutes });
        }
    };

})();

