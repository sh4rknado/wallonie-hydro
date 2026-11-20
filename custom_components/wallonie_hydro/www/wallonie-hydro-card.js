/**
 * Carte Lovelace « Wallonie Hydro »
 * Courbe 48 h de la hauteur d'eau (et débit en option) d'une station
 * du portail hydrometrie.wallonie.be.
 *
 * Récupère l'historique via le service WebSocket de l'intégration
 * `wallonie_hydro` (type: wallonie_hydro/history) — aucune clé API requise.
 *
 * Configuration :
 *   type: custom:wallonie-hydro-card
 *   station: L6710
 *   height_entity: sensor.givry_hauteur_eau   (optionnel, sinon autodétection)
 *   hours: 48
 *   show_discharge: true
 *   thresholds: { warn: 1.0, alert: 1.5, high: 2.0 }
 */

const VERSION = "1.0.0";

const CSS = `
ha-card {
  --whc-primary: var(--primary-color, #03a9f4);
  --whc-warn: #ff9800;
  --whc-alert: #f44336;
  --whc-high: #9c27b0;
  --whc-grid: rgba(128, 128, 128, 0.25);
  overflow: hidden;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 16px 16px 0 16px;
}
.title {
  font-size: 1.1em;
  font-weight: 500;
}
.subtitle {
  font-size: 0.8em;
  opacity: 0.7;
}
.value-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 4px 16px 0 16px;
  flex-wrap: wrap;
}
.big-value {
  font-size: 2.1em;
  font-weight: 400;
  line-height: 1.1;
}
.big-unit {
  font-size: 0.9em;
  opacity: 0.6;
}
.trend {
  font-size: 0.85em;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  opacity: 0.85;
}
.trend.up { color: var(--whc-alert); }
.trend.down { color: var(--whc-primary); }
.trend.flat { opacity: 0.6; }
.meta {
  font-size: 0.75em;
  opacity: 0.6;
  padding: 0 16px;
}
.chart-wrap {
  position: relative;
  margin: 8px 8px 4px 8px;
}
svg text {
  font-family: var(--paper-font-body1_-_font-family, sans-serif);
}
.legend {
  display: flex;
  gap: 14px;
  padding: 2px 16px 12px 16px;
  font-size: 0.75em;
  opacity: 0.85;
  flex-wrap: wrap;
}
.legend .item { display: inline-flex; align-items: center; gap: 4px; }
.legend .swatch { width: 14px; height: 3px; border-radius: 2px; display: inline-block; }
.legend .dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.error {
  padding: 16px;
  color: var(--error-color, #db4437);
  font-size: 0.9em;
}
.loading {
  padding: 32px;
  text-align: center;
  opacity: 0.6;
}
`;

class WallonieHydroCard extends HTMLElement {
  static getStubConfig() {
    return { station: "L6710", hours: 48, show_discharge: true };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._data = null;
    this._error = null;
    this._resizeObserver = null;
  }

  setConfig(config) {
    if (!config.station) {
      throw new Error("Vous devez définir 'station' (ex. L6710)");
    }
    this._config = { hours: 48, show_discharge: true, ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._config) this._fetchHistory();
  }

  connectedCallback() {
    this._resizeObserver = new ResizeObserver(() => this._render());
    this._resizeObserver.observe(this);
  }

  disconnectedCallback() {
    if (this._resizeObserver) this._resizeObserver.disconnect();
  }

  getCardSize() {
    return 5;
  }

  async _fetchHistory() {
    const hass = this._hass;
    if (!hass || !this._config) return;
    try {
      const res = await hass.callWS({
        type: "wallonie_hydro/history",
        station_no: String(this._config.station),
        hours: this._config.hours || 48,
      });
      this._data = res;
      this._error = null;
    } catch (err) {
      this._error = err.message || String(err);
      this._data = null;
    }
    this._render();
  }

  // ------------------------------------------------------------------
  // Rendu
  // ------------------------------------------------------------------

  _render() {
    if (!this._config) return;
    const root = this.shadowRoot;
    if (!root) return;

    const cfg = this._config;
    const data = this._data;

    const parts = [`<style>${CSS}</style>`];

    if (this._error) {
      parts.push(
        `<ha-card><div class="error">Erreur : ${this._escape(this._error)}<br>` +
          `<small>Vérifiez que l'intégration « wallonie_hydro » est installée ` +
          `et que la station ${this._escape(String(cfg.station))} y est configurée.</small></div></ha-card>`
      );
      root.innerHTML = parts.join("");
      return;
    }

    if (!data) {
      parts.push(`<div class="loading">Chargement…</div>`);
      root.innerHTML = parts.join("");
      return;
    }

    const title = cfg.name || `${data.station_name || cfg.station}`;
    const subtitle = data.river_name
      ? `${data.river_name} · ${data.station_no}`
      : data.station_no;

    // Valeur courante depuis l'entité si fournie, sinon dernier point
    const current = this._currentValue();

    parts.push(`<ha-card>
    <div class="header">
      <div>
        <div class="title">${this._escape(title)}</div>
        <div class="subtitle">${this._escape(subtitle)}</div>
      </div>
      <div class="subtitle">${this._escape(this._hoursLabel())}</div>
    </div>`);

    parts.push(`<div class="value-row">
      <div class="big-value">${current.html}</div>
      ${this._trendHtml()}
    </div>`);

    parts.push(`<div class="meta">${this._metaLine()}</div>`);

    parts.push(`<div class="chart-wrap">${this._buildSvg()}</div>`);
    parts.push(`<div class="legend">${this._legendHtml()}</div>`);
    parts.push(`</ha-card>`);

    root.innerHTML = parts.join("");
  }

