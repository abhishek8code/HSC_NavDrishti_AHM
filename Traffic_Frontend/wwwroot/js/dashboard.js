// Dashboard JavaScript for real-time updates and heatmap rendering

let map;
let heatmapLayerId = 'heatmap-layer';
let heatmapSourceId = 'heatmap-source';
let connection;
let trafficRenderer = null;
const backendApiUrl = window.BACKEND_API_URL || 'http://localhost:8000';

// Load projects on page load
document.addEventListener('DOMContentLoaded', async () => {
    await loadProjects();
    setupCreateProjectForm();
    initializeDashboardMap();
});

// Load and display projects
async function loadProjects() {
    try {
        const projects = await apiClient.getProjects();
        displayProjects(projects);
        updateProjectsMetric(projects.length);
    } catch (error) {
        console.error('Failed to load projects:', error);
        document.getElementById('projectsList').innerHTML = '<p class="text-danger">Failed to load projects</p>';
    }
}

// Display projects in the list
function displayProjects(projects) {
    const projectsList = document.getElementById('projectsList');
    
    if (!projects || projects.length === 0) {
        projectsList.innerHTML = '<p class="text-muted">No projects yet. Create one to get started!</p>';
        return;
    }

    let html = '<div class="list-group">';
    projects.forEach(project => {
        const statusBadgeClass = project.status === 'active' ? 'bg-success' : 
                                project.status === 'planned' ? 'bg-info' : 'bg-secondary';
        html += `
            <div class="list-group-item">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <h6 class="mb-1">${project.name}</h6>
                        <span class="badge ${statusBadgeClass}">${project.status}</span>
                    </div>
                    <small class="text-muted">ID: ${project.id}</small>
                </div>
            </div>
        `;
    });
    html += '</div>';
    projectsList.innerHTML = html;
}

// Setup create project form
function setupCreateProjectForm() {
    const form = document.getElementById('createProjectForm');
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const projectName = document.getElementById('projectName').value;
        const projectStatus = document.getElementById('projectStatus').value;
        
        try {
            const newProject = await apiClient.createProject({
                name: projectName,
                status: projectStatus
            });
            
            // Reset form
            form.reset();
            
            // Reload projects
            await loadProjects();
            alert('Project created successfully!');
        } catch (error) {
            console.error('Failed to create project:', error);
            alert('Failed to create project: ' + error.message);
        }
    });
}

// Update projects metric
function updateProjectsMetric(count) {
    document.getElementById('activeProjects').textContent = count;
}

