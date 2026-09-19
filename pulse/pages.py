"""
The four web pages, as plain strings.

Everything is inline - no CDN, no downloads, nothing to install. The venue
Wi-Fi may have no internet at all, so the pages must work on their own.
"""

# Shared look. Dark, because it is projected next to the slides.
CSS = """
:root{--bg:#1E1E1E;--card:#2A2A2A;--txt:#E8ECF7;--mut:#8B93AD;--acc:#5AD1FF;
      --grn:#4ADE80;--red:#F87171}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);
     font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;-webkit-text-size-adjust:100%}
.card{background:var(--card);border-radius:16px;padding:20px}
.mut{color:var(--mut)}
button{font-family:inherit;cursor:pointer;border:none;border-radius:12px}
/* Centred with left:0/right:0/margin:auto rather than left:50%, which would only
   give the pill the right half of the screen to lay out in and wrap the text.
   width:max-content sizes it to the words, so it can never wrap. */
.toast{position:fixed;left:0;right:0;bottom:26px;margin:0 auto;
  width:max-content;max-width:calc(100% - 32px);
  display:flex;align-items:center;justify-content:center;gap:9px;
  background:var(--grn);color:#07240f;font-weight:800;white-space:nowrap;
  padding:13px 24px;border-radius:999px;font-size:18px;letter-spacing:.2px;
  box-shadow:0 10px 28px rgba(0,0,0,.45);
  opacity:0;transform:translateY(10px);transition:opacity .2s,transform .2s;
  pointer-events:none;z-index:50}
.toast.show{opacity:1;transform:none}
.toast .tick{font-size:20px;line-height:1}
"""

# --------------------------------------------------------------------------
# Student page (phones)
# --------------------------------------------------------------------------

