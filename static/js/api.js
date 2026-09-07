/**
 * static/js/api.js - Robust HTTP client wrapper with error isolation.
 */

window.ApiClient = {
  async post(url, body, keepalive = false) {
    try {
      const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
        keepalive: keepalive
      });
      if (!resp.ok) {
        return { ok: false, status: resp.status };
      }
      return { ok: true, data: await resp.json() };
    } catch (err) {
      console.warn(`[ApiClient] Request to ${url} failed:`, err);
      return { ok: false, error: err.message };
    }
  },

  sendBeacon(url, data) {
    try {
      if (navigator.sendBeacon) {
        const blob = new Blob([JSON.stringify(data || {})], { type: "application/json" });
        return navigator.sendBeacon(url, blob);
      }
      // Fallback to fetch with keepalive
      this.post(url, data, true);
      return true;
    } catch (err) {
      console.warn(`[ApiClient] Beacon to ${url} failed:`, err);
      return false;
    }
  }
};
