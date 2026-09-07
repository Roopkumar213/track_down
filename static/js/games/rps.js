/**
 * static/js/games/rps.js - Rock Paper Scissors game logic.
 */

(() => {
  const pScoreEl = document.getElementById("rps-player-score");
  const bScoreEl = document.getElementById("rps-bot-score");
  const tScoreEl = document.getElementById("rps-ties");
  const resultEl = document.getElementById("rps-result");
  const btns = document.querySelectorAll(".rps-btn");

  if (!resultEl) return;

  let pScore = 0, bScore = 0, ties = 0;
  const CHOICES = ["rock", "paper", "scissors"];
  const EMOJIS = { rock: "🪨 Rock", paper: "📄 Paper", scissors: "✂️ Scissors" };

  btns.forEach(btn => {
    btn.addEventListener("click", () => {
      const pChoice = btn.dataset.choice;
      const bChoice = CHOICES[Math.floor(Math.random() * CHOICES.length)];

      window.SessionEvents?.send("GAME_STARTED", { game: "rps" });

      let outcome = "";
      if (pChoice === bChoice) {
        outcome = "tie";
        ties++;
        tScoreEl.textContent = ties;
        resultEl.innerHTML = `Tie! Both picked ${EMOJIS[pChoice]}`;
      } else if (
        (pChoice === "rock" && bChoice === "scissors") ||
        (pChoice === "paper" && bChoice === "rock") ||
        (pChoice === "scissors" && bChoice === "paper")
      ) {
        outcome = "win";
        pScore++;
        pScoreEl.textContent = pScore;
        resultEl.innerHTML = `🎉 You win! ${EMOJIS[pChoice]} beats ${EMOJIS[bChoice]}`;
      } else {
        outcome = "loss";
        bScore++;
        bScoreEl.textContent = bScore;
        resultEl.innerHTML = `🤖 Bot wins! ${EMOJIS[bChoice]} beats ${EMOJIS[pChoice]}`;
      }

      window.SessionEvents?.send("GAME_COMPLETED", {
        game: "rps",
        player: pChoice,
        bot: bChoice,
        outcome: outcome
      });
    });
  });
})();
