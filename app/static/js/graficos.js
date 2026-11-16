/* Gráficas 2D en <canvas> sin dependencias.
 *
 * const p = new Graficos.Plot(canvas, {titulo, xlabel, ylabel});
 * p.draw({lines:[{x,y,color,width,dash,label}], points:[{x,y,color,r}], includeZero:true, xmin, xmax, ymin, ymax});
 * p.cursor(xValor|null, [{x,y,color}])   // redibuja rápido encima de lo ya dibujado
 *
 * draw() pinta la parte pesada una sola vez en un canvas auxiliar; cursor() solo la copia y
 * dibuja el marcador, así la animación a 60 fps no vuelve a trazar las curvas.
 */
const Graficos = (() => {
  const css = (n, f) => getComputedStyle(document.documentElement).getPropertyValue(n).trim() || f;

  function nice(range, round) {
    const exp = Math.floor(Math.log10(range));
    const f = range / Math.pow(10, exp);
    let nf;
    if (round) nf = f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10;
    else nf = f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10;
    return nf * Math.pow(10, exp);
  }

  function ticks(min, max, n = 5) {
    if (!(max > min)) max = min + 1;
    const step = nice(nice(max - min, false) / (n - 1), true);
    const out = [];
    for (let v = Math.ceil(min / step - 1e-9) * step; v <= max + step * 1e-9; v += step) {
      out.push(Math.abs(v) < step * 1e-9 ? 0 : v);
    }
    return { ticks: out, step };
  }

  function fmt(v, step) {
    if (v === 0) return '0';
    if (Math.abs(v) >= 1e5 || (Math.abs(v) < 1e-3 && step < 1e-3)) return v.toExponential(1);
    const dec = Math.min(6, Math.max(0, -Math.floor(Math.log10(step) + 1e-9)));
    return v.toFixed(dec);
  }

  function rango(arrs, includeZero) {
    let lo = Infinity, hi = -Infinity;
    for (const a of arrs) for (const v of a) { if (v < lo) lo = v; if (v > hi) hi = v; }
    if (includeZero) { lo = Math.min(lo, 0); hi = Math.max(hi, 0); }
    if (!isFinite(lo)) { lo = -1; hi = 1; }
    if (lo === hi) { lo -= 1; hi += 1; }
    return [lo, hi];
  }

  class Plot {
    constructor(canvas, opts = {}) {
      this.c = canvas;
      this.ctx = canvas.getContext('2d');
      this.cache = document.createElement('canvas');
      this.o = Object.assign({ titulo: '', xlabel: '', ylabel: '', margin: { l: 52, r: 12, t: 28, b: 34 } }, opts);
      this.last = null;
      this.resize();
      if (window.ResizeObserver) {
        new ResizeObserver(() => { this.resize(); if (this.last) { this.draw(this.last); } }).observe(canvas);
      }
    }

    resize() {
      const r = this.c.getBoundingClientRect();
      this.dpr = window.devicePixelRatio || 1;
      this.w = Math.max(10, r.width);
      this.h = Math.max(10, r.height);
      for (const cv of [this.c, this.cache]) {
        cv.width = Math.round(this.w * this.dpr);
        cv.height = Math.round(this.h * this.dpr);
      }
    }

    draw(d) {
      this.last = d;
      const { w, h } = this, m = this.o.margin;
      const pw = w - m.l - m.r, ph = h - m.t - m.b;
      const lines = d.lines || [], pts = d.points || [];
      const inc = d.includeZero !== false;

      let [xmin, xmax] = [d.xmin, d.xmax];
      if (xmin === undefined || xmax === undefined) {
        const r = rango([...lines.map(l => l.x), ...pts.map(p => p.x)], false);
        const pad = (r[1] - r[0]) * 0.06;
        [xmin, xmax] = [r[0] - pad, r[1] + pad];
      }
      let [ymin, ymax] = [d.ymin, d.ymax];
      if (ymin === undefined || ymax === undefined) {
        const r = rango([...lines.map(l => l.y), ...pts.map(p => p.y)], inc);
        const pad = (r[1] - r[0]) * 0.08;
        [ymin, ymax] = [r[0] - pad, r[1] + pad];
      }
      const sx = v => m.l + (v - xmin) / (xmax - xmin) * pw;
      const sy = v => m.t + ph - (v - ymin) / (ymax - ymin) * ph;
      this.map = { sx, sy, xmin, xmax, ymin, ymax };

      const g = this.cache.getContext('2d');
      g.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
      g.clearRect(0, 0, w, h);
      const cGrid = css('--grid', '#e5e7eb'), cTxt = css('--muted', '#6b7280'), cInk = css('--ink', '#111827');
      g.font = '11px ui-monospace, SFMono-Regular, Menlo, monospace';

      // rejilla y ejes
      const tx = ticks(xmin, xmax, Math.max(3, Math.round(pw / 90)));
      const ty = ticks(ymin, ymax, Math.max(3, Math.round(ph / 45)));
      g.lineWidth = 1; g.strokeStyle = cGrid; g.fillStyle = cTxt;
      g.textAlign = 'center'; g.textBaseline = 'top';
      for (const v of tx.ticks) {
        const x = Math.round(sx(v)) + 0.5;
        g.beginPath(); g.moveTo(x, m.t); g.lineTo(x, m.t + ph); g.stroke();
        g.fillText(fmt(v, tx.step), x, m.t + ph + 5);
      }
      g.textAlign = 'right'; g.textBaseline = 'middle';
      for (const v of ty.ticks) {
        const y = Math.round(sy(v)) + 0.5;
        g.beginPath(); g.moveTo(m.l, y); g.lineTo(m.l + pw, y); g.stroke();
        g.fillText(fmt(v, ty.step), m.l - 6, y);
      }
      // eje cero más marcado
      if (ymin < 0 && ymax > 0) {
        g.strokeStyle = cTxt; g.globalAlpha = 0.55;
        const y = Math.round(sy(0)) + 0.5;
        g.beginPath(); g.moveTo(m.l, y); g.lineTo(m.l + pw, y); g.stroke();
        g.globalAlpha = 1;
      }
      g.strokeStyle = cTxt; g.strokeRect(m.l + 0.5, m.t + 0.5, pw, ph);

      // curvas (recortadas al área de trazado)
      g.save();
      g.beginPath(); g.rect(m.l, m.t, pw, ph); g.clip();
      for (const L of lines) {
        g.strokeStyle = L.color || cInk;
        g.lineWidth = L.width || 2;
        g.setLineDash(L.dash || []);
        g.beginPath();
        for (let i = 0; i < L.x.length; i++) {
          const X = sx(L.x[i]), Y = sy(L.y[i]);
          i ? g.lineTo(X, Y) : g.moveTo(X, Y);
        }
        g.stroke();
      }
      g.setLineDash([]);
      for (const P of pts) {
        g.fillStyle = P.color || cInk;
        for (let i = 0; i < P.x.length; i++) {
          g.beginPath(); g.arc(sx(P.x[i]), sy(P.y[i]), P.r || 4, 0, 2 * Math.PI); g.fill();
        }
      }
      g.restore();

      // títulos
      g.fillStyle = cInk; g.textAlign = 'left'; g.textBaseline = 'top';
      g.font = '600 12px system-ui, sans-serif';
      g.fillText(this.o.titulo, m.l, 6);
      g.font = '11px system-ui, sans-serif'; g.fillStyle = cTxt;
      g.textAlign = 'center'; g.textBaseline = 'bottom';
      if (this.o.xlabel) g.fillText(this.o.xlabel, m.l + pw / 2, h - 1);

      // leyenda
      const leg = lines.filter(l => l.label).concat(pts.filter(p => p.label));
      g.textAlign = 'right'; g.textBaseline = 'middle'; g.font = '11px system-ui, sans-serif';
      let lx = m.l + pw - 4;
      for (const L of leg.reverse()) {
        const tw = g.measureText(L.label).width;
        g.fillStyle = cTxt; g.fillText(L.label, lx, 14);
        g.fillStyle = L.color || cInk; g.fillRect(lx - tw - 16, 12, 12, 3);
        lx -= tw + 26;
      }
      this.cursor(null, []);
    }

    cursor(xv, dots = []) {
      if (!this.map) return;
      const ctx = this.ctx, m = this.o.margin;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, this.c.width, this.c.height);
      ctx.drawImage(this.cache, 0, 0);
      ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
      const { sx, sy } = this.map;
      const ph = this.h - m.t - m.b;
      if (xv !== null && xv !== undefined) {
        const x = sx(xv);
        ctx.strokeStyle = css('--ink', '#111827'); ctx.globalAlpha = 0.35; ctx.lineWidth = 1;
        ctx.setLineDash([4, 3]);
        ctx.beginPath(); ctx.moveTo(x, m.t); ctx.lineTo(x, m.t + ph); ctx.stroke();
        ctx.setLineDash([]); ctx.globalAlpha = 1;
      }
      for (const d of dots) {
        ctx.fillStyle = d.color; ctx.strokeStyle = '#fff'; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(sx(d.x), sy(d.y), 5, 0, 2 * Math.PI); ctx.fill(); ctx.stroke();
      }
    }
  }

  return { Plot, ticks };
})();
