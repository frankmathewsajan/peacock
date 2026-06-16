import { AppState } from './state.js';
import { API } from './api.js';
import { UI } from './ui.js';
import { Modals } from './modals.js';

document.addEventListener("DOMContentLoaded", async () => {
    console.log("[System] Peacock Engine Architecture Initializing...");

    // 1. Initialize State & Data
    AppState.init();
    await API.loadHistory();
    
    // 2. Initial DOM Paint
    UI.updateTokenTelemetry();
    UI.renderPrompts();
    UI.refreshControls();
    UI.renderHistoryFeed();

    // 3. Initialize Modals
    Modals.initRemote();
    Modals.initConfig();
    Modals.initImagePreview();

    // 4. Bind Core Toggles (Model & Mode)
    const bindToggle = (id, property, val, callback) => {
        document.getElementById(id).addEventListener('click', () => {
            AppState[property] = val;
            callback();
            
            // Fast/Deep UI Update
            ['fast', 'deep'].forEach(tier => {
                document.getElementById(`model-${tier}`).className = AppState.currentModel === tier 
                    ? "flex-1 px-2 py-1.5 text-[11px] font-bold uppercase tracking-wider rounded-md bg-white shadow-sm text-slate-800 transition" 
                    : "flex-1 px-2 py-1.5 text-[11px] font-bold uppercase tracking-wider rounded-md text-slate-400 transition";
            });
            // Single/Batch UI Update
            ['single', 'batch'].forEach(mode => {
                document.getElementById(`mode-${mode}`).className = AppState.currentMode === mode 
                    ? "flex-1 px-2 py-1.5 text-[11px] font-bold uppercase tracking-wider rounded-md bg-white shadow-sm text-slate-800 transition" 
                    : "flex-1 px-2 py-1.5 text-[11px] font-bold uppercase tracking-wider rounded-md text-slate-400 transition";
            });
        });
    };

    bindToggle('model-fast', 'currentModel', 'fast', () => {});
    bindToggle('model-deep', 'currentModel', 'deep', () => {});
    bindToggle('mode-single', 'currentMode', 'single', () => {
        if (AppState.temporaryBlobs.length > 0) {
            AppState.clearBlobs();
            UI.renderDraftGallery();
        }
        UI.refreshControls();
    });
    bindToggle('mode-batch', 'currentMode', 'batch', () => UI.refreshControls());

    // 5. Bind Core Actions
    document.getElementById('peek-btn').addEventListener('click', () => {
        API.sendCommand("CAPTURE"); 
    });

    document.getElementById('capture-btn').addEventListener('click', () => {
        if (AppState.currentMode === 'single') {
            AppState.pendingExecutionPrompt = AppState.autoFirePrompt;
        }
        API.sendCommand("CAPTURE");
    });

    document.getElementById('send-btn').addEventListener('click', () => {
        API.executeInference(AppState.autoFirePrompt);
    });

    document.getElementById('extract-text-btn').addEventListener('click', () => {
        API.sendCommand("EXTRACT_TEXT");
        const btn = document.getElementById('extract-text-btn');
        const oldHtml = btn.innerHTML;
        btn.innerHTML = `<span class="animate-pulse font-bold text-[10px]">WAIT</span>`;
        setTimeout(() => { btn.innerHTML = oldHtml; }, 800);
    });

    // 6. Connect WebSocket
    API.connect();
});