// Initialize Mapbox map
function initializeDashboardMap() {
    const mapboxToken = window.MAPBOX_ACCESS_TOKEN;
    
    if (!mapboxToken || mapboxToken === 'YOUR_MAPBOX_ACCESS_TOKEN_HERE') {
        console.error('Mapbox access token is not set');
        return;
    }

    mapboxgl.accessToken = mapboxToken;

    map = new mapboxgl.Map({
        container: 'dashboardMap',
        // Use your custom published Mapbox style
        style: 'mapbox://styles/abhi8code/cmihl5ebg003p01r184ixfrqb',
        center: [72.5714, 23.0225], // Default to Ahmedabad, India
        zoom: 12
    });

    map.on('load', () => {
        console.log('Dashboard map loaded successfully');
        
        // Initialize empty heatmap source
        map.addSource(heatmapSourceId, {
            type: 'geojson',
            data: {
                type: 'FeatureCollection',
                features: []
            }
        });

        // Add heatmap layer
        map.addLayer({
            id: heatmapLayerId,
            type: 'heatmap',
            source: heatmapSourceId,
            maxzoom: 15,
            paint: {
                // Increase the heatmap weight based on frequency and property magnitude
                'heatmap-weight': [
                    'interpolate',
                    ['linear'],
                    ['get', 'severity'],
                    0, 0,
                    1, 0.2,
                    2, 0.4,
                    3, 0.6,
                    4, 0.8,
                    5, 1
                ],
                // Increase the heatmap color weight weight by zoom level
                // heatmap-intensity is a multiplier on top of heatmap-weight
                'heatmap-intensity': [
                    'interpolate',
                    ['linear'],
                    ['zoom'],
                    0, 1,
                    9, 3,
                    15, 5
                ],
                // Color ramp for heatmap.  Domain is 0 (low) to 1 (high).
                // Begin color ramp at 0-stop with a 0-transparancy color
                // to create a blur-like effect.
                'heatmap-color': [
                    'interpolate',
                    ['linear'],
                    ['heatmap-density'],
                    0, 'rgba(33,102,172,0)',
                    0.2, 'rgb(103,169,207)',
                    0.4, 'rgb(209,229,240)',
                    0.6, 'rgb(253,219,199)',
                    0.8, 'rgb(239,138,98)',
                    1, 'rgb(178,24,43)'
                ],
                // Adjust the heatmap radius by zoom level
                'heatmap-radius': [
                    'interpolate',
                    ['linear'],
                    ['zoom'],
                    0, 2,
                    9, 20,
                    15, 30
                ],
                // Transition from heatmap to circle layer by zoom level
                'heatmap-opacity': [
                    'interpolate',
                    ['linear'],
                    ['zoom'],
                    7, 1,
                    9, 0.8,
                    15, 0.6
                ]
            }
        });

        // Add navigation controls
        map.addControl(new mapboxgl.NavigationControl(), 'top-right');

        // Initialize traffic line renderer if available
        if (typeof TrafficLineRenderer !== 'undefined') {
            trafficRenderer = new TrafficLineRenderer(map);
        }

        // Expose the map globally and notify other modules that dashboard map is ready
        try { window.dashboardMap = map; } catch (e) { console.debug('Could not set window.dashboardMap', e); }
        try { document.dispatchEvent(new CustomEvent('dashboardMapReady', { detail: { map: map } })); } catch (e) { console.debug('Could not dispatch dashboardMapReady event', e); }

        // Initialize Phase 5 modules
        if (typeof vehicleTrackingModule !== 'undefined') {
            vehicleTrackingModule.init(map);
            console.log('Vehicle tracking initialized');
        }
        if (typeof analyticsModule !== 'undefined') {
            analyticsModule.init(map);
            console.log('Analytics module initialized');
        }

        // Initialize Phase 6 AI module
        if (typeof aiModule !== 'undefined') {
            aiModule.init(map);
            console.log('AI predictions module initialized');
        }

        // Update on-page map status badge if present
        try {
            const badge = document.getElementById('mapStatusBadge');
            if (badge) {
                badge.classList.remove('bg-secondary');
                badge.classList.add('bg-success');
                badge.textContent = 'Map: ready';
            }
        } catch (e) { /* ignore */ }

        // Add click handler for red zones (heatmap points)
        map.on('click', heatmapLayerId, function(e) {
            const features = map.queryRenderedFeatures(e.point, {
                layers: [heatmapLayerId]
            });

            if (features.length > 0) {
                const feature = features[0];
                const coordinates = feature.geometry.coordinates;
                
                // Open evidence viewer in new window/tab
                const lat = coordinates[1];
                const lon = coordinates[0];
                const viewerUrl = `/Home/EvidenceViewer?lat=${lat}&lon=${lon}`;
                window.open(viewerUrl, '_blank', 'width=1200,height=800');
            }
        });

        // Change cursor on hover over heatmap
        map.on('mouseenter', heatmapLayerId, function() {
            map.getCanvas().style.cursor = 'pointer';
        });

        map.on('mouseleave', heatmapLayerId, function() {
            map.getCanvas().style.cursor = '';
        });
    });
}

// Update heatmap from JSON data
function updateHeatmap(data) {
    if (!map || !map.isStyleLoaded()) {
        console.warn('Map not ready for heatmap update');
        return;
    }

    // Expected data format: Array of objects with {lat, lon, severity}
    // or GeoJSON FeatureCollection
    let features = [];

    if (Array.isArray(data)) {
        // Convert array of {lat, lon, severity} to GeoJSON features
        features = data.map(item => ({
            type: 'Feature',
            geometry: {
                type: 'Point',
                coordinates: [item.lon || item.longitude, item.lat || item.latitude]
            },
            properties: {
                severity: parseFloat(item.severity) || 0
            }
        }));
    } else if (data.type === 'FeatureCollection' && data.features) {
        // Already in GeoJSON format
        features = data.features.map(feature => {
            // Ensure severity is in properties
            if (!feature.properties) {
                feature.properties = {};
            }
            if (!feature.properties.severity) {
                feature.properties.severity = 0;
            }
            return feature;
        });
    } else {
        console.error('Invalid heatmap data format. Expected array or GeoJSON FeatureCollection.');
        return;
    }

    // Update the heatmap source
    const source = map.getSource(heatmapSourceId);
    if (source) {
        source.setData({
            type: 'FeatureCollection',
            features: features
        });
    } else {
        console.error('Heatmap source not found');
    }
}

