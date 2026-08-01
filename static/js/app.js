/**
 * MARK — AI System Controller
 * Client-side: WebSocket, Wake Word Detection, Speech, TTS, Orb Visualization
 * 
 * Wake word: "MARK" — always listening in background.
 * When "MARK" is detected, captures the command that follows.
 */

// ─────────────────────────────────────────────
// SOCKET.IO CONNECTION
// ─────────────────────────────────────────────

const socket = io(window.location.origin, {
    reconnection: true,
    reconnectionAttempts: 10,
    reconnectionDelay: 1000
});

// ─────────────────────────────────────────────
// DOM ELEMENTS
// ─────────────────────────────────────────────

const DOM = {
    messagesArea: document.getElementById('messagesArea'),
    messageInput: document.getElementById('messageInput'),
    btnSend: document.getElementById('btnSend'),
    btnMic: document.getElementById('btnMic'),
    btnReset: document.getElementById('btnReset'),
    thinkingIndicator: document.getElementById('thinkingIndicator'),
    welcomeState: document.getElementById('welcomeState'),
    statusDot: document.getElementById('statusDot'),
    statusText: document.getElementById('statusText'),
    orbCanvas: document.getElementById('orbCanvas'),
    orbStatus: document.getElementById('orbStatus'),
    orbSubtext: document.getElementById('orbSubtext'),
    responseTime: document.getElementById('responseTime'),
    voiceIndicator: document.getElementById('voiceIndicator'),
    ttsToggle: document.getElementById('ttsToggle'),
    toastContainer: document.getElementById('toastContainer'),
    wakeWordToggle: document.getElementById('wakeWordToggle'),
    wakeWordStatus: document.getElementById('wakeWordStatus'),
    clapToggle: document.getElementById('clapToggle'),
    btnUserAccount: document.getElementById('btnUserAccount'),
    settingsOverlay: document.getElementById('settingsOverlay'),
    btnCloseSettings: document.getElementById('btnCloseSettings'),
    systemPromptEditor: document.getElementById('systemPromptEditor'),
    btnSavePrompt: document.getElementById('btnSavePrompt'),
    // Voice & Language
    voiceSelect: document.getElementById('voiceSelect'),
    rateSlider: document.getElementById('rateSlider'),
    rateLabel: document.getElementById('rateLabel'),
    btnSaveVoice: document.getElementById('btnSaveVoice'),
    voiceSaveStatus: document.getElementById('voiceSaveStatus'),
    // AI Backend
    btnBackendOllama: document.getElementById('btnBackendOllama'),
    btnBackendLocal: document.getElementById('btnBackendLocal'),
    backendStatus: document.getElementById('backendStatus'),
};

// ─────────────────────────────────────────────
// STATE
// ─────────────────────────────────────────────

let state = {
    isRecording: false,         // Manual mic recording
    isThinking: false,          // Waiting for AI response
    recognition: null,          // SpeechRecognition instance
    currentAudio: null,         // Currently playing TTS audio
    hasMessages: false,         // Has any messages been sent
    orbMode: 'dormant',         // dormant, idle, wakeword, listening, thinking, speaking
    wakeWordEnabled: false,     // Is wake word mode active
    wakeWordListening: false,   // Is background listener running
    commandMode: false,         // Actively capturing a command after wake word
    commandTimeout: null,       // Timeout to end command capture
    wakeWordCooldown: false,    // Prevent double-trigger
    clapEnabled: false,         // Clap detection enabled
    clapStream: null,           // Mic stream for clap detection
    clapAnalyser: null,         // AnalyserNode for clap detection
    clapCooldown: false,        // Prevent rapid re-triggering
};

// ─────────────────────────────────────────────
// AUDIO CHIME (generated programmatically)
// ─────────────────────────────────────────────

const AudioCtx = window.AudioContext || window.webkitAudioContext;
let audioCtx = null;

function playWakeChime() {
    try {
        if (!audioCtx) audioCtx = new AudioCtx();

        // Two-tone ascending chime — like a premium assistant activation
        const now = audioCtx.currentTime;

        // First tone
        const osc1 = audioCtx.createOscillator();
        const gain1 = audioCtx.createGain();
        osc1.type = 'sine';
        osc1.frequency.setValueAtTime(587.33, now);  // D5
        gain1.gain.setValueAtTime(0.15, now);
        gain1.gain.exponentialRampToValueAtTime(0.01, now + 0.15);
        osc1.connect(gain1);
        gain1.connect(audioCtx.destination);
        osc1.start(now);
        osc1.stop(now + 0.15);

        // Second tone (higher, slightly delayed)
        const osc2 = audioCtx.createOscillator();
        const gain2 = audioCtx.createGain();
        osc2.type = 'sine';
        osc2.frequency.setValueAtTime(880, now + 0.08);  // A5
        gain2.gain.setValueAtTime(0, now);
        gain2.gain.setValueAtTime(0.15, now + 0.08);
        gain2.gain.exponentialRampToValueAtTime(0.01, now + 0.25);
        osc2.connect(gain2);
        gain2.connect(audioCtx.destination);
        osc2.start(now + 0.08);
        osc2.stop(now + 0.25);
    } catch (e) {
        console.log('Chime skipped:', e);
    }
}

function playDeactivateChime() {
    try {
        if (!audioCtx) audioCtx = new AudioCtx();
        const now = audioCtx.currentTime;
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(440, now);
        osc.frequency.exponentialRampToValueAtTime(330, now + 0.15);
        gain.gain.setValueAtTime(0.1, now);
        gain.gain.exponentialRampToValueAtTime(0.01, now + 0.2);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start(now);
        osc.stop(now + 0.2);
    } catch (e) { }
}

// ─────────────────────────────────────────────
// SOCKET EVENTS
// ─────────────────────────────────────────────

socket.on('connect', () => {
    setConnectionStatus(true);
    showToast('Connected to MARK', 'success');
});

socket.on('disconnect', () => {
    setConnectionStatus(false);
    showToast('Disconnected from MARK', 'error');
});

socket.on('status', (data) => {
    showToast(data.message, data.type || 'info');
});

socket.on('thinking', (data) => {
    state.isThinking = data.status;
    DOM.thinkingIndicator.classList.toggle('active', data.status);
    if (data.status) {
        setOrbMode('thinking');
        scrollToBottom();
    }
});

socket.on('ai_response', (data) => {
    // Close out any agent progress panel so the next task starts a fresh one.
    if (_agentPanel && _agentPanel.isConnected) {
        const title = _agentPanel.querySelector('.agent-progress__title');
        if (title) title.textContent = `Done — ${data.steps || 0} steps`;
        _agentPanel.classList.add('agent-progress--done');
    }
    _agentPanel = null;

    addMessage('ai', data.text, data.tool_calls);
    if (data.response_time) {
        DOM.responseTime.textContent = `${data.response_time}s`;
    }
    // Return to appropriate resting state
    setOrbMode(state.wakeWordEnabled ? 'dormant' : 'idle');
});

socket.on('tts_audio', (data) => {
    if (DOM.ttsToggle.checked && data.audio) {
        playTTSAudio(data.audio);
    }
});

socket.on('tts_chunk', (data) => {
    if (DOM.ttsToggle.checked && data.audio) {
        _queueTTSChunk(data.audio, data.final || false);
    }
    // Empty final marker — just ignore (queue will drain naturally)
});

// ─────────────────────────────────────────────
// MESSAGE HANDLING
// ─────────────────────────────────────────────

