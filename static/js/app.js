import { Network } from './network.js';
import { UIManager } from './ui.js';

// Initialize System on DOM Load
document.addEventListener("DOMContentLoaded", () => {
    console.log("[System] Peacock Engine Frontend Initializing...");
    UIManager.init();
    Network.connect();
});