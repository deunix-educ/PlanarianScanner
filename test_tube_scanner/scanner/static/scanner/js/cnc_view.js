/*
 * cnc_view.js — vue isométrique du bras CNC (simulation, PC uniquement)
 *
 * Montage réel : le bras (portique Y + chariot X) est SOUS les plaques ; la caméra pointe vers le
 * haut et filme les éprouvettes par en dessous à travers un plateau transparent ; l'éclairage est
 * au-dessus des plaques. Les plaques et l'éclairage sont donc dessinés translucides pour laisser
 * voir le bras.
 *
 * Repère isométrique : x vers le haut-droite, y vers le haut-gauche, z vertical (en mm).
 * L'origine (0, 0) est le coin le plus proche du spectateur.
 *
 * Alimentation :
 *   moveTo(x, y, ms)   mouvement animé (événement `move` du simulateur GRBL)
 *   setPosition(x, y)  position faisant foi (message `xy`) ; n'interrompt pas une animation
 *   setActivePlate(p)  plaque sélectionnée dans la page (met en évidence + trace du serpentin)
 *   setZoom(bool)      vue resserrée sur la plaque active (+ l'origine) ou plateau entier
 *   toggleExpand()     panneau agrandi à toute la fenêtre (CSS ; Échap pour revenir)
 *
 * Les variantes d'un même emplacement (ex. HD 4x6 et HD_6 2x3, préfixe de position identique) ne
 * sont pas posées en même temps : seule la plaque active est dessinée.
 */
const CNC_C = Math.cos(Math.PI / 6);
const CNC_S = 0.5;
const SVG_NS = "http://www.w3.org/2000/svg";

// hauteurs (mm) : bras en bas, caméra au-dessus du chariot, plateau transparent, plaques, éclairage
const CNC_Z = { rail: 14, bar: [10, 20], car: [6, 30], cam: [30, 72], tray: [90, 92], plate: [92, 96], light: [135, 138] };

function svgEl(tag, attrs = {}, parent = null) {
    const e = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (parent) parent.appendChild(e);
    return e;
}

/** projection (x, y, z) mm -> point écran */
function isoP(x, y, z = 0) { return [(x - y) * CNC_C, -(x + y) * CNC_S - z]; }
function isoPts(list) { return list.map(([x, y, z]) => isoP(x, y, z).map(n => n.toFixed(1)).join(",")).join(" "); }

/** parallélépipède : face haute + les deux faces tournées vers le spectateur (normales -x et -y) */
class IsoBox {
    constructor(parent, cls) {
        this.g = svgEl("g", { class: `iso-box ${cls}` }, parent);
        this.left = svgEl("polygon", { class: "face-left" }, this.g);
        this.right = svgEl("polygon", { class: "face-right" }, this.g);
        this.top = svgEl("polygon", { class: "face-top" }, this.g);
    }
    set(x0, y0, z0, x1, y1, z1) {
        this.top.setAttribute("points", isoPts([[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]]));
        this.right.setAttribute("points", isoPts([[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1]]));
        this.left.setAttribute("points", isoPts([[x0, y0, z0], [x0, y1, z0], [x0, y1, z1], [x0, y0, z1]]));
        return this;
    }
}

