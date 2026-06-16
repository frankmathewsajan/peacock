import { AppState } from './state.js';
import { UI } from './ui.js';

const store = localforage.createInstance({ name: 'stealth_history_db' });

export const API = {
    ws: null,

    connect() {
        this.ws = new WebSocket(`ws://${location.host}/stream`);
        this.ws.binaryType = "blob";

        this.ws.onopen = () => {
            UI.setNetworkStatus(true);
            this.sendCommand("SET_CONFIG", JSON.stringify({
                auto_prompt: AppState.autoFirePrompt,
                presets: AppState.customPrompts
            }));
        }
        this.ws.onclose = () => {
            UI.setNetworkStatus(false);
            setTimeout(() => this.connect(), 1500); 
        };

        this.ws.onmessage = async (e) => {
            if (typeof e.data === 'string') {
                try {
                    const data = JSON.parse(e.data);
                    if (data.type === "extracted_text") {
                        this.saveToHistory("Screen Text Extraction", "Clipboard", [], data.content);
                    }
                } catch(err) {}
                return;
            }

            AppState.addBlob(e.data);
            UI.renderDraftGallery();
            UI.refreshControls();

            // Auto-fire if in Single Mode and a prompt was triggered
            if (AppState.currentMode === 'single' && AppState.pendingExecutionPrompt) {
                const prompt = AppState.pendingExecutionPrompt;
                AppState.pendingExecutionPrompt = null;
                this.executeInference(prompt);
            }
        };
    },

    sendCommand(action, text = "") {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ action, text }));
        }
    },

    async executeInference(queryText) {
        if (!queryText && AppState.temporaryBlobs.length === 0) return;
        
        UI.setLoadingState(true);

        try {
            const res = await fetch("/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ 
                    message: queryText,
                    model_tier: AppState.currentModel
                })
            });
            
            const data = await res.json();
            localStorage.setItem('token_tracker', data.total_tokens);
            UI.updateTokenTelemetry();

            await this.saveToHistory(queryText, AppState.currentModel, [...AppState.temporaryBlobs], data.response);
            
            AppState.clearBlobs();
            UI.renderDraftGallery();
            
        } catch (error) {
            alert("Backend communication failed.");
        } finally {
            UI.setLoadingState(false);
        }
    },

    async saveToHistory(prompt, model, images, response) {
        const record = { id: Date.now(), prompt, model, images, response };
        AppState.transactionHistory.unshift(record);
        await store.setItem('history_stack', AppState.transactionHistory);
        UI.renderHistoryFeed();
    },

    async loadHistory() {
        AppState.transactionHistory = await store.getItem('history_stack') || [];
    }
};