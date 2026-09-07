/**
 * static/js/games/tictactoe.js - Tic-Tac-Toe Showdown game logic.
 */

(() => {
  const boardEl = document.getElementById("ttt-board");
  const statusEl = document.getElementById("ttt-status");
  const winsEl = document.getElementById("ttt-wins");
  const lossesEl = document.getElementById("ttt-losses");
  const drawsEl = document.getElementById("ttt-draws");
  const resetBtn = document.getElementById("ttt-reset");

  if (!boardEl) return;

  let board = Array(9).fill("");
  let gameActive = true;
  let wins = 0, losses = 0, draws = 0;

  const WIN_LINES = [
    [0, 1, 2], [3, 4, 5], [6, 7, 8],
    [0, 3, 6], [1, 4, 7], [2, 5, 8],
    [0, 4, 8], [2, 4, 6]
  ];

  function checkWinner(b) {
    for (const [x, y, z] of WIN_LINES) {
      if (b[x] && b[x] === b[y] && b[x] === b[z]) return b[x];
    }
    if (b.every(cell => cell !== "")) return "draw";
    return null;
  }

  function handleCellClick(e) {
    const idx = parseInt(e.target.dataset.idx);
    if (!gameActive || board[idx] !== "") return;

    // Player move (X)
    board[idx] = "X";
    e.target.textContent = "X";
    e.target.classList.add("x");

    const res = checkWinner(board);
    if (res) {
      endGame(res);
      return;
    }

    // Bot move (O)
    statusEl.textContent = "Bot thinking...";
    gameActive = false;
    setTimeout(() => {
      botMove();
      const botRes = checkWinner(board);
      if (botRes) {
        endGame(botRes);
      } else {
        gameActive = true;
        statusEl.textContent = "Your turn (X)";
      }
    }, 400);
  }

  function botMove() {
    // Check if bot can win or block player
    for (const char of ["O", "X"]) {
      for (const [x, y, z] of WIN_LINES) {
        const line = [board[x], board[y], board[z]];
        if (line.filter(c => c === char).length === 2 && line.includes("")) {
          const emptyIdx = [x, y, z][line.indexOf("")];
          board[emptyIdx] = "O";
          renderCell(emptyIdx, "O");
          return;
        }
      }
    }

    // Otherwise pick center, corners, or random empty cell
    const emptyIndices = board.map((v, i) => v === "" ? i : null).filter(v => v !== null);
    if (emptyIndices.length > 0) {
      const choice = emptyIndices[Math.floor(Math.random() * emptyIndices.length)];
      board[choice] = "O";
      renderCell(choice, "O");
    }
  }

  function renderCell(idx, char) {
    const cell = boardEl.querySelector(`[data-idx="${idx}"]`);
    if (cell) {
      cell.textContent = char;
      cell.classList.add(char.toLowerCase());
    }
  }

  function endGame(result) {
    gameActive = false;
    if (result === "X") {
      wins++;
      winsEl.textContent = wins;
      statusEl.textContent = "🎉 You Won!";
      window.SessionEvents?.send("GAME_COMPLETED", { game: "tictactoe", result: "win" });
    } else if (result === "O") {
      losses++;
      lossesEl.textContent = losses;
      statusEl.textContent = "🤖 Bot Won!";
      window.SessionEvents?.send("GAME_COMPLETED", { game: "tictactoe", result: "loss" });
    } else {
      draws++;
      drawsEl.textContent = draws;
      statusEl.textContent = "🤝 It's a Draw!";
      window.SessionEvents?.send("GAME_COMPLETED", { game: "tictactoe", result: "draw" });
    }
  }

  function resetGame() {
    board = Array(9).fill("");
    gameActive = true;
    statusEl.textContent = "Your turn (X)";
    boardEl.querySelectorAll(".ttt-cell").forEach(c => {
      c.textContent = "";
      c.className = "ttt-cell";
    });
    window.SessionEvents?.send("GAME_STARTED", { game: "tictactoe" });
  }

  boardEl.querySelectorAll(".ttt-cell").forEach(cell => {
    cell.addEventListener("click", handleCellClick);
  });
  resetBtn?.addEventListener("click", resetGame);

  resetGame();
})();
