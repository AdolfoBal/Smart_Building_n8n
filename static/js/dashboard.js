let autoUpdateTimer = null;
let backgroundUpdateTimer = null;
let isUserInteracting = false;
let interactionTimer = null;
let uiUpdateIntervalMs = 2000;
let baseSpeed = 60;
let isInteractionSpeedActive = false;
let backgroundUpdateIntervalMs = 1000; // Polling veloce in background per catturare cambiamenti da n8n
let debugMode = false; // Modalità debug: azioni senza traccia lock
let simulationPaused = false; // Stato pausa simulazione
let currentLogs = [];
let logsSortState = {
    key: 'timestamp',
    direction: 'desc'
};

// Modal Functions
function openControlPanel() {
    document.getElementById('control-modal').classList.add('show');
}

function closeControlPanel() {
    document.getElementById('control-modal').classList.remove('show');
}

// Debug Mode Toggle
async function toggleDebugMode(checkbox) {
    try {
        const response = await fetch('/api/debug', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: checkbox.checked })
        });
        const data = await response.json();
        if (response.ok) {
            debugMode = data.debug_mode;
            updateDebugToggle(data.debug_mode);
            showToast(data.messaggio, 'success');
        } else {
            checkbox.checked = !checkbox.checked;
            showToast(data.errore || 'Errore toggle debug', 'error');
        }
    } catch (error) {
        checkbox.checked = !checkbox.checked;
        showToast(`Errore: ${error.message}`, 'error');
    }
}

function updateDebugToggle(enabled) {
    debugMode = enabled;
    const toggle = document.getElementById('debug-toggle');
    const status = document.getElementById('debug-status');
    if (toggle) toggle.checked = enabled;
    if (status) {
        status.textContent = enabled ? 'ON' : 'OFF';
        status.style.color = enabled ? '#f59e0b' : 'var(--text-muted)';
    }
}

// Pause Simulation Toggle
async function togglePause() {
    try {
        const response = await fetch('/api/pause', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: '{}'
        });
        const data = await response.json();
        if (response.ok) {
            simulationPaused = data.simulation_paused;
            updatePauseButton(data.simulation_paused);
            showToast(data.messaggio, 'success');
        } else {
            showToast(data.errore || 'Errore toggle pausa', 'error');
        }
    } catch (error) {
        showToast(`Errore: ${error.message}`, 'error');
    }
}

function updatePauseButton(paused) {
    simulationPaused = paused;
    const btn = document.getElementById('pause-btn');
    const icon = document.getElementById('pause-icon');
    const label = document.getElementById('pause-label');
    if (icon) icon.textContent = paused ? '▶️' : '⏸️';
    if (label) label.textContent = paused ? 'Riprendi' : 'Pausa';
    if (btn) {
        btn.classList.toggle('paused', paused);
    }
}

// Close modal when clicking outside
document.addEventListener('click', (e) => {
    const modal = document.getElementById('control-modal');
    if (e.target === modal) {
        closeControlPanel();
    }
});

// Close modal with ESC key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeControlPanel();
    }
});

