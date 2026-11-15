// Hero scene: a friendly block (the page is a block explorer) with smaller blocks in orbit.
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

const host = document.getElementById('scene');
const canvas = document.getElementById('scene-canvas');
const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

try {
    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 50);
    camera.position.set(0, 0.2, 10.5);

    scene.add(new THREE.HemisphereLight(0xfff4e6, 0x2a1c14, 1.5));
    const key = new THREE.DirectionalLight(0xffffff, 2.2); key.position.set(4, 6, 6); scene.add(key);
    const rim = new THREE.PointLight(0xff6a1f, 30, 20); rim.position.set(-5, -2, 3); scene.add(rim);

    const ORANGE = 0xff6a1f, CREAM = 0xfaf8f4, DARK = 0x121014, GOLD = 0xffc93c, PEACH = 0xff8a4c;
    const mat = (c, r) => new THREE.MeshStandardMaterial({ color: c, roughness: r === undefined ? 0.42 : r, metalness: 0.05 });

    const rig = new THREE.Group(); scene.add(rig);

    // The lead block, with a face
    const lead = new THREE.Group(); rig.add(lead);
    lead.add(new THREE.Mesh(new RoundedBoxGeometry(2.1, 2.1, 2.1, 6, 0.42), mat(ORANGE, 0.36)));
    const face = new THREE.Group(); face.position.z = 1.06; lead.add(face);
    const eyeGeo = new THREE.SphereGeometry(0.17, 24, 24);
    const eyes = [-0.42, 0.42].map(function (x) {
        const e = new THREE.Group(); e.position.set(x, 0.2, 0);
        const white = new THREE.Mesh(eyeGeo, mat(CREAM, 0.3)); white.scale.set(1.25, 1.45, 0.35); e.add(white);
        const pupil = new THREE.Mesh(eyeGeo, mat(DARK, 0.2)); pupil.scale.set(0.62, 0.78, 0.3); pupil.position.z = 0.05; e.add(pupil);
        e.userData.pupil = pupil; face.add(e); return e;
    });
    const grin = new THREE.Mesh(new THREE.TorusGeometry(0.34, 0.055, 12, 32, Math.PI), mat(DARK, 0.3));
    grin.rotation.z = Math.PI; grin.position.set(0, -0.3, 0.01); face.add(grin);

    // Smaller blocks in orbit, with their tracks
    const lineMat = new THREE.LineBasicMaterial({ color: 0x888888, transparent: true, opacity: 0.35 });
    const orbits = [
        { r: 2.5, s: 0.5, size: 0.52, c: CREAM, tilt: [1.2, 0.3], ph: 0 },
        { r: 2.9, s: -0.36, size: 0.42, c: GOLD, tilt: [1.45, -0.5], ph: 2.1 },
        { r: 3.3, s: 0.28, size: 0.6, c: PEACH, tilt: [1.0, 0.9], ph: 4.0 },
        { r: 3.3, s: 0.28, size: 0.34, c: CREAM, tilt: [1.0, 0.9], ph: 0.9 },
        { r: 2.5, s: 0.5, size: 0.3, c: DARK, tilt: [1.2, 0.3], ph: 3.3 },
        { r: 3.8, s: -0.2, size: 0.46, c: ORANGE, tilt: [1.7, 0.2], ph: 5.2 }
    ].map(function (o) {
        const g = new THREE.Group(); g.rotation.set(o.tilt[0], o.tilt[1], 0); rig.add(g);
        const pts = [];
        for (let i = 0; i <= 96; i++) { const a = i / 96 * Math.PI * 2; pts.push(new THREE.Vector3(Math.cos(a) * o.r, 0, Math.sin(a) * o.r)); }
        g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), lineMat));
        const m = new THREE.Mesh(new RoundedBoxGeometry(o.size, o.size, o.size, 4, o.size * 0.22), mat(o.c)); g.add(m);
        o.mesh = m; return o;
    });

    function tint() {
        const ink = getComputedStyle(document.documentElement).getPropertyValue('--ink').trim() || '#888';
        lineMat.color.set(ink);
    }
    tint();
    new MutationObserver(tint).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', tint);

    function size() {
        const w = host.clientWidth, h = host.clientHeight; if (!w || !h) return;
        renderer.setSize(w, h, false); camera.aspect = w / h;
        camera.position.z = w / h < 1 ? 13.5 : 10.5;
        camera.updateProjectionMatrix();
    }
    size(); window.addEventListener('resize', size);

    // Pointer: the block looks at the cursor wherever it is on the page
    const look = { x: 0, y: 0 }, cur = { x: 0, y: 0 };
    window.addEventListener('pointermove', function (e) {
        const r = host.getBoundingClientRect();
        look.x = THREE.MathUtils.clamp((e.clientX - (r.left + r.width / 2)) / (window.innerWidth / 2), -1, 1);
        look.y = THREE.MathUtils.clamp((e.clientY - (r.top + r.height / 2)) / (window.innerHeight / 2), -1, 1);
    }, { passive: true });

    // Tap: hop and spin
    let hop = -1;
    host.addEventListener('click', function () { if (hop < 0) hop = 0; });

    let visible = true;
    new IntersectionObserver(function (en) { visible = en[0].isIntersecting; }).observe(host);

    const clock = new THREE.Clock();
    let t = 0, nextBlink = 2.5, blink = -1;
    function frame() {
        const dt = Math.min(clock.getDelta(), 0.05);
        if (visible && !document.hidden) {
            t += dt;
            cur.x += (look.x - cur.x) * 0.07; cur.y += (look.y - cur.y) * 0.07;
            lead.rotation.y = cur.x * 0.6 + Math.sin(t * 0.6) * 0.06;
            lead.rotation.x = cur.y * 0.42 + Math.cos(t * 0.5) * 0.04;
            lead.position.y = Math.sin(t * 1.1) * 0.14;
            eyes.forEach(function (e) { e.userData.pupil.position.x = cur.x * 0.07; e.userData.pupil.position.y = -cur.y * 0.07; });
            if (t > nextBlink) { blink = 0; nextBlink = t + 2.5 + Math.random() * 3; }
            if (blink >= 0) { blink += dt / 0.16; const k = blink < 0.5 ? 1 - blink * 2 : (blink - 0.5) * 2; eyes.forEach(function (e) { e.scale.y = Math.max(0.08, k); }); if (blink >= 1) { blink = -1; eyes.forEach(function (e) { e.scale.y = 1; }); } }
            if (hop >= 0) {
                hop += dt / 0.9;
                const k = Math.min(hop, 1), ease = 1 - Math.pow(1 - k, 3);
                lead.position.y += Math.sin(k * Math.PI) * 0.9;
                lead.rotation.y += ease * Math.PI * 2;
                const sq = 1 + Math.sin(k * Math.PI * 2) * 0.08; lead.scale.set(1 / sq, sq, 1 / sq);
                if (hop >= 1) { hop = -1; lead.scale.set(1, 1, 1); }
            }
            orbits.forEach(function (o) {
                const a = o.ph + t * o.s * (hop >= 0 ? 3 : 1);
                o.mesh.position.set(Math.cos(a) * o.r, 0, Math.sin(a) * o.r);
                o.mesh.rotation.x += dt * 0.8; o.mesh.rotation.y += dt * 0.6;
            });
            rig.rotation.y = cur.x * 0.18 + window.scrollY * 0.0012;
            rig.rotation.x = cur.y * 0.1;
            renderer.render(scene, camera);
        }
        if (!reduce) requestAnimationFrame(frame);
    }
    if (reduce) { orbits.forEach(function (o) { o.mesh.position.set(Math.cos(o.ph) * o.r, 0, Math.sin(o.ph) * o.r); }); renderer.render(scene, camera); window.addEventListener('resize', function () { renderer.render(scene, camera); }); }
    else requestAnimationFrame(frame);
} catch (e) {
    host.classList.add('no-gl');
}
