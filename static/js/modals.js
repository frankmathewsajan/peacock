import { AppState } from './state.js';
import { API } from './api.js';
import { UI } from './ui.js';

export const Modals = {
    initRemote() {
        const modal = document.getElementById('remote-modal');
        const textArea = document.getElementById('remote-text');
        const targetSelect = document.getElementById('route-target');
        const sendBtn = document.getElementById('remote-send-btn');
        
        const toggleVisBtn = document.getElementById('toggle-vis-btn');
        const toggleLockBtn = document.getElementById('toggle-lock-btn');
        const toggleThemeBtn = document.getElementById('toggle-theme-btn'); // Theme button

        // Local state trackers for remote toggles
        let isPrompterVisible = true;
        let isPrompterLocked = false;

        document.getElementById('open-remote-btn').addEventListener('click', () => {
            modal.classList.remove('opacity-0', 'pointer-events-none');
            textArea.focus();
        });

        document.getElementById('close-remote-btn').addEventListener('click', () => {
            modal.classList.add('opacity-0', 'pointer-events-none');
        });

        // --- PAYLOAD ROUTING ---
        sendBtn.addEventListener('click', () => {
            const text = textArea.value;
            const target = targetSelect.value;

            if (text) {
                if (target === 'os') {
                    API.sendCommand("PASTE", text);
                } else if (target === 'prompter') {
                    API.sendCommand("PROMPTER_SYNC", text);
                }
                
                const oldText = sendBtn.innerText;
                sendBtn.innerText = target === 'os' ? "Pasted to OS!" : "Synced to Prompter!";
                sendBtn.classList.replace('bg-indigo-600', 'bg-emerald-500');
                
                setTimeout(() => {
                    sendBtn.innerText = oldText;
                    sendBtn.classList.replace('bg-emerald-500', 'bg-indigo-600');
                }, 1200);
            }
        });

        // --- HARDWARE TOGGLES ---
        toggleVisBtn.addEventListener('click', () => {
            isPrompterVisible = !isPrompterVisible;
            if (isPrompterVisible) {
                API.sendCommand("PROMPTER_SHOW");
                toggleVisBtn.innerText = "Hide UI";
                toggleVisBtn.classList.replace("bg-slate-200", "bg-slate-100");
            } else {
                API.sendCommand("PROMPTER_HIDE");
                toggleVisBtn.innerText = "Show UI";
                toggleVisBtn.classList.replace("bg-slate-100", "bg-slate-200");
            }
        });

        toggleLockBtn.addEventListener('click', () => {
            isPrompterLocked = !isPrompterLocked;
            if (isPrompterLocked) {
                API.sendCommand("PROMPTER_LOCK");
                toggleLockBtn.innerText = "Unlock UI (Solid)";
                toggleLockBtn.classList.replace("bg-slate-100", "bg-emerald-50");
                toggleLockBtn.classList.replace("text-slate-700", "text-emerald-700");
                toggleLockBtn.classList.replace("border-slate-200", "border-emerald-200");
            } else {
                API.sendCommand("PROMPTER_UNLOCK");
                toggleLockBtn.innerText = "Lock (Intangible)";
                toggleLockBtn.classList.replace("bg-emerald-50", "bg-slate-100");
                toggleLockBtn.classList.replace("text-emerald-700", "text-slate-700");
                toggleLockBtn.classList.replace("border-emerald-200", "border-slate-200");
            }
        });

        // --- THEME TOGGLE ---
        toggleThemeBtn.addEventListener('click', () => {
            API.sendCommand("PROMPTER_THEME");
        });
    },

    initConfig() {
        const modal = document.getElementById('config-modal');
        const container = document.getElementById('preset-editors-container');

        document.getElementById('open-config-btn').addEventListener('click', () => {
            document.getElementById('auto-prompt').value = AppState.autoFirePrompt;
            
            container.innerHTML = '';
            AppState.customPrompts.forEach((p, index) => {
                const row = document.createElement('div');
                row.className = "flex gap-2";
                
                const select = document.createElement('select');
                select.className = "emoji-picker w-12 rounded-lg border border-slate-200 bg-slate-50 text-base outline-none cursor-pointer";
                select.id = `p${index}-emoji`;
                AppState.natureEmojis.forEach(emoji => {
                    select.add(new Option(emoji, emoji, false, emoji === p.emoji));
                });

                const input = document.createElement('input');
                input.className = "flex-1 border border-slate-200 rounded-lg p-2 text-sm outline-none";
                input.id = `p${index}-text`;
                input.value = p.text;

                row.append(select, input);
                container.appendChild(row);
            });

            modal.classList.remove('opacity-0', 'pointer-events-none');
        });

        document.getElementById('close-config-btn').addEventListener('click', () => {
            modal.classList.add('opacity-0', 'pointer-events-none');
        });

        document.getElementById('save-config-btn').addEventListener('click', () => {
            const autoPrompt = document.getElementById('auto-prompt').value.trim();
            const newPrompts = AppState.customPrompts.map((_, i) => ({
                emoji: document.getElementById(`p${i}-emoji`).value,
                text: document.getElementById(`p${i}-text`).value.trim()
            }));

            AppState.saveConfig(autoPrompt, newPrompts);
            UI.renderPrompts();
            modal.classList.add('opacity-0', 'pointer-events-none');
        });
    },

    initImagePreview() {
        document.getElementById('close-image-modal').addEventListener('click', () => {
            document.getElementById('image-modal').classList.add('opacity-0', 'pointer-events-none');
            document.getElementById('preview-image-element').src = "";
        });
    }
};