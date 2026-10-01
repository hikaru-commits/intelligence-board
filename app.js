const state = {
  all: [], filtered: [], index: 0, category: "ALL",
  paused: false, focus: false, switchMs: 12000, timer: null,
  query: "", sort: "smart"
};

const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({
  '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'
}[c]));

function ageLabel(iso){
  if(!iso) return "";
  const diff = Math.max(0, Date.now() - new Date(iso).getTime());
  const m = Math.floor(diff/60000);
  if(m < 60) return `${m}分前`;
  const h = Math.floor(m/60);
  if(h < 24) return `${h}時間前`;
  return `${Math.floor(h/24)}日前`;
}

function sourceLabel(item){
  if(item.source_type === "x") return "X話題";
  if(item.official) return "公式";
  return "報道";
}

function signalLabel(item){
  return item.signal || (item.priority >= 5 ? "HIGH" : item.priority >= 4 ? "MEDIUM" : "LOW");
}

function searchable(item){
  return [
    item.title, item.title_ja, item.summary, item.summary_ja,
    item.why_it_matters, ...(item.key_points || []), item.source, item.category
  ].filter(Boolean).join(" ").toLowerCase();
}

function smartScore(item){
  const ageHours = Math.max(0,(Date.now()-new Date(item.published_at).getTime())/3600000);
  const freshness = Math.max(0,36-ageHours);
  const signal = signalLabel(item)==="HIGH" ? 35 : signalLabel(item)==="MEDIUM" ? 18 : 4;
  return (item.score||0) + signal + freshness*.35 + (item.source_type==="x" ? Math.min(20,(item.engagement_score||0)/2) : 0);
}

function applyFilter(){
  let list = state.category === "ALL" ? [...state.all] : state.all.filter(x => x.category === state.category);
  if(state.query){
    list = list.filter(x => searchable(x).includes(state.query));
  }
  if(state.sort === "newest"){
    list.sort((a,b)=>new Date(b.published_at)-new Date(a.published_at));
  }else if(state.sort === "priority"){
    list.sort((a,b)=>(b.priority||0)-(a.priority||0) || new Date(b.published_at)-new Date(a.published_at));
  }else{
    list.sort((a,b)=>smartScore(b)-smartScore(a));
  }
  state.filtered = list;
  if(state.index >= list.length) state.index = 0;
}

function renderFilters(){
  const cats = ["ALL", ...new Set(state.all.map(x=>x.category).filter(Boolean))];
  $("#filters").innerHTML = cats.map(c =>
    `<button data-cat="${esc(c)}" class="${c===state.category?'active':''}">${esc(c)}</button>`
  ).join("");
  $("#filters").querySelectorAll("button").forEach(b => b.onclick = () => {
    state.category = b.dataset.cat;
    state.index = 0;
    applyFilter();
    renderFilters();
    render();
    resetTimer();
  });
}

function setImage(item){
  const wrap = $("#thumbWrap"), img = $("#mainImage"), cap = $("#thumbCaption");
  if(!item.image){
    wrap.hidden = true;
    img.removeAttribute("src");
    return;
  }
  wrap.hidden = false;
  img.src = item.image;
  cap.textContent = item.source || "";
  img.onerror = () => { wrap.hidden = true; };
}

function renderKeyPoints(item){
  const points = (item.key_points || []).filter(Boolean).slice(0,3);
  $("#keyPointSection").hidden = points.length === 0;
  $("#keyPoints").innerHTML = points.map(p => `<li>${esc(p)}</li>`).join("");
}

function renderWhy(item){
  const why = item.why_it_matters || "";
  $("#whySection").hidden = !why;
  $("#whyItMatters").textContent = why;
}

