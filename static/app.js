/* Ekologický detektív – klient. Bez externých služieb alebo knižníc. */
'use strict';

const $ = (id) => document.getElementById(id);
const esc = (input) => String(input ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const TOK_PLAYER = 'eko_player_token';
const TOK_ADMIN = 'eko_admin_token';
let currentView = 'home';
let questions = [];
let playerToken = localStorage.getItem(TOK_PLAYER) || '';
let adminToken = sessionStorage.getItem(TOK_ADMIN) || '';
let playerData = null;
let adminData = null;
let currentQuestion = null;
let chosenQuestion = 1;
let busy = false;
let toastTimer;
let lastPlayerSignature = '';

function notify(message, error = false) {
  const t = $('toast');
  t.textContent = message;
  t.classList.remove('hidden');
  t.classList.toggle('error', error);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add('hidden'), 3600);
}
function view(id) {
  document.querySelectorAll('.view').forEach(v => v.classList.toggle('hidden', v.id !== id));
  currentView = id;
  window.scrollTo({top: 0, behavior: 'instant'});
}
async function api(url, method = 'GET', data = null, token = '') {
  const opts = { method, headers: {'Accept': 'application/json'} };
  if (data !== null) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(data);
  }
  if (token) opts.headers['Authorization'] = `Bearer ${token}`;
  let res;
  try { res = await fetch(url, opts); }
  catch (e) { throw new Error('Server je nedostupný. Skontroluj internetové pripojenie alebo spustený program.'); }
  let json;
  try { json = await res.json(); } catch (e) { throw new Error('Server vrátil nečakanú odpoveď.'); }
  if (!res.ok) throw new Error(json.error || `Chyba ${res.status}`);
  return json;
}
function progressFill(n) {
  $('progress-label').textContent = `OTÁZKA ${Math.min(n+1,questions.length)} / ${questions.length}`;
  $('progress-fill').style.width = (100 * n / questions.length) + '%';
}
function setPlayerState(data, force = false) {
  const signature = JSON.stringify({status: data.status, answers: data.answers, nickname: data.player?.nickname});
  playerData = data;
  if (force || signature !== lastPlayerSignature) {
    lastPlayerSignature = signature;
    renderQuiz();
  }
}
async function loadPlayer(force = false) {
  if (!playerToken) return false;
  try {
    const data = await api('/api/player/state', 'GET', null, playerToken);
    setPlayerState(data, force);
    return true;
  } catch (e) {
    playerToken = '';
    localStorage.removeItem(TOK_PLAYER);
    if (currentView === 'play') { notify(e.message, true); view('join'); }
    return false;
  }
}
function renderQuiz() {
  if (!playerData || !questions.length) return;
  const ans = playerData.answers;
  const answered = ans.length;
  const score = ans.filter(a => a.correct).length * 100;
  $('player-name').textContent = `✦ ${playerData.player.nickname}`;
  $('player-points').textContent = `${score} / ${questions.length * 100} BODOV`;
  if (currentQuestion === null) currentQuestion = answered;
  if (currentQuestion > answered) currentQuestion = answered;
  if (currentQuestion < 0) currentQuestion = 0;
  if (currentQuestion === questions.length || (answered === questions.length && currentQuestion >= questions.length)) {
    $('progress-label').textContent = 'HOTOVO';
    $('progress-fill').style.width = '100%';
    $('quiz-area').innerHTML = `<div class="finish-card"><div class="finish-icon">🏆</div><p class="eyebrow">MISIA SPLNENÁ</p><h3>Výborne, ${esc(playerData.player.nickname)}!</h3><div class="big-score">${score} / ${questions.length*100}</div><p>Správne si odpovedal na ${score/100} zo ${questions.length} otázok.<br>Výsledky už vidí autor vo svojom paneli.</p><button class="btn btn-outline" id="view-final" type="button">Zobraziť moje odpovede ↓</button><div id="player-final" class="hidden"></div></div>`;
    $('view-final').onclick = () => {
      $('player-final').innerHTML = questions.map((q,i) => {
        const a=ans.find(x => x.question_id===q.id);
        return `<div class="answer-feedback ${a?.correct?'':'bad'}" style="text-align:left"><strong>${i+1}. ${esc(q.title)}</strong>${a?.correct?'✓':'✕'} ${esc(q.options[a?.selected ?? 0])}<br><small>${esc(a?.explanation || '')}</small></div>`;
      }).join('');
      $('player-final').classList.toggle('hidden');
    };
    return;
  }
  progressFill(currentQuestion);
  const q = questions[currentQuestion];
  const a = ans.find(x => x.question_id === q.id);
  const isStopped = playerData.status !== 'running';
  $('quiz-area').innerHTML = `
    <div class="question-meta"><span>${esc(q.tag.toUpperCase())} / 0${q.id}</span><span class="difficulty">${esc(q.difficulty.toUpperCase())}</span></div>
    <h3 class="question-title">${esc(q.title)}</h3>
    <p class="question-context">${esc(q.context)}</p>
    <div class="options">${q.options.map((option,i) => `<button class="option ${a && a.correct_index===i?'correct-answer':''} ${a && a.selected===i ? (a.correct?'selected-good':'selected-bad') :''}" data-option="${i}" type="button" ${a||isStopped?'disabled':''}><span class="option-letter">${'ABCD'[i]}</span><span>${esc(option)}</span></button>`).join('')}</div>
    ${a ? `<div class="answer-feedback ${a.correct?'':'bad'}"><strong>${a.correct?'✓ Správna odpoveď! +100 bodov':'✕ Tentokrát nie. 0 bodov'}</strong>${esc(a.explanation)}</div><button class="btn btn-primary btn-wide" id="continue-btn" type="button">${currentQuestion+1 === questions.length?'Zobraziť výsledok':'Ďalšia otázka →'}</button>` : (isStopped?'<div class="answer-feedback bad">Autor hru pozastavil alebo ukončil. Odpovedať teraz nemožno.</div>':'<div class="form-hint" style="margin-top:17px">Vyber jednu odpoveď. Po potvrdení ju už nezmeníš.</div>')}
  `;
  if (a) {
    $('continue-btn').onclick = () => { currentQuestion++; renderQuiz(); };
  } else if (!isStopped) {
    document.querySelectorAll('#quiz-area [data-option]').forEach(btn => {
      btn.onclick = () => submitAnswer(q.id, Number(btn.dataset.option));
    });
  }
}
async function submitAnswer(id, selected) {
  if (busy) return;
  busy = true;
  document.querySelectorAll('#quiz-area [data-option]').forEach(el => el.disabled = true);
  try {
    const data = await api('/api/answer', 'POST', {question_id:id, selected}, playerToken);
    setPlayerState(data, true);
  } catch(e) {
    notify(e.message, true);
    await loadPlayer(true);
  } finally { busy=false; }
}
async function loginPlayer(event) {
  event.preventDefault();
  try {
    const data = await api('/api/join','POST', {
      code:$('join-code').value.trim().toUpperCase(),
      nickname:$('join-nick').value.trim(),
      team:$('join-team').value,
    });
    playerToken = data.player_token;
    localStorage.setItem(TOK_PLAYER, playerToken);
    currentQuestion = null;
    lastPlayerSignature = '';
    await loadPlayer(true);
    view('play');
  } catch(e) { notify(e.message,true); }
}
async function loginAdmin(event) {
  event.preventDefault();
  try {
    const data = await api('/api/admin/login','POST',{pin:$('admin-pin').value});
    adminToken = data.admin_token;
    sessionStorage.setItem(TOK_ADMIN, adminToken);
    $('admin-pin').value = '';
    await refreshAdmin();
    view('admin');
  } catch(e) { notify(e.message,true); }
}
async function refreshAdmin() {
  if (!adminToken) return false;
  try {
    adminData = await api('/api/admin/stats','GET',null,adminToken);
    renderAdmin();
    return true;
  } catch(e) {
    if (e.message.includes('prístup') || e.message.includes('autora')) {
      adminToken=''; sessionStorage.removeItem(TOK_ADMIN); view('admin-login');
    }
    notify(e.message,true);
    return false;
  }
}
async function adminStatus(status) {
  try {
    adminData=await api('/api/admin/status','POST',{status},adminToken);
    renderAdmin();
    notify(status==='running'?'Kvíz je spustený.':status==='closed'?'Kvíz bol ukončený.':'Kvíz bol pozastavený.');
  } catch(e) { notify(e.message,true); }
}
async function adminReset() {
  if (!confirm('Naozaj chceš začať novú hru? VŠETCI hráči aj odpovede sa nenávratne vymažú. Najprv exportuj CSV.')) return;
  try {
    adminData = await api('/api/admin/reset','POST',{},adminToken);
    renderAdmin();
    notify('Nová miestnosť je pripravená. Nový kód: '+adminData.code);
  } catch(e) { notify(e.message,true); }
}
function percent(part,total) {return total ? Math.round(part*100/total) : 0;}
function formatDuration(sec) { return sec === null ? '—' : (sec < 60 ? `${Math.round(sec)} s` : `${Math.floor(sec/60)} min ${Math.round(sec%60)} s`); }
function renderAdmin() {
  const d = adminData;
  if (!d) return;
  $('room-code').textContent = d.code;
  $('room-state').textContent = ({waiting:'Čaká na spustenie',running:'Hra prebieha',closed:'Hra je ukončená'})[d.status] || d.status;
  $('start-btn').disabled = d.status === 'running';
  $('pause-btn').disabled = d.status !== 'running';
  $('end-btn').disabled = d.status === 'closed';
  $('stat-players').textContent = d.players_count;
  $('stat-answers').textContent = d.total_answers;
  $('stat-accuracy').textContent = `${d.accuracy} %`;
  $('stat-completed').textContent = d.completed_count;
  $('leaderboard').innerHTML = d.players.length ? `<table><thead><tr><th>#</th><th>HRÁČ</th><th>SPRÁVNE</th><th>BODY</th><th>ČAS</th></tr></thead><tbody>${d.players.map((p,i) => `<tr><td class="medal">${i+1}${i===0?' 🏅':''}</td><td><div class="mini-name">${esc(p.nickname)}</div><div class="mini-team">${esc(p.team)}</div></td><td>${p.correct_count} / ${d.questions_count}</td><td class="score">${p.score}</td><td>${formatDuration(p.duration_sec)}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">Zatiaľ sa nepripojil žiadny hráč. Spusti kvíz a zdieľaj odkaz.</div>';
  $('question-overview').innerHTML = d.question_stats.map(q => `<div class="overview-row"><div class="overview-head"><span>0${q.id} · ${esc(q.tag)}</span><strong>${q.answered?percent(q.correct_count,q.answered)+' %':'—'} <small>(${q.answered})</small></strong></div><div class="bar-track"><div class="bar-inner" style="width:${percent(q.correct_count,q.answered)}%"></div></div></div>`).join('');
  if (!$('question-filter').options.length) {
    $('question-filter').innerHTML = d.question_stats.map(q=>`<option value="${q.id}">Otázka ${q.id}: ${esc(q.tag)}</option>`).join('');
  }
  $('question-filter').value = String(chosenQuestion);
  const q = d.question_stats.find(x=>x.id===chosenQuestion) || d.question_stats[0];
  if (q) {
    $('question-detail').innerHTML = `<p class="question-full">${esc(q.title)}</p><div class="answer-bars">${q.options.map((option,i) => `<div class="answer-bar ${i===q.correct_index?'is-correct':''}"><div class="answer-bar-header"><span><b>${'ABCD'[i]}.</b> ${esc(option)}</span><strong>${q.counts[i]}</strong></div><div class="bar-track"><div class="bar-inner" style="width:${percent(q.counts[i],q.answered)}%"></div></div><small>${percent(q.counts[i],q.answered)} % odpovedí ${i===q.correct_index?'<span class="correct-indicator">· SPRÁVNE</span>':''}</small></div>`).join('')}</div>`;
  }
  $('answer-matrix').innerHTML = d.players.length?`<table><thead><tr><th>HRÁČ</th>${d.question_stats.map(q=>`<th title="${esc(q.tag)}">OT. ${q.id}</th>`).join('')}<th>BODY</th></tr></thead><tbody>${d.players.map(p=>`<tr><td><div class="mini-name">${esc(p.nickname)}</div><div class="mini-team">${esc(p.team)}</div></td>${d.question_stats.map(q=>{const a=p.answers[String(q.id)];return `<td class="matrix-cell ${a?(a.correct?'yes':'no'):'none'}" title="${a?esc(a.option):'Zatiaľ bez odpovede'}">${a?(a.correct?'✓':'✕'):'–'}</td>`}).join('')}<td class="score">${p.score}</td></tr>`).join('')}</tbody></table>`:'<div class="empty">Po prihlásení hráčov uvidíš, na ktorých otázkach uspeli a ktoré im nevyšli. Podrž kurzor nad symbolom pre presnú odpoveď.</div>';
  $('team-list').innerHTML = d.teams.length?d.teams.map((t,i)=>`<div class="team-row"><div><b>${i+1}. ${esc(t.name)}</b><p>${t.players} hráčov · ${t.correct_sum} správnych odpovedí</p></div><strong>${t.average_score} b</strong></div>`).join(''):'<div class="empty">Tímy sú voliteľné. Hráči sa môžu pripojiť aj jednotlivo.</div>';
}
function csvValue(s) {
  let value=String(s ?? '');
  if (/^[=+@\-\t\r]/.test(value)) value="'"+value; // Prevencia spustenia vzorcov v Exceli
  return '"'+value.replace(/"/g,'""')+'"';
}
function exportCSV() {
  if (!adminData) return;
  const cols = ['Hráč','Tím','Body','Počet správnych','Počet odpovedí','Čas (sekundy)'];
  adminData.question_stats.forEach(q=>{cols.push(`Otázka ${q.id} - zvolená možnosť`,`Otázka ${q.id} - odpoveď`,`Otázka ${q.id} - správne`);});
  const rows = [cols];
  adminData.players.forEach(p=>{
    const vals=[p.nickname,p.team,p.score,p.correct_count,p.answered_count,p.duration_sec??''];
    adminData.question_stats.forEach(q=>{
      const a=p.answers[String(q.id)];
      vals.push(a?'ABCD'[a.selected]:'',a?a.option:'',a?(a.correct?'ÁNO':'NIE'):'');
    });
    rows.push(vals);
  });
  const csv='\ufeff'+rows.map(row=>row.map(csvValue).join(';')).join('\r\n');
  const blob=new Blob([csv],{type:'text/csv;charset=utf-8'});
  const uri=URL.createObjectURL(blob);
  const a=document.createElement('a');a.href=uri;a.download=`eko-vysledky-${adminData.code}.csv`;
  document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(uri),500);
  notify('CSV s výsledkami sa sťahuje.');
}
async function copyInvite() {
  if (!adminData) return;
  const url=location.protocol === 'https:' ? `${location.origin}/?kod=${adminData.code}` : ((adminData.join_urls||[])[0] || `${location.origin}/?kod=${adminData.code}`);
  try {
    await navigator.clipboard.writeText(url);
    notify('Odkaz skopírovaný: '+url);
  } catch (e) {
    window.prompt('Skopíruj odkaz pre spolužiakov:',url);
  }
}
async function initialize() {
  $('player-choice').onclick=()=>view('join');
  $('admin-choice').onclick=async()=>{if(adminToken && await refreshAdmin()) view('admin'); else view('admin-login');};
  $('go-home').onclick=()=>view('home');
  document.querySelectorAll('[data-nav]').forEach(el=>el.onclick=()=>view(el.dataset.nav));
  $('join-form').addEventListener('submit',loginPlayer);
  $('admin-login-form').addEventListener('submit',loginAdmin);
  $('start-btn').onclick=()=>adminStatus('running');
  $('pause-btn').onclick=()=>adminStatus('waiting');
  $('end-btn').onclick=()=>adminStatus('closed');
  $('reset-btn').onclick=adminReset;
  $('copy-link').onclick=copyInvite;
  $('export-csv').onclick=exportCSV;
  $('question-filter').onchange=(event)=>{chosenQuestion=Number(event.target.value);renderAdmin();};
  const codeFromLink = new URLSearchParams(window.location.search).get('kod');
  if (codeFromLink) $('join-code').value=codeFromLink.toUpperCase();
  try {const resp=await api('/api/questions');questions=resp.questions;}catch(e){notify(e.message,true);}
  const playerOk=await loadPlayer(true);
  if (location.pathname === '/admin') {
    if(adminToken && await refreshAdmin()) view('admin'); else view('admin-login');
  } else if (codeFromLink) {
    if(playerOk) view('play'); else view('join');
  } else if (playerOk) {
    view('play');
  } else {view('home');}
  setInterval(async()=>{
    if (currentView==='admin' && adminToken) {
      try {adminData=await api('/api/admin/stats','GET',null,adminToken);renderAdmin();}catch(e) { /* bežná strata spojenia */ }
    } else if (currentView==='play' && playerToken) {
      try {
        const data=await api('/api/player/state','GET',null,playerToken);
        setPlayerState(data);
      } catch(e){ /* pri výpadku siete hráč zostáva na aktuálnej otázke */ }
    }
  },2200);
}
document.addEventListener('DOMContentLoaded',initialize);
