/* Página de comparación: T vs m y T² vs m, con datos de /api/comparacion/<id>. */
(async () => {
  const $ = (id) => document.getElementById(id);
  const COL = { teo: '#0f766e', exp: '#c2410c', fit: '#2563eb' };
  const DOS_PI = 2 * Math.PI;
  const num = (v, d = 3) => (v === null || v === undefined || !isFinite(v)) ? '—' : v.toFixed(d);

  const pT = new Graficos.Plot($('c-T'), { titulo: 'Período T vs masa m', xlabel: 'm [kg]' });
  const pT2 = new Graficos.Plot($('c-T2'), { titulo: 'T² vs masa m', xlabel: 'm [kg]' });
  const msg = $('cmp-msg');
  const aviso = (t) => { msg.hidden = false; msg.textContent = t; };

  let d;
  try {
    const res = await fetch('/api/comparacion/' + $('cmp').dataset.rid);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    d = await res.json();
  } catch (e) {
    aviso('No se pudieron leer los datos.');
    return;
  }

  const P = d.puntos;
  if (P.length === 0) aviso('Aún no hay períodos medidos para este resorte. Ingrésalos en «Datos» (Tabla VI).');
  else if (!d.k_prom) aviso('Hay períodos medidos, pero falta la k de la Tabla V: se muestran solo los puntos experimentales.');
  else msg.hidden = true;

  // ---- tabla resumen ----
  $('cmp-filas').innerHTML = P.length ? P.map((p) =>
    `<tr><td class="num">${p.masa.toFixed(4)}</td><td class="num">${p.n}</td><td class="num">${num(p.T_exp, 4)}</td>` +
    `<td class="num">${num(p.T_teo, 4)}</td><td class="num">${p.error === null ? '—' : p.error.toFixed(2) + ' %'}</td></tr>`
  ).join('') : '<tr><td colspan="5" class="vacio">Sin datos.</td></tr>';
  $('cmp-errmed').textContent = d.error_medio === null ? '—' : d.error_medio.toFixed(2) + ' %';

  // ---- k por dos métodos ----
  $('k-hooke').textContent = d.k_prom ? num(d.k_prom, 2) + (d.k_std ? ' ± ' + num(d.k_std, 2) : '') + ' N/m' : '—';
  if (d.ajuste) {
    $('k-ajuste').textContent = num(d.ajuste.k_ajuste, 2) + ' N/m';
    $('k-r2').textContent = num(d.ajuste.r2, 4);
    $('k-ord').textContent = num(d.ajuste.ordenada, 4);
    $('k-dif').textContent = d.k_prom ? num(Math.abs(d.ajuste.k_ajuste - d.k_prom) / d.k_prom * 100, 2) + ' %' : '—';
  } else if (P.length) {
    $('k-ajuste').textContent = 'necesita ≥ 2 masas distintas';
  }

  // ---- gráficas ----
  const masas = P.map((p) => p.masa);
  const mmax = masas.length ? Math.max(...masas) * 1.15 : 1;
  const mm = Array.from({ length: 80 }, (_, i) => mmax * i / 79);

  const lT = [], lT2 = [];
  if (d.k_prom) {
    lT.push({ x: mm, y: mm.map((m) => DOS_PI * Math.sqrt(m / d.k_prom)), color: COL.teo, label: 'teórico (k Hooke)' });
    lT2.push({ x: mm, y: mm.map((m) => DOS_PI * DOS_PI * m / d.k_prom), color: COL.teo, label: 'teórico (k Hooke)' });
  }
  if (d.ajuste) {
    const a = d.ajuste;
    lT2.push({ x: mm, y: mm.map((m) => a.pendiente * m + a.ordenada), color: COL.fit, dash: [6, 4], label: 'ajuste lineal' });
    lT.push({ x: mm, y: mm.map((m) => Math.sqrt(Math.max(0, a.pendiente * m + a.ordenada))), color: COL.fit, dash: [6, 4], label: 'ajuste lineal' });
  }
  pT.draw({
    lines: lT, xmin: 0, xmax: mmax,
    points: P.length ? [{ x: masas, y: P.map((p) => p.T_exp), color: COL.exp, r: 5, label: 'experimental' }] : [],
  });
  pT2.draw({
    lines: lT2, xmin: 0, xmax: mmax,
    points: P.length ? [{ x: masas, y: P.map((p) => p.T_exp * p.T_exp), color: COL.exp, r: 5, label: 'experimental' }] : [],
  });
})();
