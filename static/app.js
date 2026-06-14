const store = localforage.createInstance({ name: 'stealth_history_db' });
const ws = new WebSocket(`ws://${location.host}/stream`);
ws.binaryType = "blob";

const captureBtn = document.getElementById("capture-btn");
const extractTextBtn = document.getElementById("extract-text-btn");
const captureText = document.getElementById("capture-text");
const sendBtn = document.getElementById("send-btn");
const draftGallery = document.getElementById("draft-gallery");
const feed = document.getElementById("feed");
const modal = document.getElementById("modal");

const MAX_TOKENS = 1000000;
let temporaryBlobs = [];
let transactionHistory = [];
let tokenFormat = 'raw';
let currentModel = 'fast';
let currentMode = 'single'; 
let pendingExecutionPrompt = null;
let currentModalText = ""; 
let isTypingPaused = false; 

const pauseIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>`;
const playIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>`;

const natureEmojis = [
    '🦚', '🌿', '🪴', '🌲', '🌸', 
    '🌻', '🍄', '🦉', '🕊️', '🦆', 
    '🦅', '🦜', '🦊', '🐢', '🦋', 
    '🐝', '🐈', '🐕', '🐅', '🐸'
];

let customPrompts = [];
let legacyPrompts = JSON.parse(localStorage.getItem('saved_prompts'));

if (Array.isArray(legacyPrompts) && typeof legacyPrompts[0] === 'string') {
    const defaultIcons = ['🦚', '🌿', '🦉'];
    customPrompts = legacyPrompts.map((text, i) => ({ emoji: defaultIcons[i], text: text }));
    customPrompts.push({ emoji: '🦊', text: "Provide the primary action item." });
    localStorage.setItem('saved_prompts', JSON.stringify(customPrompts));
} else if (legacyPrompts && legacyPrompts[0] && legacyPrompts[0].emoji) {
    const containsOldEmojis = !natureEmojis.includes(legacyPrompts[0].emoji);
    if (containsOldEmojis) {
         const defaultIcons = ['🦚', '🌿', '🦉', '🦊'];
         customPrompts = legacyPrompts.map((p, i) => ({ emoji: defaultIcons[i], text: p.text }));
         localStorage.setItem('saved_prompts', JSON.stringify(customPrompts));
    } else {
        customPrompts = legacyPrompts;
    }
} else {
    customPrompts = [
        { emoji: '🦚', text: "Summarize this slide concisely" },
        { emoji: '🌿', text: "Extract all text exactly as written" },
        { emoji: '🦉', text: "Explain the core concept" },
        { emoji: '🦊', text: "Provide the primary action item." }
    ];
}

let autoFirePrompt = localStorage.getItem('auto_prompt') || "Analyze this screen and provide key takeaways.";

async function init() {
    populateEmojiPickers();

    try {
        const res = await fetch("/tokens");
        const data = await res.json();
        localStorage.setItem('token_tracker', data.total_tokens || data.total_used);
    } catch(e) { console.error("Could not sync tokens", e); }

    transactionHistory = await store.getItem('history_stack') || [];
    renderPrompts();
    updateTokenTelemetry();
    renderHistoryFeed();
    setupTokenLongPress();
    refreshDynamicUI();
}

function populateEmojiPickers() {
    [1, 2, 3, 4].forEach(num => {
        const select = document.getElementById(`p${num}-emoji`);
        if(!select) return;
        select.innerHTML = '';
        natureEmojis.forEach(emoji => {
            const opt = document.createElement('option');
            opt.value = emoji;
            opt.innerText = emoji;
            select.appendChild(opt);
        });
    });
}

window.setModel = function(target) {
    currentModel = target;
    document.getElementById('model-fast').className = target === 'fast' ? "flex-1 px-2 py-1.5 text-[11px] font-bold uppercase tracking-wider rounded-md bg-white shadow-sm text-slate-800 transition" : "flex-1 px-2 py-1.5 text-[11px] font-bold uppercase tracking-wider rounded-md text-slate-400 transition hover:text-slate-600";
    document.getElementById('model-deep').className = target === 'deep' ? "flex-1 px-2 py-1.5 text-[11px] font-bold uppercase tracking-wider rounded-md bg-white shadow-sm text-slate-800 transition" : "flex-1 px-2 py-1.5 text-[11px] font-bold uppercase tracking-wider rounded-md text-slate-400 transition hover:text-slate-600";
}

