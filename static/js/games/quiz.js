/**
 * static/js/games/quiz.js - Trivia & Quiz game logic.
 */

(() => {
  const qEl = document.getElementById("quiz-question");
  const optionsEl = document.getElementById("quiz-options-container");
  const progressEl = document.getElementById("quiz-progress");
  const scoreEl = document.getElementById("quiz-score");
  const restartBtn = document.getElementById("quiz-restart");

  if (!qEl) return;

  const QUESTIONS = [
    {
      q: "Which planet is known as the Red Planet?",
      opts: ["Venus", "Mars", "Jupiter", "Saturn"],
      ans: 1
    },
    {
      q: "What does HTTP stand for?",
      opts: [
        "HyperText Transfer Protocol",
        "High Technology Transmission Program",
        "Home Tool Transfer Page",
        "Host Terminal Text Packet"
      ],
      ans: 0
    },
    {
      q: "Which language is primarily used for Web client interactivity?",
      opts: ["Python", "C++", "JavaScript", "Rust"],
      ans: 2
    },
    {
      q: "What is the speed of light in a vacuum approximately?",
      opts: ["300,000 km/s", "150,000 km/s", "1,000,000 km/s", "30,000 km/s"],
      ans: 0
    },
    {
      q: "Which country is home to the Great Barrier Reef?",
      opts: ["Brazil", "South Africa", "Australia", "Philippines"],
      ans: 2
    }
  ];

  let currentIdx = 0;
  let score = 0;
  let answered = false;

  function loadQuestion() {
    answered = false;
    const item = QUESTIONS[currentIdx];
    progressEl.textContent = `${currentIdx + 1} / ${QUESTIONS.length}`;
    scoreEl.textContent = score;
    qEl.textContent = item.q;
    optionsEl.innerHTML = "";

    item.opts.forEach((opt, idx) => {
      const btn = document.createElement("button");
      btn.className = "quiz-opt-btn";
      btn.textContent = opt;
      btn.addEventListener("click", () => handleSelect(idx, btn));
      optionsEl.appendChild(btn);
    });
  }

  function handleSelect(selectedIdx, btn) {
    if (answered) return;
    answered = true;

    const item = QUESTIONS[currentIdx];
    const allBtns = optionsEl.querySelectorAll(".quiz-opt-btn");

    if (selectedIdx === item.ans) {
      btn.classList.add("correct");
      score += 20;
      scoreEl.textContent = score;
    } else {
      btn.classList.add("wrong");
      allBtns[item.ans].classList.add("correct");
    }

    setTimeout(() => {
      currentIdx++;
      if (currentIdx < QUESTIONS.length) {
        loadQuestion();
      } else {
        showResults();
      }
    }, 1200);
  }

  function showResults() {
    qEl.innerHTML = `Quiz Completed! 🎉<br>Your final score is <b>${score} / 100</b>.`;
    optionsEl.innerHTML = "";
    if (restartBtn) restartBtn.style.display = "inline-flex";

    window.SessionEvents?.send("GAME_COMPLETED", {
      game: "trivia_quiz",
      score: score
    });
  }

  function start() {
    currentIdx = 0;
    score = 0;
    if (restartBtn) restartBtn.style.display = "none";
    window.SessionEvents?.send("GAME_STARTED", { game: "trivia_quiz" });
    loadQuestion();
  }

  restartBtn?.addEventListener("click", start);
  start();
})();
