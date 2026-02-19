/**
 * MARK — Gesture Controller
 * Real-time hand gesture detection using MediaPipe Hands.
 * Detects swipe left/right/up/down and sends to backend.
 */

class GestureController {
    constructor(socket) {
        this.socket = socket;
        this.active = false;
        this.hands = null;
        this.stream = null;
        this.videoEl = null;
        this.canvasEl = null;
        this.ctx = null;
        this.overlayEl = null;
        this.indicatorEl = null;
        this.positions = [];        // For swipe detection
        this.maxPositions = 20;
        this.minDisplacement = 0.13;
        this.minVelocity = 0.5;
        this.cooldownMs = 900;      // Swipe cooldown
        this.poseCooldownMs = 1200; // Pose gesture cooldown
        this.lastGestureTime = 0;
        this.lastPoseTime = 0;
        this.windowMs = 400;
        this._raf = null;
        this._lastLandmarks = null; // For pose analysis
    }

    async start() {
        if (this.active) return true;
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: { width: 320, height: 240, facingMode: 'user' }
            });
            this._createUI();
            this.videoEl.srcObject = this.stream;
            await this.videoEl.play();

            this.hands = new Hands({
                locateFile: (f) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${f}`
            });
            this.hands.setOptions({
                maxNumHands: 1,
                modelComplexity: 0,
                minDetectionConfidence: 0.6,
                minTrackingConfidence: 0.5
            });
            this.hands.onResults((r) => this._onResults(r));

            this.active = true;
            this._loop();
            console.log('🖐️ Gesture control started');
            return true;
        } catch (err) {
            console.error('Gesture start error:', err);
            this.stop();
            return false;
        }
    }

    stop() {
        this.active = false;
        if (this._raf) cancelAnimationFrame(this._raf);
        if (this.stream) {
            this.stream.getTracks().forEach(t => t.stop());
            this.stream = null;
        }
        if (this.overlayEl && this.overlayEl.parentNode) {
            this.overlayEl.remove();
            this.overlayEl = null;
        }
        this.positions = [];
        console.log('🖐️ Gesture control stopped');
    }

    _createUI() {
        this.overlayEl = document.createElement('div');
        this.overlayEl.className = 'gesture-preview';
        this.overlayEl.innerHTML = `
            <div class="gesture-preview__bar">
                <span class="gesture-preview__title">🖐️ Gestures</span>
                <span class="gesture-preview__indicator" id="gestureInd"></span>
            </div>
            <div class="gesture-preview__feed">
                <video id="gestureVid" autoplay playsinline muted></video>
                <canvas id="gestureCvs" width="320" height="240"></canvas>
            </div>`;
        document.body.appendChild(this.overlayEl);
        this.videoEl = document.getElementById('gestureVid');
        this.canvasEl = document.getElementById('gestureCvs');
        this.ctx = this.canvasEl.getContext('2d');
        this.indicatorEl = document.getElementById('gestureInd');
        this.videoEl.srcObject = this.stream;
    }

    async _loop() {
        if (!this.active || !this.hands || !this.videoEl) return;
        try { await this.hands.send({ image: this.videoEl }); } catch (e) { }
        if (this.active) this._raf = requestAnimationFrame(() => this._loop());
    }

    _onResults(results) {
        if (!this.ctx) return;
        const w = this.canvasEl.width, h = this.canvasEl.height;
        this.ctx.save();
        this.ctx.clearRect(0, 0, w, h);
        this.ctx.translate(w, 0);
        this.ctx.scale(-1, 1);
        this.ctx.drawImage(this.videoEl, 0, 0, w, h);
        this.ctx.restore();

        if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
            const lm = results.multiHandLandmarks[0];
            this._drawHand(lm, w, h);
            this._lastLandmarks = lm;

            // ── Swipe detection (palm motion) ──
            const palm = this._palmCenter(lm);
            this.positions.push({ x: palm.x, y: palm.y, time: Date.now() });
            if (this.positions.length > this.maxPositions) this.positions.shift();
            this._detect();

            // ── Pose/static gesture detection ──
            this._detectPose(lm);
        } else {
            this._lastLandmarks = null;
        }
    }

    _drawHand(lm, w, h) {
        const conns = [
            [0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8],
            [5, 9], [9, 10], [10, 11], [11, 12], [9, 13], [13, 14], [14, 15], [15, 16],
            [13, 17], [17, 18], [18, 19], [19, 20], [0, 17]
        ];
        this.ctx.strokeStyle = 'rgba(255,106,0,0.55)';
        this.ctx.lineWidth = 2;
        for (const [i, j] of conns) {
            this.ctx.beginPath();
            this.ctx.moveTo((1 - lm[i].x) * w, lm[i].y * h);
            this.ctx.lineTo((1 - lm[j].x) * w, lm[j].y * h);
            this.ctx.stroke();
        }
        this.ctx.fillStyle = 'rgba(255,106,0,0.85)';
        for (const p of lm) {
            this.ctx.beginPath();
            this.ctx.arc((1 - p.x) * w, p.y * h, 3, 0, Math.PI * 2);
            this.ctx.fill();
        }
    }

    _palmCenter(lm) {
        const pts = [lm[0], lm[5], lm[9], lm[13], lm[17]];
        return {
            x: pts.reduce((s, p) => s + p.x, 0) / pts.length,
            y: pts.reduce((s, p) => s + p.y, 0) / pts.length
        };
    }

    // ─────────────────────────────────────────
    // SWIPE DETECTION (motion-based)
    // ─────────────────────────────────────────

    _detect() {
        if (this.positions.length < 6) return;
        const now = Date.now();
        if (now - this.lastGestureTime < this.cooldownMs) return;

        const recent = this.positions.filter(p => p.time >= now - this.windowMs);
        if (recent.length < 4) return;

        const first = recent[0], last = recent[recent.length - 1];
        const dx = last.x - first.x;
        const dy = last.y - first.y;
        const dt = (last.time - first.time) / 1000;
        if (dt < 0.06) return;

        const ax = Math.abs(dx), ay = Math.abs(dy);
        const vx = ax / dt, vy = ay / dt;

        if (ax > this.minDisplacement && vx > this.minVelocity && ax > ay * 1.4) {
            // Camera is raw (not mirrored), so dx>0 means user swiped LEFT
            this._fire(dx > 0 ? 'swipe_left' : 'swipe_right');
        } else if (ay > this.minDisplacement && vy > this.minVelocity && ay > ax * 1.4) {
            this._fire(dy > 0 ? 'swipe_down' : 'swipe_up');
        }
    }

    // ─────────────────────────────────────────
    // POSE DETECTION (static hand poses)
    // ─────────────────────────────────────────

    _isFingerExtended(lm, tip, pip) {
        // Finger is extended if tip Y is above (less than) pip knuckle Y
        return lm[tip].y < lm[pip].y - 0.02;
    }

    _detectPose(lm) {
        const now = Date.now();
        if (now - this.lastPoseTime < this.poseCooldownMs) return;

        const indexUp = this._isFingerExtended(lm, 8, 6);
        const middleUp = this._isFingerExtended(lm, 12, 10);
        const ringUp = this._isFingerExtended(lm, 16, 14);
        const pinkyUp = this._isFingerExtended(lm, 20, 18);
        const thumbUp = this._isFingerExtended(lm, 4, 3);

        const palmCx = this._palmCenter(lm).x;

        // ── Finger to lips (🤫 Shush) ──
        // Key insight: when your hand is near your face (lips),
        // the WRIST (lm[0]) is also raised high in the frame —
        // this is what separates it from simply pointing upward
        // with the arm down. Thresholds tuned for laptop webcams
        // where lips appear at ~y=0.45–0.65 in the frame.
        const handNearCenter = palmCx > 0.25 && palmCx < 0.75;  // wide center
        const tipNearFace = lm[8].y < 0.62;                   // tip in upper 62%
        const wristRaised = lm[0].y < 0.82;                   // whole arm raised toward face
        const fingerToLips = indexUp && !middleUp && !ringUp && !pinkyUp
            && handNearCenter && tipNearFace && wristRaised;

        // ── Point (☝️) ──
        // Same finger shape but explicitly NOT in the lips-touch zone.
        // Without !fingerToLips, both conditions would always match together.
        const pointGesture = indexUp && !middleUp && !ringUp && !pinkyUp && !thumbUp
            && !fingerToLips;

        if (fingerToLips) {
            this._firePose('lips_touch', '🤫 Muting...');
        } else if (pointGesture) {
            this._firePose('point', '☝️ Focus window');
        }
    }

    _firePose(gesture, label) {
        this.lastPoseTime = Date.now();
        this.socket.emit('gesture', { type: gesture });
        if (this.indicatorEl) {
            this.indicatorEl.textContent = label;
            this.indicatorEl.classList.add('flash');
            setTimeout(() => this.indicatorEl.classList.remove('flash'), 800);
        }
        console.log('✋ Pose: ' + gesture);
    }

    _fire(gesture) {
        this.lastGestureTime = Date.now();
        this.positions = [];
        this.socket.emit('gesture', { type: gesture });

        const labels = {
            swipe_left: '← Next Space', swipe_right: '→ Prev Space',
            swipe_up: '↑ Scroll Down', swipe_down: '↓ Scroll Up'
        };
        if (this.indicatorEl) {
            this.indicatorEl.textContent = labels[gesture] || gesture;
            this.indicatorEl.classList.add('flash');
            setTimeout(() => this.indicatorEl.classList.remove('flash'), 600);
        }
        console.log('🖐️ ' + gesture);
    }
}

// Initialize globally — will be wired up in app.js
window.GestureController = GestureController;