window.setMode = function(target) {
    currentMode = target;
    document.getElementById('mode-single').className = target === 'single' ? "flex-1 px-2 py-1.5 text-[11px] font-bold uppercase tracking-wider rounded-md bg-white shadow-sm text-slate-800 transition" : "flex-1 px-2 py-1.5 text-[11px] font-bold uppercase tracking-wider rounded-md text-slate-400 transition hover:text-slate-600";
    document.getElementById('mode-batch').className = target === 'batch' ? "flex-1 px-2 py-1.5 text-[11px] font-bold uppercase tracking-wider rounded-md bg-white shadow-sm text-slate-800 transition" : "flex-1 px-2 py-1.5 text-[11px] font-bold uppercase tracking-wider rounded-md text-slate-400 transition hover:text-slate-600";
    
    if (target === 'single' && temporaryBlobs.length > 0) {
        temporaryBlobs = [];
        renderDraftPreviewRow();
    }
    refreshDynamicUI();
}

function refreshDynamicUI() {
    if (currentMode === 'single') {
        sendBtn.classList.add('hidden');
        captureBtn.classList.remove('bg-slate-100', 'text-slate-700');
        captureBtn.classList.add('bg-slate-900', 'text-white');
        captureText.innerText = "Capture & Analyze";
    } else {
        if (temporaryBlobs.length > 0) {
            sendBtn.classList.remove('hidden');
            captureBtn.classList.remove('bg-slate-900', 'text-white');
            captureBtn.classList.add('bg-slate-100', 'text-slate-700');
            captureText.innerText = "Add Frame";
        } else {
            sendBtn.classList.add('hidden');
            captureBtn.classList.remove('bg-slate-100', 'text-slate-700');
            captureBtn.classList.add('bg-slate-900', 'text-white');
            captureText.innerText = "Start Batch Capture";
        }
    }
}

captureBtn.onclick = () => {
    if (ws.readyState === 1) {
        if (currentMode === 'single') {
            pendingExecutionPrompt = autoFirePrompt;
        } else {
            pendingExecutionPrompt = null;
        }
        ws.send(JSON.stringify({ action: "CAPTURE" }));
    }
};

extractTextBtn.onclick = () => {
    if (ws.readyState === 1) {
        ws.send(JSON.stringify({ action: "EXTRACT_TEXT" }));
        
        const oldHtml = extractTextBtn.innerHTML;
        extractTextBtn.innerHTML = `<span class="animate-pulse font-bold text-[10px]">WAIT</span>`;
        setTimeout(() => { extractTextBtn.innerHTML = oldHtml; }, 800);
    }
}

sendBtn.onclick = () => {
    if (temporaryBlobs.length > 0) {
        executeInference(autoFirePrompt, currentModel);
    }
};

window.handlePresetClick = function(presetText) {
    if (currentMode === 'single') {
        pendingExecutionPrompt = presetText;
        if (ws.readyState === 1) ws.send(JSON.stringify({ action: "CAPTURE" }));
    } else {
        if (temporaryBlobs.length > 0) {
            executeInference(presetText, currentModel);
        }
    }
}

window.removeDraftBlob = function(index) {
    temporaryBlobs.splice(index, 1);
    renderDraftPreviewRow();
    refreshDynamicUI();
}

window.openRemoteModal = function() {
    const rm = document.getElementById('remote-modal');
    rm.classList.remove('opacity-0', 'pointer-events-none');
    rm.children[0].classList.remove('scale-95');
    document.getElementById('remote-text').value = '';
    document.getElementById('remote-text').focus();
    
    document.getElementById('injection-controls').classList.remove('hidden');
    document.getElementById('active-type-controls').classList.add('hidden');
    isTypingPaused = false;
    
    const pBtn = document.getElementById('pause-type-btn');
    pBtn.innerHTML = pauseIcon;
    pBtn.classList.replace('bg-emerald-500', 'bg-amber-500');
}

window.closeRemoteModal = function() {
    const rm = document.getElementById('remote-modal');
    rm.classList.add('opacity-0', 'pointer-events-none');
    rm.children[0].classList.add('scale-95');
}

window.sendRemoteType = function() {
    const txt = document.getElementById('remote-text').value;
    if (ws.readyState === 1 && txt) {
        ws.send(JSON.stringify({ action: "TYPE", text: txt }));
        
        document.getElementById('injection-controls').classList.add('hidden');
        document.getElementById('active-type-controls').classList.remove('hidden');
    }
}

