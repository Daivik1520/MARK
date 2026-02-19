/**
 * MARK — Presence Detector
 * Uses MediaPipe FaceDetection to detect if the user is at their desk.
 * Emits socket event 'presence' when user leaves or returns.
 */

class PresenceDetector {
    constructor(socket) {
        this.socket = socket;
        this.active = false;
        this.detector = null;
        this.stream = null;
        this.videoEl = null;
        this._raf = null;

        // State tracking
        this.isPresent = true;
        this.lastSeenTime = Date.now();
        this.absentThresholdMs = 30 * 1000;   // 30s before "away"
        this.checkIntervalMs = 1500;          // check every 1.5s (low CPU)
        this._intervalId = null;
    }

    async start() {
        if (this.active) return;
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: { width: 320, height: 240, facingMode: 'user' }
            });

            this.videoEl = document.createElement('video');
            this.videoEl.srcObject = this.stream;
            this.videoEl.autoplay = true;
            this.videoEl.muted = true;
            this.videoEl.playsInline = true;
            this.videoEl.style.display = 'none';
            document.body.appendChild(this.videoEl);
            await this.videoEl.play();

            this.detector = new FaceDetection({
                locateFile: (f) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_detection/${f}`
            });
            this.detector.setOptions({
                model: 'short',
                minDetectionConfidence: 0.5
            });
            this.detector.onResults((r) => this._onResults(r));

            this.active = true;
            // Run inference on an interval rather than every frame (saves CPU)
            this._intervalId = setInterval(() => this._tick(), this.checkIntervalMs);
            console.log('👤 Presence detection started');
        } catch (err) {
            console.warn('Presence detector: could not start -', err.message);
        }
    }

    stop() {
        this.active = false;
        if (this._intervalId) clearInterval(this._intervalId);
        if (this.stream) {
            this.stream.getTracks().forEach(t => t.stop());
            this.stream = null;
        }
        if (this.videoEl && this.videoEl.parentNode) {
            this.videoEl.remove();
            this.videoEl = null;
        }
        console.log('👤 Presence detection stopped');
    }

    async _tick() {
        if (!this.active || !this.detector || !this.videoEl) return;
        try {
            await this.detector.send({ image: this.videoEl });
        } catch (e) { /* ignore frame errors */ }
    }

    _onResults(results) {
        const faceDetected = results.detections && results.detections.length > 0;

        if (faceDetected) {
            this.lastSeenTime = Date.now();
            if (!this.isPresent) {
                // User returned
                this.isPresent = true;
                console.log('👤 User returned');
                this.socket.emit('presence', { present: true });
            }
        } else {
            const awayMs = Date.now() - this.lastSeenTime;
            if (awayMs >= this.absentThresholdMs && this.isPresent) {
                // User has been away long enough
                this.isPresent = false;
                console.log(`👤 User away for ${Math.round(awayMs / 1000)}s`);
                this.socket.emit('presence', { present: false });
            }
        }
    }
}

window.PresenceDetector = PresenceDetector;