// Toast Notification System
function showToast(message, type = 'success') {
    // Rimuovi toast precedenti
    const existingToasts = document.querySelectorAll('.toast');
    existingToasts.forEach(t => t.remove());
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icon = type === 'success' ? '✅' : '❌';
    toast.innerHTML = `
        <div class="toast-content">
            <span class="toast-icon">${icon}</span>
            <span>${message}</span>
        </div>
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideInRight 0.4s ease-out reverse';
        setTimeout(() => toast.remove(), 400);
    }, 3000);
}

// Update room data without reload
async function updateRoomData() {
    if (isUserInteracting) return;
    
    try {
        const response = await fetch('/api/dashboard/status');
        const data = await response.json();
        
        if (data.casa) {
            // Update stats bar
            updateStats(data.casa);
            
            // Update each room
            Object.entries(data.casa).forEach(([roomName, roomData]) => {
                updateRoom(roomName, roomData);
            });
            
            // Update timestamps
            if (data.ultimo_update_dati) {
                const timeData = new Date(data.ultimo_update_dati).toLocaleTimeString('it-IT');
                document.getElementById('last-data-update').textContent = timeData;
            }
            
            if (data.ultimo_update_n8n) {
                const timeN8n = new Date(data.ultimo_update_n8n).toLocaleTimeString('it-IT');
                document.getElementById('last-n8n-update').textContent = timeN8n;
            }

            if (data.ora !== undefined && data.minuto !== undefined) {
                updateTimeDisplay(data.ora, data.minuto);
            }
            
            // Aggiorna temperatura esterna dal backend (include stagioni)
            if (data.temperatura_esterna !== undefined) {
                updateExternalTempValue(data.temperatura_esterna);
            }

            if (data.velocita_tempo !== undefined) {
                // Sincronizza solo se NON in rallentamento da interazione
                if (!isInteractionSpeedActive) {
                    baseSpeed = data.velocita_tempo;
                    updateSpeedDisplay(data.velocita_tempo);
                    updateSpeedIndicator(false, 0);
                }
            }

            if (data.n8n_interval_seconds !== undefined) {
                updateN8nUpdateDisplay(data.n8n_interval_seconds);
            }

            if (data.meteo) {
                updateWeatherSelect(data.meteo);
                updateWeatherDisplay(data.meteo);
            }
            
            if (data.giorno_settimana !== undefined) {
                updateDayDisplay(data.giorno_settimana, data.giorno_settimana_idx, data.giorno_numero);
            }
            
            if (data.stagione !== undefined) {
                updateSeasonDisplay(data.stagione, data.stagione_idx);
            }

            // Sincronizza stato debug mode
            if (data.debug_mode !== undefined) {
                updateDebugToggle(data.debug_mode);
            }

            // Sincronizza stato pausa simulazione
            if (data.simulation_paused !== undefined) {
                updatePauseButton(data.simulation_paused);
            }
        }
    } catch (error) {
        console.error('Errore aggiornamento dati:', error);
    }
}

// Toggle presence and notify backend + n8n
let presenzaInProgress = {};
let presenzaUpdateLock = {};

async function togglePresenza(roomName, element) {
    // Previeni chiamate multiple per la stessa stanza
    if (presenzaInProgress[roomName]) {
        return;
    }
    
    presenzaInProgress[roomName] = true;
    presenzaUpdateLock[roomName] = true; // Blocca aggiornamenti automatici
    isUserInteracting = true;
    registerInteraction();
    clearTimeout(autoUpdateTimer);

    const current = element.textContent.trim().toLowerCase() === 'sì';
    const nuovoStato = !current;

    element.classList.add('value-changing');
    
    // Feedback visivo immediato
    element.style.opacity = '0.7';

    try {
        const response = await fetch('/api/presence', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ stanza: roomName, presenza: nuovoStato })
        });

        const data = await response.json();

        if (response.ok) {
            element.textContent = nuovoStato ? 'Sì' : 'No';
            element.style.opacity = '1';
            showToast(data.messaggio || `${nuovoStato ? 'Presenza rilevata' : 'Nessuno presente'} in ${roomName}`, 'success');
        } else {
            element.style.opacity = '1';
            showToast(data.errore || 'Errore invio presenza', 'error');
        }
    } catch (error) {
        element.style.opacity = '1';
        showToast(`Errore di connessione: ${error.message}`, 'error');
    } finally {
        setTimeout(() => {
            element.classList.remove('value-changing');
            isUserInteracting = false;
            presenzaInProgress[roomName] = false;
            startAutoUpdate();
            // Rilascia il lock dopo un breve ritardo
            setTimeout(() => {
                presenzaUpdateLock[roomName] = false;
            }, 800);
        }, 200);
    }
}

// Update statistics
function updateStats(casaData) {
    const rooms = Object.values(casaData);
    
    // Luci attive
    const luciAttive = rooms.filter(r => r.attuatori.luci === 'ON').length;
    updateValue('stat-luci', luciAttive);
    
    // Temperatura media
    const tempMedia = rooms.reduce((sum, r) => sum + r.sensori.temperatura, 0) / rooms.length;
    updateValue('stat-temp', tempMedia.toFixed(1) + '°C');
    
    // Clima attivo (qualsiasi stato != OFF)
    const climaAttivo = rooms.filter(r => r.attuatori.clima && r.attuatori.clima !== 'OFF').length;
    updateValue('stat-clima', climaAttivo);
    
    // Stanze attive
    updateValue('stat-stanze', rooms.length);
}

// Update single room
function updateRoom(roomName, roomData) {
    const roomCard = document.querySelector(`[data-room="${roomName}"]`);
    if (!roomCard) return;
    
    // Update sensors
    const sensors = roomData.sensori;
    updateSensorValue(roomCard, 'temperatura', sensors.temperatura);
    updateSensorValue(roomCard, 'luminosita', sensors.luminosita);
    updateSensorValue(roomCard, 'umidita', sensors.umidita);
    // Non aggiornare presenza se è in corso un'interazione utente
    if (!presenzaUpdateLock[roomName]) {
        updateSensorValue(roomCard, 'presenza', sensors.presenza);
    }
    
    // Update actuators — button tiles
    const actuators = roomData.attuatori;
    Object.entries(actuators).forEach(([name, state]) => {
        if (name === 'clima') {
            // Heat and Cool are separate buttons
            const heatBtn = roomCard.querySelector(`.act-btn-heat[data-attuatore="clima"]`);
            const coolBtn = roomCard.querySelector(`.act-btn-cool[data-attuatore="clima"]`);
            if (heatBtn && !heatBtn.disabled) {
                heatBtn.classList.toggle('active', state === 'HEAT');
            }
            if (coolBtn && !coolBtn.disabled) {
                coolBtn.classList.toggle('active', state === 'COOL');
            }
        } else {
            const btn = roomCard.querySelector(`.act-btn[data-attuatore="${name}"]`);
            if (btn && !btn.disabled) {
                const isActive = (state === 'ON' || state === 'APERTE');
                btn.classList.toggle('active', isActive);
            }
        }
    });
}

// Update sensor value with animation
function updateSensorValue(roomCard, sensorName, newValue) {
    const sensorEl = roomCard.querySelector(`[data-sensor="${sensorName}"]`);
    if (!sensorEl) return;

    let newValueStr = newValue.toString();
    if (sensorName === 'presenza') {
        newValueStr = newValue ? 'Sì' : 'No';
    }

    const currentValue = parseFloat(sensorEl.textContent) || sensorEl.textContent;
    
    if (currentValue != newValueStr) {
        sensorEl.classList.add('value-changing');
        sensorEl.textContent = newValueStr;
        
        setTimeout(() => {
            sensorEl.classList.remove('value-changing');
        }, 300);
    }
}

// Update value with animation
function updateValue(elementId, newValue) {
    const el = document.getElementById(elementId);
    if (!el) return;
    
    const currentValue = el.textContent;
    const newValueStr = newValue.toString();
    
    if (currentValue !== newValueStr) {
        el.classList.add('value-changing');
        el.textContent = newValueStr;
        
        setTimeout(() => {
            el.classList.remove('value-changing');
        }, 500);
    }
}

// Toggle Actuator via button tile
async function toggleActBtn(btn) {
    isUserInteracting = true;
    registerInteraction();
    clearTimeout(autoUpdateTimer);

    const stanza = btn.dataset.room;
    const attuatore = btn.dataset.attuatore;
    const roomCard = btn.closest('.room-card');

    // Determine new state
    let nuovoStato;
    if (attuatore === 'clima') {
        const action = btn.dataset.action; // HEAT or COOL
        // If already active, turn OFF; otherwise activate this mode
        nuovoStato = btn.classList.contains('active') ? 'OFF' : action;
    } else if (attuatore === 'tapparelle' || attuatore === 'finestre') {
        nuovoStato = btn.classList.contains('active') ? 'CHIUSE' : 'APERTE';
    } else {
        nuovoStato = btn.classList.contains('active') ? 'OFF' : 'ON';
    }

    roomCard.classList.add('loading');
    const allBtns = roomCard.querySelectorAll('.act-btn');
    allBtns.forEach(b => b.disabled = true);

    try {
        const response = await fetch(`/api/${stanza}/${attuatore}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ azione: nuovoStato })
        });

        const data = await response.json();

        if (response.ok) {
            showToast(data.messaggio, 'success');
            // Update button states immediately
            if (attuatore === 'clima') {
                const heatBtn = roomCard.querySelector('.act-btn-heat[data-attuatore="clima"]');
                const coolBtn = roomCard.querySelector('.act-btn-cool[data-attuatore="clima"]');
                if (heatBtn) heatBtn.classList.toggle('active', nuovoStato === 'HEAT');
                if (coolBtn) coolBtn.classList.toggle('active', nuovoStato === 'COOL');
            } else {
                const isActive = (nuovoStato === 'ON' || nuovoStato === 'APERTE');
                btn.classList.toggle('active', isActive);
            }
        } else {
            showToast(data.errore || 'Errore durante il controllo', 'error');
        }
    } catch (error) {
        showToast(`Errore di connessione: ${error.message}`, 'error');
    } finally {
        roomCard.classList.remove('loading');
        allBtns.forEach(b => b.disabled = false);

        setTimeout(() => {
            isUserInteracting = false;
            startAutoUpdate();
        }, 1000);
    }
}