window.sendRemotePaste = function() {
    const txt = document.getElementById('remote-text').value;
    if (ws.readyState === 1 && txt) {
        ws.send(JSON.stringify({ action: "PASTE", text: txt }));
        window.closeRemoteModal();
    }
}

window.togglePauseType = function() {
    const btn = document.getElementById('pause-type-btn');
    if (!isTypingPaused) {
        ws.send(JSON.stringify({ action: "PAUSE_TYPE" }));
        isTypingPaused = true;
        btn.innerHTML = playIcon; 
        btn.classList.replace('bg-amber-500', 'bg-emerald-500');
    } else {
        ws.send(JSON.stringify({ action: "RESUME_TYPE" }));
        isTypingPaused = false;
        btn.innerHTML = pauseIcon; 
        btn.classList.replace('bg-emerald-500', 'bg-amber-500');
    }
}

window.stopRemoteType = function() {
    ws.send(JSON.stringify({ action: "STOP_TYPE" }));
    window.closeRemoteModal();
}

ws.onmessage = async (e) => {
    if (typeof e.data === 'string') {
        try {
            const data = JSON.parse(e.data);
            if (data.type === "extracted_text") {
                const contextRecord = {
                    id: Date.now(),
                    prompt: "Screen Text Extraction (Ctrl+A, Ctrl+C)",
                    model: "Clipboard",
                    images: [],
                    response: data.content
                };
                
                transactionHistory.unshift(contextRecord);
                await store.setItem('history_stack', transactionHistory);
                renderHistoryFeed();
            }
        } catch(err) { console.error(err); }
        return;
    }

    temporaryBlobs.push(e.data);
    renderDraftPreviewRow();
    refreshDynamicUI();

    if (pendingExecutionPrompt) {
        const promptToFire = pendingExecutionPrompt;
        pendingExecutionPrompt = null;
        executeInference(promptToFire, currentModel);
    }
};

function renderPrompts() {
    const container = document.getElementById('prompts-container');
    container.innerHTML = '';
    customPrompts.forEach(p => {
        if (!p.text.trim()) return;
        const btn = document.createElement('button');
        btn.title = p.text; 
        btn.className = "flex-1 h-11 rounded-xl border border-slate-200 bg-white text-base active:bg-slate-100 shadow-sm transition active:scale-95 flex items-center justify-center";
        btn.innerText = p.emoji;
        btn.onclick = () => handlePresetClick(p.text);
        container.appendChild(btn);
    });
}

