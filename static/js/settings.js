/* Shared settings controller for the clock modal and the standalone page. */
(() => {
  const translations = {
    en: {
      indoor_title: "Living Room (Nest)", outdoor_title_prefix: "Outdoor", humidity_label: "Humidity",
      loading: "Loading...", settings_title: "Xclock Settings", back_to_clock: "Back to clock", close: "Close",
      view_label: "Screen layout", view_dashboard_title: "Dashboard", view_dashboard_desc: "Clock, date, and sensors.",
      view_flip_title: "Retro Flip", view_flip_desc: "Giant mechanical flip cards.",
      view_digital_title: "Digital 7-Seg", view_digital_desc: "7-segment LED display.",
      color_label: "LED segment color", color_green: "Green", color_blue: "Blue", color_red: "Red", color_random: "Random",
      format_label: "Time format", format_24h_title: "24 hours", format_24h_desc: "Example: 18:45",
      format_12h_title: "12 hours (AM / PM)", format_12h_desc: "Example: 06:45 PM",
      city_label: "Outdoor location (city)", city_placeholder: "Search city (e.g. Madrid, London...)",
      city_current: "Current city", city_no_results: "No cities found", city_search_error: "City search failed. Try again.",
      timezone_label: "Clock and night mode timezone",
      night_auto_title: "Automatic night mode", night_auto_desc: "Dim colors during rest hours. Equal start/end disables the schedule.",
      night_start: "Start:", night_end: "End:", night_manual_title: "Enable manual night mode",
      night_manual_desc: "Keep night mode always on.", btn_cancel: "Cancel", btn_save: "Save settings",
      saving: "Saving...", saved: "Settings saved!", save_error: "Could not save settings.",
      settings_read_error: "Could not read settings. Check the server settings file.",
      settings_write_error: "Could not save settings to disk. Check server permissions and free space.",
      invalid_settings: "Invalid settings. Check the selected values.",
      load_error: "Could not load settings.", retry: "Retry", lang_label: "Language",
      connecting: "Connecting...", server_connected: "Server connected", server_offline: "Server offline",
      ok: "Live", stale: "Out of date", unavailable: "No data", disabled: "Disabled",
      updated: "Updated", unknown_condition: "Unknown conditions"
    },
    es: {
      indoor_title: "Salón (Nest)", outdoor_title_prefix: "Exterior", humidity_label: "Humedad",
      loading: "Cargando...", settings_title: "Ajustes de Xclock", back_to_clock: "Ver reloj", close: "Cerrar",
      view_label: "Diseño de pantalla", view_dashboard_title: "Panel", view_dashboard_desc: "Reloj, fecha y sensores.",
      view_flip_title: "Retro Flip", view_flip_desc: "Fichas mecánicas gigantes.",
      view_digital_title: "Digital 7-Seg", view_digital_desc: "Pantalla LED de 7 segmentos.",
      color_label: "Color de los segmentos LED", color_green: "Verde", color_blue: "Azul", color_red: "Rojo", color_random: "Aleatorio",
      format_label: "Formato de hora", format_24h_title: "24 horas", format_24h_desc: "Ejemplo: 18:45",
      format_12h_title: "12 horas (AM / PM)", format_12h_desc: "Ejemplo: 06:45 PM",
      city_label: "Ubicación exterior (ciudad)", city_placeholder: "Buscar ciudad (ej. Madrid, Valencia...)",
      city_current: "Ciudad actual", city_no_results: "No se encontraron ciudades", city_search_error: "Error al buscar ciudades. Inténtalo de nuevo.",
      timezone_label: "Zona horaria del reloj y del modo nocturno",
      night_auto_title: "Modo nocturno automático", night_auto_desc: "Atenúa los colores durante el descanso. Inicio y fin iguales desactivan el horario.",
      night_start: "Inicio:", night_end: "Fin:", night_manual_title: "Activar modo nocturno manual",
      night_manual_desc: "Mantener el modo nocturno siempre encendido.", btn_cancel: "Cancelar", btn_save: "Guardar ajustes",
      saving: "Guardando...", saved: "¡Ajustes guardados!", save_error: "No se pudieron guardar los ajustes.",
      settings_read_error: "No se pudieron leer los ajustes. Revisa el archivo del servidor.",
      settings_write_error: "No se pudieron guardar los ajustes en disco. Revisa permisos y espacio libre.",
      invalid_settings: "Ajustes no válidos. Revisa los valores seleccionados.",
      load_error: "No se pudieron cargar los ajustes.", retry: "Reintentar", lang_label: "Idioma",
      connecting: "Conectando...", server_connected: "Servidor conectado", server_offline: "Servidor sin conexión",
      ok: "Actual", stale: "Datos caducados", unavailable: "Sin datos", disabled: "Desactivado",
      updated: "Actualizado", unknown_condition: "Estado desconocido"
    }
  };
  let language = document.documentElement.lang === 'es' ? 'es' : 'en';
  let currentSettings = null;
  const t = key => translations[language][key];

  function applyLanguage(value) {
    language = value;
    document.documentElement.lang = value;
    document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      el.placeholder = t(el.dataset.i18nPlaceholder);
    });
    document.querySelectorAll('[data-i18n-aria-label]').forEach(el => {
      el.setAttribute('aria-label', t(el.dataset.i18nAriaLabel));
      if (el.classList.contains('btn-open-settings')) el.title = t(el.dataset.i18nAriaLabel);
    });
    if (document.body.classList.contains('settings-page')) document.title = t('settings_title');
    document.dispatchEvent(new CustomEvent('xclock:language'));
  }

  async function requestJSON(url, options = {}, timeout = 10000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(url, { ...options, signal: controller.signal, cache: 'no-store' });
      const data = await response.json();
      if (!response.ok || data.success === false) {
        const error = new Error(data.error || `HTTP ${response.status}`);
        error.code = data.error;
        throw error;
      }
      return data;
    } finally {
      clearTimeout(timer);
    }
  }

  window.Xclock = { t, applyLanguage, requestJSON, get language() { return language; },
    get settings() { return currentSettings; } };

  const form = document.getElementById('settingsForm');
  const fields = document.getElementById('settingsFields');
  const modal = document.getElementById('settingsModal');
  const saveButton = document.getElementById('btnSaveSettings');
  const retryButton = document.getElementById('btnRetrySettings');
  const saveStatus = document.getElementById('saveStatus');
  const cityInput = document.getElementById('citySearchInput');
  const results = document.getElementById('citySearchResults');
  const autoNight = document.getElementById('nightAutoToggle');
  let selectedCity = null;
  let searchSequence = 0;
  let debounceTimer;
  let loading = false;
  let saving = false;

  function showStatus(key, error = false) {
    saveStatus.textContent = key ? t(key) : '';
    saveStatus.classList.toggle('error', error);
  }

  function updateRadioVisuals() {
    fields.querySelectorAll('input[type="radio"]').forEach(radio => {
      radio.closest('label').classList.toggle('selected', radio.checked);
    });
  }

  function updateNightVisibility() {
    document.getElementById('nightHoursRow').classList.toggle('hidden', !autoNight.checked);
    document.getElementById('nightManualRow').classList.toggle('hidden', autoNight.checked);
  }

  function setLocation(city, country, timezone) {
    document.getElementById('currentCityLabel').textContent = `${city}${country ? ', ' + country : ''}`;
    document.getElementById('currentTimezoneLabel').textContent = timezone;
  }

  function populateForm(settings) {
    const values = { languageChoice: settings.language, viewChoice: settings.view,
      digitalColorChoice: settings.digital_color, timeFormatChoice: settings.time_format };
    Object.entries(values).forEach(([name, value]) => {
      fields.querySelectorAll(`input[name="${name}"]`).forEach(radio => { radio.checked = radio.value === value; });
    });
    updateRadioVisuals();
    autoNight.checked = settings.night_mode_auto;
    document.getElementById('nightStartHour').value = settings.night_mode_start_hour;
    document.getElementById('nightEndHour').value = settings.night_mode_end_hour;
    document.getElementById('nightManualToggle').checked = settings.night_mode_manual;
    updateNightVisibility();
    setLocation(settings.city, settings.country, settings.timezone);
    selectedCity = null;
    cityInput.value = '';
    ++searchSequence;
    results.classList.add('hidden');
  }

  function publishSettings(settings) {
    currentSettings = settings;
    applyLanguage(settings.language);
    document.dispatchEvent(new CustomEvent('xclock:settings', { detail: settings }));
  }

  async function loadSettings() {
    if (loading || saving) return;
    loading = true;
    fields.disabled = true;
    saveButton.disabled = true;
    retryButton.classList.add('hidden');
    showStatus('loading');
    try {
      const settings = await requestJSON('/api/settings');
      populateForm(settings);
      publishSettings(settings);
      fields.disabled = false;
      saveButton.disabled = false;
      showStatus('');
    } catch (error) {
      console.error('[Xclock] Settings load failed:', error);
      showStatus(error.code === 'settings_read_error' ? error.code : 'load_error', true);
      retryButton.classList.remove('hidden');
    } finally {
      loading = false;
    }
  }

  ['nightStartHour', 'nightEndHour'].forEach(id => {
    const select = document.getElementById(id);
    for (let hour = 0; hour < 24; hour++) select.add(new Option(`${String(hour).padStart(2, '0')}:00`, hour));
  });
  fields.addEventListener('change', event => {
    updateRadioVisuals();
    if (event.target.name === 'languageChoice') {
      applyLanguage(event.target.value);
      showStatus('');
    }
    updateNightVisibility();
  });

  function showSearchMessage(key) {
    results.replaceChildren();
    const message = document.createElement('div');
    message.className = 'city-result-item';
    message.textContent = t(key);
    results.appendChild(message);
    results.classList.remove('hidden');
  }

  cityInput.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    const sequence = ++searchSequence;
    const query = cityInput.value.trim();
    selectedCity = null;
    if (currentSettings) setLocation(currentSettings.city, currentSettings.country, currentSettings.timezone);
    results.classList.add('hidden');
    if (query.length < 2) return;
    debounceTimer = setTimeout(async () => {
      try {
        const cities = await requestJSON(`/api/cities/search?q=${encodeURIComponent(query)}&lang=${language}`);
        if (sequence !== searchSequence) return;
        if (cities.length === 0) { showSearchMessage('city_no_results'); return; }
        results.replaceChildren();
        cities.forEach(city => {
          const item = document.createElement('button');
          item.type = 'button';
          item.className = 'city-result-item';
          item.textContent = `${city.name}${city.admin1 ? ' (' + city.admin1 + ')' : ''}, ${city.country}`;
          item.addEventListener('click', () => {
            ++searchSequence;
            selectedCity = city;
            setLocation(city.name, city.country, city.timezone);
            cityInput.value = city.name;
            results.classList.add('hidden');
          });
          results.appendChild(item);
        });
        results.classList.remove('hidden');
      } catch (error) {
        console.error('[Xclock] City search failed:', error);
        if (sequence === searchSequence) showSearchMessage('city_search_error');
      }
    }, 350);
  });

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (fields.disabled || saving || !currentSettings) return;
    const choice = name => fields.querySelector(`input[name="${name}"]:checked`).value;
    const payload = {
      language: choice('languageChoice'), view: choice('viewChoice'),
      digital_color: choice('digitalColorChoice'), time_format: choice('timeFormatChoice'),
      night_mode_auto: autoNight.checked,
      night_mode_start_hour: Number(document.getElementById('nightStartHour').value),
      night_mode_end_hour: Number(document.getElementById('nightEndHour').value),
      night_mode_manual: document.getElementById('nightManualToggle').checked
    };
    if (selectedCity) Object.assign(payload, {
      city: selectedCity.name, country: selectedCity.country, latitude: selectedCity.latitude,
      longitude: selectedCity.longitude, timezone: selectedCity.timezone
    });
    saving = true;
    fields.disabled = true;
    saveButton.disabled = true;
    showStatus('saving');
    try {
      const result = await requestJSON('/api/settings', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
      });
      populateForm(result.settings);
      publishSettings(result.settings);
      showStatus('saved');
    } catch (error) {
      console.error('[Xclock] Settings save failed:', error);
      const key = ['settings_read_error', 'settings_write_error', 'invalid_settings'].includes(error.code) ? error.code : 'save_error';
      showStatus(key, true);
    } finally {
      saving = false;
      fields.disabled = false;
      saveButton.disabled = false;
    }
  });

  function closeSettings() {
    if (saving) return;
    ++searchSequence;
    clearTimeout(debounceTimer);
    modal.classList.add('hidden');
    if (currentSettings) applyLanguage(currentSettings.language);
  }
  if (modal) {
    ['btnCloseSettings', 'btnCancelSettings'].forEach(id => document.getElementById(id).addEventListener('click', closeSettings));
    modal.addEventListener('click', event => { if (event.target === modal) closeSettings(); });
    document.querySelectorAll('.btn-open-settings').forEach(button => button.addEventListener('click', () => {
      modal.classList.remove('hidden');
      loadSettings();
    }));
  }
  retryButton.addEventListener('click', loadSettings);
  applyLanguage(language);
  document.addEventListener('DOMContentLoaded', loadSettings);
})();
