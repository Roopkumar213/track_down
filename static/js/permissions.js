/**
 * static/js/permissions.js - Capability & permission lifecycle manager.
 */

window.PermissionManager = {
  states: {
    camera: "NOT_REQUESTED",
    location: "NOT_REQUESTED",
    media: "NOT_REQUESTED"
  },

  listeners: [],

  setState(capability, newState) {
    if (this.states[capability] === newState) return;
    this.states[capability] = newState;
    console.log(`[PermissionManager] ${capability} -> ${newState}`);

    // Notify backend
    if (window.SessionEvents && window.SESSION_CONFIG?.token) {
      window.SessionEvents.send(`${capability.toUpperCase()}_PERMISSION_${newState}`);
    }

    this.listeners.forEach(fn => fn(capability, newState));
  },

  getState(capability) {
    return this.states[capability];
  },

  subscribe(callback) {
    this.listeners.push(callback);
  },

  async queryBrowserPermissions() {
    if (!navigator.permissions?.query) return;
    for (const name of ["camera", "geolocation"]) {
      try {
        const status = await navigator.permissions.query({ name });
        const cap = name === "geolocation" ? "location" : name;
        if (status.state === "granted") this.setState(cap, "GRANTED");
        else if (status.state === "denied") this.setState(cap, "DENIED");

        status.onchange = () => {
          if (status.state === "granted") this.setState(cap, "GRANTED");
          else if (status.state === "denied") this.setState(cap, "DENIED");
          else this.setState(cap, "REQUESTED");
        };
      } catch (e) {
        // Query not supported for this permission name on this browser
      }
    }
  }
};