function renderDraftPreviewRow() {
    draftGallery.innerHTML = '';
    if (temporaryBlobs.length === 0) {
        draftGallery.classList.add('hidden');
        return;
    }
    draftGallery.classList.remove('hidden');
    temporaryBlobs.forEach((blob, index) => {
        const url = URL.createObjectURL(blob);
        const wrapper = document.createElement('div');
        wrapper.className = "relative h-14 w-20 shrink-0 border border-slate-200 rounded-lg overflow-hidden bg-slate-100";
        
        const img = document.createElement('img');
        img.src = url;
        img.className = "h-full w-full object-cover";
        
        const delBtn = document.createElement('button');
        delBtn.className = "absolute top-0.5 right-0.5 bg-black/50 text-white rounded-full p-0.5 hover:bg-red-500 transition";
        delBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`;
        delBtn.onclick = () => removeDraftBlob(index);
        
        wrapper.appendChild(img);
        wrapper.appendChild(delBtn);
        draftGallery.appendChild(wrapper);
    });
}

function renderHistoryFeed() {
    feed.innerHTML = '';
    if (transactionHistory.length === 0) {
        feed.innerHTML = `<div class="h-full flex items-center justify-center text-xs text-slate-400 font-medium">No active contexts.</div>`;
        return;
    }

    transactionHistory.forEach(record => {
        const card = document.createElement('div');
        card.className = "bg-white border border-slate-200 rounded-xl p-3.5 shadow-sm flex flex-col gap-3 relative";
        
        const deleteBtn = document.createElement('button');
        deleteBtn.className = "absolute top-3 right-3 text-slate-300 hover:text-red-500 transition p-1 rounded-md";
        deleteBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>`;
        deleteBtn.onclick = () => deleteRecord(record.id);
        card.appendChild(deleteBtn);

        const metaRow = document.createElement('div');
        metaRow.className = "flex gap-2 items-center pr-8";
        
        const badge = document.createElement('span');
        badge.className = record.model === 'deep' ? "px-1.5 py-0.5 rounded text-[9px] font-bold bg-indigo-50 text-indigo-600 border border-indigo-100 uppercase" : "px-1.5 py-0.5 rounded text-[9px] font-bold bg-slate-100 text-slate-500 border border-slate-200 uppercase";
        badge.innerText = record.model;
        metaRow.appendChild(badge);

        const promptTitle = document.createElement('div');
        promptTitle.className = "text-sm font-medium text-slate-800 break-words line-clamp-2";
        promptTitle.innerText = record.prompt || "Visual analysis";
        metaRow.appendChild(promptTitle);
        
        card.appendChild(metaRow);

        if (record.images && record.images.length > 0) {
            const scrollContainer = document.createElement('div');
            scrollContainer.className = "flex gap-1.5 overflow-x-auto pb-0.5 scrollbar-hide";
            record.images.forEach(imgBlob => {
                const url = URL.createObjectURL(imgBlob);
                const thumbnail = document.createElement('img');
                thumbnail.src = url;
                thumbnail.className = "h-11 w-16 object-cover rounded border border-slate-100 bg-slate-50 shrink-0";
                scrollContainer.appendChild(thumbnail);
            });
            card.appendChild(scrollContainer);
        }

        const actionBtn = document.createElement('button');
        actionBtn.className = "w-full py-2.5 bg-slate-50 hover:bg-slate-100 border border-slate-200 text-slate-800 font-semibold rounded-lg text-xs transition active:scale-[0.98]";
        actionBtn.innerText = "Review Response";
        actionBtn.onclick = () => showModalContent(record.id);
        card.appendChild(actionBtn);

        feed.appendChild(card);
    });
}

function updateTokenTelemetry() {
    const used = parseInt(localStorage.getItem('token_tracker') || '0', 10);
    const ratio = Math.min((used / MAX_TOKENS) * 100, 100);
    document.getElementById('token-fill').style.width = `${ratio}%`;
    document.getElementById('token-text').innerText = tokenFormat === 'percent' ? `${ratio.toFixed(2)}% USED` : `${used.toLocaleString()} / ${MAX_TOKENS.toLocaleString()}`;
}

function setupTokenLongPress() {
    const btn = document.getElementById('refresh-btn');
    let pressTimer;
    const startPress = () => {
        pressTimer = setTimeout(() => {
            tokenFormat = tokenFormat === 'raw' ? 'percent' : 'raw';
            updateTokenTelemetry();
            btn.classList.add('text-indigo-500');
            setTimeout(() => btn.classList.remove('text-indigo-500'), 300);
        }, 600);
    };
    const cancelPress = () => clearTimeout(pressTimer);
    btn.addEventListener('pointerdown', startPress);
    btn.addEventListener('pointerup', cancelPress);
    btn.addEventListener('pointerleave', cancelPress);
    btn.addEventListener('click', () => updateTokenTelemetry());
}

window.openConfigModal = function() {
    document.getElementById('auto-prompt').value = autoFirePrompt;
    [1, 2, 3, 4].forEach(num => {
        const data = customPrompts[num - 1] || { emoji: '🌿', text: '' };
        document.getElementById(`p${num}-emoji`).value = data.emoji;
        document.getElementById(`p${num}-text`).value = data.text;
    });
    const modal = document.getElementById('config-modal');
    modal.classList.remove('opacity-0', 'pointer-events-none');
    modal.children[0].classList.remove('scale-95');
}

window.closeConfigModal = function() {
    const modal = document.getElementById('config-modal');
    modal.classList.add('opacity-0', 'pointer-events-none');
    modal.children[0].classList.add('scale-95');
}

window.saveConfig = function() {
    autoFirePrompt = document.getElementById('auto-prompt').value.trim() || "Analyze this screen and provide key takeaways.";
    localStorage.setItem('auto_prompt', autoFirePrompt);
    customPrompts = [1, 2, 3, 4].map(num => ({
        emoji: document.getElementById(`p${num}-emoji`).value,
        text: document.getElementById(`p${num}-text`).value.trim()
    }));
    localStorage.setItem('saved_prompts', JSON.stringify(customPrompts));
    renderPrompts();
    closeConfigModal();
}

