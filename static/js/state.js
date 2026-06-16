export const AppState = {
    MAX_TOKENS: 1000000,
    temporaryBlobs: [],
    transactionHistory: [],
    currentModel: 'fast',
    currentMode: 'single', 
    pendingExecutionPrompt: null,
    
    autoFirePrompt: localStorage.getItem('auto_prompt') || "Analyze this screen and provide key takeaways.",
    customPrompts: [],
    
    natureEmojis: [
        '🦚', '🌿', '🪴', '🌲', '🌸', '🌻', '🍄', '🦉', '🕊️', '🦆', 
        '🦅', '🦜', '🦊', '🐢', '🦋', '🐝', '🐈', '🐕', '🐅', '🐸'
    ],

    init() {
        const legacy = JSON.parse(localStorage.getItem('saved_prompts'));
        if (legacy && legacy[0] && legacy[0].emoji) {
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

    saveConfig(autoPrompt, promptsArray) {
        this.autoFirePrompt = autoPrompt || "Analyze this screen and provide key takeaways.";
        localStorage.setItem('auto_prompt', this.autoFirePrompt);
        this.customPrompts = promptsArray;
        localStorage.setItem('saved_prompts', JSON.stringify(this.customPrompts));
    },

    addBlob(blob) { this.temporaryBlobs.push(blob); },
    clearBlobs() { this.temporaryBlobs = []; },
    removeBlob(index) { this.temporaryBlobs.splice(index, 1); }
};