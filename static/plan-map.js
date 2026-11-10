import * as maplibregl from 'https://unpkg.com/maplibre-gl@6.15.0/dist/maplibre-gl.mjs';

(() => {
  const root = document.getElementById('map-controls');
  const mapNode = document.getElementById('trip-map');
  if (!root || !mapNode) return;

  const form = document.getElementById('place-search-form');
  const queryInput = document.getElementById('place-query');
  const resultsNode = document.getElementById('place-results');
  const waypointNode = document.getElementById('waypoint-list');
  const calculateButton = document.getElementById('calculate-route');
  const nearbyButton = document.getElementById('find-nearby');
  const clearButton = document.getElementById('clear-waypoints');
  const modeSelect = document.getElementById('route-mode');
  const statusNode = document.getElementById('map-status');
  const summaryNode = document.getElementById('route-summary');
  const waypoints = [];
  const markers = [];
  const routeSourceId = 'tabidea-route';
  const prefectureCenters = {
    '北海道': [142.83, 43.47, 6.5], '青森県': [140.74, 40.82, 8], '岩手県': [141.15, 39.70, 7.5],
    '宮城県': [140.87, 38.27, 8], '秋田県': [140.10, 39.72, 7.7], '山形県': [140.36, 38.24, 7.8],
    '福島県': [140.47, 37.75, 7.5], '茨城県': [140.45, 36.34, 8], '栃木県': [139.88, 36.57, 8],
    '群馬県': [139.06, 36.39, 8], '埼玉県': [139.65, 35.86, 8.5], '千葉県': [140.12, 35.60, 8],
    '東京都': [139.69, 35.68, 9], '神奈川県': [139.64, 35.45, 8.8], '新潟県': [139.02, 37.90, 7.5],
    '富山県': [137.21, 36.70, 8.5], '石川県': [136.63, 36.59, 8], '福井県': [136.22, 36.07, 8],
    '山梨県': [138.57, 35.66, 8], '長野県': [138.18, 36.65, 7.5], '岐阜県': [136.76, 35.42, 7.8],
    '静岡県': [138.38, 34.98, 7.8], '愛知県': [136.91, 35.18, 8.5], '三重県': [136.51, 34.73, 8],
    '滋賀県': [135.87, 35.00, 8.5], '京都府': [135.76, 35.02, 9], '大阪府': [135.52, 34.69, 9],
    '兵庫県': [135.18, 34.69, 8], '奈良県': [135.83, 34.69, 8.5], '和歌山県': [135.17, 34.23, 8],
    '鳥取県': [134.24, 35.50, 8], '島根県': [132.77, 35.47, 7.8], '岡山県': [133.93, 34.66, 8.5],
    '広島県': [132.46, 34.40, 8], '山口県': [131.47, 34.19, 8], '徳島県': [134.56, 34.07, 8.5],
    '香川県': [134.04, 34.34, 9], '愛媛県': [132.77, 33.84, 8], '高知県': [133.53, 33.56, 7.8],
    '福岡県': [130.42, 33.59, 8.5], '佐賀県': [130.30, 33.25, 8.5], '長崎県': [129.87, 32.75, 8],
    '熊本県': [130.71, 32.79, 8], '大分県': [131.61, 33.24, 8], '宮崎県': [131.42, 31.91, 7.8],
    '鹿児島県': [130.56, 31.60, 7.5], '沖縄県': [127.68, 26.21, 7.2]
  };
  const destination = root.dataset.destination || '';
  const matchedPrefecture = Object.keys(prefectureCenters).find(name => destination.includes(name));
  const destinationView = matchedPrefecture ? prefectureCenters[matchedPrefecture] : null;

  const map = new maplibregl.Map({
    container: mapNode,
    style: 'https://tiles.openfreemap.org/styles/liberty',
    center: destinationView ? destinationView.slice(0, 2) : [137.5, 36.2],
    zoom: destinationView ? destinationView[2] : 4.6,
    attributionControl: true
  });
  map.addControl(new maplibregl.NavigationControl(), 'top-right');
  let mapLoaded = false;
  map.on('load', () => {
    mapLoaded = true;
    map.addSource(routeSourceId, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
    map.addLayer({
      id: 'tabidea-route-line', type: 'line', source: routeSourceId,
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': '#126c5b', 'line-width': 5, 'line-opacity': 0.9 }
    });
  });
  map.on('error', (event) => {
    console.error('MapLibre map error:', event?.error || event);
    if (!mapLoaded) setStatus('地図を読み込めません。インターネット接続や地図データ配信を確認してください。', true);
  });

  function setStatus(message, isError = false) {
    statusNode.textContent = message;
    statusNode.classList.toggle('map-error', isError);
  }

  async function getJson(url, options) {
    const response = await fetch(url, options);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.error || '通信に失敗しました。');
    return body;
  }

  function clearRoute() {
    summaryNode.textContent = '';
    const source = map.getSource(routeSourceId);
    if (source) source.setData({ type: 'FeatureCollection', features: [] });
  }

  function renderWaypoints() {
    waypointNode.replaceChildren();
    markers.splice(0).forEach(marker => marker.remove());
    waypoints.forEach((place, index) => {
      const item = document.createElement('li');
      const label = document.createElement('span');
      label.textContent = `${index + 1}. ${place.name}`;
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'ghost waypoint-remove';
      remove.textContent = '削除';
      remove.setAttribute('aria-label', `${place.name}を削除`);
      remove.addEventListener('click', () => {
        waypoints.splice(index, 1);
        renderWaypoints();
        clearRoute();
      });
      item.append(label, remove);
      waypointNode.append(item);
      const marker = new maplibregl.Marker({ color: '#126c5b' })
        .setLngLat([place.lon, place.lat]).setPopup(new maplibregl.Popup({ offset: 24 }).setText(place.name)).addTo(map);
      markers.push(marker);
    });
    calculateButton.disabled = waypoints.length < 2 || waypoints.length > 8;
    nearbyButton.disabled = waypoints.length === 0;
    if (waypoints.length) {
      const bounds = new maplibregl.LngLatBounds();
      waypoints.forEach(place => bounds.extend([place.lon, place.lat]));
      if (waypoints.length === 1) map.flyTo({ center: [waypoints[0].lon, waypoints[0].lat], zoom: 13 });
      else map.fitBounds(bounds, { padding: 60, maxZoom: 13 });
    }
  }

  function renderSearchResults(places, emptyMessage) {
    resultsNode.replaceChildren();
    if (!places.length) {
      setStatus(emptyMessage);
      return;
    }
    places.forEach(place => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'place-result';
      const name = document.createElement('strong');
      name.textContent = place.name;
      const address = document.createElement('small');
      address.textContent = place.address || '住所情報なし';
      button.append(name, address);
      button.addEventListener('click', () => {
        if (waypoints.length >= 8) {
          setStatus('地点は最大8か所まで追加できます。', true);
          return;
        }
        if (waypoints.some(item => item.lat === place.lat && item.lon === place.lon)) {
          setStatus('この地点は追加済みです。');
          return;
        }
        waypoints.push(place);
        renderWaypoints();
        clearRoute();
        setStatus(`${place.name}を追加しました。`);
      });
      resultsNode.append(button);
    });
    setStatus('検索結果から地点を選んで追加してください。');
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const query = queryInput.value.trim();
    if (query.length < 2) {
      setStatus('場所の名前を2文字以上入力してください。', true);
      return;
    }
    resultsNode.replaceChildren();
    setStatus('場所を検索しています…');
    try {
      const data = await getJson(`${root.dataset.searchUrl}?q=${encodeURIComponent(query)}`);
      if (!data.results.length) {
        setStatus('候補が見つかりませんでした。別の名前で検索してください。');
        return;
      }
      renderSearchResults(data.results, '場所が見つかりませんでした。');
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  nearbyButton.addEventListener('click', async () => {
    if (!waypoints.length) return;
    const point = waypoints[waypoints.length - 1];
    setStatus(`${point.name}の周辺スポットを検索しています…`);
    try {
      const params = new URLSearchParams({ lat: point.lat, lon: point.lon });
      const data = await getJson(`${root.dataset.nearbyUrl}?${params}`);
      renderSearchResults(data.results, '周辺にスポットが見つかりませんでした。');
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  calculateButton.addEventListener('click', async () => {
    calculateButton.disabled = true;
    setStatus('ルートを計算しています…');
    try {
      const data = await getJson(root.dataset.routeUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': root.dataset.csrf },
        body: JSON.stringify({ waypoints, mode: modeSelect.value })
      });
      const source = map.getSource(routeSourceId);
      if (!source) throw new Error('地図の準備が終わるまで少し待ってください。');
      source.setData(data.geojson);
      const feature = data.geojson.features[0];
      const bounds = new maplibregl.LngLatBounds();
      const collect = coordinates => {
        if (typeof coordinates[0] === 'number' && typeof coordinates[1] === 'number') bounds.extend(coordinates);
        else coordinates.forEach(collect);
      };
      collect(feature.geometry.coordinates);
      map.fitBounds(bounds, { padding: 55, maxZoom: 14 });
      const km = data.distance == null ? null : (data.distance / 1000).toFixed(1);
      const minutes = data.time == null ? null : Math.round(data.time / 60);
      summaryNode.textContent = [km && `距離 約${km} km`, minutes != null && `所要時間 約${minutes}分`].filter(Boolean).join(' · ');
      setStatus('ルートを表示しました。実際の運行状況・通行状況もご確認ください。');
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      calculateButton.disabled = waypoints.length < 2;
    }
  });

  clearButton.addEventListener('click', () => {
    waypoints.splice(0);
    resultsNode.replaceChildren();
    renderWaypoints();
    clearRoute();
    setStatus('場所を検索して2か所以上追加すると、ルートを表示できます。');
  });
})();