// Auto-update System (every 5 seconds)
function startAutoUpdate() {
    clearTimeout(autoUpdateTimer);
    clearTimeout(backgroundUpdateTimer);
    if (!isUserInteracting) {
        autoUpdateTimer = setTimeout(() => {
            updateRoomData();
            startAutoUpdate(); // Schedule next update
        }, uiUpdateIntervalMs);
    }
    // Avvia il polling veloce in background per catturare cambiamenti da n8n
    startBackgroundUpdate();
}

// Background update system - polling veloce per catturare cambiamenti da n8n
function startBackgroundUpdate() {
    clearTimeout(backgroundUpdateTimer);
    backgroundUpdateTimer = setTimeout(() => {
        updateRoomData();
        startBackgroundUpdate(); // Schedule next update
    }, backgroundUpdateIntervalMs);
}

// Time Control
function updateTimeDisplay(hour, minute = 0) {
    const display = document.getElementById('time-display-top');
    const icon = document.getElementById('time-icon-top');
    display.textContent = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
    
    // Update icon based on time
    if (hour >= 6 && hour < 8) {
        icon.textContent = '🌅';  // Alba
    } else if (hour >= 8 && hour < 18) {
        icon.textContent = '🌞';  // Giorno
    } else if (hour >= 18 && hour < 20) {
        icon.textContent = '🌇';  // Tramonto
    } else {
        icon.textContent = '🌙';  // Notte
    }
}

function updateSpeedDisplay(speed) {
    const display = document.getElementById('speed-display');
    if (display) {
        display.textContent = `${speed} min/min`;
    }
    // Aggiorna anche la posizione dello slider se non sta interagendo
    const slider = document.getElementById('speed-slider');
    if (slider && !slider.matches(':active')) {
        slider.value = speed;
    }
}

function updateSpeedIndicator(active, actualSpeed) {
    const indicator = document.getElementById('speed-indicator');
    const actualDisplay = document.getElementById('speed-actual');
    if (indicator) {
        indicator.style.display = active ? 'block' : 'none';
    }
    if (actualDisplay && active) {
        actualDisplay.textContent = actualSpeed;
    }
}

function updateUiUpdateDisplay(seconds) {
    const display = document.getElementById('ui-update-display');
    if (display) {
        display.textContent = `${seconds} s`;
    }
}

function updateN8nUpdateDisplay(seconds) {
    const display = document.getElementById('n8n-update-display');
    if (display) {
        display.textContent = `${seconds} s`;
    }
}

function updateWeatherDisplay(value) {
    const display = document.getElementById('weather-display');
    if (display) {
        display.textContent = value;
    }
}

function updateWeatherSelect(value) {
    const select = document.getElementById('weather-select');
    if (select && select.value !== value) {
        select.value = value;
    }
}

function updateExternalTempValue(temp) {
    const display = document.getElementById('temp-esterna');
    if (display) {
        display.textContent = temp.toFixed(1) + '°C';
    }
}

async function changeTimeSpeed(speed) {
    try {
        const response = await fetch('/api/time-speed', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ velocita: parseInt(speed) })
        });
        
        if (response.ok) {
            const data = await response.json();
            // Non aggiornare slider/display se è un rallentamento da interazione
            if (!isInteractionSpeedActive) {
                updateSpeedDisplay(speed);
            }
            showToast(data.messaggio || `Velocità tempo: ${speed} min/min`, 'success');
        } else {
            const error = await response.json();
            showToast(error.errore || 'Errore cambio velocità', 'error');
        }
    } catch (error) {
        console.error('Errore cambio velocità tempo:', error);
        showToast(`Errore di connessione: ${error.message}`, 'error');
    }
}

async function changeN8nInterval(seconds) {
    try {
        const response = await fetch('/api/n8n-interval', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ seconds: parseInt(seconds) })
        });

        if (response.ok) {
            const data = await response.json();
            updateN8nUpdateDisplay(seconds);
            showToast(data.messaggio || `Intervallo AI Agent: ${seconds}s`, 'success');
        } else {
            const error = await response.json();
            showToast(error.errore || 'Errore cambio intervallo', 'error');
        }
    } catch (error) {
        console.error('Errore cambio intervallo n8n:', error);
        showToast(`Errore di connessione: ${error.message}`, 'error');
    }
}

