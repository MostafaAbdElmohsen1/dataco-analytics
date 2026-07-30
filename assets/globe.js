/* globe.js - decorative draggable globe for the cover.
   Auto-rotates, and can be grabbed and spun in any direction with
   momentum. No library, no CDN, works offline. Survives Dash page
   navigation via a persistent watcher. */
(function () {
  var ENC = "-76_-144_111111111111111111d111111111111111111111111111111111111111111111~-72_-100_72e11111111111111111111111111111111111111111111~-68_48_111114111111111111111~-64_-60_~-52_-72_~-48_-72_1~-44_-72_1Y~-40_-72_11Y~-36_-72_111O11~-32_-68_1111i11m11121111~-28_-68_1111h1111l111111111~-24_-68_11111g11113i11111111~-20_-68_111111f11114i1111111~-16_-72_11111111d11111112k112~-12_-76_111111111e111111o~-8_-76_1111111111d11111j72~-4_-80_1111111111d111111h4411~0_-80_1111111g1111111f3112~4_-76_111111g11111111i~8_-76_1111c111111111111111856~12_-84_3e11111111111111971~16_-96_1j1111111111111211615113~20_-104_133f11111111111112111511311~24_-104_1m11111111111211113111111111111~28_-108_11m111111111111111111111111111111111~32_-116_11111111j11111213111111111111111111111~36_-120_11111111111k1811111111111111111111221~40_-124_111111111111h11411111111211111111111111124~44_-124_1111111111111i1111111312111111111111111111113~48_-124_111111111111113d11111111111111111111111111111111111~52_-124_1111111111211111c112111111111111111111111111111111111~56_-160_7111111111113111f43111111111111111111111111111151~60_-164_1141111111111151k11221111111111111111111111111111113~64_-160_11111111111111111231516811111111111111111111111111111111111111111~68_-164_111111111111213221141111d11111131111111111111111111111111111111~72_-124_213311161111111j52111111111111311~76_-116_22281111111111k1811117~80_-96_111111211111111111911i";
  var D = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";

  var land = [];
  ENC.split("~").forEach(function (row) {
    var q = row.split("_"), lat = +q[0], lon = +q[1], ds = q[2] || "";
    land.push([lat, lon]);
    for (var i = 0; i < ds.length; i++) { lon += D.indexOf(ds[i]) * 4; land.push([lat, lon]); }
  });

  var grid = [];
  for (var i = 0; i < 31; i++) {
    var la = -84 + i * 5.6;
    var n = Math.max(4, Math.round(34 * Math.cos(la * Math.PI / 180)));
    for (var j = 0; j < n; j++) grid.push([la, -180 + j * (360 / n)]);
  }

  function v3(lat, lon) {
    var a = lat * Math.PI / 180, o = lon * Math.PI / 180;
    return [Math.cos(a) * Math.sin(o), Math.sin(a), Math.cos(a) * Math.cos(o)];
  }

  function start(host) {
    var cv = document.createElement("canvas");
    cv.className = "globe-canvas";
    host.appendChild(cv);
    var ctx = cv.getContext("2d");

    var W = 0, H = 0, cx = 0, cy = 0, R = 0;
    function resize() {
      var dpr = window.devicePixelRatio || 1;
      var r = host.getBoundingClientRect();
      W = Math.max(260, r.width);
      H = Math.max(260, r.height || 520);
      cv.width = W * dpr; cv.height = H * dpr;
      cv.style.width = W + "px"; cv.style.height = H + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      cx = W / 2; cy = H / 2; R = Math.min(W, H) * 0.415;
    }
    resize();
    var onResize = function () { resize(); };
    window.addEventListener("resize", onResize);

    /* --- rotation state --------------------------------------------- */
    var yaw = 0, pitch = 20 * Math.PI / 180;
    var vYaw = 0, vPitch = 0;
    var AUTO = (Math.PI * 2) / 64000;      /* radians per ms: 64s a turn */
    var dragging = false, lastX = 0, lastY = 0, lastT = 0, moved = false;

    function down(e) {
      dragging = true; moved = false;
      var p = e.touches ? e.touches[0] : e;
      lastX = p.clientX; lastY = p.clientY; lastT = performance.now();
      vYaw = 0; vPitch = 0;
      host.classList.add("is-grabbing");
    }
    function move(e) {
      if (!dragging) return;
      var p = e.touches ? e.touches[0] : e;
      var now = performance.now();
      var dx = p.clientX - lastX, dy = p.clientY - lastY;
      var dt = Math.max(1, now - lastT);

      yaw += dx * 0.0062;
      pitch = Math.max(-1.15, Math.min(1.15, pitch + dy * 0.0052));

      vYaw = (dx * 0.0062) / dt;
      vPitch = (dy * 0.0052) / dt;

      lastX = p.clientX; lastY = p.clientY; lastT = now;
      if (Math.abs(dx) + Math.abs(dy) > 2) moved = true;
      if (e.cancelable) e.preventDefault();
    }
    function up() {
      dragging = false;
      host.classList.remove("is-grabbing");
    }

    host.addEventListener("mousedown", down);
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    host.addEventListener("touchstart", down, { passive: true });
    host.addEventListener("touchmove", move, { passive: false });
    host.addEventListener("touchend", up);

    function proj(lat, lon) {
      var v = v3(lat, lon);
      var x = v[0] * Math.cos(yaw) - v[2] * Math.sin(yaw);
      var z = v[0] * Math.sin(yaw) + v[2] * Math.cos(yaw);
      var y = v[1];
      var yy = Math.cos(pitch) * y - Math.sin(pitch) * z;
      var zz = Math.sin(pitch) * y + Math.cos(pitch) * z;
      return [cx + x * R, cy - yy * R, zz];
    }

    var last = performance.now();

    function frame(now) {
      if (!host.isConnected) {
        window.removeEventListener("resize", onResize);
        window.removeEventListener("mousemove", move);
        window.removeEventListener("mouseup", up);
        return;
      }
      var dt = Math.min(48, now - last); last = now;

      if (dragging) {
        /* controlled by the pointer */
      } else {
        /* momentum, then settle back into the idle drift */
        yaw += vYaw * dt;
        pitch = Math.max(-1.15, Math.min(1.15, pitch + vPitch * dt));
        vYaw *= Math.pow(0.94, dt / 16);
        vPitch *= Math.pow(0.94, dt / 16);
        if (Math.abs(vYaw) < AUTO) vYaw = 0;
        if (Math.abs(vPitch) < 1e-6) vPitch = 0;
        yaw += AUTO * dt;
      }

      ctx.clearRect(0, 0, W, H);

      /* soft halo so the sphere sits inside the page, not on top of it */
      var g = ctx.createRadialGradient(cx, cy, R * 0.55, cx, cy, R * 1.5);
      g.addColorStop(0, "rgba(255,0,128,.10)");
      g.addColorStop(0.55, "rgba(121,40,202,.06)");
      g.addColorStop(1, "rgba(11,6,20,0)");
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(cx, cy, R * 1.5, 0, Math.PI * 2); ctx.fill();

      ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2);
      ctx.strokeStyle = "rgba(255,0,128,.14)"; ctx.lineWidth = 1; ctx.stroke();

      /* graticule - faint, gives the sphere its shape */
      ctx.fillStyle = "rgba(126,105,158,.22)";
      for (var i2 = 0; i2 < grid.length; i2++) {
        var p = proj(grid[i2][0], grid[i2][1]);
        if (p[2] < 0.02) continue;
        ctx.beginPath(); ctx.arc(p[0], p[1], 0.95, 0, Math.PI * 2); ctx.fill();
      }

      /* land */
      for (var k = 0; k < land.length; k++) {
        var q = proj(land[k][0], land[k][1]);
        if (q[2] < 0.04) continue;
        var d = q[2];
        ctx.fillStyle = d > 0.72 ? "rgba(240,234,248,.80)"
                      : d > 0.44 ? "rgba(255,77,157,.68)"
                                 : "rgba(150,74,220,.46)";
        ctx.beginPath();
        ctx.arc(q[0], q[1], d > 0.72 ? 1.85 : d > 0.44 ? 1.6 : 1.3, 0, Math.PI * 2);
        ctx.fill();
      }

      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  function watch() {
    var host = document.getElementById("cover-globe");
    if (host && !host.dataset.started) { host.dataset.started = "1"; start(host); }
  }
  setInterval(watch, 250);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", watch);
  } else { watch(); }
})();