function sendMessage(text) {
    if (!text || !text.trim()) return;

    // Hide welcome state
    if (!state.hasMessages) {
        DOM.welcomeState.style.display = 'none';
        state.hasMessages = true;
    }

    addMessage('user', text.trim());
    socket.emit('user_message', { message: text.trim() });
    DOM.messageInput.value = '';
    setOrbMode('thinking');
}

function addMessage(type, text, toolCalls = null) {
    const msg = document.createElement('div');
    msg.className = `message ${type}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = type === 'ai' ? 'M' : '→';

    const content = document.createElement('div');
    content.className = 'message-content';

    // Parse markdown-like formatting
    let formattedText = text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code style="background:rgba(255,106,0,0.1);padding:2px 6px;border-radius:4px;font-family:JetBrains Mono,monospace;font-size:12px">$1</code>')
        .replace(/\n/g, '<br>');

    content.innerHTML = `<div>${formattedText}</div>`;

    // Add tool badges
    if (toolCalls && toolCalls.length > 0) {
        toolCalls.forEach(tc => {
            const badge = document.createElement('div');
            badge.className = 'tool-badge';
            badge.textContent = tc.name;
            content.appendChild(badge);
        });
    }

    // Add timestamp
    const meta = document.createElement('div');
    meta.className = 'message-meta';
    meta.textContent = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    content.appendChild(meta);

    msg.appendChild(avatar);
    msg.appendChild(content);

    // Insert before thinking indicator
    DOM.messagesArea.insertBefore(msg, DOM.thinkingIndicator);
    scrollToBottom();
}

function scrollToBottom() {
    requestAnimationFrame(() => {
        DOM.messagesArea.scrollTop = DOM.messagesArea.scrollHeight;
    });
}

// ─────────────────────────────────────────────
// WAKE WORD SYSTEM — "MARK"
// ─────────────────────────────────────────────

const WAKE_WORD = 'mark';
const WAKE_VARIANTS = [
    'mark', 'marc', 'park', 'dark', 'bark', 'marque', 'marks',
    'march', 'marsh', 'mock', 'mach', 'mart', 'marck', 'maak',
    'marg', 'mak', 'mac', 'mar', 'marquee', 'markk'
];

function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        showToast('Speech recognition not supported', 'error');
        DOM.btnMic.style.display = 'none';
        return;
    }

    state.recognition = new SpeechRecognition();
    state.recognition.continuous = true;        // Keep listening!
    state.recognition.interimResults = true;
    state.recognition.lang = _currentLang || 'en-US';
    state.recognition.maxAlternatives = 3;      // More alternatives for better wake word matching

    state.recognition.onresult = handleSpeechResult;
    state.recognition.onerror = handleSpeechError;
    state.recognition.onend = handleSpeechEnd;
}

function handleSpeechResult(event) {
    let finalTranscript = '';
    let interimTranscript = '';

    for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        // Check ALL alternatives for wake word (not just top result)
        let bestTranscript = result[0].transcript;
        for (let a = 0; a < result.length; a++) {
            const alt = result[a].transcript;
            if (detectWakeWord(alt.toLowerCase().trim())) {
                bestTranscript = alt; // Use the alternative that matched the wake word
                break;
            }
        }
        const transcript = bestTranscript;

        if (result.isFinal) {
            finalTranscript += transcript;
        } else {
            interimTranscript += transcript;
        }
    }

    // ── MODE: Manual recording (mic button pressed) ──
    if (state.isRecording && !state.wakeWordEnabled) {
        if (interimTranscript) DOM.messageInput.value = interimTranscript;
        if (finalTranscript) {
            DOM.messageInput.value = '';
            stopRecording();
            sendMessage(finalTranscript);
        }
        return;
    }

    // ── MODE: Wake word listening ──
    if (state.wakeWordEnabled) {
        // Check BOTH interim and final for fastest wake word detection
        const interimCheck = interimTranscript.toLowerCase().trim();
        const finalCheck = finalTranscript.toLowerCase().trim();
        const fullText = finalCheck || interimCheck;

        // Already in command mode — capture the command
        if (state.commandMode) {
            if (interimTranscript) {
                DOM.messageInput.value = interimTranscript;
                state.lastSpeechActivity = Date.now();
            }
            if (finalTranscript) {
                const command = finalTranscript.trim();
                if (command && command.length > 1) {
                    // Don't send too quickly — ensure at least 1.5s of listening
                    const elapsed = Date.now() - (state.commandStartTime || 0);
                    if (elapsed < 1500) {
                        // Too soon, accumulate in buffer
                        state.commandBuffer = (state.commandBuffer || '') + ' ' + command;
                        DOM.messageInput.value = state.commandBuffer.trim();
                        return;
                    }
                    // Combine any buffered text
                    const fullCommand = ((state.commandBuffer || '') + ' ' + command).trim();
                    DOM.messageInput.value = '';
                    state.commandMode = false;
                    state.commandBuffer = '';
                    clearTimeout(state.commandTimeout);
                    setOrbMode('thinking');
                    DOM.voiceIndicator.classList.remove('active');
                    sendMessage(fullCommand);
                }
            }
            // Reset silence timeout on any speech activity — 10 second patience window
            if (state.commandTimeout) clearTimeout(state.commandTimeout);
            state.commandTimeout = setTimeout(() => {
                if (state.commandMode) {
                    // If we have buffered text, send it
                    const buffered = (state.commandBuffer || '').trim() || DOM.messageInput.value.trim();
                    state.commandMode = false;
                    state.commandBuffer = '';
                    DOM.voiceIndicator.classList.remove('active');
                    if (buffered && buffered.length > 1) {
                        DOM.messageInput.value = '';
                        setOrbMode('thinking');
                        sendMessage(buffered);
                    } else {
                        setOrbMode('dormant');
                        DOM.messageInput.value = '';
                        DOM.messageInput.placeholder = 'Say "MARK" to activate...';
                        showToast('No command detected, going back to sleep', 'info');
                    }
                }
            }, 10000);
            return;
        }

        // Check for wake word in transcript
        if (detectWakeWord(fullText)) {
            if (state.wakeWordCooldown) return;
            state.wakeWordCooldown = true;
            setTimeout(() => { state.wakeWordCooldown = false; }, 1000); // 1s cooldown (was 2s)

            // Extract command after wake word if present
            const afterWake = extractCommandAfterWake(fullText);

            playWakeChime();
            setOrbMode('wakeword');

            if (afterWake && afterWake.length > 3 && finalTranscript) {
                // Wake word + command in same utterance: "Mark open Safari"
                setTimeout(() => {
                    setOrbMode('thinking');
                    sendMessage(afterWake);
                }, 400);
            } else {
                // Just wake word — enter command mode and wait for command
                state.commandMode = true;
                state.commandBuffer = '';
                state.commandStartTime = Date.now();
                DOM.messageInput.placeholder = 'Listening for command...';
                DOM.voiceIndicator.classList.add('active');

                setTimeout(() => setOrbMode('listening'), 500);

                // Long timeout: 10 seconds of silence before giving up
                state.commandTimeout = setTimeout(() => {
                    if (state.commandMode) {
                        const buffered = (state.commandBuffer || '').trim() || DOM.messageInput.value.trim();
                        state.commandMode = false;
                        state.commandBuffer = '';
                        DOM.voiceIndicator.classList.remove('active');
                        if (buffered && buffered.length > 1) {
                            DOM.messageInput.value = '';
                            setOrbMode('thinking');
                            sendMessage(buffered);
                        } else {
                            setOrbMode('dormant');
                            DOM.messageInput.value = '';
                            DOM.messageInput.placeholder = 'Say "MARK" to activate...';
                            showToast('No command detected, going back to sleep', 'info');
                        }
                    }
                }, 10000);
            }
        }
    }
}

function detectWakeWord(text) {
    const lower = text.toLowerCase();
    const words = lower.split(/[\s,.!?;:]+/).filter(w => w.length > 0);

    for (const word of words) {
        // Exact match against variants
        if (WAKE_VARIANTS.includes(word)) return true;
        // Starts with "mark"
        if (word.startsWith('mark')) return true;
        // Fuzzy: Levenshtein distance ≤ 1 from "mark"
        if (word.length >= 3 && word.length <= 6 && levenshtein(word, 'mark') <= 1) return true;
    }
    // Phrase-level checks
    if (lower.includes('hey mark') || lower.includes('okay mark') || lower.includes('ok mark')) return true;
    if (lower.includes('hey marc') || lower.includes('okay marc') || lower.includes('ok marc')) return true;
    return false;
}

// Levenshtein distance for fuzzy wake word matching
function levenshtein(a, b) {
    const m = a.length, n = b.length;
    const d = Array.from({ length: m + 1 }, (_, i) => [i]);
    for (let j = 1; j <= n; j++) d[0][j] = j;
    for (let i = 1; i <= m; i++) {
        for (let j = 1; j <= n; j++) {
            d[i][j] = a[i - 1] === b[j - 1]
                ? d[i - 1][j - 1]
                : 1 + Math.min(d[i - 1][j], d[i][j - 1], d[i - 1][j - 1]);
        }
    }
    return d[m][n];
}

function extractCommandAfterWake(text) {
    // Find where the wake word is and extract everything after
    const patterns = ['hey mark', 'okay mark', 'ok mark', 'mark'];
    const lower = text.toLowerCase();

    for (const pattern of patterns) {
        const idx = lower.indexOf(pattern);
        if (idx !== -1) {
            const after = text.substring(idx + pattern.length).trim();
            // Remove leading punctuation/comma
            return after.replace(/^[,.\s]+/, '').trim();
        }
    }
    return '';
}

function handleSpeechError(event) {
    console.error('Speech error:', event.error);

    if (event.error === 'not-allowed') {
        showToast('Microphone access denied. Please allow mic access.', 'error');
        disableWakeWord();
        return;
    }

    // For non-fatal errors, just restart if wake word is on
    if (event.error !== 'aborted' && state.wakeWordEnabled) {
        setTimeout(() => startWakeWordListener(), 500);
    }

    if (state.isRecording && !state.wakeWordEnabled) {
        stopRecording();
    }
}

function handleSpeechEnd() {
    // Auto-restart if wake word mode is active
    if (state.wakeWordEnabled && !state.isThinking) {
        setTimeout(() => startWakeWordListener(), 100); // 100ms restart (was 200ms)
    } else if (state.isRecording) {
        stopRecording();
    }
}

// ─────────────────────────────────────────────
// WAKE WORD CONTROL
// ─────────────────────────────────────────────

function enableWakeWord() {
    state.wakeWordEnabled = true;
    state.commandMode = false;
    setOrbMode('dormant');
    DOM.messageInput.placeholder = 'Say "MARK" to activate...';
    if (DOM.wakeWordStatus) DOM.wakeWordStatus.textContent = 'Wake word active';
    showToast('🎤 Wake word activated — say "MARK" to give commands', 'success');
    startWakeWordListener();
}

function disableWakeWord() {
    state.wakeWordEnabled = false;
    state.commandMode = false;
    clearTimeout(state.commandTimeout);
    setOrbMode('idle');
    DOM.messageInput.placeholder = 'Type a command or speak...';
    if (DOM.wakeWordStatus) DOM.wakeWordStatus.textContent = '';
    DOM.voiceIndicator.classList.remove('active');
    playDeactivateChime();
    showToast('Wake word deactivated', 'info');

    try {
        if (state.recognition) state.recognition.stop();
    } catch (e) { }
}

function toggleWakeWord() {
    if (state.wakeWordEnabled) {
        disableWakeWord();
    } else {
        enableWakeWord();
    }
}

function startWakeWordListener() {
    if (!state.wakeWordEnabled) return;
    if (!state.recognition) initSpeechRecognition();
    if (!state.recognition) return;

    try {
        state.recognition.start();
        state.wakeWordListening = true;
    } catch (e) {
        // Already running — fine
        if (e.name !== 'InvalidStateError') {
            console.error('Wake word start error:', e);
        }
    }
}

// ─────────────────────────────────────────────
// CLAP DETECTION SYSTEM — Double-Clap to Activate
// ─────────────────────────────────────────────

let clapCtx = null;       // Dedicated AudioContext for clap detection
let clapTimeDomain = null; // Uint8Array for time-domain data
let lastClapTime = 0;      // Timestamp of last detected clap
let clapCheckInterval = null;

function startClapDetection() {
    if (state.clapEnabled) return;
    navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
        .then(stream => {
            state.clapStream = stream;
            state.clapEnabled = true;

            if (!clapCtx) clapCtx = new (window.AudioContext || window.webkitAudioContext)();
            const source = clapCtx.createMediaStreamSource(stream);
            state.clapAnalyser = clapCtx.createAnalyser();
            state.clapAnalyser.fftSize = 2048;
            state.clapAnalyser.smoothingTimeConstant = 0.3;
            source.connect(state.clapAnalyser);
            clapTimeDomain = new Uint8Array(state.clapAnalyser.fftSize);

            // Check for claps at 60fps
            clapCheckInterval = setInterval(detectClap, 16);

            showToast('👏 Clap detection ON — double-clap to activate MARK', 'success');
            console.log('Clap detection started');
        })
        .catch(err => {
            console.error('Clap detection mic error:', err);
            showToast('Microphone access needed for clap detection', 'error');
            if (DOM.clapToggle) DOM.clapToggle.checked = false;
        });
}

function stopClapDetection() {
    state.clapEnabled = false;
    if (clapCheckInterval) { clearInterval(clapCheckInterval); clapCheckInterval = null; }
    if (state.clapStream) {
        state.clapStream.getTracks().forEach(t => t.stop());
        state.clapStream = null;
    }
    state.clapAnalyser = null;
    clapTimeDomain = null;
    lastClapTime = 0;
    showToast('Clap detection OFF', 'info');
    console.log('Clap detection stopped');
}

function detectClap() {
    if (!state.clapEnabled || !state.clapAnalyser || !clapTimeDomain) return;
    // Don't detect during speaking (prevents TTS audio triggering a clap)
    if (state.orbMode === 'speaking' || state.currentAudio) return;
    // Don't detect if already activated / cooldown
    if (state.clapCooldown) return;

    state.clapAnalyser.getByteTimeDomainData(clapTimeDomain);

    // Find peak amplitude — clap shows as a sharp spike
    let peak = 0;
    for (let i = 0; i < clapTimeDomain.length; i++) {
        const v = Math.abs(clapTimeDomain[i] - 128);
        if (v > peak) peak = v;
    }

    // Threshold: a strong clap typically peaks above 60-80 out of 128
    const CLAP_THRESHOLD = 55;

    if (peak > CLAP_THRESHOLD) {
        const now = Date.now();
        const gap = now - lastClapTime;

        if (gap > 150 && gap < 700) {
            // ✅ DOUBLE CLAP DETECTED!
            lastClapTime = 0;
            triggerClapActivation();
        } else {
            // First clap — wait for second
            lastClapTime = now;
        }
    }
}

function triggerClapActivation() {
    if (state.clapCooldown) return;
    state.clapCooldown = true;

    console.log('👏👏 Double clap detected — activating MARK!');

    // Visual feedback: orb goes wakeword mode
    setOrbMode('wakeword');
    playWakeChime();

    // Tell server to generate activation TTS
    socket.emit('clap_activate');

    // Cooldown: 4 seconds before next clap can trigger
    setTimeout(() => {
        state.clapCooldown = false;
    }, 4000);
}

// ─────────────────────────────────────────────
// MANUAL MIC (push to talk, still works)
// ─────────────────────────────────────────────

function startRecording() {
    if (!state.recognition) initSpeechRecognition();
    if (!state.recognition) return;

    // If wake word is active, temporarily disable
    if (state.wakeWordEnabled) {
        try { state.recognition.stop(); } catch (e) { }
        state.wakeWordEnabled = false;
        // We'll re-enable after recording
    }

    // Stop any playing audio
    if (state.currentAudio) {
        state.currentAudio.pause();
        state.currentAudio = null;
    }

    state.isRecording = true;
    state.recognition.continuous = false;  // Single utterance for manual
    DOM.btnMic.classList.add('recording');
    DOM.voiceIndicator.classList.add('active');
    DOM.messageInput.placeholder = 'Listening...';
    setOrbMode('listening');

    try {
        state.recognition.start();
    } catch (e) { }
}

function stopRecording() {
    state.isRecording = false;
    DOM.btnMic.classList.remove('recording');
    DOM.voiceIndicator.classList.remove('active');
    DOM.messageInput.placeholder = 'Type a command or speak...';

    if (!state.isThinking) {
        setOrbMode('idle');
    }

    try {
        state.recognition.stop();
    } catch (e) { }

    // Restore continuous mode for wake word
    if (state.recognition) {
        state.recognition.continuous = true;
    }

    // Re-enable wake word if toggle is on
    if (DOM.wakeWordToggle && DOM.wakeWordToggle.checked) {
        setTimeout(() => {
            state.wakeWordEnabled = true;
            setOrbMode(state.isThinking ? 'thinking' : 'dormant');
            DOM.messageInput.placeholder = 'Say "MARK" to activate...';
            startWakeWordListener();
        }, 1000);
    }
}

function toggleRecording() {
    if (state.isRecording) {
        stopRecording();
    } else {
        startRecording();
    }
}

// ─────────────────────────────────────────────
// TTS AUDIO PLAYBACK — Streaming Queue System
// Plays audio chunks seamlessly with no gaps.
// First sentence starts playing within ~300ms.
// ─────────────────────────────────────────────

const ttsQueue = {
    chunks: [],          // queued base64 audio chunks
    playing: false,      // is a chunk currently playing
    wasWakeWord: false,  // was wake word active when playback started
    analyzerSetup: false,// has analyzer been connected
};

function playTTSAudio(base64Audio) {
    // Legacy single-chunk path — queue it
    _queueTTSChunk(base64Audio, true);
}

function _queueTTSChunk(base64Audio, isFinal = false) {
    ttsQueue.chunks.push({ audio: base64Audio, final: isFinal });

    // Start playing if not already
    if (!ttsQueue.playing) {
        // Pause wake word listener during TTS
        ttsQueue.wasWakeWord = state.wakeWordEnabled;
        if (ttsQueue.wasWakeWord) {
            try { state.recognition.stop(); } catch (e) { }
            state.wakeWordListening = false;
        }
        _playNextChunk();
    }
}

function _playNextChunk() {
    if (ttsQueue.chunks.length === 0) {
        // All chunks played — restore state
        ttsQueue.playing = false;
        ttsQueue.analyzerSetup = false;
        setOrbMode(state.wakeWordEnabled ? 'dormant' : 'idle');
        state.currentAudio = null;
        audioAnalyzer = null;
        audioFreqData = null;

        // Resume wake word after TTS
        if (ttsQueue.wasWakeWord) {
            state.wakeWordEnabled = true;
            setTimeout(() => startWakeWordListener(), 500);
        }
        return;
    }

    ttsQueue.playing = true;
    const chunk = ttsQueue.chunks.shift();

    try {
        // Stop any existing audio
        if (state.currentAudio) {
            state.currentAudio.pause();
            state.currentAudio = null;
        }

        const audioData = Uint8Array.from(atob(chunk.audio), c => c.charCodeAt(0));
        const blob = new Blob([audioData], { type: 'audio/mp3' });
        const url = URL.createObjectURL(blob);

        state.currentAudio = new Audio(url);
        setOrbMode('speaking');

        // Connect each Audio element to the analyzer for visualization
        try {
            if (!audioCtx) audioCtx = new AudioCtx();
            const source = audioCtx.createMediaElementSource(state.currentAudio);
            if (!ttsQueue.analyzerSetup) {
                audioAnalyzer = audioCtx.createAnalyser();
                audioAnalyzer.fftSize = 256;
                audioAnalyzer.smoothingTimeConstant = 0.7;
                audioFreqData = new Uint8Array(audioAnalyzer.frequencyBinCount);
                audioAnalyzer.connect(audioCtx.destination);
                ttsQueue.analyzerSetup = true;
            }
            source.connect(audioAnalyzer);
        } catch (e) {
            // Fallback: play without visualization
        }

        state.currentAudio.onended = () => {
            URL.revokeObjectURL(url);
            // Immediately play next chunk — no gap
            _playNextChunk();
        };

        state.currentAudio.onerror = () => {
            URL.revokeObjectURL(url);
            _playNextChunk(); // Skip to next on error
        };

        state.currentAudio.play().catch(err => {
            console.error('Audio chunk playback error:', err);
            _playNextChunk(); // Skip to next on error
        });
    } catch (e) {
        console.error('TTS chunk error:', e);
        _playNextChunk(); // Skip to next
    }
}

function stopTTSPlayback() {
    // Clear the queue and stop current audio
    ttsQueue.chunks = [];
    ttsQueue.playing = false;
    ttsQueue.analyzerSetup = false;
    if (state.currentAudio) {
        state.currentAudio.pause();
        state.currentAudio = null;
    }
    audioAnalyzer = null;
    audioFreqData = null;
    setOrbMode(state.wakeWordEnabled ? 'dormant' : 'idle');
    if (ttsQueue.wasWakeWord) {
        state.wakeWordEnabled = true;
        setTimeout(() => startWakeWordListener(), 500);
    }
}

// ─────────────────────────────────────────────
// ORB VISUALIZATION — Premium 3D Orb
// ─────────────────────────────────────────────

// Initialize 3D Orb
let centerOrb = null;

// Wait for DOM
document.addEventListener('DOMContentLoaded', () => {
    if (typeof OrbVisualizer !== 'undefined') {
        centerOrb = new OrbVisualizer(DOM.orbCanvas);
    }
});

// Audio bridge
let audioAnalyzer = null;
let audioFreqData = null;

function _getAudioData() {
    if (!audioAnalyzer || !audioFreqData) return [];
    audioAnalyzer.getByteFrequencyData(audioFreqData);
    return audioFreqData;
}

function setOrbMode(mode) {
    state.orbMode = mode;

    // Update text labels
    const labels = {
        dormant: ['D O R M A N T', 'Say "MARK" to activate'],
        idle: ['I D L E', 'Awaiting your command'],
        wakeword: ['A C T I V A T E D', 'Wake word detected!'],
        listening: ['L I S T E N I N G', 'I\'m all ears, sir'],
        thinking: ['P R O C E S S I N G', 'Analyzing your request...'],
        speaking: ['S P E A K I N G', 'Delivering response']
    };
    const [s, sub] = labels[mode] || labels.idle;
    if (DOM.orbStatus) DOM.orbStatus.textContent = s;
    if (DOM.orbSubtext) DOM.orbSubtext.textContent = sub;

    // Update 3D Orb
    if (centerOrb) {
        centerOrb.setMode(mode);
    }
}

// Main loop to feed audio data to orb
function orbLoop() {
    requestAnimationFrame(orbLoop);
    if (centerOrb && state.orbMode === 'speaking' && audioAnalyzer) {
        centerOrb.updateAudio(_getAudioData());
    } else if (centerOrb) {
        // Clear audio data when not speaking
        centerOrb.updateAudio([]);
    }
}
orbLoop();





// ─────────────────────────────────────────────
// UI HELPERS
// ─────────────────────────────────────────────

function setConnectionStatus(connected) {
    DOM.statusDot.className = `status-dot${connected ? '' : ' offline'}`;
    DOM.statusText.textContent = connected ? 'Online' : 'Offline';
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    DOM.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(40px)';
        toast.style.transition = 'all 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ─────────────────────────────────────────────
// EVENT LISTENERS
// ─────────────────────────────────────────────

// Send message
DOM.btnSend.addEventListener('click', () => {
    sendMessage(DOM.messageInput.value);
});

DOM.messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage(DOM.messageInput.value);
    }
});

// Mic button
DOM.btnMic.addEventListener('click', toggleRecording);

// Wake word toggle
if (DOM.wakeWordToggle) {
    DOM.wakeWordToggle.addEventListener('change', (e) => {
        if (e.target.checked) {
            enableWakeWord();
        } else {
            disableWakeWord();
        }
    });
}

// Clap detection toggle
if (DOM.clapToggle) {
    DOM.clapToggle.addEventListener('change', (e) => {
        if (e.target.checked) {
            startClapDetection();
        } else {
            stopClapDetection();
        }
    });
}

// Listen for clap activation TTS from server
socket.on('clap_activation_tts', (data) => {
    if (data.audio) {
        playTTSAudio(data.audio);
    }
});

// Listen for fired reminders from background scheduler
socket.on('reminder_fired', (data) => {
    showToast(`🔔 Reminder: ${data.message}`, 'success');
});

// ── Proactive Voice Monitor Alerts ──
socket.on('proactive_alert', (data) => {
    const sev = data.severity || 'info';  // info / warning / critical
    const icons = { info: 'ℹ️', warning: '⚠️', critical: '🚨' };
    const icon = icons[sev] || 'ℹ️';
    showToast(`${icon} ${data.message}`, sev === 'critical' ? 'error' : sev === 'warning' ? 'warning' : 'info');

    // Speak the alert via TTS
    if (DOM.ttsToggle && DOM.ttsToggle.checked) {
        // Inject the alert into chat as a MARK message too
        addMessage('ai', data.message, null);
        scrollToBottom();
    }
});

// ── Agent progress ──
// The server has always emitted these; nothing used to listen, so multi-step
// tasks ran completely invisibly.
let _agentPanel = null;

function ensureAgentPanel() {
    if (_agentPanel && _agentPanel.isConnected) return _agentPanel;
    const panel = document.createElement('div');
    panel.className = 'message ai agent-progress';
    panel.innerHTML = `
        <div class="message-avatar">M</div>
        <div class="message-content">
            <div class="agent-progress__title">Working through it…</div>
            <ol class="agent-progress__steps"></ol>
        </div>`;
    DOM.messagesArea.appendChild(panel);
    _agentPanel = panel;
    scrollToBottom();
    return panel;
}

socket.on('agentic_step', (data) => {
    const panel = ensureAgentPanel();
    const list = panel.querySelector('.agent-progress__steps');
    const item = document.createElement('li');
    const tools = (data.tools || []).join(', ');
    item.innerHTML = tools
        ? `<span class="agent-progress__tool">${tools}</span> ${escapeHtml(data.message || '')}`
        : escapeHtml(data.message || '');
    list.appendChild(item);
    scrollToBottom();
});

socket.on('tool_used', (data) => {
    showToast(`🛠️ ${data.name}`, 'info');
});

// ── Sensitive action awaiting approval ──
socket.on('confirmation_required', (data) => {
    if (!data || !data.tool) return;
    const panel = document.createElement('div');
    panel.className = 'message ai confirm-request';
    const args = Object.entries(data.args || {})
        .map(([k, v]) => `${k}: ${String(v).slice(0, 120)}`).join('\n');
    panel.innerHTML = `
        <div class="message-avatar">M</div>
        <div class="message-content">
            <div class="confirm-request__title">Needs your go-ahead</div>
            <pre class="confirm-request__detail">${escapeHtml(data.tool)}${args ? '\n' + escapeHtml(args) : ''}</pre>
            <div class="confirm-request__actions">
                <button class="confirm-btn confirm-btn--yes">Run it</button>
                <button class="confirm-btn confirm-btn--no">Cancel</button>
            </div>
        </div>`;
    DOM.messagesArea.appendChild(panel);
    scrollToBottom();

    const resolve = async (approve) => {
        panel.querySelectorAll('button').forEach(b => b.disabled = true);
        try {
            const resp = await fetch('/api/permissions/resolve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ approve })
            });
            const result = await resp.json();
            panel.remove();
            addMessage('ai', result.response, result.tool_calls);
            scrollToBottom();
        } catch (e) {
            showToast('Could not send that decision: ' + e.message, 'error');
        }
    };
    panel.querySelector('.confirm-btn--yes').addEventListener('click', () => resolve(true));
    panel.querySelector('.confirm-btn--no').addEventListener('click', () => resolve(false));
});

// ── Proactive speech ──
socket.on('proactive_speak', (data) => {
    if (DOM.ttsToggle && DOM.ttsToggle.checked && data.text) {
        addMessage('ai', data.text, null);
        scrollToBottom();
    }
});

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str == null ? '' : String(str);
    return div.innerHTML;
}

// ── Holographic HUD Cards ──
socket.on('hud_card', (data) => {
    const overlay = document.getElementById('hudOverlay');
    if (!overlay) return;

    const duration = (data.duration || 8) * 1000;
    const card = document.createElement('div');
    card.className = 'hud-card';
    card.innerHTML = `
        <button class="hud-card-close" title="Dismiss">×</button>
        <div class="hud-card-header">
            <div class="hud-card-icon">${data.icon || '🔮'}</div>
            <div class="hud-card-title">${data.title || 'MARK HUD'}</div>
        </div>
        <div class="hud-card-body">${data.content || ''}</div>
        <div class="hud-card-timer" style="animation-duration: ${duration}ms;"></div>
    `;

    // Close button
    card.querySelector('.hud-card-close').addEventListener('click', () => dismissHud(card));

    overlay.appendChild(card);

    // Auto-dismiss
    const timer = setTimeout(() => dismissHud(card), duration);
    card._hudTimer = timer;

    function dismissHud(el) {
        if (el._dismissed) return;
        el._dismissed = true;
        clearTimeout(el._hudTimer);
        el.classList.add('dismissing');
        setTimeout(() => el.remove(), 400);
    }
});


// Reset conversation
DOM.btnReset.addEventListener('click', () => {
    socket.emit('reset_chat');
    DOM.messagesArea.querySelectorAll('.message').forEach(m => m.remove());
    DOM.welcomeState.style.display = 'flex';
    state.hasMessages = false;
    DOM.responseTime.textContent = '';
    showToast('Conversation reset', 'info');
});

// Quick actions
document.querySelectorAll('.chip, .quick-action').forEach(btn => {
    btn.addEventListener('click', () => {
        sendMessage(btn.dataset.cmd);
    });
});

// ─────────────────────────────────────────────
// VOICE & LANGUAGE
// ─────────────────────────────────────────────

let _currentLang = 'en-US'; // kept in sync with server

async function loadVoices() {
    try {
        const resp = await fetch('/api/voices');
        const data = await resp.json();
        const select = DOM.voiceSelect;
        if (!select) return;

        select.innerHTML = '';

        // Group by language
        const groups = {};
        data.voices.forEach(v => {
            if (!groups[v.lang]) groups[v.lang] = [];
            groups[v.lang].push(v);
        });

        const langOrder = ['English', 'Telugu', 'Hindi', 'Tamil'];
        const ordered = [...langOrder, ...Object.keys(groups).filter(l => !langOrder.includes(l))];

        ordered.forEach(lang => {
            if (!groups[lang]) return;
            const grp = document.createElement('optgroup');
            grp.label = `── ${lang} ──`;
            groups[lang].forEach(v => {
                const opt = document.createElement('option');
                opt.value = v.id;
                opt.textContent = v.name;
                if (v.id === data.current) opt.selected = true;
                grp.appendChild(opt);
            });
            select.appendChild(grp);
        });
    } catch (e) {
        console.error('Failed to load voices:', e);
    }
}

async function applyVoice() {
    const select = DOM.voiceSelect;
    const slider = DOM.rateSlider;
    const statusEl = DOM.voiceSaveStatus;
    if (!select) return;

    const voiceId = select.value;
    const rateVal = parseInt(slider ? slider.value : 10);
    const ratePct = rateVal >= 0 ? `+${rateVal}%` : `${rateVal}%`;

    try {
        const resp = await fetch('/api/set_voice', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ voice_id: voiceId, rate: ratePct })
        });
        const data = await resp.json();
        if (data.success) {
            _currentLang = data.lang || 'en-US';
            // Update speech recognition language on the fly
            if (state.recognition) {
                const wasRunning = state.wakeWordEnabled;
                try { state.recognition.stop(); } catch (e) { }
                state.recognition.lang = _currentLang;
                if (wasRunning) setTimeout(() => startWakeWordListener(), 300);
            }
            showToast(`🗣️ Voice changed — ${select.options[select.selectedIndex].text}`, 'success');
            if (statusEl) {
                statusEl.textContent = '✓ Applied';
                statusEl.style.opacity = '1';
                setTimeout(() => { statusEl.style.opacity = '0'; }, 2500);
            }
        } else {
            showToast('Failed to change voice', 'error');
        }
    } catch (e) {
        showToast('Voice change error: ' + e.message, 'error');
    }
}

// Rate slider label + gradient
if (DOM.rateSlider && DOM.rateLabel) {
    DOM.rateSlider.addEventListener('input', () => {
        const v = parseInt(DOM.rateSlider.value);
        const pct = (v + 50) / 100; // 0-1 range
        DOM.rateSlider.style.background =
            `linear-gradient(to right, var(--accent) ${pct * 100}%, var(--surface-4) ${pct * 100}%)`;
        if (v === 0) DOM.rateLabel.textContent = 'Normal';
        else if (v > 0) DOM.rateLabel.textContent = `+${v}% Faster`;
        else DOM.rateLabel.textContent = `${v}% Slower`;
    });
    // Init slider position
    DOM.rateSlider.dispatchEvent(new Event('input'));
}

if (DOM.btnSaveVoice) {
    DOM.btnSaveVoice.addEventListener('click', applyVoice);
}

// ─────────────────────────────────────────────
// AI BACKEND TOGGLE
// ─────────────────────────────────────────────

let _backendPollTimer = null;

async function loadBackendStatus() {
    try {
        const resp = await fetch('/api/llm_status');
        const data = await resp.json();
        updateBackendUI(data.backend, data.local_model);
    } catch (e) {
        console.error('Backend status error:', e);
    }
}

function updateBackendUI(backend, localModel) {
    // Toggle buttons
    if (DOM.btnBackendOllama) {
        DOM.btnBackendOllama.classList.toggle('active', backend === 'ollama');
    }
    if (DOM.btnBackendLocal) {
        DOM.btnBackendLocal.classList.toggle('active', backend === 'local');
    }

    // Status indicator
    const statusEl = DOM.backendStatus;
    if (!statusEl) return;
    const dot = statusEl.querySelector('.backend-status__dot');
    const text = statusEl.querySelector('.backend-status__text');

    if (backend === 'ollama') {
        dot.className = 'backend-status__dot';
        text.textContent = 'Replies via Ollama — routing stays on-device';
        if (_backendPollTimer) { clearInterval(_backendPollTimer); _backendPollTimer = null; }
    } else {
        const status = localModel ? localModel.status : 'unloaded';
        const message = localModel ? localModel.message : '';
        dot.className = 'backend-status__dot';

        if (status === 'ready') {
            // green by default, no extra classes needed
            text.textContent = '✓ ' + message;
            if (_backendPollTimer) { clearInterval(_backendPollTimer); _backendPollTimer = null; }
        } else if (status === 'loading' || status === 'downloading') {
            dot.classList.add('loading');
            text.textContent = '⏳ ' + message;
            // Keep polling
            if (!_backendPollTimer) {
                _backendPollTimer = setInterval(loadBackendStatus, 2000);
            }
        } else if (status === 'error') {
            dot.classList.add('error');
            text.textContent = '✗ ' + message;
            if (_backendPollTimer) { clearInterval(_backendPollTimer); _backendPollTimer = null; }
        } else {
            text.textContent = 'Model not loaded yet';
        }
    }
}

async function switchBackend(backend) {
    try {
        const resp = await fetch('/api/set_llm_backend', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ backend })
        });
        const data = await resp.json();
        if (data.success) {
            showToast(backend === 'local' ? '💻 Running fully on-device' : '🦙 Replies routed to Ollama', 'success');
            loadBackendStatus();
            // Start polling if local (model may be loading)
            if (backend === 'local' && !_backendPollTimer) {
                _backendPollTimer = setInterval(loadBackendStatus, 2000);
            }
        } else {
            showToast('Failed to switch backend', 'error');
        }
    } catch (e) {
        showToast('Backend switch error: ' + e.message, 'error');
    }
}

if (DOM.btnBackendOllama) {
    DOM.btnBackendOllama.addEventListener('click', () => switchBackend('ollama'));
}
if (DOM.btnBackendLocal) {
    DOM.btnBackendLocal.addEventListener('click', () => switchBackend('local'));
}

// ─────────────────────────────────────────────
// SETTINGS PANEL
// ─────────────────────────────────────────────

function openSettings() {
    DOM.settingsOverlay.classList.add('active');
    // Load current system prompt from server
    socket.emit('get_system_prompt');
    // Load voices
    loadVoices();
    // Load backend status
    loadBackendStatus();
}

function closeSettings() {
    DOM.settingsOverlay.classList.remove('active');
    if (_backendPollTimer) { clearInterval(_backendPollTimer); _backendPollTimer = null; }
}

// Open settings
if (DOM.btnUserAccount) {
    DOM.btnUserAccount.addEventListener('click', openSettings);
}

// Close settings
if (DOM.btnCloseSettings) {
    DOM.btnCloseSettings.addEventListener('click', closeSettings);
}

// Click overlay to close
if (DOM.settingsOverlay) {
    DOM.settingsOverlay.addEventListener('click', (e) => {
        if (e.target === DOM.settingsOverlay) closeSettings();
    });
}

// Escape key closes settings
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && DOM.settingsOverlay.classList.contains('active')) {
        closeSettings();
    }
});

// Receive system prompt from server
socket.on('system_prompt', (data) => {
    if (DOM.systemPromptEditor) {
        DOM.systemPromptEditor.value = data.prompt || '';
    }
});

// Save system prompt
if (DOM.btnSavePrompt) {
    DOM.btnSavePrompt.addEventListener('click', () => {
        const prompt = DOM.systemPromptEditor.value.trim();
        if (prompt) {
            socket.emit('set_system_prompt', { prompt });
            showToast('💾 System prompt saved', 'success');
        } else {
            showToast('Prompt cannot be empty', 'error');
        }
    });
}

// ─────────────────────────────────────────────
// GESTURE CONTROLLER
// ─────────────────────────────────────────────

const gestureToggle = document.getElementById('gestureToggle');
let gestureCtrl = null;

if (gestureToggle && window.GestureController) {
    gestureCtrl = new GestureController(socket);

    gestureToggle.addEventListener('change', async () => {
        if (gestureToggle.checked) {
            const ok = await gestureCtrl.start();
            if (!ok) {
                gestureToggle.checked = false;
                showToast('Camera access denied or unavailable', 'error');
            } else {
                showToast('🖐️ Gesture control enabled', 'success');
            }
        } else {
            gestureCtrl.stop();
            showToast('Gesture control disabled', 'info');
        }
    });
}

// ─────────────────────────────────────────────
// INIT
// ─────────────────────────────────────────────

initSpeechRecognition();
console.log('%c M.A.R.K. %c AI System Controller %c Wake Word Ready ',
    'background: #FF6A00; color: #000; font-weight: 900; padding: 4px 8px; border-radius: 4px 0 0 4px;',
    'background: #111; color: #FF6A00; font-weight: 600; padding: 4px 8px;',
    'background: #1a1a1a; color: #888; padding: 4px 8px; border-radius: 0 4px 4px 0;'
);

// ── Presence Detector ── (auto-starts silently)
// Starts after a 3s delay to let all other resources settle
if (typeof PresenceDetector !== 'undefined') {
    setTimeout(() => {
        window._presenceDetector = new PresenceDetector(socket);
        window._presenceDetector.start().catch(() => {
            console.warn('Presence detector not available — no camera or permission denied.');
        });
    }, 3000);
}


// ─────────────────────────────────────────────
// IoT & VIRTUAL MOUSE CONTROLLER FRONTEND
// ─────────────────────────────────────────────

(function initIotVirtualMouse() {
    const btnOpenIotHud = document.getElementById('btnOpenIotHud');
    const btnCloseIotHud = document.getElementById('btnCloseIotHud');
    const iotHudOverlay = document.getElementById('iotHudOverlay');
    const iotHudPanel = document.getElementById('iotHudPanel');
    
    if (!btnOpenIotHud || !iotHudOverlay) return;

    let iotState = {};
    let vmouseState = { x: 500, y: 300, mode: 'desktop' };

    // Modal Toggle
    btnOpenIotHud.addEventListener('click', () => {
        iotHudOverlay.classList.add('active');
        fetchIotDevices();
        fetchVmouseState();
    });

    btnCloseIotHud.addEventListener('click', () => {
        iotHudOverlay.classList.remove('active');
    });

    iotHudOverlay.addEventListener('click', (e) => {
        if (e.target === iotHudOverlay) {
            iotHudOverlay.classList.remove('active');
        }
    });

    // Sub-tab Navigation
    const hudTabs = document.querySelectorAll('.hud-tab');
    hudTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            hudTabs.forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.hud-tab-content').forEach(c => c.classList.remove('active'));
            
            tab.classList.add('active');
            const targetId = 'tabContent' + tab.dataset.tab.charAt(0).toUpperCase() + tab.dataset.tab.slice(1);
            const content = document.getElementById(targetId);
            if (content) {
                content.classList.add('active');
                if (tab.dataset.tab === 'floorplan') {
                    renderFloorplan();
                }
            }
        });
    });

    // Mode Toggle
    const btnModeDesktop = document.getElementById('btnModeDesktop');
    const btnModeIot = document.getElementById('btnModeIot');
    if (btnModeDesktop && btnModeIot) {
        btnModeDesktop.addEventListener('click', () => {
            btnModeDesktop.classList.add('active');
            btnModeIot.classList.remove('active');
            vmouseState.mode = 'desktop';
            socket.emit('virtual_mouse_move', { x: vmouseState.x, y: vmouseState.y, mode: 'desktop' });
        });
        btnModeIot.addEventListener('click', () => {
            btnModeIot.classList.add('active');
            btnModeDesktop.classList.remove('active');
            vmouseState.mode = 'iot_canvas';
            socket.emit('virtual_mouse_move', { x: vmouseState.x, y: vmouseState.y, mode: 'iot_canvas' });
        });
    }

    // Touchpad Control
    const vmouseTrackpad = document.getElementById('vmouseTrackpad');
    const vmouseCursorDot = document.getElementById('vmouseCursorDot');
    const vmouseCoordsLabel = document.getElementById('vmouseCoordsLabel');

    let isDragging = false;
    let lastX = 0, lastY = 0;

    function handleTrackpadMove(clientX, clientY) {
        if (!vmouseTrackpad) return;
        const rect = vmouseTrackpad.getBoundingClientRect();
        const relX = Math.max(0, Math.min(rect.width, clientX - rect.left));
        const relY = Math.max(0, Math.min(rect.height, clientY - rect.top));

        // Update dot UI inside trackpad
        if (vmouseCursorDot) {
            vmouseCursorDot.style.left = `${relX}px`;
            vmouseCursorDot.style.top = `${relY}px`;
        }

        // Map relative touch position to desktop/canvas coords (1920x1080)
        const targetX = Math.round((relX / rect.width) * 1280);
        const targetY = Math.round((relY / rect.height) * 800);

        vmouseState.x = targetX;
        vmouseState.y = targetY;

        if (vmouseCoordsLabel) {
            vmouseCoordsLabel.textContent = `Position: (${targetX}, ${targetY}) · Mode: ${vmouseState.mode}`;
        }

        socket.emit('virtual_mouse_move', { x: targetX, y: targetY, mode: vmouseState.mode });
    }

    if (vmouseTrackpad) {
        vmouseTrackpad.addEventListener('mousedown', (e) => {
            isDragging = true;
            handleTrackpadMove(e.clientX, e.clientY);
        });

        window.addEventListener('mousemove', (e) => {
            if (isDragging) {
                handleTrackpadMove(e.clientX, e.clientY);
            }
        });

        window.addEventListener('mouseup', () => {
            if (isDragging) isDragging = false;
        });

        // Touch support
        vmouseTrackpad.addEventListener('touchstart', (e) => {
            if (e.touches.length > 0) {
                isDragging = true;
                handleTrackpadMove(e.touches[0].clientX, e.touches[0].clientY);
            }
        });

        vmouseTrackpad.addEventListener('touchmove', (e) => {
            if (isDragging && e.touches.length > 0) {
                handleTrackpadMove(e.touches[0].clientX, e.touches[0].clientY);
            }
        });

        vmouseTrackpad.addEventListener('touchend', () => {
            isDragging = false;
        });
    }

    // D-Pad Controls
    const dpadButtons = {
        dpadUp: { dir: 'up', step: 50 },
        dpadDown: { dir: 'down', step: 50 },
        dpadLeft: { dir: 'left', step: 50 },
        dpadRight: { dir: 'right', step: 50 },
        dpadClick: { action: 'click' }
    };

    Object.keys(dpadButtons).forEach(id => {
        const btn = document.getElementById(id);
        if (btn) {
            btn.addEventListener('click', () => {
                const conf = dpadButtons[id];
                if (conf.action === 'click') {
                    socket.emit('virtual_mouse_click', { button: 'left' });
                } else {
                    socket.emit('virtual_mouse_dpad', { direction: conf.dir, step: conf.step });
                }
            });
        }
    });

    // Mouse Action Buttons
    const btnLeft = document.getElementById('btnVmouseLeftClick');
    const btnRight = document.getElementById('btnVmouseRightClick');
    const btnScrollUp = document.getElementById('btnVmouseScrollUp');
    const btnScrollDown = document.getElementById('btnVmouseScrollDown');

    if (btnLeft) btnLeft.addEventListener('click', () => socket.emit('virtual_mouse_click', { button: 'left' }));
    if (btnRight) btnRight.addEventListener('click', () => socket.emit('virtual_mouse_click', { button: 'right' }));
    if (btnScrollUp) btnScrollUp.addEventListener('click', () => socket.emit('virtual_mouse_move', { x: 0, y: -100, relative: true }));
    if (btnScrollDown) btnScrollDown.addEventListener('click', () => socket.emit('virtual_mouse_move', { x: 0, y: 100, relative: true }));

    // REST Fetchers
    function fetchIotDevices() {
        fetch('/api/iot/devices')
            .then(res => res.json())
            .then(devices => {
                iotState = devices;
                renderIotDevices(devices);
                renderFloorplan();
            })
            .catch(err => console.error('IoT fetch error:', err));
    }

    function fetchVmouseState() {
        fetch('/api/virtual_mouse/state')
            .then(res => res.json())
            .then(st => {
                vmouseState = st;
                updateVmouseUI(st);
            })
            .catch(err => console.error('Vmouse fetch error:', err));
    }

    // Socket listeners
    socket.on('iot_state_update', (devices) => {
        iotState = devices;
        renderIotDevices(devices);
        renderFloorplan();
    });

    socket.on('virtual_mouse_update', (st) => {
        vmouseState = st;
        updateVmouseUI(st);
        renderFloorplan();
    });

    function updateVmouseUI(st) {
        if (vmouseCoordsLabel) {
            vmouseCoordsLabel.textContent = `Position: (${st.x}, ${st.y}) · Mode: ${st.mode}`;
        }
    }

    // Render IoT Device Cards
    function renderIotDevices(devices) {
        const grid = document.getElementById('iotDeviceGrid');
        if (!grid) return;
        grid.innerHTML = '';

        Object.keys(devices).forEach(dId => {
            const dev = devices[dId];
            const card = document.createElement('div');
            card.className = 'iot-card';
            
            const isLight = dev.type === 'light';
            const isPlug = dev.type === 'plug';
            const isThermo = dev.type === 'thermostat';
            
            let extraControls = '';
            if (isLight && dev.state === 'on') {
                extraControls = `
                    <label style="font-size:11px;color:var(--text-2);">Brightness: ${dev.brightness || 100}%</label>
                    <input type="range" class="iot-card__slider" min="10" max="100" value="${dev.brightness || 100}" 
                        onchange="window._controlIot('${dId}', 'brightness', this.value)">
                `;
            } else if (isThermo) {
                extraControls = `
                    <label style="font-size:11px;color:var(--text-2);">Target Temp: ${dev.target_temp || 72}°F</label>
                    <input type="range" class="iot-card__slider" min="60" max="85" value="${dev.target_temp || 72}" 
                        onchange="window._controlIot('${dId}', 'temp', this.value)">
                `;
            }

            card.innerHTML = `
                <div class="iot-card__header">
                    <div>
                        <div class="iot-card__title">${dev.name}</div>
                        <div class="iot-card__location">📍 ${dev.location}</div>
                    </div>
                    <span style="font-size:18px;">${dev.state === 'on' ? '💡' : '🔌'}</span>
                </div>
                <div class="iot-card__controls">
                    <button class="btn-subtab ${dev.state === 'on' ? 'active' : ''}" 
                        onclick="window._controlIot('${dId}', 'toggle')">
                        ${dev.state.toUpperCase()}
                    </button>
                    <span style="font-size:11px;color:var(--accent);">${dev.type.toUpperCase()}</span>
                </div>
                ${extraControls}
            `;
            grid.appendChild(card);
        });
    }

    // Global helper for inline card event handlers
    window._controlIot = function(deviceId, action, val) {
        socket.emit('iot_control', { device_id: deviceId, action: action, value: val });
    };

    // 2D Floorplan Canvas Renderer
    function renderFloorplan() {
        const canvas = document.getElementById('iotFloorplanCanvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const w = canvas.width;
        const h = canvas.height;

        ctx.clearRect(0, 0, w, h);

        // Draw Room Grid & Boundaries
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
        ctx.lineWidth = 1;

        // Grid lines
        for (let x = 0; x < w; x += 40) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, h);
            ctx.stroke();
        }
        for (let y = 0; y < h; y += 40) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(w, y);
            ctx.stroke();
        }

        // Rooms
        ctx.strokeStyle = 'rgba(255, 106, 0, 0.3)';
        ctx.lineWidth = 2;
        
        // Living Room
        ctx.strokeRect(20, 20, 280, 160);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
        ctx.font = '11px sans-serif';
        ctx.fillText('Living Room', 30, 40);

        // Bedroom
        ctx.strokeRect(320, 20, 260, 160);
        ctx.fillText('Bedroom', 330, 40);

        // Office
        ctx.strokeRect(20, 200, 280, 150);
        ctx.fillText('Office', 30, 220);

        // Hallway
        ctx.strokeRect(320, 200, 260, 150);
        ctx.fillText('Hallway', 330, 220);

        // Render IoT Devices on Canvas
        Object.keys(iotState).forEach(dId => {
            const dev = iotState[dId];
            const pos = dev.pos || { x: 100, y: 100 };
            
            // Map pos to canvas scale
            const cx = (pos.x / 650) * w;
            const cy = (pos.y / 450) * h;

            // Draw device node
            ctx.beginPath();
            ctx.arc(cx, cy, 14, 0, Math.PI * 2);
            ctx.fillStyle = dev.state === 'on' ? 'rgba(255, 170, 0, 0.3)' : 'rgba(100, 100, 100, 0.2)';
            ctx.fill();
            ctx.strokeStyle = dev.state === 'on' ? '#ffaa00' : '#666';
            ctx.lineWidth = 2;
            ctx.stroke();

            // Label
            ctx.fillStyle = '#fff';
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(dev.name, cx, cy + 26);
        });

        // Render Virtual Mouse Cursor on Canvas
        if (vmouseState) {
            const cursorX = (vmouseState.x / 1280) * w;
            const cursorY = (vmouseState.y / 800) * h;

            // Pulse glow ring
            ctx.beginPath();
            ctx.arc(cursorX, cursorY, 12, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(255, 106, 0, 0.3)';
            ctx.fill();

            // Core dot
            ctx.beginPath();
            ctx.arc(cursorX, cursorY, 5, 0, Math.PI * 2);
            ctx.fillStyle = '#ff6a00';
            ctx.fill();
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 2;
            ctx.stroke();
        }
    }

    // Canvas click event to toggle target IoT device directly on floorplan
    const canvas = document.getElementById('iotFloorplanCanvas');
    if (canvas) {
        canvas.addEventListener('click', (e) => {
            const rect = canvas.getBoundingClientRect();
            const clickX = ((e.clientX - rect.left) / canvas.width) * 650;
            const clickY = ((e.clientY - rect.top) / canvas.height) * 450;

            Object.keys(iotState).forEach(dId => {
                const dev = iotState[dId];
                const pos = dev.pos || { x: 0, y: 0 };
                const dist = Math.hypot(clickX - pos.x, clickY - pos.y);
                if (dist <= 35) {
                    socket.emit('iot_control', { device_id: dId, action: 'toggle' });
                }
            });
        });
    }

})();