async function changeWeather(condition) {
    try {
        const response = await fetch('/api/weather', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ condizione: condition })
        });

        if (response.ok) {
            const data = await response.json();
            updateWeatherSelect(condition);
            showToast(data.messaggio || `Meteo cambiato a: ${condition}`, 'success');
            setTimeout(() => updateRoomData(), 300);
        } else {
            const error = await response.json();
            showToast(error.errore || 'Errore nel cambio del meteo', 'error');
        }
    } catch (error) {
        console.error('Errore cambio meteo:', error);
        showToast(`Errore di connessione: ${error.message}`, 'error');
    }
}

async function changeDay(dayIndex) {
    try {
        const response = await fetch('/api/day', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ giorno: parseInt(dayIndex) })
        });

        const data = await response.json();
        if (response.ok) {
            updateDayDisplay(data.giorno_settimana, data.giorno_settimana_idx, data.giorno_numero);
            showToast(data.messaggio || `Giorno impostato a ${data.giorno_settimana}`, 'success');
        } else {
            showToast(data.errore || 'Errore cambio giorno', 'error');
        }
    } catch (error) {
        console.error('Errore cambio giorno:', error);
        showToast(`Errore di connessione: ${error.message}`, 'error');
    }
}

function updateDayDisplay(dayName, dayIndex, dayNumber) {
    const dayDisplay = document.getElementById('day-display');
    const dayNumberDisplay = document.getElementById('day-number');
    const daySelect = document.getElementById('day-select');
    
    if (dayDisplay) dayDisplay.textContent = dayName;
    if (dayNumberDisplay) dayNumberDisplay.textContent = dayNumber || 1;
    if (daySelect && daySelect.value != dayIndex) {
        daySelect.value = dayIndex;
    }
}

async function changeSeason(seasonIndex) {
    try {
        const response = await fetch('/api/season', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ stagione: parseInt(seasonIndex) })
        });

        const data = await response.json();
        if (response.ok) {
            updateSeasonDisplay(data.stagione, data.stagione_idx);
            showToast(data.messaggio || `Stagione impostata a ${data.stagione}`, 'success');
            // Aggiorna temperatura che dipende dalla stagione
            setTimeout(() => updateRoomData(), 300);
        } else {
            showToast(data.errore || 'Errore cambio stagione', 'error');
        }
    } catch (error) {
        console.error('Errore cambio stagione:', error);
        showToast(`Errore di connessione: ${error.message}`, 'error');
    }
}

function updateSeasonDisplay(seasonName, seasonIndex) {
    const seasonDisplay = document.getElementById('season-display');
    const seasonSelect = document.getElementById('season-select');
    
    // Emoji per stagioni
    const seasonEmojis = {
        'Inverno': '❄️',
        'Primavera': '🌸',
        'Estate': '☀️',
        'Autunno': '🍂'
    };
    
    const emoji = seasonEmojis[seasonName] || '🌿';
    
    if (seasonDisplay) seasonDisplay.textContent = `${emoji} ${seasonName}`;
    if (seasonSelect && seasonSelect.value != seasonIndex) {
        seasonSelect.value = seasonIndex;
    }
}

function setInteractionSpeed(active) {
    if (active && !isInteractionSpeedActive) {
        isInteractionSpeedActive = true;
        if (baseSpeed === 0) return;
        const slowed = Math.max(1, Math.floor(baseSpeed / 4));
        changeTimeSpeed(slowed);
        // Display mostra sempre baseSpeed, indicatore mostra la velocità effettiva
        updateSpeedDisplay(baseSpeed);
        updateSpeedIndicator(true, slowed);
    }

    if (!active && isInteractionSpeedActive) {
        isInteractionSpeedActive = false;
        changeTimeSpeed(baseSpeed);
        updateSpeedDisplay(baseSpeed);
        updateSpeedIndicator(false, 0);
    }
}

function registerInteraction() {
    clearTimeout(interactionTimer);
    setInteractionSpeed(true);
    interactionTimer = setTimeout(() => {
        setInteractionSpeed(false);
    }, 2000);
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Initialize time display
    const timeDisplay = document.getElementById('time-display-top');
    const initialHour = parseInt(timeDisplay.getAttribute('data-hour')) || 0;
    const initialMinute = parseInt(timeDisplay.getAttribute('data-minute')) || 0;
    updateTimeDisplay(initialHour, initialMinute);

    // Initialize speed control
    const speedSlider = document.getElementById('speed-slider');
    baseSpeed = parseInt(speedSlider.value) || 0;
    updateSpeedDisplay(speedSlider.value);

    speedSlider.addEventListener('input', (e) => {
        baseSpeed = parseInt(e.target.value) || 0;
        updateSpeedDisplay(e.target.value);
    });

    speedSlider.addEventListener('change', (e) => {
        baseSpeed = parseInt(e.target.value) || 0;
        changeTimeSpeed(e.target.value);
    });

    // Initialize UI update interval control
    const uiUpdateSlider = document.getElementById('ui-update-slider');
    uiUpdateIntervalMs = (parseInt(uiUpdateSlider.value) || 2) * 1000;
    updateUiUpdateDisplay(uiUpdateSlider.value);

    uiUpdateSlider.addEventListener('input', (e) => {
        updateUiUpdateDisplay(e.target.value);
    });

    uiUpdateSlider.addEventListener('change', (e) => {
        uiUpdateIntervalMs = (parseInt(e.target.value) || 2) * 1000;
        startAutoUpdate();
    });

    // Initialize n8n interval control
    const n8nUpdateSlider = document.getElementById('n8n-update-slider');
    updateN8nUpdateDisplay(n8nUpdateSlider.value);

    n8nUpdateSlider.addEventListener('input', (e) => {
        updateN8nUpdateDisplay(e.target.value);
    });

    n8nUpdateSlider.addEventListener('change', (e) => {
        changeN8nInterval(e.target.value);
    });

    // Initialize meteo select
    const weatherSelect = document.getElementById('weather-select');
    weatherSelect.addEventListener('change', (e) => {
        changeWeather(e.target.value);
    });
    // Initialize day control
    const daySelect = document.getElementById('day-select');
    daySelect.addEventListener('change', (e) => {
        changeDay(e.target.value);
    });
    
    // Initialize season control
    const seasonSelect = document.getElementById('season-select');
    seasonSelect.addEventListener('change', (e) => {
        changeSeason(e.target.value);
    });
    
    // Start auto-update
    startAutoUpdate();
    
    // Pause auto-update during mouse interaction
    let mouseTimer;
    document.addEventListener('mousemove', () => {
        clearTimeout(mouseTimer);
        registerInteraction();

        mouseTimer = setTimeout(() => {
            if (!isUserInteracting) {
                startAutoUpdate();
            }
        }, 500);
    });

    document.addEventListener('touchstart', registerInteraction);
    document.addEventListener('keydown', registerInteraction);

    // Make presence tiles clickable
    document.querySelectorAll('.presence-tile').forEach(tile => {
        const roomCard = tile.closest('.room-card');
        if (!roomCard) return;
        const roomName = roomCard.getAttribute('data-room');
        const valueElement = tile.querySelector('[data-sensor="presenza"]');
        
        // Previeni doppi click
        let clickTimeout = null;
        tile.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            if (clickTimeout) return;
            
            clickTimeout = setTimeout(() => {
                clickTimeout = null;
            }, 500);
            
            togglePresenza(roomName, valueElement);
        });
        
        // Supporto touch migliore per mobile
        tile.addEventListener('touchend', (e) => {
            e.preventDefault();
        });
    });
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (e.key === 'r' && e.ctrlKey) {
        e.preventDefault();
        location.reload();
    }
    
    // Force update with 'U' key
    if (e.key === 'u' || e.key === 'U') {
        updateRoomData();
        showToast('Aggiornamento manuale eseguito', 'success');
    }
});

