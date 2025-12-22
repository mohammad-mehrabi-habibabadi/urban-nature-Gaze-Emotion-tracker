// File: app/static/js/main.js
// Purpose: Interactive Map Logic (Google Maps Style) with Gaze & Mouse Tracking.

const state = {
    sessionId: null,
    participantCode: null,
    currentNeighborhood: null,
    stimulusStartTime: null,
    lastMouseLog: 0,
    cameraPos: 'top' // Default
};

const API_BASE = '/api';

// UI Helper for Camera Selection
window.selectCam = function(pos) {
    state.cameraPos = pos;
    document.querySelectorAll('.cam-option').forEach(el => el.classList.remove('selected'));
    document.querySelector(`.cam-option.${pos}`).classList.add('selected');
};

// --- SVG Icons (Red Pin) ---
const PIN_SVG = `
<svg viewBox="0 0 24 24">
    <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
</svg>`;

// --- Utilities ---

function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
    document.getElementById(screenId).classList.add('active');
    
    // Update Context for Backend (e.g., 'map', 'stimulus_view')
    const contextName = screenId.replace('screen-', '');
    updateBackendContext(contextName);
}

async function apiPost(endpoint, data) {
    try {
        const res = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return res.json();
    } catch (e) {
        console.error("API Post Error:", e);
    }
}

async function apiGet(endpoint) {
    try {
        const res = await fetch(`${API_BASE}${endpoint}`);
        return res.json();
    } catch (e) {
        console.error("API Get Error:", e);
        return [];
    }
}

async function logEvent(eventType, payload) {
    if (!state.sessionId) return;
    apiPost('/events/', { session_id: state.sessionId, event_type: eventType, payload: payload });
}

async function updateBackendContext(contextName, stimulusId = null) {
    if (!state.sessionId) return;
    await apiPost(`/sessions/${state.sessionId}/context`, {
        context: contextName,
        stimulus_id: stimulusId
    });
}

// --- Screen Config for Gaze Tracker (Crucial for Off-Screen Detection) ---
function sendScreenConfig() {
    if (!state.sessionId) return;
    
    const config = {
        screen_w: window.screen.width,
        screen_h: window.screen.height,
        window_w: window.innerWidth,
        window_h: window.innerHeight,
        window_x: window.screenX !== undefined ? window.screenX : window.screenLeft,
        window_y: window.screenY !== undefined ? window.screenY : window.screenTop
    };
    
    apiPost(`/sessions/${state.sessionId}/screen_config`, config);
}

// --- Mouse Tracking ---
document.addEventListener('mousemove', (e) => {
    if (!state.sessionId) return;
    const now = Date.now();
    // Log mouse position every 200ms
    if (now - state.lastMouseLog > 200) {
        logEvent('mouse_move', { 
            x: e.clientX, y: e.clientY,
            screen_width: window.innerWidth, screen_height: window.innerHeight
        });
        state.lastMouseLog = now;
    }
});

// Update screen config on resize
window.addEventListener('resize', () => {
    clearTimeout(window.resizeTimer);
    window.resizeTimer = setTimeout(sendScreenConfig, 500);
});

// --- Map Logic ---

function createPin(x, y, label, onClick) {
    const pin = document.createElement('div');
    pin.className = 'map-pin';
    // Use percentages for responsive positioning
    pin.style.left = `${x}%`;
    pin.style.top = `${y}%`;
    
    pin.innerHTML = `${PIN_SVG}<div class="pin-label">${label}</div>`;
    
    pin.onclick = (e) => {
        e.stopPropagation();
        onClick();
    };
    
    // Hover Tracking for Pins (Hesitation Analysis)
    pin.onmouseenter = () => logEvent('hover_start', { name: label, type: 'map_pin' });
    pin.onmouseleave = () => logEvent('hover_end', { name: label, type: 'map_pin' });
    
    return pin;
}

