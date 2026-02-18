/**
 * MARK — 3D Model Viewer
 * Local buffer loading (no upload delay), touch gestures, progress bar.
 */

/* global THREE */

class ModelViewer {
    constructor() {
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.model = null;
        this.overlay = null;
        this.animId = null;
        this.autoRotate = true;
        this._escH = null;
        this._resH = null;
    }

    /* Open from a URL (existing method) */
    open(url, name) {
        this._buildUI(name);
        this._initScene();
        this._loadFromURL(url, name);
        this._animate();
    }

    /* Open from a local ArrayBuffer — instant, no upload needed */
    openFromBuffer(buffer, name) {
        this._buildUI(name);
        this._initScene();
        this._loadFromBuffer(buffer, name);
        this._animate();
    }

    close() {
        if (this.animId) cancelAnimationFrame(this.animId);
        this.animId = null;
        if (this.renderer) {
            this.renderer.dispose();
            this.renderer.forceContextLoss();
        }
        if (this.controls) this.controls.dispose();
        if (this.overlay) this.overlay.remove();
        if (this._escH) document.removeEventListener('keydown', this._escH);
        if (this._resH) window.removeEventListener('resize', this._resH);
        this.scene = this.camera = this.renderer = null;
        this.controls = this.model = this.overlay = null;
    }

    /* ═══ UI ═══ */
    _buildUI(name) {
        if (this.overlay) this.close();
        var o = document.createElement('div');
        o.className = 'v3d-overlay';
        o.innerHTML =
            '<div class="v3d-toolbar">' +
            '<span class="v3d-name">' + (name || '3D Model') + '</span>' +
            '<div class="v3d-actions">' +
            '<button class="v3d-btn v3d-btn--active" id="v3dRotate">⟳ Auto Rotate</button>' +
            '<button class="v3d-btn" id="v3dWire">◇ Wireframe</button>' +
            '<button class="v3d-btn" id="v3dReset">⊙ Reset</button>' +
            '<button class="v3d-btn v3d-btn--close" id="v3dClose">✕</button>' +
            '</div>' +
            '</div>' +
            '<div class="v3d-hint">🖱 Drag: rotate · Scroll: zoom · Right-drag: pan &nbsp;|&nbsp; 📱 1-finger: rotate · Pinch: zoom · 2-finger: pan</div>' +
            '<div class="v3d-loading" id="v3dLoading">' +
            '<div class="v3d-spinner"></div>' +
            '<span id="v3dProgress">Parsing model…</span>' +
            '</div>' +
            '<canvas id="v3dCanvas"></canvas>';
        document.body.appendChild(o);
        this.overlay = o;

        var self = this;
        document.getElementById('v3dClose').onclick = function () { self.close(); };
        document.getElementById('v3dRotate').onclick = function (ev) {
            self.autoRotate = !self.autoRotate;
            if (self.controls) self.controls.autoRotate = self.autoRotate;
            ev.currentTarget.classList.toggle('v3d-btn--active', self.autoRotate);
        };
        document.getElementById('v3dWire').onclick = function (ev) {
            var on = ev.currentTarget.classList.toggle('v3d-btn--active');
            if (self.model) self.model.traverse(function (c) {
                if (c.isMesh && c.material) c.material.wireframe = on;
            });
        };
        document.getElementById('v3dReset').onclick = function () {
            if (self.controls) self.controls.reset();
        };
        this._escH = function (ev) { if (ev.key === 'Escape') self.close(); };
        document.addEventListener('keydown', this._escH);
    }

    /* ═══ Scene ═══ */
    _initScene() {
        var canvas = document.getElementById('v3dCanvas');
        var w = window.innerWidth, h = window.innerHeight;

        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x0a0a0e);

        // Camera
        this.camera = new THREE.PerspectiveCamera(45, w / h, 0.01, 1000);
        this.camera.position.set(4, 3, 5);

        // Renderer
        this.renderer = new THREE.WebGLRenderer({
            canvas: canvas,
            antialias: true,
            powerPreference: 'high-performance'
        });
        this.renderer.setSize(w, h);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.2;
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        this.renderer.outputEncoding = THREE.sRGBEncoding;

        // ── OrbitControls with full touch gesture support ──
        this.controls = new THREE.OrbitControls(this.camera, canvas);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.07;
        this.controls.autoRotate = this.autoRotate;
        this.controls.autoRotateSpeed = 1.5;
        this.controls.enablePan = true;
        this.controls.enableZoom = true;
        this.controls.enableRotate = true;
        this.controls.minDistance = 0.3;
        this.controls.maxDistance = 50;
        this.controls.rotateSpeed = 0.8;
        this.controls.zoomSpeed = 1.2;
        this.controls.panSpeed = 0.8;
        // Touch: 1-finger rotate, 2-finger dolly+pan
        this.controls.touches = {
            ONE: THREE.TOUCH.ROTATE,
            TWO: THREE.TOUCH.DOLLY_PAN
        };
        // Mouse: left=rotate, middle=dolly, right=pan
        this.controls.mouseButtons = {
            LEFT: THREE.MOUSE.ROTATE,
            MIDDLE: THREE.MOUSE.DOLLY,
            RIGHT: THREE.MOUSE.PAN
        };

        // ── Lighting ──
        this.scene.add(new THREE.AmbientLight(0xffffff, 0.6));
        var hemi = new THREE.HemisphereLight(0xffeedd, 0x080820, 0.8);
        this.scene.add(hemi);

        var dir = new THREE.DirectionalLight(0xffffff, 1.5);
        dir.position.set(5, 8, 5);
        dir.castShadow = true;
        dir.shadow.mapSize.set(1024, 1024);
        this.scene.add(dir);

