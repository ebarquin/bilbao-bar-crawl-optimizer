const map = L.map('map', {
  zoomControl: false,
  zoomSnap: 0.25,
  dragging: false,
  scrollWheelZoom: false,
  doubleClickZoom: false,
  boxZoom: false,
  keyboard: false,
  touchZoom: false,
  tap: false
}).setView([43.2578, -2.9235], 16);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 20, attribution: '&copy; OpenStreetMap contributors' }).addTo(map);

const status = document.querySelector('#data-status');
const count = document.querySelector('#venue-count');
const categoryList = document.querySelector('#category-list');
const qualityList = document.querySelector('#quality-list');
const networkList = document.querySelector('#network-list');
const algorithmSelect = document.querySelector('#algorithm-select');
const playAnimationButton = document.querySelector('#play-animation');
const pauseAnimationButton = document.querySelector('#pause-animation');
const resetAnimationButton = document.querySelector('#reset-animation');
const animationSpeed = document.querySelector('#animation-speed');
const animationTimeline = document.querySelector('#animation-timeline');
const animationStatus = document.querySelector('#animation-status');
const simulationList = document.querySelector('#simulation-list');
let areaLayer;

const areaUrl = '../data/study-areas/casco-viejo-bilbao.geojson';
const venuesUrl = '../data/processed/venues.geojson';
const reportUrl = '../data/processed/quality-report.json';
const networkReportUrl = '../data/processed/pedestrian-network-report.json';
const accessUrl = '../data/processed/venue-access.json';
const simulationsUrl = '../data/processed/optimization-simulations.json';
const optimizationRoutesUrl = '../data/processed/optimization-routes.geojson';
const algorithmColors = { random: '#9b9a91', nearest_neighbor: '#e96b45', nearest_neighbor_multi_start: '#4d7a9a', two_opt: '#9b6f52', or_tools: '#2c6e49' };
const algorithmNames = { random: 'Aleatorio', nearest_neighbor: 'Nearest Neighbor', nearest_neighbor_multi_start: 'Nearest Neighbor multi-start', two_opt: '2-opt', or_tools: 'OR-Tools' };
const categoryColors = { bar: '#FF5A43', cafetería: '#00B8A9', pub: '#F5B82E' };
const algorithmDescriptions = {
  random: 'Orden aleatorio usado como referencia. No intenta optimizar la ruta.',
  nearest_neighbor: 'Desde el punto inicial, visita siempre el establecimiento no visitado más cercano.',
  nearest_neighbor_multi_start: 'Ejecuta Nearest Neighbor desde distintos puntos iniciales y conserva la mejor ruta encontrada.',
  two_opt: 'Parte de una ruta inicial y mejora sus cruces invirtiendo tramos cuando consigue reducir la distancia.',
  or_tools: 'Utiliza un solver de optimización para buscar una ruta mejor. Es la mejor solución encontrada, no una garantía del óptimo global.'
};
let optimizationRouteFeatures = [];
let optimizationRouteLayer;
let simulationData;
let animationLayer;
let animationMarker;
let animationFrame;
let animationPath = [];
let animationCumulative = [];
let animationTotalDistance = 0;
let animationProgress = 0;
let animationStartedAt = 0;
let animationPausedAt = 0;
let animationRunning = false;
let animationAlgorithm = 'or_tools';

