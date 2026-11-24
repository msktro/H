(() => {
  const canvas = document.getElementById("mini-game-canvas");
  if (!canvas) return;
  const context = canvas.getContext("2d");
  const scoreNode = document.getElementById("mini-game-score");
  const livesNode = document.getElementById("mini-game-lives");
  const statusNode = document.getElementById("mini-game-status");
  const titleNode = document.getElementById("mini-game-title");
  const helpNode = document.querySelector(".mini-game-help");
  const startButton = document.getElementById("mini-game-start");
  const fullscreenButton = document.getElementById("mini-game-fullscreen");
  const game = document.querySelector(".mini-game");
  const faceMode = new URLSearchParams(window.location.search).get("mode") === "sugano";
  const faceSpriteSheet = new Image();
  if (faceMode) faceSpriteSheet.src = "/static/404-face-hazards.png?v=20261124-2";
  if (faceMode) {
    canvas.height = 420;
    canvas.classList.add("sugano-shooter");
  }
  const keys = { left: false, right: false };
  const width = canvas.width;
  const height = canvas.height;
  const player = { x: width / 2, y: height - 28, radius: 13, speed: 300 };
  let clouds = [];
  let hearts = [];
  let playerShots = [];
  let enemyShots = [];
  const stars = faceMode ? Array.from({ length: 54 }, () => ({
    x: Math.random() * canvas.width,
    y: Math.random() * canvas.height,
    speed: 18 + Math.random() * 45,
    size: 1 + Math.random() * 2
  })) : [];
  let score = 0;
  let lives = 2;
  let hitCooldown = 0;
  let edgeHoldElapsed = 0;
  let edgeStrikeTimer = 0;
  let edgeStrikeX = 0;
  let heartSpawnElapsed = 0;
  let heartSpawnInterval = 6 + Math.random() * 5;
  let running = false;
  let previousTime = 0;
  let spawnElapsed = 0;
  let shotElapsed = 0;
  let enemyShotElapsed = 0;
  let stillElapsed = 0;
  let stillAnchorX = player.x;
  let frame = 0;
  let thunderNoticeShown = false;
  let showFaceJumpscare = false;
  let jumpscareFaceIndex = 0;

  if (faceMode) {
    if (titleNode) titleNode.textContent = "suganoシューティング";
    if (helpNode) helpNode.textContent = "自動ショットで顔の敵を倒し、敵の弾や落雷をよけてください。同じ場所に3秒いると顔が高速で落ちてきます。左右の端に3秒いると落雷し、60〜100点の雷雲に当たると残機が2つ減ります。";
  }

  function drawCloud(cloud) {
    if (faceMode && faceSpriteSheet.complete && faceSpriteSheet.naturalWidth > 0) {
      const sourceWidth = faceSpriteSheet.naturalWidth / 5;
      const sourceTop = faceSpriteSheet.naturalHeight * 0.18;
      const sourceHeight = faceSpriteSheet.naturalHeight * 0.65;
      const spriteSize = cloud.radius * 2 + 4;
      context.drawImage(
        faceSpriteSheet,
        cloud.faceIndex * sourceWidth, sourceTop, sourceWidth, sourceHeight,
        cloud.x - spriteSize / 2, cloud.y - spriteSize / 2, spriteSize, spriteSize
      );
    } else {
      context.fillStyle = cloud.thunder ? "#465452" : "#ffffff";
      context.beginPath();
      context.arc(cloud.x - 9, cloud.y + 2, cloud.thunder ? 9 : 8, 0, Math.PI * 2);
      context.arc(cloud.x, cloud.y - 3, cloud.thunder ? 12 : 11, 0, Math.PI * 2);
      context.arc(cloud.x + 10, cloud.y + 2, cloud.thunder ? 9 : 8, 0, Math.PI * 2);
      context.fill();
    }
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

  function drawHeart(heart) {
    context.fillStyle = "#ec6b83";
    context.beginPath();
    context.moveTo(heart.x, heart.y + 8);
    context.bezierCurveTo(heart.x - 19, heart.y - 3, heart.x - 11, heart.y - 17, heart.x, heart.y - 8);
    context.bezierCurveTo(heart.x + 11, heart.y - 17, heart.x + 19, heart.y - 3, heart.x, heart.y + 8);
    context.fill();
    context.fillStyle = "rgba(255,255,255,.75)";
    context.beginPath();
    context.arc(heart.x - 5, heart.y - 5, 2, 0, Math.PI * 2);
    context.fill();
  }

  function drawShots() {
    if (!faceMode) return;
    context.save();
    context.fillStyle = "#74f5ff";
    context.shadowColor = "#4de8ff";
    context.shadowBlur = 11;
    for (const shot of playerShots) {
      context.fillRect(shot.x - 2, shot.y - 10, 4, 18);
    }
    context.fillStyle = "#ff6ca7";
    context.shadowColor = "#ff4c92";
    for (const shot of enemyShots) {
      context.beginPath();
      context.arc(shot.x, shot.y, shot.radius, 0, Math.PI * 2);
      context.fill();
    }
    context.restore();
  }

  function drawEdgeStrike() {
    if (edgeStrikeTimer <= 0) return;
    context.save();
    context.globalAlpha = Math.min(1, edgeStrikeTimer / 0.32 + 0.25);
    context.strokeStyle = "#f2c64b";
    context.lineWidth = 5;
    context.lineJoin = "round";
    context.shadowColor = "#fff1a8";
    context.shadowBlur = 14;
    context.beginPath();
    context.moveTo(edgeStrikeX, 0);
    context.lineTo(edgeStrikeX - 6, player.y * 0.25);
    context.lineTo(edgeStrikeX + 5, player.y * 0.43);
    context.lineTo(edgeStrikeX - 4, player.y * 0.66);
    context.lineTo(edgeStrikeX + 2, player.y + 8);
    context.stroke();
    context.restore();
  }

  function updateLives() {
    if (!livesNode) return;
    livesNode.value = lives;
    livesNode.textContent = String(lives);
  }

  function draw() {
    context.clearRect(0, 0, width, height);
    context.fillStyle = faceMode ? "#08152d" : "#e5f4ef";
    context.fillRect(0, 0, width, height);
    if (faceMode) {
      context.fillStyle = "rgba(185,220,255,.72)";
      for (const star of stars) {
        context.globalAlpha = 0.45 + (star.size / 2) * 0.45;
        context.fillRect(star.x, star.y, star.size, star.size);
      }
      context.globalAlpha = 1;
    } else {
      context.strokeStyle = "rgba(8,120,102,.13)";
      context.lineWidth = 2;
      context.setLineDash([7, 9]);
      context.beginPath();
      context.moveTo(width / 2, 0);
      context.lineTo(width / 2, height);
      context.stroke();
      context.setLineDash([]);
    }
    clouds.forEach(drawCloud);
    hearts.forEach(drawHeart);
    drawShots();
    drawEdgeStrike();
    context.save();
    if (hitCooldown > 0 && Math.floor(hitCooldown * 10) % 2) context.globalAlpha = 0.45;
    context.translate(player.x, player.y);
    context.rotate(-Math.PI / 4);
    context.font = "27px system-ui, sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillStyle = faceMode ? "#5cebd7" : "#087866";
    context.fillText("✈", 0, 0);
    context.restore();
    if (showFaceJumpscare && faceMode) {
      context.save();
      context.fillStyle = "rgba(8, 5, 13, .92)";
      context.fillRect(0, 0, width, height);
      if (faceSpriteSheet.complete && faceSpriteSheet.naturalWidth > 0) {
        const sourceWidth = faceSpriteSheet.naturalWidth / 5;
        const sourceTop = faceSpriteSheet.naturalHeight * 0.18;
        const sourceHeight = faceSpriteSheet.naturalHeight * 0.65;
        const scale = Math.max(width / sourceWidth, height / sourceHeight) * 1.02;
        const faceWidth = sourceWidth * scale;
        const faceHeight = sourceHeight * scale;
        context.drawImage(faceSpriteSheet,
          jumpscareFaceIndex * sourceWidth, sourceTop, sourceWidth, sourceHeight,
          (width - faceWidth) / 2, (height - faceHeight) / 2, faceWidth, faceHeight);
      }
      context.fillStyle = "rgba(35, 0, 12, .28)";
      context.fillRect(0, 0, width, height);
      context.textAlign = "center";
      context.textBaseline = "middle";
      context.font = "bold 30px system-ui, sans-serif";
      context.lineWidth = 5;
      context.strokeStyle = "rgba(20, 0, 0, .85)";
      context.strokeText("すがのに殺された", width / 2, height - 34);
      context.fillStyle = "#fff";
      context.fillText("すがのに殺された", width / 2, height - 34);
      context.restore();
    }
  }

  function endGame() {
    running = false;
    showFaceJumpscare = faceMode;
    if (faceMode) {
      jumpscareFaceIndex = clouds.find((cloud) => cloud.dive)?.faceIndex ?? Math.floor(Math.random() * 5);
      canvas.classList.remove("sugano-jumpscare");
      void canvas.offsetWidth;
      canvas.classList.add("sugano-jumpscare");
    }
    startButton.disabled = false;
    startButton.textContent = "もう一度飛ぶ";
    statusNode.textContent = faceMode ? "ゲームオーバー！顔の敵や敵弾に注意。" : "雲にぶつかった！";
    canvas.setAttribute("aria-label", `ゲーム終了。スコア ${score}。もう一度飛ぶボタンで再開できます。`);
    draw();
  }

  function tick(time) {
    if (!running) return;
    const delta = Math.min((time - previousTime) / 1000 || 0, 0.04);
    previousTime = time;
    hitCooldown = Math.max(0, hitCooldown - delta);
    edgeStrikeTimer = Math.max(0, edgeStrikeTimer - delta);
    if (faceMode) {
      for (const star of stars) {
        star.y += star.speed * delta;
        if (star.y > height) {
          star.y = -2;
          star.x = Math.random() * width;
        }
      }
      shotElapsed += delta;
      if (shotElapsed >= 0.18) {
        shotElapsed = 0;
        playerShots.push({ x: player.x, y: player.y - 17, speed: 520, radius: 3 });
      }
    }
    spawnElapsed += delta;
    heartSpawnElapsed += delta;
    if (heartSpawnElapsed >= heartSpawnInterval) {
      heartSpawnElapsed = 0;
      heartSpawnInterval = 8 + Math.random() * 8;
      if (!hearts.length) hearts.push({ x: 24 + Math.random() * (width - 48), y: -14, speed: 105 + Math.min(score * 0.35, 55), radius: 10 });
    }
    const spawnInterval = faceMode ? Math.max(1.1, 2.3 - score * 0.008) : Math.max(0.32, 0.88 - score * 0.0056);
    if (spawnElapsed >= spawnInterval) {
      spawnElapsed = 0;
      const thunderChance = score >= 60 && score <= 100 ? Math.min(0.4, 0.22 + (score - 60) * 0.002) : 0;
      const thunder = Math.random() < thunderChance;
      const speed = faceMode ? 82 + Math.min(score * 1.5, 150) + Math.random() * 20 : 115 + Math.min(score * 2.25, 270) + Math.random() * 28;
      const lateralRange = score >= 80 ? 8 + Math.min((score - 80) * 0.05, 10) : 0;
      if (faceMode) {
        const formationSize = Math.min(5, 3 + Math.floor(score / 20));
        const spacing = 62;
        const formationWidth = (formationSize - 1) * spacing;
        const startX = 54 + Math.random() * (width - formationWidth - 108);
        for (let index = 0; index < formationSize; index += 1) {
          const enemyX = startX + index * spacing;
          clouds.push({ x: enemyX, startX: enemyX, y: -24 - (index % 2) * 16, speed, radius: 20, thunder: Math.random() < thunderChance, faceIndex: Math.floor(Math.random() * 5), lateralRange, phase: Math.random() * Math.PI * 2, age: 0 });
        }
      } else {
        const spawnMargin = lateralRange ? 42 : 25;
        const startX = spawnMargin + Math.random() * (width - spawnMargin * 2);
        clouds.push({ x: startX, startX, y: -22, speed, radius: thunder ? 17 : 14, thunder, faceIndex: 0, lateralRange, phase: Math.random() * Math.PI * 2, age: 0 });
      }
    }
    if (keys.left) player.x -= player.speed * delta;
    if (keys.right) player.x += player.speed * delta;
    player.x = Math.max(20, Math.min(width - 20, player.x));
    if (faceMode) {
      if (Math.abs(player.x - stillAnchorX) > 12) {
        stillAnchorX = player.x;
        stillElapsed = 0;
      } else {
        stillElapsed += delta;
      }
      if (stillElapsed >= 3) {
        // Staying in one place for too long draws a fast face dive to that position.
        clouds.push({
          x: player.x, startX: player.x, y: -30, speed: 680 + Math.min(score * 1.2, 140),
          radius: 22, thunder: false, faceIndex: Math.floor(Math.random() * 5),
          lateralRange: 0, phase: 0, age: 0, dive: true
        });
        stillElapsed = 0;
        stillAnchorX = player.x;
        statusNode.textContent = "同じ場所に3秒いると顔が高速で落ちてくる！移動して避けてください。";
      }
    }
    const atScreenEdge = player.x <= 34 || player.x >= width - 34;
    if (atScreenEdge) {
      edgeHoldElapsed += delta;
      if (edgeHoldElapsed >= 2.5 && edgeHoldElapsed - delta < 2.5) {
        statusNode.textContent = "左右の端に3秒いると落雷！端から離れてください。";
      }
      if (edgeHoldElapsed >= 3 && hitCooldown <= 0) {
        edgeHoldElapsed = 0;
        edgeStrikeTimer = 0.32;
        edgeStrikeX = player.x;
        lives = Math.max(0, lives - 1);
        updateLives();
        hitCooldown = 1.1;
        statusNode.textContent = "落雷！残機を1つ使いました。";
        if (lives <= 0) {
          endGame();
          return;
        }
      }
    } else {
      edgeHoldElapsed = 0;
    }
    clouds.forEach((cloud) => {
      cloud.y += cloud.speed * delta;
      if (!cloud.lateralRange && score >= 80) {
        cloud.startX = cloud.x;
        cloud.lateralRange = 8 + Math.min((score - 80) * 0.05, 10);
        cloud.phase = Math.random() * Math.PI * 2;
      }
      if (cloud.lateralRange) {
        cloud.age += delta;
        const swayRate = score >= 100 ? 2.1 + Math.sin(cloud.age * 0.9) * 0.55 : 2.1;
        cloud.phase += swayRate * delta;
        cloud.x = cloud.startX + Math.sin(cloud.phase) * cloud.lateralRange;
      }
    });
    if (faceMode) {
      enemyShotElapsed += delta;
      if (enemyShotElapsed >= Math.max(0.55, 1.35 - score * 0.004)) {
        enemyShotElapsed = 0;
        const shooters = clouds.filter((cloud) => cloud.y > 24 && cloud.y < player.y - 80);
        if (shooters.length) {
          const shooter = shooters[Math.floor(Math.random() * shooters.length)];
          const speed = 280 + Math.min(score * 1.2, 180);
          if (score > 100) {
            const aimVelocity = Math.max(-150, Math.min(150, (player.x - shooter.x) * 0.45));
            [-11, 11].forEach((offset) => enemyShots.push({
              x: shooter.x + offset, y: shooter.y + shooter.radius,
              vx: aimVelocity, speed, radius: 5
            }));
          } else {
            enemyShots.push({ x: shooter.x, y: shooter.y + shooter.radius, vx: 0, speed, radius: 5 });
          }
        }
      }
      const remainingPlayerShots = [];
      for (const shot of playerShots) {
        shot.y -= shot.speed * delta;
        const targetIndex = clouds.findIndex((cloud) => !cloud.dive && Math.hypot(shot.x - cloud.x, shot.y - cloud.y) < cloud.radius + shot.radius);
        if (targetIndex >= 0) {
          clouds.splice(targetIndex, 1);
          score += 1;
        } else if (shot.y > -20) remainingPlayerShots.push(shot);
      }
      playerShots = remainingPlayerShots;

      const remainingEnemyShots = [];
      for (const shot of enemyShots) {
        shot.x += (shot.vx || 0) * delta;
        shot.y += shot.speed * delta;
        if (Math.hypot(player.x - shot.x, player.y - shot.y) < player.radius + shot.radius) {
          if (hitCooldown <= 0) {
            lives = Math.max(0, lives - 1);
            updateLives();
            hitCooldown = 1.1;
            statusNode.textContent = "敵の弾に当たった！残機を1つ使いました。";
            if (lives <= 0) {
              endGame();
              return;
            }
          }
        } else if (shot.y < height + 12) remainingEnemyShots.push(shot);
      }
      enemyShots = remainingEnemyShots;
    }
    const fallingHearts = [];
    for (const heart of hearts) {
      heart.y += heart.speed * delta;
      if (Math.hypot(player.x - heart.x, player.y - heart.y) < player.radius + heart.radius) {
        if (lives < 5) {
          lives += 1;
          updateLives();
          statusNode.textContent = "ハートをゲット！残機が1増えました。";
        } else {
          statusNode.textContent = "残機は最大です。";
        }
      } else if (heart.y < height + 16) fallingHearts.push(heart);
    }
    hearts = fallingHearts;
    const remaining = [];
    for (const cloud of clouds) {
      const hitCloud = Math.hypot(player.x - cloud.x, player.y - cloud.y) < player.radius + cloud.radius - 4;
      const hitLightning = cloud.thunder && Math.abs(player.x - cloud.x) < 10 && player.y >= cloud.y + 12 && player.y <= cloud.y + 48;
      if (hitCloud || hitLightning) {
        if (hitCooldown <= 0) {
          const damage = cloud.thunder ? 2 : 1;
          lives = Math.max(0, lives - damage);
          updateLives();
          if (lives <= 0) {
            endGame();
            return;
          }
          hitCooldown = 1.1;
          statusNode.textContent = cloud.thunder ? "雷雲に直撃！残機を2つ失いました。" : faceMode ? "顔の敵にぶつかった！残機を1つ使いました。" : "ぶつかった！残機を1つ使いました。";
        }
        continue;
      }
      if (cloud.y > height + 20) {
        if (!faceMode) score += 1;
      }
      else remaining.push(cloud);
    }
    clouds = remaining;
    if (score >= 60 && !thunderNoticeShown) {
      thunderNoticeShown = true;
      statusNode.textContent = "60〜100点では雷雲が出現！当たると残機を2つ失います。";
    }
    scoreNode.value = score;
    scoreNode.textContent = String(score);
    draw();
    frame = window.requestAnimationFrame(tick);
  }

  function startGame() {
    window.cancelAnimationFrame(frame);
    clouds = [];
    hearts = [];
    playerShots = [];
    enemyShots = [];
    score = 0;
    lives = 2;
    hitCooldown = 0;
    edgeHoldElapsed = 0;
    edgeStrikeTimer = 0;
    edgeStrikeX = 0;
    heartSpawnElapsed = 0;
    heartSpawnInterval = 6 + Math.random() * 5;
    spawnElapsed = 0;
    shotElapsed = 0;
    enemyShotElapsed = 0;
    stillElapsed = 0;
    stillAnchorX = width / 2;
    previousTime = 0;
    thunderNoticeShown = false;
    showFaceJumpscare = false;
    canvas.classList.remove("sugano-jumpscare");
    player.x = width / 2;
    keys.left = false;
    keys.right = false;
    running = true;
    scoreNode.value = 0;
    scoreNode.textContent = "0";
    updateLives();
    statusNode.textContent = faceMode ? "suganoシューティング！自動ショットで敵を撃とう！" : "雲をよけて飛ぼう！";
    startButton.disabled = true;
    startButton.textContent = "飛行中…";
    canvas.setAttribute("aria-label", faceMode ? "ゲーム中。左右の矢印キーまたは左右ボタンで移動し、自動ショットで顔の敵を攻撃します。敵の弾と落雷をよけてください。" : "ゲーム中。左右の矢印キーまたは左右ボタンで雲をよけます。画面の端に3秒いると落雷します。");
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
  if (fullscreenButton && game) {
    const updateFullscreenButton = () => {
      const isFullscreen = document.fullscreenElement === game || document.webkitFullscreenElement === game;
      fullscreenButton.textContent = isFullscreen ? "全画面を終了" : "全画面";
      fullscreenButton.setAttribute("aria-pressed", String(isFullscreen));
    };
    fullscreenButton.addEventListener("click", async () => {
      try {
        if (document.fullscreenElement || document.webkitFullscreenElement) {
          await (document.exitFullscreen?.() || document.webkitExitFullscreen?.());
        } else if (game.requestFullscreen) {
          await game.requestFullscreen();
        } else if (game.webkitRequestFullscreen) {
          game.webkitRequestFullscreen();
        } else {
          statusNode.textContent = "このブラウザーでは全画面表示を利用できません。";
        }
      } catch (_) {
        statusNode.textContent = "全画面表示を開始できませんでした。ブラウザーの設定をご確認ください。";
      }
      updateFullscreenButton();
    });
    document.addEventListener("fullscreenchange", updateFullscreenButton);
    document.addEventListener("webkitfullscreenchange", updateFullscreenButton);
  }
  draw();
})();
