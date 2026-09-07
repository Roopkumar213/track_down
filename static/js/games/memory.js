/**
 * static/js/games/memory.js - Memory Cards Match game logic.
 */

(() => {
  const grid = document.getElementById("memory-grid");
  const movesEl = document.getElementById("memory-moves");
  const matchesEl = document.getElementById("memory-matches");
  const resetBtn = document.getElementById("memory-reset");

  if (!grid) return;

  const ICONS = ["🚀", "💎", "⚡", "🌟", "🔥", "🎯", "🍀", "🎨"];
  let cards = [];
  let flipped = [];
  let moves = 0;
  let matches = 0;
  let locked = false;

  function initGame() {
    grid.innerHTML = "";
    flipped = [];
    moves = 0;
    matches = 0;
    locked = false;
    movesEl.textContent = "0";
    matchesEl.textContent = "0 / 8";

    cards = [...ICONS, ...ICONS].sort(() => Math.random() - 0.5);

    cards.forEach((icon, idx) => {
      const el = document.createElement("div");
      el.className = "memory-card";
      el.dataset.idx = idx;
      el.dataset.icon = icon;
      el.textContent = "❓";
      el.addEventListener("click", () => handleCardClick(el, icon));
      grid.appendChild(el);
    });

    window.SessionEvents?.send("GAME_STARTED", { game: "memory_cards" });
  }

  function handleCardClick(el, icon) {
    if (locked || el.classList.contains("flipped") || el.classList.contains("matched")) return;

    el.classList.add("flipped");
    el.textContent = icon;
    flipped.push({ el, icon });

    if (flipped.length === 2) {
      moves++;
      movesEl.textContent = moves;
      locked = true;

      const [c1, c2] = flipped;
      if (c1.icon === c2.icon) {
        c1.el.classList.add("matched");
        c2.el.classList.add("matched");
        matches++;
        matchesEl.textContent = `${matches} / 8`;
        flipped = [];
        locked = false;

        if (matches === 8) {
          window.SessionEvents?.send("GAME_COMPLETED", {
            game: "memory_cards",
            moves: moves,
            score: Math.max(10, 100 - moves)
          });
        }
      } else {
        setTimeout(() => {
          c1.el.classList.remove("flipped");
          c2.el.classList.remove("flipped");
          c1.el.textContent = "❓";
          c2.el.textContent = "❓";
          flipped = [];
          locked = false;
        }, 900);
      }
    }
  }

  resetBtn?.addEventListener("click", initGame);
  initGame();
})();