PAGE_STUDENT = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Pulse</title><style>/*CSS*/
body{padding:18px;font-size:18px}
h1{font-size:26px;margin:0 0 16px}
header{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
header .logo{font-size:20px;font-weight:800;color:var(--acc);letter-spacing:.5px}
#leave{padding:9px 16px;font-size:15px;font-weight:700;background:#3A3F52;color:var(--mut)}
#leave:hover{color:var(--txt)}
label{display:block;margin:14px 0 6px;font-size:17px;color:var(--mut)}
input,select,textarea{width:100%;padding:15px;font-size:19px;border-radius:12px;border:2px solid #3A3F52;
  background:#1E1E1E;color:var(--txt);font-family:inherit}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--acc)}
textarea{min-height:130px;resize:vertical}
.primary{width:100%;margin-top:18px;padding:18px;font-size:20px;font-weight:800;
  background:var(--acc);color:#06222E}
.err{color:var(--red);font-size:16px;min-height:20px}
.center{text-align:center}
#waiting{padding:40px 20px;font-size:21px;line-height:1.5;color:var(--mut)}
#waiting b{color:var(--txt);display:block;font-size:24px;margin-bottom:8px}
.qcard{margin-top:4px}
.prompt{font-size:24px;font-weight:800;line-height:1.35;margin-bottom:20px}
.opt{display:block;width:100%;margin-bottom:12px;padding:20px;font-size:20px;font-weight:700;
  text-align:left;background:#1E1E1E;color:var(--txt);border:2px solid #3A3F52}
.opt.on{border-color:var(--acc);background:#10323F;color:var(--acc)}
.scale{display:flex;gap:10px}
.scale .opt{text-align:center;padding:24px 0;font-size:26px}
.scalelab{display:flex;justify-content:space-between;color:var(--mut);font-size:15px;margin-top:8px}
#clock{font-size:20px;font-weight:800;color:var(--acc);margin-bottom:14px;
  font-variant-numeric:tabular-nums;font-feature-settings:"tnum" 1;min-height:24px}
/* the time sits in a fixed-width slot, so "left to answer" never slides */
#clock .num{display:inline-block;min-width:96px}
#clock.low{color:var(--red)}
#clock.up{color:var(--red)}
.locked .opt,.locked textarea,.locked .primary{opacity:.45;pointer-events:none}
.in{animation:slide .35s ease-out}
@keyframes slide{from{opacity:0;transform:translateY(-18px)}to{opacity:1;transform:none}}
</style></head><body>
<header><span class="logo">&#9679; PULSE</span><button id="leave" hidden>Log out</button></header>
<section id="join" class="card">
  <h1>Join the session</h1>
  <label for="name">Your name</label>
  <input id="name" maxlength="60" autocomplete="name" placeholder="e.g. Aarav Sharma">
  <label for="sem">Semester</label>
  <select id="sem"><option>1st</option><option>2nd</option><option>3rd</option><option>4th</option><option>5th</option><option>6th</option><option>7th</option><option>8th</option><option>Other</option></select>
  <label for="email">Email <span class="mut">(optional)</span></label>
  <input id="email" type="email" maxlength="120" inputmode="email" placeholder="you@example.com">
  <button class="primary" id="joinbtn">Join</button>
  <p class="err" id="joinerr"></p>
</section>
<section id="live" hidden>
  <div id="waiting" class="card center"></div>
  <div id="clock" hidden></div>
  <div id="qbox"></div>
</section>
<div class="toast" id="toast"><span class="tick">&#10003;</span><span>answer received</span></div>
<script>
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
let sid = localStorage.getItem("pulse_sid");
let myName = localStorage.getItem("pulse_name") || "";
let shownKey = "";                       // so we only redraw when the question really changes

function toast(msg){ const t = document.getElementById("toast");
  if (msg) t.lastElementChild.innerHTML = msg;
  t.classList.add("show");
  setTimeout(() => { t.classList.remove("show");
                     setTimeout(() => t.lastElementChild.textContent = "answer received", 300); }, 1400); }

document.getElementById("joinbtn").onclick = async () => {
  const name = document.getElementById("name").value.trim();
  const err = document.getElementById("joinerr");
  if (!name) { err.textContent = "Please type your name"; return; }
  err.textContent = "";
  const r = await fetch("/quiz/join", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({name, semester: document.getElementById("sem").value,
                          email: document.getElementById("email").value.trim()})});
  if (!r.ok) { err.textContent = (await r.json()).detail || "Could not join"; return; }
  const d = await r.json();
  sid = d.student_id; myName = d.name;
  localStorage.setItem("pulse_sid", sid); localStorage.setItem("pulse_name", myName);
  showLive();
};

function showLive(){
  document.getElementById("join").hidden = true;
  document.getElementById("live").hidden = false;
  document.getElementById("leave").hidden = false;
  document.getElementById("waiting").innerHTML =
    "<b>You're in, " + esc(myName) + "</b>Waiting for the next question&hellip;";
  tick(); setInterval(tick, 2000);
}

async function send(value){
  const r = await fetch("/quiz/answer", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({student_id: sid, question_id: shownId, answer: value})});
  if (r.ok) { localStorage.setItem("pulse_a_" + shownId, String(value)); toast(); }
  else if (r.status === 409) { lock(); toast("&#9203; time is up"); }
}

// When the clock runs out the question stays on screen, it just stops taking
// answers - same as the projector.
function lock(){
  document.getElementById("qbox").classList.add("locked");
  const c = document.getElementById("clock");
  c.hidden = false; c.className = "up"; c.textContent = "Time is up - answers closed";
}

function clock(n){
  if (n >= 60){
    const m = Math.floor(n / 60), sec = n % 60;
    return sec ? m + "m " + sec + "s" : m + "m";
  }
  return n + "s";
}

let ticker = null;
function startClock(left){
  clearInterval(ticker);
  const c = document.getElementById("clock");
  if (left === null || left === undefined){ c.hidden = true; return; }
  let n = left;
  const paint = () => {
    if (n <= 0){ lock(); clearInterval(ticker); return; }
    c.hidden = false; c.className = n <= 10 ? "low" : "";
    c.innerHTML = '<span class="num">' + clock(n) + "</span> left to answer";
    n -= 1;
  };
  paint();
  ticker = setInterval(paint, 1000);
}

let shownId = null;
let lastLeft = null;
function draw(q){
  const mine = localStorage.getItem("pulse_a_" + q.id);
  let html = '<div class="card qcard in"><div class="prompt">' + esc(q.prompt) + "</div>";
  if (q.type === "choice")
    html += q.options.map((o, i) => '<button class="opt' + (String(i) === mine ? " on" : "") +
            '" data-v="' + i + '">' + esc(o) + "</button>").join("");
  else if (q.type === "scale")
    html += '<div class="scale">' + [1,2,3,4,5].map(n => '<button class="opt' +
            (String(n) === mine ? " on" : "") + '" data-v="' + n + '">' + n + "</button>").join("") +
            '</div><div class="scalelab"><span>Not at all</span><span>Totally</span></div>';
  else
    html += '<textarea id="ta" maxlength="200" placeholder="Type your answer">' + esc(mine || "") +
            '</textarea><button class="primary" id="send">Submit</button>';
  document.getElementById("qbox").innerHTML = html + "</div>";
  document.getElementById("qbox").classList.remove("locked");

  document.querySelectorAll(".opt").forEach(b => b.onclick = () => {
    document.querySelectorAll(".opt").forEach(x => x.classList.remove("on"));
    b.classList.add("on"); send(b.dataset.v);
  });
  const s = document.getElementById("send");
  if (s) s.onclick = () => { const t = document.getElementById("ta").value.trim();
                             if (t) send(t); };
  if (navigator.vibrate) navigator.vibrate(100);
}

async function tick(){
  try {
    const d = await (await fetch("/quiz/state")).json();
    const q = d.open_question;
    if (!q){ shownKey = ""; shownId = null;
             clearInterval(ticker);
             document.getElementById("clock").hidden = true;
             document.getElementById("qbox").innerHTML = "";
             document.getElementById("waiting").hidden = false; return; }
    document.getElementById("waiting").hidden = true;
    // Redraw only when the question changes - otherwise we would wipe what
    // the student is typing every two seconds.
    const key = q.id + "|" + q.prompt + "|" + q.options.join("~");
    if (key !== shownKey){ shownKey = key; shownId = q.id; draw(q); startClock(d.seconds_left); }
    if (!d.accepting) lock();
    else if (d.seconds_left !== null && Math.abs(d.seconds_left - lastLeft) > 2) startClock(d.seconds_left);
    lastLeft = d.seconds_left;
  } catch (e) { /* server busy - try again next tick */ }
}

document.getElementById("leave").onclick = () => {
  if (!confirm("Log out of Pulse on this phone? You can join again with a different name.")) return;
  // Only clears this device. Answers already sent stay with the instructor.
  Object.keys(localStorage).filter(k => k.startsWith("pulse_")).forEach(k => localStorage.removeItem(k));
  location.reload();
};

if (sid) showLive();
</script></body></html>
"""

# --------------------------------------------------------------------------
# Projector page
# --------------------------------------------------------------------------

PAGE_SCREEN = """<!doctype html><html><head><meta charset="utf-8">
<title>Pulse - screen</title><style>/*CSS*/
body{height:100vh;overflow:hidden;padding:24px 28px;display:flex}
.screen{display:flex;gap:22px;width:100%;height:100%;min-height:0}
/* 65 / 35 - the question and its results on the left, the room on the right */
.main{flex:0 0 65%;max-width:65%;display:flex;flex-direction:column;min-width:0;min-height:0}
.main.full{flex:1 1 100%;max-width:100%}
.side{flex:1;display:flex;flex-direction:column;gap:16px;min-width:0;min-height:0}
.side[hidden]{display:none}
.head{display:flex;align-items:flex-start;gap:22px;margin:0 0 22px}
#prompt{font-size:50px;font-weight:800;line-height:1.2;margin:0;flex:1;min-width:0}
/* fixed width and tabular figures, so the prompt never shifts as digits change */
#timer{flex:0 0 auto;width:250px;font-size:52px;font-weight:800;color:var(--acc);
  background:#1E1E1E;border-radius:16px;padding:10px 16px;line-height:1.1;
  font-variant-numeric:tabular-nums;font-feature-settings:"tnum" 1;text-align:center}
#timer small{display:block;font-size:14px;color:var(--mut);letter-spacing:1.5px;font-weight:600;
  margin-top:2px}
