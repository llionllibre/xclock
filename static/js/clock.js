/**
 * Xclock - Dashboard, Retro Flip and Digital 7-Segment controller.
 */
const viewDefault = document.getElementById('viewDefault');
const viewFlip = document.getElementById('viewFlip');
const viewDigital = document.getElementById('viewDigital');
const hoursEl = document.getElementById('screenHours');
const minutesEl = document.getElementById('screenMinutes');
const secondsEl = document.getElementById('screenSeconds');
const dateEl = document.getElementById('screenDate');
const ampmElements = ['screenAmpm', 'flipAmpm', 'digitalAmpm'].map(id => document.getElementById(id));

const SEGMENT_MAP = {
  '0': ['a', 'b', 'c', 'd', 'e', 'f'], '1': ['b', 'c'],
  '2': ['a', 'b', 'd', 'e', 'g'], '3': ['a', 'b', 'c', 'd', 'g'],
  '4': ['b', 'c', 'f', 'g'], '5': ['a', 'c', 'd', 'f', 'g'],
  '6': ['a', 'c', 'd', 'e', 'f', 'g'], '7': ['a', 'b', 'c'],
  '8': ['a', 'b', 'c', 'd', 'e', 'f', 'g'], '9': ['a', 'b', 'c', 'd', 'f', 'g']
};
const RANDOM_PALETTE = ['#00ff66', '#00d9ff', '#ff1e38', '#f59e0b', '#ec4899', '#a855f7', '#ff8800', '#00ffcc', '#eab308'];
let currentRandomHex = RANDOM_PALETTE[0];
let currentView = 'default';
let currentTimeFormat = '24h';
let currentDigitalColor = 'green';
let currentTimezone = null;
let clockFormatter = null;
let serverOffset = 0;
let lastHours = null;
let lastMinutes = null;
let sensorData = null;
let apiConnected = null;
let lastServerSuccess = null;
let fetchingData = false;
let settingsRevision = 0;
let refreshPending = false;
let sendingHeartbeat = false;
const displayId = new URLSearchParams(location.search).get('display_id');

function applyView(value) {
  currentView = value;
  viewDefault.classList.toggle('hidden', value !== 'default');
  viewFlip.classList.toggle('hidden', value !== 'flip');
  viewDigital.classList.toggle('hidden', value !== 'digital');
}

function applyDigitalColor(value) {
  currentDigitalColor = value;
  viewDigital.classList.remove('theme-green', 'theme-blue', 'theme-red');
  viewDigital.style.color = '';
  if (value === 'random') viewDigital.style.color = currentRandomHex;
  else viewDigital.classList.add(`theme-${value}`);
}

