/**
 * WorldSim 2.5D SceneViz — isometric / layered stage.
 * Consumes /world/snapshot. True 3D renderer reserved (same DTO); not implemented.
 */
(function (global) {
  "use strict";

  // Fallback topology if snapshot edges missing (world-pack-v0)
  const FALLBACK_EDGES = {
    home: ["neighborhood"],
    neighborhood: ["home", "transit", "commerce", "outdoors"],
    transit: ["neighborhood", "workplace"],
    workplace: ["transit", "commerce"],
    commerce: ["neighborhood", "workplace", "outdoors"],
    outdoors: ["neighborhood", "commerce"],
  };

  // Pseudo-isometric stage positions (canvas space)
  const STAGE = {
    home: { x: 120, y: 220, z: 0 },
    neighborhood: { x: 280, y: 180, z: 1 },
    transit: { x: 420, y: 140, z: 2 },
    workplace: { x: 560, y: 100, z: 3 },
    commerce: { x: 360, y: 260, z: 1 },
    outdoors: { x: 200, y: 300, z: 0 },
  };

  const PALETTE = {
    home: "#5b8c5a",
    neighborhood: "#6b7c8a",
    transit: "#8a7a5b",
    workplace: "#5a6b8c",
    commerce: "#8c5a6b",
    outdoors: "#4a8c7a",
  };

  function edgesOf(loc, all) {
    if (loc.edges && loc.edges.length) return loc.edges.map((e) => e.to);
    return FALLBACK_EDGES[loc.id] || [];
  }

  function drawIsoTile(ctx, x, y, w, h, color, label) {
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(x, y - h * 0.35);
    ctx.lineTo(x + w * 0.5, y);
    ctx.lineTo(x, y + h * 0.35);
    ctx.lineTo(x - w * 0.5, y);
    ctx.closePath();
    const g = ctx.createLinearGradient(x, y - h, x, y + h);
    g.addColorStop(0, color);
    g.addColorStop(1, "#1a2228");
    ctx.fillStyle = g;
    ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,0.18)";
    ctx.stroke();
    // facade slab (2.5D depth cue)
    ctx.beginPath();
    ctx.moveTo(x - w * 0.5, y);
    ctx.lineTo(x, y + h * 0.35);
    ctx.lineTo(x, y + h * 0.55);
    ctx.lineTo(x - w * 0.5, y + h * 0.2);
    ctx.closePath();
    ctx.fillStyle = "rgba(0,0,0,0.28)";
    ctx.fill();
    ctx.fillStyle = "#e8ecef";
    ctx.font = "12px 'IBM Plex Sans', 'Noto Sans SC', sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(label, x, y + 4);
    ctx.restore();
  }

  function drawAgent(ctx, x, y, pad) {
    const p = (pad && pad.p) || 0;
    const hue = Math.round(120 * ((p + 1) / 2)); // pleasure → green↔red-ish
    ctx.save();
    ctx.translate(x, y - 28);
    // bob
    const bob = Math.sin(Date.now() / 280) * 2;
    ctx.translate(0, bob);
    ctx.beginPath();
    ctx.arc(0, 0, 10, 0, Math.PI * 2);
    ctx.fillStyle = `hsl(${hue} 55% 55%)`;
    ctx.shadowColor = "rgba(0,0,0,0.45)";
    ctx.shadowBlur = 8;
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.fillStyle = "#fff";
    ctx.font = "bold 10px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("★", 0, 3);
    ctx.restore();
  }

  function drawEdge(ctx, a, b) {
    ctx.save();
    ctx.strokeStyle = "rgba(180,200,220,0.35)";
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
    ctx.restore();
  }

  function SceneRenderer(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.snap = null;
    this._prevLoc = null;
    this._fade = 1;
    this._raf = null;
  }

  SceneRenderer.prototype.setSnapshot = function (snap) {
    const next = snap && snap.location && snap.location.id;
    if (this._prevLoc && next && this._prevLoc !== next) {
      this._fade = 0;
    }
    this._prevLoc = next || this._prevLoc;
    this.snap = snap;
    this.paint();
  };

  SceneRenderer.prototype.paint = function () {
    const ctx = this.ctx;
    const w = (this.canvas.width = this.canvas.clientWidth || 720);
    const h = (this.canvas.height = this.canvas.clientHeight || 380);
    ctx.clearRect(0, 0, w, h);

    // sky gradient by day_part
    const part = (this.snap && this.snap.day_part) || "day";
    const skies = {
      dawn: ["#3a4a6a", "#c48a5a"],
      morning: ["#5a7aaa", "#c8d8e8"],
      midday: ["#4a90c8", "#e8f0f8"],
      afternoon: ["#5a80a8", "#d8c8a8"],
      evening: ["#3a3560", "#c07050"],
      night: ["#121820", "#2a3550"],
    };
    const [c0, c1] = skies[part] || skies.morning;
    const bg = ctx.createLinearGradient(0, 0, 0, h);
    bg.addColorStop(0, c0);
    bg.addColorStop(1, c1);
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, w, h);

    // ground plane
    ctx.fillStyle = "rgba(20,28,32,0.55)";
    ctx.beginPath();
    ctx.moveTo(40, h * 0.55);
    ctx.lineTo(w - 40, h * 0.4);
    ctx.lineTo(w - 20, h - 20);
    ctx.lineTo(30, h - 10);
    ctx.closePath();
    ctx.fill();

    const locs = (this.snap && this.snap.locations) || [];
    const byId = {};
    locs.forEach((L) => {
      byId[L.id] = L;
    });

    // edges
    locs.forEach((L) => {
      const a = STAGE[L.id];
      if (!a) return;
      edgesOf(L).forEach((to) => {
        const b = STAGE[to];
        if (b) drawEdge(ctx, a, b);
      });
    });

    // tiles sorted by depth (z then y)
    const order = Object.keys(STAGE).sort((i, j) => {
      const A = STAGE[i];
      const B = STAGE[j];
      return A.z - B.z || A.y - B.y;
    });

    order.forEach((id) => {
      const pos = STAGE[id];
      const L = byId[id] || { id, display_name: id };
      const color = PALETTE[id] || "#667";
      drawIsoTile(ctx, pos.x, pos.y, 110, 70, color, L.display_name || id);
    });

    // agent sprite
    if (this.snap && this.snap.location) {
      const id = this.snap.location.id;
      const pos = STAGE[id] || STAGE.home;
      if (this._fade < 1) this._fade = Math.min(1, this._fade + 0.08);
      ctx.globalAlpha = 0.35 + 0.65 * this._fade;
      drawAgent(ctx, pos.x, pos.y, this.snap.pad);
      ctx.globalAlpha = 1;
    }

    // HUD strip
    ctx.fillStyle = "rgba(0,0,0,0.45)";
    ctx.fillRect(0, 0, w, 36);
    ctx.fillStyle = "#e8ecef";
    ctx.font = "13px 'IBM Plex Sans', 'Noto Sans SC', sans-serif";
    ctx.textAlign = "left";
    const label = this.snap
      ? `${this.snap.clock_label || ""} · ${this.snap.weather || ""} · @${
          (this.snap.location && this.snap.location.display_name) || "?"
        } · 2.5D`
      : "等待 snapshot…";
    ctx.fillText(label, 12, 22);

    if (this._fade < 1) {
      cancelAnimationFrame(this._raf);
      this._raf = requestAnimationFrame(() => this.paint());
    }
  };

  global.WorldSimScene = { SceneRenderer, STAGE, FALLBACK_EDGES };
})(typeof window !== "undefined" ? window : globalThis);
