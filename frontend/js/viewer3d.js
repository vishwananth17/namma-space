/**
 * NammaSpace 3D - Three.js Spatial Viewport & Digital Twin Engine
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

export class Viewer3D {
  constructor(canvas) {
    this.canvas = canvas;
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.controls = null;
    this.gltfLoader = new GLTFLoader();

    // Layers & Groups
    this.venueGroup = new THREE.Group();
    this.poiGroup = new THREE.Group();
    this.pathGroup = new THREE.Group();
    this.obstacleGroup = new THREE.Group();
    this.navmeshMesh = null;

    // Interaction & State
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2(-1000, -1000);
    this.hoveredMarker = null;
    this.selectedMarker = null;
    this.activeVenue = null;
    this.isTopDown = false;
    this.tourActive = false;
    this.tourTween = null;

    // Callbacks
    this.onPOIClick = null;
    this.onPOIHover = null;

    // Performance telemetry
    this.fps = 60;
    this._frameCount = 0;
    this._lastFpsUpdate = performance.now();

    // Category Color Palette
    this.categoryColors = {
      workstation: 0x00f2fe,    // Neon Cyan
      lab_equipment: 0xa855f7,  // Electric Purple
      amenity: 0xf59e0b,        // Warm Amber
      safety: 0xef4444,         // Crimson
      exit: 0x10b981,           // Emerald Green
      default: 0x38bdf8         // Sky Blue
    };

    this._init();
  }

  _init() {
    // 1. Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0a0d14);
    this.scene.fog = new THREE.FogExp2(0x0a0d14, 0.015);

    // 2. Camera
    const aspect = this.canvas.clientWidth / this.canvas.clientHeight;
    this.camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 500);
    this.camera.position.set(0, 10, 20);

    // 3. Renderer
    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      antialias: true,
      powerPreference: 'high-performance'
    });
    this.renderer.setSize(this.canvas.clientWidth, this.canvas.clientHeight, false);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.1;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    // 4. Controls
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.05;
    this.controls.maxPolarAngle = Math.PI / 2 - 0.02; // Prevent going underground
    this.controls.minDistance = 1;
    this.controls.maxDistance = 150;
    this.controls.target.set(0, 0, 0);

    // 5. Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    this.scene.add(ambientLight);

    const sunLight = new THREE.DirectionalLight(0xdbeafe, 1.2);
    sunLight.position.set(15, 25, 10);
    sunLight.castShadow = true;
    sunLight.shadow.mapSize.width = 2048;
    sunLight.shadow.mapSize.height = 2048;
    sunLight.shadow.camera.near = 0.5;
    sunLight.shadow.camera.far = 100;
    const d = 25;
    sunLight.shadow.camera.left = -d;
    sunLight.shadow.camera.right = d;
    sunLight.shadow.camera.top = d;
    sunLight.shadow.camera.bottom = -d;
    this.scene.add(sunLight);

    const blueRimLight = new THREE.DirectionalLight(0x00f2fe, 0.4);
    blueRimLight.position.set(-15, 10, -15);
    this.scene.add(blueRimLight);

    // 6. Base Groups
    this.scene.add(this.venueGroup);
    this.scene.add(this.poiGroup);
    this.scene.add(this.pathGroup);
    this.scene.add(this.obstacleGroup);

    // 7. Event Listeners
    window.addEventListener('resize', () => this._onWindowResize());
    this.canvas.addEventListener('mousemove', (e) => this._onMouseMove(e));
    this.canvas.addEventListener('click', (e) => this._onMouseClick(e));

    // 8. Animation Loop
    this._animate();
  }

  _onWindowResize() {
    if (!this.canvas) return;
    const width = this.canvas.clientWidth;
    const height = this.canvas.clientHeight;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height, false);
  }

  _onMouseMove(event) {
    const rect = this.canvas.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    // Raycast POI markers
    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObjects(this.poiGroup.children, true);

    if (intersects.length > 0) {
      // Find top parent marker
      let obj = intersects[0].object;
      while (obj.parent && obj.parent !== this.poiGroup) {
        obj = obj.parent;
      }
      if (obj && obj.userData && obj.userData.poi) {
        if (this.hoveredMarker !== obj) {
          this.hoveredMarker = obj;
          this.canvas.style.cursor = 'pointer';
          if (this.onPOIHover) {
            this.onPOIHover(obj.userData.poi, event.clientX, event.clientY);
          }
        }
        return;
      }
    }

    if (this.hoveredMarker) {
      this.hoveredMarker = null;
      this.canvas.style.cursor = 'default';
      if (this.onPOIHover) this.onPOIHover(null);
    }
  }

  _onMouseClick(event) {
    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObjects(this.poiGroup.children, true);

    if (intersects.length > 0) {
      let obj = intersects[0].object;
      while (obj.parent && obj.parent !== this.poiGroup) {
        obj = obj.parent;
      }
      if (obj && obj.userData && obj.userData.poi) {
        this.selectPOI(obj.userData.poi.id);
        if (this.onPOIClick) {
          this.onPOIClick(obj.userData.poi);
        }
      }
    }
  }

  loadVenue(venueData, modelUrl) {
    this.activeVenue = venueData;
    this.clearAll();

    // 1. Position camera to venue spawn point
    if (venueData.spawn_point) {
      const pos = venueData.spawn_point.position;
      const target = venueData.spawn_point.target || { x: 0, y: 0, z: 0 };
      this.camera.position.set(pos.x, pos.y + 4, pos.z + 8);
      this.controls.target.set(target.x, target.y, target.z);
    }

    // 2. Setup venue ground grid & bounds box
    const bounds = venueData.bounds || {
      min: { x: -10, y: 0, z: -7.5 },
      max: { x: 10, y: 3, z: 7.5 }
    };
    const sizeX = Math.abs(bounds.max.x - bounds.min.x);
    const sizeZ = Math.abs(bounds.max.z - bounds.min.z);
    const centerX = (bounds.min.x + bounds.max.x) / 2;
    const centerZ = (bounds.min.z + bounds.max.z) / 2;

    // Architectural Ground Grid
    const gridHelper = new THREE.GridHelper(Math.max(sizeX, sizeZ) * 1.5, 30, 0x00f2fe, 0x1e293b);
    gridHelper.position.set(centerX, bounds.min.y, centerZ);
    this.venueGroup.add(gridHelper);

    // Floor platform plane
    const floorGeo = new THREE.PlaneGeometry(sizeX, sizeZ);
    const floorMat = new THREE.MeshStandardMaterial({
      color: 0x0f172a,
      roughness: 0.8,
      metalness: 0.2
    });
    const floorMesh = new THREE.Mesh(floorGeo, floorMat);
    floorMesh.rotation.x = -Math.PI / 2;
    floorMesh.position.set(centerX, bounds.min.y - 0.01, centerZ);
    floorMesh.receiveShadow = true;
    this.venueGroup.add(floorMesh);

    // 3. Load GLB Model
    return new Promise((resolve, reject) => {
      this.gltfLoader.load(
        modelUrl,
        (gltf) => {
          const model = gltf.scene;
          model.traverse((child) => {
            if (child.isMesh) {
              child.castShadow = true;
              child.receiveShadow = true;
              if (child.material) {
                child.material.side = THREE.DoubleSide;
              }
            }
          });
          this.venueGroup.add(model);
          resolve(model);
        },
        (xhr) => {
          // Progress
        },
        (error) => {
          console.warn('GLB load error or placeholder:', error);
          // Fallback procedural room walls if GLB failed
          const roomBox = new THREE.BoxGeometry(sizeX, bounds.max.y, sizeZ);
          const wireframe = new THREE.WireframeGeometry(roomBox);
          const line = new THREE.LineSegments(wireframe, new THREE.LineBasicMaterial({ color: 0x334155 }));
          line.position.set(centerX, bounds.max.y / 2, centerZ);
          this.venueGroup.add(line);
          resolve(null);
        }
      );
    });
  }

  renderPOIs(poiList) {
    // Clear existing POIs
    while (this.poiGroup.children.length > 0) {
      const child = this.poiGroup.children[0];
      this.poiGroup.remove(child);
    }

    poiList.forEach((poi) => {
      const marker = this._createPOIMarker(poi);
      this.poiGroup.add(marker);
    });
  }

  _createPOIMarker(poi) {
    const group = new THREE.Group();
    group.position.set(poi.position.x, poi.position.y || 0.8, poi.position.z);
    group.userData = { poi };

    const colorHex = this.categoryColors[poi.category] || this.categoryColors.default;

    // 1. 3D Diamond / Pin
    const pinGeo = new THREE.OctahedronGeometry(0.35, 0);
    const pinMat = new THREE.MeshStandardMaterial({
      color: colorHex,
      emissive: colorHex,
      emissiveIntensity: 0.4,
      roughness: 0.2,
      metalness: 0.8
    });
    const pinMesh = new THREE.Mesh(pinGeo, pinMat);
    pinMesh.position.y = 0.5;
    pinMesh.name = 'pinMesh';
    group.add(pinMesh);

    // 2. Vertical stem line to floor
    const stemGeo = new THREE.CylinderGeometry(0.02, 0.02, 0.5, 8);
    const stemMat = new THREE.MeshBasicMaterial({ color: colorHex, transparent: true, opacity: 0.6 });
    const stemMesh = new THREE.Mesh(stemGeo, stemMat);
    stemMesh.position.y = 0.25;
    group.add(stemMesh);

    // 3. Ground Pulsing Ring
    const ringGeo = new THREE.RingGeometry(0.2, 0.35, 24);
    const ringMat = new THREE.MeshBasicMaterial({
      color: colorHex,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.5
    });
    const ringMesh = new THREE.Mesh(ringGeo, ringMat);
    ringMesh.rotation.x = -Math.PI / 2;
    ringMesh.position.y = -(poi.position.y || 0.8) + 0.03;
    ringMesh.name = 'ringMesh';
    group.add(ringMesh);

    // 4. Billboarded Canvas Label
    const sprite = this._createTextSprite(poi.name, colorHex);
    sprite.position.y = 1.1;
    group.add(sprite);

    return group;
  }

  _createTextSprite(text, colorHex) {
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 64;
    const ctx = canvas.getContext('2d');

    // Background pill
    ctx.fillStyle = 'rgba(16, 20, 31, 0.85)';
    ctx.roundRect(10, 10, 236, 44, 12);
    ctx.fill();

    // Border
    ctx.strokeStyle = `#${colorHex.toString(16).padStart(6, '0')}`;
    ctx.lineWidth = 2.5;
    ctx.roundRect(10, 10, 236, 44, 12);
    ctx.stroke();

    // Text
    ctx.fillStyle = '#f8fafc';
    ctx.font = 'bold 20px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const truncated = text.length > 16 ? text.substring(0, 15) + '…' : text;
    ctx.fillText(truncated, 128, 32);

    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;
    const spriteMat = new THREE.SpriteMaterial({ map: texture, transparent: true });
    const sprite = new THREE.Sprite(spriteMat);
    sprite.scale.set(1.8, 0.45, 1.0);
    return sprite;
  }

  selectPOI(poiId) {
    let found = null;
    this.poiGroup.children.forEach((child) => {
      const isTarget = child.userData?.poi?.id === poiId;
      const pin = child.getObjectByName('pinMesh');
      if (pin) {
        if (isTarget) {
          pin.scale.set(1.4, 1.4, 1.4);
          pin.material.emissiveIntensity = 0.9;
          found = child;
        } else {
          pin.scale.set(1, 1, 1);
          pin.material.emissiveIntensity = 0.4;
        }
      }
    });

    if (found) {
      this.selectedMarker = found;
      this.flyTo(
        {
          x: found.position.x,
          y: found.position.y + 2.5,
          z: found.position.z + 4.5
        },
        found.position,
        800
      );
    }
  }

  renderPath(waypoints) {
    this.clearPath();
    if (!waypoints || waypoints.length < 2) return;

    // 1. Build 3D Points Elevated Above Ground
    const points = waypoints.map((wp) => new THREE.Vector3(wp.x, (wp.y || 0.0) + 0.15, wp.z));

    // Smooth curve
    const curve = new THREE.CatmullRomCurve3(points, false, 'catmullrom', 0.15);
    const curvePoints = curve.getPoints(Math.max(waypoints.length * 10, 50));

    // 2. Glowing Neon Polyline
    const lineGeo = new THREE.BufferGeometry().setFromPoints(curvePoints);
    const lineMat = new THREE.LineBasicMaterial({
      color: 0x00f2fe,
      linewidth: 4,
      transparent: true,
      opacity: 0.95
    });
    const pathLine = new THREE.Line(lineGeo, lineMat);
    this.pathGroup.add(pathLine);

    // 3. Glowing Tube for volumetric glow
    const tubeGeo = new THREE.TubeGeometry(curve, 64, 0.05, 8, false);
    const tubeMat = new THREE.MeshBasicMaterial({
      color: 0x00f2fe,
      transparent: true,
      opacity: 0.45,
      wireframe: true
    });
    const tubeMesh = new THREE.Mesh(tubeGeo, tubeMat);
    this.pathGroup.add(tubeMesh);

    // 4. Waypoint Node Markers
    waypoints.forEach((wp, index) => {
      const isStart = index === 0;
      const isGoal = index === waypoints.length - 1;
      const color = isStart ? 0x10b981 : isGoal ? 0x00f2fe : 0x64748b;
      const radius = isStart || isGoal ? 0.22 : 0.12;

      const nodeGeo = new THREE.SphereGeometry(radius, 16, 16);
      const nodeMat = new THREE.MeshStandardMaterial({
        color: color,
        emissive: color,
        emissiveIntensity: 0.8
      });
      const nodeMesh = new THREE.Mesh(nodeGeo, nodeMat);
      nodeMesh.position.set(wp.x, (wp.y || 0.0) + 0.15, wp.z);
      this.pathGroup.add(nodeMesh);
    });

    // 5. Adjust camera to frame path nicely
    const box = new THREE.Box3().setFromPoints(points);
    const center = new THREE.Vector3();
    box.getCenter(center);
    const size = new THREE.Vector3();
    box.getSize(size);
    const maxDim = Math.max(size.x, size.z, 5);

    this.flyTo(
      { x: center.x, y: center.y + maxDim * 1.1, z: center.z + maxDim * 1.1 },
      center,
      900
    );
  }

  clearPath() {
    this.stopWalkTour();
    while (this.pathGroup.children.length > 0) {
      const child = this.pathGroup.children[0];
      this.pathGroup.remove(child);
    }
  }

  startWalkTour(waypoints, onComplete) {
    if (!waypoints || waypoints.length < 2) return;
    this.stopWalkTour();
    this.tourActive = true;

    let currentIndex = 0;
    const walkSpeed = 1.6; // meters per second

    const stepToNext = () => {
      if (!this.tourActive || currentIndex >= waypoints.length - 1) {
        this.tourActive = false;
        if (onComplete) onComplete();
        return;
      }

      const current = waypoints[currentIndex];
      const next = waypoints[currentIndex + 1];
      const dx = next.x - current.x;
      const dz = next.z - current.z;
      const distance = Math.sqrt(dx * dx + dz * dz);
      const durationMs = Math.max(400, (distance / walkSpeed) * 1000);

      const startPos = {
        x: this.camera.position.x,
        y: this.camera.position.y,
        z: this.camera.position.z,
        tx: this.controls.target.x,
        ty: this.controls.target.y,
        tz: this.controls.target.z
      };

      const targetPos = {
        x: next.x - dx * 0.2,
        y: (next.y || 0.0) + 1.6, // Eye height
        z: next.z - dz * 0.2,
        tx: next.x + dx * 0.5,
        ty: (next.y || 0.0) + 1.2,
        tz: next.z + dz * 0.5
      };

      this.tourTween = new window.TWEEN.Tween(startPos)
        .to(targetPos, durationMs)
        .easing(window.TWEEN.Easing.Quadratic.InOut)
        .onUpdate(() => {
          this.camera.position.set(startPos.x, startPos.y, startPos.z);
          this.controls.target.set(startPos.tx, startPos.ty, startPos.tz);
        })
        .onComplete(() => {
          currentIndex++;
          stepToNext();
        })
        .start();
    };

    // First jump camera near start
    const first = waypoints[0];
    const second = waypoints[1];
    this.flyTo(
      { x: first.x, y: (first.y || 0.0) + 1.6, z: first.z },
      { x: second.x, y: (second.y || 0.0) + 1.2, z: second.z },
      600
    );
    setTimeout(stepToNext, 650);
  }

  stopWalkTour() {
    this.tourActive = false;
    if (this.tourTween) {
      this.tourTween.stop();
      this.tourTween = null;
    }
  }

  flyTo(position, target, duration = 800) {
    if (!window.TWEEN) {
      this.camera.position.set(position.x, position.y, position.z);
      this.controls.target.set(target.x, target.y, target.z);
      return;
    }

    const startPos = {
      x: this.camera.position.x,
      y: this.camera.position.y,
      z: this.camera.position.z,
      tx: this.controls.target.x,
      ty: this.controls.target.y,
      tz: this.controls.target.z
    };

    const targetPos = {
      x: position.x,
      y: position.y,
      z: position.z,
      tx: target.x,
      ty: target.y,
      tz: target.z
    };

    new window.TWEEN.Tween(startPos)
      .to(targetPos, duration)
      .easing(window.TWEEN.Easing.Cubic.Out)
      .onUpdate(() => {
        this.camera.position.set(startPos.x, startPos.y, startPos.z);
        this.controls.target.set(startPos.tx, startPos.ty, startPos.tz);
      })
      .start();
  }

  toggleViewMode() {
    this.isTopDown = !this.isTopDown;
    const target = this.controls.target.clone();
    if (this.isTopDown) {
      this.flyTo({ x: target.x, y: target.y + 25, z: target.z + 0.01 }, target, 700);
    } else {
      this.flyTo({ x: target.x, y: target.y + 8, z: target.z + 16 }, target, 700);
    }
    return this.isTopDown;
  }

  resetCamera() {
    if (!this.activeVenue?.spawn_point) return;
    const spawn = this.activeVenue.spawn_point;
    this.flyTo(
      { x: spawn.position.x, y: spawn.position.y + 2, z: spawn.position.z + 5 },
      spawn.target || { x: 0, y: 0, z: 0 },
      700
    );
  }

  toggleNavmeshOverlay(show, venueId, debugMapUrl) {
    if (!show) {
      if (this.navmeshMesh) {
        this.venueGroup.remove(this.navmeshMesh);
        this.navmeshMesh = null;
      }
      return;
    }

    if (this.navmeshMesh) return;

    const bounds = this.activeVenue?.bounds || {
      min: { x: -10, y: 0, z: -7.5 },
      max: { x: 10, y: 3, z: 7.5 }
    };
    const sizeX = Math.abs(bounds.max.x - bounds.min.x);
    const sizeZ = Math.abs(bounds.max.z - bounds.min.z);
    const centerX = (bounds.min.x + bounds.max.x) / 2;
    const centerZ = (bounds.min.z + bounds.max.z) / 2;

    const textureLoader = new THREE.TextureLoader();
    textureLoader.load(debugMapUrl, (texture) => {
      texture.magFilter = THREE.NearestFilter;
      const planeGeo = new THREE.PlaneGeometry(sizeX, sizeZ);
      const planeMat = new THREE.MeshBasicMaterial({
        map: texture,
        transparent: true,
        opacity: 0.6,
        side: THREE.DoubleSide
      });
      this.navmeshMesh = new THREE.Mesh(planeGeo, planeMat);
      this.navmeshMesh.rotation.x = -Math.PI / 2;
      this.navmeshMesh.position.set(centerX, bounds.min.y + 0.02, centerZ);
      this.venueGroup.add(this.navmeshMesh);
    });
  }

  renderObstacles(obstacles) {
    while (this.obstacleGroup.children.length > 0) {
      const child = this.obstacleGroup.children[0];
      this.obstacleGroup.remove(child);
    }

    if (!obstacles || obstacles.length === 0) return;

    obstacles.forEach((obs) => {
      const group = new THREE.Group();
      group.position.set(obs.x, 0.0, obs.z);

      // 1. Translucent Hazard Cylinder
      const cylGeo = new THREE.CylinderGeometry(obs.radius, obs.radius, 1.2, 24);
      const cylMat = new THREE.MeshBasicMaterial({
        color: 0xef4444,
        transparent: true,
        opacity: 0.35,
        side: THREE.DoubleSide
      });
      const cylMesh = new THREE.Mesh(cylGeo, cylMat);
      cylMesh.position.y = 0.6;
      group.add(cylMesh);

      // 2. Wireframe Warning
      const wireMat = new THREE.MeshBasicMaterial({
        color: 0xf59e0b,
        wireframe: true,
        transparent: true,
        opacity: 0.5
      });
      const wireMesh = new THREE.Mesh(cylGeo, wireMat);
      wireMesh.position.y = 0.6;
      group.add(wireMesh);

      // 3. Floor Caution Ring
      const ringGeo = new THREE.RingGeometry(obs.radius * 0.88, obs.radius, 24);
      const ringMat = new THREE.MeshBasicMaterial({
        color: 0xef4444,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.85
      });
      const ringMesh = new THREE.Mesh(ringGeo, ringMat);
      ringMesh.rotation.x = -Math.PI / 2;
      ringMesh.position.y = 0.04;
      ringMesh.name = 'hazardRing';
      group.add(ringMesh);

      // 4. Floating Warning Tag
      const sprite = this._createTextSprite(`⚠️ ${obs.name}`, 0xef4444);
      sprite.position.y = 1.4;
      group.add(sprite);

      this.obstacleGroup.add(group);
    });
  }

  clearAll() {
    this.clearPath();
    while (this.venueGroup.children.length > 0) {
      this.venueGroup.remove(this.venueGroup.children[0]);
    }
    while (this.poiGroup.children.length > 0) {
      this.poiGroup.remove(this.poiGroup.children[0]);
    }
    while (this.obstacleGroup.children.length > 0) {
      this.obstacleGroup.remove(this.obstacleGroup.children[0]);
    }
    this.navmeshMesh = null;
  }

  _animate(time) {
    requestAnimationFrame((t) => this._animate(t));

    // Update TWEEN
    if (window.TWEEN) {
      window.TWEEN.update(time);
    }

    // Gentle floating animation on POI pins
    const tSec = time * 0.002;
    this.poiGroup.children.forEach((marker, idx) => {
      const pin = marker.getObjectByName('pinMesh');
      const ring = marker.getObjectByName('ringMesh');
      if (pin) {
        pin.position.y = 0.5 + Math.sin(tSec + idx) * 0.08;
        pin.rotation.y += 0.015;
      }
      if (ring) {
        const s = 1.0 + Math.sin(tSec * 1.5 + idx) * 0.15;
        ring.scale.set(s, s, 1);
      }
    });

    // Pulse hazard obstacles
    this.obstacleGroup.children.forEach((obsGroup, idx) => {
      const ring = obsGroup.getObjectByName('hazardRing');
      if (ring) {
        const s = 1.0 + Math.sin(tSec * 2.5 + idx) * 0.08;
        ring.scale.set(s, s, 1);
      }
    });

    this.controls.update();
    this.renderer.render(this.scene, this.camera);

    // FPS Telemetry
    this._frameCount++;
    const now = performance.now();
    if (now - this._lastFpsUpdate >= 1000) {
      this.fps = Math.round((this._frameCount * 1000) / (now - this._lastFpsUpdate));
      this._frameCount = 0;
      this._lastFpsUpdate = now;
    }
  }
}
