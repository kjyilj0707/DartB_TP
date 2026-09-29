/* 음성 안내 엔진 — 브라우저(window.NavEngine)와 Node(require) 양쪽에서 같은 코드를 쓴다.
 *
 * 경로 규칙은 route_guidance.py와 같다.
 *   지표: A = 지나는 교차 지점 A 점수 합 / B = 경사 위험·계단 구간 길이 / C = 급한 전환 + 횡단 이벤트
 *   기준(mode)은 체크한 지표 문자열: "최단"(아무것도 안 고름), "A", "B", "C", "AB", "AC", "BC", "ABC"
 *   후보 경로: 비용 = 거리 + Σ λ_k·지표_k 로 λ 조합을 바꿔 가며 최단경로를 구한다(거리 ≤ 최단 × CAP).
 *   선택: 체크한 지표가 어느 것도 최단 경로보다 나빠지지 않는 후보 중, Σ(지표_k / 최단의 지표_k)가 가장 작은 것
 *         (= 줄어든 비율의 합이 가장 큰 것). 같으면 짧은 것. 지표 하나만 고르면 route_guidance.py와 같은 결과.
 * 안내 규칙
 *   회전: 경로 노드에서 방향이 25° 이상 바뀌면 안내. 50m 전 "50미터 앞에서 ○○", 15m 전 "곧 ○○"
 *   위험: 교차 지점·경사 구간 시작·구간 안 급한 전환을 경로 위 위치로 바꿔, 30m 앞에 오면 한 번 안내
 *   이탈: 경로에서 max(30m, GPS 정확도×2.5) 넘게 떨어진 위치가 5번 연속이면 "경로를 벗어났습니다" 후 재탐색
 *   이미 지나친 지점의 안내는 재생 직전에 버린다(isStale). 경로 요약은 출발 전 제자리에서 듣는 것으로 본다.
 *   도착: 문까지 15m 이내
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.NavEngine = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const CAP = 1.3;
  const LAMBDAS = [0, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 5000, 20000];   // 지표 하나일 때
  const GRID = { A: [0, 5, 20, 100, 500, 5000], B: [0, 0.5, 2, 5, 20, 200], C: [0, 5, 20, 100, 500, 5000] }; // 여러 개일 때
  const MODES = ["최단", "A", "B", "C", "AB", "AC", "BC", "ABC"];
  const METRIC = { A: "aSum", B: "bLen", C: "cEv" };
  const critOf = (mode) => (mode === "최단" || !mode ? [] : mode.split(""));
  const TURN_TEXT = "길이 크게 꺾이는 곳입니다.";
  const DIST_STEPS = [10, 20, 30, 50, 100, 150, 200, 300];
  const DEFAULTS = {
    hazardAhead: 30, maneuverFar: 50, maneuverNear: 15, offRouteM: 30, offRouteAcc: 2.5, offRouteCount: 5,
    arriveM: 15, snapMaxM: 150, mergeM: 15, freeRadius: 30, freeResetM: 60,
  };

  // ------------------------------------------------------------ 좌표 (학교 중심 기준 평면 근사, m)
  function makeProj(nodes) {
    let lon0 = 0, lat0 = 0;
    for (const [x, y] of nodes) { lon0 += x; lat0 += y; }
    lon0 /= nodes.length; lat0 /= nodes.length;
    const kx = Math.cos((lat0 * Math.PI) / 180) * 111320, ky = 110540;
    return {
      to: (lon, lat) => [(lon - lon0) * kx, (lat - lat0) * ky],
      from: (x, y) => [x / kx + lon0, y / ky + lat0],
    };
  }
  const hyp = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  const bearing = (a, b) => (Math.atan2(b[0] - a[0], b[1] - a[1]) * 180) / Math.PI; // 북 0°, 시계방향
  const angDiff = (a, b) => ((b - a + 540) % 360) - 180;

  function projectOnSeg(p, a, b) {
    const dx = b[0] - a[0], dy = b[1] - a[1];
    const L2 = dx * dx + dy * dy;
    let t = L2 > 0 ? ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2 : 0;
    t = Math.max(0, Math.min(1, t));
    const q = [a[0] + t * dx, a[1] + t * dy];
    return { t, q, d: hyp(p, q) };
  }

  // ------------------------------------------------------------ 그래프
  function Graph(data, clips) {
    this.data = data;
    this.clips = clips || {};
    this.proj = makeProj(data.nodes);
    this.nxy = data.nodes.map(([x, y]) => this.proj.to(x, y));
    this.exy = data.edges.map((e) => e.xy.map(([x, y]) => this.proj.to(x, y)));
    this.adj = data.nodes.map(() => []);
    data.edges.forEach((e, i) => {
      this.adj[e.u].push({ t: e.v, i, fwd: true });
      this.adj[e.v].push({ t: e.u, i, fwd: false });
    });
    this.cross = {};
    for (const k in data.cross) this.cross[+k] = data.cross[k];
    this.gateByNode = {};
    data.gates.forEach((g) => (this.gateByNode[g.node] = g.name));
    this.turnKey = keyOfText(this.clips, TURN_TEXT);
  }

  function keyOfText(clips, text) {
    for (const k in clips) if (clips[k] === text) return k;
    return null;
  }

  Graph.prototype.nearestNode = function (p) {
    let best = -1, bd = Infinity;
    this.nxy.forEach((q, i) => {
      if (!this.adj[i].length) return;
      const d = hyp(p, q);
      if (d < bd) { bd = d; best = i; }
    });
    return { node: best, d: bd };
  };

  /** lams = {A: λ, B: λ, C: λ} (없으면 0) */
  Graph.prototype.dijkstra = function (src, lams) {
    const la = lams.A || 0, lb = lams.B || 0, lc = lams.C || 0;
    const n = this.nxy.length;
    const dist = new Float64Array(n).fill(Infinity), prevN = new Int32Array(n).fill(-1), prevE = new Int32Array(n).fill(-1);
    dist[src] = 0;
    const heap = [[0, src]];
    const push = (x) => { heap.push(x); let i = heap.length - 1; while (i > 0) { const p = (i - 1) >> 1; if (heap[p][0] <= heap[i][0]) break; [heap[p], heap[i]] = [heap[i], heap[p]]; i = p; } };
    const pop = () => { const top = heap[0], last = heap.pop(); if (heap.length) { heap[0] = last; let i = 0; for (;;) { const l = 2 * i + 1, r = l + 1; let m = i; if (l < heap.length && heap[l][0] < heap[m][0]) m = l; if (r < heap.length && heap[r][0] < heap[m][0]) m = r; if (m === i) break; [heap[m], heap[i]] = [heap[i], heap[m]]; i = m; } } return top; };
    while (heap.length) {
      const [d, u] = pop();
      if (d > dist[u]) continue;
      for (const { t, i } of this.adj[u]) {
        const e = this.data.edges[i], c = this.cross[t];
        const nd = d + e.len + (la ? la * (c ? c.a : 0) : 0) + (lb ? lb * e.b : 0)
          + (lc ? lc * (e.turns.length + (c ? c.c : 0)) : 0);
        if (nd < dist[t]) { dist[t] = nd; prevN[t] = u; prevE[t] = i; push([nd, t]); }
      }
    }
    return { dist, prevN, prevE };
  };

  Graph.prototype.stats = function (nodes, edges) {
    let len = 0, bLen = 0, turns = 0, stairs = 0;
    edges.forEach(({ i }) => { const e = this.data.edges[i]; len += e.len; bLen += e.b; turns += e.turns.length; if (e.stairs) stairs++; });
    let aSum = 0, a3 = 0, cCross = 0, nCross = 0;
    nodes.slice(1).forEach((n) => { const c = this.cross[n]; if (!c) return; nCross++; aSum += c.a; cCross += c.c; if (c.araw !== null && c.araw >= 3) a3++; });
    return { len, aSum, a3, bLen, stairs, cEv: turns + cCross, nCross };
  };

  Graph.prototype.bestFor = function (src, targets, lams) {
    const { dist, prevN, prevE } = this.dijkstra(src, lams);
    let g = -1;
    targets.forEach((t) => { if (dist[t] < Infinity && (g < 0 || dist[t] < dist[g])) g = t; });
    if (g < 0) return null;
    const nodes = [g], edges = [];
    while (nodes[nodes.length - 1] !== src) {
      const n = nodes[nodes.length - 1];
      edges.push({ i: prevE[n], fwd: this.data.edges[prevE[n]].v === n });
      nodes.push(prevN[n]);
    }
    nodes.reverse(); edges.reverse();
    return { nodes, edges, stats: this.stats(nodes, edges), lams, gate: g };
  };

  /** 기준(mode)별 경로. targets 생략 시 모든 문. */
  Graph.prototype.route = function (src, mode, targets) {
    targets = targets || this.data.gates.map((g) => g.node);
    const crit = critOf(mode);
    const shortest = this.bestFor(src, targets, {});
    if (!shortest) return null;
    if (!crit.length) return Object.assign({}, shortest, { mode: "최단", crit, shortest });
    const limit = shortest.stats.len * CAP;
    const base = crit.map((k) => shortest.stats[METRIC[k]]);
    const score = (st) => {                      // 나빠지는 지표가 있으면 Infinity
      let sc = 0;
      for (let j = 0; j < crit.length; j++) {
        const v = st[METRIC[crit[j]]];
        if (v > base[j] + 1e-9) return Infinity;
        sc += base[j] > 0 ? v / base[j] : 0;
      }
      return sc;
    };
    // λ 조합: 지표 하나면 LAMBDAS, 여러 개면 GRID의 곱
    let combos = crit.length === 1 ? LAMBDAS.slice(1).map((l) => ({ [crit[0]]: l })) : [{}];
    if (crit.length > 1) crit.forEach((k) => { combos = combos.flatMap((c) => GRID[k].map((l) => Object.assign({}, c, { [k]: l }))); });
    let best = shortest, bestSc = score(shortest.stats);
    for (const lams of combos) {
      if (!Object.values(lams).some((v) => v > 0)) continue;
      const r = this.bestFor(src, targets, lams);
      if (!r || r.stats.len > limit + 1e-6) continue;
      const sc = score(r.stats);
      if (sc < bestSc - 1e-9 || (Math.abs(sc - bestSc) < 1e-9 && r.stats.len < best.stats.len)) { best = r; bestSc = sc; }
    }
    return Object.assign({}, best, { mode, crit, shortest });
  };

  // ------------------------------------------------------------ 경로 -> 선, 회전, 위험
  Graph.prototype.plan = function (r, opt) {
    opt = Object.assign({}, DEFAULTS, opt || {});
    const pts = [], cum = [], nodeAt = [];
    let s = 0;
    r.edges.forEach(({ i, fwd }, k) => {
      let xy = this.exy[i];
      if (!fwd) xy = xy.slice().reverse();
      if (k === 0) { pts.push(xy[0]); cum.push(0); }
      nodeAt.push(s);
      for (let j = 1; j < xy.length; j++) { s += hyp(xy[j - 1], xy[j]); pts.push(xy[j]); cum.push(s); }
    });
    nodeAt.push(s);
    if (!pts.length) { pts.push(this.nxy[r.nodes[0]]); cum.push(0); }   // 출발 노드 = 문 (길이 0 경로)
    const total = s;
    const at = (d) => { // 경로 위 거리 d의 좌표
      d = Math.max(0, Math.min(total, d));
      if (pts.length === 1) return pts[0].slice();
      let j = 1; while (j < cum.length - 1 && cum[j] < d) j++;
      const t = cum[j] > cum[j - 1] ? (d - cum[j - 1]) / (cum[j] - cum[j - 1]) : 0;
      return [pts[j - 1][0] + t * (pts[j][0] - pts[j - 1][0]), pts[j - 1][1] + t * (pts[j][1] - pts[j - 1][1])];
    };

    // 회전: 경로 노드 앞뒤 10m 방향 비교
    const maneuvers = [];
    for (let k = 1; k < r.nodes.length - 1; k++) {
      const d0 = nodeAt[k];
      const inB = bearing(at(d0 - 10), at(d0)), outB = bearing(at(d0), at(d0 + 10));
      const a = angDiff(inB, outB), abs = Math.abs(a);
      let key = null;
      if (abs >= 150) key = "uturn";
      else if (abs >= 60) key = a > 0 ? "turn_right" : "turn_left";
      else if (abs >= 25) key = a > 0 ? "slight_right" : "slight_left";
      if (key) maneuvers.push({ s: d0, key, angle: Math.round(a), node: r.nodes[k] });
    }

    // 위험: 교차 지점(출발 노드 제외), 경사·계단 구간 시작, 구간 안 급한 전환
    const hz = [];
    r.nodes.forEach((n, k) => { if (k > 0 && this.cross[n]) hz.push({ s: nodeAt[k], keys: [this.cross[n].ahead], kind: "횡단", node: n }); });
    const sev = (key) => { const t = this.clips[key] || ""; return t.includes("계단") ? 4 : t.includes("매우") ? 3 : t.includes("가파른") ? 2 : 1; };
    let run = null;
    r.edges.forEach(({ i, fwd }, k) => {
      const e = this.data.edges[i];
      if (e.hz) {
        if (!run) { run = { s: nodeAt[k], keys: [e.hz], kind: "경사" }; hz.push(run); }
        else if (sev(e.hz) > sev(run.keys[0])) run.keys = [e.hz];
      } else run = null;
      e.turns.forEach((t) => hz.push({ s: nodeAt[k] + (fwd ? t : e.len - t), keys: [this.turnKey], kind: "회전" }));
    });
    hz.sort((a, b) => a.s - b.s);
    const merged = [];
    hz.forEach((h) => {
      const last = merged[merged.length - 1];
      if (last && h.s - last.s <= opt.mergeM) { h.keys.forEach((k) => { if (!last.keys.includes(k)) last.keys.push(k); }); last.kind += "+" + h.kind; }
      else merged.push({ s: h.s, keys: h.keys.slice(), kind: h.kind });
    });
    return { route: r, pts, cum, total, maneuvers, hazards: merged, at };
  };

  function bucket(v, steps) { let b = steps[0]; steps.forEach((x) => { if (Math.abs(x - v) < Math.abs(b - v)) b = x; }); return b; }
  const KOR = [1, 2, 3, 4, 5, 6, 7, 8];

  /** 경로 시작 안내 조각: 기준, 목적지, 총 거리, 최단 대비 얻는 것과 잃는 것. */
  Graph.prototype.summaryKeys = function (r) {
    const keys = ["start", "mode_" + r.mode, "dest_" + this.gateByNode[r.gate]];
    keys.push("total_" + Math.min(2000, Math.max(100, Math.round(r.stats.len / 100) * 100)));
    if (!r.crit.length) return keys;
    const s0 = r.shortest.stats, s1 = r.stats;
    if (r.crit.every((k) => s1[METRIC[k]] >= s0[METRIC[k]] - 1e-9)) { keys.push("same_as_shortest"); return keys; }
    const extra = s1.len - s0.len;
    if (extra >= 5) keys.push("extra_" + bucket(extra, [10, 20, 30, 50, 100, 150, 200, 300, 400, 500]));
    if (r.crit.includes("A") && s1.aSum < s0.aSum) { const k = s0.a3 - s1.a3; keys.push(k > 0 ? "gainA_" + Math.min(8, k) : "gainA_score"); }
    if (r.crit.includes("B") && s0.bLen - s1.bLen >= 25) keys.push("gainB_" + bucket(s0.bLen - s1.bLen, [50, 100, 150, 200, 300, 400, 500]));
    if (r.crit.includes("C") && s0.cEv - s1.cEv >= 0.5) keys.push("gainC_" + Math.min(8, Math.max(1, Math.round(s0.cEv - s1.cEv))));
    if (!r.crit.includes("A") && s1.aSum > s0.aSum + 0.5) keys.push("trade_A");
    if (!r.crit.includes("B") && s1.bLen > s0.bLen + 20) keys.push("trade_B");
    if (!r.crit.includes("C") && s1.cEv > s0.cEv + 0.5) keys.push("trade_C");
    return keys;
  };

  // ------------------------------------------------------------ 안내기 (위치 -> 말할 것)
  function Navigator(graph, mode, opt) {
    this.g = graph; this.mode = mode;
    this.opt = Object.assign({}, DEFAULTS, opt || {});
    this.targets = this.opt.gate != null ? [this.opt.gate] : null;
    this.plan = null; this.progress = 0; this.off = 0; this.done = false; this.log = [];
  }

  Navigator.prototype._emit = function (t, type, keys, extra) {
    const ev = Object.assign({ t, type, keys, text: keys.map((k) => this.g.clips[k] || k).join(" ") }, extra || {});
    this.log.push(ev);
    return ev;
  };

  Navigator.prototype._start = function (p, t, reroute) {
    const near = this.g.nearestNode(p);
    if (near.d > this.opt.snapMaxM) return [this._emit(t, "outside", ["outside"])];
    const r = this.g.route(near.node, this.mode, this.targets);
    if (!r) return [this._emit(t, "outside", ["outside"])];
    this.plan = this.g.plan(r, this.opt);
    this.progress = 0; this.off = 0;
    this.said = { man: new Set(), hz: new Set() };
    if (reroute) return [this._emit(t, "reroute", ["offroute"])];
    return [this._emit(t, "start", this.g.summaryKeys(r), { stats: r.stats, shortest: r.shortest.stats })];
  };

  /** 위치 하나를 넣으면 이번에 말할 안내 목록을 돌려준다. pos = {lon, lat, t} */
  Navigator.prototype.update = function (pos) {
    if (this.done) return [];
    const p = this.g.proj.to(pos.lon, pos.lat), t = pos.t || 0, out = [];
    if (!this.plan) return this._start(p, t, false);
    const P = this.plan;
    // 진행 위치: 지금 진행 거리 -30m ~ +150m 안에서 가장 가까운 점
    let best = { d: Infinity, s: this.progress };
    for (let j = 1; j < P.pts.length; j++) {
      if (P.cum[j] < this.progress - 30 || P.cum[j - 1] > this.progress + 150) continue;
      const q = projectOnSeg(p, P.pts[j - 1], P.pts[j]);
      if (q.d < best.d) best = { d: q.d, s: P.cum[j - 1] + q.t * (P.cum[j] - P.cum[j - 1]) };
    }
    const offLimit = Math.max(this.opt.offRouteM, this.opt.offRouteAcc * (pos.acc || 0));
    if (best.d > offLimit) {
      if (++this.off >= this.opt.offRouteCount) return this._start(p, t, true);
      return out;
    }
    this.off = 0;
    this.progress = Math.max(this.progress, best.s);
    const s = this.progress;
    if (P.total - s <= this.opt.arriveM) {
      this.done = true;
      out.push(this._emit(t, "arrive", ["arrive_" + this.g.gateByNode[P.route.gate]], { s }));
      return out;
    }
    P.hazards.forEach((h, i) => {
      const ahead = h.s - s;
      if (!this.said.hz.has(i) && ahead <= this.opt.hazardAhead && ahead > -5) {
        this.said.hz.add(i);
        out.push(this._emit(t, "hazard", h.keys, { s, target: h.s, kind: h.kind, xy: P.at(h.s) }));
      }
    });
    P.maneuvers.forEach((m, i) => {
      const ahead = m.s - s;
      if (ahead <= 0) return;
      const farId = i + ":far", nearId = i + ":near";
      if (ahead <= this.opt.maneuverNear && !this.said.man.has(nearId)) {
        this.said.man.add(nearId); this.said.man.add(farId);
        out.push(this._emit(t, "maneuver", ["d_soon", m.key], { s, target: m.s, which: "near", node: m.node }));
      } else if (ahead <= this.opt.maneuverFar && !this.said.man.has(farId)) {
        this.said.man.add(farId);
        out.push(this._emit(t, "maneuver", ["d_" + bucket(ahead, DIST_STEPS), m.key], { s, target: m.s, which: "far", node: m.node }));
      }
    });
    return out;
  };

  /** 재생 직전 확인: 회전·위험 지점을 이미 지나쳤으면 true (재생하지 않는다). */
  Navigator.prototype.isStale = function (ev) {
    return (ev.type === "maneuver" || ev.type === "hazard") && ev.target != null && ev.target < this.progress - 2;
  };

  // ------------------------------------------------------------ 자유 보행 (경로 없이 주변 위험만)
  function FreeWalker(graph, opt) {
    this.g = graph; this.opt = Object.assign({}, DEFAULTS, opt || {});
    this.cues = graph.data.cues.map((c) => ({ key: c.key, kind: c.kind, pt: c.pt, xy: c.xy.map(([x, y]) => graph.proj.to(x, y)) }));
    this.armed = this.cues.map(() => true); this.log = [];
  }
  FreeWalker.prototype.update = function (pos) {
    const p = this.g.proj.to(pos.lon, pos.lat), out = [];
    this.cues.forEach((c, i) => {
      let d = Infinity;
      if (c.pt) d = hyp(p, c.xy[0]);
      else for (let j = 1; j < c.xy.length; j++) d = Math.min(d, projectOnSeg(p, c.xy[j - 1], c.xy[j]).d);
      if (this.armed[i] && d <= this.opt.freeRadius) {
        this.armed[i] = false;
        const ev = { t: pos.t || 0, type: "hazard", keys: [c.key], text: this.g.clips[c.key], kind: c.kind, cue: i, d };
        this.log.push(ev); out.push(ev);
      } else if (!this.armed[i] && d > this.opt.freeResetM) this.armed[i] = true;
    });
    return out;
  };

  // ------------------------------------------------------------ 가상 걷기 (시연·시뮬레이션용)
  function rng(seed) { let s = seed >>> 0 || 1; return () => { s ^= s << 13; s ^= s >>> 17; s ^= s << 5; return ((s >>> 0) % 1e9) / 1e9; }; }
  function gauss(rand) { let u = 0; while (u === 0) u = rand(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * rand()); }

  /** 계획된 경로를 따라 걷는 GPS 기록. noise = 위치 오차 표준편차(m), 오차는 시간에 따라 천천히 변한다. */
  function walkTrace(graph, plan, o) {
    o = Object.assign({ speed: 1.0, hz: 1, noise: 5, corr: 0.8, seed: 1, startT: 0 }, o || {});
    const rand = rng(o.seed), out = [];
    let ex = 0, ey = 0;
    const k = Math.sqrt(1 - o.corr * o.corr);
    for (let t = 0, d = 0; d <= plan.total + o.speed; t += 1 / o.hz, d += o.speed / o.hz) {
      ex = o.corr * ex + k * o.noise * gauss(rand);
      ey = o.corr * ey + k * o.noise * gauss(rand);
      const [x, y] = plan.at(Math.min(d, plan.total));
      const [lon, lat] = graph.proj.from(x + ex, y + ey);
      out.push({ lon, lat, t: o.startT + t, trueS: Math.min(d, plan.total) });
    }
    return out;
  }

  return { Graph, Navigator, FreeWalker, walkTrace, MODES, METRIC, DEFAULTS, CAP, critOf };
});