// Update dashboard metrics and heatmap
function updateDashboard(data) {
    console.log('Updating dashboard with data:', data);

    // Update Active Projects
    if (data.activeProjects !== undefined) {
        const activeProjectsEl = document.getElementById('activeProjects');
        if (activeProjectsEl) {
            activeProjectsEl.textContent = data.activeProjects;
        }
    }

    // Update Critical Alerts (Red counter)
    if (data.criticalAlerts !== undefined) {
        const criticalAlertsEl = document.getElementById('criticalAlerts');
        if (criticalAlertsEl) {
            criticalAlertsEl.textContent = data.criticalAlerts;
        }
    }

    // Update CO2 Saved (Green text)
    if (data.co2Saved !== undefined) {
        const co2SavedEl = document.getElementById('co2Saved');
        if (co2SavedEl) {
            const value = typeof data.co2Saved === 'number' 
                ? data.co2Saved.toFixed(2) 
                : data.co2Saved;
            co2SavedEl.textContent = value + ' kg';
        }
    }

    // Update heatmap if heatmap data is provided
    if (data.heatmapData) {
        updateHeatmap(data.heatmapData);
    }

    // Also check if data itself is heatmap data (for direct heatmap updates)
    if (data.lat !== undefined && data.lon !== undefined) {
        // Single point update - add to existing heatmap
        const source = map.getSource(heatmapSourceId);
        if (source) {
            const currentData = source._data;
            const newFeature = {
                type: 'Feature',
                geometry: {
                    type: 'Point',
                    coordinates: [data.lon || data.longitude, data.lat || data.latitude]
                },
                properties: {
                    severity: parseFloat(data.severity) || 0
                }
            };
            currentData.features.push(newFeature);
            source.setData(currentData);
        }
    }

    // Update traffic lines if provided
    if (data.trafficLines && trafficRenderer) {
        trafficRenderer.updateTrafficLines(data.trafficLines);
    }
}

// Initialize SignalR connection
function initializeSignalR() {
    connection = new signalR.HubConnectionBuilder()
        .withUrl("/dashboardHub")
        .withAutomaticReconnect()
        .build();

    connection.on("UpdateDashboard", function (data) {
        updateDashboard(data);
    });

    // Listen for traffic line updates
    connection.on("UpdateTrafficLines", function (data) {
        if (trafficRenderer && data.lines) {
            trafficRenderer.updateTrafficLines(data.lines);
        }
    });

    connection.start()
        .then(function () {
            console.log("SignalR connection established");
        })
        .catch(function (err) {
            console.error("SignalR connection error: ", err.toString());
        });

    connection.onreconnecting(function () {
        console.log("SignalR reconnecting...");
    });

    connection.onreconnected(function () {
        console.log("SignalR reconnected");
    });

    connection.onclose(function () {
        console.log("SignalR connection closed");
    });
}

// Initialize everything when DOM is ready
document.addEventListener('DOMContentLoaded', function () {
    initializeDashboardMap();
    initializeSignalR();
});

// Export for use in other scripts
window.updateDashboard = updateDashboard;
window.updateHeatmap = updateHeatmap;

// showToast helper using Bootstrap toasts
window.showToast = function(message, type = 'info', timeout = 4000) {
    try {
        // Create toast container if missing
        let container = document.getElementById('toastContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toastContainer';
            container.style.position = 'fixed';
            container.style.top = '1rem';
            container.style.right = '1rem';
            container.style.zIndex = 2000;
            document.body.appendChild(container);
        }

        const toastEl = document.createElement('div');
        toastEl.className = 'toast align-items-center text-white border-0 show';
        toastEl.role = 'alert';
        toastEl.ariaLive = 'assertive';
        toastEl.ariaAtomic = 'true';
        toastEl.style.minWidth = '200px';
        toastEl.style.marginTop = '0.5rem';

        const bgClass = type === 'success' ? 'bg-success' : type === 'error' ? 'bg-danger' : 'bg-secondary';
        toastEl.classList.add(bgClass);

        toastEl.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" aria-label="Close"></button>
            </div>
        `;

        container.appendChild(toastEl);

        // Close handler
        toastEl.querySelector('.btn-close').addEventListener('click', () => {
            toastEl.remove();
        });

        // Auto remove
        setTimeout(() => {
            try { toastEl.remove(); } catch (e) {}
        }, timeout);
    } catch (e) {
        console.warn('showToast error', e);
    }
};

