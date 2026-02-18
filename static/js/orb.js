/**
 * MARK - 3D Orb Visualizer
 * Uses Three.js for a premium, Jarvis-like particle sphere.
 */

class OrbVisualizer {
    constructor(canvas) {
        this.canvas = canvas;
        this.width = canvas.parentElement.offsetWidth;
        this.height = canvas.parentElement.offsetHeight;

        // Scene setup
        this.scene = new THREE.Scene();
        this.camera = new THREE.PerspectiveCamera(75, this.width / this.height, 0.1, 1000);
        this.camera.position.z = 2.2;

        this.renderer = new THREE.WebGLRenderer({
            canvas: canvas,
            alpha: true,
            antialias: true,
            powerPreference: "high-performance"
        });
        this.renderer.setSize(this.width, this.height);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

        // State
        this.mode = 'idle';
        this.baseColor = new THREE.Color(0x00aaff); // Default Blue
        this.targetColor = new THREE.Color(0x00aaff);
        this.particleCount = 1800; // Dense core
        this.clock = new THREE.Clock();

        // Audio Data
        this.audioLevel = 0;
        this.audioData = new Uint8Array(0);

        this.initParticles();
        this.initOuterShell();

        // Auto-resize
        window.addEventListener('resize', () => this.resize());
        this.resize();

        this.animate = this.animate.bind(this);
        this.animate();
    }

    initParticles() {
        const geometry = new THREE.BufferGeometry();
        const positions = [];
        const originalPositions = [];
        const colors = [];
        const sizes = [];

        const color = new THREE.Color();

        for (let i = 0; i < this.particleCount; i++) {
            // Sphere distribution
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);
            const r = 0.85 + Math.random() * 0.15; // Radius variability

            const x = r * Math.sin(phi) * Math.cos(theta);
            const y = r * Math.sin(phi) * Math.sin(theta);
            const z = r * Math.cos(phi);

            positions.push(x, y, z);
            originalPositions.push(x, y, z);

            // Random initial colors (mostly base color)
            color.setHSL(0.55 + Math.random() * 0.1, 1.0, 0.6);
            colors.push(color.r, color.g, color.b);

            sizes.push(Math.random() * 1.5);
        }

        geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
        geometry.setAttribute('originalPosition', new THREE.Float32BufferAttribute(originalPositions, 3));
        geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
        geometry.setAttribute('size', new THREE.Float32BufferAttribute(sizes, 1));

        // Shader Material for glowing dots
        const material = new THREE.PointsMaterial({
            size: 0.04,
            vertexColors: true,
            map: this.createGlowTexture(),
            blending: THREE.AdditiveBlending,
            depthWrite: false,
            transparent: true,
            opacity: 0.8
        });

        this.particleSystem = new THREE.Points(geometry, material);
        this.scene.add(this.particleSystem);
    }

    initOuterShell() {
        // Subtle wireframe sphere around the core
        const geometry = new THREE.IcosahedronGeometry(1.2, 2);
        const material = new THREE.MeshBasicMaterial({
            color: 0x00aaff,
            wireframe: true,
            transparent: true,
            opacity: 0.08,
            blending: THREE.AdditiveBlending
        });
        this.shell = new THREE.Mesh(geometry, material);
        this.scene.add(this.shell);
    }

    createGlowTexture() {
        const canvas = document.createElement('canvas');
        canvas.width = 32;
        canvas.height = 32;
        const ctx = canvas.getContext('2d');
        const grad = ctx.createRadialGradient(16, 16, 0, 16, 16, 16);
        grad.addColorStop(0, 'rgba(255,255,255,1)');
        grad.addColorStop(0.4, 'rgba(255,255,255,0.4)');
        grad.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, 32, 32);
        const texture = new THREE.CanvasTexture(canvas);
        return texture;
    }

    resize() {
        if (!this.canvas.parentElement) return;
        this.width = this.canvas.parentElement.offsetWidth;
        this.height = this.canvas.parentElement.offsetHeight;
        this.camera.aspect = this.width / this.height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(this.width, this.height);
    }

    setMode(mode) {
        this.mode = mode;
        // Color Mapping
        switch (mode) {
            case 'idle':
            case 'dormant':
                this.targetColor.setHex(0x00aaff); // Cyan Blue
                break;
            case 'listening':
            case 'wakeword':
                this.targetColor.setHex(0x00ff88); // Bright Green
                break;
            case 'thinking':
                this.targetColor.setHex(0xaa00ff); // Purple
                break;
            case 'speaking':
                this.targetColor.setHex(0xffaa00); // Orange/Gold
                break;
            default:
                this.targetColor.setHex(0x00aaff);
        }
    }

    updateAudio(frequencyData) {
        this.audioData = frequencyData;
        // Calculate average volume level (0.0 to 1.0)
        let sum = 0;
        for (let i = 0; i < frequencyData.length; i++) {
            sum += frequencyData[i];
        }
        this.audioLevel = sum / (frequencyData.length * 255);
    }

    animate() {
        requestAnimationFrame(this.animate);

        const time = this.clock.getElapsedTime();
        const delta = this.clock.getDelta();

        // ── Color Transition ──
        this.baseColor.lerp(this.targetColor, 0.05);

        // ── Particle Animation ──
        const positions = this.particleSystem.geometry.attributes.position.array;
        const originals = this.particleSystem.geometry.attributes.originalPosition.array;
        const colors = this.particleSystem.geometry.attributes.color.array;

        // Rotation
        this.particleSystem.rotation.y += 0.003;
        this.particleSystem.rotation.z += 0.001;
        this.shell.rotation.y -= 0.002;

        // Pulse intensity based on mode & audio
        let pulseIntensity = 0.05;
        let speed = 1;

        if (this.mode === 'speaking') {
            pulseIntensity = 0.1 + (this.audioLevel * 1.5); // React strongly to voice
            speed = 2;
        } else if (this.mode === 'listening') {
            pulseIntensity = 0.2;
            speed = 1.5;
        } else if (this.mode === 'thinking') {
            speed = 4;
            this.particleSystem.rotation.y += 0.02; // Spin fast
        }

        // Shell Color Update
        this.shell.material.color.copy(this.baseColor);

        for (let i = 0; i < this.particleCount; i++) {
            const ix = i * 3;
            // Original coords
            const ox = originals[ix];
            const oy = originals[ix + 1];
            const oz = originals[ix + 2];

            // 1. Basic breathing (sine wave)
            let scale = 1 + Math.sin(time * 1.5 * speed + i * 0.01) * 0.05;

            // 2. Audio distortion (frequency based)
            if (this.audioData.length > 0) {
                // Map particle index to frequency band
                const band = i % this.audioData.length;
                const freqVal = this.audioData[band] / 255.0; // 0.0 to 1.0
                scale += freqVal * pulseIntensity;
            } else if (this.mode === 'wakeword' || this.mode === 'listening') {
                // Random jitter/expansion when listening
                scale += Math.sin(time * 5 + i) * 0.1;
            }

            positions[ix] = ox * scale;
            positions[ix + 1] = oy * scale;
            positions[ix + 2] = oz * scale;

            // Update colors per particle (slight variation)
            colors[ix] = this.baseColor.r + Math.sin(time + i) * 0.1;
            colors[ix + 1] = this.baseColor.g + Math.sin(time + i + 1) * 0.1;
            colors[ix + 2] = this.baseColor.b + Math.sin(time + i + 2) * 0.1;
        }

        this.particleSystem.geometry.attributes.position.needsUpdate = true;
        this.particleSystem.geometry.attributes.color.needsUpdate = true;
        this.renderer.render(this.scene, this.camera);
    }
}
