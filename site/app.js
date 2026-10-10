/* agentckpt v3: Game Boy level. 10 fps frame stepping, whole native pixels, four DMG colours. */
(function () {
  "use strict";
  var C = ["#0f380f", "#306230", "#8bac0f", "#9bbc0f"];
  var RM = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- 3x5 pixel font ---------- */
  var F = {
    A:"010101111101101",B:"110101110101110",C:"011100100100011",D:"110101101101110",E:"111100110100111",
    F:"111100110100100",G:"011100101101011",H:"101101111101101",I:"111010010010111",K:"101101110101101",
    L:"100100100100111",M:"101111111101101",N:"110101101101101",O:"010101101101010",P:"110101110100100",
    R:"110101110101101",S:"011100010001110",T:"111010010010010",U:"101101101101111",V:"101101101101010",
    W:"101101111111101",X:"101101010101101",Y:"101101010010010",
    "0":"111101101101111","1":"010110010010111","2":"110001010100111","3":"110001010001110","4":"101101111001001",
    "5":"111100110001110","6":"011100111101111","7":"111001010010010","8":"111101111101111","9":"111101111001110",
    "?":"110001010000010","!":"010010010000010",".":"000000000000010","-":"000000111000000",">":"100110111110100",
    ":":"000010000010000"," ":"000000000000000"
  };
  function text(g, s, x, y, col) {
    g.fillStyle = C[col];
    for (var i = 0; i < s.length; i++) {
      var b = F[s[i]] || F[" "];
      for (var r = 0; r < 5; r++) for (var c = 0; c < 3; c++)
        if (b[r * 3 + c] === "1") g.fillRect(x + i * 4 + c, y + r, 1, 1);
    }
  }
  function tw(s) { return s.length * 4 - 1; }

  /* ---------- sprites ('.' = transparent, digit = DMG shade) ---------- */
  var HEAD = ["....0...", "....0...", ".000000.", ".003030.", ".000000.", ".011110.", ".011110.", "..0000.."];
  var LEGS = [["..0..0..", ".00..00."], [".0....0.", "0......0"], ["...00...", "..0..0.."]];
  var CLOTH_OK = ["0000000000", "0111111130", "0111111310", "0131113110", "0113131110", "0111311110", "0000000000"];
  var CLOTH_NO = ["0000000000", "0232323230", "0323232320", "0232323230", "0323232320", "0232323230", "0000000000"];
  var FILE = ["000000000000", "022222222220", "020000002220", "022222222220", "020000000020", "022222222220",
              "020000022220", "022222222220", "020000000220", "022222222220", "022222222220", "000000000000"];
  var UNTR = ["000000000000", "032323232320", "023232323230", "032300003320", "023232320230", "032323200320",
              "023232002230", "032323232320", "023232002230", "032323232320", "023232323230", "000000000000"];
  var NEWB = ["000000000000", "011111111110", "011111111110", "011113311110", "011113311110", "011333333110",
              "011333333110", "011113311110", "011113311110", "011111111110", "011111111110", "000000000000"];
  var CLOUD = ["....0000......", "..00333300....", ".0333333330000", "033333333333330", "0333333333333330", ".00000000000000"];
  function spr(g, rows, x, y) {
    for (var r = 0; r < rows.length; r++) for (var c = 0; c < rows[r].length; c++) {
      var ch = rows[r][c];
      if (ch !== ".") { g.fillStyle = C[+ch]; g.fillRect(x + c, y + r, 1, 1); }
    }
  }

  /* ---------- HUD ---------- */
  var hudSnaps = document.getElementById("hud-snaps");
  var hudWorld = document.getElementById("hud-world");
  var hudTime = document.getElementById("hud-time");
  var snaps = 0;
  function bumpSnaps() { snaps = Math.min(99, snaps + 1); if (hudSnaps) hudSnaps.textContent = snaps; }

  /* ---------- hero scene ---------- */
  var stage = document.getElementById("stage");
  var cv = document.getElementById("scene");
  var tick = document.getElementById("tick-text");
  var TICKS = [
    'The agent runs. Touch the flag first: <code>agentckpt snap</code> saves the whole tree as <code>b66469f</code>.',
    'SAVED b66469f. Tracked and untracked files are in the shadow store under <code>.agentckpt/</code>.',
    'The agent breaks things: edits, deletes, even an untracked file git never saw.',
    'CONTINUE? <code>agentckpt restore b66469f</code> puts every saved byte back.',
    'Respawned at the flag. The new block stays (restore never deletes). The git bedrock never moved.'
  ];
  var lastTick = -1;
  function setTick(i) { if (i !== lastTick && tick) { lastTick = i; tick.innerHTML = TICKS[i]; } }

  if (cv && cv.getContext) {
    var g = cv.getContext("2d");
    var W = 160, H = 120, S = 3, GY = 0, NARROW = false;
    var fx, bx = [], nx, px, py, f, phase, flagY, saved, broken, debris, jump, newOn, wipe, cont, onScreen = true, timer = 0;

    var layout = function () {
      S = +getComputedStyle(document.documentElement).getPropertyValue("--s") || 3;
      var w = stage.clientWidth, h = stage.clientHeight;
      W = Math.ceil(w / S); H = Math.ceil(h / S);
      cv.width = W; cv.height = H;
      cv.style.width = W * S + "px"; cv.style.height = H * S + "px";
      NARROW = W < 200;
      GY = H - (NARROW ? 32 : 24);       // ground top; 8 rows ground + 16 (24 on narrow screens) rows bedrock below
      fx = Math.max(28, Math.min(Math.round(W * 0.26), 84));
      var b0 = fx + (W < 160 ? 26 : 44), gap = W < 160 ? 14 : 20;
      bx = [b0, b0 + gap, b0 + gap * 2];
      nx = bx[2] + gap + 4;
      buildBg();
    };

    var reset = function () {
      px = -10; py = 0; f = 0; phase = 0; flagY = GY - 9; saved = false;
      broken = [false, false, false]; debris = []; jump = -1; newOn = false; wipe = -1; cont = 0;
    };

    var finalState = function () {
      reset(); phase = 5; saved = true; flagY = GY - 31; px = fx + 3; newOn = true; f = 0;
    };

    var bg = null, chk = null;
    var buildBg = function () {                           // static world, drawn once per layout
      bg = document.createElement("canvas"); bg.width = W; bg.height = H;
      var b = bg.getContext("2d");
      var t = document.createElement("canvas"); t.width = 2; t.height = 2;
      var tg = t.getContext("2d"); tg.fillStyle = C[0]; tg.fillRect(0, 0, 2, 2); tg.fillStyle = C[1]; tg.fillRect(1, 0, 1, 1); tg.fillRect(0, 1, 1, 1);
      var w2 = document.createElement("canvas"); w2.width = 2; w2.height = 2;
      var wg = w2.getContext("2d"); wg.fillStyle = C[0]; wg.fillRect(1, 0, 1, 1); wg.fillRect(0, 1, 1, 1);
      chk = g.createPattern(w2, "repeat");
      if (W > 200) { spr(b, CLOUD, W - 60, GY - 46); spr(b, CLOUD, W - 120, GY - 38); }
      b.fillStyle = C[1]; b.fillRect(0, GY, W, 8);
      b.fillStyle = C[0]; b.fillRect(0, GY, W, 1); b.fillRect(0, GY + 7, W, 1);
      for (var x = 0; x < W; x += 8) { b.fillStyle = C[0]; b.fillRect(x + (x % 16 ? 0 : 4), GY + 1, 1, 6); b.fillStyle = C[2]; b.fillRect(x + 1, GY + 1, 2, 1); }
      b.fillStyle = b.createPattern(t, "repeat"); b.fillRect(0, GY + 8, W, H - GY - 8);
      var label = "GIT HEAD 63FC0AE - INDEX CLEAN";
      b.fillStyle = C[0]; b.fillRect(2, GY + 11, tw(label) + 4, 9);
      text(b, label, 4, GY + 13, 3);
    };
    var drawWorld = function () {
      g.clearRect(0, 0, W, H);
      g.drawImage(bg, 0, 0);
    };

    var drawFlag = function () {
      g.fillStyle = C[0];
      g.fillRect(fx, GY - 33, 1, 33);
      g.fillRect(fx - 1, GY - 35, 3, 2);
      g.fillRect(fx - 2, GY - 2, 5, 2);
      spr(g, saved ? CLOTH_OK : CLOTH_NO, fx + 1, flagY);
      if (saved && phase < 5) {
        var s = "SAVED B66469F", w = tw(s), x = Math.max(1, Math.min(fx - (w >> 1), W - w - 2));
        g.fillStyle = C[3]; g.fillRect(x - 2, GY - 45, w + 4, 9);
        text(g, s, x, GY - 43, 0);
      }
    };

    var drawBlocks = function () {
      for (var i = 0; i < 3; i++) if (!broken[i]) spr(g, i === 1 ? UNTR : FILE, bx[i], GY - 30);
      if (newOn) spr(g, NEWB, nx, GY - 12);
      g.fillStyle = C[0];
      for (var d = 0; d < debris.length; d++) { var p = debris[d]; if (p.t < 9) g.fillRect(p.x, p.y, 3, 3); }
    };

    var drawPlayer = function (frame) {
      var y = GY - 10 + py;
      spr(g, HEAD, px, y);
      spr(g, LEGS[frame], px, y + 8);
    };

    var drawBox = function (lines, cx, y) {
      var w = 0; for (var i = 0; i < lines.length; i++) w = Math.max(w, tw(lines[i]));
      var x = Math.max(1, Math.min(cx - (w >> 1) - 4, W - w - 10));
      g.fillStyle = C[0]; g.fillRect(x, y, w + 8, lines.length * 8 + 4);
      g.fillStyle = C[3]; g.fillRect(x + 1, y + 1, w + 6, 1); g.fillRect(x + 1, y + lines.length * 8 + 2, w + 6, 1);
      for (var j = 0; j < lines.length; j++) text(g, lines[j], x + 4, y + 3 + j * 8 - (j ? 1 : 0) + 1, 3);
    };

    var render = function () {
      drawWorld(); drawFlag(); drawBlocks();
      var run = (phase === 0 || phase === 2) && !(phase === 2 && px >= nx - 10);
      drawPlayer(run ? 1 + ((f >> 1) & 1) : 0);
      if (phase === 3) drawBox(["CONTINUE?", (f & 4 ? ">" : " ") + "YES"], bx[1] + 6, GY - 46);
      if (phase === 4) {
        // dither wipe across sky and ground; the bedrock is never covered
        var edge = Math.min(W, Math.round(W * (wipe + 1) / 8));
        g.fillStyle = C[0]; g.fillRect(0, 0, Math.max(0, edge - 12), GY + 8);
        g.fillStyle = chk; g.fillRect(Math.max(0, edge - 12), 0, Math.min(12, edge), GY + 8);
      }
      if (phase === 5) {
        var s = "CONTINUE FROM B66469F", w2 = tw(s), x2 = Math.max(1, Math.min(fx - 4, W - w2 - 2));
        g.fillStyle = C[3]; g.fillRect(x2 - 2, GY - 45, w2 + 4, 9);
        text(g, s, x2, GY - 43, 0);
        if (RM || (f >> 2) & 1) {
          var u = "UNCHANGED", lx = NARROW ? 4 : tw("GIT HEAD 63FC0AE - INDEX CLEAN") + 12, ly = NARROW ? GY + 21 : GY + 11;
          g.fillStyle = C[3]; g.fillRect(lx - 2, ly, tw(u) + 4, 9); text(g, u, lx, ly + 2, 0);
        }
      }
    };

    var JUMP = [-2, -4, -6, -7, -7, -6, -4, -2, 0];
    var step = function () {
      f++;
      for (var d = 0; d < debris.length; d++) { var p = debris[d]; p.x += p.vx; p.y += p.vy; p.vy += 1; p.t++; }
      if (phase === 0) {                                   // run to the flag
        px += 2; setTick(0);
        if (px >= fx - 7) { px = fx - 7; phase = 1; f = 0; }
      } else if (phase === 1) {                            // touch flag: it climbs in 2px steps
        if (f === 1) { saved = true; bumpSnaps(); setTick(1); }
        if (flagY > GY - 31) flagY = Math.max(GY - 31, flagY - 2);
        else if (f > 16) { phase = 2; f = 0; }
      } else if (phase === 2) {                            // run through the files
        setTick(2);
        if (px < nx - 10) px += 2;
        for (var i = 0; i < 3; i++) if (!broken[i] && jump < 0 && px + 4 >= bx[i] + 2 && px + 4 <= bx[i] + 10) jump = 0;
        if (jump >= 0) {
          py = JUMP[jump];
          if (jump === 3) for (var k = 0; k < 3; k++) if (!broken[k] && px + 8 > bx[k] && px < bx[k] + 12) {
            broken[k] = true;
            debris.push({ x: bx[k], y: GY - 30, vx: -1, vy: -3, t: 0 }, { x: bx[k] + 8, y: GY - 30, vx: 1, vy: -3, t: 0 },
                        { x: bx[k], y: GY - 24, vx: -2, vy: -1, t: 0 }, { x: bx[k] + 8, y: GY - 24, vx: 2, vy: -1, t: 0 });
          }
          jump++; if (jump >= JUMP.length) { jump = -1; py = 0; }
        }
        if (px >= nx - 10 && jump < 0) {
          if (!newOn) { newOn = true; f = 0; }
          if (f > 6) { phase = 3; f = 0; debris = []; }
        }
      } else if (phase === 3) {                            // CONTINUE? >YES
        setTick(3);
        if (f > 22) { phase = 4; wipe = 0; f = 0; }
      } else if (phase === 4) {                            // dither wipe
        wipe++;
        if (wipe > 8) { phase = 5; f = 0; broken = [false, false, false]; px = fx + 3; py = 0; setTick(4); }
      } else if (phase === 5) {                            // respawned, world rebuilt, bedrock unchanged
        if (f > 46) reset();
      }
      render();
    };

    var loop = function () {
      timer = 0;
      if (!onScreen || document.hidden) return;
      step();
      timer = setTimeout(loop, 100);                         // 10 fps
    };
    var start = function () { if (!timer && !RM) timer = setTimeout(loop, 100); };

    layout();
    if (RM) { finalState(); render(); setTick(4); snaps = 0; bumpSnaps(); }
    else { reset(); render(); start(); }

    var rt;
    window.addEventListener("resize", function () {
      clearTimeout(rt);
      rt = setTimeout(function () { var p = phase; layout(); if (RM || p === 5) { finalState(); } else reset(); render(); }, 150);
    });
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (es) { onScreen = es[0].isIntersecting; if (onScreen) start(); }).observe(stage);
    }
    document.addEventListener("visibilitychange", function () { if (!document.hidden) start(); });
  }

  /* ---------- HUD timer: counts down in whole seconds ---------- */
  if (hudTime && !RM) {
    var t = 400;
    setInterval(function () { if (document.hidden) return; t = t > 0 ? t - 1 : 400; hudTime.textContent = ("00" + t).slice(-3); }, 1000);
  }

  /* ---------- WORLD indicator from the section in view ---------- */
  if ("IntersectionObserver" in window && hudWorld) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) hudWorld.textContent = e.target.getAttribute("data-world"); });
    }, { rootMargin: "-45% 0px -50% 0px" });
    document.querySelectorAll("[data-world]").forEach(function (el) { io.observe(el); });
  }

  /* ---------- WORLD 1-2/1-3 step machine ---------- */
  var screen = document.getElementById("screen");
  var steps = document.querySelectorAll(".step");
  var slotT = document.getElementById("slot-t");
  var stateEl = document.getElementById("state");
  var NAMES = ["", "STEP 1 · INIT", "STEP 2 · SAVED B66469F", "STEP 3 · BLOCKS BROKEN", "STEP 4 · CONTINUE: WORLD REBUILT", "STEP 5 · BEDROCK UNCHANGED"];
  function setStep(n) {
    if (!screen || screen.getAttribute("data-step") === String(n)) return;
    screen.setAttribute("data-step", n);
    steps.forEach(function (s) { s.classList.toggle("on", s.getAttribute("data-step") === String(n)); });
    if (n >= 2 && snaps < 1) bumpSnaps();
    if (slotT) slotT.textContent = n >= 2 ? "SLOT 1 · B66469F · 3 FILES" : "SLOT 1 · EMPTY";
    if (stateEl) stateEl.textContent = NAMES[n];
    if (hudWorld) hudWorld.textContent = n >= 4 ? "1-3" : "1-2";
  }
  if (screen && steps.length) {
    steps[0].classList.add("on");
    steps.forEach(function (s) {
      var n = +s.getAttribute("data-step");
      s.addEventListener("click", function () { setStep(n); });
      s.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setStep(n); } });
    });
    if ("IntersectionObserver" in window) {
      var so = new IntersectionObserver(function (es) {
        es.forEach(function (e) { if (e.isIntersecting) setStep(+e.target.getAttribute("data-step")); });
      }, { rootMargin: "-55% 0px -40% 0px" });
      steps.forEach(function (s) { so.observe(s); });
    }
  }

  /* ---------- [A] COPY ---------- */
  document.querySelectorAll("[data-copy]").forEach(function (b) {
    b.addEventListener("click", function () {
      var el = document.querySelector(b.getAttribute("data-copy"));
      if (!el || !navigator.clipboard) return;
      navigator.clipboard.writeText(el.textContent).then(function () {
        var old = b.innerHTML;
        b.classList.add("done"); b.innerHTML = '<span aria-hidden="true">A</span> SAVED';
        setTimeout(function () { b.classList.remove("done"); b.innerHTML = old; }, 1400);
      });
    });
  });
})();
