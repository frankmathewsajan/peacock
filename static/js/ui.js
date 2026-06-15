import { AppState } from './state.js';
import { Network } from './network.js';

const store = localforage.createInstance({ name: 'stealth_history_db' });

export const UIManager = {
    async init() {
        AppState.initPrompts();
        this.bindEvents();
        
        try {
            const res = await fetch("/tokens");
            const data = await res.json();
            localStorage.setItem('token_tracker', data.total_tokens || data.total_used);
        } catch(e) { console.error("Could not sync tokens", e); }

        AppState.transactionHistory = await store.getItem('history_stack') || [];
        this.renderPrompts();
        this.updateTokenTelemetry();
        this.renderHistoryFeed();
        this.refreshDynamicUI();
    },

    setNetworkStatus(isConnected) {
        const indicator = document.getElementById('network-status');
        if (isConnected) {
            indicator.classList.replace('bg-red-500', 'bg-emerald-500');
        } else {
            indicator.classList.replace('bg-emerald-500', 'bg-red-500');
        }
    },

    bindEvents() {
        // Core Capture Controls
        document.getElementById('capture-btn').addEventListener('click', () => {
            if (AppState.currentMode === 'single') {
                AppState.pendingExecutionPrompt = AppState.autoFirePrompt;
            }
            Network.sendCommand("CAPTURE");
        });

        document.getElementById('extract-text-btn').addEventListener('click', () => {
            Network.sendCommand("EXTRACT_TEXT");
            const btn = document.getElementById('extract-text-btn');
            const oldHtml = btn.innerHTML;
            btn.innerHTML = `<span class="animate-pulse font-bold text-[10px]">WAIT</span>`;
            setTimeout(() => { btn.innerHTML = oldHtml; }, 800);
        });

        document.getElementById('send-btn').addEventListener('click', () => {
            if (AppState.temporaryBlobs.length > 0) {
                this.executeInference(AppState.autoFirePrompt);
            }
        });

        // Mode Toggles
        document.getElementById('model-fast').addEventListener('click', () => this.setModel('fast'));
        document.getElementById('model-deep').addEventListener('click', () => this.setModel('deep'));
        document.getElementById('mode-single').addEventListener('click', () => this.setMode('single'));
        document.getElementById('mode-batch').addEventListener('click', () => this.setMode('batch'));

        // Remote Controls
        document.getElementById('open-remote-btn').addEventListener('click', () => {
            document.getElementById('remote-modal').classList.remove('opacity-0', 'pointer-events-none');
            document.getElementById('remote-text').value = '';
            document.getElementById('remote-text').focus();
            document.getElementById('injection-controls').classList.remove('hidden');
            document.getElementById('active-type-controls').classList.add('hidden');
        });

        document.getElementById('close-remote-btn').addEventListener('click', () => {
            document.getElementById('remote-modal').classList.add('opacity-0', 'pointer-events-none');
        });

        document.getElementById('remote-type-btn').addEventListener('click', () => {
            const txt = document.getElementById('remote-text').value;
            if (txt) {
                Network.sendCommand("TYPE", txt);
                document.getElementById('injection-controls').classList.add('hidden');
                document.getElementById('active-type-controls').classList.remove('hidden');
            }
        });
        
        document.getElementById('remote-paste-btn').addEventListener('click', () => {
            const txt = document.getElementById('remote-text').value;
            if (txt) {
                Network.sendCommand("PASTE", txt);
                document.getElementById('remote-modal').classList.add('opacity-0', 'pointer-events-none');
            }
        });

        document.getElementById('stop-type-btn').addEventListener('click', () => {
            Network.sendCommand("STOP_TYPE");
            document.getElementById('remote-modal').classList.add('opacity-0', 'pointer-events-none');
        });
    },

    setModel(target) {
        AppState.currentModel = target;
        const activeClass = "flex-1 px-2 py-1.5 text-[11px] font-bold uppercase tracking-wider rounded-md bg-white shadow-sm text-slate-800 transition";
        const inactiveClass = "flex-1 px-2 py-1.5 text-[11px] font-bold uppercase tracking-wider rounded-md text-slate-400 transition hover:text-slate-600";
        document.getElementById('model-fast').className = target === 'fast' ? activeClass : inactiveClass;
        document.getElementById('model-deep').className = target === 'deep' ? activeClass : inactiveClass;
    },

    setMode(target) {
        AppState.currentMode = target;
        const activeClass = "flex-1 px-2 py-1.5 text-[11px] font-bold uppercase tracking-wider rounded-md bg-white shadow-sm text-slate-800 transition";
        const inactiveClass = "flex-1 px-2 py-1.5 text-[11px] font-bold uppercase tracking-wider rounded-md text-slate-400 transition hover:text-slate-600";
        document.getElementById('mode-single').className = target === 'single' ? activeClass : inactiveClass;
        document.getElementById('mode-batch').className = target === 'batch' ? activeClass : inactiveClass;
        
        if (target === 'single' && AppState.temporaryBlobs.length > 0) {
            AppState.clearBlobs();
            this.renderDraftPreviewRow();
        }
        this.refreshDynamicUI();
    },

    refreshDynamicUI() {
        const sendBtn = document.getElementById('send-btn');
        const captureBtn = document.getElementById('capture-btn');
        const captureText = document.getElementById('capture-text');

        if (AppState.currentMode === 'single') {
            sendBtn.classList.add('hidden');
            captureBtn.className = "flex-1 h-14 rounded-xl bg-slate-900 text-white text-base font-semibold active:scale-[0.98] transition flex items-center justify-center gap-2 shadow-md";
            captureText.innerText = "Capture & Analyze";
        } else {
            if (AppState.temporaryBlobs.length > 0) {
                sendBtn.classList.remove('hidden');
                captureBtn.className = "flex-1 h-14 rounded-xl bg-slate-100 text-slate-700 text-base font-semibold active:scale-[0.98] transition flex items-center justify-center gap-2 shadow-md border border-slate-200";
                captureText.innerText = "Add Frame";
            } else {
                sendBtn.classList.add('hidden');
                captureBtn.className = "flex-1 h-14 rounded-xl bg-slate-900 text-white text-base font-semibold active:scale-[0.98] transition flex items-center justify-center gap-2 shadow-md";
                captureText.innerText = "Start Batch Capture";
            }
        }
    },

    renderPrompts() {
        const container = document.getElementById('prompts-container');
        container.innerHTML = '';
        AppState.customPrompts.forEach(p => {
            if (!p.text.trim()) return;
            const btn = document.createElement('button');
            btn.title = p.text; 
            btn.className = "flex-1 h-11 rounded-xl border border-slate-200 bg-white text-base active:bg-slate-100 shadow-sm transition active:scale-95 flex items-center justify-center";
            btn.innerText = p.emoji;
            btn.addEventListener('click', () => {
                if (AppState.currentMode === 'single') {
                    AppState.pendingExecutionPrompt = p.text;
                    Network.sendCommand("CAPTURE");
                } else if (AppState.temporaryBlobs.length > 0) {
                    this.executeInference(p.text);
                }
            });
            container.appendChild(btn);
        });
    },

    renderDraftPreviewRow() {
        const gallery = document.getElementById("draft-gallery");
        gallery.innerHTML = '';
        if (AppState.temporaryBlobs.length === 0) {
            gallery.classList.add('hidden');
            return;
        }
        gallery.classList.remove('hidden');
        AppState.temporaryBlobs.forEach((blob, index) => {
            const url = URL.createObjectURL(blob);
            const wrapper = document.createElement('div');
            wrapper.className = "relative h-14 w-20 shrink-0 border border-slate-200 rounded-lg overflow-hidden bg-slate-100";
            
            const img = document.createElement('img');
            img.src = url;
            img.className = "h-full w-full object-cover";
            
            const delBtn = document.createElement('button');
            delBtn.className = "absolute top-0.5 right-0.5 bg-black/50 text-white rounded-full p-0.5 hover:bg-red-500 transition";
            delBtn.innerHTML = `<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`;
            delBtn.onclick = () => {
                AppState.removeBlob(index);
                this.renderDraftPreviewRow();
                this.refreshDynamicUI();
            };
            
            wrapper.appendChild(img);
            wrapper.appendChild(delBtn);
            gallery.appendChild(wrapper);
        });
    },

    async executeInference(queryText) {
        if (!queryText && AppState.temporaryBlobs.length === 0) return;
        
        // Prevent multiple triggers
        document.getElementById('capture-btn').disabled = true;
        document.getElementById('send-btn').disabled = true;
        
        const feed = document.getElementById('feed');
        const skel = document.createElement('div');
        skel.id = "skeleton-loader";
        skel.className = "bg-white border border-slate-200 rounded-xl p-3.5 shadow-sm flex flex-col gap-3 animate-pulse";
        skel.innerHTML = `<div class="h-8 bg-slate-100 rounded w-full"></div>`;
        feed.prepend(skel);
        feed.scrollTo({ top: 0, behavior: 'smooth' });

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
            this.updateTokenTelemetry();

            const contextRecord = {
                id: Date.now(),
                prompt: queryText,
                model: AppState.currentModel,
                images: [...AppState.temporaryBlobs],
                response: data.response
            };
            
            AppState.transactionHistory.unshift(contextRecord);
            await store.setItem('history_stack', AppState.transactionHistory);
            
            AppState.clearBlobs();
            this.renderDraftPreviewRow();
            
        } catch (error) {
            console.error("Network fault:", error);
            alert("Backend communication failed.");
        } finally {
            const el = document.getElementById('skeleton-loader');
            if(el) el.remove();
            this.renderHistoryFeed();
            this.refreshDynamicUI(); 
            
            document.getElementById('capture-btn').disabled = false;
            document.getElementById('send-btn').disabled = false;
        }
    },

    updateTokenTelemetry() {
        const used = parseInt(localStorage.getItem('token_tracker') || '0', 10);
        const ratio = Math.min((used / AppState.MAX_TOKENS) * 100, 100);
        document.getElementById('token-fill').style.width = `${ratio}%`;
        document.getElementById('token-text').innerText = AppState.tokenFormat === 'percent' ? `${ratio.toFixed(2)}% USED` : `${used.toLocaleString()} / ${AppState.MAX_TOKENS.toLocaleString()}`;
    },

    async handleTextExtraction(content) {
        const contextRecord = {
            id: Date.now(),
            prompt: "Screen Text Extraction",
            model: "Clipboard",
            images: [],
            response: content
        };
        AppState.transactionHistory.unshift(contextRecord);
        await store.setItem('history_stack', AppState.transactionHistory);
        this.renderHistoryFeed();
    },

    renderHistoryFeed() {
        const feed = document.getElementById('feed');
        feed.innerHTML = '';
        if (AppState.transactionHistory.length === 0) {
            feed.innerHTML = `<div class="h-full flex items-center justify-center text-xs text-slate-400 font-medium">No active contexts.</div>`;
            return;
        }
        
        AppState.transactionHistory.forEach(record => {
            const card = document.createElement('div');
            card.className = "bg-white border border-slate-200 rounded-xl p-3.5 shadow-sm flex flex-col gap-3 relative";
            // ... Omitted repetitive DOM node creation for brevity, it mirrors your original card rendering logic ...
            // Just bind the delete action properly
            const deleteBtn = document.createElement('button');
            deleteBtn.className = "absolute top-3 right-3 text-slate-300 hover:text-red-500";
            deleteBtn.innerHTML = `[X]`; // Replaced icon for brevity
            deleteBtn.onclick = async () => {
                AppState.transactionHistory = AppState.transactionHistory.filter(item => item.id !== record.id);
                await store.setItem('history_stack', AppState.transactionHistory);
                this.renderHistoryFeed();
            };
            card.appendChild(deleteBtn);

            const text = document.createElement('div');
            text.className = "text-sm text-slate-800 line-clamp-3";
            text.innerText = record.response;
            card.appendChild(text);

            feed.appendChild(card);
        });
    }
};