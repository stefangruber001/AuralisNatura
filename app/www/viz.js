/* ============================================================
   Auralis Natura — data visualization kit
   Premium animated SVG. No libraries. Builders return HTML strings;
   call AN_VIZ.play(container) after inserting to run the entrance animations.
   ============================================================ */
(function () {
  "use strict";
  var uid = 0;
  function id() { return "v" + (++uid); }
  var C = {
    ink: "#281F16", forest: "#3D2719", clay: "#A8492A", clayd: "#8F3D22",
    gold: "#AD7A32", goldb: "#D6A84E", sage: "#927B4A", sageSoft: "#DAC79E",
    ok: "#3F7B5A", warn: "#B0553F", line: "rgba(61,39,25,.14)", cream: "#FBF6EB"
  };
  var SCALE_META = {
    energy:    { de: "Energie",   en: "Energy",    es: "Energía",   ico: "spark",  inv: false },
    sleep:     { de: "Schlaf",    en: "Sleep",     es: "Sueño",     ico: "moon",   inv: false },
    stress:    { de: "Stress",    en: "Stress",    es: "Estrés",    ico: "wave",   inv: true },
    digestion: { de: "Verdauung", en: "Digestion", es: "Digestión", ico: "leaf",   inv: false }
  };
  function label(k, lang) { var m = SCALE_META[k]; return m ? (m[lang] || m.de) : k; }
  // 1..5 → status color (stress inverse)
  function statusColor(k, v) {
    var good = SCALE_META[k] && SCALE_META[k].inv ? (6 - v) : v;
    return good >= 4 ? C.ok : good >= 3 ? C.gold : C.warn;
  }

  /* ---------- THE BLOOM (signature hero) ----------
     A 4-scale organic petal chart with the Balance score in the centre.
     Energy(top) · Sleep(right) · Digestion(bottom) · Stress(left, inverted). */
  function bloom(scales, score, lang, opts) {
    opts = opts || {};
    var keys = ["energy", "sleep", "digestion", "stress"];
    if (!scales || keys.some(function (k) { return scales[k] == null; })) return "";
    var W = 244, cx = W / 2, R = 84, gid = id(), cg = id();
    function ang(i) { return (-90 + i * 90) * Math.PI / 180; }
    function val01(k) { var v = SCALE_META[k].inv ? (6 - scales[k]) : scales[k]; return v / 5; }
    function vtx(i, rad) { var a = ang(i); return [cx + Math.cos(a) * rad, cx + Math.sin(a) * rad]; }
    // concentric circle hairlines (organic, not geometric diamonds)
    var grid = [0.25, 0.5, 0.75, 1].map(function (lv) {
      return '<circle cx="' + cx + '" cy="' + cx + '" r="' + (R * lv).toFixed(1) + '" fill="none" stroke="' + C.line + '" stroke-width=".75"/>';
    }).join("");
    // petal path through the 4 value-vertices, control points pushed well outward
    var v = keys.map(function (k, i) { return vtx(i, R * val01(k)); });
    function ctrl(a, b) { var mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2; return [cx + (mx - cx) * 1.34, cx + (my - cx) * 1.34]; }
    var d = "M" + v[0][0].toFixed(1) + " " + v[0][1].toFixed(1);
    for (var i = 0; i < 4; i++) { var a = v[i], b = v[(i + 1) % 4], c = ctrl(a, b); d += " Q" + c[0].toFixed(1) + " " + c[1].toFixed(1) + " " + b[0].toFixed(1) + " " + b[1].toFixed(1); }
    d += " Z";
    var dots = keys.map(function (k, i) { var p = vtx(i, R * val01(k)); return '<circle cx="' + p[0].toFixed(1) + '" cy="' + p[1].toFixed(1) + '" r="3.5" fill="' + statusColor(k, scales[k]) + '" stroke="' + C.cream + '" stroke-width="1.6"/>'; }).join("");
    var labels = opts.compact ? "" : keys.map(function (k, i) { var p = vtx(i, R + 15); var anch = Math.abs(p[0] - cx) < 6 ? "middle" : (p[0] > cx ? "start" : "end"); var dy = Math.abs(p[1] - cx) < 6 ? 4 : (p[1] > cx ? 11 : -2); return '<text x="' + p[0].toFixed(1) + '" y="' + (p[1] + dy).toFixed(1) + '" text-anchor="' + anch + '" class="viz-mono-lab">' + label(k, lang).toUpperCase() + '</text>'; }).join("");
    return '<div class="viz-bloom' + (opts.compact ? " viz-bloom--sm" : "") + '"><svg width="100%" height="' + W + '" viewBox="0 0 ' + W + ' ' + W + '" preserveAspectRatio="xMidYMid meet" style="max-width:' + (opts.compact ? 168 : W) + 'px;overflow:visible">' +
      '<defs><linearGradient id="' + gid + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="' + C.gold + '" stop-opacity=".34"/><stop offset="1" stop-color="' + C.sage + '" stop-opacity=".12"/></linearGradient>' +
      '<radialGradient id="' + cg + '" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="' + C.cream + '" stop-opacity=".95"/><stop offset=".72" stop-color="' + C.cream + '" stop-opacity=".78"/><stop offset="1" stop-color="' + C.cream + '" stop-opacity="0"/></radialGradient></defs>' +
      grid +
      '<path class="bloom-petal" d="' + d + '" fill="url(#' + gid + ')" stroke="' + C.forest + '" stroke-width="1.6" stroke-linejoin="round" style="transform-box:fill-box;transform-origin:center;transform:scale(.04);opacity:0;filter:drop-shadow(0 6px 14px rgba(61,39,25,.18))"/>' +
      '<g class="bloom-dots" style="opacity:0">' + dots + '</g>' +
      '<circle cx="' + cx + '" cy="' + cx + '" r="42" fill="url(#' + cg + ')"/>' +
      labels + '</svg>' +
      '<div class="viz-bloom-c"><span class="viz-bloom-n num" data-count="' + (score == null ? 0 : Math.round(score)) + '">0</span>' +
      (opts.compact ? "" : '<span class="viz-mono-lab">BALANCE</span>') + '</div></div>';
  }

  /* ---------- METRIC BARS (Ampel) ---------- */
  function bars(scales, lang) {
    var keys = ["energy", "sleep", "stress", "digestion"].filter(function (k) { return scales && scales[k] != null; });
    if (!keys.length) return "";
    return '<div class="viz-bars">' + keys.map(function (k) {
      var v = scales[k], col = statusColor(k, v), pct = v / 5 * 100;
      return '<div class="viz-bar"><span class="viz-bl">' + label(k, lang) + '</span>' +
        '<span class="viz-bt"><i class="viz-bf" style="background:linear-gradient(100deg,' + col + 'E6,' + col + ');box-shadow:inset 0 1px 0 rgba(255,255,255,.28)" data-w="' + pct + '"></i><i class="viz-tick"></i></span>' +
        '<span class="viz-bn num" style="color:' + col + '">' + v + '<small>/5</small></span></div>';
    }).join("") + '</div>';
  }

  /* ---------- HABIT STREAK CHECKLIST ---------- */
  function habits(list) {
    if (!list || !list.length) return "";
    return '<div class="viz-habits">' + list.map(function (h, i) {
      return '<button class="viz-habit" data-h="' + i + '"><span class="viz-hdot"></span><span>' + esc(h) + '</span></button>';
    }).join("") + '</div>';
  }

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

  /* ---------- PLAY: run entrance animations after insertion ---------- */
  function play(root) {
    if (!root) return;
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    // count-ups
    [].forEach.call(root.querySelectorAll("[data-count]"), function (el) {
      var target = +el.getAttribute("data-count") || 0;
      if (reduce || target === 0) { el.textContent = target; return; }
      var t0 = null, dur = 1000;
      function step(ts) { if (!t0) t0 = ts; var p = Math.min(1, (ts - t0) / dur); el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3))); if (p < 1) requestAnimationFrame(step); }
      requestAnimationFrame(step);
    });
    // bloom petal
    [].forEach.call(root.querySelectorAll(".bloom-petal"), function (el) {
      if (reduce) { el.style.transform = "scale(1)"; el.style.opacity = "1"; return; }
      requestAnimationFrame(function () { requestAnimationFrame(function () { el.style.transition = "transform .85s cubic-bezier(.34,1.35,.5,1),opacity .5s"; el.style.transform = "scale(1)"; el.style.opacity = "1"; }); });
    });
    [].forEach.call(root.querySelectorAll(".bloom-dots"), function (el) {
      if (reduce) { el.style.opacity = "1"; return; }
      setTimeout(function () { el.style.transition = "opacity .5s"; el.style.opacity = "1"; }, 560);
    });
    // bars
    [].forEach.call(root.querySelectorAll(".viz-bf"), function (el) {
      var w = el.getAttribute("data-w") + "%";
      if (reduce) { el.style.width = w; }
      else { el.style.width = "0"; requestAnimationFrame(function () { requestAnimationFrame(function () { el.style.transition = "width .9s cubic-bezier(.22,.8,.24,1)"; el.style.width = w; }); }); }
    });
  }

  window.AN_VIZ = { bloom: bloom, bars: bars, habits: habits, play: play, label: label };
})();