function applyClockSettings(settings) {
  if (settings.view !== currentView) applyView(settings.view);
  if (settings.digital_color !== currentDigitalColor) applyDigitalColor(settings.digital_color);
  if (settings.time_format !== currentTimeFormat || settings.timezone !== currentTimezone) lastHours = lastMinutes = null;
  currentTimeFormat = settings.time_format;
  if (settings.timezone !== currentTimezone) {
    clockFormatter = new Intl.DateTimeFormat('en-GB', {
      timeZone: settings.timezone, hourCycle: 'h23',
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
    currentTimezone = settings.timezone;
  }
  updateClock();
}

function set7SegmentDigit(svgId, charVal) {
  const activeSegments = SEGMENT_MAP[charVal] || [];
  document.getElementById(svgId).querySelectorAll('.seg').forEach(segment => {
    const active = activeSegments.some(name => segment.classList.contains(`seg-${name}`));
    segment.classList.toggle('seg-on', active);
    segment.classList.toggle('seg-off', !active);
  });
}

function flipUnit(unit, newValue, oldValue) {
  const card = document.getElementById(`flip${unit}Card`);
  const top = document.getElementById(`flip${unit}Top`);
  const bottom = document.getElementById(`flip${unit}Bottom`);
  const frontText = document.getElementById(`flip${unit}FlapFrontText`);
  const backText = document.getElementById(`flip${unit}FlapBackText`);
  top.textContent = newValue;
  backText.textContent = newValue;
  if (oldValue === null) {
    bottom.textContent = frontText.textContent = newValue;
    return;
  }
  bottom.textContent = frontText.textContent = oldValue;
  card.classList.remove('flipping');
  void card.offsetWidth;
  card.classList.add('flipping');
  setTimeout(() => {
    bottom.textContent = frontText.textContent = newValue;
    card.classList.remove('flipping');
  }, 550);
}

function getZonedTime(date) {
  return Object.fromEntries(clockFormatter.formatToParts(date).map(part => [part.type, part.value]));
}

function updateClock() {
  if (!clockFormatter) return;
  const now = getZonedTime(new Date(Date.now() + serverOffset));
  const rawHours = Number(now.hour);
  const hours = String(currentTimeFormat === '12h' ? rawHours % 12 || 12 : rawHours).padStart(2, '0');
  const minutes = now.minute;
  ampmElements.forEach(element => {
    element.textContent = rawHours >= 12 ? 'PM' : 'AM';
    element.classList.toggle('hidden', currentTimeFormat !== '12h');
  });
  hoursEl.textContent = hours;
  minutesEl.textContent = minutes;
  secondsEl.textContent = now.second;
  dateEl.textContent = `${now.day}/${now.month}/${now.year}`;
  if (hours !== lastHours) flipUnit('Hours', hours, lastHours);
  if (minutes !== lastMinutes) flipUnit('Minutes', minutes, lastMinutes);
  lastHours = hours;
  lastMinutes = minutes;
  ['digitH1', 'digitH2', 'digitM1', 'digitM2'].forEach((id, index) => {
    set7SegmentDigit(id, (hours + minutes)[index]);
  });
}

const formatNumber = value => typeof value === 'number' && Number.isFinite(value) ? value.toFixed(1) : '--';

function readingStatus(reading) {
  if (apiConnected === false && reading.status === 'ok') return 'stale';
  return reading.status;
}

function renderUpdated(id, reading) {
  const element = document.getElementById(id);
  if (!reading.updated_at || !currentTimezone) { element.textContent = ''; return; }
  const timestamp = new Date(reading.updated_at);
  const label = timestamp.toLocaleString(Xclock.language, {
    timeZone: currentTimezone, day: '2-digit', month: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
  });
  element.textContent = `${Xclock.t('updated')}: ${label}`;
  element.title = `${timestamp.toISOString()} (${currentTimezone})`;
}

function renderConnection() {
  const key = apiConnected === null ? 'connecting' : apiConnected ? 'server_connected' : 'server_offline';
  const label = document.getElementById('connectionLabel');
  label.removeAttribute('data-i18n');
  label.textContent = Xclock.t(key);
  document.getElementById('connectionStatus').dataset.state = apiConnected === null ? 'connecting' : apiConnected ? 'online' : 'offline';
  const warning = document.getElementById('connectionWarning');
  warning.textContent = Xclock.t(key);
  warning.classList.toggle('hidden', apiConnected !== false);
}

function renderSensors() {
  renderConnection();
  if (!sensorData) return;
  const indoor = sensorData.indoor;
  const outdoor = sensorData.outdoor;
  document.getElementById('indoorTemp').textContent = formatNumber(indoor.temperature);
  document.getElementById('indoorHumidity').textContent = `${formatNumber(indoor.humidity)}%`;
  const indoorStatus = document.getElementById('indoorStatus');
  indoorStatus.removeAttribute('data-i18n');
  indoorStatus.textContent = Xclock.t(readingStatus(indoor));
  indoorStatus.dataset.state = readingStatus(indoor);
  renderUpdated('indoorUpdated', indoor);

  document.getElementById('outdoorTemp').textContent = formatNumber(outdoor.temperature);
  document.getElementById('outdoorCity').textContent = outdoor.city;
  document.getElementById('weatherIcon').textContent = outdoor.icon;
  const condition = document.getElementById('weatherCondition');
  condition.removeAttribute('data-i18n');
  condition.textContent = outdoor.status === 'unavailable' ? Xclock.t('unavailable') :
    outdoor[`condition_${Xclock.language}`] || outdoor.condition || Xclock.t('unknown_condition');
  document.getElementById('weatherMinMax').textContent = `${formatNumber(outdoor.temp_min)}° / ${formatNumber(outdoor.temp_max)}°`;
  const outdoorStatus = document.getElementById('outdoorStatus');
  outdoorStatus.textContent = Xclock.t(readingStatus(outdoor));
  outdoorStatus.dataset.state = readingStatus(outdoor);
  renderUpdated('outdoorUpdated', outdoor);
}

async function fetchSensorData() {
  if (fetchingData) { refreshPending = true; return; }
  fetchingData = true;
  const revision = settingsRevision;
  try {
    const data = await Xclock.requestJSON('/api/data', {}, 25000);
    if (revision !== settingsRevision) return;
    applyClockSettings(data);
    serverOffset = Date.parse(data.server_time) - Date.now();
    if (data.language !== Xclock.language && document.getElementById('settingsModal').classList.contains('hidden')) {
      Xclock.applyLanguage(data.language);
    }
    sensorData = data;
    apiConnected = true;
    lastServerSuccess = performance.now();
    document.body.classList.toggle('night-mode', data.night_mode);
    updateClock();
  } catch (error) {
    if (revision === settingsRevision) apiConnected = false;
    console.warn('[Xclock] Data update failed:', error);
  } finally {
    fetchingData = false;
    renderSensors();
    if (refreshPending) {
      refreshPending = false;
      fetchSensorData();
    }
  }
}

async function sendHeartbeat() {
  if (!displayId || sendingHeartbeat || !clockFormatter) return;
  sendingHeartbeat = true;
  try {
    updateClock();
    await Xclock.requestJSON('/api/display/heartbeat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_id: displayId })
    }, 5000);
  } catch (error) {
    console.warn('[Xclock] Display heartbeat failed:', error);
  } finally {
    sendingHeartbeat = false;
  }
}

document.addEventListener('xclock:settings', event => {
  ++settingsRevision;
  if (sensorData && (sensorData.outdoor.city !== event.detail.city || currentTimezone !== event.detail.timezone)) {
    sensorData = null;
    ['indoorTemp', 'outdoorTemp', 'indoorHumidity', 'weatherMinMax'].forEach(id => {
      document.getElementById(id).textContent = '--';
    });
    document.getElementById('outdoorCity').textContent = event.detail.city;
    ['indoorStatus', 'outdoorStatus', 'weatherCondition'].forEach(id => {
      document.getElementById(id).textContent = Xclock.t('loading');
    });
    ['indoorUpdated', 'outdoorUpdated'].forEach(id => { document.getElementById(id).textContent = ''; });
    document.getElementById('weatherIcon').textContent = '';
  }
  applyClockSettings(event.detail);
  fetchSensorData();
  sendHeartbeat();
});
document.addEventListener('xclock:language', renderSensors);
window.addEventListener('offline', () => { apiConnected = false; renderSensors(); });
window.addEventListener('online', fetchSensorData);

applyDigitalColor(currentDigitalColor);
renderConnection();
setInterval(() => {
  updateClock();
  if (lastServerSuccess !== null && performance.now() - lastServerSuccess > 45000 && apiConnected !== false) {
    apiConnected = false;
    renderSensors();
  }
}, 1000);
setInterval(() => {
  currentRandomHex = RANDOM_PALETTE[Math.floor(Math.random() * RANDOM_PALETTE.length)];
  if (currentDigitalColor === 'random') applyDigitalColor('random');
}, 600000);
setInterval(fetchSensorData, 30000);
setInterval(sendHeartbeat, 15000);
document.addEventListener('DOMContentLoaded', fetchSensorData);
