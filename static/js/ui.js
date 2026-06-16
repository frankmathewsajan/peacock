import { AppState } from './state.js';
import { API } from './api.js';

const store = localforage.createInstance({ name: 'stealth_history_db' });

export const UI = {
    setNetworkStatus(isConnected) {
        const indicator = document.getElementById('network-status');
        indicator.className = isConnected ? "w-2 h-2 rounded-full bg-emerald-500" : "w-2 h-2 rounded-full bg-red-500";
    },

    setLoadingState(isLoading) {
        document.getElementById('capture-btn').disabled = isLoading;
        document.getElementById('send-btn').disabled = isLoading;
        const feed = document.getElementById('feed');

        if (isLoading) {
            const skel = document.createElement('div');
            skel.id = "skeleton-loader";
            skel.className = "bg-white border border-slate-200 rounded-xl p-3.5 shadow-sm flex flex-col gap-3 animate-pulse";
            skel.innerHTML = `<div class="h-8 bg-slate-100 rounded w-full"></div>`;
            feed.prepend(skel);
            feed.scrollTo({ top: 0, behavior: 'smooth' });
        } else {
            const el = document.getElementById('skeleton-loader');
            if (el) el.remove();
        }
    },

    refreshControls() {
        const sendBtn = document.getElementById('send-btn');
        const captureBtn = document.getElementById('capture-btn');
        const captureText = document.getElementById('capture-text');

        if (AppState.currentMode === 'single') {
            sendBtn.classList.add('hidden');
            captureBtn.className = "flex-1 h-14 rounded-xl bg-slate-900 text-white font-semibold active:scale-[0.98] transition flex items-center justify-center gap-2 shadow-md";
            captureText.innerText = "Capture & Analyze";
        } else {
            if (AppState.temporaryBlobs.length > 0) {
                sendBtn.classList.remove('hidden');
                captureBtn.className = "flex-1 h-14 rounded-xl bg-slate-100 text-slate-700 font-semibold active:scale-[0.98] transition flex items-center justify-center gap-2 shadow-md border border-slate-200";
                captureText.innerText = "Add Frame";
            } else {
                sendBtn.classList.add('hidden');
                captureBtn.className = "flex-1 h-14 rounded-xl bg-slate-900 text-white font-semibold active:scale-[0.98] transition flex items-center justify-center gap-2 shadow-md";
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
                    API.sendCommand("CAPTURE");
                } else if (AppState.temporaryBlobs.length > 0) {
                    API.executeInference(p.text);
                }
            });
            container.appendChild(btn);
        });
    },

    renderDraftGallery() {
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
            // Add pointer and click event to open the Image Modal
            img.className = "h-full w-full object-cover cursor-pointer hover:opacity-80 transition";
            img.onclick = () => {
                document.getElementById('preview-image-element').src = url;
                document.getElementById('image-modal').classList.remove('opacity-0', 'pointer-events-none');
            };
            
            const delBtn = document.createElement('button');
            delBtn.className = "absolute top-0.5 right-0.5 bg-black/50 text-white rounded-full p-0.5 hover:bg-red-500 transition";
            delBtn.innerHTML = `✕`; 
            delBtn.onclick = (e) => {
                e.stopPropagation(); // Prevent the image from opening when clicking delete
                AppState.removeBlob(index);
                this.renderDraftGallery();
                this.refreshControls();
            };
            
            wrapper.appendChild(img);
            wrapper.appendChild(delBtn);
            gallery.appendChild(wrapper);
        });
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
            
            const deleteBtn = document.createElement('button');
            deleteBtn.className = "absolute top-3 right-3 text-slate-300 hover:text-red-500 font-bold text-xs";
            deleteBtn.innerHTML = `✕`; 
            deleteBtn.onclick = async () => {
                AppState.transactionHistory = AppState.transactionHistory.filter(item => item.id !== record.id);
                await store.setItem('history_stack', AppState.transactionHistory);
                this.renderHistoryFeed();
            };
            card.appendChild(deleteBtn);

            const text = document.createElement('div');
            text.className = "text-sm text-slate-800 line-clamp-3 mt-4";
            text.innerText = record.response;
            card.appendChild(text);

            feed.appendChild(card);
        });
    },

    updateTokenTelemetry() {
        const used = parseInt(localStorage.getItem('token_tracker') || '0', 10);
        const ratio = Math.min((used / AppState.MAX_TOKENS) * 100, 100);
        document.getElementById('token-fill').style.width = `${ratio}%`;
        document.getElementById('token-text').innerText = `${used.toLocaleString()} / ${AppState.MAX_TOKENS.toLocaleString()}`;
    }
};