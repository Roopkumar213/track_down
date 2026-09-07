/**
 * static/js/events.js - Dispatches structured session events.
 */

window.SessionEvents = {
  send(eventName, metadata = {}) {
    const token = window.SESSION_CONFIG?.token;
    if (!token) return;

    window.ApiClient.post(`/event/${token}`, {
      event: eventName,
      timestamp: new Date().toISOString(),
      metadata: metadata
    });
  }
};