  _currentValue() {
    const cfg = this._config;
    const data = this._data;
    let value = null;
    let unit = data.unit_h || "m";

    if (cfg.height_entity && this._hass) {
      const state = this._hass.states[cfg.height_entity];
      if (state) {
        value = parseFloat(state.state);
        unit = state.attributes.unit_of_measurement || unit;
      }
    }
    if (value === null && data.history_h && data.history_h.length) {
      value = data.history_h[data.history_h.length - 1][1];
    }
    if (value === null || isNaN(value)) {
      return { value: null, html: "—" };
    }
    // coloration selon les seuils
    const th = this._thresholds();
    let color = "inherit";
    if (th.high != null && value >= th.high) color = "var(--whc-high)";
    else if (th.alert != null && value >= th.alert) color = "var(--whc-alert)";
    else if (th.warn != null && value >= th.warn) color = "var(--whc-warn)";
    return {
      value,
      html: `<span style="color:${color}">${value.toFixed(2).replace(".", ",")}</span>` +
            ` <span class="big-unit">${this._escape(unit)}</span>`,
    };
  }

  _trendHtml() {
    // variation sur 1 h à partir de l'historique
    const h = this._data.history_h;
    if (!h || h.length < 2) return "";
    const [tLast, vLast] = h[h.length - 1];
    const last = new Date(tLast).getTime();
    let ref = null;
    for (const [t, v] of h) {
      if (last - new Date(t).getTime() <= 3600e3) {
        ref = v;
        break;
      }
    }
    if (ref == null) return "";
    const d = vLast - ref;
    const abs = Math.abs(d);
    const cls = d > 0.005 ? "up" : d < -0.005 ? "down" : "flat";
    const icon = d > 0.005 ? "▲" : d < -0.005 ? "▼" : "▬";
    const sign = d > 0 ? "+" : "";
    return `<div class="trend ${cls}">${icon} ${sign}${d.toFixed(2).replace(".", ",")} m/1h</div>`;
  }

  _metaLine() {
    const h = this._data.history_h;
    if (!h || !h.length) return "";
    const last = h[h.length - 1][0];
    const d = new Date(last);
    const label = d.toLocaleTimeString("fr-BE", { hour: "2-digit", minute: "2-digit" });
    return `Dernière mesure : ${label} · source hydrometrie.wallonie.be`;
  }

  _hoursLabel() {
    const h = this._config.hours || 48;
    return `48 dernières heures`.replace("48", String(h));
  }

  _thresholds() {
    return this._config.thresholds || {};
  }

  _legendHtml() {
    const th = this._thresholds();
    const items = [];
    if (this._data.unit_h) {
      items.push(
        `<span class="item"><span class="swatch" style="background:var(--whc-primary)"></span>Hauteur (${this._escape(this._data.unit_h)})</span>`
      );
    }
    if (this._config.show_discharge && this._data.unit_q) {
      items.push(
        `<span class="item"><span class="swatch" style="background:#8bc34a;opacity:.75"></span>Débit (${this._escape(this._data.unit_q)})</span>`
      );
    }
    if (th.warn != null)
      items.push(`<span class="item"><span class="dot" style="background:var(--whc-warn)"></span>Vigilance ${th.warn} m</span>`);
    if (th.alert != null)
      items.push(`<span class="item"><span class="dot" style="background:var(--whc-alert)"></span>Alerte ${th.alert} m</span>`);
    if (th.high != null)
      items.push(`<span class="item"><span class="dot" style="background:var(--whc-high)"></span>Crue ${th.high} m</span>`);
    return items.join("");
  }

  // ------------------------------------------------------------------
  // SVG
  // ------------------------------------------------------------------