function renderQueue(){
  const source = state.filtered.length ? state.filtered : state.all;
  const next = [];
  const primaryIds = new Set();
  for(let i=1; i<=source.length && next.length<7; i++){
    const q = source[(state.index+i)%source.length];
    if(!q || primaryIds.has(q.id)) continue;
    primaryIds.add(q.id);
    next.push(q);
  }
  // If selected category has too few items, supplement with overall high-signal stories.
  if(next.length < 7){
    for(const q of [...state.all].sort((a,b)=>smartScore(b)-smartScore(a))){
      if(next.length >= 7) break;
      if(primaryIds.has(q.id)) continue;
      primaryIds.add(q.id); next.push(q);
    }
  }

  $("#queue").innerHTML = next.map(q => `
    <div class="qitem" data-id="${esc(q.id)}">
      ${q.image ? `<img class="qthumb" src="${esc(q.image)}" alt="">` : `<div class="qplaceholder">${q.source_type==="x"?"X":"NEWS"}</div>`}
      <div>
        <div class="qtop"><span class="qcat">${esc(q.category||"NEWS")}</span><span class="qsignal">${esc(signalLabel(q))}</span></div>
        <div class="qtitle">${esc(q.title_ja || q.title || "")}</div>
        <div class="qmeta">${esc(sourceLabel(q))} · ${esc(q.source||"")} · ${esc(ageLabel(q.published_at))}</div>
      </div>
    </div>`).join("");

  $("#queue").querySelectorAll(".qitem").forEach(el => el.onclick = () => selectById(el.dataset.id));
}

function selectById(id){
  let idx = state.filtered.findIndex(x=>x.id===id);
  if(idx < 0){
    state.category = "ALL"; applyFilter(); renderFilters();
    idx = state.filtered.findIndex(x=>x.id===id);
  }
  if(idx >= 0){ state.index = idx; render(); resetTimer(); }
}

function renderTopStories(){
  const stories = [...state.all].filter(x=>x.source_type!=="x").sort((a,b)=>smartScore(b)-smartScore(a)).slice(0,6);
  $("#topStories").innerHTML = stories.map(x=>`
    <div class="story-mini" data-id="${esc(x.id)}">
      <div class="sm-top">${esc(sourceLabel(x))} · ${esc(x.category||"")}</div>
      <div class="sm-title">${esc(x.title_ja || x.title || "")}</div>
      <div class="sm-meta">${esc(x.source||"")} · ${esc(ageLabel(x.published_at))}</div>
    </div>`).join("");
  $("#topStories").querySelectorAll(".story-mini").forEach(el => el.onclick = ()=>selectById(el.dataset.id));
}

function renderSocial(){
  const items = [...state.all].filter(x=>x.source_type==="x").sort((a,b)=>(b.engagement_score||0)-(a.engagement_score||0)).slice(0,4);
  $("#socialStatus").textContent = items.length ? `${items.length}件表示` : "X未接続";
  $("#socialPulse").innerHTML = items.length ? items.map(x=>`
    <div class="social-item" data-id="${esc(x.id)}">
      <div class="social-source">${esc(x.source||"X")} · 話題度 ${esc(x.engagement_score||0)}</div>
      <div class="social-title">${esc(x.title_ja || x.title || "")}</div>
    </div>`).join("") : `<div class="social-empty">X APIを接続すると、AI分野の注目投稿・解説がここに入ります。</div>`;
  $("#socialPulse").querySelectorAll(".social-item").forEach(el=>el.onclick=()=>selectById(el.dataset.id));
}

function renderAlert(){
  const high = [...state.all].filter(x=>signalLabel(x)==="HIGH" && ((Date.now()-new Date(x.published_at).getTime()) < 24*3600000))
    .sort((a,b)=>smartScore(b)-smartScore(a))[0];
  const strip = $("#alertStrip");
  if(!high){ strip.hidden = true; return; }
  strip.hidden = false;
  $("#alertText").textContent = high.title_ja || high.title;
  $("#alertOpenBtn").onclick = ()=>selectById(high.id);
}

function render(){
  if(!state.filtered.length){
    $("#mainTitle").textContent = "表示できる記事がありません";
    $("#brief").textContent = "検索条件またはカテゴリを変更してください。";
    $("#keyPointSection").hidden = true;
    $("#whySection").hidden = true;
    $("#queue").innerHTML = "";
    return;
  }

  state.index = (state.index + state.filtered.length) % state.filtered.length;
  const item = state.filtered[state.index];

  const type = sourceLabel(item);
  $("#sourceTypeBadge").textContent = type;
  $("#categoryBadge").textContent = item.category || "NEWS";

  const sig = signalLabel(item);
  $("#signalBadge").textContent = sig;
  $("#signalBadge").className = `badge signal ${sig.toLowerCase()}`;

  $("#sourceName").textContent = item.source || "";
  $("#publishedAge").textContent = ageLabel(item.published_at);

  const hasJaTitle = item.title_ja && item.title_ja.trim() && item.title_ja.trim() !== item.title?.trim();
  $("#originalTitle").textContent = hasJaTitle ? item.title : "";
  $("#originalTitle").hidden = !hasJaTitle;

  $("#mainTitle").textContent = item.title_ja || item.title || "";
  $("#brief").textContent = item.summary_ja || item.summary || "";
  $("#openArticle").href = item.url || "#";
  $("#positionText").textContent = `${state.index+1} / ${state.filtered.length}`;

  renderKeyPoints(item);
  renderWhy(item);
  setImage(item);
  renderQueue();
}

