/* 음성 안내 서비스 시뮬레이션 (codex&claude.md §16.37).
 * 기존 출발지(숭실대 79, 중앙대 74)마다, 4개 모드 경로를 가상 보행자가 초속 speed m로 걷는다.
 * GPS 오차(표준편차 noise m, 시간에 따라 천천히 변함)를 섞은 위치를 1초마다 안내기에 넣고 기록을 평가한다.
 * 음성 길이는 글자당 0.17초 + 조각 사이 0.3초로 어림하고, 안내는 순서대로(겹치지 않게) 재생된다고 본다.
 * 실행: node simulate_nav.js [출력 csv 경로]
 */
const fs = require("fs");
const path = require("path");
const E = require("./nav_engine.js");

const DIR = __dirname;
const clips = JSON.parse(fs.readFileSync(path.join(DIR, "clips.json"), "utf8"));
const NOISES = [0, 5, 10, 15];
const SPEED = 1.0;
const speechSec = (ev) => ev.text.replace(/\s/g, "").length * 0.17 + 0.3 * ev.keys.length;

function evaluate(g, origin, mode, noise, seed) {
  const r = g.route(origin, mode);
  const plan = g.plan(r);
  const nav = new E.Navigator(g, mode);
  // 출발 전: 첫 위치에서 경로 요약을 듣고, 요약이 끝나면 걷기 시작
  const first = E.walkTrace(g, plan, { speed: SPEED, noise, seed, hz: 1 })[0];
  const intro = nav.update(Object.assign({}, first, { acc: noise }));
  const introSec = intro.reduce((a, e) => a + speechSec(e), 0);
  const trace = E.walkTrace(g, plan, { speed: SPEED, noise, seed, startT: introSec });
  let busyUntil = introSec;
  const spoken = intro.map((e) => Object.assign({}, e, { trueS: 0, endS: 0, delay: 0 }));
  for (const pos of trace) {
    for (const ev of nav.update(Object.assign({}, pos, { acc: noise }))) {
      const start = Math.max(pos.t, busyUntil);
      // 재생 차례가 왔을 때 이미 지나친 지점이면 버린다 (페이지에서는 nav.isStale로 같은 판단)
      const sAtStart = pos.trueS + (start - pos.t) * SPEED;
      if ((ev.type === "maneuver" || ev.type === "hazard") && ev.target < sAtStart - 2) { spoken.push(Object.assign({}, ev, { dropped: true, trueS: pos.trueS, endS: sAtStart, delay: start - pos.t })); continue; }
      busyUntil = start + speechSec(ev);
      // 음성이 끝나는 순간 보행자의 실제 위치(경로 위 거리)
      const endS = Math.min(plan.total, pos.trueS + (busyUntil - pos.t) * SPEED);
      spoken.push(Object.assign({}, ev, { trueS: pos.trueS, endS, delay: start - pos.t }));
    }
    if (nav.done) break;
  }
  const reroutes = spoken.filter((e) => e.type === "reroute").length;
  const firstReroute = spoken.find((e) => e.type === "reroute");
  const validUntil = firstReroute ? firstReroute.trueS : Infinity;
  // 회전: 원래 경로의 회전 노드마다 'far/near' 안내가 나왔는지, 음성이 끝났을 때 몇 m 남았는지
  const man = plan.maneuvers.filter((m) => m.s < validUntil).map((m) => {
    const evs = spoken.filter((e) => e.type === "maneuver" && !e.dropped && e.node === m.node);
    const near = evs.find((e) => e.which === "near") || evs[evs.length - 1];
    return { said: evs.length > 0, endLead: near ? m.s - near.endS : null };
  });
  // 위험: 원래 경로의 위험 지점마다 10m 안에서 안내가 나왔는지
  // 출발 위치가 이미 위험 구간 안(경로 위 5m 미만)이면 미리 알릴 수 없으므로 따로 센다
  const startInside = plan.hazards.filter((h) => h.s < 5).length;
  const hz = plan.hazards.filter((h) => h.s >= 5 && h.s < validUntil).map((h) => {
    const xy = plan.at(h.s);
    const ev = spoken.find((e) => e.type === "hazard" && !e.dropped && e.xy && Math.hypot(e.xy[0] - xy[0], e.xy[1] - xy[1]) <= 10);
    return { said: !!ev, endLead: ev ? h.s - ev.endS : null };
  });
  const arrive = spoken.find((e) => e.type === "arrive");
  return {
    mode, noise, len: plan.total, reroutes, start: spoken[0] ? spoken[0].type : "none",
    manN: man.length, manSaid: man.filter((m) => m.said).length,
    manLate: man.filter((m) => m.said && m.endLead < 0).length,
    manLeadMed: median(man.filter((m) => m.said).map((m) => m.endLead)),
    hzN: hz.length, hzSaid: hz.filter((h) => h.said).length,
    hzLate: hz.filter((h) => h.said && h.endLead < 0).length,
    hzLeadMed: median(hz.filter((h) => h.said).map((h) => h.endLead)),
    hzStartInside: startInside,
    arrived: !!arrive, arriveLeft: arrive ? +(plan.total - arrive.trueS).toFixed(1) : null,
    nSpoken: spoken.filter((e) => !e.dropped).length, nDropped: spoken.filter((e) => e.dropped).length, introSec: +introSec.toFixed(1), maxDelay: Math.max(0, ...spoken.filter((e) => !e.dropped).map((e) => e.delay)),
  };
}

function median(a) { if (!a.length) return null; const s = a.slice().sort((x, y) => x - y); return s[Math.floor(s.length / 2)]; }

const rows = [];
for (const [tag, school] of [["soongsil", "숭실대"], ["chungang", "중앙대"]]) {
  const d = JSON.parse(fs.readFileSync(path.join(DIR, `data_${tag}.json`), "utf8"));
  const g = new E.Graph(d, clips);
  d.origins.forEach((o, k) => E.MODES.forEach((mode) => NOISES.forEach((noise) => {
    rows.push(Object.assign({ school, origin: k }, evaluate(g, o, mode, noise, 1000 + k)));
  })));
}
const out = process.argv[2] || path.join(DIR, "..", "..", "data", "route", "nav_simulation.csv");
const cols = Object.keys(rows[0]);
fs.writeFileSync(out, "﻿" + cols.join(",") + "\n" + rows.map((r) => cols.map((c) => r[c] === null ? "" : r[c]).join(",")).join("\n"));
console.log(`${rows.length} runs -> ${out}`);
