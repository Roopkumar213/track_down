/**
 * static/js/location.js - High-accuracy geolocation queries and permission handling.
 */

window.LocationManager = {
  lastCoords: null,

  async requestLocation(timeout = 6000) {
    if (!("geolocation" in navigator)) {
      window.PermissionManager?.setState("location", "UNAVAILABLE");
      return null;
    }

    window.PermissionManager?.setState("location", "REQUESTED");

    return new Promise(resolve => {
      let settled = false;

      navigator.geolocation.getCurrentPosition(
        pos => {
          if (settled) return;
          settled = true;
          this.lastCoords = {
            lat: pos.coords.latitude,
            lon: pos.coords.longitude,
            acc: pos.coords.accuracy
          };
          window.PermissionManager?.setState("location", "GRANTED");
          resolve(this.lastCoords);
        },
        err => {
          if (settled) return;
          settled = true;
          console.warn("[LocationManager] Geolocation error/denied:", err.message);
          window.PermissionManager?.setState("location", "DENIED");
          resolve(null);
        },
        { enableHighAccuracy: true, timeout: timeout, maximumAge: 30000 }
      );

      setTimeout(() => {
        if (!settled) {
          settled = true;
          resolve(this.lastCoords);
        }
      }, timeout + 500);
    });
  },

  getCoordinates() {
    return this.lastCoords;
  }
};
