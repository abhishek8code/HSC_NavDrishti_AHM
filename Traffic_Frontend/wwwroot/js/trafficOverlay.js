// Traffic overlay: poll live traffic and update heatmap
 (function(){
  // Traffic overlay: poll live traffic and update heatmap
  // Controlled by `window.ENABLE_TRAFFIC_POLL` (defaults to false)
  const POLL_MS = 30000;
  let routeId = 1;

  async function poll(){
    if (!window.ENABLE_TRAFFIC_POLL) {
      console.debug('trafficOverlay: polling disabled via window.ENABLE_TRAFFIC_POLL');
      return;
    }
    if (typeof apiClient === 'undefined') {
      console.warn('trafficOverlay: apiClient not available, skipping poll');
      return;
    }
    if (typeof map === 'undefined' || !map) {
      console.warn('trafficOverlay: map not ready, skipping poll');
      return;
    }

    try{
      const data = await apiClient.getTraffic(routeId);
      if(!data) return;
      // Update a simple heat source using vehicle_count as weight
      const features = [];
      if(data.averageSpeed != null && data.congestionState){
        // Emit a point at center for demo; in future, per-segment data
        const center = map.getCenter();
        features.push({ type:'Feature', properties:{ weight: data.vehicleCount ?? 1 }, geometry:{ type:'Point', coordinates:[center.lng, center.lat] } });
      }
      const srcId = 'traffic-heat-source';
      if(!map.getSource(srcId)){
        map.addSource(srcId, { type:'geojson', data:{ type:'FeatureCollection', features } });
        map.addLayer({ id:'traffic-heat-layer', type:'heatmap', source:srcId, paint:{ 'heatmap-weight':['get','weight'], 'heatmap-intensity':1 } });
      } else {
        map.getSource(srcId).setData({ type:'FeatureCollection', features });
      }
      // Alerts panel
      const panel = document.getElementById('trafficAlertsPanel');
      if(panel){
        panel.innerHTML = `<div><strong>State:</strong> ${data.congestionState || 'Unknown'} | <strong>Vehicles:</strong> ${data.vehicleCount ?? '-'} | <strong>Speed:</strong> ${data.averageSpeed ?? '-'} km/h</div>`;
      }
    }catch(err){
      console.warn('Traffic poll failed', err);
    }
    setTimeout(poll, POLL_MS);
  }

  // Start polling only if polling is enabled - keep safe fallback
  document.addEventListener('DOMContentLoaded', ()=>{
    if (window.ENABLE_TRAFFIC_POLL) {
      setTimeout(poll, 1000);
    } else {
      console.debug('trafficOverlay: not starting poll (window.ENABLE_TRAFFIC_POLL is false)');
    }
  });
})();