  _buildSvg() {
    const data = this._data;
    const width = Math.max(280, this.clientWidth || 360) - 16;
    const height = 190;
    const padL = 40;
    const padR = 40;
    const padT = 12;
    const padB = 22;

    const h = data.history_h || [];
    const q = this._config.show_discharge ? data.history_q || [] : [];

    if (!h.length) {
      return `<div class="loading">Aucune donnée sur la période</div>`;
    }

    const th = this._thresholds();
    const thList = [
      ["warn", th.warn, "var(--whc-warn)"],
      ["alert", th.alert, "var(--whc-alert)"],
      ["high", th.high, "var(--whc-high)"],
    ].filter(([, v]) => v != null);

    const now = new Date(h[h.length - 1][0]).getTime();
    const t0 = now - (this._config.hours || 48) * 3600e3;

    let vMin = Math.min(...h.map((p) => p[1]));
    let vMax = Math.max(...h.map((p) => p[1]));
    for (const [, v] of thList) {
      vMax = Math.max(vMax, v);
    }
    if (vMax - vMin < 0.1) {
      vMax = vMin + 0.1;
    }
    vMin = Math.max(0, vMin - (vMax - vMin) * 0.1);
    vMax = vMax + (vMax - vMin) * 0.05;

    // Débit : axe droit, normalisé à sa propre échelle
    let qPath = "";
    let qMax = 1;
    if (q.length) {
      qMax = Math.max(...q.map((p) => p[1])) * 1.15 || 1;
      qPath = this._path(q, t0, now, 0, qMax, padL, width - padR, padT, height - padB);
    }

    const x = (t) => padL + ((t - t0) / (now - t0)) * (width - padL - padR);
    const y = (v) =>
      (height - padB) - ((v - vMin) / (vMax - vMin)) * (height - padT - padB);

    const hPath = this._path(h, t0, now, vMin, vMax, padL, width - padR, padT, height - padB);

    let grid = "";
    // 4 lignes horizontales avec labels
    for (let i = 0; i <= 3; i++) {
      const v = vMin + ((vMax - vMin) * i) / 3;
      const yy = y(v);
      grid +=
        `<line x1="${padL}" y1="${yy.toFixed(1)}" x2="${width - padR}" y2="${yy.toFixed(1)}" ` +
        `stroke="var(--whc-grid)" stroke-width="1" stroke-dasharray="3,4"/>` +
        `<text x="${padL - 5}" y="${(yy + 3).toFixed(1)}" font-size="9" text-anchor="end" fill="rgba(128,128,128,0.9)">` +
        `${v.toFixed(vMax < 3 ? 2 : 1).replace(".", ",")}</text>`;
    }
    // labels temporels : -48h, -24h, maintenant
    const labels = [
      [t0, this._fmtHoursAgo(this._config.hours || 48)],
      [(t0 + now) / 2, ""],
      [now, "maintenant"],
    ];
    labels[1][1] = this._midLabel(t0, now);
    for (const [t, label] of labels) {
      grid +=
        `<text x="${x(t).toFixed(1)}" y="${height - 7}" font-size="9" ` +
        `text-anchor="${t === now ? "end" : t === t0 ? "start" : "middle"}" ` +
        `fill="rgba(128,128,128,0.9)">${label}</text>`;
    }

    // lignes de seuils
    let thLines = "";
    for (const [key, v, color] of thList) {
      if (v > vMax) continue;
      const yy = y(v);
      thLines +=
        `<line x1="${padL}" y1="${yy.toFixed(1)}" x2="${width - padR}" y2="${yy.toFixed(1)}" ` +
        `stroke="${color}" stroke-width="1.2" stroke-dasharray="6,3" opacity="0.8"/>` +
        `<text x="${width - padR + 3}" y="${(yy + 3).toFixed(1)}" font-size="8.5" fill="${color}">${v}</text>`;
    }

    const lastPoint = h[h.length - 1];
    const cx = x(new Date(lastPoint[0]).getTime());
    const cy = y(lastPoint[1]);

    return `<svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}" preserveAspectRatio="none" style="display:block">
      ${grid}
      ${thLines}
      ${qPath ? `<path d="${qPath}" fill="none" stroke="#8bc34a" stroke-width="1.2" opacity="0.55" stroke-dasharray="1,0"/>` : ""}
      <path d="${hPath}" fill="none" stroke="var(--whc-primary)" stroke-width="2" stroke-linejoin="round"/>
      <circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="3.5" fill="var(--whc-primary)"/>
    </svg>`;
  }

  _path(points, t0, t1, vMin, vMax, padL, padR_, padT, padB_) {
    const W = padR_;
    const H = padB_;
    const map = (t, v) => {
      const xx = padL + ((t - t0) / (t1 - t0)) * (W - padL);
      const yy = H - ((v - vMin) / (vMax - vMin)) * (H - padT);
      return [xx, yy];
    };
    let d = "";
    let started = false;
    for (const [ts, val] of points) {
      const t = new Date(ts).getTime();
      if (t < t0) continue;
      const [xx, yy] = map(t, val);
      d += `${started ? "L" : "M"}${xx.toFixed(1)},${yy.toFixed(1)} `;
      started = true;
    }
    return d.trim();
  }

  _fmtHoursAgo(h) {
    return `-${h} h`;
  }

  _midLabel(t0, t1) {
    const mid = new Date((t0 + t1) / 2);
    return mid.toLocaleDateString("fr-BE", { weekday: "short", hour: "2-digit" });
  }

  _escape(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[c]);
  }
}

customElements.define("wallonie-hydro-card", WallonieHydroCard);

// Enregistrement dans la fenêtre pour le panneau de ressources
window.customCards = window.customCards || [];
window.customCards.push({
  type: "wallonie-hydro-card",
  name: "Wallonie Hydro",
  description: "Hauteur d'eau et débit d'une station hydrometrie.wallonie.be (courbe 48 h)",
});

console.info(`%c WALLONIE-HYDRO-CARD v${VERSION} `, "color: white; background: #03a9f4; font-weight: 700;");