function resetTimer(){
  clearInterval(state.timer);
  if(!state.paused){
    state.timer = setInterval(()=>{
      if(state.filtered.length){ state.index = (state.index+1)%state.filtered.length; render(); }
    }, state.switchMs);
  }
}

async function loadNews(){
  try{
    const r = await fetch(`./data/news.json?t=${Date.now()}`, {cache:"no-store"});
    if(!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    state.all = data.items || [];
    applyFilter();
    renderFilters();
    render();
    renderTopStories();
    renderSocial();
    renderAlert();

    const when = data.updated_at ? new Date(data.updated_at).toLocaleString("ja-JP") : "—";
    $("#feedMeta").textContent = `${state.all.length}件 · 更新 ${when}`;
    $("#statusText").textContent = `${state.all.length} items · ${data.source_count||0} sources · ${data.enriched_count||0} JP enriched · ${data.content_extracted_count||0} full-text`;
    $("#versionBadge").textContent = data.version || "v1.0";
  }catch(e){
    $("#statusText").textContent = `ニュース読込エラー: ${e.message}`;
  }
}

async function loadMarket(){
  try{
    const r = await fetch(`./data/stocks.json?t=${Date.now()}`, {cache:"no-store"});
    const data = await r.json();
    const items = data.items || [];
    $("#marketStatus").textContent = data.status || (items.length ? "updated" : "未設定");
    $("#ticker").innerHTML = items.map(x=>{
      const cls = x.change_pct>0 ? "pos" : x.change_pct<0 ? "neg" : "";
      const sign = x.change_pct>0 ? "+" : "";
      return `<div class="tick"><span class="sym">${esc(x.symbol)} ${esc(x.name||"")}</span><span class="val">${esc(x.price??"—")}</span><span class="chg ${cls}">${sign}${esc(x.change_pct??"—")}%</span></div>`;
    }).join("") || `<div class="tick"><span class="sym">MARKET</span><span class="val">未設定</span></div>`;
  }catch(e){
    $("#marketStatus").textContent = "unavailable";
  }
}

$("#prevBtn").onclick = ()=>{ if(state.filtered.length){state.index--;render();resetTimer()} };
$("#nextBtn").onclick = ()=>{ if(state.filtered.length){state.index++;render();resetTimer()} };
$("#pauseBtn").onclick = ()=>{
  state.paused = !state.paused;
  $("#pauseBtn").textContent = state.paused ? "Resume" : "Pause";
  $("#pauseBtn").classList.toggle("active",state.paused);
  resetTimer();
};
$("#focusModeBtn").onclick = ()=>{
  state.focus = !state.focus;
  document.body.classList.toggle("focus-mode",state.focus);
  $("#focusModeBtn").classList.toggle("active",state.focus);
};
$("#refreshBtn").onclick = ()=>{ loadNews(); loadMarket(); };
$("#searchInput").addEventListener("input",e=>{
  state.query = e.target.value.trim().toLowerCase();
  state.index = 0; applyFilter(); render();
});
$("#sortSelect").addEventListener("change",e=>{
  state.sort = e.target.value; state.index=0; applyFilter(); render();
});

setInterval(()=>$("#clock").textContent = new Date().toLocaleTimeString("ja-JP",{hour:"2-digit",minute:"2-digit",second:"2-digit"}),1000);
$("#switchSeconds").textContent = state.switchMs/1000;

loadNews();
loadMarket();
resetTimer();
setInterval(loadNews,5*60*1000);
setInterval(loadMarket,5*60*1000);
