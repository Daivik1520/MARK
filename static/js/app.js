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
    wakeWordStatus: document.getElementById('wakeWordStatus')
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
// ORB VISUALIZATION — Premium Animated Orb
// ─────────────────────────────────────────────

const orbCtx = DOM.orbCanvas.getContext('2d');
// 2x resolution for retina
DOM.orbCanvas.width = 520;
DOM.orbCanvas.height = 520;
DOM.orbCanvas.style.width = '260px';
DOM.orbCanvas.style.height = '260px';

let orbAnimFrame;
let orbPhase = 0;
let wakeFlash = 0;

// Smooth interpolation state
let orbCur = { intensity: 0.1, speed: 0.015, coreAlpha: 0.15, pSpeed: 1 };
let orbTgt = { intensity: 0.1, speed: 0.015, coreAlpha: 0.15, pSpeed: 1 };

// Web Audio API analyzer (connected during TTS playback)
let audioAnalyzer = null;
let audioFreqData = null;

// Particle system — 40 tiny orbiting light points
const PARTICLES = [];
for (let i = 0; i < 40; i++) {
    PARTICLES.push({
        a: (i / 40) * Math.PI * 2,
        r: 0.85 + Math.random() * 0.55,
        s: (0.002 + Math.random() * 0.004) * (Math.random() > 0.5 ? 1 : -1),
        size: 0.8 + Math.random() * 1.4,
        op: 0.15 + Math.random() * 0.35,
        ph: Math.random() * Math.PI * 2,
        w: 0.02 + Math.random() * 0.04
    });
}

function _lerp(a, b, t) { return a + (b - a) * t; }

function _audioLevel() {
    if (!audioAnalyzer || !audioFreqData) return 0;
    try {
        audioAnalyzer.getByteFrequencyData(audioFreqData);
        let s = 0;
        for (let i = 0; i < audioFreqData.length; i++) s += audioFreqData[i];
        return s / (audioFreqData.length * 255);
    } catch (e) { return 0; }
}

function _audioBands() {
    if (!audioAnalyzer || !audioFreqData) return [0, 0, 0, 0];
    try {
        audioAnalyzer.getByteFrequencyData(audioFreqData);
        const n = audioFreqData.length, q = Math.floor(n / 4), b = [0, 0, 0, 0];
        for (let i = 0; i < 4; i++) {
            let s = 0;
            for (let j = i * q; j < (i + 1) * q; j++) s += audioFreqData[j];
            b[i] = s / (q * 255);
        }
        return b;
    } catch (e) { return [0, 0, 0, 0]; }
}

function setOrbMode(mode) {
    state.orbMode = mode;
    const labels = {
        dormant: ['D O R M A N T', 'Say "MARK" to activate'],
        idle: ['I D L E', 'Awaiting your command'],
        wakeword: ['A C T I V A T E D', 'Wake word detected!'],
        listening: ['L I S T E N I N G', 'I\'m all ears, sir'],
        thinking: ['P R O C E S S I N G', 'Analyzing your request...'],
        speaking: ['S P E A K I N G', 'Delivering response']
    };
    const [s, sub] = labels[mode] || labels.idle;
    DOM.orbStatus.textContent = s;
    DOM.orbSubtext.textContent = sub;

    switch (mode) {
        case 'dormant': orbTgt = { intensity: 0.05, speed: 0.008, coreAlpha: 0.08, pSpeed: 0.3 }; break;
        case 'wakeword': orbTgt = { intensity: 0.6, speed: 0.1, coreAlpha: 0.7, pSpeed: 4 }; wakeFlash = 1; break;
        case 'listening': orbTgt = { intensity: 0.35, speed: 0.05, coreAlpha: 0.4, pSpeed: 2.5 }; break;
        case 'thinking': orbTgt = { intensity: 0.3, speed: 0.07, coreAlpha: 0.35, pSpeed: 3 }; break;
        case 'speaking': orbTgt = { intensity: 0.45, speed: 0.04, coreAlpha: 0.5, pSpeed: 2 }; break;
        default: orbTgt = { intensity: 0.15, speed: 0.02, coreAlpha: 0.2, pSpeed: 1 };
    }
}

