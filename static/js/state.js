/**
 * State Management
 * Isolates data structures from DOM manipulation and network logic.
 */
export const AppState = {
    MAX_TOKENS: 1000000,
    temporaryBlobs: [],
    transactionHistory: [],
    tokenFormat: 'raw',
    currentModel: 'fast',
    currentMode: 'single', 
    pendingExecutionPrompt: null,
    currentModalText: "", 
    isTypingPaused: false,
    autoFirePrompt: localStorage.getItem('auto_prompt') || "Analyze this screen and provide key takeaways.",
    customPrompts: [],
    
    natureEmojis: [
        '🦚', '🌿', '🪴', '🌲', '🌸', 
        '🌻', '🍄', '🦉', '🕊️', '🦆', 
        '🦅', '🦜', '🦊', '🐢', '🦋', 
        '🐝', '🐈', '🐕', '🐅', '🐸'
    ],

    initPrompts() {
        const legacy = JSON.parse(localStorage.getItem('saved_prompts'));
        if (Array.isArray(legacy) && typeof legacy[0] === 'string') {
            this.customPrompts = legacy.map((text, i) => ({ emoji: ['🦚', '🌿', '🦉'][i] || '🦊', text }));
            localStorage.setItem('saved_prompts', JSON.stringify(this.customPrompts));
        } else if (legacy && legacy[0] && legacy[0].emoji) {
            this.customPrompts = legacy;
        } else {
            this.customPrompts = [
                { emoji: '🦚', text: "Summarize this slide concisely" },
                { emoji: '🌿', text: "Extract all text exactly as written" },
                { emoji: '🦉', text: "Explain the core concept" },
                { emoji: '🦊', text: "Provide the primary action item." }
            ];
        }
    },

    addBlob(blob) {
        this.temporaryBlobs.push(blob);
    },

    clearBlobs() {
        this.temporaryBlobs = [];
    },

    removeBlob(index) {
        this.temporaryBlobs.splice(index, 1);
    }
};