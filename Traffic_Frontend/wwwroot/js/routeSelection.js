/**
 * Route Selection Module
 * Handles interactive route drawing on map with detailed analytics
 */

(function() {
    'use strict';

    let map = null;
    let draw = null;
    let selectedRoute = null;
    let routeCoordinates = [];
    let clickSelectMode = false;
    let clickMarkers = [];
    
    // Initialize: prefer reusing the dashboard map. Wait for 'dashboardMapReady' or poll for it.
    (function waitForMap() {
        function startIfMapReady() {
            try {
                initializeMap();
                setupEventListeners();
            } catch (err) {
                console.error('RouteSelection initialization error:', err);
            }
        }

        if (window.dashboardMap && typeof window.dashboardMap.loaded === 'function' && window.dashboardMap.loaded()) {
            console.log('routeSelection: dashboardMap already available, initializing.');
            startIfMapReady();
            return;
        }

        // Listen for explicit ready event
        const onReady = function(e) {
            console.log('routeSelection: received dashboardMapReady event');
            document.removeEventListener('dashboardMapReady', onReady);
            startIfMapReady();
        };
        document.addEventListener('dashboardMapReady', onReady);

        // Poll as a fallback for a short period (5s)
        let attempts = 0;
        const maxAttempts = 20; // 20 * 250ms = 5s
        const iv = setInterval(() => {
            attempts++;
            if (window.dashboardMap && typeof window.dashboardMap.loaded === 'function' && window.dashboardMap.loaded()) {
                clearInterval(iv);
                document.removeEventListener('dashboardMapReady', onReady);
                console.log('routeSelection: detected dashboardMap via polling, initializing.');
                startIfMapReady();
                return;
            }
            if (attempts >= maxAttempts) {
                clearInterval(iv);
                console.warn('routeSelection: dashboardMap not found after polling. Route selection will remain disabled.');
            }
        }, 250);
    })();

    function initializeMap() {
        if (!window.MAPBOX_ACCESS_TOKEN) {
            console.error('Mapbox access token not found');
            return;
        }

        mapboxgl.accessToken = window.MAPBOX_ACCESS_TOKEN;

        // If a dashboard map already exists (initialized by dashboard.js), reuse it
        if (window.dashboardMap && typeof window.dashboardMap.addControl === 'function') {
            map = window.dashboardMap;
            console.log('Using existing dashboard map for route selection');
        } else {
            map = new mapboxgl.Map({
                container: 'dashboardMap',
                style: 'mapbox://styles/mapbox/streets-v12',
                center: [72.5714, 23.0225], // Ahmedabad coordinates
                zoom: 12
            });

            // Store map globally for other modules
            window.dashboardMap = map;
        }

        // Add navigation controls
        map.addControl(new mapboxgl.NavigationControl(), 'top-right');

        // Initialize Mapbox GL Draw (reuse if already present)
        if (window.mapboxDraw) {
            draw = window.mapboxDraw;
        } else {
            draw = new MapboxDraw({
                displayControlsDefault: false,
                controls: {
                    line_string: false,
                    polygon: false,
                    point: false,
                    trash: false
                },
                styles: [
                // Line styling
                {
                    'id': 'gl-draw-line',
                    'type': 'line',
                    'filter': ['all', ['==', '$type', 'LineString'], ['!=', 'mode', 'static']],
                    'layout': {
                        'line-cap': 'round',
                        'line-join': 'round'
                    },
                    'paint': {
                        'line-color': '#3b82f6',
                        'line-width': 4,
                        'line-opacity': 0.8
                    }
                },
                // Point styling
                {
                    'id': 'gl-draw-point',
                    'type': 'circle',
                    'filter': ['all', ['==', '$type', 'Point'], ['==', 'meta', 'vertex']],
                    'paint': {
                        'circle-radius': 6,
                        'circle-color': '#3b82f6',
                        'circle-stroke-width': 2,
                        'circle-stroke-color': '#ffffff'
                    }
                }
            ]
        });

            // expose globally
            window.mapboxDraw = draw;
        }

        // Add draw control to map if not already added
        try {
            // Avoid adding duplicate controls
            if (!map._controls || !map._controls.some(c => c instanceof MapboxDraw || c.name === 'mapbox-gl-draw')) {
                map.addControl(draw, 'top-left');
            }
        } catch (err) {
            // Some Mapbox builds don't expose internals; attempt safe add
            map.addControl(draw, 'top-left');
        }

        // Listen for draw events (attach once)
        if (!map.__routeSelectionHandlersAttached) {
            map.on('draw.create', handleRouteDrawn);
            map.on('draw.update', handleRouteDrawn);
            map.on('draw.delete', handleRouteDeleted);
            map.__routeSelectionHandlersAttached = true;
        }

        // Handle map clicks when in click-select mode
        if (!map.__routeSelectionClickHandler) {
            map.on('click', function(e) {
                if (clickSelectMode) {
                    handleMapClickForClickSelect(e);
                }
            });
            map.__routeSelectionClickHandler = true;
        }

        // ensure globals are set
        window.dashboardMap = map;
        window.mapboxDraw = draw;

        console.log('Map initialized with route selection enabled');
    }

    function setupEventListeners() {
        const startDrawingBtn = document.getElementById('startDrawingBtn');
        const clearRouteBtn = document.getElementById('clearRouteBtn');
        const createProjectBtn = document.getElementById('createProjectFromRoute');
        const clickSelectBtn = document.getElementById('clickSelectBtn');

        if (startDrawingBtn) {
            startDrawingBtn.addEventListener('click', startDrawing);
        }

        if (clickSelectBtn) {
            clickSelectBtn.addEventListener('click', startClickSelect);
        }

        if (clearRouteBtn) {
            clearRouteBtn.addEventListener('click', clearRoute);
        }

        if (createProjectBtn) {
            createProjectBtn.addEventListener('click', createProjectFromRoute);
        }
    }

    function startDrawing() {
        if (!draw) return;

        // Clear any existing routes
        draw.deleteAll();
        removeClickMarkers();
        clickSelectMode = false;
        
        // Enable line drawing mode
        draw.changeMode('draw_line_string');
        
        document.getElementById('selectionHint').textContent = 
            'Click on the map to add points. Double-click or press Enter to finish.';
        
        console.log('Route drawing mode activated');
    }

    function handleRouteDrawn(e) {
        const data = draw.getAll();
        
        if (data.features.length === 0) {
            return;
        }

        // Get the drawn feature
        selectedRoute = data.features[0];
        routeCoordinates = selectedRoute.geometry.coordinates;

        console.log('Route drawn:', routeCoordinates.length, 'points');

        // Calculate and display route information
        analyzeRoute();

        // Enable clear button
        document.getElementById('clearRouteBtn').disabled = false;
        
        // Update hint
        document.getElementById('selectionHint').textContent = 
            'Route selected. View details below or create a project.';
    }

    function handleRouteDeleted(e) {
        clearRouteInfo();
    }

    function clearRoute() {
        if (draw) {
            draw.deleteAll();
        }
        clearRouteInfo();
        removeClickMarkers();
        clickSelectMode = false;
        
        document.getElementById('selectionHint').textContent = 
            'Click "Draw Route" then click points on the map to create a construction route.';
    }

    function clearRouteInfo() {
        selectedRoute = null;
        routeCoordinates = [];
        
        document.getElementById('routeInfoPanel').classList.add('d-none');
        document.getElementById('clearRouteBtn').disabled = true;
        
        // Reset all info fields
        document.getElementById('routeLength').textContent = '-';
        document.getElementById('routePoints').textContent = '-';
        document.getElementById('roadType').textContent = '-';
        document.getElementById('roadWidth').textContent = '-';
        document.getElementById('roadLanes').textContent = '-';
        document.getElementById('vehicleCount').textContent = '-';
        document.getElementById('twoWheelerCount').textContent = '-';
        document.getElementById('fourWheelerCount').textContent = '-';
        document.getElementById('heavyVehicleCount').textContent = '-';
    }

    async function analyzeRoute() {
        if (!selectedRoute || routeCoordinates.length < 2) {
            console.warn('No valid route to analyze');
            return;
        }

        // Calculate route length using Turf.js
        const line = turf.lineString(routeCoordinates);
        const lengthKm = turf.length(line, {units: 'kilometers'});

        // Display basic route info
        document.getElementById('routeLength').textContent = lengthKm.toFixed(2);
        document.getElementById('routePoints').textContent = routeCoordinates.length;

        // Estimate road properties based on route (mock data for now)
        // In production, this would query backend API with coordinates
        const roadInfo = estimateRoadProperties(routeCoordinates, lengthKm);
        
        document.getElementById('roadType').textContent = roadInfo.type;
        document.getElementById('roadWidth').textContent = roadInfo.width;
        document.getElementById('roadLanes').textContent = roadInfo.lanes;

        // Estimate traffic counts (would come from backend in production)
        const trafficInfo = await estimateTrafficCounts(routeCoordinates, lengthKm);
        
        document.getElementById('vehicleCount').textContent = trafficInfo.total.toLocaleString();
        document.getElementById('twoWheelerCount').textContent = trafficInfo.twoWheeler.toLocaleString();
        document.getElementById('fourWheelerCount').textContent = trafficInfo.fourWheeler.toLocaleString();
        document.getElementById('heavyVehicleCount').textContent = trafficInfo.heavy.toLocaleString();

        // Show the info panel
        document.getElementById('routeInfoPanel').classList.remove('d-none');

        // Optionally call backend for detailed analysis
        await fetchBackendRouteAnalysis(routeCoordinates);
    }

    function estimateRoadProperties(coordinates, lengthKm) {
        // Mock estimation based on route length and location
        // In production, this would query road network database
        
        let type = 'Urban Road';
        let width = 7.5;
        let lanes = 2;

        if (lengthKm > 10) {
            type = 'Highway';
            width = 12;
            lanes = 4;
        } else if (lengthKm > 5) {
            type = 'Main Road';
            width = 10;
            lanes = 4;
        } else if (lengthKm < 1) {
            type = 'Local Street';
            width = 5;
            lanes = 1;
        }

        return { type, width, lanes };
    }

    async function estimateTrafficCounts(coordinates, lengthKm) {
        // Mock traffic estimation
        // In production, query backend API with coordinates for real traffic data
        
        const baseVehiclesPerKm = 500; // vehicles per km per hour
        const total = Math.round(baseVehiclesPerKm * lengthKm);
        
        // Distribution (mock percentages)
        const twoWheeler = Math.round(total * 0.45); // 45% two wheelers
        const fourWheeler = Math.round(total * 0.40); // 40% cars
        const heavy = Math.round(total * 0.15); // 15% heavy vehicles

        return {
            total,
            twoWheeler,
            fourWheeler,
            heavy
        };
    }

    async function fetchBackendRouteAnalysis(coordinates) {
        try {
            // Prepare route data for backend
            const routeData = {
                start_lat: coordinates[0][1],
                start_lon: coordinates[0][0],
                end_lat: coordinates[coordinates.length - 1][1],
                end_lon: coordinates[coordinates.length - 1][0],
                waypoints: coordinates.slice(1, -1).map(coord => ({
                    lat: coord[1],
                    lon: coord[0]
                }))
            };

            const backendUrl = window.BACKEND_API_URL || 'http://localhost:8001';
            
            // Call backend route analysis API
            const response = await fetch(`${backendUrl}/routes/analyze`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(routeData)
            });

            if (response.ok) {
                const analysis = await response.json();
                console.log('Backend route analysis:', analysis);
                
                // Update UI with backend data
                if (analysis.distance_km) {
                    document.getElementById('routeLength').textContent = analysis.distance_km.toFixed(2);
                }
                
                if (analysis.road_properties) {
                    document.getElementById('roadType').textContent = analysis.road_properties.road_type;
                    document.getElementById('roadWidth').textContent = analysis.road_properties.road_width_m.toFixed(1);
                    document.getElementById('roadLanes').textContent = analysis.road_properties.lanes;
                }
                
                if (analysis.traffic_counts) {
                    document.getElementById('vehicleCount').textContent = 
                        analysis.traffic_counts.total_vehicles.toLocaleString();
                    document.getElementById('twoWheelerCount').textContent = 
                        analysis.traffic_counts.two_wheeler.toLocaleString();
                    document.getElementById('fourWheelerCount').textContent = 
                        analysis.traffic_counts.four_wheeler.toLocaleString();
                    document.getElementById('heavyVehicleCount').textContent = 
                        analysis.traffic_counts.heavy_vehicle.toLocaleString();
                }
                
                // Store for project creation
                window.lastRouteAnalysis = analysis;
                
                return analysis;
            } else {
                console.warn('Backend route analysis failed:', response.status);
                return null;
            }
        } catch (error) {
            console.warn('Could not fetch backend route analysis:', error.message);
            // Continue with frontend estimation
            return null;
        }
    }

    async function createProjectFromRoute() {
        if (!selectedRoute || routeCoordinates.length < 2) {
            alert('Please draw a route on the map first.');
            return;
        }

        // Prepare project data
        const lengthKm = parseFloat(document.getElementById('routeLength').textContent);
        const roadType = document.getElementById('roadType').textContent;
        const lanes = document.getElementById('roadLanes').textContent;
        
        const projectName = prompt(
            'Enter project name:',
            `Construction Project - ${roadType} (${lengthKm.toFixed(1)} km)`
        );

        if (!projectName) {
            return; // User cancelled
        }

        const projectData = {
            name: projectName,
            status: 'planned',
            startLat: routeCoordinates[0][1],
            startLon: routeCoordinates[0][0],
            endLat: routeCoordinates[routeCoordinates.length - 1][1],
            endLon: routeCoordinates[routeCoordinates.length - 1][0],
            resourceAllocation: `${lanes} lanes, ${lengthKm.toFixed(2)} km ${roadType}`,
            emissionReductionEstimate: null
        };

        try {
            // Use the API client to create project
            const response = await fetch('/api/projects', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(projectData)
            });

            if (response.ok) {
                const createdProject = await response.json();
                if (window.showToast) window.showToast(`Project "${projectName}" created successfully.`, 'success');

                // Refresh projects list
                if (window.loadProjects) {
                    window.loadProjects();
                }

                // Clear the route
                clearRoute();
            } else {
                let errorText = response.statusText;
                try { const err = await response.json(); errorText = err.error || errorText; } catch(e){}
                if (window.showToast) window.showToast(`Failed to create project: ${errorText}`, 'error');
            }
        } catch (error) {
            console.error('Error creating project:', error);
            alert('Error creating project. Please ensure backend is running.');
        }
    }

    // --- Click-select helpers ---
    function startClickSelect() {
        if (!map) {
            console.warn('Map not initialized for click-select');
            return;
        }

        // Clear any previous selection
        draw.deleteAll();
        removeClickMarkers();
        routeCoordinates = [];
        selectedRoute = null;

        clickSelectMode = true;
        document.getElementById('selectionHint').textContent = 'Click the map to select START point, then click to select END point.';
        console.log('Click-select mode activated');
    }

    function handleMapClickForClickSelect(e) {
        try {
            const lngLat = [e.lngLat.lng, e.lngLat.lat];

            // Add a marker for this click
            const marker = new mapboxgl.Marker({ color: '#ff7f0e' })
                .setLngLat(lngLat)
                .addTo(map);
            clickMarkers.push(marker);

            routeCoordinates.push(lngLat);

            if (routeCoordinates.length === 1) {
                document.getElementById('selectionHint').textContent = 'Start point set. Click the map to set END point.';
                return;
            }

            // On second click, create a straight line between points
            if (routeCoordinates.length >= 2) {
                // Create GeoJSON LineString feature
                const feature = {
                    type: 'Feature',
                    geometry: {
                        type: 'LineString',
                        coordinates: routeCoordinates
                    },
                    properties: {}
                };

                // Add to draw so it becomes the selected feature
                try {
                    draw.deleteAll();
                    draw.add(feature);
                } catch (err) {
                    console.warn('Could not add feature to draw:', err);
                }

                // Store selection and analyze
                selectedRoute = feature;
                analyzeRoute();

                document.getElementById('clearRouteBtn').disabled = false;
                document.getElementById('selectionHint').textContent = 'Route selected. View details below or create a project.';

                // Exit click-select mode
                clickSelectMode = false;
                console.log('Click-select mode finished');
            }
        } catch (err) {
            console.error('Error handling map click for click-select:', err);
        }
    }

    function removeClickMarkers() {
        if (clickMarkers && clickMarkers.length) {
            clickMarkers.forEach(m => {
                try { m.remove(); } catch (e) {}
            });
            clickMarkers = [];
        }
    }

    // --- Alternatives rendering ---
    let alternativeRouteIds = [];

    async function fetchAndRenderAlternatives(coordinates) {
        const backendUrl = window.BACKEND_API_URL || 'http://localhost:8001';
        const payload = {
            start_lat: coordinates[0][1],
            start_lon: coordinates[0][0],
            end_lat: coordinates[coordinates.length - 1][1],
            end_lon: coordinates[coordinates.length - 1][0],
            waypoints: coordinates.slice(1, -1).map(c => ({ lat: c[1], lon: c[0] }))
        };

        try {
            const res = await fetch(`${backendUrl}/routes/recommend`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                const data = await res.json();
                if (data && data.routes) {
                    renderAlternativesOnMap(data.routes);
                    dispatchAlternativesEvent(data.routes);
                    return;
                }
            }
        } catch (err) {
            console.warn('Could not fetch /routes/recommend:', err.message);
        }

        // Fallback: generate mock alternatives by perturbing coordinates
        const mock = generateMockAlternatives(coordinates);
        renderAlternativesOnMap(mock);
        dispatchAlternativesEvent(mock);
    }

    function generateMockAlternatives(coordinates) {
        const alts = [];
        const base = coordinates;
        for (let i = 0; i < 3; i++) {
            const coords = base.map(c => [c[0] + (i - 1) * 0.001 * (Math.random() * 0.5), c[1] + (i - 1) * 0.001 * (Math.random() * 0.5)]);
            alts.push({
                id: `mock-${i+1}`,
                name: `Alt ${i+1}`,
                coordinates: coords,
                distance_km: turf.length(turf.lineString(coords), { units: 'kilometers' }),
                travel_time_min: Math.round(turf.length(turf.lineString(coords), { units: 'kilometers' }) * 2),
                traffic_score: Math.random(),
                emission_g: Math.round(Math.random() * 1000),
                rank: i+1
            });
        }
        return alts;
    }

    function renderAlternativesOnMap(routes) {
        if (!map || !map.isStyleLoaded()) return;

        // Remove previous alternatives
        alternativeRouteIds.forEach(id => {
            try { if (map.getLayer(`${id}-line`)) map.removeLayer(`${id}-line`); } catch(e){}
            try { if (map.getSource(id)) map.removeSource(id); } catch(e){}
        });
        alternativeRouteIds = [];

        const colors = ['#3b82f6','#10b981','#f59e0b','#ef4444'];

        routes.forEach((r, idx) => {
            const rid = `alt-route-${r.id || r.id}`;
            alternativeRouteIds.push(rid);

            const geojson = {
                type: 'Feature',
                geometry: { type: 'LineString', coordinates: r.coordinates }
            };

            try {
                if (map.getSource(rid)) {
                    map.getSource(rid).setData(geojson);
                } else {
                    map.addSource(rid, { type: 'geojson', data: geojson });
                    map.addLayer({
                        id: `${rid}-line`,
                        type: 'line',
                        source: rid,
                        layout: { 'line-join': 'round', 'line-cap': 'round' },
                        paint: { 'line-color': colors[idx % colors.length], 'line-width': 4, 'line-opacity': 0.8 }
                    });

                    // Hover effect
                    map.on('mouseenter', `${rid}-line`, function() { map.getCanvas().style.cursor = 'pointer'; });
                    map.on('mouseleave', `${rid}-line`, function() { map.getCanvas().style.cursor = ''; });

                    // Click to select an alternative
                    map.on('click', `${rid}-line`, function(e) { highlightAlternative(r, rid); });
                }
            } catch (err) {
                console.warn('Error rendering alternative', rid, err);
            }
        });

        // Populate Alternatives panel via event (scenarioCompare will render)
        dispatchAlternativesEvent(routes.map((r, i) => ({ routeId: r.id || `mock-${i+1}`, lengthKm: r.distance_km || (turf.length(turf.lineString(r.coordinates), {units: 'kilometers'})), numSegments: (r.coordinates||[]).length, suitabilityScore: r.traffic_score || 0.5, rank: r.rank || (i+1), raw: r })));
    }

    function highlightAlternative(route, rid) {
        try {
            // Emphasize the selected route by increasing width and opacity
            const layerId = `${rid}-line`;
            if (map.getLayer(layerId)) {
                map.setPaintProperty(layerId, 'line-width', 6);
                map.setPaintProperty(layerId, 'line-opacity', 1.0);
            }

            // Zoom to route
            const coords = route.coordinates || (route.geometry && route.geometry.coordinates) || [];
            if (coords.length) {
                const bounds = coords.reduce(function(b, coord) { return b.extend(coord); }, new mapboxgl.LngLatBounds(coords[0], coords[0]));
                map.fitBounds(bounds, { padding: 60 });
            }

            // Dispatch selection event
            document.dispatchEvent(new CustomEvent('routes:alternativeSelected', { detail: { route: route } }));
        } catch (err) {
            console.warn('Could not highlight alternative:', err);
        }
    }

    function dispatchAlternativesEvent(routes) {
        const detail = { allAlternatives: routes, recommendedAlternativeId: routes.length ? routes[0].routeId || routes[0].id : null };
        try { document.dispatchEvent(new CustomEvent('routes:alternatives', { detail: detail })); } catch(e){}
    }

    // Listen for clicks inside Alternatives panel (select button)
    document.addEventListener('click', function(e) {
        const btn = e.target.closest && e.target.closest('[data-route]');
        if (btn && btn.dataset && btn.dataset.route) {
            const rid = btn.dataset.route;
            // Find matching route source id and simulate highlight
            const matching = alternativeRouteIds.find(id => id.endsWith(rid) || id.includes(rid));
            if (matching) {
                // read route data from source
                try {
                    const src = map.getSource(matching);
                    if (src) {
                        const data = src._data || src._geojson || null;
                        if (data) {
                            highlightAlternative({ coordinates: data.geometry.coordinates }, matching);
                        }
                    }
                } catch(e){ console.warn(e); }
            }
        }
    });

    // Export functions for other modules
    window.RouteSelection = {
        getSelectedRoute: () => selectedRoute,
        getRouteCoordinates: () => routeCoordinates,
        clearRoute: clearRoute
    };

})();
