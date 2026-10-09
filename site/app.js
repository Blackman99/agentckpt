(function () {
  "use strict";
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var hasIO = "IntersectionObserver" in window;

  /* copy buttons */
  $$(".copy").forEach(function (b) {
    b.addEventListener("click", function () {
      var el = $(b.getAttribute("data-copy")); if (!el) return;
      var done = function () { b.textContent = "copied!"; b.classList.add("done"); setTimeout(function () { b.textContent = "copy"; b.classList.remove("done"); }, 1400); };
      if (navigator.clipboard) navigator.clipboard.writeText(el.textContent).then(done, done); else done();
    });
  });

  /* grease pencil marks that draw once when seen */
  var draws = $$("[data-draw]");
  if (reduce || !hasIO) draws.forEach(function (d) { d.classList.add("drawn"); });
  else {
    var dio = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { setTimeout(function () { e.target.classList.add("drawn"); }, 250); dio.unobserve(e.target); } });
    }, { threshold: 0.6 });
    draws.forEach(function (d) { dio.observe(d); });
  }

  /* hero: the work print runs through the gate; the negative never moves */
  var reel = $("#reel"), strip = $("#strip");
  if (reel && strip) {
    var frames = $$(".strip > .fr"), f2 = $("#f2"), f5 = $("#f5"), rest = $("#rest"), unt = $("#untouched");
    var fc = $("#fc"), cmd = $("#cmd"), cap = $("#cap"), lamp = $(".lamp");
    var cur = 1, timers = [], running = false;
    var CAP = {
      1: "Frame 1: <code>agentckpt init</code> sets up a private store in <code>.agentckpt/</code>.",
      2: "Frame 2: <code>snap</code> circles this frame. Tracked and untracked files go into the shadow store.",
      3: "Frame 3: agent turn 1 edits <code>src/app.py</code>.",
      4: "Frame 4: turn 2 deletes <code>src/utils.py</code> and the untracked <code>notes.md</code>.",
      5: "Frame 5: turn 3 adds <code>scratch.py</code> and breaks the build. NG.",
      6: "Rewinding to the circled frame…",
      7: "Back on frame 2: <code>utils.py</code> and untracked <code>notes.md</code> are restored. <code>scratch.py</code> stays (restore never deletes). The negative didn't move."
    };
    function pad(n) { return (n < 10 ? "0" : "") + n; }
    function place(i, mode) {
      cur = i;
      var fw = frames[0].getBoundingClientRect().width;
      var x = Math.round(reel.clientWidth / 2 - (i + 0.5) * fw);
      strip.style.transition = mode === "rewind" ? "transform 1.1s cubic-bezier(.65,0,.35,1)" : mode === "cut" ? "none" : "transform .75s cubic-bezier(.4,0,.2,1)";
      strip.style.transform = "translateX(" + x + "px)";
      fc.textContent = pad(i);
    }
    function at(ms, fn) { timers.push(setTimeout(fn, ms)); }
    function clear() { timers.forEach(clearTimeout); timers = []; }
    function noAnim(els, fn) { els.forEach(function (e) { e.style.transition = "none"; $$(".gp", e).forEach(function (g) { g.style.transition = "none"; }); }); fn(); void strip.offsetWidth; els.forEach(function (e) { e.style.transition = ""; $$(".gp", e).forEach(function (g) { g.style.transition = ""; }); }); }
    function reset() {
      noAnim([f2, f5, rest, unt], function () { [f2, f5, rest, unt].forEach(function (e) { e.classList.remove("on"); }); });
      lamp.classList.remove("run");
      place(1, "cut"); cmd.textContent = "$ agentckpt init"; cap.innerHTML = CAP[1];
    }
    function finalState() {
      [f2, f5, rest, unt].forEach(function (e) { e.classList.add("on"); });
      place(2, "cut"); cmd.textContent = "$ agentckpt restore b66469f --force"; cap.innerHTML = CAP[7];
    }
    function run() {
      clear(); reset(); running = true;
      at(1300, function () { place(2); cmd.textContent = '$ agentckpt snap -m "before agent"'; cap.innerHTML = CAP[2]; });
      at(2000, function () { f2.classList.add("on"); });
      at(3400, function () { lamp.classList.add("run"); place(3); cmd.textContent = "● agent running: turn 1"; cap.innerHTML = CAP[3]; });
      at(4800, function () { place(4); cmd.textContent = "● agent running: turn 2"; cap.innerHTML = CAP[4]; });
      at(6200, function () { place(5); cmd.textContent = "● agent running: turn 3"; cap.innerHTML = CAP[5]; });
      at(6900, function () { f5.classList.add("on"); lamp.classList.remove("run"); });
      at(8300, function () { cmd.textContent = "$ agentckpt restore b66469f --force"; cap.innerHTML = CAP[6]; place(2, "rewind"); fc.textContent = "05"; [4, 3, 2].forEach(function (n, k) { at(300 + k * 300, function () { fc.textContent = pad(n); }); }); });
      at(9600, function () { rest.classList.add("on"); unt.classList.add("on"); cap.innerHTML = CAP[7]; });
      at(15000, run);
    }
    function stop() { clear(); running = false; }
    window.addEventListener("resize", function () { place(cur, "cut"); });
    if (reduce) finalState();
    else if (hasIO) {
      place(1, "cut");
      new IntersectionObserver(function (es) {
        es.forEach(function (e) { if (e.isIntersecting && !running) run(); else if (!e.isIntersecting && running) { stop(); } });
      }, { threshold: 0.15 }).observe(reel);
      document.addEventListener("visibilitychange", function () { if (document.hidden && running) stop(); });
      reel.addEventListener("click", run);
    } else run();
  }

  /* EDL: the active row drives the viewer */
  var viewer = $("#viewer"), rows = $$(".row");
  if (viewer && rows.length) {
    var vfn = $("#vfn"), vstate = $("#vstate"), vdots = $("#vdots");
    var M = { 1: ["init", 0], 2: ["snap · b66469f", 1], 3: ["agent turn · NG", 2], 4: ["restored from b66469f", 2], 5: ["negative checked", 2] };
    var step = 0;
    function set(n) {
      if (n === step) return; step = n;
      viewer.setAttribute("data-step", n);
      rows.forEach(function (r) { var k = +r.getAttribute("data-step"); r.classList.toggle("active", k === n); r.classList.toggle("on", k <= n); });
      vfn.textContent = "00" + n; vstate.textContent = M[n][0];
      if (vdots.children.length !== M[n][1]) { vdots.innerHTML = ""; for (var i = 0; i < M[n][1]; i++) vdots.appendChild(document.createElement("i")); }
    }
    set(1);
    if (hasIO) {
      var rio = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) set(+e.target.getAttribute("data-step")); }); }, { rootMargin: "-45% 0px -45% 0px" });
      rows.forEach(function (r) { rio.observe(r); });
    }
    rows.forEach(function (r) {
      var go = function () { set(+r.getAttribute("data-step")); };
      r.addEventListener("click", go);
      r.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
    });
  }
})();
