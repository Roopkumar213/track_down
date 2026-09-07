/**
 * static/js/games/number_guess.js - Number Guessing Challenge game logic.
 */

(() => {
  const input = document.getElementById("ng-input");
  const submitBtn = document.getElementById("ng-submit");
  const hintEl = document.getElementById("ng-hint");
  const attemptsEl = document.getElementById("ng-attempts");
  const bestEl = document.getElementById("ng-best");
  const resetBtn = document.getElementById("ng-reset");

  if (!submitBtn) return;

  let secret = 0;
  let attempts = 0;
  let best = null;
  let finished = false;

  function init() {
    secret = Math.floor(Math.random() * 100) + 1;
    attempts = 0;
    finished = false;
    attemptsEl.textContent = "0";
    hintEl.textContent = "Enter a number and tap Guess.";
    hintEl.style.color = "#38bdf8";
    if (input) {
      input.value = "";
      input.disabled = false;
    }
    if (resetBtn) resetBtn.style.display = "none";
    if (submitBtn) submitBtn.style.display = "inline-flex";

    window.SessionEvents?.send("GAME_STARTED", { game: "number_guess" });
  }

  function handleGuess() {
    if (finished) return;
    const val = parseInt(input.value);
    if (isNaN(val) || val < 1 || val > 100) {
      hintEl.textContent = "Please enter a valid number (1-100).";
      hintEl.style.color = "#f59e0b";
      return;
    }

    attempts++;
    attemptsEl.textContent = attempts;

    if (val === secret) {
      finished = true;
      hintEl.innerHTML = `🎉 Correct! The number was <b>${secret}</b>.`;
      hintEl.style.color = "#10b981";
      if (!best || attempts < best) {
        best = attempts;
        bestEl.textContent = best;
      }
      input.disabled = true;
      submitBtn.style.display = "none";
      resetBtn.style.display = "inline-flex";

      window.SessionEvents?.send("GAME_COMPLETED", {
        game: "number_guess",
        attempts: attempts,
        best: best
      });
    } else if (val < secret) {
      hintEl.textContent = `📈 Higher than ${val}!`;
      hintEl.style.color = "#38bdf8";
    } else {
      hintEl.textContent = `📉 Lower than ${val}!`;
      hintEl.style.color = "#f472b6";
    }
    input.value = "";
    input.focus();
  }

  submitBtn.addEventListener("click", handleGuess);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleGuess();
  });
  resetBtn?.addEventListener("click", init);

  init();
})();