#timer.low{color:var(--red);animation:pulse 1s infinite}
#timer.up{color:var(--red);font-size:32px;padding:20px 16px}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.45}}
#stage{flex:1;min-height:0;display:flex;flex-direction:column;justify-content:center;overflow:hidden}
/* the answer wall is the one result that can outgrow the screen, so it scrolls */
#stage.top{justify-content:flex-start;overflow-y:auto;padding-right:8px;
  scrollbar-width:thin;scrollbar-color:#4A5168 transparent}
#stage.top::-webkit-scrollbar{width:10px}
#stage.top::-webkit-scrollbar-thumb{background:#4A5168;border-radius:5px}
.qr{display:flex;align-items:center;justify-content:center;gap:60px;height:100%}
.qr img{background:#fff;padding:18px;border-radius:20px;width:520px;height:520px}
.qr .join{font-size:34px;color:var(--mut)}
.qr .url{font-size:46px;font-weight:800;color:var(--acc);word-break:break-all;margin-top:10px}
.row{margin-bottom:20px}
.rowtop{display:flex;justify-content:space-between;font-size:32px;font-weight:700;margin-bottom:8px}
.track{height:42px;background:#1E1E1E;border-radius:10px;overflow:hidden}
.fill{height:100%;background:var(--acc);width:0;transition:width .6s ease-out;border-radius:10px}
.row.correct .fill{background:var(--grn)} .row.dim{opacity:.35}
.wall{column-count:2;column-gap:18px}
.wall .a{break-inside:avoid;background:var(--card);border-radius:14px;padding:13px 16px;margin-bottom:16px}
.wall .who{font-size:15px;color:var(--mut);margin-bottom:4px}
.wall .txt{font-size:23px;line-height:1.3}
.wall .a.new{animation:pop .45s ease-out}
@keyframes pop{from{opacity:0;transform:scale(.94)}to{opacity:1;transform:none}}
.donutwrap{display:flex;align-items:center;justify-content:center;gap:46px}
.legend div{font-size:26px;margin-bottom:12px;display:flex;align-items:center;gap:12px}
.swatch{width:24px;height:24px;border-radius:7px;display:inline-block}
.cmp{display:flex;gap:34px}.cmp>div{flex:1;min-width:0}
.row.sc{margin-bottom:12px}
.sc .rowtop{font-size:24px;margin-bottom:5px}
.sc .track{height:32px}
.cmphead{font-size:26px;color:var(--mut);margin-bottom:10px;text-transform:uppercase;letter-spacing:1px;min-height:26px}
.avg{font-size:58px;font-weight:800;color:var(--acc);text-align:center;margin-top:6px}
.avg span{font-size:22px;color:var(--mut);display:block;font-weight:600;letter-spacing:1px}
footer{display:flex;justify-content:space-between;font-size:26px;color:var(--mut);padding-top:14px}

/* the right-hand column: answered on top, still waiting underneath */
.panel{flex:1;background:var(--card);border-radius:16px;padding:16px 18px;
  display:flex;flex-direction:column;min-height:0}
.panel h2{font-size:21px;color:var(--mut);margin:0 0 12px;text-transform:uppercase;
  letter-spacing:1px;display:flex;justify-content:space-between;align-items:baseline}
.panel h2 b{font-size:30px;color:var(--acc)}
.panel h2.ok b{color:var(--grn)}
.list{overflow-y:auto;flex:1;min-height:0;scrollbar-width:thin;scrollbar-color:#4A5168 transparent}
.list::-webkit-scrollbar{width:9px}
.list::-webkit-scrollbar-thumb{background:#4A5168;border-radius:5px}
.who2{display:flex;gap:10px;align-items:baseline;padding:8px 0;border-bottom:1px solid #343945;cursor:pointer}
.who2 .nm{font-size:21px;font-weight:700;flex:0 0 auto;max-width:44%;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.who2 .an{font-size:19px;color:var(--acc);flex:1;min-width:0;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.who2.open .an{white-space:normal;overflow:visible;text-overflow:clip}
.who2.open{background:#1E1E1E;border-radius:10px;padding:8px 10px}
.wait{display:inline-block;font-size:19px;padding:6px 12px;margin:0 8px 8px 0;
  border-radius:999px;background:#1E1E1E;color:var(--mut)}
.empty2{color:var(--mut);font-size:19px;padding:8px 0}
.new2{animation:pop .4s ease-out}

@media (max-height:820px){
  #prompt{font-size:38px}
  .head{margin-bottom:14px;gap:16px}
  #timer{width:190px;font-size:38px;padding:8px 12px}#timer small{font-size:11px}
  #timer.up{font-size:24px;padding:16px 12px}
  .rowtop{font-size:24px}.track{height:30px}.row{margin-bottom:13px}
  .row.sc{margin-bottom:8px}.sc .rowtop{font-size:20px}.sc .track{height:24px}
  .cmphead{font-size:21px;min-height:21px}
  .avg{font-size:42px}.avg span{font-size:17px}
  .wall .txt{font-size:19px}.wall .who{font-size:13px}
  .wall .a{padding:10px 13px;margin-bottom:12px}
  .legend div{font-size:21px;margin-bottom:9px}
  .qr img{width:400px;height:400px}.qr .url{font-size:34px}.qr .join{font-size:26px}
  footer{font-size:21px;padding-top:9px}
  .panel h2{font-size:17px}.panel h2 b{font-size:24px}
  .who2 .nm{font-size:18px}.who2 .an{font-size:16px}
  .wait{font-size:16px;padding:5px 10px}
}
</style></head><body>
<div class="screen">
  <div class="main full" id="main">
    <div class="head"><h1 id="prompt"></h1><div id="timer" hidden></div></div>
    <div id="stage"></div>
    <footer><div id="answered"></div><div id="joined"></div></footer>
  </div>
  <aside class="side" id="side" hidden>
    <section class="panel">
      <h2 class="ok">Answered <b id="acount">0</b></h2>
      <div class="list" id="alist"></div>
    </section>
    <section class="panel">
      <h2>Still to answer <b id="wcount">0</b></h2>
      <div class="list" id="wlist"></div>
    </section>
  </aside>
</div>
<script>
const JOIN_URL = "__JOIN_URL__";
const COLORS = ["#5AD1FF","#4ADE80","#F87171","#FBBF24","#A78BFA","#F472B6","#2DD4BF","#FB923C"];
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const stage = document.getElementById("stage");
const side = document.getElementById("side");
const main = document.getElementById("main");
let builtKey = "";            // rebuild the skeleton only when the question changes
let seen = new Set();         // text answers that have already animated in
let opened = new Set();       // rows the instructor clicked open, kept across refreshes
let seenWho = new Set();

function pct(n, total){ return total ? Math.round(n * 100 / total) : 0; }

function buildBars(labels){
  const tight = labels.length > 5 ? " sc" : "";   // 8 options only fit at the smaller size
  stage.innerHTML = labels.map((l, i) =>
    '<div class="row' + tight + '" data-i="' + i + '"><div class="rowtop"><span>' + esc(l) +
    '</span><span class="n"></span></div><div class="track"><div class="fill"></div></div></div>').join("");
}
function paintBars(counts, reveal, correct){
  const total = counts.reduce((a, b) => a + b, 0);
  stage.querySelectorAll(".row").forEach(row => {
    const i = +row.dataset.i;
    row.querySelector(".n").textContent = counts[i] + "  ·  " + pct(counts[i], total) + "%";
    row.querySelector(".fill").style.width = pct(counts[i], total) + "%";
    row.classList.toggle("correct", reveal && i === correct);
    row.classList.toggle("dim", reveal && correct != null && i !== correct);
  });
}

function buildDonut(labels){
  stage.innerHTML = '<div class="donutwrap"><svg id="dn" width="400" height="400" viewBox="0 0 42 42">' +
    labels.map((l, i) => '<circle class="sl" data-i="' + i + '" cx="21" cy="21" r="15.9" fill="none" ' +
      'stroke="' + COLORS[i % COLORS.length] + '" stroke-width="7" stroke-dasharray="0 100" ' +
      'transform="rotate(-90 21 21)" style="transition:stroke-dasharray .6s"></circle>').join("") +
    '</svg><div class="legend">' + labels.map((l, i) =>
      '<div><span class="swatch" style="background:' + COLORS[i % COLORS.length] + '"></span>' +
      esc(l) + ' <b class="n" data-i="' + i + '"></b></div>').join("") + "</div></div>";
}
function paintDonut(counts){
  const total = counts.reduce((a, b) => a + b, 0) || 1;
  let acc = 0;
  stage.querySelectorAll(".sl").forEach(c => {
    const i = +c.dataset.i, len = counts[i] * 100 / total;
    c.setAttribute("stroke-dasharray", len + " " + (100 - len));
    c.setAttribute("stroke-dashoffset", -acc); acc += len;
  });
  stage.querySelectorAll(".legend .n").forEach(n =>
    n.textContent = counts[+n.dataset.i] + " (" + pct(counts[+n.dataset.i],
      counts.reduce((a, b) => a + b, 0)) + "%)");
}

function scaleBlock(title, counts, average){
  return '<div><div class="cmphead">' + esc(title) + "</div>" +
    counts.map((c, i) => {
      const total = counts.reduce((a, b) => a + b, 0);
      return '<div class="row sc"><div class="rowtop"><span>' + (i + 1) + '</span><span>' + c +
        "</span></div><div class='track'><div class='fill' style='width:" +
        pct(c, total) + "%'></div></div></div>";
    }).join("") + '<div class="avg">' + average.toFixed(1) + "<span>AVERAGE</span></div></div>";
}

// 95 -> "1m 35s", 45 -> "45s". Keeps the wording steady instead of counting
// down through three-digit second counts.
function clock(n){
  if (n >= 60){
    const m = Math.floor(n / 60), sec = n % 60;
    return sec ? m + "m " + sec + "s" : m + "m";
  }
  return n + "s";
}

let ticker = null, lastLeft = null;
// The countdown ticks locally between polls so it moves every second, not
// every 1.5. When it hits zero the results stay up - only answering stops.
function startTimer(left){
  clearInterval(ticker);
  const t = document.getElementById("timer");
  if (left === null || left === undefined){ t.hidden = true; return; }
  let n = left;
  const paint = () => {
    t.hidden = false;
    if (n <= 0){ t.className = "up"; t.innerHTML = "TIME UP<small>ANSWERS CLOSED</small>";
                 clearInterval(ticker); return; }
    t.className = n <= 10 ? "low" : "";
    t.innerHTML = clock(n) + "<small>LEFT TO ANSWER</small>";
    n -= 1;
  };
  paint();
  ticker = setInterval(paint, 1000);
}

function showQR(){
  clearInterval(ticker);
  document.getElementById("timer").hidden = true;
  side.hidden = true; main.classList.add("full");
  if (builtKey === "qr") return;
  builtKey = "qr";
  document.getElementById("prompt").textContent = "";
  document.getElementById("answered").textContent = "";
  stage.innerHTML = '<div class="qr"><img src="/quiz/qr.svg" alt="Join QR code">' +
    '<div><div class="join">Scan to join</div><div class="url">' + esc(JOIN_URL) + "</div></div></div>";
}

// Right column. Long answers are cut with an ellipsis; hover shows the full text
// as a tooltip and clicking the row expands it in place.
// Redraw a list but stay where the instructor scrolled to, instead of snapping
// back to the top every 1.5 seconds.
function fill(id, html){
  const box = document.getElementById(id);
  const top = box.scrollTop;
  box.innerHTML = html;
  box.scrollTop = top;
}

function drawSide(d){
  const a = d.answered_by || [], w = d.waiting || [];
  document.getElementById("acount").textContent = a.length;
  document.getElementById("wcount").textContent = w.length;
  fill("alist", a.length
    ? a.map(x => {
        const key = x.name + "|" + x.answer;
        const cls = (opened.has(key) ? " open" : "") + (seenWho.has(key) ? "" : " new2");
        seenWho.add(key);
        return '<div class="who2' + cls + '" data-k="' + esc(key) + '" title="' +
               esc(x.name + " — " + x.answer) + '"><span class="nm">' + esc(x.name) +
               '</span><span class="an">' + esc(x.answer) + "</span></div>";
      }).join("")
    : '<div class="empty2">nobody yet</div>');
  fill("wlist", w.length
    ? w.map(n => '<span class="wait">' + esc(n) + "</span>").join("")
    : '<div class="empty2">everyone has answered</div>');
  document.querySelectorAll("#alist .who2").forEach(el => el.onclick = () => {
    const k = el.dataset.k;
    if (opened.has(k)) opened.delete(k); else opened.add(k);
    el.classList.toggle("open");
  });
}

async function tick(){
  try {
    const d = await (await fetch("/quiz/board")).json();
    document.getElementById("joined").textContent = d.joined + " students joined";
    const q = d.open_question;
    if (!q){ showQR(); return; }
    side.hidden = false; main.classList.remove("full");
    document.getElementById("answered").textContent = d.answered + " answered";
    document.getElementById("prompt").textContent = q.prompt;
    stage.className = q.type === "text" ? "top" : "";
    if (!d.accepting) startTimer(0);
    else if (d.seconds_left === null) startTimer(null);
    else if (lastLeft === null || Math.abs(d.seconds_left - lastLeft) > 2) startTimer(d.seconds_left);
    lastLeft = d.seconds_left;
    const key = q.id + "|" + q.type + "|" + q.pie + "|" + q.options.join("~") + "|" + !!d.compare;

    if (q.type === "choice"){
      if (key !== builtKey){ builtKey = key; q.pie ? buildDonut(q.options) : buildBars(q.options); }
      q.pie ? paintDonut(d.results.counts)
            : paintBars(d.results.counts, q.reveal, q.correct_index);
    } else if (q.type === "scale"){
      builtKey = key;
      stage.innerHTML = d.compare
        ? '<div class="cmp">' + scaleBlock("Start of session", d.compare.counts, d.compare.average) +
          scaleBlock("Now", d.results.counts, d.results.average) + "</div>"
        : scaleBlock("", d.results.counts, d.results.average);
    } else {
      if (key !== builtKey){ builtKey = key; seen = new Set(); stage.innerHTML = '<div class="wall"></div>'; }
      const wall = stage.querySelector(".wall");
      const wallTop = stage.scrollTop;                 // redrawing would jump to the top
      wall.innerHTML = d.results.answers.map(a => {
        const id = a.name + "|" + a.answer, fresh = seen.has(id) ? "" : " new";
        seen.add(id);
        return '<div class="a' + fresh + '"><div class="who">' + esc(a.name) +
               '</div><div class="txt">' + esc(a.answer) + "</div></div>";
      }).join("");
      stage.scrollTop = wallTop;
    }
    drawSide(d);
  } catch (e) { /* try again next tick */ }
}
tick(); setInterval(tick, 1500);
</script></body></html>
"""

# --------------------------------------------------------------------------
# Login page
# --------------------------------------------------------------------------

PAGE_LOGIN = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pulse - instructor</title><style>/*CSS*/
body{display:flex;align-items:center;justify-content:center;height:100vh}
.box{width:360px}
h1{font-size:26px;margin:0 0 6px}
p{color:var(--mut);margin:0 0 20px}
input{width:100%;padding:15px;font-size:19px;border-radius:12px;border:2px solid #3A3F52;
  background:#1E1E1E;color:var(--txt);font-family:inherit}
input:focus{outline:none;border-color:var(--acc)}
button{width:100%;margin-top:16px;padding:16px;font-size:18px;font-weight:800;
  background:var(--acc);color:#06222E}
.err{color:var(--red);min-height:22px;margin-top:12px;font-size:16px}
</style></head><body>
<form class="card box" id="f">
  <h1>Instructor login</h1><p>Pulse control panel</p>
  <input id="pw" type="password" placeholder="Password" autofocus autocomplete="current-password">
  <button>Log in</button>
  <div class="err" id="err"></div>
</form>
<script>
document.getElementById("f").onsubmit = async (e) => {
  e.preventDefault();
  const r = await fetch("/quiz/admin/login", {method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify({password: document.getElementById("pw").value})});
  if (r.ok) location.reload();
  else document.getElementById("err").textContent =
    r.status === 429 ? "Too many attempts. Wait a minute." : "Wrong password";
};
</script></body></html>
"""

# --------------------------------------------------------------------------
# Instructor control panel
# --------------------------------------------------------------------------

PAGE_ADMIN = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pulse - control</title><style>/*CSS*/
body{padding:18px;font-size:15px}
header{display:flex;align-items:center;gap:16px;margin-bottom:16px}
header h1{font-size:22px;margin:0;color:var(--acc)}
header .open{font-size:15px;color:var(--mut);flex:1}
.cols{display:flex;gap:16px;align-items:flex-start}
.left{flex:2}.right{flex:1;position:sticky;top:18px}
h2{font-size:14px;text-transform:uppercase;letter-spacing:1px;color:var(--mut);margin:0 0 12px}
.q{display:flex;gap:12px;align-items:center;background:#1E1E1E;border-radius:12px;
   padding:12px 14px;margin-bottom:9px;border:2px solid transparent}
.q.live{border-color:var(--acc)}
.qmain{flex:1;min-width:0}
.qp{font-size:16px;font-weight:700;margin-bottom:3px}
.qmeta{font-size:13px;color:var(--mut)}
.qbtns{display:flex;gap:5px;flex-wrap:wrap;justify-content:flex-end}
button{padding:7px 11px;font-size:13px;font-weight:700;background:#3A3F52;color:var(--txt)}
button:hover{background:#4A5168}
button.go{background:var(--acc);color:#06222E}
button.warn{background:#4A2530;color:var(--red)}
button.on{background:var(--grn);color:#07240f}
.big{width:100%;margin-top:8px;padding:12px;font-size:15px}
.stat{display:flex;gap:10px;margin-bottom:14px}
.stat div{flex:1;background:#1E1E1E;border-radius:10px;padding:10px;text-align:center}
.semsplit{flex-wrap:wrap}
.semsplit div{flex:0 0 auto;min-width:62px;padding:7px 10px}
.semsplit b{font-size:20px}
.stat b{display:block;font-size:26px;color:var(--acc)}
.stat span{font-size:12px;color:var(--mut)}
#names{max-height:280px;overflow-y:auto;font-size:14px;
  scrollbar-width:thin;scrollbar-color:#4A5168 transparent}
#names div{padding:6px 0;border-bottom:1px solid #333}
.modal{position:fixed;inset:0;background:#000A;display:flex;align-items:center;
  justify-content:center;z-index:40}
.modal .card{width:560px;max-height:90vh;overflow-y:auto}
label{display:block;margin:12px 0 5px;color:var(--mut);font-size:13px}
input,select,textarea{width:100%;padding:10px;font-size:15px;border-radius:10px;
  border:2px solid #3A3F52;background:#1E1E1E;color:var(--txt);font-family:inherit}
textarea{min-height:70px;resize:vertical}
.rowb{display:flex;gap:10px;margin-top:18px}
.chk{display:flex;align-items:center;gap:9px;margin-top:14px;color:var(--txt)}
.chk input{width:20px;height:20px}
#saved{color:var(--grn);font-weight:800;opacity:0;transition:opacity .3s}
#saved.show{opacity:1}
</style></head><body>
<header>
  <h1>&#9679; Pulse</h1>
  <div class="open" id="openlbl"></div>
  <span id="saved">Saved &#10003;</span>
  <button onclick="location.href='/quiz/screen'">Open screen</button>
  <button class="warn" onclick="logout()">Log out</button>
</header>
<div class="cols">
  <div class="left card">
    <h2>Questions</h2>
    <div id="qs"></div>
    <button class="big go" onclick="editor(null)">+ Add question</button>
    <div class="rowb">
      <button class="big" onclick="exportQs()">Export questions (JSON)</button>
      <button class="big" onclick="document.getElementById('imp').click()">Import questions</button>
    </div>
    <input type="file" id="imp" accept="application/json" hidden>
  </div>
  <div class="right card">
    <h2>Roster</h2>
    <div class="stat"><div><b id="njoined">0</b><span>students joined</span></div></div>
    <div class="stat semsplit" id="semsplit"></div>
    <div id="names"></div>
    <button class="big" onclick="location.href='/quiz/export'">Export answers (CSV)</button>
    <button class="big warn" onclick="reset('answers')">Reset answers</button>
    <button class="big warn" onclick="reset('all')">Reset everything</button>
  </div>
</div>
<div id="modal"></div>
<script>
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
let QS = [], OPEN = null, sig = "";

// Any 401 means the login expired - go back to the login page.
async function api(path, opts){
  const o = Object.assign({headers: {"Content-Type": "application/json"}}, opts || {});
  const r = await fetch(path, o);
  if (r.status === 401){ location.reload(); throw new Error("unauthorised"); }
  return r;
}
function saved(){ const s = document.getElementById("saved");
  s.classList.add("show"); setTimeout(() => s.classList.remove("show"), 1200); }

async function load(){
  const d = await (await api("/quiz/admin/questions")).json();
  QS = d.questions; OPEN = d.open;
  const now = QS.map(q => [q.id, q.prompt, q.open, q.reveal, q.type].join(",")).join("|");
  if (now !== sig){ sig = now; drawList(); }      // rebuild only when something structural changed
  QS.forEach(q => { const el = document.getElementById("c" + q.id);
                    if (el) el.textContent = q.answers + " answers"; });
  const open = QS.find(q => q.open);
  let label = open ? "Open now: " + open.prompt : "Nothing open - students see the waiting screen";
  if (open && d.seconds_left !== null)
    label += d.accepting
      ? "   (" + (d.seconds_left >= 60
          ? Math.floor(d.seconds_left / 60) + "m " + (d.seconds_left % 60) + "s"
          : d.seconds_left + "s") + " left)"
      : "   (time up - answers closed)";
  document.getElementById("openlbl").textContent = label;
  const r = await (await api("/quiz/admin/roster")).json();
  document.getElementById("njoined").textContent = r.joined;
  const sems = Object.entries(r.by_semester).filter(([, n]) => n > 0);
  document.getElementById("semsplit").innerHTML = sems.length
    ? sems.map(([name, n]) => "<div><b>" + n + "</b><span>" + esc(name) + "</span></div>").join("")
    : '<div class="mut" style="text-align:left">no one yet</div>';
  document.getElementById("names").innerHTML =
    r.students.map(s => "<div>" + esc(s.name) + ' <span class="mut">' + esc(s.semester) +
                        "</span></div>").join("") || '<div class="mut">nobody yet</div>';
}

function drawList(){
  document.getElementById("qs").innerHTML = QS.map((q, i) =>
    '<div class="q' + (q.open ? " live" : "") + '"><div class="qmain">' +
      '<div class="qp">' + (i + 1) + ". " + esc(q.prompt) + "</div>" +
      '<div class="qmeta">' + q.type + (q.seconds ? " &middot; " + q.seconds + "s timer" : "") +
      ' &middot; <span id="c' + q.id + '">' + q.answers +
      " answers</span></div></div><div class=\\"qbtns\\">" +
      '<button class="go" onclick="launch(' + q.id + ',0)">Launch</button>' +
      '<button onclick="launch(' + q.id + ',1)">Fresh</button>' +
      (q.open ? '<button onclick="closeQ()">Close</button>' : "") +
      (q.type === "choice" && q.correct_index != null
        ? '<button class="' + (q.reveal ? "on" : "") + '" onclick="reveal(' + q.id + ')">Reveal</button>' : "") +
      '<button onclick="editor(' + q.id + ')">Edit</button>' +
      '<button onclick="move(' + q.id + ',\\'up\\')">&#9650;</button>' +
      '<button onclick="move(' + q.id + ',\\'down\\')">&#9660;</button>' +
      '<button class="warn" onclick="del(' + q.id + ')">Delete</button>' +
    "</div></div>").join("");
}

async function launch(id, fresh){
  if (fresh && !confirm("Clear this question's answers and launch it fresh?")) return;
  await api("/quiz/admin/launch/" + id + "?fresh=" + fresh, {method: "POST"}); sig = ""; load();
}
async function closeQ(){ await api("/quiz/admin/close", {method: "POST"}); sig = ""; load(); }
async function reveal(id){ await api("/quiz/admin/reveal/" + id, {method: "POST"}); sig = ""; load(); }
async function move(id, direction){
  await api("/quiz/admin/question/" + id + "/move",
            {method: "POST", body: JSON.stringify({direction})}); sig = ""; load();
}
async function del(id){
  if (!confirm("Delete this question? It disappears from every page.")) return;
  await api("/quiz/admin/question/" + id, {method: "DELETE"}); sig = ""; load();
}
async function reset(scope){
  const msg = scope === "all" ? "Remove every student AND every answer?" : "Clear every answer?";
  if (!confirm(msg)) return;
  await api("/quiz/admin/reset?scope=" + scope, {method: "POST"}); sig = ""; load();
}
async function logout(){ await api("/quiz/admin/logout", {method: "POST"}); location.reload(); }

async function exportQs(){
  const d = await (await api("/quiz/admin/questions/export")).json();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], {type: "application/json"}));
  a.download = "pulse-questions.json"; a.click();
}
document.getElementById("imp").onchange = async (e) => {
  const file = e.target.files[0]; if (!file) return;
  if (!confirm("Importing REPLACES all current questions. Continue?")) return;
  const r = await api("/quiz/admin/questions/import", {method: "POST", body: await file.text()});
  if (r.ok){ saved(); sig = ""; load(); } else alert((await r.json()).detail);
};

function editor(id){
  const q = QS.find(x => x.id === id) ||
            {id: null, type: "choice", prompt: "", options: ["", ""], correct_index: null,
             pie: false, compare_with: null, answers: 0};
  const scales = QS.filter(x => x.type === "scale" && x.id !== q.id);
  document.getElementById("modal").innerHTML =
   '<div class="modal"><div class="card"><h2>' + (id ? "Edit question" : "New question") + "</h2>" +
   '<label>Prompt</label><textarea id="e_prompt">' + esc(q.prompt) + "</textarea>" +
   '<label>Type</label><select id="e_type">' +
     ["choice","text","scale"].map(t => '<option' + (t === q.type ? " selected" : "") + ">" + t +
     "</option>").join("") + "</select>" +
   '<div id="choicebits"><label>Options (one per line, 2 to 8)</label>' +
   '<textarea id="e_options">' + esc(q.options.join("\\n")) + "</textarea>" +
   '<label>Correct answer</label><select id="e_correct"></select>' +
   '<div class="chk"><input type="checkbox" id="e_pie"' + (q.pie ? " checked" : "") +
   '><span>Show as a donut on the projector</span></div></div>' +
   '<label>Timer (seconds after launch, 0 = no limit)</label>' +
   '<input id="e_secs" type="number" min="0" max="3600" value="' + (q.seconds || 0) + '">' +
   '<div id="scalebits"><label>Compare with an earlier scale question</label>' +
   '<select id="e_cmp"><option value="">none</option>' +
     scales.map(s => '<option value="' + s.id + '"' + (q.compare_with === s.id ? " selected" : "") +
     ">" + esc(s.prompt.slice(0, 50)) + "</option>").join("") + "</select></div>" +
   '<div class="rowb"><button class="big go" onclick="save(' + (id || "null") + "," + q.answers +
   ')">Save</button><button class="big" onclick="closeEditor()">Cancel</button></div></div></div>';
  document.getElementById("e_type").onchange = syncEditor;
  document.getElementById("e_options").oninput = fillCorrect;
  syncEditor(); fillCorrect(q.correct_index);
}
function syncEditor(){
  const t = document.getElementById("e_type").value;
  document.getElementById("choicebits").hidden = t !== "choice";
  document.getElementById("scalebits").hidden = t !== "scale";
}
function fillCorrect(selected){
  const opts = document.getElementById("e_options").value.split("\\n").map(s => s.trim()).filter(Boolean);
  const want = typeof selected === "number" ? selected
             : parseInt(document.getElementById("e_correct").value, 10);
  document.getElementById("e_correct").innerHTML = '<option value="">no correct answer</option>' +
    opts.map((o, i) => '<option value="' + i + '"' + (i === want ? " selected" : "") + ">" +
                       esc(o) + "</option>").join("");
}
function closeEditor(){ document.getElementById("modal").innerHTML = ""; }

async function save(id, answers){
  const type = document.getElementById("e_type").value;
  const options = type === "choice"
    ? document.getElementById("e_options").value.split("\\n").map(s => s.trim()).filter(Boolean) : [];
  const before = id ? (QS.find(q => q.id === id) || {}).options || [] : [];
  if (answers > 0 && JSON.stringify(before) !== JSON.stringify(options) &&
      !confirm("This question has " + answers + " answers; changing options will clear them. Continue?"))
    return;
  const correct = document.getElementById("e_correct").value;
  const body = JSON.stringify({
    type, prompt: document.getElementById("e_prompt").value,
    options, correct_index: correct === "" ? null : +correct,
    pie: document.getElementById("e_pie").checked,
    seconds: +document.getElementById("e_secs").value || 0,
    compare_with: document.getElementById("e_cmp").value
      ? +document.getElementById("e_cmp").value : null});
  const r = id ? await api("/quiz/admin/question/" + id, {method: "PUT", body})
               : await api("/quiz/admin/question", {method: "POST", body});
  if (!r.ok){ alert((await r.json()).detail); return; }
  closeEditor(); saved(); sig = ""; load();
}

load(); setInterval(load, 2000);
</script></body></html>
"""

# Drop the shared CSS into each page.
PAGE_STUDENT = PAGE_STUDENT.replace("/*CSS*/", CSS)
PAGE_SCREEN = PAGE_SCREEN.replace("/*CSS*/", CSS)
PAGE_LOGIN = PAGE_LOGIN.replace("/*CSS*/", CSS)
PAGE_ADMIN = PAGE_ADMIN.replace("/*CSS*/", CSS)
