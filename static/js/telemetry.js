/**
 * static/js/telemetry.js - Feature-detected client device telemetry collector.
 */

window.TelemetryCollector = {
  async getBattery() {
    try {
      if ("getBattery" in navigator) {
        const b = await navigator.getBattery();
        return {
          level: Math.round(b.level * 100),
          charging: Boolean(b.charging)
        };
      }
    } catch (e) {
      console.debug("Battery API unavailable:", e);
    }
    return null;
  },

  async getDeviceDetails() {
    const d = {
      userAgent: navigator.userAgent || "",
      platform: navigator.platform || "",
      cpuCores: navigator.hardwareConcurrency ?? null,
      ramGB: navigator.deviceMemory ?? null,
      languages: navigator.languages || [navigator.language],
      screen: {
        w: window.screen?.width ?? null,
        h: window.screen?.height ?? null,
        ratio: window.devicePixelRatio ?? 1
      },
      storage: {},
      network: {},
      tz: {}
    };

    // Network connection
    const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (conn) {
      d.network = {
        type: conn.effectiveType || conn.type || null,
        downlink: conn.downlink ?? null,
        rtt: conn.rtt ?? null,
        saveData: Boolean(conn.saveData)
      };
    }

    // Storage estimation
    try {
      if (navigator.storage?.estimate) {
        const est = await navigator.storage.estimate();
        d.storage.quotaBytes = est.quota ?? null;
        d.storage.usageBytes = est.usage ?? null;
      }
    } catch (e) {}

    // Timezone
    try {
      const opt = Intl.DateTimeFormat().resolvedOptions();
      d.tz = {
        zone: opt.timeZone,
        offset: new Date().getTimezoneOffset()
      };
    } catch (e) {}

    // Query permissions snapshot
    d.permissions = {};
    if (navigator.permissions?.query) {
      for (const name of ["camera", "geolocation"]) {
        try {
          const r = await navigator.permissions.query({ name });
          d.permissions[name] = r.state;
        } catch (e) {}
      }
    }

    return d;
  },

  async collectAll() {
    const [battery, details] = await Promise.all([
      this.getBattery(),
      this.getDeviceDetails()
    ]);
    return { battery, details };
  }
};
