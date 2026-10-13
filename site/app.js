/* agentckpt v4: pill organizer. Hero loop, step demo, dispense buttons. Transforms and opacity only. */
(function () {
  "use strict";
  var RM = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var hero = document.getElementById("hero");
  var status = document.getElementById("status");
  var flyer = document.getElementById("flyer");
  var cells = hero ? hero.querySelectorAll(".cells .cell") : [];
  var DAY = 2; // Wednesday's dose
  var MSG = {
    calm: 'Agent is working. Last dose: <code>b66469f</code>',
    sick: 'Agent turn: rewrites <code>a.txt</code>, deletes <code>src/app.py</code> and the untracked <code>notes.md</code>.',
    dose: 'Opening Wednesday… <code>agentckpt restore b66469f</code>',
    gulp: '<i>gulp</i>',
    well: 'Restored 3 files from <code>b66469f</code>. git: no interactions.'
  };
  function setPhase(p) {
    if (!hero) return;
    hero.setAttribute("data-phase", p);
    if (status) status.innerHTML = MSG[p];
  }

  function throwPill(done) {
    var cell = cells[DAY], mouth = hero.querySelector(".ward .agent");
    if (!cell || !mouth || !flyer.animate) { done(); return; }
    var hb = hero.getBoundingClientRect(), cb = cell.getBoundingClientRect(), mb = mouth.getBoundingClientRect();
    var x0 = cb.left - hb.left + cb.width / 2 - 36, y0 = cb.top - hb.top + cb.height / 2 - 14;
    var x1 = mb.left - hb.left + mb.width / 2 - 36, y1 = mb.top - hb.top + mb.height * 0.66 - 14;
    var peak = Math.min(y0, y1) - 70;
    flyer.classList.add("go");
    cell.classList.add("taken");
    var kf = [], n = 12;
    for (var i = 0; i <= n; i++) {
      var t = i / n, x = x0 + (x1 - x0) * t;
      var y = (1 - t) * (1 - t) * y0 + 2 * (1 - t) * t * peak + t * t * y1; // quadratic arc
      kf.push({ transform: "translate(" + x.toFixed(1) + "px," + y.toFixed(1) + "px) rotate(" + (-30 + t * 540).toFixed(0) + "deg) scale(" + (1 - t * 0.2).toFixed(2) + ")" });
    }
    var a = flyer.animate(kf, { duration: 1000, easing: "linear", fill: "forwards" });
    a.onfinish = function () { flyer.classList.remove("go"); a.cancel(); done(); };
  }

  var timers = [], running = false, visible = true;
  function at(ms, fn) { timers.push(setTimeout(fn, ms)); }
  function clear() { timers.forEach(clearTimeout); timers = []; }
  function cycle() {
    if (!visible || document.hidden) { running = false; return; }
    running = true;
    cells.forEach(function (c) { c.classList.remove("open", "taken"); });
    setPhase("calm");
    at(1800, function () { setPhase("sick"); });
    at(4000, function () { setPhase("dose"); cells[DAY].classList.add("open"); });
    at(4600, function () {
      throwPill(function () {
        setPhase("gulp");
        at(380, function () { setPhase("well"); });
        at(4300, function () { cells[DAY].classList.remove("open"); });
        at(5200, cycle);
      });
    });
  }
  function finalFrame() {
    cells[DAY] && cells[DAY].classList.add("open", "taken");
    setPhase("well");
  }
  if (hero) {
    if (RM) finalFrame();
    else {
      cycle();
      if ("IntersectionObserver" in window) {
        new IntersectionObserver(function (es) {
          visible = es[0].isIntersecting;
          if (visible && !running) { clear(); cycle(); }
        }).observe(hero);
      }
      document.addEventListener("visibilitychange", function () { if (!document.hidden && !running) { clear(); cycle(); } });
    }
  }

  /* step demo */
  var panel = document.getElementById("panel");
  var steps = document.querySelectorAll(".step");
  var pstate = document.getElementById("pstate");
  var NAMES = ["", "Step 1 · organizer filled (init)", "Step 2 · dose b66469f taken before the turn", "Step 3 · agent acting up: a.txt changed, untracked.md gone, new.py added", "Step 4 · pill given: 3 files restored, new.py kept", "Step 5 · git: no interactions"];
  var PH = ["", "calm", "calm", "sick", "well", "well"];
  function setStep(n) {
    if (!panel || panel.getAttribute("data-step") === String(n)) return;
    panel.setAttribute("data-step", n);
    panel.setAttribute("data-phase", PH[n]);
    steps.forEach(function (s) { s.classList.toggle("on", s.getAttribute("data-step") === String(n)); });
    if (pstate) pstate.textContent = NAMES[n];
  }
  if (panel && steps.length) {
    panel.setAttribute("data-phase", "calm");
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

  /* Dispense → Taken ✓ */
  document.querySelectorAll("[data-copy]").forEach(function (b) {
    b.addEventListener("click", function () {
      var el = document.querySelector(b.getAttribute("data-copy"));
      if (!el || !navigator.clipboard) return;
      navigator.clipboard.writeText(el.textContent).then(function () {
        b.classList.add("done"); b.textContent = "Taken ✓";
        setTimeout(function () { b.classList.remove("done"); b.textContent = "Dispense"; }, 1500);
      });
    });
  });
})();