class CncView {
    constructor(container, geometry, options = {}) {
        this.container = container;
        this.bed = geometry.bed;                       // {x, y} course machine en mm
        this.plates = geometry.plates || [];
        this.minMs = options.minMs ?? 150;             // durée minimale d'une animation (lisibilité)
        this.cx = 0; this.cy = 0;
        this.anim = null; this.raf = 0;
        this.active = null;
        this.visited = new Set();
        this.under = null;
        this.zoom = options.zoom ?? CncView._stored("cnc.zoom", true);
        this.path = [];                                // derniers points de la caméra
        this.wellEls = new Map();                      // "HD:D1" -> <circle>
        this.plateTop = CNC_Z.plate[1];                // hauteur du dessus des plaques (mm)
        this.camR = 8;                                 // rayon du corps de caméra
        this.fovR = (this.plates[0]?.diameter || 16) / 2;   // rayon du champ caméra sur la plaque
        this._build();
        this.render();
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && this.expanded) this.toggleExpand(false);
        });
    }

    // ------------------------------------------------------------------ construction
    _build() {
        const X = this.bed.x, Y = this.bed.y, pad = 44, zmax = CNC_Z.light[1] + 6;
        const xs = [isoP(-pad, Y + pad)[0], isoP(X + pad, -pad)[0]];
        const ys = [isoP(X + pad, Y + pad, zmax)[1], isoP(-pad, -pad, -14)[1]];
        const w = xs[1] - xs[0], h = ys[1] - ys[0];

        this.container.classList.add("cnc-view");
        this.fullBox = [xs[0], ys[0], w, h];
        this.svg = svgEl("svg", {
            viewBox: `${xs[0]} ${ys[0]} ${w} ${h}`, preserveAspectRatio: "xMidYMid meet",
            class: "cnc-svg", role: "img", "aria-label": "Bras CNC",
        }, this.container);

        const defs = svgEl("defs", {}, this.svg);
        const mk = svgEl("marker", { id: "cnc-arrow", viewBox: "0 0 10 10", refX: 8, refY: 5,
                                      markerWidth: 6, markerHeight: 6, orient: "auto" }, defs);
        svgEl("path", { d: "M0,0 L10,5 L0,10 z", class: "trail-head" }, mk);

        this.ground = (z) => `matrix(${CNC_C} ${-CNC_S} ${-CNC_C} ${-CNC_S} 0 ${-z})`;

        // 1. châssis, plateau, grille, axes
        this.gStatic = svgEl("g", {}, this.svg);
        new IsoBox(this.gStatic, "frame").set(-12, -12, -14, X + 12, Y + 12, -1);
        new IsoBox(this.gStatic, "bed").set(0, 0, -1, X, Y, 0);
        const g0 = svgEl("g", { transform: this.ground(0) }, this.gStatic);
        for (let x = 50; x < X; x += 50) svgEl("line", { x1: x, y1: 0, x2: x, y2: Y, class: "grid" }, g0);
        for (let y = 50; y < Y; y += 50) svgEl("line", { x1: 0, y1: y, x2: X, y2: y, class: "grid" }, g0);
        svgEl("line", { x1: 0, y1: 0, x2: 60, y2: 0, class: "axis axis-x" }, g0);
        svgEl("line", { x1: 0, y1: 0, x2: 0, y2: 60, class: "axis axis-y" }, g0);
        // libellés hors du châssis (les rails masqueraient ceux posés sur le plateau)
        const tx = isoP(X / 2, -34), ty = isoP(-34, Y / 2);
        svgEl("text", { x: tx[0], y: tx[1], class: "axis-label axis-x" }, this.gStatic).textContent = "X →";
        svgEl("text", { x: ty[0], y: ty[1], class: "axis-label axis-y" }, this.gStatic).textContent = "Y →";

        // 2. rails Y et montants du plateau transparent (les 3 montants du fond / côtés)
        const t = 30;                                    // le plateau déborde du lit de 30 mm
        this.tray = [-t, -t, X + t, Y + t];
        const post = (x, y) => new IsoBox(this.gStatic, "post").set(x, y, 0, x + 6, y + 6, CNC_Z.light[0]);
        post(this.tray[2] - 6, this.tray[3] - 6);        // fond
        post(this.tray[0], this.tray[3] - 6);            // côté gauche
        post(this.tray[2] - 6, this.tray[1]);            // côté droit
        new IsoBox(this.gStatic, "rail").set(X + 6, -6, 0, X + 16, Y + 6, CNC_Z.rail);
        new IsoBox(this.gStatic, "rail").set(-16, -6, 0, -6, Y + 6, CNC_Z.rail);

        // 3. éléments mobiles SOUS les plaques, dans l'ordre de peinture
        this.gDyn = svgEl("g", {}, this.svg);
        this.shBar = svgEl("polygon", { class: "shadow" }, this.gDyn);
        this.shCar = svgEl("polygon", { class: "shadow" }, this.gDyn);
        this.slideL = new IsoBox(this.gDyn, "slider");
        this.slideR = new IsoBox(this.gDyn, "slider");
        this.bar = new IsoBox(this.gDyn, "bar");
        this.carriage = new IsoBox(this.gDyn, "carriage");
        this.camSide = svgEl("rect", { class: "cam-side" }, this.gDyn);
        this.camBase = svgEl("ellipse", { class: "cam-base" }, this.gDyn);   // dessus du boîtier
        this.camRing = svgEl("ellipse", { class: "cam-ring" }, this.gDyn);   // objectif, tourné vers le haut

        // 4. plateau transparent, plaques, puits
        this.gPlates = svgEl("g", {}, this.svg);
        new IsoBox(this.gPlates, "glass").set(this.tray[0], this.tray[1], CNC_Z.tray[0], this.tray[2], this.tray[3], CNC_Z.tray[1]);
        this._buildPlates();

        // 5. au niveau des plaques : trace du serpentin, chemin, empreinte et faisceau de la caméra
        this.gTrail = svgEl("g", { transform: this.ground(this.plateTop + 0.5), class: "trail" }, this.svg);
        this.gOver = svgEl("g", {}, this.svg);
        this.cone = svgEl("polygon", { class: "cone" }, this.gOver);
        this.gFoot = svgEl("g", { transform: this.ground(this.plateTop + 0.5) }, this.gOver);
        this.pathLine = svgEl("polyline", { class: "cam-path" }, this.gFoot);
        this.foot = svgEl("circle", { class: "foot", r: 8 }, this.gFoot);

        // 6. éclairage au-dessus des plaques (translucide) + montant proche + rayons vers la plaque active
        this.gLight = svgEl("g", {}, this.svg);
        this.gRays = svgEl("g", { class: "rays" }, this.gLight);
        new IsoBox(this.gLight, "post").set(this.tray[0], this.tray[1], 0, this.tray[0] + 6, this.tray[1] + 6, CNC_Z.light[0]);
        new IsoBox(this.gLight, "light").set(this.tray[0], this.tray[1], CNC_Z.light[0], this.tray[2], this.tray[3], CNC_Z.light[1]);
        const lp = isoP(this.tray[2] - 4, this.tray[1] + 4, CNC_Z.light[1] + 4);
        svgEl("text", { x: lp[0], y: lp[1], class: "light-label" }, this.gLight).textContent = "éclairage";

        // lecture X / Y / état
        this.readout = document.createElement("div");
        this.readout.className = "cnc-readout";
        this.container.appendChild(this.readout);
    }

    _buildPlates() {
        for (const p of this.plates) {
            const r = (p.diameter || 16) / 2;
            const xs = p.wells.map(w => w.x), ys = p.wells.map(w => w.y);
            if (!xs.length) continue;
            const m = r + 4;
            p.bounds = [Math.min(...xs) - m, Math.min(...ys) - m, Math.max(...xs) + m, Math.max(...ys) + m];
            p.r = r;
            const g = svgEl("g", { class: "plate", "data-position": p.position }, this.gPlates);
            p.el = g;
            new IsoBox(g, "plate-body").set(p.bounds[0], p.bounds[1], CNC_Z.plate[0], p.bounds[2], p.bounds[3], CNC_Z.plate[1]);
            const gw = svgEl("g", { transform: this.ground(this.plateTop) }, g);
            for (const w of p.wells) {
                const c = svgEl("circle", { cx: w.x, cy: w.y, r: r - 0.6, class: "well" }, gw);
                this.wellEls.set(`${p.position}:${w.name}`, c);
            }
            const lp = isoP((p.bounds[0] + p.bounds[2]) / 2, p.bounds[1] - 9, this.plateTop);
            const label = svgEl("text", { x: lp[0], y: lp[1], class: "plate-label" }, g);
            label.textContent = p.position + (p.stale ? " ⚠" : "");
            if (p.stale) {
                g.classList.add("stale");
                svgEl("title", {}, label).textContent = "Les positions enregistrées des puits ne suivent pas l'origine D1 " +
                    "(xbase/ybase) : décocher « Positions » du multi-puits en admin pour les régénérer.";
            }
        }
    }

    // ------------------------------------------------------------------ pilotage
    setActivePlate(position) {
        this.active = position;
        this.visited.clear();
        this.path = [];
        this._updateVisibility();
        for (const p of this.plates) if (p.el) p.el.classList.toggle("active", p.position === position);
        this.gTrail.replaceChildren();
        this.gRays.replaceChildren();
        const p = this.plates.find(q => q.position === position);
        if (p) this.fovR = (p.diameter || 16) / 2;
        if (p && p.wells.length > 1) {
            const w = [...p.wells].sort((a, b) => a.order - b.order);
            svgEl("polyline", { points: w.map(q => `${q.x},${q.y}`).join(" "), class: "trail-line",
                                "marker-end": "url(#cnc-arrow)" }, this.gTrail);
            svgEl("circle", { cx: w[0].x, cy: w[0].y, r: 2.2, class: "trail-start" }, this.gTrail);
        }
        if (p && p.bounds) {                           // faisceau lumineux de l'éclairage vers la plaque
            const [x0, y0, x1, y1] = p.bounds;
            for (const [x, y] of [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]) {
                const a = isoP(x, y, CNC_Z.light[0]), b = isoP(x, y, this.plateTop);
                svgEl("line", { x1: a[0], y1: a[1], x2: b[0], y2: b[1], class: "ray" }, this.gRays);
            }
        }
        for (const el of this.wellEls.values()) el.classList.remove("visited", "under");
        this.under = null;
        this._applyView();
        this.render();
    }

    /**
     * Une seule plaque par emplacement : les variantes d'un même emplacement ont le même préfixe de
     * position (HD, HD_6...). La plaque active est dessinée, ses variantes sont masquées.
     */
    _updateVisibility() {
        const slot = (p) => p.position.split("_")[0];
        const act = this.plates.find(p => p.position === this.active);
        const taken = new Set();
        this.visible = new Set();
        for (const p of [act, ...this.plates]) {
            if (!p || this.visible.has(p.position) || taken.has(slot(p))) continue;
            taken.add(slot(p));
            this.visible.add(p.position);
        }
        for (const p of this.plates) if (p.el) p.el.classList.toggle("hidden", !this.visible.has(p.position));
    }

    setZoom(on) {
        this.zoom = !!on;
        try { localStorage.setItem("cnc.zoom", this.zoom ? "1" : "0"); } catch (e) { /* stockage indisponible */ }
        this._applyView();
    }

    static _stored(key, dflt) {
        try { const v = localStorage.getItem(key); return v === null ? dflt : v === "1"; } catch (e) { return dflt; }
    }

    /** Zoom : plaque active + origine (où repart souvent le portique), avec une marge. */
    _applyView() {
        const p = this.plates.find(q => q.position === this.active);
        if (!this.zoom || !p || !p.bounds) {
            this.svg.setAttribute("viewBox", this.fullBox.join(" "));
            return;
        }
        const m = 28;
        const x0 = Math.min(0, p.bounds[0]) - m, y0 = Math.min(0, p.bounds[1]) - m;
        const x1 = Math.max(p.bounds[2], 40) + m, y1 = Math.max(p.bounds[3], 40) + m;
        const pts = [];
        for (const x of [x0, x1]) for (const y of [y0, y1]) for (const z of [-6, CNC_Z.light[1]]) pts.push(isoP(x, y, z));
        const xs = pts.map(q => q[0]), ys = pts.map(q => q[1]);
        const bx = Math.min(...xs), by = Math.min(...ys);
        this.svg.setAttribute("viewBox", `${bx} ${by} ${Math.max(...xs) - bx} ${Math.max(...ys) - by}`);
    }

    setPosition(x, y) {
        if (typeof x !== "number" || typeof y !== "number") return;
        if (this.anim) { this.anim.x1 = x; this.anim.y1 = y; return; }   // l'animation finit sur la position faisant foi
        this.cx = x; this.cy = y;
        this.render();
    }

    moveTo(x, y, ms) {
        if (typeof x !== "number" || typeof y !== "number") return;
        this.anim = { x0: this.cx, y0: this.cy, x1: x, y1: y, t0: performance.now(),
                      ms: Math.max(ms || 0, this.minMs) };
        if (!this.raf) this.raf = requestAnimationFrame((t) => this._step(t));
    }

    _step(now) {
        const a = this.anim;
        if (!a) { this.raf = 0; return; }
        const k = (now - a.t0) / a.ms;
        if (k >= 1) {
            this.cx = a.x1; this.cy = a.y1; this.anim = null; this.raf = 0;
            this.render();
            return;
        }
        const e = 0.5 - 0.5 * Math.cos(Math.PI * k);      // accélération / freinage
        this.cx = a.x0 + (a.x1 - a.x0) * e;
        this.cy = a.y0 + (a.y1 - a.y0) * e;
        this.render();
        this.raf = requestAnimationFrame((t) => this._step(t));
    }

    get expanded() { return this.container.classList.contains("cnc-expanded"); }

    /**
     * Agrandit le panneau à toute la fenêtre. Volontairement en CSS (position: fixed) et non via
     * l'API plein écran : certains navigateurs (Brave) referment un plein écran d'élément après ~1 s.
     */
    toggleExpand(force) {
        const on = force ?? !this.expanded;
        this.container.classList.toggle("cnc-expanded", on);
        document.documentElement.classList.toggle("cnc-noscroll", on);
        return on;
    }

    // ------------------------------------------------------------------ rendu
    _wellUnderCamera() {
        let best = null, bestD = 1e9;
        for (const p of this.plates) {
            if (this.visible && !this.visible.has(p.position)) continue;
            for (const w of p.wells) {
                const d = Math.hypot(w.x - this.cx, w.y - this.cy);
                if (d < bestD) { bestD = d; best = `${p.position}:${w.name}`; }
            }
        }
        return best && bestD <= 3 ? best : null;
    }

    render() {
        const X = this.bed.x, cx = this.cx, cy = this.cy;
        const [zb0, zb1] = CNC_Z.bar, [zc0, zc1] = CNC_Z.car, [za0, za1] = CNC_Z.cam;

        // ombres portées sur le lit (éclairage vertical) : repère de profondeur
        this.shBar.setAttribute("points", isoPts([[0, cy - 6, 0], [X, cy - 6, 0], [X, cy + 6, 0], [0, cy + 6, 0]]));
        this.shCar.setAttribute("points", isoPts([[cx - 14, cy - 12, 0], [cx + 14, cy - 12, 0], [cx + 14, cy + 12, 0], [cx - 14, cy + 12, 0]]));

        // portique : coulisseaux, barre X, chariot
        this.slideL.set(-16, cy - 9, 4, -6, cy + 9, zb1 + 2);
        this.slideR.set(X + 6, cy - 9, 4, X + 16, cy + 9, zb1 + 2);
        this.bar.set(-6, cy - 5, zb0, X + 6, cy + 5, zb1);
        this.carriage.set(cx - 14, cy - 12, zc0, cx + 14, cy + 12, zc1);

        // caméra : cylindre au-dessus du chariot, objectif (bague bleue) tourné vers le haut
        const R = this.camR, rx = CNC_C * Math.SQRT2 * R, ry = CNC_S * Math.SQRT2 * R;
        const [px, pyTop] = isoP(cx, cy, za1), [, pyBot] = isoP(cx, cy, za0);
        this.camSide.setAttribute("x", (px - rx).toFixed(1));
        this.camSide.setAttribute("y", pyTop.toFixed(1));
        this.camSide.setAttribute("width", (2 * rx).toFixed(1));
        this.camSide.setAttribute("height", (pyBot - pyTop).toFixed(1));
        for (const [e, k] of [[this.camBase, 1], [this.camRing, 0.62]]) {
            e.setAttribute("cx", px.toFixed(1)); e.setAttribute("cy", pyTop.toFixed(1));
            e.setAttribute("rx", (rx * k).toFixed(1)); e.setAttribute("ry", (ry * k).toFixed(1));
        }

        // faisceau : de l'objectif vers le haut jusqu'à l'empreinte sur la plaque
        const fr = this.fovR || 8, frx = CNC_C * Math.SQRT2 * fr;
        const [fx, fy] = isoP(cx, cy, this.plateTop);
        this.foot.setAttribute("cx", cx.toFixed(2)); this.foot.setAttribute("cy", cy.toFixed(2));
        this.foot.setAttribute("r", fr);
        this.cone.setAttribute("points", [
            [px - rx * 0.62, pyTop], [px + rx * 0.62, pyTop], [fx + frx, fy], [fx - frx, fy],
        ].map(p => p.map(n => n.toFixed(1)).join(",")).join(" "));

        // chemin parcouru (aide à voir un petit déplacement)
        const last = this.path[this.path.length - 1];
        if (!last || Math.hypot(last[0] - cx, last[1] - cy) > 0.25) {
            this.path.push([cx, cy]);
            if (this.path.length > 80) this.path.shift();
        }
        this.pathLine.setAttribute("points", this.path.map(q => `${q[0].toFixed(2)},${q[1].toFixed(2)}`).join(" "));

        // puits sous la caméra / déjà visités
        const under = this._wellUnderCamera();
        if (under !== this.under) {
            if (this.under) this.wellEls.get(this.under)?.classList.remove("under");
            if (under) { this.wellEls.get(under)?.classList.add("under"); this.wellEls.get(under)?.classList.add("visited"); }
            this.under = under;
        }

        this.readout.innerHTML =
            `<span>X <b>${cx.toFixed(1)}</b></span><span>Y <b>${cy.toFixed(1)}</b></span>` +
            `<span class="state ${this.anim ? "run" : "idle"}">${this.anim ? "Run" : "Idle"}</span>` +
            (under ? `<span class="well-name">${under.split(":")[1]}</span>` : "");
    }
}
