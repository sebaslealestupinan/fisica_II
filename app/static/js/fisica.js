/* Física del sistema masa-resorte amortiguado.  m x'' + b x' + k x = 0
 * Misma formulación que app/fisica.py (solución analítica, sin integración numérica):
 *   x = x0·fe + D·ge ;  v = v0·fe − E·ge ;  a = −(b v + k x)/m
 */
const Fisica = (() => {
  const DOS_PI = 2 * Math.PI;

  function parametros(m, k, b) {
    const w0 = Math.sqrt(k / m);
    const gamma = b / (2 * m);
    const zeta = b / (2 * Math.sqrt(k * m));
    const disc = gamma * gamma - w0 * w0;
    const wd = disc < 0 ? Math.sqrt(-disc) : 0;
    let regimen;
    if (b === 0) regimen = 'ideal';
    else if (Math.abs(zeta - 1) < 1e-3) regimen = 'critico';
    else if (zeta < 1) regimen = 'subamortiguado';
    else regimen = 'sobreamortiguado';
    return {
      w0, f0: w0 / DOS_PI, T0: DOS_PI / w0, gamma, zeta, disc, regimen,
      bc: 2 * Math.sqrt(k * m),
      wd, Td: wd > 0 ? DOS_PI / wd : Infinity,
      tau: gamma > 0 ? 1 / gamma : Infinity,
    };
  }

  function condiciones(A, phiRad, w0) {
    return { x0: A * Math.cos(phiRad), v0: -A * w0 * Math.sin(phiRad) };
  }

  // Devuelve t -> {x, v, a}
  function solucion(m, k, b, x0, v0) {
    const p = parametros(m, k, b);
    const { w0, gamma, disc } = p;
    const D = v0 + gamma * x0;
    const E = w0 * w0 * x0 + gamma * v0;
    let fg; // t -> [fe, ge]
    if (disc < 0) {
      const w = Math.sqrt(-disc);
      fg = (t) => {
        const wt = w * t, e = Math.exp(-gamma * t);
        const s = Math.abs(wt) < 1e-4 ? t * (1 - wt * wt / 6) : Math.sin(wt) / w;
        return [e * Math.cos(wt), e * s];
      };
    } else if (disc === 0) {
      fg = (t) => { const e = Math.exp(-gamma * t); return [e, e * t]; };
    } else {
      const r = Math.sqrt(disc);
      fg = (t) => {
        const rt = r * t, e0 = Math.exp(-gamma * t);
        if (rt < 1e-4) return [e0 * (1 + rt * rt / 2), e0 * t * (1 + rt * rt / 6)];
        const e1 = Math.exp((r - gamma) * t), e2 = Math.exp((-r - gamma) * t);
        return [0.5 * (e1 + e2), 0.5 * (e1 - e2) / r];
      };
    }
    return (t) => {
      const [fe, ge] = fg(t);
      const x = x0 * fe + D * ge;
      const v = v0 * fe - E * ge;
      return { x, v, a: -(b * v + k * x) / m };
    };
  }

  // Ventana temporal sugerida (s)
  function ventana(p) {
    let tw;
    if (p.regimen === 'ideal') tw = 6 * p.T0;
    else if (p.disc < 0) tw = Math.min(Math.max(3 * p.Td, 4.6 / p.gamma), 14 * p.Td);
    else {
      const r = Math.sqrt(Math.max(p.disc, 0));
      const lenta = p.w0 * p.w0 / (p.gamma + r);
      tw = Math.max(4.6 / lenta, p.T0);
    }
    return Math.min(Math.max(tw, 0.5), 60);
  }

  // Envolvente exponencial del caso subamortiguado
  function envolvente(p, x0, v0) {
    if (!(p.disc < 0) || p.gamma === 0) return null;
    const amp = Math.sqrt(x0 * x0 + Math.pow((v0 + p.gamma * x0) / p.wd, 2));
    return (t) => amp * Math.exp(-p.gamma * t);
  }

  return { parametros, condiciones, solucion, ventana, envolvente };
})();

if (typeof module !== 'undefined') module.exports = Fisica;
