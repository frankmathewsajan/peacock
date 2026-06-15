import { AppState } from './state.js';
import { UIManager } from './ui.js';

export const Network = {
    ws: null,
    reconnectInterval: 1000,
    maxReconnectInterval: 15000,

    connect() {
        this.ws = new WebSocket(`ws://${location.host}/stream`);
        this.ws.binaryType = "blob";

        this.ws.onopen = () => {
            console.log("[Network] WebSocket connected.");
            this.reconnectInterval = 1000; // Reset backoff
            UIManager.setNetworkStatus(true);
        };

        this.ws.onmessage = async (e) => {
            if (typeof e.data === 'string') {
                try {
                    const data = JSON.parse(e.data);
                    if (data.type === "extracted_text") {
                        UIManager.handleTextExtraction(data.content);
                    }
                } catch(err) { console.error(err); }
                return;
            }

            // Binary data means an image was captured
            AppState.addBlob(e.data);
            UIManager.renderDraftPreviewRow();
            UIManager.refreshDynamicUI();

            if (AppState.pendingExecutionPrompt) {
                const promptToFire = AppState.pendingExecutionPrompt;
                AppState.pendingExecutionPrompt = null;
                UIManager.executeInference(promptToFire);
            }
        };

        this.ws.onclose = () => {
            console.warn("[Network] WebSocket dropped. Reconnecting in", this.reconnectInterval, "ms");
            UIManager.setNetworkStatus(false);
            setTimeout(() => this.connect(), this.reconnectInterval);
            this.reconnectInterval = Math.min(this.reconnectInterval * 1.5, this.maxReconnectInterval);
        };

        this.ws.onerror = (err) => {
            console.error("[Network] WebSocket encountered an error.", err);
            this.ws.close();
        };
    },

    /**
     * Enforces the StreamEvent Pydantic schema
     */
    sendCommand(action, text = "") {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ action, text }));
        } else {
            console.warn("[Network] Command ignored. Engine is disconnected.");
        }
    }
};