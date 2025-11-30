// Traffic Overlay Module - Real-time traffic visualization and alerts
// Polls /traffic/live and /traffic/alerts endpoints and renders on map
(function() {
    'use strict';

    const TRAFFIC_POLL_INTERVAL = 30000; // 30 seconds
    const ALERTS_POLL_INTERVAL = 30000;  // 30 seconds
    const BACKEND_URL = window.BACKEND_API_URL || 'http://localhost:8002';
    
    let trafficLayerVisible = localStorage.getItem('trafficLayerVisible') === 'true';
    let alertsLayerVisible = localStorage.getItem('alertsLayerVisible') !== 'false'; // default true
    let trafficPollTimer = null;
    let alertsPollTimer = null;
    let alertMarkers = [];

    // Initialize when map is ready
    function init() {
        if (!window.map || !window.map.isStyleLoaded()) {
            setTimeout(init, 500);
            return;
        }

        console.log('[TrafficOverlay] Initializing...');
        setupControls();
        
        if (trafficLayerVisible) {
            startTrafficPolling();
        }
        
        if (alertsLayerVisible) {
            startAlertsPolling();
        }
    }

    function setupControls() {
        // Traffic layer toggle
        const trafficToggle = document.getElementById('trafficToggle');
        if (trafficToggle) {
            trafficToggle.checked = trafficLayerVisible;
            trafficToggle.addEventListener('change', (e) => {
                trafficLayerVisible = e.target.checked;
                localStorage.setItem('trafficLayerVisible', trafficLayerVisible);
                
                if (trafficLayerVisible) {
                    startTrafficPolling();
                } else {
                    stopTrafficPolling();
                    clearTrafficLayer();
                }
            });
        }

        // Alerts toggle (optional)
        const alertsToggle = document.getElementById('alertsToggle');
        if (alertsToggle) {
            alertsToggle.checked = alertsLayerVisible;
            alertsToggle.addEventListener('change', (e) => {
                alertsLayerVisible = e.target.checked;
                localStorage.setItem('alertsLayerVisible', alertsLayerVisible);
                
                if (alertsLayerVisible) {
                    startAlertsPolling();
                } else {
                    stopAlertsPolling();
                    clearAlerts();
                }
            });
        }
    }

    // Traffic overlay functions
    function startTrafficPolling() {
        console.log('[TrafficOverlay] Starting traffic polling...');
        fetchAndRenderTraffic(); // Immediate fetch
        trafficPollTimer = setInterval(fetchAndRenderTraffic, TRAFFIC_POLL_INTERVAL);
    }

    function stopTrafficPolling() {
        if (trafficPollTimer) {
            clearInterval(trafficPollTimer);
            trafficPollTimer = null;
        }
    }

    async function fetchAndRenderTraffic() {
        try {
            const response = await fetch(`${BACKEND_URL}/traffic/live`);
            if (!response.ok) {
                console.warn('[TrafficOverlay] Traffic API returned', response.status);
                return;
            }

            const data = await response.json();
            console.log('[TrafficOverlay] Fetched', data.segments?.length || 0, 'traffic segments');
            
            if (data.segments && data.segments.length > 0) {
                renderTrafficSegments(data.segments);
                updateTrafficStats(data.segments);
            }
        } catch (error) {
            console.error('[TrafficOverlay] Error fetching traffic:', error);
        }
    }

    function renderTrafficSegments(segments) {
        if (!window.map) return;

        const sourceId = 'traffic-segments';
        const layerId = 'traffic-segments-layer';

        // Create GeoJSON from segments
        const features = segments.map(segment => ({
            type: 'Feature',
            properties: {
                segment_id: segment.segment_id,
                name: segment.name || 'Road Segment',
                congestion_level: segment.congestion_level,
                speed_kmh: segment.speed_kmh,
                vehicle_count: segment.vehicle_count
            },
            geometry: {
                type: 'LineString',
                coordinates: segment.coordinates
            }
        }));

        const geojson = {
            type: 'FeatureCollection',
            features: features
        };

        // Add or update source
        if (!window.map.getSource(sourceId)) {
            window.map.addSource(sourceId, {
                type: 'geojson',
                data: geojson
            });

            // Add traffic layer with color coding
            window.map.addLayer({
                id: layerId,
                type: 'line',
                source: sourceId,
                layout: {
                    'line-join': 'round',
                    'line-cap': 'round'
                },
                paint: {
                    'line-color': [
                        'interpolate',
                        ['linear'],
                        ['get', 'congestion_level'],
                        0.0, '#22c55e',  // green (low congestion)
                        0.3, '#84cc16',  // lime
                        0.5, '#eab308',  // yellow (medium)
                        0.7, '#f97316',  // orange
                        1.0, '#ef4444'   // red (high congestion)
                    ],
                    'line-width': 6,
                    'line-opacity': 0.7
                }
            });

            // Add hover interaction
            window.map.on('mouseenter', layerId, function(e) {
                window.map.getCanvas().style.cursor = 'pointer';
                
                const feature = e.features[0];
                const props = feature.properties;
                
                new mapboxgl.Popup({ closeButton: false })
                    .setLngLat(e.lngLat)
                    .setHTML(`
                        <div style="padding: 8px;">
                            <strong>${props.name}</strong><br>
                            Speed: ${props.speed_kmh} km/h<br>
                            Vehicles: ${props.vehicle_count}<br>
                            Congestion: ${(props.congestion_level * 100).toFixed(0)}%
                        </div>
                    `)
                    .addTo(window.map);
            });

            window.map.on('mouseleave', layerId, function() {
                window.map.getCanvas().style.cursor = '';
                const popups = document.getElementsByClassName('mapboxgl-popup');
                if (popups.length) {
                    popups[0].remove();
                }
            });
        } else {
            window.map.getSource(sourceId).setData(geojson);
        }
    }

    function clearTrafficLayer() {
        if (!window.map) return;

        const layerId = 'traffic-segments-layer';
        const sourceId = 'traffic-segments';

        try {
            if (window.map.getLayer(layerId)) {
                window.map.removeLayer(layerId);
            }
            if (window.map.getSource(sourceId)) {
                window.map.removeSource(sourceId);
            }
        } catch (e) {
            console.warn('[TrafficOverlay] Error clearing traffic layer:', e);
        }
    }

    function updateTrafficStats(segments) {
        if (!segments || segments.length === 0) return;

        // Calculate average congestion
        const avgCongestion = segments.reduce((sum, s) => sum + (s.congestion_level || 0), 0) / segments.length;
        const avgSpeed = segments.reduce((sum, s) => sum + (s.speed_kmh || 0), 0) / segments.length;
        const totalVehicles = segments.reduce((sum, s) => sum + (s.vehicle_count || 0), 0);

        // Update UI if elements exist
        const congestionEl = document.getElementById('avgCongestion');
        const speedEl = document.getElementById('avgSpeed');
        const vehiclesEl = document.getElementById('totalVehicles');

        if (congestionEl) {
            congestionEl.textContent = `${(avgCongestion * 100).toFixed(0)}%`;
            congestionEl.className = avgCongestion > 0.7 ? 'text-danger' : avgCongestion > 0.4 ? 'text-warning' : 'text-success';
        }
        if (speedEl) {
            speedEl.textContent = `${avgSpeed.toFixed(0)} km/h`;
        }
        if (vehiclesEl) {
            vehiclesEl.textContent = totalVehicles.toLocaleString();
        }
    }

    // Alerts functions
    function startAlertsPolling() {
        console.log('[TrafficOverlay] Starting alerts polling...');
        fetchAndRenderAlerts(); // Immediate fetch
        alertsPollTimer = setInterval(fetchAndRenderAlerts, ALERTS_POLL_INTERVAL);
    }

    function stopAlertsPolling() {
        if (alertsPollTimer) {
            clearInterval(alertsPollTimer);
            alertsPollTimer = null;
        }
    }

    async function fetchAndRenderAlerts() {
        try {
            const response = await fetch(`${BACKEND_URL}/traffic/alerts`);
            if (!response.ok) {
                console.warn('[TrafficOverlay] Alerts API returned', response.status);
                return;
            }

            const data = await response.json();
            console.log('[TrafficOverlay] Fetched', data.alerts?.length || 0, 'alerts');
            
            if (data.alerts && data.alerts.length > 0) {
                renderAlerts(data.alerts);
                updateAlertsPanel(data.alerts);
            }
        } catch (error) {
            console.error('[TrafficOverlay] Error fetching alerts:', error);
        }
    }

    function renderAlerts(alerts) {
        if (!window.map) return;

        // Clear existing alert markers
        clearAlerts();

        // Add new alert markers
        alerts.forEach(alert => {
            const el = document.createElement('div');
            el.className = 'alert-marker';
            el.innerHTML = `
                <div style="
                    background: ${alert.severity === 'high' ? '#ef4444' : alert.severity === 'medium' ? '#f97316' : '#eab308'};
                    color: white;
                    width: 32px;
                    height: 32px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 16px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
                    border: 2px solid white;
                    cursor: pointer;
                    animation: pulse 2s infinite;
                " title="${alert.message}">
                    ${alert.icon || '⚠️'}
                </div>
            `;

            const marker = new mapboxgl.Marker({ element: el })
                .setLngLat(alert.location)
                .setPopup(new mapboxgl.Popup({ offset: 25 })
                    .setHTML(`
                        <div style="padding: 10px; max-width: 250px;">
                            <strong style="color: ${alert.severity === 'high' ? '#ef4444' : '#f97316'};">
                                ${alert.type.toUpperCase()}
                            </strong><br>
                            <small>${alert.area}</small><br>
                            ${alert.message}<br>
                            <small class="text-muted">
                                ${new Date(alert.timestamp).toLocaleTimeString()}
                            </small>
                        </div>
                    `))
                .addTo(window.map);

            alertMarkers.push(marker);
        });

        // Add pulse animation
        if (!document.getElementById('alert-marker-styles')) {
            const style = document.createElement('style');
            style.id = 'alert-marker-styles';
            style.textContent = `
                @keyframes pulse {
                    0%, 100% { transform: scale(1); opacity: 1; }
                    50% { transform: scale(1.1); opacity: 0.8; }
                }
            `;
            document.head.appendChild(style);
        }
    }

    function clearAlerts() {
        alertMarkers.forEach(marker => marker.remove());
        alertMarkers = [];
    }

    function updateAlertsPanel(alerts) {
        const panel = document.getElementById('trafficAlertsContent');
        if (!panel) return;

        if (alerts.length === 0) {
            panel.innerHTML = '<p class="text-muted">No active alerts</p>';
            return;
        }

        const html = alerts.map(alert => `
            <div class="alert alert-${alert.severity === 'high' ? 'danger' : alert.severity === 'medium' ? 'warning' : 'info'} alert-dismissible fade show mb-2" role="alert">
                <strong>${alert.icon || '⚠️'} ${alert.type.charAt(0).toUpperCase() + alert.type.slice(1)}</strong>
                <br><small>${alert.area}</small>
                <p class="mb-0 mt-1" style="font-size: 0.9em;">${alert.message}</p>
                <small class="text-muted">${new Date(alert.timestamp).toLocaleTimeString()}</small>
            </div>
        `).join('');

        panel.innerHTML = html;
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose controls for external access
    window.TrafficOverlay = {
        toggleTraffic: () => {
            trafficLayerVisible = !trafficLayerVisible;
            localStorage.setItem('trafficLayerVisible', trafficLayerVisible);
            trafficLayerVisible ? startTrafficPolling() : (stopTrafficPolling(), clearTrafficLayer());
        },
        toggleAlerts: () => {
            alertsLayerVisible = !alertsLayerVisible;
            localStorage.setItem('alertsLayerVisible', alertsLayerVisible);
            alertsLayerVisible ? startAlertsPolling() : (stopAlertsPolling(), clearAlerts());
        },
        refresh: () => {
            if (trafficLayerVisible) fetchAndRenderTraffic();
            if (alertsLayerVisible) fetchAndRenderAlerts();
        }
    };

})();