async function loadMainMap() {
    const neighborhoods = await apiGet('/stimuli/neighborhoods');
    const mapContainer = document.getElementById('map-container');
    
    // Set Main City Map Background
    mapContainer.style.backgroundImage = "url('img/city_map_bg.jpg')";
    mapContainer.innerHTML = ''; 
    
    // Skip Button
    const controls = document.createElement('div');
    controls.className = 'map-controls';
    controls.innerHTML = `<button class="map-btn" onclick="goToRoutes()">Skip to Routes >></button>`;
    mapContainer.appendChild(controls);
    
    // Title
    const titleEl = document.getElementById('map-title');
    if(titleEl) titleEl.innerText = "Select a Neighborhood to Explore";
    
    // Add Pins
    neighborhoods.forEach(n => {
        const pin = createPin(n.map_x, n.map_y, n.name, () => selectNeighborhood(n));
        mapContainer.appendChild(pin);
    });
    
    showScreen('screen-map');
    
    // Important: Update screen config when map loads
    setTimeout(sendScreenConfig, 500);

    // --- Send pin positions for gaze analysis---
    setTimeout(() => {
        const layoutData = [];
        document.querySelectorAll('.map-pin').forEach(el => {
            const rect = el.getBoundingClientRect();
            // Only add pins that have names.
            const label = el.querySelector('.pin-label');
            if (label) {
                layoutData.push({
                    name: label.innerText, 
                    x: rect.left / window.innerWidth,
                    y: rect.top / window.innerHeight,
                    w: rect.width / window.innerWidth,
                    h: rect.height / window.innerHeight
                });
            }
        });
        logEvent('ui_layout', { screen: 'map_overview', elements: layoutData });
    }, 600); 
    // ------------------------------------------------------
}

async function selectNeighborhood(n) {
    state.currentNeighborhood = n;
    logEvent('click', { target: 'neighborhood', id: n.id, name: n.name });
    
    const pois = await apiGet(`/stimuli/neighborhoods/${n.id}/pois`);
    const mapContainer = document.getElementById('map-container');
    
    // Change Background to Neighborhood Map
    if (n.media_path) {
        mapContainer.style.backgroundImage = `url('${n.media_path}')`;
    }
    
    mapContainer.innerHTML = '';
    
    // Back Button
    const controls = document.createElement('div');
    controls.className = 'map-controls';
    controls.innerHTML = `
        <button class="map-btn secondary" onclick="loadMainMap()">< Back to City View</button>
        <div style="padding: 10px; font-weight:bold; color: #333;">Current: ${n.name}</div>
    `;
    mapContainer.appendChild(controls);
    
    const titleEl = document.getElementById('map-title');
    if(titleEl) titleEl.innerText = `Exploring ${n.name}`;
    
    // Add POI Pins
    pois.forEach(p => {
        const pin = createPin(p.map_x, p.map_y, p.name, () => viewStimulus(p));
        mapContainer.appendChild(pin);
    });

    // --- Send POI pin locations ---
    setTimeout(() => {
        const layoutData = [];
        document.querySelectorAll('.map-pin').forEach(el => {
            const rect = el.getBoundingClientRect();
            const label = el.querySelector('.pin-label');
            if (label) {
                layoutData.push({
                    name: label.innerText, 
                    x: rect.left / window.innerWidth,
                    y: rect.top / window.innerHeight,
                    w: rect.width / window.innerWidth,
                    h: rect.height / window.innerHeight
                });
            }
        });
        logEvent('ui_layout', { screen: 'neighborhood_view', elements: layoutData });
    }, 600);
    // --------------------------------------------
}

// --- Stimulus & Routes ---

async function viewStimulus(poi) {
    logEvent('click', { target: 'poi', id: poi.id, name: poi.name });
    updateBackendContext("stimulus_view", poi.id);
    
    const details = await apiGet(`/stimuli/${poi.id}`);
    const container = document.getElementById('stimulus-content');
    const imgSrc = details.media_path ? details.media_path : '';
    
    container.innerHTML = `
        <h2>${details.name}</h2>
        <div class="stimulus-img-container">
            <img src="${imgSrc}" alt="${details.name}" onerror="this.src='https://site'">
        </div>
        <p>${details.description}</p>
        <div style="margin-top: 20px;">
            <button class="map-btn secondary" onclick="closeStimulus()">Back to Map</button>
            <button class="map-btn" onclick="goToRoutes()">Finish Experiment</button>
        </div>
    `;
    
    showScreen('screen-stimulus');
    state.stimulusStartTime = Date.now();
}

