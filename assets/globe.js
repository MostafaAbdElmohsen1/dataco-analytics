/* globe.js - dependency-free rotating globe with hover detail.
   Survives Dash page navigation: a watcher keeps looking for a fresh
   #globe-data host and stops the render loop when one is removed. */
(function () {
  var ENC = "-76_-144_111111111111111111d111111111111111111111111111111111111111111111~-72_-100_72e11111111111111111111111111111111111111111111~-68_48_111114111111111111111~-64_-60_~-52_-72_~-48_-72_1~-44_-72_1Y~-40_-72_11Y~-36_-72_111O11~-32_-68_1111i11m11121111~-28_-68_1111h1111l111111111~-24_-68_11111g11113i11111111~-20_-68_111111f11114i1111111~-16_-72_11111111d11111112k112~-12_-76_111111111e111111o~-8_-76_1111111111d11111j72~-4_-80_1111111111d111111h4411~0_-80_1111111g1111111f3112~4_-76_111111g11111111i~8_-76_1111c111111111111111856~12_-84_3e11111111111111971~16_-96_1j1111111111111211615113~20_-104_133f11111111111112111511311~24_-104_1m11111111111211113111111111111~28_-108_11m111111111111111111111111111111111~32_-116_11111111j11111213111111111111111111111~36_-120_11111111111k1811111111111111111111221~40_-124_111111111111h11411111111211111111111111124~44_-124_1111111111111i1111111312111111111111111111113~48_-124_111111111111113d11111111111111111111111111111111111~52_-124_1111111111211111c112111111111111111111111111111111111~56_-160_7111111111113111f43111111111111111111111111111151~60_-164_1141111111111151k11221111111111111111111111111111113~64_-160_11111111111111111231516811111111111111111111111111111111111111111~68_-164_111111111111213221141111d11111131111111111111111111111111111111~72_-124_213311161111111j52111111111111311~76_-116_22281111111111k1811117~80_-96_111111211111111111911i";
  var D = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";

  var land = [];
  ENC.split("~").forEach(function (row) {
    var q = row.split("_"), lat = +q[0], lon = +q[1], ds = q[2] || "";
    land.push([lat, lon]);
    for (var i = 0; i < ds.length; i++) { lon += D.indexOf(ds[i]) * 4; land.push([lat, lon]); }
  });

  var ocean = [];
  for (var i = 0; i < 30; i++) {
    var la = -84 + i * 6, n = Math.max(4, Math.round(30 * Math.cos(la * Math.PI / 180)));
    for (var j = 0; j < n; j++) ocean.push([la, -180 + j * (360 / n)]);
  }

  var SPIN_MS = 75000;   /* one full turn - slow enough to read labels */
  var LEG_MS  = 4200;    /* time the shipment spends on one leg */

  function v3(lat, lon) {
    var a = lat * Math.PI / 180, o = lon * Math.PI / 180;
    return [Math.cos(a) * Math.sin(o), Math.sin(a), Math.cos(a) * Math.cos(o)];
  }

  function fmt(v) {
    if (v >= 1e6) return "$" + (v / 1e6).toFixed(2) + "M";
    if (v >= 1e3) return "$" + (v / 1e3).toFixed(1) + "K";
    return "$" + Math.round(v);
  }

  function parsePoints(host) {
    var out = [];
    (host.getAttribute("data-points") || "").split("|").forEach(function (p) {
      var f = p.split("~");
      if (f.length < 4) return;
      out.push({
        name: f[0], lat: +f[1], lon: +f[2], w: +f[3],
        rev: f[4] ? +f[4] : null, sx: 0, sy: 0, sz: -1, sr: 0
      });
    });
    return out;
  }

  function start(host) {
    var cv = document.createElement("canvas");
    cv.className = "globe-canvas";
    host.appendChild(cv);

    var tip = document.createElement("div");
    tip.className = "globe-tip";
    tip.style.display = "none";
    host.appendChild(tip);

    var ctx = cv.getContext("2d");
    var pts = parsePoints(host);
    var TILT = 22 * Math.PI / 180;
    var W = 0, H = 0, cx = 0, cy = 0, R = 0;
    var mouse = null, hovered = null, paused = false;

    function resize() {
      var dpr = window.devicePixelRatio || 1;
      var r = host.getBoundingClientRect();
      W = Math.max(280, r.width);
      H = Math.max(280, r.height || 440);
      cv.width = W * dpr; cv.height = H * dpr;
      cv.style.width = W + "px"; cv.style.height = H + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      cx = W / 2; cy = H / 2; R = Math.min(W, H) * 0.42;
    }
    resize();

    var onResize = function () { resize(); };
    window.addEventListener("resize", onResize);

    cv.addEventListener("mousemove", function (e) {
      var r = cv.getBoundingClientRect();
      mouse = [e.clientX - r.left, e.clientY - r.top];
    });
    cv.addEventListener("mouseleave", function () {
      mouse = null; hovered = null; paused = false;
      tip.style.display = "none";
      cv.style.cursor = "default";
    });

    function proj(lat, lon, spin, lift) {
      var v = v3(lat, lon), s = lift || 1;
      var x = v[0] * Math.cos(spin) - v[2] * Math.sin(spin);
      var z = v[0] * Math.sin(spin) + v[2] * Math.cos(spin);
      var y = v[1];
      var yy = Math.cos(TILT) * y - Math.sin(TILT) * z;
      var zz = Math.sin(TILT) * y + Math.cos(TILT) * z;
      return [cx + x * R * s, cy - yy * R * s, zz];
    }

    var legs = [];
    for (var k = 0; k < pts.length; k++) legs.push([k, (k + 1) % pts.length]);

    function arcPoints(a, b, spin) {
      var A = v3(a.lat, a.lon), B = v3(b.lat, b.lon);
      var dot = Math.max(-1, Math.min(1, A[0]*B[0] + A[1]*B[1] + A[2]*B[2]));
      var om = Math.acos(dot), so = Math.sin(om), out = [];
      for (var s = 0; s <= 40; s++) {
        var t = s / 40;
        var w1 = so ? Math.sin((1 - t) * om) / so : 1 - t;
        var w2 = so ? Math.sin(t * om) / so : t;
        var v = [A[0]*w1 + B[0]*w2, A[1]*w1 + B[1]*w2, A[2]*w1 + B[2]*w2];
        var m = Math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2]) || 1;
        out.push(proj(
          Math.asin(v[1] / m) * 180 / Math.PI,
          Math.atan2(v[0] / m, v[2] / m) * 180 / Math.PI,
          spin, 1 + 0.17 * Math.sin(Math.PI * t)
        ));
      }
      return out;
    }

    var t0 = performance.now();
    var clock = 0, last = t0, alive = true;

    function frame(now) {
      if (!host.isConnected) {                /* page navigated away */
        alive = false;
        window.removeEventListener("resize", onResize);
        return;
      }
      var dt = now - last; last = now;
      if (!paused) clock += dt;
      var spin = (clock / SPIN_MS) * Math.PI * 2;

      ctx.clearRect(0, 0, W, H);

      ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2);
      ctx.fillStyle = "#0d0a1a"; ctx.fill();
      ctx.strokeStyle = "rgba(255,0,128,.20)"; ctx.lineWidth = 1; ctx.stroke();

      ctx.fillStyle = "rgba(122,102,150,.24)";
      for (var i = 0; i < ocean.length; i++) {
        var p = proj(ocean[i][0], ocean[i][1], spin);
        if (p[2] < 0.04) continue;
        ctx.beginPath(); ctx.arc(p[0], p[1], 1.0, 0, Math.PI * 2); ctx.fill();
      }

      for (var k2 = 0; k2 < land.length; k2++) {
        var q = proj(land[k2][0], land[k2][1], spin);
        if (q[2] < 0.05) continue;
        var d = q[2];
        ctx.fillStyle = d > 0.72 ? "rgba(238,232,246,.88)"
                      : d > 0.44 ? "rgba(177,74,237,.70)"
                                 : "rgba(121,40,202,.50)";
        ctx.beginPath();
        ctx.arc(q[0], q[1], d > 0.72 ? 1.8 : d > 0.44 ? 1.6 : 1.35, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.lineWidth = 0.9;
      ctx.strokeStyle = "rgba(0,229,160,.14)";
      for (var g = 0; g < legs.length; g++) {
        var ap = arcPoints(pts[legs[g][0]], pts[legs[g][1]], spin);
        ctx.beginPath();
        var pen = false;
        for (var s3 = 0; s3 < ap.length; s3++) {
          if (ap[s3][2] < 0.02) { pen = false; continue; }
          if (!pen) { ctx.moveTo(ap[s3][0], ap[s3][1]); pen = true; }
          else ctx.lineTo(ap[s3][0], ap[s3][1]);
        }
        ctx.stroke();
      }

      var arriving = -1, arrive = 0;
      if (legs.length) {
        var total = legs.length * LEG_MS;
        var el = clock % total;
        var li = Math.floor(el / LEG_MS);
        var lt = (el % LEG_MS) / LEG_MS;
        var ap2 = arcPoints(pts[legs[li][0]], pts[legs[li][1]], spin);

        ctx.strokeStyle = "rgba(0,229,160,.5)"; ctx.lineWidth = 1.5;
        ctx.beginPath();
        var pen2 = false;
        for (var s4 = 0; s4 < ap2.length; s4++) {
          if (ap2[s4][2] < 0.02) { pen2 = false; continue; }
          if (!pen2) { ctx.moveTo(ap2[s4][0], ap2[s4][1]); pen2 = true; }
          else ctx.lineTo(ap2[s4][0], ap2[s4][1]);
        }
        ctx.stroke();

        var idx = Math.round(lt * 40);
        for (var b = 0; b < 10; b++) {
          var ii = idx - b;
          if (ii < 0 || ii > 40 || ap2[ii][2] < 0.02) continue;
          ctx.fillStyle = "rgba(0,229,160," + (0.95 - b * 0.09).toFixed(2) + ")";
          ctx.beginPath();
          ctx.arc(ap2[ii][0], ap2[ii][1], 3.4 - b * 0.26, 0, Math.PI * 2);
          ctx.fill();
        }
        if (lt > 0.82) { arriving = legs[li][1]; arrive = (lt - 0.82) / 0.18; }
      }

      /* bubbles */
      hovered = null;
      for (var m2 = 0; m2 < pts.length; m2++) {
        var pt = pts[m2];
        var pp = proj(pt.lat, pt.lon, spin);
        pt.sx = pp[0]; pt.sy = pp[1]; pt.sz = pp[2];
        if (pp[2] < 0.09) { pt.sr = 0; continue; }

        var scale = 0.55 + pp[2] * 0.55;
        var rr = (5 + pt.w * 20) * scale;
        pt.sr = rr;

        var isHover = mouse &&
          Math.hypot(mouse[0] - pp[0], mouse[1] - pp[1]) < Math.max(rr + 6, 13);
        if (isHover) hovered = pt;

        var boost = (m2 === arriving) ? (1 + Math.sin(arrive * Math.PI) * 1.1) : 1;

        ctx.fillStyle = (m2 === arriving)
          ? "rgba(0,229,160," + (0.30 * boost).toFixed(2) + ")"
          : "rgba(255,0,128,.18)";
        ctx.beginPath(); ctx.arc(pp[0], pp[1], rr * 2.1 * boost, 0, Math.PI * 2); ctx.fill();

        ctx.fillStyle = isHover ? "rgba(245,240,250,.98)"
                      : (m2 === arriving) ? "rgba(0,229,160,.95)"
                                          : "rgba(255,0,128,.92)";
        ctx.beginPath(); ctx.arc(pp[0], pp[1], rr * (isHover ? 1.25 : 1), 0, Math.PI * 2);
        ctx.fill();

        if (pp[2] > 0.4 && (rr > 6 || m2 === arriving || isHover)) {
          ctx.font = (isHover ? 600 + " " : "") +
                     Math.max(11, Math.min(15, rr * 1.05)) +
                     "px 'Segoe UI', Arial, sans-serif";
          ctx.fillStyle = isHover
            ? "rgba(245,240,250,1)"
            : "rgba(245,240,250," + (0.30 + pp[2] * 0.6).toFixed(2) + ")";
          ctx.textAlign = "left"; ctx.textBaseline = "middle";
          ctx.fillText(pt.name, pp[0] + rr + 7, pp[1]);
        }
      }

      /* tooltip + pause on hover */
      paused = !!hovered;
      if (hovered) {
        cv.style.cursor = "pointer";
        tip.innerHTML =
          '<div class="gt-name">' + hovered.name + '</div>' +
          '<div class="gt-val">' + (hovered.rev !== null ? fmt(hovered.rev) : "") + '</div>' +
          '<div class="gt-sub">' + (hovered.w * 100).toFixed(1) +
          '% of the top country</div>';
        tip.style.display = "block";
        var tw = tip.offsetWidth, th = tip.offsetHeight;
        var tx = Math.min(Math.max(hovered.sx + 16, 8), W - tw - 8);
        var ty = Math.min(Math.max(hovered.sy - th / 2, 8), H - th - 8);
        tip.style.left = tx + "px";
        tip.style.top = ty + "px";
      } else {
        cv.style.cursor = "default";
        tip.style.display = "none";
      }

      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  /* keep watching - Dash replaces the DOM on every page change */
  function watch() {
    var host = document.getElementById("globe-data");
    if (host && !host.dataset.started) {
      host.dataset.started = "1";
      start(host);
    }
  }
  setInterval(watch, 250);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", watch);
  } else { watch(); }
})();
