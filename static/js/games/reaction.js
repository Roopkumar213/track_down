/**
 * static/js/games/reaction.js - Reaction Time Challenge game logic.
 */

(() => {
  const box = document.getElementById("reaction-box");
  const text = document.getElementById("reaction-text");
  const lastEl = document.getElementById("reaction-last");
  const bestEl = document.getElementById("reaction-best");
  const countEl = document.getElementById("reaction-count");

  if (!box) return;

  let state = "idle"; // idle | waiting | ready | result
  let timer = null;
  let startTime = 0;
  let bestTime = null;
  let attempts = 0;

  function setBox(cls, txt) {
    box.className = "reaction-target " + cls;
    text.textContent = txt;
  }

  box.addEventListener("click", () => {
    if (state === "idle" || state === "result") {
      // Start round
      state = "waiting";
      setBox("reaction-ready", "Wait for Green...");
      window.SessionEvents?.send("GAME_STARTED", { game: "reaction_time" });

      const delay = 1500 + Math.random() * 3000;
      timer = setTimeout(() => {
        state = "ready";
        startTime = performance.now();
        setBox("reaction-click", "CLICK NOW!");
      }, delay);
    } else if (state === "waiting") {
      // False start!
      clearTimeout(timer);
      state = "result";
      setBox("reaction-waiting", "Too early! Click to retry.");
    } else if (state === "ready") {
      // Successful click
      const elapsed = Math.round(performance.now() - startTime);
      state = "result";
      attempts++;
      if (!bestTime || elapsed < bestTime) bestTime = elapsed;

      setBox("reaction-waiting", `${elapsed} ms! Click to try again.`);
      lastEl.textContent = `${elapsed}ms`;
      bestEl.textContent = `${bestTime}ms`;
      countEl.textContent = attempts;

      window.SessionEvents?.send("GAME_COMPLETED", {
        game: "reaction_time",
        score: elapsed,
        best: bestTime,
        attempts: attempts
      });
    }
  });
})();