// Handle visibility change (pause when tab is hidden)
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        clearTimeout(autoUpdateTimer);
    } else {
        updateRoomData();
        startAutoUpdate();
    }
});

// ============================================================================
// PREFERENZE UTENTE
// ============================================================================

const ROOM_ICONS = {
    cucina: '🍳', camera: '🛏️', soggiorno: '🛋️',
    bagno: '🚿', garage: '🚗', giardino: '🌳'
};

// Stanze che hanno tapparelle (coerente col modello)
const STANZE_CON_TAPPARELLE = ['cucina', 'camera', 'soggiorno', 'bagno'];
const STANZE_CON_CLIMA = ['cucina', 'camera', 'soggiorno', 'bagno'];
const STANZE_CON_FINESTRE = ['cucina', 'camera', 'soggiorno', 'bagno'];

let preferencesLoaded = false;

function openPreferencesModal() {
    document.getElementById('prefs-modal').classList.add('show');
    loadPreferences();
}

function closePreferencesModal() {
    document.getElementById('prefs-modal').classList.remove('show');
}

async function loadPreferences() {
    try {
        const response = await fetch('/api/preferences');
        const prefs = await response.json();
        populatePreferencesForm(prefs);
        preferencesLoaded = true;
    } catch (error) {
        console.error('Errore caricamento preferenze:', error);
        showToast('Errore caricamento preferenze', 'error');
    }
}

function populatePreferencesForm(prefs) {
    // Note generali
    const noteEl = document.getElementById('pref-global-note');
    if (noteEl) noteEl.value = prefs.note_generali ?? '';

    // Genera le sezioni per ogni stanza
    const container = document.getElementById('prefs-rooms-container');
    container.innerHTML = '';

    const stanze = Object.keys(prefs).filter(k => k !== 'note_generali');
    
    stanze.forEach(stanza => {
        const p = prefs[stanza];
        const icon = ROOM_ICONS[stanza] || '🏠';
        const hasTapparelle = STANZE_CON_TAPPARELLE.includes(stanza);
        const hasClima = STANZE_CON_CLIMA.includes(stanza);
        const hasFinestre = STANZE_CON_FINESTRE.includes(stanza);

        let tapparelleHtml = '';
        if (hasTapparelle) {
            tapparelleHtml = `
                <div class="pref-card">
                    <div class="pref-card-label">🪟 Tapparelle Giorno</div>
                    <select class="pref-select" id="pref-${stanza}-tapp-giorno">
                        <option value="APERTE" ${p.tapparelle_giorno === 'APERTE' ? 'selected' : ''}>APERTE</option>
                        <option value="CHIUSE" ${p.tapparelle_giorno === 'CHIUSE' ? 'selected' : ''}>CHIUSE</option>
                    </select>
                </div>
                <div class="pref-card">
                    <div class="pref-card-label">🌙 Tapparelle Notte</div>
                    <select class="pref-select" id="pref-${stanza}-tapp-notte">
                        <option value="CHIUSE" ${p.tapparelle_notte === 'CHIUSE' ? 'selected' : ''}>CHIUSE</option>
                        <option value="APERTE" ${p.tapparelle_notte === 'APERTE' ? 'selected' : ''}>APERTE</option>
                    </select>
                </div>
                ${hasFinestre ? `
                <div class="pref-card">
                    <div class="pref-card-label">🔒 Blocco Finestre</div>
                    <select class="pref-select" id="pref-${stanza}-blocco-finestre">
                        <option value="auto" ${p.blocco_finestre === 'auto' ? 'selected' : ''}>🤖 Auto</option>
                        <option value="bloccate" ${p.blocco_finestre === 'bloccate' ? 'selected' : ''}>🔒 Bloccate</option>
                    </select>
                </div>` : ''}`;
        }

        const temperaturaHtml = hasClima ? `
                    <div class="pref-card">
                        <div class="pref-card-label">🌡️ Temperatura Ideale</div>
                        <div class="pref-input-row">
                            <input type="number" class="pref-input" id="pref-${stanza}-temp" min="10" max="30" step="0.5" value="${p.temperatura_ideale ?? 22}">
                            <span class="pref-unit">°C</span>
                        </div>
                    </div>` : '';

        const sectionHtml = `
            <div class="pref-section" data-pref-room="${stanza}">
                <div class="pref-section-title">${icon} ${stanza.charAt(0).toUpperCase() + stanza.slice(1)}</div>
                <div class="pref-row">
                    ${temperaturaHtml}
                    <div class="pref-card">
                        <div class="pref-card-label">💡 Luci Ingresso</div>
                        <select class="pref-select" id="pref-${stanza}-luci">
                            <option value="auto" ${p.luci_ingresso === 'auto' ? 'selected' : ''}>🤖 Auto</option>
                            <option value="sempre_on" ${p.luci_ingresso === 'sempre_on' ? 'selected' : ''}>💡 Sempre ON</option>
                            <option value="sempre_off" ${p.luci_ingresso === 'sempre_off' ? 'selected' : ''}>🌑 Sempre OFF</option>
                        </select>
                    </div>
                </div>
                ${hasTapparelle ? `<div class="pref-row pref-row-3">${tapparelleHtml}</div>` : ''}
                <div class="pref-row pref-row-full">
                    <div class="pref-card pref-card-wide">
                        <div class="pref-card-label">📝 Note per questa stanza</div>
                        <textarea class="pref-textarea" id="pref-${stanza}-note" placeholder="Istruzioni specifiche per ${stanza}...">${p.note ?? ''}</textarea>
                    </div>
                </div>
            </div>`;
        
        container.insertAdjacentHTML('beforeend', sectionHtml);
    });
}

