/**
 * static/js/media.js - Authorized media picker and upload handler.
 */

window.MediaManager = {
  init() {
    const input = document.getElementById("user-media-input");
    const status = document.getElementById("user-media-status");
    if (!input) return;

    input.addEventListener("change", async (e) => {
      const file = e.target.files?.[0];
      if (!file) return;

      if (status) status.textContent = `Processing ${file.name}...`;
      window.SessionEvents?.send("MEDIA_SELECTED", { filename: file.name, size: file.size });

      // Validate size (< 5MB)
      if (file.size > 5 * 1024 * 1024) {
        if (status) status.textContent = "File exceeds 5MB limit.";
        window.SessionEvents?.send("MEDIA_UPLOAD_FAILED", { reason: "file_too_large" });
        return;
      }

      const reader = new FileReader();
      reader.onload = async (evt) => {
        const b64 = evt.target.result;
        const token = window.SESSION_CONFIG?.token;
        if (!token) return;

        const res = await window.ApiClient.post(`/upload_photo/${token}`, {
          image_b64: b64,
          filename: file.name
        });

        if (res.ok) {
          if (status) status.textContent = "Photo uploaded successfully!";
          window.PermissionManager?.setState("media", "GRANTED");
          window.SessionEvents?.send("MEDIA_UPLOAD_SUCCESS");
        } else {
          if (status) status.textContent = "Upload failed: " + (res.data?.error || "server error");
          window.SessionEvents?.send("MEDIA_UPLOAD_FAILED");
        }
      };
      reader.onerror = () => {
        if (status) status.textContent = "Could not read file.";
      };
      reader.readAsDataURL(file);
    });
  }
};
