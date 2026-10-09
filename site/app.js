(function () {
  "use strict";
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  /* copy buttons */
  $$(".copy").forEach(function (b) {
    b.addEventListener("click", function () {
      var el = $(b.getAttribute("data-copy"));
      if (!el) return;
      var t = el.textContent;
      var done = function () { b.textContent = "copied"; b.classList.add("done"); setTimeout(function () { b.textContent = "copy"; b.classList.remove("done"); }, 1400); };
      if (navigator.clipboard) navigator.clipboard.writeText(t).then(done, done); else done();
    });
  });

  /* hero deck: snap -> agent damage -> one-step restore, git row never moves */
  var deck = $("#deck");
  if (deck) {
    var files = {}; $$("#files li").forEach(function (li) { files[li.getAttribute("data-f")] = li; });
    var head = $("#playhead"), span = $("#agentspan"), cmd = $("#cmd"), tc = $("#tc"), git = $("#gitrow");
    var ck = [$("#ck1"), $("#ck2"), $("#ck3")];
    var timers = [], running = false;
    var P = '<span class="p">$</span> ';
    function tag(f, cls, text) {
      var li = files[f]; li.classList.remove("saved", "mod", "del", "new", "back", "kept");
      if (cls) li.classList.add(cls);
      li.querySelector(".tag").textContent = text || "";
    }
    function at(ms, fn) { timers.push(setTimeout(fn, ms)); }
    function clear() { timers.forEach(clearTimeout); timers = []; }
    function reset() {
      ["readme", "app", "utils", "notes", "scratch"].forEach(function (f) { tag(f, "", ""); });
      ck.forEach(function (c) { c.classList.remove("in", "target"); });
      head.classList.remove("rewind"); head.style.transition = "none"; head.style.left = "4%";
      span.style.transition = "none"; span.style.width = "0"; span.style.opacity = "1";
      git.classList.remove("pulse");
      cmd.innerHTML = P + 'agentckpt snap -m "before agent"'; tc.textContent = "T+00:00";
      void head.offsetWidth; head.style.transition = ""; span.style.transition = "";
    }
    function snapState() {
      head.style.transition = "left .5s var(--ease)"; head.style.left = "14%";
      ck[0].classList.add("in");
      ["readme", "app", "utils", "notes"].forEach(function (f) { tag(f, "saved", "◆ saved"); });
      tc.textContent = "T+00:01";
    }
    function agentState() {
      ["readme", "app", "utils", "notes"].forEach(function (f) { tag(f, "", ""); });
      cmd.innerHTML = '<span style="color:var(--agent)">● agent turn</span> <span style="color:var(--mut)">editing…</span>';
      head.style.transition = ""; head.style.left = "74%"; span.style.width = "60%"; tc.textContent = "T+04:12";
    }
    function restoreCmd() {
      cmd.innerHTML = P + "agentckpt restore b66469f --force"; tc.textContent = "T+04:20";
      head.classList.add("rewind"); head.style.left = "14%"; ck[0].classList.add("target"); span.style.opacity = ".3";
    }
    function restored() {
      tag("readme", "", "= unchanged");
      tag("app", "back", "↺ restored"); tag("utils", "back", "↺ restored"); tag("notes", "back", "↺ restored");
      tag("scratch", "kept", "new · left in place");
      git.classList.add("pulse");
    }
    function finalState() {
      reset(); ck.forEach(function (c) { c.classList.add("in"); }); ck[0].classList.add("target");
      head.style.left = "14%"; span.style.width = "60%"; span.style.opacity = ".3";
      cmd.innerHTML = P + "agentckpt restore b66469f --force"; tc.textContent = "T+04:20";
      restored();
    }
    function run() {
      clear(); reset(); running = true;
      at(500, snapState);
      at(2000, agentState);
      at(2500, function () { tag("app", "mod", "M modified"); });
      at(3000, function () { ck[1].classList.add("in"); });
      at(3300, function () { tag("utils", "del", "deleted"); });
      at(3800, function () { tag("notes", "del", "deleted"); });
      at(4200, function () { tag("scratch", "new", "+ new"); ck[2].classList.add("in"); });
      at(5300, restoreCmd);
      at(6300, restored);
      at(11000, run);
    }
    function stop() { clear(); running = false; }
    if (reduce) { finalState(); }
    else if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (es) {
        es.forEach(function (e) { if (e.isIntersecting && !running) run(); else if (!e.isIntersecting && running) stop(); });
      }, { threshold: 0.2 }).observe(deck);
      document.addEventListener("visibilitychange", function () { if (document.hidden) stop(); });
      deck.addEventListener("click", run);
    } else { run(); }
  }

  /* how it works: scroll- or tap-driven state */
  var stage = $("#stage"), steps = $$(".step");
  if (stage && steps.length) {
    var treeS = $("#tree-state"), shadowS = $("#shadow-state"), dias = $("#dias");
    var model = {
      1: ["a.txt · untracked.md", "init commit", 0],
      2: ["3 files incl. untracked", "1 snapshot", 1],
      3: ["a.txt M · untracked.md ✕ · new.py +", "1 snapshot + auto", 2],
      4: ["a.txt, untracked.md back · new.py kept", "restore from b66469f", 2],
      5: ["back to before the agent", "2 snapshots", 2]
    };
    var cur = 0;
    function setStep(n) {
      if (n === cur) return; cur = n;
      stage.setAttribute("data-step", n);
      steps.forEach(function (s) { s.classList.toggle("active", +s.getAttribute("data-step") === n); });
      var m = model[n]; if (!m) return;
      treeS.textContent = m[0]; shadowS.textContent = m[1];
      if (dias.children.length !== m[2]) { dias.innerHTML = ""; for (var i = 0; i < m[2]; i++) dias.appendChild(document.createElement("i")); }
    }
    setStep(1);
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (es) {
        es.forEach(function (e) { if (e.isIntersecting) setStep(+e.target.getAttribute("data-step")); });
      }, { rootMargin: "-45% 0px -45% 0px" });
      steps.forEach(function (s) { io.observe(s); });
    }
    steps.forEach(function (s) {
      var go = function () { setStep(+s.getAttribute("data-step")); };
      s.addEventListener("click", go);
      s.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
    });
  }
})();