function escapeHtml(value) { return String(value).replace(/[&<>'"]/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[char])); }
function formatMinutes(value) { const minutes = Math.round(Number(value)); const hours = Math.floor(minutes / 60); const remainder = minutes % 60; return hours ? `${hours} h ${remainder} min` : `${remainder} min`; }

function buildAnimationPath(algorithm) {
  const features = optimizationRouteFeatures.filter(feature => feature.properties.algorithm === algorithm).sort((a, b) => a.properties.leg_index - b.properties.leg_index || a.properties.edge_index - b.properties.edge_index);
  const path = [];
  features.forEach(feature => feature.geometry.coordinates.forEach(([lon, lat]) => { const point = [lat, lon]; const previous = path[path.length - 1]; if (!previous || previous[0] !== point[0] || previous[1] !== point[1]) path.push(point); }));
  const cumulative = [0];
  for (let index = 1; index < path.length; index += 1) cumulative.push(cumulative[index - 1] + map.distance(path[index - 1], path[index]));
  animationPath = path;
  animationCumulative = cumulative;
  animationTotalDistance = cumulative[cumulative.length - 1] || 0;
}

function updateAnimationAt(progress) {
  if (!animationPath.length) return;
  animationProgress = Math.max(0, Math.min(1, progress));
  animationTimeline.value = String(Math.round(animationProgress * 1000));
  const target = animationTotalDistance * animationProgress;
  let index = animationCumulative.findIndex(distance => distance >= target);
  if (index < 1) index = 1;
  if (index >= animationPath.length) index = animationPath.length - 1;
  const previousDistance = animationCumulative[index - 1];
  const segmentDistance = animationCumulative[index] - previousDistance || 1;
  const segmentProgress = (target - previousDistance) / segmentDistance;
  const current = [animationPath[index - 1][0] + (animationPath[index][0] - animationPath[index - 1][0]) * segmentProgress, animationPath[index - 1][1] + (animationPath[index][1] - animationPath[index - 1][1]) * segmentProgress];
  animationLayer.setLatLngs(animationPath.slice(0, index).concat([current]));
  animationMarker.setLatLng(current);
  animationStatus.textContent = `${animationAlgorithm.replaceAll('_', ' ')} · ${Math.round(animationProgress * 100)}% · ${Math.round(target)} m recorridos`;
}

function resetAnimation() {
  cancelAnimationFrame(animationFrame);
  animationRunning = false;
  animationPausedAt = 0;
  buildAnimationPath(animationAlgorithm);
  animationLayer.setLatLngs([]);
  animationMarker.setLatLng(animationPath[0] || map.getCenter());
  updateAnimationAt(0);
  playAnimationButton.disabled = false;
  pauseAnimationButton.disabled = true;
}

function animate(timestamp) {
  if (!animationRunning) return;
  const speed = Number(animationSpeed.value);
  const elapsed = timestamp - animationStartedAt;
  const duration = 60000 / speed;
  const progress = Math.min(1, elapsed / duration);
  updateAnimationAt(progress);
  if (progress >= 1) {
    animationRunning = false;
    playAnimationButton.disabled = false;
    pauseAnimationButton.disabled = true;
    animationStatus.textContent = `${animationAlgorithm.replaceAll('_', ' ')} · recorrido completado`;
    return;
  }
  animationFrame = requestAnimationFrame(animate);
}

function prepareAnimation(algorithm) {
  animationAlgorithm = algorithm;
  buildAnimationPath(animationAlgorithm);
  if (animationLayer) map.removeLayer(animationLayer);
  if (animationMarker) map.removeLayer(animationMarker);
  animationLayer = L.polyline([], { color: algorithmColors[animationAlgorithm] || '#2c6e49', weight: 6, opacity: .95, lineCap: 'round', lineJoin: 'round' }).addTo(map);
  animationMarker = L.circleMarker(animationPath[0] || map.getCenter(), { radius: 6, color: '#fff', weight: 2, fillColor: algorithmColors[animationAlgorithm] || '#2c6e49', fillOpacity: 1 }).addTo(map);
  resetAnimation();
}

Promise.all([fetch(areaUrl).then(response => response.json()), fetch(venuesUrl).then(response => response.json()), fetch(reportUrl).then(response => response.json()), fetch(networkReportUrl).then(response => response.json()), fetch(accessUrl).then(response => response.json()), fetch(simulationsUrl).then(response => response.json()), fetch(optimizationRoutesUrl).then(response => response.json())]).then(([area, venues, report, networkReport, access, simulations, optimizationRoutes]) => {
  areaLayer = L.geoJSON(area, { style: { color: '#20211f', weight: 2, dashArray: '6 6', fillColor: '#e96b45', fillOpacity: .10 } }).addTo(map);
  map.invalidateSize({ pan: false });
  const studyBounds = areaLayer.getBounds();
  map.fitBounds(studyBounds, { padding: [0, 0], maxZoom: 16.5 });
  map.setView(studyBounds.getCenter(), 16.5, { animate: false });
  const counts = {};
  const accessByVenue = Object.fromEntries(access.map(item => [item.venue_id, item]));
  L.geoJSON(venues, { pointToLayer: (feature, latlng) => { const streetPoint = accessByVenue[feature.id]?.street_point; const displayLatLng = streetPoint ? [streetPoint[1], streetPoint[0]] : latlng; const category = feature.properties.category; const markerColor = categoryColors[category] || '#B8E5DE'; return L.marker(displayLatLng, { icon: L.divIcon({ className: 'venue-marker', html: `<span style="background:${markerColor}"></span>`, iconSize: [14, 14], iconAnchor: [7, 7] }) }); }, onEachFeature: (feature, layer) => { const category = feature.properties.category; counts[category] = (counts[category] || 0) + 1; layer.bindTooltip(feature.properties.name, { direction: 'top', offset: [0, -8] }); } }).addTo(map);
  count.textContent = report.exported_features;
  categoryList.innerHTML = Object.entries(counts).sort().map(([name, value]) => `<div class="category-item"><span class="category-name"><i class="category-color" style="background:${categoryColors[name] || '#B8E5DE'}"></i>${escapeHtml(name)}</span><strong>${value}</strong></div>`).join('');
  qualityList.innerHTML = [['Elementos consultados', report.total_elements], ['Establecimientos usados', report.exported_features], ['Candidatos a duplicado', report.duplicate_candidates.length], ['Finalidad', 'experimental']].map(([name, value]) => `<div class="quality-item"><span>${escapeHtml(name)}</span><strong>${escapeHtml(value)}</strong></div>`).join('');
  const routeColors = ['#e96b45', '#4d7a9a', '#9b6f52'];
  networkList.innerHTML = [['Nodos', networkReport.nodes], ['Aristas', networkReport.edges], ['Componentes débiles', networkReport.weakly_connected_components], ['Fuera del principal', networkReport.venues_outside_largest_weak_component.length]].map(([name, value]) => `<div class="quality-item"><span>${escapeHtml(name)}</span><strong>${escapeHtml(value)}</strong></div>`).join('');
  simulationData = simulations;
  optimizationRouteFeatures = optimizationRoutes.features;
  const orderedSimulations = [...simulations.simulations].sort((a, b) => a.total_duration_min - b.total_duration_min);
  orderedSimulations.forEach(item => { const option = document.createElement('option'); option.value = item.algorithm; option.textContent = algorithmNames[item.algorithm] || item.algorithm; algorithmSelect.appendChild(option); });
  const renderOptimizationRoute = (selection) => {
    if (optimizationRouteLayer) { map.removeLayer(optimizationRouteLayer); optimizationRouteLayer = null; }
    if (selection === 'all') {
      simulationList.innerHTML = `<div class="algorithm-legend">${simulations.simulations.map(item => `<div class="algorithm-legend-item"><span class="algorithm-swatch" style="background:${algorithmColors[item.algorithm] || '#667'}"></span><span>${escapeHtml(algorithmNames[item.algorithm] || item.algorithm)}</span></div>`).join('')}</div>`;
      return;
    }
    const selected = simulations.simulations.filter(item => item.algorithm === selection);
    simulationList.innerHTML = selected.map(item => `<div class="simulation-card"><div class="simulation-name-row"><div class="simulation-name">${escapeHtml(algorithmNames[item.algorithm] || item.algorithm)}</div><details class="algorithm-help"><summary aria-label="Explicar algoritmo">i</summary><div class="algorithm-popover"><strong>Cómo funciona</strong><p>${escapeHtml(algorithmDescriptions[item.algorithm] || 'Método de comparación de rutas.')}</p></div></details></div><div class="simulation-total"><span>Tiempo total</span><strong>${formatMinutes(item.total_duration_min)}</strong></div><div class="simulation-breakdown"><span>Distancia caminando</span><span>${(item.distance_m / 1000).toFixed(2)} km</span><span>Tiempo caminando</span><span>${formatMinutes(item.walking_time_min)}</span><span>Tiempo en bares</span><span>${formatMinutes(item.stop_time_min)}</span><span>Jornadas de 6 h</span><span>${item.estimated_days}</span></div></div>`).join('');
  };
  algorithmSelect.addEventListener('change', () => { renderOptimizationRoute(algorithmSelect.value); if (algorithmSelect.value !== 'all') prepareAnimation(algorithmSelect.value); });
  const fastestAlgorithm = orderedSimulations[0]?.algorithm || 'or_tools';
  algorithmSelect.value = fastestAlgorithm;
  renderOptimizationRoute(fastestAlgorithm);
  animationTimeline.addEventListener('input', () => { animationRunning = false; animationPausedAt = 0; updateAnimationAt(Number(animationTimeline.value) / 1000); playAnimationButton.disabled = animationProgress >= 1; pauseAnimationButton.disabled = true; });
  playAnimationButton.addEventListener('click', () => { if (animationProgress >= 1) resetAnimation(); animationRunning = true; animationStartedAt = performance.now() - (animationPausedAt || animationProgress * (60000 / Number(animationSpeed.value))); playAnimationButton.disabled = true; pauseAnimationButton.disabled = false; animationFrame = requestAnimationFrame(animate); });
  pauseAnimationButton.addEventListener('click', () => { animationRunning = false; animationPausedAt = animationProgress * (60000 / Number(animationSpeed.value)); playAnimationButton.disabled = false; pauseAnimationButton.disabled = true; });
  resetAnimationButton.addEventListener('click', resetAnimation);
  prepareAnimation(fastestAlgorithm);
  status.textContent = `Datos OSM capturados ${new Date(report.source_captured_at).toLocaleDateString('es-ES')}`;
  document.querySelector('.status-dot').style.background = '#3d9b68';
}).catch(error => { status.textContent = 'No se pudieron cargar los artefactos locales'; console.error(error); });