function drawOrb() {
    const w = DOM.orbCanvas.width, h = DOM.orbCanvas.height;
    const cx = w / 2, cy = h / 2;
    const LR = 0.04;

    // Smooth lerp towards target
    orbCur.intensity = _lerp(orbCur.intensity, orbTgt.intensity, LR);
    orbCur.speed = _lerp(orbCur.speed, orbTgt.speed, LR);
    orbCur.coreAlpha = _lerp(orbCur.coreAlpha, orbTgt.coreAlpha, LR);
    orbCur.pSpeed = _lerp(orbCur.pSpeed, orbTgt.pSpeed, LR);

    let intensity = orbCur.intensity;
    let coreAlpha = orbCur.coreAlpha;

    // Audio reactivity
    let aLvl = 0, aBands = [0, 0, 0, 0];
    if (state.orbMode === 'speaking') {
        aLvl = _audioLevel();
        aBands = _audioBands();
        intensity += aLvl * 0.6;
        coreAlpha += aLvl * 0.4;
    }

    orbPhase += orbCur.speed;
    orbCtx.clearRect(0, 0, w, h);
    const R = 150;

    // Wake flash decay
    if (wakeFlash > 0) {
        intensity += wakeFlash * 0.5;
        coreAlpha += wakeFlash * 0.4;
        wakeFlash *= 0.92;
        if (wakeFlash < 0.01) wakeFlash = 0;
    }

    // ── Outer glow ──
    const g1 = orbCtx.createRadialGradient(cx, cy, R * 0.3, cx, cy, R * (1.8 + intensity * 0.5));
    g1.addColorStop(0, `rgba(255,106,0,${0.08 + intensity * 0.12})`);
    g1.addColorStop(0.5, `rgba(255,80,0,${0.03 + intensity * 0.05})`);
    g1.addColorStop(1, 'rgba(0,0,0,0)');
    orbCtx.fillStyle = g1;
    orbCtx.fillRect(0, 0, w, h);

    // ── Wake pulse rings ──
    if (wakeFlash > 0.05) {
        for (let r = 0; r < 3; r++) {
            const pr = R * (1.1 + (1 - wakeFlash) * 2 + r * 0.15);
            orbCtx.strokeStyle = `rgba(255,200,50,${Math.max(0, wakeFlash - r * 0.1) * 0.4})`;
            orbCtx.lineWidth = 2.5 - r * 0.5;
            orbCtx.beginPath();
            orbCtx.arc(cx, cy, pr, 0, Math.PI * 2);
            orbCtx.stroke();
        }
    }

    // ── Orbiting particles ──
    for (const p of PARTICLES) {
        p.a += p.s * orbCur.pSpeed;
        const wobble = Math.sin(orbPhase * 3 + p.ph) * p.w;
        const pr = R * (p.r + wobble);
        let szMul = 1, aBst = 0;
        if (state.orbMode === 'speaking' && aLvl > 0) {
            const b = aBands[Math.floor(Math.abs(p.a) * 2) % 4];
            szMul = 1 + b * 3;
            aBst = b * 0.4;
        }
        const px = cx + Math.cos(p.a) * pr;
        const py = cy + Math.sin(p.a) * pr;
        const sz = p.size * szMul * (0.8 + intensity);
        const al = Math.min(1, p.op + intensity * 0.2 + aBst);

        const pg = orbCtx.createRadialGradient(px, py, 0, px, py, sz * 3);
        pg.addColorStop(0, `rgba(255,160,40,${al})`);
        pg.addColorStop(0.5, `rgba(255,106,0,${al * 0.3})`);
        pg.addColorStop(1, 'rgba(255,80,0,0)');
        orbCtx.fillStyle = pg;
        orbCtx.beginPath();
        orbCtx.arc(px, py, sz * 3, 0, Math.PI * 2);
        orbCtx.fill();

        orbCtx.fillStyle = `rgba(255,220,150,${al * 0.8})`;
        orbCtx.beginPath();
        orbCtx.arc(px, py, sz * 0.6, 0, Math.PI * 2);
        orbCtx.fill();
    }

    // ── Main morphing orb (7 layers, 5-harmonic noise) ──
    for (let i = 7; i >= 0; i--) {
        const t = i / 7;
        const ma = intensity * (1 - t * 0.4);
        const lr = R * (0.3 + t * 0.7);

        orbCtx.beginPath();
        for (let j = 0; j <= 180; j++) {
            const ang = (j / 180) * Math.PI * 2;
            let d = 0;
            d += Math.sin(ang * 2 + orbPhase * 1.1) * ma * lr * 0.12;
            d += Math.cos(ang * 3 + orbPhase * 0.8) * ma * lr * 0.08;
            d += Math.sin(ang * 5 + orbPhase * 1.5) * ma * lr * 0.06;
            d += Math.cos(ang * 7 + orbPhase * 0.6) * ma * lr * 0.04;
            d += Math.sin(ang * 11 + orbPhase * 2.0) * ma * lr * 0.02;
            if (state.orbMode === 'speaking' && aLvl > 0) {
                d += aBands[Math.floor((j / 180) * 4) % 4] * lr * 0.25;
            }
            const x = cx + Math.cos(ang) * (lr + d);
            const y = cy + Math.sin(ang) * (lr + d);
            j === 0 ? orbCtx.moveTo(x, y) : orbCtx.lineTo(x, y);
        }
        orbCtx.closePath();

        const ox = Math.sin(orbPhase * 0.5) * lr * 0.15;
        const oy = Math.cos(orbPhase * 0.7) * lr * 0.15;
        const gr = orbCtx.createRadialGradient(cx + ox, cy + oy, 0, cx, cy, lr * 1.3);
        const bo = 0.08 + t * 0.18 + intensity * 0.1;
        const hue = 25 + t * 12 + Math.sin(orbPhase * 0.3) * 5;
        gr.addColorStop(0, `hsla(${hue + 10},100%,${60 + t * 10}%,${bo})`);
        gr.addColorStop(0.4, `hsla(${hue},100%,${50 + t * 10}%,${bo * 0.7})`);
        gr.addColorStop(0.8, `hsla(${hue - 5},100%,${40 + t * 10}%,${bo * 0.3})`);
        gr.addColorStop(1, 'hsla(15,100%,20%,0)');
        orbCtx.fillStyle = gr;
        orbCtx.fill();
    }

    // ── Inner core ──
    const cp = 0.9 + 0.1 * Math.sin(orbPhase * 3);
    const cr = R * 0.35 * cp;
    const cg = orbCtx.createRadialGradient(cx, cy, 0, cx, cy, cr);
    cg.addColorStop(0, `rgba(255,230,180,${coreAlpha * 0.9})`);
    cg.addColorStop(0.3, `rgba(255,180,80,${coreAlpha * 0.5})`);
    cg.addColorStop(0.7, `rgba(255,120,30,${coreAlpha * 0.2})`);
    cg.addColorStop(1, 'rgba(255,80,0,0)');
    orbCtx.fillStyle = cg;
    orbCtx.beginPath();
    orbCtx.arc(cx, cy, cr, 0, Math.PI * 2);
    orbCtx.fill();

    // ── Specular highlight ──
    const sg = orbCtx.createRadialGradient(cx - R * 0.25, cy - R * 0.3, 0, cx - R * 0.1, cy - R * 0.15, R * 0.5);
    sg.addColorStop(0, `rgba(255,255,255,${0.03 + intensity * 0.05})`);
    sg.addColorStop(1, 'rgba(255,255,255,0)');
    orbCtx.fillStyle = sg;
    orbCtx.beginPath();
    orbCtx.arc(cx, cy, R, 0, Math.PI * 2);
    orbCtx.fill();

    // ── Dormant: breathing rings ──
    if (state.orbMode === 'dormant') {
        const b1 = 0.5 + 0.5 * Math.sin(orbPhase * 1.5);
        orbCtx.strokeStyle = `rgba(255,106,0,${0.04 + b1 * 0.08})`;
        orbCtx.lineWidth = 1.5;
        orbCtx.beginPath();
        orbCtx.arc(cx, cy, R * (1.05 + b1 * 0.2), 0, Math.PI * 2);
        orbCtx.stroke();
        const b2 = 0.5 + 0.5 * Math.sin(orbPhase * 0.8 + 1);
        orbCtx.strokeStyle = `rgba(255,106,0,${0.02 + b2 * 0.04})`;
        orbCtx.lineWidth = 1;
        orbCtx.beginPath();
        orbCtx.arc(cx, cy, R * (1.15 + b2 * 0.25), 0, Math.PI * 2);
        orbCtx.stroke();
    }

    // ── Thinking: rotating arcs ──
    if (state.orbMode === 'thinking') {
        for (let a = 0; a < 3; a++) {
            const as = orbPhase * 2 + a * Math.PI * 2 / 3;
            orbCtx.strokeStyle = `rgba(255,180,50,${0.15 + a * 0.05})`;
            orbCtx.lineWidth = 2;
            orbCtx.beginPath();
            orbCtx.arc(cx, cy, R * (1.08 + a * 0.06), as, as + 0.4 + Math.sin(orbPhase * 3 + a) * 0.2);
            orbCtx.stroke();
        }
    }

    // ── Speaking: audio-reactive pulsing rings ──
    if (state.orbMode === 'speaking' && aLvl > 0.01) {
        for (let r = 0; r < 3; r++) {
            const rr = R * (1.1 + r * 0.12 + aBands[r] * 0.3);
            orbCtx.strokeStyle = `rgba(255,${150 + r * 30},${50 + r * 20},${0.08 + aBands[r] * 0.25})`;
            orbCtx.lineWidth = 1.5 + aBands[r] * 3;
            orbCtx.beginPath();
            orbCtx.arc(cx, cy, rr, 0, Math.PI * 2);
            orbCtx.stroke();
        }
    }

    orbAnimFrame = requestAnimationFrame(drawOrb);
}

// Start orb animation
drawOrb();




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
document.querySelectorAll('.quick-action').forEach(btn => {
    btn.addEventListener('click', () => {
        sendMessage(btn.dataset.cmd);
    });
});

// ─────────────────────────────────────────────
// INIT
// ─────────────────────────────────────────────

initSpeechRecognition();
console.log('%c M.A.R.K. %c AI System Controller %c Wake Word Ready ',
    'background: #FF6A00; color: #000; font-weight: 900; padding: 4px 8px; border-radius: 4px 0 0 4px;',
    'background: #111; color: #FF6A00; font-weight: 600; padding: 4px 8px;',
    'background: #1a1a1a; color: #888; padding: 4px 8px; border-radius: 0 4px 4px 0;'
);