function collectPreferencesFromForm() {
    const prefs = {
        note_generali: document.getElementById('pref-global-note')?.value || ''
    };

    // Raccogli per ogni stanza
    const sections = document.querySelectorAll('[data-pref-room]');
    sections.forEach(section => {
        const stanza = section.dataset.prefRoom;
        const roomPrefs = {
            luci_ingresso: document.getElementById(`pref-${stanza}-luci`)?.value || 'auto',
            note: document.getElementById(`pref-${stanza}-note`)?.value || ''
        };

        const tempInput = document.getElementById(`pref-${stanza}-temp`);
        if (tempInput) {
            roomPrefs.temperatura_ideale = parseFloat(tempInput.value) || 22;
        }

        // Tapparelle (solo se presenti)
        const tappGiorno = document.getElementById(`pref-${stanza}-tapp-giorno`);
        const tappNotte = document.getElementById(`pref-${stanza}-tapp-notte`);
        if (tappGiorno) roomPrefs.tapparelle_giorno = tappGiorno.value;
        if (tappNotte) roomPrefs.tapparelle_notte = tappNotte.value;

        // Blocco finestre (solo se presenti)
        const bloccoFinestre = document.getElementById(`pref-${stanza}-blocco-finestre`);
        if (bloccoFinestre) roomPrefs.blocco_finestre = bloccoFinestre.value;

        prefs[stanza] = roomPrefs;
    });

    return prefs;
}

async function saveAllPreferences() {
    const prefs = collectPreferencesFromForm();
    
    try {
        const response = await fetch('/api/preferences', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(prefs)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast('Preferenze salvate con successo', 'success');
            if (data.errori && data.errori.length > 0) {
                showToast(`Attenzione: ${data.errori.join(', ')}`, 'error');
            }
        } else {
            showToast(data.errore || data.errori?.join(', ') || 'Errore salvataggio preferenze', 'error');
        }
    } catch (error) {
        console.error('Errore salvataggio preferenze:', error);
        showToast(`Errore: ${error.message}`, 'error');
    }
}

async function resetPreferences() {
    if (!confirm('⚠️ Vuoi ripristinare tutte le preferenze ai valori di default?')) {
        return;
    }
    
    try {
        const response = await fetch('/api/preferences', { method: 'DELETE' });
        
        if (response.ok) {
            showToast('Preferenze ripristinate ai default', 'success');
            loadPreferences(); // Ricarica il form
        } else {
            showToast('Errore nel ripristino preferenze', 'error');
        }
    } catch (error) {
        console.error('Errore reset preferenze:', error);
        showToast(`Errore: ${error.message}`, 'error');
    }
}

// Close preferences modal handlers
document.addEventListener('click', (e) => {
    if (e.target === document.getElementById('prefs-modal')) {
        closePreferencesModal();
    }
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && document.getElementById('prefs-modal')?.classList.contains('show')) {
        closePreferencesModal();
    }
});

// ============================================================================
// LOGS MODAL FUNCTIONS
// ============================================================================

function openLogsModal() {
    const modal = document.getElementById('logs-modal');
    modal.classList.add('show');
    loadLogs();
}

function closeLogsModal() {
    const modal = document.getElementById('logs-modal');
    modal.classList.remove('show');
}

// Close logs modal when clicking outside
document.addEventListener('click', (e) => {
    const modal = document.getElementById('logs-modal');
    const logsBtn = document.querySelector('.logs-btn');
    if (e.target === modal) {
        closeLogsModal();
    }
});

async function loadLogs() {
    const agentFilter = document.getElementById('logs-agent-filter')?.value || '';
    const dateFilter = document.getElementById('logs-date-filter')?.value || '';
    
    try {
        let url = '/api/logs/agent';
        const params = new URLSearchParams();
        
        if (agentFilter) params.append('agent', agentFilter);
        if (dateFilter) params.append('date', dateFilter);
        
        if (params.toString()) {
            url += '?' + params.toString();
        }
        
        const response = await fetch(url);
        const data = await response.json();

        currentLogs = data.logs || [];
        displayLogs(currentLogs);
        
        // Aggiorna il conteggio
        const count = data.count || 0;
        const countNode = document.getElementById('logs-count');
        if (countNode) {
            countNode.textContent = `${count} record${count !== 1 ? 's' : ''}`;
        }
    } catch (error) {
        console.error('Errore caricamento log:', error);
        const tbody = document.getElementById('logs-tbody');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color: var(--accent-red);">❌ Errore caricamento log</td></tr>';
        }
    }
}

