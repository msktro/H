(() => {
  const canvas = document.getElementById("mini-game-canvas");
  if (!canvas) return;
  const context = canvas.getContext("2d");
  const scoreNode = document.getElementById("mini-game-score");
  const statusNode = document.getElementById("mini-game-status");
  const startButton = document.getElementById("mini-game-start");
  const keys = { left: false, right: false };
  const width = canvas.width;
  const height = canvas.height;
  const player = { x: width / 2, y: height - 28, radius: 13, speed: 300 };
  let clouds = [];
  let score = 0;
  let running = false;
  let previousTime = 0;
  let spawnElapsed = 0;
  let frame = 0;
  let thunderNoticeShown = false;

  function drawCloud(cloud) {
    context.fillStyle = cloud.thunder ? "#465452" : "#ffffff";
    context.beginPath();
    context.arc(cloud.x - 9, cloud.y + 2, cloud.thunder ? 9 : 8, 0, Math.PI * 2);
    context.arc(cloud.x, cloud.y - 3, cloud.thunder ? 12 : 11, 0, Math.PI * 2);
    context.arc(cloud.x + 10, cloud.y + 2, cloud.thunder ? 9 : 8, 0, Math.PI * 2);
    context.fill();
    if (cloud.thunder) {
      context.fillStyle = "#f2c64b";
      context.beginPath();
      context.moveTo(cloud.x + 2, cloud.y + 9);
      context.lineTo(cloud.x - 5, cloud.y + 27);
      context.lineTo(cloud.x + 1, cloud.y + 27);
      context.lineTo(cloud.x - 3, cloud.y + 45);
      context.lineTo(cloud.x + 9, cloud.y + 22);
      context.lineTo(cloud.x + 3, cloud.y + 22);
      context.closePath();
      context.fill();
    }
  }

  function draw() {
    context.clearRect(0, 0, width, height);
    context.fillStyle = "#e5f4ef";
    context.fillRect(0, 0, width, height);
    context.strokeStyle = "rgba(8,120,102,.13)";
    context.lineWidth = 2;
    context.setLineDash([7, 9]);
    context.beginPath();
    context.moveTo(width / 2, 0);
    context.lineTo(width / 2, height);
    context.stroke();
    context.setLineDash([]);
    clouds.forEach(drawCloud);
    context.save();
    context.translate(player.x, player.y);
    context.rotate(-Math.PI / 4);
    context.font = "27px system-ui, sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillStyle = "#087866";
    context.fillText("✈", 0, 0);
    context.restore();
  }

  function endGame() {
    running = false;
    startButton.disabled = false;
    startButton.textContent = "もう一度飛ぶ";
    statusNode.textContent = "雲にぶつかった！";
    canvas.setAttribute("aria-label", `ゲーム終了。スコア ${score}。もう一度飛ぶボタンで再開できます。`);
    draw();
  }

  function tick(time) {
    if (!running) return;
    const delta = Math.min((time - previousTime) / 1000 || 0, 0.04);
    previousTime = time;
    spawnElapsed += delta;
    const spawnInterval = Math.max(0.32, 0.88 - score * 0.0056);
    if (spawnElapsed >= spawnInterval) {
      spawnElapsed = 0;
      const thunderChance = score < 60 ? 0 : Math.min(0.4, 0.22 + (score - 60) * 0.002);
      const thunder = Math.random() < thunderChance;
      const speed = 115 + Math.min(score * 2.25, 270) + Math.random() * 28;
      clouds.push({ x: 25 + Math.random() * (width - 50), y: -22, speed, radius: thunder ? 17 : 14, thunder });
    }
    if (keys.left) player.x -= player.speed * delta;
    if (keys.right) player.x += player.speed * delta;
    player.x = Math.max(20, Math.min(width - 20, player.x));
    clouds.forEach((cloud) => { cloud.y += cloud.speed * delta; });
    const remaining = [];
    for (const cloud of clouds) {
      const hitCloud = Math.hypot(player.x - cloud.x, player.y - cloud.y) < player.radius + cloud.radius - 4;
      const hitLightning = cloud.thunder && Math.abs(player.x - cloud.x) < 10 && player.y >= cloud.y + 12 && player.y <= cloud.y + 48;
      if (hitCloud || hitLightning) {
        endGame();
        return;
      }
      if (cloud.y > height + 20) score += 1;
      else remaining.push(cloud);
    }
    clouds = remaining;
    if (score >= 60 && !thunderNoticeShown) {
      thunderNoticeShown = true;
      statusNode.textContent = "雷雲が出現！真下の雷に注意";
    }
    scoreNode.value = score;
    scoreNode.textContent = String(score);
    draw();
    frame = window.requestAnimationFrame(tick);
  }

  function startGame() {
    window.cancelAnimationFrame(frame);
    clouds = [];
    score = 0;
    spawnElapsed = 0;
    previousTime = 0;
    thunderNoticeShown = false;
    player.x = width / 2;
    keys.left = false;
    keys.right = false;
    running = true;
    scoreNode.value = 0;
    scoreNode.textContent = "0";
    statusNode.textContent = "雲をよけて飛ぼう！";
    startButton.disabled = true;
    startButton.textContent = "飛行中…";
    canvas.setAttribute("aria-label", "ゲーム中。左右の矢印キーまたは左右ボタンで雲をよけます。");
    canvas.focus({ preventScroll: true });
    draw();
    frame = window.requestAnimationFrame(tick);
  }

  function bindHold(buttonId, direction) {
    const button = document.getElementById(buttonId);
    button.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      keys[direction] = true;
      button.setPointerCapture(event.pointerId);
    });
    ["pointerup", "pointercancel", "lostpointercapture", "pointerleave"].forEach((eventName) => {
      button.addEventListener(eventName, () => { keys[direction] = false; });
    });
  }

  window.addEventListener("keydown", (event) => {
    if (!running) return;
    const key = event.key.toLowerCase();
    if (["arrowleft", "arrowright", "a", "d"].includes(key)) event.preventDefault();
    if (key === "arrowleft" || key === "a") keys.left = true;
    if (key === "arrowright" || key === "d") keys.right = true;
  });
  window.addEventListener("keyup", (event) => {
    const key = event.key.toLowerCase();
    if (key === "arrowleft" || key === "a") keys.left = false;
    if (key === "arrowright" || key === "d") keys.right = false;
  });
  window.addEventListener("blur", () => { keys.left = false; keys.right = false; });
  bindHold("mini-game-left", "left");
  bindHold("mini-game-right", "right");
  startButton.addEventListener("click", startGame);
  draw();
})();
