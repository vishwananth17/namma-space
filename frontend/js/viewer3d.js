/**
 * NammaSpace 3D — Google Maps Indoor Viewport & Spatial Engine
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

    // Scene Groups
    this.venueGroup = new THREE.Group();
    this.poiGroup = new THREE.Group();
    this.pathGroup = new THREE.Group();
    this.obstacleGroup = new THREE.Group();
    this.userDotGroup = new THREE.Group();
    this.destinationPinGroup = new THREE.Group();
    this.navmeshMesh = null;

    // Interaction & State
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2(-1000, -1000);
    this.hoveredMarker = null;
    this.selectedMarker = null;
    this.activeVenue = null;
    this.isTopDown = false;
    this.navigationActive = false;
    this.navTween = null;

    // User Blue Dot ("You Are Here")
    this.userPos = { x: 0.0, y: 0.1, z: 2.0, headingDeg: 0 };
    this.userHeadingRad = 0;

    // Live Walking Sensor & Pedometer Tracking
    this.liveTrackingActive = false;
    this.stepCount = 0;
    this.lastStepTimestamp = 0;
    this.activeRouteWaypoints = null;
    this.activeRouteIndex = 0;

    // Callbacks
    this.onPOIClick = null;
    this.onPOIHover = null;
    this.onFloorClick = null;
    this.onCameraRotate = null;
    this.onUserWalkStep = null;
    this.onHeadingChange = null;

    // Category Colors (Google Maps style)
    this.categoryColors = {
      workstation: 0x1a73e8,   // Google Blue
      lab_equipment: 0x9334e6, // Purple
      amenity: 0xf29900,       // Warm Amber (Coffee/Food)
      safety: 0xe52592,        // Pink/Red (First Aid)
      exit: 0x0f9d58,          // Google Green
      default: 0x1a73e8
    };

    this._init();
  }

  _init() {
    // 1. Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x12151c);
    this.scene.fog = new THREE.FogExp2(0x12151c, 0.018);

    // 2. Camera
    const aspect = this.canvas.clientWidth / this.canvas.clientHeight;
    this.camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 500);
    this.camera.position.set(0, 14, 18);

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
    this.renderer.toneMappingExposure = 1.15;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    // 4. Controls
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.06;
    this.controls.maxPolarAngle = Math.PI / 2 - 0.02;
    this.controls.minDistance = 1;
    this.controls.maxDistance = 120;
    this.controls.target.set(0, 0, 0);

    // 5. Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.85);
    this.scene.add(ambientLight);

    const sun = new THREE.DirectionalLight(0xffffff, 1.1);
    sun.position.set(12, 24, 10);
    sun.castShadow = true;
    sun.shadow.mapSize.width = 2048;
    sun.shadow.mapSize.height = 2048;
    this.scene.add(sun);

    const softFill = new THREE.DirectionalLight(0x8ab4f8, 0.45);
    softFill.position.set(-15, 12, -15);
    this.scene.add(softFill);

    // 6. Base Groups
    this.scene.add(this.venueGroup);
    this.scene.add(this.poiGroup);
    this.scene.add(this.pathGroup);
    this.scene.add(this.obstacleGroup);
    this.scene.add(this.userDotGroup);
    this.scene.add(this.destinationPinGroup);

    // 7. Initialize User Blue Dot
    this._createUserBlueDot();

    // 8. Event Listeners
    window.addEventListener('resize', () => this._onWindowResize());
    this.canvas.addEventListener('mousemove', (e) => this._onMouseMove(e));
    this.canvas.addEventListener('click', (e) => this._onMouseClick(e));
    this._setupSensorAndKeyboardControls();

    // 9. Animation Loop
    this._animate();
  }

  _setupSensorAndKeyboardControls() {
    // 1. Device Orientation (Physical Phone Compass)
    window.addEventListener('deviceorientation', (e) => {
      let heading = null;
      if (e.webkitCompassHeading !== undefined) {
        heading = e.webkitCompassHeading;
      } else if (e.alpha !== null) {
        heading = (360 - e.alpha) % 360;
      }
      if (heading !== null && Math.abs(heading - this.userPos.headingDeg) > 1.5) {
        this.setUserPosition(this.userPos.x, this.userPos.z, heading);
        if (this.onHeadingChange) this.onHeadingChange(heading);
      }
    });

    // 2. Device Motion (Pedestrian Step Detector)
    window.addEventListener('devicemotion', (e) => {
      if (!this.liveTrackingActive) return;
      const acc = e.accelerationIncludingGravity || e.acceleration;
      if (!acc) return;
      const mag = Math.hypot(acc.x || 0, acc.y || 0, acc.z || 0);
      const now = performance.now();
      // Heel-strike acceleration spike threshold (approx 12.2 m/s² with gravity)
      if (mag > 12.2 && (now - this.lastStepTimestamp) > 340) {
        this.lastStepTimestamp = now;
        this.stepCount++;
        this.walkForward(0.7);
      }
    });

    // 3. Desktop / Laptop Keyboard Controls (WASD / Arrows)
    window.addEventListener('keydown', (e) => {
      // Do not trigger if typing in search input
      if (document.activeElement?.tagName === 'INPUT') return;

      if (e.code === 'KeyW' || e.code === 'ArrowUp') {
        e.preventDefault();
        this.walkForward(0.65);
      } else if (e.code === 'KeyS' || e.code === 'ArrowDown') {
        e.preventDefault();
        this.walkForward(-0.65);
      } else if (e.code === 'KeyA' || e.code === 'ArrowLeft') {
        e.preventDefault();
        this.turnHeading(-15);
      } else if (e.code === 'KeyD' || e.code === 'ArrowRight') {
        e.preventDefault();
        this.turnHeading(15);
      }
    });
  }

  walkForward(distance = 0.65) {
    let targetX = this.userPos.x;
    let targetZ = this.userPos.z;

    if (this.activeRouteWaypoints && this.activeRouteWaypoints.length > 1) {
      // Advance along active navigation route
      const wps = this.activeRouteWaypoints;
      let nextWp = wps[this.activeRouteIndex + 1];
      if (!nextWp) nextWp = wps[wps.length - 1];

      const dx = nextWp.x - this.userPos.x;
      const dz = nextWp.z - this.userPos.z;
      const distToNext = Math.hypot(dx, dz);

      if (distToNext <= Math.abs(distance)) {
        targetX = nextWp.x;
        targetZ = nextWp.z;
        if (this.activeRouteIndex < wps.length - 2) {
          this.activeRouteIndex++;
        }
      } else {
        const ratio = distance / distToNext;
        targetX += dx * ratio;
        targetZ += dz * ratio;
      }

      const rad = Math.atan2(dx, -dz);
      const headingDeg = (THREE.MathUtils.radToDeg(rad) + 360) % 360;
      this.setUserPosition(targetX, targetZ, headingDeg);
    } else {
      // Free roaming in current heading direction
      const rad = THREE.MathUtils.degToRad(this.userPos.headingDeg || 0);
      targetX += Math.sin(rad) * distance;
      targetZ -= Math.cos(rad) * distance;
      this.setUserPosition(targetX, targetZ, this.userPos.headingDeg);
    }

    // Follow camera smoothly
    const dX = targetX - this.controls.target.x;
    const dZ = targetZ - this.controls.target.z;
    this.camera.position.x += dX;
    this.camera.position.z += dZ;
    this.controls.target.set(targetX, 0.2, targetZ);

    if (this.onUserWalkStep) {
      this.onUserWalkStep(this.userPos, this.stepCount);
    }
  }

  turnHeading(degDelta) {
    const newHeading = ((this.userPos.headingDeg || 0) + degDelta + 360) % 360;
    this.setUserPosition(this.userPos.x, this.userPos.z, newHeading);
  }

  async toggleLiveTracking() {
    if (this.liveTrackingActive) {
      this.liveTrackingActive = false;
      return false;
    }

    // Request iOS orientation permission if required
    if (typeof DeviceOrientationEvent !== 'undefined' && typeof DeviceOrientationEvent.requestPermission === 'function') {
      try {
        const response = await DeviceOrientationEvent.requestPermission();
        if (response !== 'granted') {
          console.warn('Motion sensor permission denied by user.');
        }
      } catch (err) {
        console.warn('Error requesting device orientation permission:', err);
      }
    }

    this.liveTrackingActive = true;
    this.stepCount = 0;
    return true;
  }

  _createUserBlueDot() {
    // 1. Central Core Blue Dot
    const dotGeo = new THREE.SphereGeometry(0.24, 24, 24);
    const dotMat = new THREE.MeshStandardMaterial({
      color: 0x1a73e8,
      emissive: 0x1a73e8,
      emissiveIntensity: 0.5,
      roughness: 0.2
    });
    const dotMesh = new THREE.Mesh(dotGeo, dotMat);
    dotMesh.position.y = 0.25;
    this.userDotGroup.add(dotMesh);

    // White Outer Ring
    const whiteRingGeo = new THREE.RingGeometry(0.25, 0.32, 32);
    const whiteRingMat = new THREE.MeshBasicMaterial({ color: 0xffffff, side: THREE.DoubleSide });
    const whiteRing = new THREE.Mesh(whiteRingGeo, whiteRingMat);
    whiteRing.rotation.x = -Math.PI / 2;
    whiteRing.position.y = 0.03;
    this.userDotGroup.add(whiteRing);

    // 2. Pulsing Radar Floor Ring
    const pulseGeo = new THREE.RingGeometry(0.3, 0.9, 32);
    const pulseMat = new THREE.MeshBasicMaterial({
      color: 0x1a73e8,
      transparent: true,
      opacity: 0.4,
      side: THREE.DoubleSide
    });
    const pulseRing = new THREE.Mesh(pulseGeo, pulseMat);
    pulseRing.rotation.x = -Math.PI / 2;
    pulseRing.position.y = 0.02;
    pulseRing.name = 'userPulseRing';
    this.userDotGroup.add(pulseRing);

    // 3. Directional Heading Flashlight Cone
    const coneShape = new THREE.Shape();
    coneShape.moveTo(0, 0);
    coneShape.lineTo(-0.7, 2.2);
    coneShape.lineTo(0.7, 2.2);
    coneShape.closePath();
    const coneGeo = new THREE.ShapeGeometry(coneShape);
    const coneMat = new THREE.MeshBasicMaterial({
      color: 0x4285f4,
      transparent: true,
      opacity: 0.25,
      side: THREE.DoubleSide
    });
    const headingCone = new THREE.Mesh(coneGeo, coneMat);
    headingCone.rotation.x = -Math.PI / 2;
    headingCone.position.y = 0.025;
    headingCone.name = 'headingCone';
    this.userDotGroup.add(headingCone);

    this.userDotGroup.position.set(this.userPos.x, this.userPos.y, this.userPos.z);
  }

  setUserPosition(x, z, headingDeg = null) {
    this.userPos.x = x;
    this.userPos.z = z;
    this.userDotGroup.position.set(x, 0.05, z);

    if (headingDeg !== null) {
      this.userPos.headingDeg = headingDeg;
      const cone = this.userDotGroup.getObjectByName('headingCone');
      if (cone) {
        cone.rotation.z = -THREE.MathUtils.degToRad(headingDeg);
      }
    }
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

    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObjects(this.poiGroup.children, true);

    if (intersects.length > 0) {
      let obj = intersects[0].object;
      while (obj.parent && obj.parent !== this.poiGroup) {
        obj = obj.parent;
      }
      if (obj?.userData?.poi) {
        if (this.hoveredMarker !== obj) {
          this.hoveredMarker = obj;
          this.canvas.style.cursor = 'pointer';
          if (this.onPOIHover) this.onPOIHover(obj.userData.poi, event.clientX, event.clientY);
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

    // 1. Check POI Click
    const poiIntersects = this.raycaster.intersectObjects(this.poiGroup.children, true);
    if (poiIntersects.length > 0) {
      let obj = poiIntersects[0].object;
      while (obj.parent && obj.parent !== this.poiGroup) {
        obj = obj.parent;
      }
      if (obj?.userData?.poi) {
        this.selectPOI(obj.userData.poi.id);
        if (this.onPOIClick) this.onPOIClick(obj.userData.poi);
        return;
      }
    }

    // 2. Check Floor Click -> Move User Blue Dot!
    const floorIntersects = this.raycaster.intersectObjects(this.venueGroup.children, true);
    if (floorIntersects.length > 0) {
      const pt = floorIntersects[0].point;
      this.setUserPosition(pt.x, pt.z);
      if (this.onFloorClick) this.onFloorClick({ x: pt.x, z: pt.z });
    }
  }

  loadVenue(venueData, modelUrl) {
    this.activeVenue = venueData;
    this.clearAll();

    // Spawn camera
    if (venueData.spawn_point) {
      const pos = venueData.spawn_point.position;
      const target = venueData.spawn_point.target || { x: 0, y: 0, z: 0 };
      this.camera.position.set(pos.x, pos.y + 6, pos.z + 9);
      this.controls.target.set(target.x, target.y, target.z);

      // Default blue dot at spawn location
      this.setUserPosition(pos.x, pos.z, 0);
    }

    const bounds = venueData.bounds || {
      min: { x: -10, y: 0, z: -7.5 },
      max: { x: 10, y: 3, z: 7.5 }
    };
    const sizeX = Math.abs(bounds.max.x - bounds.min.x);
    const sizeZ = Math.abs(bounds.max.z - bounds.min.z);
    const centerX = (bounds.min.x + bounds.max.x) / 2;
    const centerZ = (bounds.min.z + bounds.max.z) / 2;

    // Stylized Floor Plane (Google Maps subtle dark ground)
    const floorGeo = new THREE.PlaneGeometry(sizeX * 1.5, sizeZ * 1.5);
    const floorMat = new THREE.MeshStandardMaterial({
      color: 0x161a23,
      roughness: 0.9,
      metalness: 0.1
    });
    const floorMesh = new THREE.Mesh(floorGeo, floorMat);
    floorMesh.rotation.x = -Math.PI / 2;
    floorMesh.position.set(centerX, bounds.min.y - 0.01, centerZ);
    floorMesh.receiveShadow = true;
    this.venueGroup.add(floorMesh);

    // Subtle Architectural Grid
    const grid = new THREE.GridHelper(Math.max(sizeX, sizeZ) * 1.5, 30, 0x282e3d, 0x1c212d);
    grid.position.set(centerX, bounds.min.y, centerZ);
    this.venueGroup.add(grid);

    // Load 3D Model
    return new Promise((resolve) => {
      this.gltfLoader.load(
        modelUrl,
        (gltf) => {
          const model = gltf.scene;
          model.traverse((child) => {
            if (child.isMesh) {
              child.castShadow = true;
              child.receiveShadow = true;
            }
          });
          this.venueGroup.add(model);
          resolve(model);
        },
        null,
        () => {
          // Fallback room wireframe
          const box = new THREE.BoxGeometry(sizeX, bounds.max.y, sizeZ);
          const wire = new THREE.WireframeGeometry(box);
          const line = new THREE.LineSegments(wire, new THREE.LineBasicMaterial({ color: 0x334155 }));
          line.position.set(centerX, bounds.max.y / 2, centerZ);
          this.venueGroup.add(line);
          resolve(null);
        }
      );
    });
  }

  renderPOIs(poiList) {
    while (this.poiGroup.children.length > 0) {
      this.poiGroup.remove(this.poiGroup.children[0]);
    }

    poiList.forEach((poi) => {
      const marker = this._createGoogleMapsPin(poi);
      this.poiGroup.add(marker);
    });
  }

  _createGoogleMapsPin(poi) {
    const group = new THREE.Group();
    group.position.set(poi.position.x, poi.position.y || 0.6, poi.position.z);
    group.userData = { poi };

    const colorHex = this.categoryColors[poi.category] || this.categoryColors.default;

    // 1. Google Pin 3D Mesh
    const pinGeo = new THREE.ConeGeometry(0.24, 0.6, 16);
    pinGeo.rotateX(Math.PI);
    const pinMat = new THREE.MeshStandardMaterial({
      color: colorHex,
      roughness: 0.3,
      metalness: 0.4
    });
    const pin = new THREE.Mesh(pinGeo, pinMat);
    pin.position.y = 0.5;
    pin.name = 'pinMesh';
    group.add(pin);

    const capGeo = new THREE.SphereGeometry(0.24, 16, 16);
    const cap = new THREE.Mesh(capGeo, pinMat);
    cap.position.y = 0.7;
    group.add(cap);

    // 2. Ground Anchor Dot
    const dotGeo = new THREE.CircleGeometry(0.12, 16);
    const dotMat = new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.4 });
    const dot = new THREE.Mesh(dotGeo, dotMat);
    dot.rotation.x = -Math.PI / 2;
    dot.position.y = -(poi.position.y || 0.6) + 0.02;
    group.add(dot);

    // 3. Floating Label
    const sprite = this._createTextSprite(poi.name, colorHex);
    sprite.position.y = 1.25;
    group.add(sprite);

    return group;
  }

  _createTextSprite(text, colorHex) {
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 64;
    const ctx = canvas.getContext('2d');

    ctx.fillStyle = 'rgba(28, 33, 45, 0.9)';
    ctx.roundRect(8, 8, 240, 48, 24);
    ctx.fill();

    ctx.strokeStyle = `#${colorHex.toString(16).padStart(6, '0')}`;
    ctx.lineWidth = 2.5;
    ctx.roundRect(8, 8, 240, 48, 24);
    ctx.stroke();

    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 19px Google Sans, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const truncated = text.length > 17 ? text.substring(0, 16) + '…' : text;
    ctx.fillText(truncated, 128, 32);

    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;
    const spriteMat = new THREE.SpriteMaterial({ map: texture, transparent: true });
    const sprite = new THREE.Sprite(spriteMat);
    sprite.scale.set(1.6, 0.4, 1.0);
    return sprite;
  }

  selectPOI(poiId) {
    let found = null;
    this.poiGroup.children.forEach((child) => {
      const isTarget = child.userData?.poi?.id === poiId;
      const pin = child.getObjectByName('pinMesh');
      if (pin) {
        if (isTarget) {
          pin.scale.set(1.3, 1.3, 1.3);
          found = child;
        } else {
          pin.scale.set(1, 1, 1);
        }
      }
    });

    if (found) {
      this.selectedMarker = found;
      this.flyTo(
        { x: found.position.x, y: found.position.y + 3, z: found.position.z + 4.5 },
        found.position,
        700
      );
    }
  }

  renderPath(waypoints) {
    this.clearPath();
    if (!waypoints || waypoints.length < 2) return;
    this.activeRouteWaypoints = waypoints;
    this.activeRouteIndex = 0;

    const points = waypoints.map((wp) => new THREE.Vector3(wp.x, 0.12, wp.z));
    const curve = new THREE.CatmullRomCurve3(points, false, 'catmullrom', 0.15);
    const curvePoints = curve.getPoints(Math.max(waypoints.length * 8, 40));

    // 1. Google Maps Vibrant Royal Blue Path Line
    const lineGeo = new THREE.BufferGeometry().setFromPoints(curvePoints);
    const lineMat = new THREE.LineBasicMaterial({
      color: 0x1a73e8,
      linewidth: 5,
      transparent: true,
      opacity: 0.95
    });
    const pathLine = new THREE.Line(lineGeo, lineMat);
    this.pathGroup.add(pathLine);

    // 2. Smooth 3D Tube for elevation and soft glow
    const tubeGeo = new THREE.TubeGeometry(curve, 48, 0.06, 8, false);
    const tubeMat = new THREE.MeshBasicMaterial({ color: 0x4285f4, transparent: true, opacity: 0.7 });
    const tubeMesh = new THREE.Mesh(tubeGeo, tubeMat);
    this.pathGroup.add(tubeMesh);

    // 3. Destination Iconic Red 3D Google Pin 📍
    while (this.destinationPinGroup.children.length > 0) {
      this.destinationPinGroup.remove(this.destinationPinGroup.children[0]);
    }
    const dest = waypoints[waypoints.length - 1];
    const redPinGeo = new THREE.ConeGeometry(0.3, 0.8, 16);
    redPinGeo.rotateX(Math.PI);
    const redPinMat = new THREE.MeshStandardMaterial({ color: 0xea4335, roughness: 0.2 });
    const redPin = new THREE.Mesh(redPinGeo, redPinMat);
    redPin.position.set(dest.x, 0.8, dest.z);
    this.destinationPinGroup.add(redPin);

    const redCapGeo = new THREE.SphereGeometry(0.3, 16, 16);
    const redCap = new THREE.Mesh(redCapGeo, redPinMat);
    redCap.position.set(dest.x, 1.1, dest.z);
    this.destinationPinGroup.add(redCap);

    // Frame camera
    const box = new THREE.Box3().setFromPoints(points);
    const center = new THREE.Vector3();
    box.getCenter(center);
    const size = new THREE.Vector3();
    box.getSize(size);
    const maxDim = Math.max(size.x, size.z, 6);

    this.flyTo(
      { x: center.x, y: center.y + maxDim * 1.1, z: center.z + maxDim * 1.1 },
      center,
      800
    );
  }

  clearPath() {
    this.stopNavigation();
    this.activeRouteWaypoints = null;
    this.activeRouteIndex = 0;
    while (this.pathGroup.children.length > 0) {
      this.pathGroup.remove(this.pathGroup.children[0]);
    }
    while (this.destinationPinGroup.children.length > 0) {
      this.destinationPinGroup.remove(this.destinationPinGroup.children[0]);
    }
  }

  startNavigation(waypoints, onStepChange, onComplete) {
    if (!waypoints || waypoints.length < 2) return;
    this.stopNavigation();
    this.navigationActive = true;

    let currentIndex = 0;
    const walkSpeed = 1.3; // Google Maps walking speed (1.3 m/s)

    const stepToNext = () => {
      if (!this.navigationActive || currentIndex >= waypoints.length - 1) {
        this.navigationActive = false;
        if (onComplete) onComplete();
        return;
      }

      if (onStepChange) onStepChange(currentIndex);

      const current = waypoints[currentIndex];
      const next = waypoints[currentIndex + 1];
      const dx = next.x - current.x;
      const dz = next.z - current.z;
      const dist = Math.hypot(dx, dz);
      const durationMs = Math.max(450, (dist / walkSpeed) * 1000);

      // Compute heading
      const rad = Math.atan2(dx, -dz);
      const headingDeg = (THREE.MathUtils.radToDeg(rad) + 360) % 360;

      const startState = {
        x: current.x,
        z: current.z,
        camX: this.camera.position.x,
        camY: this.camera.position.y,
        camZ: this.camera.position.z,
        tarX: this.controls.target.x,
        tarY: this.controls.target.y,
        tarZ: this.controls.target.z
      };

      // Camera rides smoothly behind the user
      const camOffsetDist = 3.5;
      const camHeight = 2.4;
      const targetCamX = next.x - Math.sin(rad) * camOffsetDist;
      const targetCamZ = next.z + Math.cos(rad) * camOffsetDist;

      this.navTween = new window.TWEEN.Tween(startState)
        .to(
          {
            x: next.x,
            z: next.z,
            camX: targetCamX,
            camY: camHeight,
            camZ: targetCamZ,
            tarX: next.x + Math.sin(rad) * 2,
            tarY: 1.0,
            tarZ: next.z - Math.cos(rad) * 2
          },
          durationMs
        )
        .easing(window.TWEEN.Easing.Linear.None)
        .onUpdate(() => {
          this.setUserPosition(startState.x, startState.z, headingDeg);
          this.camera.position.set(startState.camX, startState.camY, startState.camZ);
          this.controls.target.set(startState.tarX, startState.tarY, startState.tarZ);
        })
        .onComplete(() => {
          currentIndex++;
          stepToNext();
        })
        .start();
    };

    // First jump user to start waypoint
    this.setUserPosition(waypoints[0].x, waypoints[0].z);
    stepToNext();
  }

  stopNavigation() {
    this.navigationActive = false;
    if (this.navTween) {
      this.navTween.stop();
      this.navTween = null;
    }
  }

  renderObstacles(obstacles) {
    while (this.obstacleGroup.children.length > 0) {
      this.obstacleGroup.remove(this.obstacleGroup.children[0]);
    }
    if (!obstacles || obstacles.length === 0) return;

    obstacles.forEach((obs) => {
      const group = new THREE.Group();
      group.position.set(obs.x, 0.0, obs.z);

      // Warning Red/Amber Cylinder
      const cylGeo = new THREE.CylinderGeometry(obs.radius, obs.radius, 1.0, 24);
      const cylMat = new THREE.MeshBasicMaterial({
        color: 0xea4335,
        transparent: true,
        opacity: 0.35,
        side: THREE.DoubleSide
      });
      const cyl = new THREE.Mesh(cylGeo, cylMat);
      cyl.position.y = 0.5;
      group.add(cyl);

      // Caution Ring
      const ringGeo = new THREE.RingGeometry(obs.radius * 0.88, obs.radius, 24);
      const ringMat = new THREE.MeshBasicMaterial({ color: 0xfbbc04, side: THREE.DoubleSide });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.rotation.x = -Math.PI / 2;
      ring.position.y = 0.04;
      group.add(ring);

      const sprite = this._createTextSprite(`⚠️ ${obs.name}`, 0xea4335);
      sprite.position.y = 1.3;
      group.add(sprite);

      this.obstacleGroup.add(group);
    });
  }

  flyTo(position, target, duration = 750) {
    if (!window.TWEEN) {
      this.camera.position.set(position.x, position.y, position.z);
      this.controls.target.set(target.x, target.y, target.z);
      return;
    }

    const start = {
      cx: this.camera.position.x,
      cy: this.camera.position.y,
      cz: this.camera.position.z,
      tx: this.controls.target.x,
      ty: this.controls.target.y,
      tz: this.controls.target.z
    };

    new window.TWEEN.Tween(start)
      .to({ cx: position.x, cy: position.y, cz: position.z, tx: target.x, ty: target.y, tz: target.z }, duration)
      .easing(window.TWEEN.Easing.Cubic.Out)
      .onUpdate(() => {
        this.camera.position.set(start.cx, start.cy, start.cz);
        this.controls.target.set(start.tx, start.ty, start.tz);
      })
      .start();
  }

  toggleViewMode() {
    this.isTopDown = !this.isTopDown;
    const target = this.controls.target.clone();
    if (this.isTopDown) {
      this.flyTo({ x: target.x, y: target.y + 24, z: target.z + 0.01 }, target, 650);
    } else {
      this.flyTo({ x: target.x, y: target.y + 10, z: target.z + 16 }, target, 650);
    }
    return this.isTopDown;
  }

  recenterOnUser() {
    this.flyTo(
      { x: this.userPos.x, y: 7, z: this.userPos.z + 8 },
      { x: this.userPos.x, y: 0.2, z: this.userPos.z },
      650
    );
  }

  resetNorth() {
    const target = this.controls.target.clone();
    const dist = this.camera.position.distanceTo(target);
    this.flyTo({ x: target.x, y: target.y + 8, z: target.z + dist * 0.8 }, target, 600);
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

    const bounds = this.activeVenue?.bounds || { min: { x: -10, y: 0, z: -7.5 }, max: { x: 10, y: 3, z: 7.5 } };
    const sizeX = Math.abs(bounds.max.x - bounds.min.x);
    const sizeZ = Math.abs(bounds.max.z - bounds.min.z);
    const centerX = (bounds.min.x + bounds.max.x) / 2;
    const centerZ = (bounds.min.z + bounds.max.z) / 2;

    const textureLoader = new THREE.TextureLoader();
    textureLoader.load(debugMapUrl, (texture) => {
      texture.magFilter = THREE.NearestFilter;
      const planeGeo = new THREE.PlaneGeometry(sizeX, sizeZ);
      const planeMat = new THREE.MeshBasicMaterial({ map: texture, transparent: true, opacity: 0.6, side: THREE.DoubleSide });
      this.navmeshMesh = new THREE.Mesh(planeGeo, planeMat);
      this.navmeshMesh.rotation.x = -Math.PI / 2;
      this.navmeshMesh.position.set(centerX, bounds.min.y + 0.02, centerZ);
      this.venueGroup.add(this.navmeshMesh);
    });
  }

  clearAll() {
    this.clearPath();
    while (this.venueGroup.children.length > 0) this.venueGroup.remove(this.venueGroup.children[0]);
    while (this.poiGroup.children.length > 0) this.poiGroup.remove(this.poiGroup.children[0]);
    while (this.obstacleGroup.children.length > 0) this.obstacleGroup.remove(this.obstacleGroup.children[0]);
    this.navmeshMesh = null;
  }

  _animate(time) {
    requestAnimationFrame((t) => this._animate(t));
    if (window.TWEEN) window.TWEEN.update(time);

    // Pulse radar ring on Blue Dot
    const pulseRing = this.userDotGroup.getObjectByName('userPulseRing');
    if (pulseRing) {
      const s = 1.0 + Math.sin(time * 0.003) * 0.35;
      pulseRing.scale.set(s, s, 1);
    }

    // Rotate compass needle based on camera azimuthal angle
    if (this.controls) {
      const rotY = this.controls.getAzimuthalAngle();
      const needle = document.getElementById('compass-needle');
      if (needle) {
        needle.style.transform = `rotate(${-rotY}rad)`;
      }
    }

    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }
}