function displayLogs(logs) {
    const tbody = document.getElementById('logs-tbody');
    if (!tbody) return;
    
    if (!logs || logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color: var(--text-muted);">Nessun log trovato</td></tr>';
        return;
    }
    
    const sortedLogs = sortLogs(logs);
    
    // Store snapshots for JSON viewer (indexed by log position)
    const _logSnapshots = [];
    const _logPayloads = [];
    
    tbody.innerHTML = sortedLogs.map((log, idx) => {
        const timestamp = formatTimestamp(log.ts_sim);
        const giorno_numero = log.giorno_numero || 'N/A';
        const giorno_nome = log.giorno_nome || '';
        const agent = log.agent_id || 'unknown';
        const action = log.action || 'unknown';
        const rawPayload = log.payload || {};
        const hasSnapshot = rawPayload.status_snapshot != null;
        
        // Per log con snapshot, mostra payload senza lo snapshot inline
        let displayPayload;
        let snapshotBtn = '';

        const payloadIdx = _logPayloads.length;
        _logPayloads.push({
            data: rawPayload,
            agent: agent,
            context: `${giorno_nome} #${giorno_numero} ${timestamp}`
        });
        const payloadBtn = `<button class="json-view-btn" onclick="_openPayloadByIdx(${payloadIdx})" title="Visualizza payload completo">🧾 Payload</button>`;

        if (hasSnapshot) {
            const { status_snapshot, ...rest } = rawPayload;
            displayPayload = formatPayload(rest);
            // Salva snapshot nell'array e referenzia per indice
            const snapIdx = _logSnapshots.length;
            _logSnapshots.push({
                data: status_snapshot,
                agent: agent,
                context: `${giorno_nome} #${giorno_numero} ${timestamp}`
            });
            snapshotBtn = `<button class="json-view-btn" onclick="_openSnapshotByIdx(${snapIdx})" title="Visualizza snapshot inviato">📄 Snapshot</button>`;
        } else {
            displayPayload = formatPayload(rawPayload);
        }
        
        const giorno_display = giorno_nome ? `#${giorno_numero} - ${giorno_nome} ${timestamp}` : timestamp;
        
        return `
            <tr>
                <td class="logs-cell-timestamp"><span class="log-timestamp">${giorno_display}</span></td>
                <td class="logs-cell-agent"><span class="log-agent">${escapeHtml(agent)}</span></td>
                <td class="logs-cell-action"><span class="log-action">${escapeHtml(action)}</span></td>
                <td class="logs-cell-payload">
                    <div class="log-payload">${displayPayload}</div>
                    <div class="logs-payload-actions">${payloadBtn}${snapshotBtn}</div>
                </td>
                <td class="logs-cell-tools"><button class="log-delete-btn" onclick="deleteLog('${log.ts_sim}', '${escapeHtml(agent)}', ${log.giorno_numero}, '${escapeHtml(giorno_nome)}', event)" title="Elimina questo log">🗑️</button></td>
            </tr>
        `;
    }).join('');
    
    // Esponi gli snapshot globalmente per accesso dall'onclick
    window._logSnapshots = _logSnapshots;
    window._logPayloads = _logPayloads;
}

function sortLogs(logs) {
    const directionFactor = logsSortState.direction === 'asc' ? 1 : -1;
    const sorted = [...logs].sort((left, right) => {
        const leftValue = getLogSortValue(left, logsSortState.key);
        const rightValue = getLogSortValue(right, logsSortState.key);

        if (typeof leftValue === 'number' && typeof rightValue === 'number') {
            return (leftValue - rightValue) * directionFactor;
        }

        const textLeft = String(leftValue ?? '').toLowerCase();
        const textRight = String(rightValue ?? '').toLowerCase();
        const cmp = textLeft.localeCompare(textRight, 'it', { numeric: true, sensitivity: 'base' });
        return cmp * directionFactor;
    });

    return sorted;
}

function getLogSortValue(log, key) {
    if (key === 'timestamp') {
        const ts = String(log.ts_sim || '');

        // 1) Se è un datetime ISO parseabile, usa epoch ms (ordinamento affidabile)
        const parsedDate = new Date(ts);
        if (!Number.isNaN(parsedDate.getTime())) {
            return parsedDate.getTime();
        }

        // 2) Se è un orario HH:MM:SS, combina con giorno_numero simulato
        const dayRaw = Number(log.giorno_numero);
        const dayNumber = Number.isFinite(dayRaw) ? dayRaw : 0;
        const parts = ts.match(/(\d{2}):(\d{2}):(\d{2})/);
        if (parts) {
            const seconds = (Number(parts[1]) * 3600) + (Number(parts[2]) * 60) + Number(parts[3]);
            return (dayNumber * 86400) + seconds;
        }

        // 3) Fallback stabile
        return 0;
    }

    if (key === 'agent') return log.agent_id || '';
    if (key === 'action') return log.action || '';
    if (key === 'payload') return JSON.stringify(log.payload || {});
    return '';
}

function updateLogsSortIndicators() {
    const buttons = document.querySelectorAll('.logs-sort-btn');
    buttons.forEach((button) => {
        const key = button.dataset.sortKey;
        const indicator = button.querySelector('.logs-sort-indicator');
        const isActive = key === logsSortState.key;

        button.classList.toggle('is-active', isActive);
        if (!indicator) return;

        if (!isActive) {
            indicator.textContent = '↕';
        } else {
            indicator.textContent = logsSortState.direction === 'asc' ? '↑' : '↓';
        }
    });
}

function initLogsSorting() {
    const buttons = document.querySelectorAll('.logs-sort-btn');
    buttons.forEach((button) => {
        button.addEventListener('click', () => {
            const key = button.dataset.sortKey;
            if (!key) return;

            if (logsSortState.key === key) {
                logsSortState.direction = logsSortState.direction === 'asc' ? 'desc' : 'asc';
            } else {
                logsSortState.key = key;
                const defaultDirection = button.dataset.sortDefault || 'asc';
                logsSortState.direction = defaultDirection;
            }

            updateLogsSortIndicators();
            displayLogs(currentLogs);
        });
    });

    updateLogsSortIndicators();
}

