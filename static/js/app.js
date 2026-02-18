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
    btnSavePrompt: document.getElementById('btnSavePrompt')
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
const WAKE_VARIANTS = ['mark', 'marc', 'park', 'dark', 'bark', 'marque', 'marks']; // fuzzy matching

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
    state.recognition.lang = 'en-US';
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
        const transcript = result[0].transcript;

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
        const fullText = (finalTranscript || interimTranscript).toLowerCase().trim();

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
            setTimeout(() => { state.wakeWordCooldown = false; }, 2000);

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
    const words = text.toLowerCase().split(/\s+/);
    for (const word of words) {
        // Direct match
        if (WAKE_VARIANTS.includes(word)) return true;
        // Fuzzy: check if any word starts with "mark"
        if (word.startsWith('mark')) return true;
    }
    // Also check if the whole text contains "hey mark" or "ok mark"
    if (text.includes('hey mark') || text.includes('okay mark') || text.includes('ok mark')) return true;
    return false;
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
        setTimeout(() => startWakeWordListener(), 200);
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
// TTS AUDIO PLAYBACK
// ─────────────────────────────────────────────

function playTTSAudio(base64Audio) {
    try {
        // Stop any existing audio
        if (state.currentAudio) {
            state.currentAudio.pause();
            state.currentAudio = null;
        }

        // Pause wake word listener during TTS to avoid feedback
        let wasWakeWord = state.wakeWordEnabled;
        if (wasWakeWord) {
            try { state.recognition.stop(); } catch (e) { }
            state.wakeWordListening = false;
        }

        const audioData = Uint8Array.from(atob(base64Audio), c => c.charCodeAt(0));
        const blob = new Blob([audioData], { type: 'audio/mp3' });
        const url = URL.createObjectURL(blob);

        state.currentAudio = new Audio(url);
        setOrbMode('speaking');

        // Connect to Web Audio API analyzer for audio-reactive orb
        try {
            if (!audioCtx) audioCtx = new AudioCtx();
            const source = audioCtx.createMediaElementSource(state.currentAudio);
            audioAnalyzer = audioCtx.createAnalyser();
            audioAnalyzer.fftSize = 256;
            audioAnalyzer.smoothingTimeConstant = 0.7;
            audioFreqData = new Uint8Array(audioAnalyzer.frequencyBinCount);
            source.connect(audioAnalyzer);
            audioAnalyzer.connect(audioCtx.destination);
        } catch (e) {
            console.log('Audio analyzer setup skipped:', e);
        }

        state.currentAudio.onended = () => {
            setOrbMode(state.wakeWordEnabled ? 'dormant' : 'idle');
            URL.revokeObjectURL(url);
            state.currentAudio = null;
            audioAnalyzer = null;
            audioFreqData = null;
            // Resume wake word after TTS
            if (wasWakeWord) {
                state.wakeWordEnabled = true;
                setTimeout(() => startWakeWordListener(), 500);
            }
        };

        state.currentAudio.onerror = () => {
            setOrbMode(state.wakeWordEnabled ? 'dormant' : 'idle');
            URL.revokeObjectURL(url);
            state.currentAudio = null;
            if (wasWakeWord) {
                state.wakeWordEnabled = true;
                setTimeout(() => startWakeWordListener(), 500);
            }
        };

        state.currentAudio.play().catch(err => {
            console.error('Audio playback error:', err);
            setOrbMode(state.wakeWordEnabled ? 'dormant' : 'idle');
        });
    } catch (e) {
        console.error('TTS audio error:', e);
        setOrbMode(state.wakeWordEnabled ? 'dormant' : 'idle');
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
// SETTINGS PANEL
// ─────────────────────────────────────────────

function openSettings() {
    DOM.settingsOverlay.classList.add('active');
    // Load current system prompt from server
    socket.emit('get_system_prompt');
}

function closeSettings() {
    DOM.settingsOverlay.classList.remove('active');
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