function closeStimulus() {
    // Log duration
    if (state.stimulusStartTime) {
        const duration = Date.now() - state.stimulusStartTime;
        logEvent('view_duration', { duration_ms: duration });
    }

    apiPost('/stimuli/stop_viewing', {});
    // Return to map (last state is preserved in UI)
    showScreen('screen-map'); 
}

async function goToRoutes() {
    const routes = await apiGet('/stimuli/routes');
    const container = document.getElementById('route-list');
    container.innerHTML = '';
    
    routes.forEach(r => {
        const card = document.createElement('div');
        card.className = 'route-card';
        const imgSrc = r.media_path ? r.media_path : 'https://site';
        
        card.innerHTML = `
            <img src="${imgSrc}" onerror="this.src='https://site'">
            <h3>${r.name}</h3>
            <p style="padding:0 10px; font-size:0.9rem;">${r.description}</p>
        `;
        
        // Manual hover tracking for route cards
        card.onmouseenter = () => logEvent('hover_start', { name: r.name, type: 'route' });
        card.onmouseleave = () => logEvent('hover_end', { name: r.name, type: 'route' });
        
        card.onclick = () => selectRoute(r);
        container.appendChild(card);
    });
    
    showScreen('screen-route-choice');

    // --- Send element positions to the server for accurate look analysis---
    
    setTimeout(() => {
        const layoutData = [];
        document.querySelectorAll('.route-card').forEach(el => {
            const rect = el.getBoundingClientRect();
            // Convert pixels to normal coordinates (0 to 1)
            layoutData.push({
                name: el.querySelector('h3').innerText, 
                x: rect.left / window.innerWidth,
                y: rect.top / window.innerHeight,
                w: rect.width / window.innerWidth,
                h: rect.height / window.innerHeight
            });
        });
        logEvent('ui_layout', { screen: 'route_choice', elements: layoutData });
    }, 500);
    // -------------------------------------------------------------------
}

async function selectRoute(route) {
    logEvent('route_choice', { route_id: route.id, route_name: route.name });
    await apiPost(`/sessions/${state.sessionId}/stop`);
    
    const summary = document.getElementById('summary-text');
    if(summary) summary.innerHTML = `You chose <b>${route.name}</b>.<br>Thank you for participating!`;
    
    showScreen('screen-final');
    updateBackendContext("finished");
}

// --- Initialization ---

async function startExperiment() {
    const codeInput = document.getElementById('participant-code');
    const code = codeInput ? codeInput.value.trim() : 'anon_' + Date.now();
    
    // Reading the state of a checkbox
    const recordCheckbox = document.getElementById('record-toggle');
    const shouldRecord = recordCheckbox ? recordCheckbox.checked : false;
    
    // Reading monitor size
    const monitorInput = document.getElementById('monitor-size');
    const monitorInches = monitorInput ? parseFloat(monitorInput.value) : 17.3;

    // Send to server
    const res = await apiPost('/sessions/start', { 
        participant_code: code,
        record_video: shouldRecord,
        monitor_inches: monitorInches,
        camera_pos: state.cameraPos 
    });
    
    if (res && res.session_id) {
        state.sessionId = res.session_id;
        state.participantCode = res.participant_code;
        
        // Start by sending screen dimensions for the gaze tracker
        sendScreenConfig();
        
        // Instead of going straight to the map, let's start with the calibration.
        showScreen('screen-calibration');
    }
}