function formatTimestamp(isoString) {
    try {
        // Se è già nel formato HH:MM:SS, restituiscilo direttamente
        if (isoString && isoString.match(/^\d{2}:\d{2}:\d{2}$/)) {
            return isoString;
        }
        
        // Altrimenti parsalo come datetime ISO
        const date = new Date(isoString);
        if (isNaN(date.getTime())) {
            return isoString;
        }
        
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        const seconds = String(date.getSeconds()).padStart(2, '0');
        return `${hours}:${minutes}:${seconds}`;
    } catch (e) {
        return isoString;
    }
}

function formatPayload(payload) {
    try {
        const jsonStr = JSON.stringify(payload, null, 2);
        // Escape HTML e highligh chiavi
        return jsonStr
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"([^"]+)":/g, '<span style="color: var(--accent-blue);">"$1":</span>')
            .replace(/: "([^"]*)"/g, ': <span style="color: var(--accent-green);">"$1"</span>')
            .replace(/: (\d+),?/g, ': <span style="color: var(--accent-orange);">$1</span>')
            .replace(/: (true|false),?/g, ': <span style="color: var(--accent-purple);">$1</span>');
    } catch (e) {
        return JSON.stringify(payload);
    }
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// ============================================================================
// JSON VIEWER MODAL
// ============================================================================

let _currentJsonData = null;

function _openSnapshotByIdx(idx) {
    const snapshots = window._logSnapshots || [];
    if (idx >= 0 && idx < snapshots.length) {
        const snap = snapshots[idx];
        openJsonViewer(snap.data, snap.agent, snap.context);
    }
}

function _openPayloadByIdx(idx) {
    const payloads = window._logPayloads || [];
    if (idx >= 0 && idx < payloads.length) {
        const entry = payloads[idx];
        openJsonViewer(entry.data, entry.agent, `${entry.context} · payload`);
    }
}

function openJsonViewer(snapshotData, agentName, contextInfo) {
    _currentJsonData = typeof snapshotData === 'string' ? JSON.parse(snapshotData) : snapshotData;
    
    const modal = document.getElementById('json-viewer-modal');
    const title = document.getElementById('json-viewer-title');
    const meta = document.getElementById('json-viewer-meta');
    const content = document.getElementById('json-viewer-content');
    
    title.textContent = `JSON Snapshot — ${agentName}`;
    meta.innerHTML = `<span>📅 ${escapeHtml(contextInfo)}</span><span>🤖 Agent: <strong>${escapeHtml(agentName)}</strong></span>`;
    
    // Formatta e syntax-highlight il JSON
    const formatted = JSON.stringify(_currentJsonData, null, 2);
    content.innerHTML = syntaxHighlightJson(formatted);
    
    modal.classList.add('show');
}

function closeJsonViewer() {
    document.getElementById('json-viewer-modal').classList.remove('show');
    _currentJsonData = null;
}

function copyJsonToClipboard() {
    if (!_currentJsonData) return;
    const text = JSON.stringify(_currentJsonData, null, 2);
    navigator.clipboard.writeText(text).then(() => {
        showToast('✅ JSON copiato negli appunti', 'success');
    }).catch(() => {
        showToast('❌ Errore copia', 'error');
    });
}

function syntaxHighlightJson(json) {
    return json
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/("[^"]+")\s*:/g, '<span class="json-key">$1</span>:')
        .replace(/:\s*("[^"]*")/g, ': <span class="json-string">$1</span>')
        .replace(/:\s*(\d+\.?\d*)/g, ': <span class="json-number">$1</span>')
        .replace(/:\s*(true|false)/g, ': <span class="json-bool">$1</span>')
        .replace(/:\s*(null)/g, ': <span class="json-null">$1</span>');
}

// Chiudi JSON viewer cliccando fuori o con ESC
document.addEventListener('click', (e) => {
    if (e.target === document.getElementById('json-viewer-modal')) {
        closeJsonViewer();
    }
});
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && document.getElementById('json-viewer-modal')?.classList.contains('show')) {
        closeJsonViewer();
    }
});

// Event listeners per i filtri dei log
document.addEventListener('DOMContentLoaded', () => {
    const agentInput = document.getElementById('logs-agent-filter');
    const dateInput = document.getElementById('logs-date-filter');
    
    if (agentInput) {
        agentInput.addEventListener('keyup', () => {
            loadLogs();
        });
    }
    
    if (dateInput) {
        dateInput.addEventListener('change', () => {
            loadLogs();
        });
    }

    initLogsSorting();
});

async function resetLogs() {
    if (!confirm('⚠️ Eliminerai TUTTI i log degli agenti. Vuoi continuare?')) {
        return;
    }
    
    try {
        const response = await fetch('/api/logs/agent', {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showToast('✅ Log eliminati', 'success');
            loadLogs();
        } else {
            showToast('❌ Errore nell\'eliminazione', 'error');
        }
    } catch (error) {
        console.error('Errore reset log:', error);
        showToast('❌ Errore reset log', 'error');
    }
}

async function deleteLog(timestamp, agent, giornoNumero, giornoNome, event) {
    // Previeni il click di propagarsi
    event.preventDefault();
    event.stopPropagation();
    
    if (!confirm(`🗑️ Elimini questo log?\n${timestamp} - ${agent}`)) {
        return;
    }
    
    try {
        const params = new URLSearchParams({
            ts_sim: timestamp,
            agent_id: agent,
            giorno_numero: giornoNumero,
            giorno_nome: giornoNome
        });
        
        const response = await fetch(`/api/logs/agent/delete?${params.toString()}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showToast('✅ Log eliminato', 'success');
            loadLogs();
        } else {
            showToast('❌ Errore nell\'eliminazione', 'error');
        }
    } catch (error) {
        console.error('Errore eliminazione log:', error);
        showToast('❌ Errore eliminazione log', 'error');
    }
}

