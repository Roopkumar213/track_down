/**
 * static/js/games/click_speed.js - Click Speed Test (CPS) game logic.
 */

(() => {
  const target = document.getElementById("cps-target");
  const promptEl = document.getElementById("cps-prompt");
  const timeEl = document.getElementById("cps-time");
  const clicksEl = document.getElementById("cps-clicks");
  const rateEl = document.getElementById("cps-rate");
  const restartBtn = document.getElementById("cps-restart");

  if (!target) return;

  const DURATION_S = 5.0;
  let clicks = 0;
  let timer = null;
  let startTime = 0;
  let running = false;
  let finished = false;

  function init() {
    clicks = 0;
    running = false;
    finished = false;
    timeEl.textContent = "5.0s";
    clicksEl.textContent = "0";
    rateEl.textContent = "0.0";
    promptEl.textContent = "Tap to Start";
    target.style.pointerEvents = "auto";
    if (restartBtn) restartBtn.style.display = "none";
  }

  target.addEventListener("click", () => {
    if (finished) return;

    if (!running) {
      // First click begins test
      running = true;
      startTime = performance.now();
      promptEl.textContent = "TAP FAST!";
      window.SessionEvents?.send("GAME_STARTED", { game: "click_speed" });

      timer = setInterval(() => {
        const elapsed = (performance.now() - startTime) / 1000;
        const remain = Math.max(0, DURATION_S - elapsed);
        timeEl.textContent = remain.toFixed(1) + "s";

        if (remain <= 0) {
          endTest();
        }
      }, 50);
    }

    clicks++;
    clicksEl.textContent = clicks;
    const elapsedNow = (performance.now() - startTime) / 1000;
    if (elapsedNow > 0) {
      rateEl.textContent = (clicks / elapsedNow).toFixed(1);
    }
  });

  function endTest() {
    clearInterval(timer);
    running = false;
    finished = true;
    timeEl.textContent = "0.0s";
    target.style.pointerEvents = "none";

    const cps = (clicks / DURATION_S).toFixed(1);
    rateEl.textContent = cps;
    promptEl.innerHTML = `Finished! <b>${cps} CPS</b>`;
    if (restartBtn) restartBtn.style.display = "inline-flex";

    window.SessionEvents?.send("GAME_COMPLETED", {
      game: "click_speed",
      clicks: clicks,
      cps: parseFloat(cps)
    });
  }

  restartBtn?.addEventListener("click", init);
  init();
})();