// --- Calibration Logic---
async function runCalibrationSequence() {
    const instruction = document.getElementById('calib-instruction');
    const dot = document.getElementById('calib-dot');
    
    // Resetting the previous calibration
    await apiPost(`/sessions/${state.sessionId}/calibration/reset`, {});

    // Helper function to wait for clicks
    const waitForClick = () => new Promise(resolve => {
        const handler = () => {
            document.removeEventListener('click', handler);
            resolve();
        };
        setTimeout(() => document.addEventListener('click', handler), 200);
    });

    // Helper function to execute a set of points with a special message
    async function runPointSet(points, title, subtext) {
        // Get the page element to change the background color
        const screen = document.getElementById('screen-calibration');
        
        // Step 1: Set the background to white for text readability
        screen.style.background = "#ffffff"; 
        
        instruction.style.display = 'block';
        
        instruction.innerHTML = `
            <h2 style='color: #000000ff; font-size:2em; margin-bottom:15px; text-shadow: 0 0 10px #000;'>${title}</h2>
            <p style='color: #3c00f2ff; font-size:1.4em; font-weight:bold;'>${subtext}</p>
            <p style='color: #0b0000ff; margin-top:30px; font-size:1em;'>(Click anywhere to start)</p>
        `;
        dot.style.display = 'none';
        
        await waitForClick(); // Phase starts with user click
        
        // Step 2: Change the background to absolute black for point contrast
        screen.style.background = "#000000";

        instruction.style.display = 'none';
        dot.style.display = 'block';

        for (const p of points) {
            dot.style.left = `${p.x}%`;
            dot.style.top = `${p.y}%`;
            
            // Waiting for the user to click on the dot
            await waitForClick(); 
            
            // --- Wait for eye fixation (fixes motion crystallization issue)---
            dot.style.background = "#ffffff"; // Visual feedback (whitening of the dot)
            await new Promise(r => setTimeout(r, 500)); // Wait half a second.
            
            // Save point (now that the eye is fixed)
            await apiPost(`/sessions/${state.sessionId}/calibration/point`, {
                x: p.x / 100, 
                y: p.y / 100
            });
            
            // Visual feedback (green flash)
            dot.style.transform = "scale(1.4)";
            dot.style.background = "#00ff00";
            dot.style.boxShadow = "0 0 25px #00ff00";
            await new Promise(r => setTimeout(r, 150));
            dot.style.transform = "scale(1)";
            dot.style.background = "red";
            dot.style.boxShadow = "0 0 15px red";
        }
    }

    // --- Phase 1: Precise eye calibration (fixed head)---
    // This data teaches the model to capture lens and eye errors.
    const pointsPhase1 = [
        {x: 10, y: 10}, {x: 50, y: 10}, {x: 90, y: 10},
        {x: 10, y: 50}, {x: 50, y: 50}, {x: 90, y: 50},
        {x: 10, y: 90}, {x: 50, y: 90}, {x: 90, y: 90}
    ];
    await runPointSet(
        pointsPhase1, 
        "PHASE 1: HEAD STILL", 
        "Keep your head <b>completely still</b>.<br>Move ONLY your eyes to look at the dots then click on it."
    );

    // --- Phase 2: Motor Calibration (Natural)---
    // This data teaches the model to compensate for changes in distance and head angle.
    const pointsPhase2 = [
        {x: 20, y: 20}, {x: 80, y: 20},
        {x: 50, y: 50},
        {x: 20, y: 80}, {x: 80, y: 80}
    ];
    await runPointSet(
        pointsPhase2, 
        "PHASE 2: NATURAL MOVEMENT", 
        "Now relax. Move your <b>head and eyes naturally</b>.<br>You can lean slightly forward or back</b>.look at the dots then click on it."
    );

    // End: Model training
    dot.style.display = 'none';
    instruction.style.display = 'block';
    instruction.innerHTML = "<h2 style='color:white;'>Processing AI Model...</h2>";

    const res = await apiPost(`/sessions/${state.sessionId}/calibration/train`, {});
    
    if(res.status === 'calibrated') {
        alert("Calibration Complete! The AI has learned your movement patterns.");
    } else {
        alert("Calibration warning (low data). Using standard accuracy.");
    }
    
    loadMainMap();
}

function skipCalibration() {
    loadMainMap();
}

document.addEventListener('DOMContentLoaded', () => {
    showScreen('screen-landing');
});
