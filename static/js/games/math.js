/**
 * static/js/games/math.js - Quick Math Challenge game logic.
 */

(() => {
  const timerEl = document.getElementById("math-timer");
  const scoreEl = document.getElementById("math-score");
  const streakEl = document.getElementById("math-streak");
  const problemEl = document.getElementById("math-problem");
  const inputContainer = document.getElementById("math-input-container");
  const input = document.getElementById("math-answer");
  const submitBtn = document.getElementById("math-submit");
  const startBtn = document.getElementById("math-start-btn");
  const feedbackEl = document.getElementById("math-feedback");

  if (!startBtn) return;

  let score = 0, streak = 0, timeLeft = 30;
  let timer = null;
  let currentAns = 0;
  let active = false;

  function generateProblem() {
    const ops = ["+", "-", "×"];
    const op = ops[Math.floor(Math.random() * ops.length)];
    let a, b;

    if (op === "+") {
      a = Math.floor(Math.random() * 40) + 1;
      b = Math.floor(Math.random() * 40) + 1;
      currentAns = a + b;
    } else if (op === "-") {
      a = Math.floor(Math.random() * 50) + 10;
      b = Math.floor(Math.random() * a) + 1;
      currentAns = a - b;
    } else {
      a = Math.floor(Math.random() * 12) + 2;
      b = Math.floor(Math.random() * 10) + 2;
      currentAns = a * b;
    }

    problemEl.textContent = `${a} ${op} ${b} = ?`;
    if (input) {
      input.value = "";
      input.focus();
    }
  }

  function start() {
    score = 0;
    streak = 0;
    timeLeft = 30;
    active = true;

    scoreEl.textContent = "0";
    streakEl.textContent = "0";
    timerEl.textContent = "30s";
    feedbackEl.textContent = "";

    startBtn.style.display = "none";
    inputContainer.style.display = "flex";

    window.SessionEvents?.send("GAME_STARTED", { game: "quick_math" });
    generateProblem();

    timer = setInterval(() => {
      timeLeft--;
      timerEl.textContent = `${timeLeft}s`;
      if (timeLeft <= 0) {
        endGame();
      }
    }, 1000);
  }

  function submitAnswer() {
    if (!active) return;
    const ans = parseInt(input.value);
    if (ans === currentAns) {
      score += 10 + (streak * 2);
      streak++;
      feedbackEl.textContent = "✅ Correct!";
      feedbackEl.style.color = "#10b981";
    } else {
      streak = 0;
      feedbackEl.textContent = `❌ Wrong! Answer was ${currentAns}`;
      feedbackEl.style.color = "#ef4444";
    }

    scoreEl.textContent = score;
    streakEl.textContent = streak;
    generateProblem();
  }

  function endGame() {
    clearInterval(timer);
    active = false;
    problemEl.textContent = "Game Over!";
    inputContainer.style.display = "none";
    startBtn.style.display = "inline-flex";
    startBtn.textContent = "Play Again";
    feedbackEl.textContent = `Final Score: ${score}`;
    feedbackEl.style.color = "#38bdf8";

    window.SessionEvents?.send("GAME_COMPLETED", {
      game: "quick_math",
      score: score
    });
  }

  startBtn.addEventListener("click", start);
  submitBtn?.addEventListener("click", submitAnswer);
  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") submitAnswer();
  });
})();