window.deleteRecord = async function(id) {
    transactionHistory = transactionHistory.filter(item => item.id !== id);
    await store.setItem('history_stack', transactionHistory);
    renderHistoryFeed();
}

function showSkeleton() {
    const skel = document.createElement('div');
    skel.id = "skeleton-loader";
    skel.className = "bg-white border border-slate-200 rounded-xl p-3.5 shadow-sm flex flex-col gap-3 animate-pulse";
    skel.innerHTML = `
        <div class="flex gap-2 items-center"><div class="h-4 w-8 bg-slate-200 rounded"></div><div class="h-4 bg-slate-200 rounded w-1/2"></div></div>
        <div class="flex gap-1.5"><div class="h-11 w-16 bg-slate-200 rounded"></div></div>
        <div class="h-8 bg-slate-100 rounded w-full"></div>
    `;
    feed.prepend(skel);
}

function removeSkeleton() {
    const skel = document.getElementById('skeleton-loader');
    if (skel) skel.remove();
}

async function executeInference(queryText, executionModel) {
    if (!queryText && temporaryBlobs.length === 0) return;

    captureBtn.disabled = true;
    sendBtn.disabled = true;
    const buttons = document.querySelectorAll('#prompts-container button');
    buttons.forEach(b => b.disabled = true);
    
    const originalBtnHTML = sendBtn.innerHTML;
    const originalCaptureHTML = captureBtn.innerHTML;
    
    if(currentMode === 'single') {
        captureBtn.innerHTML = `<span class="animate-pulse">Analyzing...</span>`;
    } else {
        sendBtn.innerHTML = `<span class="animate-pulse">...</span>`;
    }
    
    showSkeleton();
    feed.scrollTo({ top: 0, behavior: 'smooth' });

    try {
        const res = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                message: queryText,
                model_tier: executionModel
            })
        });
        
        const data = await res.json();
        
        localStorage.setItem('token_tracker', data.total_tokens);
        updateTokenTelemetry();

        const contextRecord = {
            id: Date.now(),
            prompt: queryText,
            model: executionModel,
            images: [...temporaryBlobs],
            response: data.response
        };
        
        transactionHistory.unshift(contextRecord);
        await store.setItem('history_stack', transactionHistory);
        
        temporaryBlobs = [];
        renderDraftPreviewRow();
        
    } catch (error) {
        console.error("Network fault:", error);
        alert("Backend communication failed.");
    } finally {
        removeSkeleton();
        renderHistoryFeed();
        refreshDynamicUI(); 
        
        captureBtn.disabled = false;
        sendBtn.disabled = false;
        buttons.forEach(b => b.disabled = false);
        
        if(currentMode === 'single') {
             captureBtn.innerHTML = originalCaptureHTML;
        } else {
             sendBtn.innerHTML = originalBtnHTML;
        }
    }
}

window.showModalContent = function(id) {
    const target = transactionHistory.find(item => item.id === id);
    if (target) {
        currentModalText = target.response; 
        document.getElementById('modal-content').innerHTML = marked.parse(target.response);
        modal.classList.remove('translate-y-full');
    }
}

window.copyModalContent = function() {
    if (!currentModalText) return;
    
    const btn = document.querySelector('#modal button[onclick="copyModalContent()"]');
    const oldHtml = btn.innerHTML;
    
    const successUI = () => {
        btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg> Copied!`;
        btn.classList.replace('text-indigo-700', 'text-emerald-600');
        btn.classList.replace('border-indigo-200', 'border-emerald-200');
        
        setTimeout(() => {
            btn.innerHTML = oldHtml;
            btn.classList.replace('text-emerald-600', 'text-indigo-700');
            btn.classList.replace('border-emerald-200', 'border-indigo-200');
        }, 1500);
    };

    // Use modern clipboard if Secure Context, fallback to legacy if HTTP/Local IP
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(currentModalText).then(successUI);
    } else {
        let textArea = document.createElement("textarea");
        textArea.value = currentModalText;
        textArea.style.position = "fixed";
        textArea.style.left = "-9999px";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        try {
            document.execCommand('copy');
            successUI();
        } catch (err) {
            console.error('Fallback copy failed', err);
            alert("Secure copy blocked over HTTP. Please long-press text to copy manually.");
        }
        document.body.removeChild(textArea);
    }
}

window.closeModal = function() {
    modal.classList.add('translate-y-full');
    currentModalText = ""; 
}

init();