        var fill = new THREE.DirectionalLight(0xff6a00, 0.3);
        fill.position.set(-5, 2, -5);
        this.scene.add(fill);

        // Floor grid
        var grid = new THREE.GridHelper(20, 40, 0x1a1a22, 0x111118);
        grid.material.opacity = 0.4;
        grid.material.transparent = true;
        this.scene.add(grid);

        // Resize
        var self = this;
        this._resH = function () {
            var w2 = window.innerWidth, h2 = window.innerHeight;
            self.camera.aspect = w2 / h2;
            self.camera.updateProjectionMatrix();
            self.renderer.setSize(w2, h2);
        };
        window.addEventListener('resize', this._resH);
    }

    /* ═══ Load from ArrayBuffer (instant — no upload) ═══ */
    _loadFromBuffer(buffer, name) {
        var ext = name.split('.').pop().toLowerCase();
        var self = this;

        // Use setTimeout to let the UI render first
        setTimeout(function () {
            try {
                var obj = null;
                if (ext === 'stl') {
                    var loader = new THREE.STLLoader();
                    var geo = loader.parse(buffer);
                    geo.computeVertexNormals();
                    var mat = new THREE.MeshStandardMaterial({
                        color: 0xff6a00, metalness: 0.35, roughness: 0.45
                    });
                    obj = new THREE.Mesh(geo, mat);
                    obj.castShadow = true;
                } else if (ext === 'obj') {
                    var dec = new TextDecoder();
                    var text = dec.decode(buffer);
                    obj = new THREE.OBJLoader().parse(text);
                } else if (ext === 'glb' || ext === 'gltf') {
                    var loader2 = new THREE.GLTFLoader();
                    var draco = new THREE.DRACOLoader();
                    draco.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.6/');
                    loader2.setDRACOLoader(draco);
                    loader2.parse(buffer, '', function (gltf) {
                        self._addModel(gltf.scene);
                        self._hideLoading();
                    }, function (err) {
                        self._showError('Failed to parse GLTF: ' + err);
                    });
                    return; // async parse
                } else {
                    self._showError('Unsupported format: .' + ext);
                    return;
                }

                if (obj) {
                    self._addModel(obj);
                    self._hideLoading();
                }
            } catch (err) {
                console.error('Parse error:', err);
                self._showError('Failed to parse model');
            }
        }, 50);
    }

    /* ═══ Load from URL (fallback) ═══ */
    _loadFromURL(url, name) {
        var ext = name.split('.').pop().toLowerCase();
        var self = this;

        var onErr = function (e) {
            console.error('Load error:', e);
            self._showError('Failed to load model');
        };

        if (ext === 'glb' || ext === 'gltf') {
            var gl = new THREE.GLTFLoader();
            var dr = new THREE.DRACOLoader();
            dr.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.6/');
            gl.setDRACOLoader(dr);
            gl.load(url, function (gltf) {
                self._addModel(gltf.scene);
                self._hideLoading();
            }, function (p) { self._showProgress(p); }, onErr);
        } else if (ext === 'obj') {
            new THREE.OBJLoader().load(url, function (o) {
                self._addModel(o);
                self._hideLoading();
            }, function (p) { self._showProgress(p); }, onErr);
        } else if (ext === 'stl') {
            new THREE.STLLoader().load(url, function (geo) {
                geo.computeVertexNormals();
                var mat = new THREE.MeshStandardMaterial({
                    color: 0xff6a00, metalness: 0.35, roughness: 0.45
                });
                var m = new THREE.Mesh(geo, mat);
                m.castShadow = true;
                self._addModel(m);
                self._hideLoading();
            }, function (p) { self._showProgress(p); }, onErr);
        } else {
            self._showError('Unsupported: .' + ext);
        }
    }

    _showProgress(p) {
        if (p.lengthComputable) {
            var pct = Math.round((p.loaded / p.total) * 100);
            var el = document.getElementById('v3dProgress');
            if (el) el.textContent = 'Loading… ' + pct + '%';
        }
    }

    _hideLoading() {
        var el = document.getElementById('v3dLoading');
        if (el) el.style.display = 'none';
    }

    _showError(msg) {
        var el = document.getElementById('v3dLoading');
        if (el) el.innerHTML = '<span style="color:#F87171">' + msg + '</span>';
    }

    /* ═══ Add model to scene ═══ */
    _addModel(obj) {
        var box = new THREE.Box3().setFromObject(obj);
        var center = box.getCenter(new THREE.Vector3());
        var size = box.getSize(new THREE.Vector3());
        var maxDim = Math.max(size.x, size.y, size.z);
        var scale = maxDim > 0 ? 3 / maxDim : 1;

        obj.position.sub(center);
        obj.scale.multiplyScalar(scale);
        obj.position.y += (size.y * scale) / 2;

        obj.traverse(function (c) {
            if (c.isMesh) {
                c.castShadow = true;
                c.receiveShadow = true;
            }
        });

        this.model = obj;
        this.scene.add(obj);

        // Frame camera on model
        var d = 4;
        this.camera.position.set(d, d * 0.7, d);
        this.controls.target.set(0, (size.y * scale) / 2, 0);
        this.controls.update();
        this.controls.saveState();

        console.log('🧊 Model loaded:', name, '| Scaled:', scale.toFixed(3));
    }

    /* ═══ Render loop ═══ */
    _animate() {
        if (!this.renderer) return;
        var self = this;
        this.animId = requestAnimationFrame(function () { self._animate(); });
        if (self.controls) self.controls.update();
        self.renderer.render(self.scene, self.camera);
    }
}

window.ModelViewer = ModelViewer;
window._viewer3d = null;
