(() => {
  const canvas = document.getElementById("mini-game-canvas");
  if (!canvas) return;
  const context = canvas.getContext("2d");
  const scoreNode = document.getElementById("mini-game-score");
  const livesNode = document.getElementById("mini-game-lives");
  const statusNode = document.getElementById("mini-game-status");
  const killCommentNode = document.getElementById("mini-game-kill-comment");
  const titleNode = document.getElementById("mini-game-title");
  const helpNode = document.querySelector(".mini-game-help");
  const startButton = document.getElementById("mini-game-start");
  const fullscreenButton = document.getElementById("mini-game-fullscreen");
  const game = document.querySelector(".mini-game");
  const faceMode = new URLSearchParams(window.location.search).get("mode") === "sugano";
  const faceSpriteSheet = new Image();
  const bossSpriteImage = new Image();
  let bossSpriteCanvas = null;
  const duoBossImage = new Image();
  const summonedFaceImage = new Image();
  let summonedFaceCanvas = null;
  const thunderJumpscareImage = new Image();
  let thunderJumpscareCanvas = null;
  if (faceMode) faceSpriteSheet.src = "/static/404-face-hazards.png?v=20261124-2";
  if (faceMode) {
    duoBossImage.src = "/static/404-sugano-dual-boss.png?v=20261127-1";
    bossSpriteImage.onload = () => {
      const sprite = document.createElement("canvas");
      sprite.width = 84;
      sprite.height = 84;
      const spriteContext = sprite.getContext("2d", { willReadFrequently: true });
      spriteContext.drawImage(bossSpriteImage, 4, 18, 84, 84, 0, 0, 84, 84);
      const pixels = spriteContext.getImageData(0, 0, sprite.width, sprite.height);
      for (let index = 0; index < pixels.data.length; index += 4) {
        const red = pixels.data[index];
        const green = pixels.data[index + 1];
        const blue = pixels.data[index + 2];
        if (red > 224 && green > 224 && blue > 224 && Math.max(red, green, blue) - Math.min(red, green, blue) < 22) {
          pixels.data[index + 3] = 0;
        }
      }
      spriteContext.putImageData(pixels, 0, 0);
      bossSpriteCanvas = sprite;
    };
    bossSpriteImage.src = "/static/404-sugano-boss-source.png?v=20261124-1";
    summonedFaceImage.onload = () => {
      const sprite = document.createElement("canvas");
      sprite.width = summonedFaceImage.naturalWidth;
      sprite.height = summonedFaceImage.naturalHeight;
      const spriteContext = sprite.getContext("2d", { willReadFrequently: true });
      spriteContext.drawImage(summonedFaceImage, 0, 0);
      const pixels = spriteContext.getImageData(0, 0, sprite.width, sprite.height);
      for (let index = 0; index < pixels.data.length; index += 4) {
        const red = pixels.data[index];
        const green = pixels.data[index + 1];
        const blue = pixels.data[index + 2];
        if (red > 224 && green > 224 && blue > 224 && Math.max(red, green, blue) - Math.min(red, green, blue) < 22) {
          pixels.data[index + 3] = 0;
        }
      }
      spriteContext.putImageData(pixels, 0, 0);
      summonedFaceCanvas = sprite;
    };
    summonedFaceImage.src = "/static/404-sugano-summoned-face.png?v=20261124-1";
    thunderJumpscareImage.onload = () => {
      const sprite = document.createElement("canvas");
      sprite.width = thunderJumpscareImage.naturalWidth;
      sprite.height = thunderJumpscareImage.naturalHeight;
      const spriteContext = sprite.getContext("2d", { willReadFrequently: true });
      spriteContext.drawImage(thunderJumpscareImage, 0, 0);
      const pixels = spriteContext.getImageData(0, 0, sprite.width, sprite.height);
      for (let index = 0; index < pixels.data.length; index += 4) {
        const red = pixels.data[index];
        const green = pixels.data[index + 1];
        const blue = pixels.data[index + 2];
        if (red > 238 && green > 238 && blue > 238 && Math.max(red, green, blue) - Math.min(red, green, blue) < 18) {
          pixels.data[index + 3] = 0;
        }
      }
      spriteContext.putImageData(pixels, 0, 0);
      thunderJumpscareCanvas = sprite;
    };
    thunderJumpscareImage.src = "/static/404-sugano-thunder.png?v=20261124-1";
  }
  if (faceMode) {
    canvas.height = 420;
    canvas.classList.add("sugano-shooter");
  }
  const keys = { left: false, right: false };
  const width = canvas.width;
  const height = canvas.height;
  const player = { x: width / 2, y: height - 28, radius: 13, speed: 300 };
  let clouds = [];
  let boss = null;
  let bossAppeared = false;
  let duoBosses = null;
  let duoBossesStarted = false;
  let duoProjectiles = [];
  let duoLightning = [];
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
  let jumpscareIsBoss = false;
  let jumpscareIsDuoBoss = false;
  let duoBossKillSource = null;
  let jumpscareDuoBossKind = null;
  let wasKilledByThunder = false;
  let jumpscareIsThunder = false;
  let bossKeySequence = "";

  if (faceMode) {
    if (titleNode) titleNode.textContent = "suganoシューティング";
    if (helpNode) helpNode.textContent = "自動ショットで顔の敵を倒し、敵の弾や落雷をよけてください。同じ場所に3秒いると顔が高速で落ちてきます。150点でボス、250点で左右の双子ボスが出現します。";
  }

  function drawCloud(cloud) {
    if (cloud.bossMinion && summonedFaceCanvas) {
      const spriteSize = cloud.radius * 2 + 4;
      context.drawImage(summonedFaceCanvas, cloud.x - spriteSize / 2, cloud.y - spriteSize / 2, spriteSize, spriteSize);
    } else if (faceMode && faceSpriteSheet.complete && faceSpriteSheet.naturalWidth > 0) {
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

  function drawBoss() {
    if (!boss) return;
    if (bossSpriteCanvas) {
      context.drawImage(bossSpriteCanvas, boss.x - 75, boss.y - 35, 150, 150);
    } else if (faceSpriteSheet.complete && faceSpriteSheet.naturalWidth > 0) {
      const sourceWidth = faceSpriteSheet.naturalWidth / 5;
      const sourceTop = faceSpriteSheet.naturalHeight * 0.18;
      const sourceHeight = faceSpriteSheet.naturalHeight * 0.65;
      [1, 3, 4].forEach((index, position) => {
        const offset = position === 0 ? 0 : position === 1 ? -46 : 46;
        const yOffset = position === 0 ? -16 : 13;
        const size = position === 0 ? 76 : 66;
        context.drawImage(faceSpriteSheet, index * sourceWidth, sourceTop, sourceWidth, sourceHeight,
          boss.x + offset - size / 2, boss.y + yOffset - size / 2, size, size);
      });
    }
    const barWidth = 190;
    const barX = boss.x - barWidth / 2;
    const barY = boss.y + 76;
    context.fillStyle = "rgba(255,255,255,.85)";
    context.fillRect(barX, barY, barWidth, 10);
    context.fillStyle = "#ff4e88";
    context.fillRect(barX, barY, barWidth * Math.max(0, boss.hp) / 100, 10);
    context.strokeStyle = "rgba(255,255,255,.9)";
    context.strokeRect(barX, barY, barWidth, 10);
    context.fillStyle = "#fff";
    context.font = "bold 13px system-ui, sans-serif";
    context.textAlign = "center";
    context.textBaseline = "bottom";
    context.fillText(`BOSS ${boss.hp}/100`, boss.x, barY - 3);
  }

  function drawDuoBosses() {
    if (!duoBosses?.length) return;
    for (const enemy of duoBosses) {
      const maxBossWidth = 112;
      const maxBossHeight = 132;
      const imageScale = duoBossImage.naturalWidth > 0 ? Math.min(maxBossWidth / duoBossImage.naturalWidth, maxBossHeight / duoBossImage.naturalHeight) : 1;
      const bossWidth = duoBossImage.naturalWidth * imageScale;
      const bossHeight = duoBossImage.naturalHeight * imageScale;
      if (duoBossImage.complete && duoBossImage.naturalWidth > 0) {
        context.save();
        if (enemy.kind === "thunder") {
          context.translate(enemy.x, enemy.y);
          context.scale(-1, 1);
          context.drawImage(duoBossImage, -bossWidth / 2, -bossHeight / 2, bossWidth, bossHeight);
        } else {
          context.drawImage(duoBossImage, enemy.x - bossWidth / 2, enemy.y - bossHeight / 2, bossWidth, bossHeight);
        }
        context.restore();
      } else {
        context.fillStyle = enemy.kind === "wind" ? "#72e6df" : "#f4cd5f";
        context.beginPath();
        context.arc(enemy.x, enemy.y, 38, 0, Math.PI * 2);
        context.fill();
      }
      const barWidth = 104;
      const barX = enemy.x - barWidth / 2;
      const barY = enemy.y + 52;
      context.fillStyle = "rgba(255,255,255,.9)";
      context.fillRect(barX, barY, barWidth, 9);
      context.fillStyle = enemy.kind === "wind" ? "#62e8df" : "#ffd35d";
      context.fillRect(barX, barY, barWidth * Math.max(0, enemy.hp) / 150, 9);
      context.strokeStyle = "rgba(255,255,255,.95)";
      context.strokeRect(barX, barY, barWidth, 9);
      context.fillStyle = "#fff";
      context.font = "bold 12px system-ui, sans-serif";
      context.textAlign = "center";
      context.textBaseline = "bottom";
      context.fillText(`${enemy.kind === "wind" ? "風 BOSS" : "雷 BOSS"} ${enemy.hp}/150`, enemy.x, barY - 2);
    }
  }

  function drawDuoAttacks() {
    context.save();
    for (const orb of duoProjectiles) {
      const glow = context.createRadialGradient(orb.x - 4, orb.y - 5, 2, orb.x, orb.y, orb.radius + 9);
      glow.addColorStop(0, "#efffff");
      glow.addColorStop(.45, "#74f4ed");
      glow.addColorStop(1, "rgba(61,190,224,0)");
      context.fillStyle = glow;
      context.beginPath();
      context.arc(orb.x, orb.y, orb.radius + 9, 0, Math.PI * 2);
      context.fill();
      context.strokeStyle = "rgba(226,255,255,.9)";
      context.lineWidth = 2;
      context.beginPath();
      context.arc(orb.x, orb.y, orb.radius * .72, orb.spin, orb.spin + Math.PI * 1.45);
      context.stroke();
    }
    for (const bolt of duoLightning) {
      context.strokeStyle = "#ffe36c";
      context.lineWidth = 7;
      context.lineJoin = "round";
      context.shadowColor = "#fff1a0";
      context.shadowBlur = 16;
      context.beginPath();
      context.moveTo(bolt.x, bolt.y);
      context.lineTo(bolt.x - 8, bolt.y + 23);
      context.lineTo(bolt.x + 7, bolt.y + 37);
      context.lineTo(bolt.x - 6, bolt.y + 54);
      context.lineTo(bolt.x + 3, Math.min(height, bolt.y + bolt.length));
      context.stroke();
    }
    context.restore();
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
    for (const shot of enemyShots) {
      context.fillStyle = shot.windShard ? "#a8fff3" : "#ff6ca7";
      context.shadowColor = shot.windShard ? "#61ebdf" : "#ff4c92";
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
    drawBoss();
    drawDuoAttacks();
    drawDuoBosses();
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
      let gameOverCaptionY = height - 34;
      if (jumpscareIsThunder && thunderJumpscareCanvas) {
        const scale = Math.min(width / thunderJumpscareCanvas.width, height / thunderJumpscareCanvas.height) * 1.18;
        const faceWidth = thunderJumpscareCanvas.width * scale;
        const faceHeight = thunderJumpscareCanvas.height * scale;
        context.drawImage(thunderJumpscareCanvas, (width - faceWidth) / 2, (height - faceHeight) / 2, faceWidth, faceHeight);
      } else if (jumpscareIsBoss && bossSpriteCanvas) {
        const scale = Math.max(width / bossSpriteCanvas.width, height / bossSpriteCanvas.height) * 1.18;
        const faceWidth = bossSpriteCanvas.width * scale;
        const faceHeight = bossSpriteCanvas.height * scale;
        context.drawImage(bossSpriteCanvas, (width - faceWidth) / 2, (height - faceHeight) / 2, faceWidth, faceHeight);
      } else if (jumpscareIsDuoBoss && duoBossImage.complete && duoBossImage.naturalWidth > 0) {
        const scale = Math.min(width / duoBossImage.naturalWidth, height / duoBossImage.naturalHeight) * .72;
        const faceWidth = duoBossImage.naturalWidth * scale;
        const faceHeight = duoBossImage.naturalHeight * scale;
        gameOverCaptionY = Math.min(height - 18, (height + faceHeight) / 2 + 27);
        if (jumpscareDuoBossKind === "thunder") {
          context.translate(width / 2, height / 2);
          context.scale(-1, 1);
          context.drawImage(duoBossImage, -faceWidth / 2, -faceHeight / 2, faceWidth, faceHeight);
        } else {
          context.drawImage(duoBossImage, (width - faceWidth) / 2, (height - faceHeight) / 2, faceWidth, faceHeight);
        }
      } else if (faceSpriteSheet.complete && faceSpriteSheet.naturalWidth > 0) {
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
      const gameOverCaption = jumpscareIsDuoBoss && jumpscareDuoBossKind === "thunder" ? "ずっと一緒だね❤️" : jumpscareIsThunder ? "俺より馬鹿やんｗｗ" : jumpscareIsDuoBoss ? "また１から頑張ってねーー＾＾" : jumpscareIsBoss ? "学校いけよ" : "すがのに殺された";
      if (!jumpscareIsDuoBoss) {
        context.strokeText(gameOverCaption, width / 2, gameOverCaptionY);
        context.fillStyle = "#fff";
        context.fillText(gameOverCaption, width / 2, gameOverCaptionY);
      }
      context.restore();
    }
  }

  function endGame() {
    running = false;
    showFaceJumpscare = faceMode;
    jumpscareIsDuoBoss = faceMode && Boolean(duoBosses?.length);
    jumpscareIsThunder = faceMode && wasKilledByThunder && !jumpscareIsDuoBoss;
    jumpscareIsBoss = faceMode && Boolean(boss) && !jumpscareIsThunder && !jumpscareIsDuoBoss;
    jumpscareDuoBossKind = duoBossKillSource || (wasKilledByThunder ? "thunder" : "wind");
    if (killCommentNode) {
      killCommentNode.hidden = !jumpscareIsDuoBoss;
      killCommentNode.textContent = jumpscareIsDuoBoss
        ? jumpscareDuoBossKind === "thunder" ? "ずっと一緒だね❤️" : "また１から頑張ってねーー＾＾"
        : "";
    }
    if (faceMode) {
      jumpscareFaceIndex = clouds.find((cloud) => cloud.dive)?.faceIndex ?? Math.floor(Math.random() * 5);
      canvas.classList.remove("sugano-jumpscare");
      void canvas.offsetWidth;
      canvas.classList.add("sugano-jumpscare");
    }
    startButton.disabled = false;
    startButton.textContent = "もう一度飛ぶ";
    statusNode.textContent = faceMode ? "ゲームオーバー！もう一度飛んでね。" : "雲にぶつかった！";
    canvas.setAttribute("aria-label", `ゲーム終了。スコア ${score}。もう一度飛ぶボタンで再開できます。`);
    draw();
  }

  function startBossFight() {
    if (!faceMode || bossAppeared) return;
    bossAppeared = true;
    boss = { x: width / 2, y: 82, age: 0, hp: 100, summonElapsed: 0 };
    spawnElapsed = 0;
    clouds = [];
    enemyShots = [];
    score = Math.max(score, 150);
    scoreNode.value = score;
    scoreNode.textContent = String(score);
    statusNode.textContent = "ボス出現！3つの顔を攻撃して、召喚された顔を避けよう！";
  }

  function startDuoBossFight() {
    if (!faceMode || duoBossesStarted || score < 250) return;
    duoBossesStarted = true;
    boss = null;
    duoBosses = [
      { kind: "wind", x: width * .22, baseX: width * .22, y: 88, age: 0, hp: 150, attackElapsed: 0, phase: Math.asin(-.28 / .44) },
      { kind: "thunder", x: width * .8, baseX: width * .8, y: 88, age: 0, hp: 150, attackElapsed: 0, phase: Math.asin(.3 / .44) }
    ];
    clouds = [];
    enemyShots = [];
    duoProjectiles = [];
    duoLightning = [];
    score = Math.max(score, 250);
    scoreNode.value = score;
    scoreNode.textContent = String(score);
    statusNode.textContent = "250点！双子ボス出現。左の風弾は分裂、右の雷は真下に落ちる！";
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
    if (faceMode && !bossAppeared && score > 150) startBossFight();
    if (faceMode && bossAppeared && !boss && !duoBossesStarted && score >= 250) startDuoBossFight();
    heartSpawnElapsed += delta;
    if (heartSpawnElapsed >= heartSpawnInterval) {
      heartSpawnElapsed = 0;
      heartSpawnInterval = 8 + Math.random() * 8;
      if (!hearts.length) hearts.push({ x: 24 + Math.random() * (width - 48), y: -14, speed: 105 + Math.min(score * 0.35, 55), radius: 10 });
    }
    const spawnInterval = faceMode ? Math.max(1.1, 2.3 - score * 0.008) : Math.max(0.32, 0.88 - score * 0.0056);
    if ((!faceMode || (!boss && !duoBosses)) && spawnElapsed >= spawnInterval) {
      spawnElapsed = 0;
      const thunderChance = score >= 60 && score <= 100 ? Math.min(0.4, 0.22 + (score - 60) * 0.002) : 0;
      const thunder = Math.random() < thunderChance;
      const speed = faceMode ? 82 + Math.min(score * 1.5, 150) + Math.random() * 20 : 115 + Math.min(score * 2.25, 270) + Math.random() * 28;
      const lateralRange = score >= 80 ? 8 + Math.min((score - 80) * 0.05, 10) : 0;
      if (faceMode) {
        const maxEnemies = score > 100 ? 6 : Math.min(5, 3 + Math.floor(score / 20));
        const enemyCount = 2 + Math.floor(Math.random() * (maxEnemies - 1));
        const usedX = [];
        for (let index = 0; index < enemyCount; index += 1) {
          let enemyX = 0;
          for (let attempt = 0; attempt < 8; attempt += 1) {
            enemyX = 30 + Math.random() * (width - 60);
            if (usedX.every((x) => Math.abs(x - enemyX) > 42)) break;
          }
          usedX.push(enemyX);
          const enemyY = -24 - Math.random() * 132;
          const enemySpeed = speed * (0.72 + Math.random() * 0.62);
          const enemySway = score >= 80 ? lateralRange * (0.45 + Math.random() * 1.1) : 0;
          clouds.push({ x: enemyX, startX: enemyX, y: enemyY, speed: enemySpeed, radius: 20, thunder: Math.random() < thunderChance, faceIndex: Math.floor(Math.random() * 5), lateralRange: enemySway, phase: Math.random() * Math.PI * 2, age: 0 });
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
        wasKilledByThunder = lives <= 1;
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
      if (cloud.charge) {
        cloud.x += cloud.vx * delta;
        cloud.y += cloud.vy * delta;
        return;
      }
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
    if (boss) {
      boss.age += delta;
      boss.x = width / 2 + Math.sin(boss.age * 0.82) * Math.min(150, width * 0.23);
      boss.y = 76 + Math.sin(boss.age * 1.25) * 12;
      boss.summonElapsed += delta;
      if (boss.summonElapsed >= 2.2) {
        boss.summonElapsed = 0;
        const summonCount = boss.hp < 50 ? 2 : 1;
        for (let index = 0; index < summonCount; index += 1) {
          const laneOffset = summonCount === 2 ? (index === 0 ? -34 : 34) : (Math.random() - 0.5) * 90;
          const startX = boss.x + (index - (summonCount - 1) / 2) * 26;
          const startY = boss.y + 46;
          const targetX = Math.max(24, Math.min(width - 24, player.x + laneOffset));
          const deltaX = targetX - startX;
          const deltaY = player.y - startY;
          const distance = Math.hypot(deltaX, deltaY) || 1;
          const chargeSpeed = 440;
          clouds.push({
            x: startX, y: startY, startX, speed: 0,
            vx: deltaX / distance * chargeSpeed, vy: deltaY / distance * chargeSpeed,
            radius: 29, thunder: false, faceIndex: 0, lateralRange: 0, phase: 0, age: 0,
            dive: true, bossMinion: true, charge: true
          });
        }
        statusNode.textContent = summonCount === 2 ? "ボスが顔を2体召喚！突進を避けて！" : "ボスが顔を召喚！突進を避けて！";
      }
    }
    if (duoBosses?.length) {
      for (const enemy of duoBosses) {
        enemy.age += delta;
        const enraged = enemy.hp <= 75;
        const movementSpeed = enemy.kind === "wind" ? (enraged ? 2.35 : 1.55) : (enraged ? 2.1 : 1.35);
        enemy.x = Math.max(48, Math.min(width - 48, width * .5 + Math.sin(enemy.age * movementSpeed + enemy.phase) * width * .44));
        enemy.y = 82 + Math.sin(enemy.age * (enraged ? 2.7 : 1.65)) * 11;
        enemy.attackElapsed += delta;
        const attackInterval = enemy.kind === "thunder" ? (enraged ? .95 : 1.65) : (enraged ? 1.2 : 2.15);
        if (enemy.attackElapsed >= attackInterval) {
          enemy.attackElapsed = 0;
          if (enemy.kind === "thunder") {
            const boltCount = enraged ? 2 : 1;
            for (let index = 0; index < boltCount; index += 1) {
              const offset = boltCount === 2 ? (index === 0 ? -32 : 32) : 0;
              duoLightning.push({ x: Math.max(24, Math.min(width - 24, player.x + offset)), y: enemy.y + 45, speed: enraged ? 820 : 650, length: enraged ? height : 74 });
            }
            statusNode.textContent = enraged ? "雷ボスが画面を貫く狙い撃ち落雷を連続発射！" : "雷ボスがあなたの位置を狙って落雷！横へ避けて！";
          } else {
            const volleyCount = enraged ? 2 : 1;
            for (let volley = 0; volley < volleyCount; volley += 1) {
              duoProjectiles.push({ x: enemy.x + (volley ? 26 : 0), y: enemy.y + 40, radius: 14, speed: enraged ? 235 : 185, splitAt: height * .48, spin: Math.random() * Math.PI * 2 });
            }
            statusNode.textContent = enraged ? "風ボスが風の玉を連続発射！分裂弾に注意！" : "左の風ボスが風の玉を発射！分裂後の弾を避けて！";
          }
        }
      }
    }
    const remainingOrbs = [];
    for (const orb of duoProjectiles) {
      orb.y += orb.speed * delta;
      orb.spin += delta * 5;
      if (Math.hypot(player.x - orb.x, player.y - orb.y) < player.radius + orb.radius && hitCooldown <= 0) {
        wasKilledByThunder = false;
        if (lives <= 1) duoBossKillSource = "wind";
        lives = Math.max(0, lives - 1);
        updateLives();
        hitCooldown = 1.1;
        statusNode.textContent = "風の玉に当たった！残機を1つ使いました。";
        if (lives <= 0) { endGame(); return; }
      }
      if (orb.y >= orb.splitAt) {
        const baseAngle = Math.atan2(player.x - orb.x, player.y - orb.y);
        const bulletSpeed = duoBosses?.find((enemy) => enemy.kind === "wind")?.hp <= 75 ? 390 : 300;
        [-.48, 0, .48].forEach((offset) => {
          const angle = baseAngle + offset;
          enemyShots.push({ x: orb.x, y: orb.y, vx: Math.sin(angle) * bulletSpeed, speed: Math.cos(angle) * bulletSpeed, radius: 6, windShard: true });
        });
      } else if (orb.y < height + 20) remainingOrbs.push(orb);
    }
    duoProjectiles = remainingOrbs;
    const remainingLightning = [];
    for (const bolt of duoLightning) {
      bolt.y += bolt.speed * delta;
      const inBoltPath = Math.abs(player.x - bolt.x) < 15 && player.y >= bolt.y - 8 && player.y <= bolt.y + bolt.length;
      if (inBoltPath && hitCooldown <= 0) {
        wasKilledByThunder = false;
        if (lives <= 1) duoBossKillSource = "thunder";
        lives = Math.max(0, lives - 1);
        updateLives();
        hitCooldown = 1.1;
        statusNode.textContent = "雷ボスの落雷に当たった！残機を1つ使いました。";
        if (lives <= 0) { endGame(); return; }
      }
      if (bolt.y < height + 12) remainingLightning.push(bolt);
    }
    duoLightning = remainingLightning;
    if (faceMode) {
      if (!duoBosses?.length) {
        enemyShotElapsed += delta;
        if (enemyShotElapsed >= Math.max(0.55, 1.35 - score * 0.004)) {
          enemyShotElapsed = 0;
          const shooters = clouds.filter((cloud) => !cloud.bossMinion && cloud.y > 24 && cloud.y < player.y - 80);
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
      }
      const remainingPlayerShots = [];
      for (const shot of playerShots) {
        shot.y -= shot.speed * delta;
        if (duoBosses?.length) {
          const target = duoBosses.find((enemy) => Math.abs(shot.x - enemy.x) < 56 && Math.abs(shot.y - enemy.y) < 63);
          if (target) {
            target.hp = Math.max(0, target.hp - 1);
            if (target.hp === 0) {
              const defeated = target.kind === "wind" ? "風" : "雷";
              duoBosses = duoBosses.filter((enemy) => enemy !== target);
              if (!duoBosses.length) {
                duoBosses = null;
                score += 50;
                statusNode.textContent = "双子ボス撃破！ボーナス50点！";
              } else {
                statusNode.textContent = `${defeated}ボス撃破！もう1体を倒そう！`;
              }
            } else if (target.hp === 75) {
              statusNode.textContent = `${target.kind === "wind" ? "風" : "雷"}ボスが本気になった！動きと攻撃が速くなる！`;
            }
            continue;
          }
        }
        if (boss && Math.abs(shot.x - boss.x) < 82 && Math.abs(shot.y - (boss.y + 25)) < 60) {
          boss.hp -= 1;
          if (boss.hp <= 0) {
            boss = null;
            score += 25;
            statusNode.textContent = "ボス撃破！ボーナス25点！";
          }
          continue;
        }
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
            wasKilledByThunder = false;
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
          wasKilledByThunder = cloud.thunder && lives <= damage;
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
    if (score >= 60 && score <= 100 && !thunderNoticeShown) {
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
    boss = null;
    bossAppeared = false;
    duoBosses = null;
    duoBossesStarted = false;
    duoProjectiles = [];
    duoLightning = [];
    bossKeySequence = "";
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
    if (killCommentNode) {
      killCommentNode.hidden = true;
      killCommentNode.textContent = "";
    }
    jumpscareIsBoss = false;
    jumpscareIsDuoBoss = false;
    duoBossKillSource = null;
    jumpscareDuoBossKind = null;
    wasKilledByThunder = false;
    jumpscareIsThunder = false;
    canvas.classList.remove("sugano-jumpscare");
    player.x = width / 2;
    keys.left = false;
    keys.right = false;
    running = true;
    scoreNode.value = score;
    scoreNode.textContent = String(score);
    updateLives();
    statusNode.textContent = faceMode ? "suganoゲーム開始！プレイ中に boss と入力するとボス戦！" : "雲をよけて飛ぼう！";
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
    if (faceMode && !event.repeat && /^[a-z]$/.test(key)) {
      bossKeySequence = (bossKeySequence + key).slice(-8);
      if (bossKeySequence === "hannbunn") {
        score = 250;
        bossAppeared = true;
        scoreNode.value = score;
        scoreNode.textContent = String(score);
        startDuoBossFight();
        bossKeySequence = "";
      }
      if (bossKeySequence === "boss") {
        startBossFight();
        bossKeySequence = "";
      }
    }
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
