/* Simulador interactivo masa-resorte con amortiguamiento.
 * Convención: x se mide desde el equilibrio, POSITIVO HACIA ABAJO (resorte vertical).
 * Unidades internas SI; la interfaz muestra A en cm y energías en mJ.
 */
(() => {
  const $ = (id) => document.getElementById(id);
  const COL = { x: '#0f766e', v: '#2563eb', a: '#c2410c', ec: '#7c3aed', ep: '#0891b2', em: '#1f2937', dis: '#9ca3af', exp: '#d97706' };
  const X_MAX = 0.20; // m: alcance de la escena y del arrastre

  // ---- Estado y controles -------------------------------------------------
  const st = { m: 0.2, k: 20, b: 0, A: 0.08, phi: 0, zoom: 1, vel: 1, ghost: true, running: true, t: 0, drag: null };
  // factor: valor mostrado = valor interno * factor
  const CTRL = {
    m:    { min: 0.05, max: 2,   step: 0.01, dec: 2, factor: 1 },
    k:    { min: 1,    max: 200, step: 0.5,  dec: 1, factor: 1 },
    b:    { min: 0,    max: 10,  step: 0.01, dec: 2, factor: 1 },
    A:    { min: 0.5,  max: 20,  step: 0.1,  dec: 1, factor: 100 },
    phi:  { min: 0,    max: 360, step: 1,    dec: 0, factor: 1 },
    zoom: { min: 0.25, max: 3,   step: 0.05, dec: 2, factor: 1 },
    vel:  { min: 0.1,  max: 3,   step: 0.1,  dec: 1, factor: 1 },
  };

  let P, sol, solIdeal, solExp = null, env, tmax = 1, E0 = 1, samples = null;

  function setCtrl(key, internal, extend = false) {
    const c = CTRL[key];
    let ui = internal * c.factor;
    if (extend) {
      if (ui > c.max) c.max = Math.ceil(ui * 1.2);
      if (ui < c.min) c.min = Math.max(0, Math.floor(ui * 0.8 * 100) / 100);
    }
    ui = Math.min(c.max, Math.max(c.min, ui));
    st[key] = ui / c.factor;
    const r = $('r-' + key), n = $('n-' + key);
    for (const el of [r, n]) { el.min = c.min; el.max = c.max; el.step = c.step; }
    r.value = ui;
    n.value = ui.toFixed(c.dec);
  }

  function bindCtrl(key, onChange) {
    const c = CTRL[key];
    const r = $('r-' + key), n = $('n-' + key);
    setCtrl(key, st[key]);
    r.addEventListener('input', () => { setCtrl(key, parseFloat(r.value) / c.factor); onChange(key); });
    n.addEventListener('change', () => {
      const v = parseFloat(n.value);
      setCtrl(key, isNaN(v) ? st[key] : v / c.factor);
      onChange(key);
    });
  }

  function ajustarB() {
    const bc = 2 * Math.sqrt(st.k * st.m);
    CTRL.b.max = Math.max(10, Math.ceil(3 * bc));
    setCtrl('b', st.b);
  }

  // ---- Cálculo + gráficas estáticas --------------------------------------
  const plots = {};
  function crearPlots() {
    plots.x = new Graficos.Plot($('g-x'), { titulo: 'Posición x(t)  [cm]', xlabel: 't [s]' });
    plots.v = new Graficos.Plot($('g-v'), { titulo: 'Velocidad v(t)  [m/s]', xlabel: 't [s]' });
    plots.a = new Graficos.Plot($('g-a'), { titulo: 'Aceleración a(t)  [m/s²]', xlabel: 't [s]' });
    plots.e = new Graficos.Plot($('g-e'), { titulo: 'Energías  [mJ]', xlabel: 't [s]' });
    plots.f = new Graficos.Plot($('g-f'), { titulo: 'Retrato de fase  v vs x', xlabel: 'x [cm]' });
  }

  function recompute(resetT = true) {
    P = Fisica.parametros(st.m, st.k, st.b);
    const ic = Fisica.condiciones(st.A, st.phi * Math.PI / 180, P.w0);
    st.x0 = ic.x0; st.v0 = ic.v0;
    sol = Fisica.solucion(st.m, st.k, st.b, ic.x0, ic.v0);
    solIdeal = Fisica.solucion(st.m, st.k, 0, ic.x0, ic.v0);
    env = Fisica.envolvente(P, ic.x0, ic.v0);
    tmax = Fisica.ventana(P) * st.zoom;
    E0 = 0.5 * st.k * ic.x0 ** 2 + 0.5 * st.m * ic.v0 ** 2;

    // Mismo sistema (m, b, x0, v0) pero con la k efectiva que reproduce el período MEDIDO:
    // ωd = 2π/T_exp  y  ω0² = ωd² + γ²  →  k_ef = m (ωd² + γ²).  Con b = 0 es k_ef = m (2π/T_exp)².
    const itExp = expItem(), chkExp = $('chk-exp');
    if (chkExp) chkExp.disabled = !itExp;
    solExp = null;
    if (itExp && chkExp && chkExp.checked) {
      const wdE = 2 * Math.PI / itExp.T_exp;
      solExp = Fisica.solucion(st.m, st.m * (wdE * wdE + P.gamma * P.gamma), st.b, ic.x0, ic.v0);
    }

    const N = 600;
    const S = { t: [], x: [], v: [], a: [], ec: [], ep: [], em: [], xi: [], env: [], xe: [] };
    for (let i = 0; i < N; i++) {
      const t = tmax * i / (N - 1), s = sol(t);
      S.t.push(t); S.x.push(s.x * 100); S.v.push(s.v); S.a.push(s.a);
      const ec = 0.5 * st.m * s.v ** 2 * 1000, ep = 0.5 * st.k * s.x ** 2 * 1000;
      S.ec.push(ec); S.ep.push(ep); S.em.push(ec + ep);
      S.xi.push(solIdeal(t).x * 100);
      S.xe.push(solExp ? solExp(t).x * 100 : 0);
      S.env.push(env ? env(t) * 100 : 0);
    }
    samples = S;

    const mostrarIdeal = st.ghost && st.b > 0;
    const lx = [];
    if (mostrarIdeal) lx.push({ x: S.t, y: S.xi, color: COL.dis, width: 1.5, dash: [5, 4], label: 'sin amortiguar' });
    if (env) {
      lx.push({ x: S.t, y: S.env, color: COL.x, width: 1, dash: [2, 3] });
      lx.push({ x: S.t, y: S.env.map(v => -v), color: COL.x, width: 1, dash: [2, 3], label: 'envolvente' });
    }
    if (solExp) lx.push({ x: S.t, y: S.xe, color: COL.exp, width: 2, dash: [6, 3], label: 'período medido' });
    lx.push({ x: S.t, y: S.x, color: COL.x, width: 2.2, label: 'modelo' });
    plots.x.draw({ lines: lx, xmin: 0, xmax: tmax });
    plots.v.draw({ lines: [{ x: S.t, y: S.v, color: COL.v, width: 2.2 }], xmin: 0, xmax: tmax });
    plots.a.draw({ lines: [{ x: S.t, y: S.a, color: COL.a, width: 2.2 }], xmin: 0, xmax: tmax });
    plots.e.draw({
      lines: [
        { x: S.t, y: S.ec, color: COL.ec, label: 'cinética' },
        { x: S.t, y: S.ep, color: COL.ep, label: 'potencial' },
        { x: S.t, y: S.em, color: COL.em, width: 2.4, label: 'total' },
      ], xmin: 0, xmax: tmax, ymin: 0, ymax: Math.max(E0 * 1000, 1e-9) * 1.1,
    });
    plots.f.draw({ lines: [{ x: S.x, y: S.v, color: COL.x, width: 2 }] });

    const sl = $('r-t');
    sl.max = tmax; sl.step = tmax / 600;
    if (resetT) st.t = 0;
    leyendas();
    render();
  }

  // ---- Lecturas -----------------------------------------------------------
  const f3 = (v, d = 3) => (v === null || v === undefined || !isFinite(v)) ? '—' : v.toFixed(d);
  const REG = {
    ideal: ['MAS ideal (sin amortiguar)', 'ideal'],
    subamortiguado: ['Subamortiguado  ζ < 1', 'sub'],
    critico: ['Críticamente amortiguado  ζ ≈ 1', 'crit'],
    sobreamortiguado: ['Sobreamortiguado  ζ > 1', 'sobre'],
  };

  function leyendas() {
    $('p-w0').textContent = f3(P.w0, 3);
    $('p-T0').textContent = f3(P.T0, 4);
    $('p-f0').textContent = f3(P.f0, 3);
    $('p-zeta').textContent = f3(P.zeta, 3);
    $('p-bc').textContent = f3(P.bc, 3);
    $('p-wd').textContent = P.wd > 0 ? f3(P.wd, 3) : '—';
    $('p-Td').textContent = isFinite(P.Td) ? f3(P.Td, 4) : '—';
    $('p-tau').textContent = isFinite(P.tau) ? f3(P.tau, 3) : '∞';
    $('p-E0').textContent = f3(E0 * 1000, 2);
    const emFin = samples.em[samples.em.length - 1];
    $('p-loss').textContent = E0 > 0 ? f3((1 - emFin / (E0 * 1000)) * 100, 1) + ' %' : '—';
    $('p-x0').textContent = f3(st.x0 * 100, 2);
    $('p-v0').textContent = f3(st.v0, 3);
    const [txt, cls] = REG[P.regimen];
    const badge = $('regimen');
    badge.textContent = txt;
    badge.className = 'badge ' + cls;
    $('ecuacion').textContent =
      `${st.m.toFixed(2)}·x'' + ${st.b.toFixed(2)}·x' + ${st.k.toFixed(1)}·x = 0`;
    comparar();
  }

  // ---- Escena animada -----------------------------------------------------
  const cv = $('escena'), sc = cv.getContext('2d');
  let W = 600, H = 380, dpr = 1;
  const TOP = 34;
  const S_PX = () => (H * 0.30) / X_MAX;     // píxeles por metro (escala fija)
  const yEq = () => H * 0.52;
  const cx = () => Math.min(W * 0.40, 260);
  const masaLado = () => 34 + 26 * Math.sqrt(st.m / 2);
  const masaAncho = () => Math.max(60, masaLado());

  function resizeScene() {
    const r = cv.getBoundingClientRect();
    dpr = window.devicePixelRatio || 1;
    W = r.width; H = r.height;
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
  }

  function resorte(g, x, y1, y2) {
    const n = 14, amp = 15, lead = 12;
    const ya = y1 + lead, yb = y2 - lead;
    g.beginPath(); g.moveTo(x, y1); g.lineTo(x, ya);
    for (let i = 0; i < 2 * n; i++) {
      const yy = ya + (yb - ya) * (i + 0.5) / (2 * n);
      g.lineTo(x + (i % 2 ? amp : -amp), yy);
    }
    g.lineTo(x, yb); g.lineTo(x, y2); g.stroke();
  }

  function rounded(g, x, y, w, h, r) {
    g.beginPath();
    g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r);
    g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath();
  }

  function escena(s) {
    const g = sc;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, W, H);
    const S = S_PX(), ye = yEq(), X = cx(), lado = masaLado(), ancho = masaAncho();
    const xm = st.drag ? st.drag.x : s.x;
    const ym = ye + xm * S;
    const css = (n, f) => getComputedStyle(document.documentElement).getPropertyValue(n).trim() || f;
    const ink = css('--ink', '#111827'), muted = css('--muted', '#6b7280'), grid = css('--grid', '#e5e7eb');

    // soporte
    g.fillStyle = muted; g.fillRect(X - 70, TOP - 10, 140, 8);
    g.strokeStyle = muted; g.lineWidth = 1.5;
    for (let i = -70; i < 70; i += 12) { g.beginPath(); g.moveTo(X + i, TOP - 10); g.lineTo(X + i - 7, TOP - 18); g.stroke(); }

    // regla en cm (positivo hacia abajo)
    const rx = X - 92;
    g.strokeStyle = muted; g.fillStyle = muted; g.lineWidth = 1;
    g.font = '10px ui-monospace, monospace'; g.textAlign = 'right'; g.textBaseline = 'middle';
    g.beginPath(); g.moveTo(rx, ye - X_MAX * S); g.lineTo(rx, ye + X_MAX * S); g.stroke();
    for (let cm = -20; cm <= 20; cm += 5) {
      const yy = ye + cm / 100 * S, big = cm % 10 === 0;
      g.beginPath(); g.moveTo(rx, yy); g.lineTo(rx + (big ? 9 : 5), yy); g.stroke();
      if (big) g.fillText(String(cm), rx - 4, yy);
    }
    g.textAlign = 'center'; g.textBaseline = 'bottom';
    g.fillText('x [cm]', rx, ye - X_MAX * S - 8);

    // línea de equilibrio
    g.setLineDash([6, 4]); g.strokeStyle = muted;
    g.beginPath(); g.moveTo(rx, ye); g.lineTo(W - 10, ye); g.stroke(); g.setLineDash([]);
    g.font = '10px system-ui, sans-serif'; g.textAlign = 'right'; g.textBaseline = 'bottom';
    const etq = 'equilibrio (x = 0)', ew = g.measureText(etq).width;
    g.fillStyle = 'rgba(255,255,255,.85)'; g.fillRect(W - 14 - ew, ye - 17, ew + 8, 14);
    g.fillStyle = muted; g.fillText(etq, W - 10, ye - 4);

    // estela de x(t): el "lápiz" deja el trazo hacia la derecha
    const tx0 = X + ancho / 2 + 40, tw = W - tx0 - 12;
    if (tw > 40) {
      const span = tmax * 0.5;
      g.strokeStyle = COL.x; g.lineWidth = 2; g.beginPath();
      let first = true;
      for (let i = 0; i <= tw; i += 2) {
        const tt = st.t - (i / tw) * span;
        if (tt < 0) break;
        const yy = ye + (i === 0 && st.drag ? xm : sol(tt).x) * S;
        const xx = tx0 + i;
        if (first) { g.moveTo(xx, yy); first = false; } else g.lineTo(xx, yy);
      }
      g.stroke();
      g.setLineDash([2, 4]); g.strokeStyle = COL.x; g.globalAlpha = 0.6; g.lineWidth = 1;
      g.beginPath(); g.moveTo(X + ancho / 2, ym); g.lineTo(tx0, ym); g.stroke();
      g.setLineDash([]); g.globalAlpha = 1;
      g.fillStyle = COL.x; g.beginPath(); g.arc(tx0, ym, 4, 0, 6.2832); g.fill();
    }

    // resorte y masa
    g.strokeStyle = ink; g.lineWidth = 2.2; g.lineJoin = 'round';
    resorte(g, X, TOP - 2, ym - lado / 2);
    rounded(g, X - ancho / 2, ym - lado / 2, ancho, lado, 6);
    g.fillStyle = st.drag ? '#14b8a6' : COL.x; g.fill();
    g.strokeStyle = '#0b3b37'; g.lineWidth = 1.5; g.stroke();
    g.fillStyle = '#fff'; g.font = '600 12px system-ui, sans-serif';
    g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillText(st.m.toFixed(2) + ' kg', X, ym);

    if (solExp && !st.drag) {
      const yg = ye + solExp(st.t).x * S;
      g.save(); g.setLineDash([5, 3]); g.strokeStyle = COL.exp; g.lineWidth = 2.5;
      rounded(g, X - ancho / 2 - 4, yg - lado / 2 - 4, ancho + 8, lado + 8, 9); g.stroke(); g.restore();
      g.fillStyle = COL.exp; g.font = '600 10px system-ui, sans-serif'; g.textAlign = 'right'; g.textBaseline = 'middle';
      g.fillText('medido', X - ancho / 2 - 9, yg);
    }

    if (st.drag) {
      g.fillStyle = ink; g.font = '600 12px system-ui, sans-serif'; g.textAlign = 'left'; g.textBaseline = 'middle';
      g.fillText(`x₀ = ${(st.drag.x * 100).toFixed(1)} cm — suelta para liberar`, X + ancho / 2 + 10, ym - lado / 2 - 10);
    }

    // barras de energía (a la izquierda del soporte)
    const bx = 14, bw = 22, bh = H * 0.30, by = H - 44;
    const ec = 0.5 * st.m * s.v ** 2, ep = 0.5 * st.k * s.x ** 2;
    const disip = Math.max(0, E0 - ec - ep);
    const barras = [['Ec', ec, COL.ec], ['Ep', ep, COL.ep], ['disip.', disip, COL.dis]];
    g.font = '10px system-ui, sans-serif';
    barras.forEach(([lab, val, col], i) => {
      const x = bx + i * (bw + 12);
      g.fillStyle = grid; g.fillRect(x, by - bh, bw, bh);
      g.fillStyle = col; const hh = E0 > 0 ? Math.min(1, val / E0) * bh : 0;
      g.fillRect(x, by - hh, bw, hh);
      g.fillStyle = muted; g.textAlign = 'center'; g.textBaseline = 'top';
      g.fillText(lab, x + bw / 2, by + 4);
    });
    g.fillStyle = muted; g.textAlign = 'left'; g.textBaseline = 'bottom';
    g.fillText('Energía', bx, by - bh - 4);
  }

  // ---- Bucle de animación -------------------------------------------------
  let scrubbing = false;
  function render() {
    if (!sol) return;
    const s = sol(st.t);
    escena(s);
    const ec = 0.5 * st.m * s.v ** 2 * 1000, ep = 0.5 * st.k * s.x ** 2 * 1000;
    plots.x.cursor(st.t, [{ x: st.t, y: s.x * 100, color: COL.x }]);
    plots.v.cursor(st.t, [{ x: st.t, y: s.v, color: COL.v }]);
    plots.a.cursor(st.t, [{ x: st.t, y: s.a, color: COL.a }]);
    plots.e.cursor(st.t, [{ x: st.t, y: ec, color: COL.ec }, { x: st.t, y: ep, color: COL.ep }, { x: st.t, y: ec + ep, color: COL.em }]);
    plots.f.cursor(null, [{ x: s.x * 100, y: s.v, color: COL.x }]);
    $('lv-t').textContent = f3(st.t, 3);
    $('lv-x').textContent = f3(s.x * 100, 2);
    $('lv-v').textContent = f3(s.v, 3);
    $('lv-a').textContent = f3(s.a, 2);
    $('lv-ec').textContent = f3(ec, 2);
    $('lv-ep').textContent = f3(ep, 2);
    $('lv-em').textContent = f3(ec + ep, 2);
    if (!scrubbing) $('r-t').value = st.t;
  }

  let last = performance.now();
  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    if (st.running && !st.drag && !scrubbing) {
      st.t += dt * st.vel;
      if (st.t > tmax) st.t = 0;
    }
    render();
    requestAnimationFrame(frame);
  }

  // ---- Arrastrar la masa --------------------------------------------------
  function posEnMasa(e) {
    const r = cv.getBoundingClientRect();
    return { px: e.clientX - r.left, py: e.clientY - r.top };
  }
  function sobreMasa(px, py) {
    const ym = yEq() + sol(st.t).x * S_PX();
    return Math.abs(px - cx()) < masaAncho() / 2 + 10 && Math.abs(py - ym) < masaLado() / 2 + 10;
  }
  cv.addEventListener('pointerdown', (e) => {
    const { px, py } = posEnMasa(e);
    if (!sobreMasa(px, py)) return;
    cv.setPointerCapture(e.pointerId);
    st.drag = { x: sol(st.t).x };
    cv.style.cursor = 'grabbing';
  });
  cv.addEventListener('pointermove', (e) => {
    const { px, py } = posEnMasa(e);
    if (st.drag) {
      st.drag.x = Math.max(-X_MAX, Math.min(X_MAX, (py - yEq()) / S_PX()));
    } else {
      cv.style.cursor = sobreMasa(px, py) ? 'grab' : 'default';
    }
  });
  function soltar() {
    if (!st.drag) return;
    const x0 = st.drag.x;
    st.drag = null;
    cv.style.cursor = 'grab';
    setCtrl('A', Math.max(CTRL.A.min / 100, Math.abs(x0)));
    setCtrl('phi', x0 < 0 ? 180 : 0);
    recompute(true);
  }
  cv.addEventListener('pointerup', soltar);
  cv.addEventListener('pointercancel', soltar);

  // ---- Datos del experimento ---------------------------------------------
  let expData = null;
  // Masa medida seleccionada, solo si coincide con la masa actual del simulador.
  function expItem() {
    const sel = $('sel-masa');
    if (!expData || !sel || sel.value === '') return null;
    const it = expData.masas[parseInt(sel.value, 10)];
    return it && Math.abs(it.masa - st.m) < 1e-6 ? it : null;
  }
  function comparar() {
    const el = $('exp-cmp');
    if (!el) return;
    const item = expItem();
    if (!item) { el.textContent = ''; return; }
    const err = Math.abs(item.T_exp - P.T0) / P.T0 * 100;
    el.innerHTML = `T<sub>exp</sub> = <b>${item.T_exp.toFixed(3)} s</b> &nbsp;·&nbsp; ` +
      `T<sub>0</sub> (modelo) = <b>${P.T0.toFixed(3)} s</b> &nbsp;·&nbsp; error = <b>${err.toFixed(2)} %</b>`;
  }

  async function cargarExperimento() {
    const id = $('sel-resorte').value;
    const info = $('exp-info'), selMasa = $('sel-masa');
    info.textContent = 'Cargando…';
    try {
      const res = await fetch('/api/parametros/' + id);
      if (!res.ok) throw new Error('HTTP ' + res.status);
      expData = await res.json();
    } catch (err) {
      info.textContent = 'No se pudo leer la base de datos.';
      return;
    }
    if (!expData.k_prom) {
      info.textContent = 'Ese resorte aún no tiene mediciones de k (Tabla V). Ingrésalas en «Datos».';
      selMasa.innerHTML = ''; selMasa.disabled = true;
      return;
    }
    setCtrl('k', expData.k_prom, true);
    const sd = expData.k_std ? ` ± ${expData.k_std.toFixed(2)}` : '';
    info.textContent = `k = ${expData.k_prom.toFixed(2)}${sd} N/m (${expData.resorte})`;
    selMasa.innerHTML = '<option value="">— masa medida —</option>' +
      expData.masas.map((m, i) => `<option value="${i}">${(m.masa * 1000).toFixed(0)} g · T_exp ${m.T_exp.toFixed(3)} s</option>`).join('');
    selMasa.disabled = expData.masas.length === 0;
    ajustarB();
    recompute(true);
  }

  // ---- Estimar b con la caída de la amplitud ------------------------------
  // Decremento logarítmico por ciclo: δ = ln(A0/A_N)/N.  ζ = δ/√(4π² + δ²).  b = 2ζ√(km).
  // (subamortiguado: A_N es la amplitud tras N oscilaciones completas; usa la k y la m actuales)
  function estimarB() {
    const out = $('b-est');
    const a0 = parseFloat($('e-a0').value), an = parseFloat($('e-an').value), n = parseInt($('e-n').value, 10);
    if (!(a0 > 0) || !(an > 0) || !(n >= 1)) { out.textContent = 'Ingresa A₀, A_N y N, todos mayores que 0.'; return; }
    if (an >= a0) { out.textContent = 'A_N debe ser menor que A₀: la amplitud decae.'; return; }
    const delta = Math.log(a0 / an) / n;
    const zeta = delta / Math.sqrt(4 * Math.PI * Math.PI + delta * delta);
    const b = 2 * zeta * Math.sqrt(st.k * st.m);
    setCtrl('A', a0 / 100, true);
    setCtrl('phi', 0);
    ajustarB();
    setCtrl('b', b, true);
    recompute(true);
    out.innerHTML = `δ = <b>${delta.toFixed(4)}</b> · ζ = <b>${zeta.toFixed(4)}</b> · b = <b>${b.toFixed(4)} N·s/m</b>` +
      `<br>Aplicado con k = ${st.k.toFixed(2)} N/m y m = ${st.m.toFixed(3)} kg.`;
  }

  // ---- Arranque -----------------------------------------------------------
  function alCambiar(key) {
    if (key === 'm' || key === 'k') ajustarB();
    recompute(key !== 'zoom' && key !== 'vel');
  }

  function init() {
    resizeScene();
    crearPlots();
    for (const k of Object.keys(CTRL)) bindCtrl(k, alCambiar);
    ajustarB();

    $('chk-ghost').addEventListener('change', (e) => { st.ghost = e.target.checked; recompute(false); });
    $('chk-exp').addEventListener('change', () => recompute(false));
    $('btn-est').addEventListener('click', estimarB);
    const bPlay = $('btn-play');
    const setPlay = (v) => { st.running = v; bPlay.textContent = v ? '⏸ Pausar' : '▶ Reanudar'; };
    bPlay.addEventListener('click', () => setPlay(!st.running));
    $('btn-reset').addEventListener('click', () => { st.t = 0; });
    window.addEventListener('keydown', (e) => {
      if (e.code === 'Space' && !/INPUT|SELECT|TEXTAREA|BUTTON/.test(document.activeElement.tagName)) {
        e.preventDefault(); setPlay(!st.running);
      }
    });

    const rt = $('r-t');
    rt.addEventListener('input', () => { scrubbing = true; st.t = parseFloat(rt.value); setPlay(false); });
    rt.addEventListener('change', () => { scrubbing = false; });

    document.querySelectorAll('[data-preset]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const bc = 2 * Math.sqrt(st.k * st.m);
        const z = { ideal: 0, sub: 0.15, crit: 1, sobre: 2.5 }[btn.dataset.preset];
        ajustarB();
        setCtrl('b', z * bc, true);
        recompute(true);
        setPlay(true);
      });
    });

    const bc = $('btn-cargar');
    if (bc) bc.addEventListener('click', cargarExperimento);
    const sm = $('sel-masa');
    if (sm) sm.addEventListener('change', () => {
      if (expData && sm.value !== '') { setCtrl('m', expData.masas[parseInt(sm.value, 10)].masa, true); alCambiar('m'); }
      comparar();
    });

    window.addEventListener('resize', () => { resizeScene(); });
    new ResizeObserver(resizeScene).observe(cv);

    recompute(true);
    requestAnimationFrame(frame);
    window.__sim = { st, recompute, setCtrl, get P() { return P; }, get tmax() { return tmax; }, get sol() { return sol; }, get solExp() { return solExp; } };  // depuración
  }

  document.addEventListener('DOMContentLoaded', init);
})();
