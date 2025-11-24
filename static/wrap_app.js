// static/wrap_app.js
(async () => {
  const consentChk = document.getElementById("consentChk");
  const startBtn = document.getElementById("startBtn");
  const stopBtn = document.getElementById("stopBtn");
  const video = document.getElementById("video");
  const batteryEl = document.getElementById("battery");
  const ipEl = document.getElementById("ip");
  const coordsEl = document.getElementById("coords");
  const logEl = document.getElementById("log");

  let stream = null;
  let captureInterval = null;
  const captureMs = 5000;
  const token = TOKEN;

  // Re-use a single offscreen canvas instead of recreating each time
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");

  consentChk.addEventListener("change", () => {
    startBtn.disabled = !consentChk.checked;
  });

  function log(...args) {
    logEl.textContent =
      `${new Date().toLocaleTimeString()} — ${args.join(" ")}\n` +
      logEl.textContent;
  }

  function json(o) {
    return JSON.stringify(o);
  }

  async function fetchIp() {
    try {
      const res = await fetch(`/upload_info/${token}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: json({ battery: null, coords: null }),
      });
      const j = await res.json();
      ipEl.textContent = (j.stored && j.stored.ip) || "unknown";
      log("IP stored:", (j.stored && j.stored.ip) || "unknown");
    } catch (e) {
      log("IP fetch error", e);
    }
  }

  async function sendInfo(battery, coords) {
    try {
      await fetch(`/upload_info/${token}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: json({ battery, coords }),
      });
    } catch (e) {
      log("sendInfo error", e);
    }
  }

  // Wait until video has real dimensions / frame
  function waitForVideoReady(maxWaitMs = 3000) {
    return new Promise((resolve) => {
      if (video.videoWidth > 0 && video.videoHeight > 0) {
        return resolve(true);
      }
      let done = false;

      function onReady() {
        if (!done && video.videoWidth > 0 && video.videoHeight > 0) {
          done = true;
          cleanup();
          resolve(true);
        }
      }

      function cleanup() {
        video.removeEventListener("loadedmetadata", onReady);
        video.removeEventListener("canplay", onReady);
      }

      video.addEventListener("loadedmetadata", onReady);
      video.addEventListener("canplay", onReady);

      setTimeout(() => {
        if (!done) {
          done = true;
          cleanup();
          resolve(false);
        }
      }, maxWaitMs);
    });
  }

  async function captureAndUpload() {
    if (!stream) return;

    // Make sure we actually have a frame
    if (!video.videoWidth || !video.videoHeight) {
      log("Video frame not ready, skipping capture");
      return;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const dataUrl = canvas.toDataURL("image/jpeg", 0.7);

    // Sanity log: length of payload
    log("Capturing frame, dataUrl length:", dataUrl.length);

    try {
      const res = await fetch(`/upload_image/${token}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: json({ image_b64: dataUrl }),
      });

      const j = await res.json();
      if (j && j.filename) {
        log("Uploaded image:", j.filename);
      } else {
        log("Image upload response without filename");
      }
    } catch (e) {
      log("Image upload failed", e);
    }
  }

  async function readBattery() {
    try {
      if (navigator.getBattery) {
        const bat = await navigator.getBattery();
        const info = { level: bat.level, charging: bat.charging };
        batteryEl.textContent = `${Math.round(info.level * 100)}% ${
          info.charging ? "(charging)" : ""
        }`;
        return info;
      } else {
        batteryEl.textContent = "unsupported";
        return null;
      }
    } catch (e) {
      batteryEl.textContent = "error";
      return null;
    }
  }

  async function getLocation() {
    return new Promise((resolve) => {
      if (!navigator.geolocation) {
        coordsEl.textContent = "unsupported";
        resolve(null);
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const coords = {
            lat: pos.coords.latitude,
            lon: pos.coords.longitude,
            acc: pos.coords.accuracy,
          };
          coordsEl.textContent = `${coords.lat.toFixed(
            6
          )}, ${coords.lon.toFixed(6)} (±${coords.acc}m)`;
          resolve(coords);
        },
        () => {
          coordsEl.textContent = "denied";
          resolve(null);
        },
        { enableHighAccuracy: true, maximumAge: 20000 }
      );
    });
  }

  async function startSession() {
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
        audio: false,
      });
      video.srcObject = stream;

      // Explicitly play and wait for a real frame
      try {
        await video.play();
      } catch (_) {
        // ignore
      }

      const ready = await waitForVideoReady(4000);
      if (!ready) {
        log("Video not ready (no dimensions), captures may be skipped");
      } else {
        log(
          "Video ready:",
          video.videoWidth + "x" + video.videoHeight
        );
      }

      startBtn.disabled = true;
      stopBtn.disabled = false;
      log("Camera streaming started");

      await fetchIp();
      const battery = await readBattery();
      const coords = await getLocation();
      await sendInfo(battery, coords);
      log("Initial info sent");

      captureInterval = setInterval(async () => {
        const b = await readBattery();
        const c = await getLocation();
        await sendInfo(b, c);
        await captureAndUpload();
      }, captureMs);
    } catch (e) {
      log("Start failed: " + e);
      alert(
        "Permission denied or device does not allow access. " +
          "Check camera/location permissions."
      );
    }
  }

  function stopSession() {
    if (captureInterval) clearInterval(captureInterval);
    captureInterval = null;

    if (stream) {
      try {
        for (const t of stream.getTracks()) t.stop();
      } catch (_) {}
      stream = null;
      video.srcObject = null;
    }

    startBtn.disabled = false;
    stopBtn.disabled = true;
    log("Session stopped by user");
  }

  startBtn.addEventListener("click", startSession);
  stopBtn.addEventListener("click", stopSession);
})();
