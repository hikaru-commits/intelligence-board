const state = {
  all: [], filtered: [], index: 0, category: "ALL", paused: false,
  switchMs: 10000, timer: null
};

const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));

function ageLabel(iso){
  if(!iso) return "";
  const d = new Date(iso), diff = Math.max(0, Date.now()-d.getTime());
  const m = Math.floor(diff/60000);
  if(m<60) return `${m}分前`;
  const h = Math.floor(m/60);
  if(h<24) return `${h}時間前`;
  return `${Math.floor(h/24)}日前`;
}

function renderFilters(){
  const cats = ["ALL", ...new Set(state.all.map(x=>x.category).filter(Boolean))];
  $("#filters").innerHTML = cats.map(c => `<button data-cat="${esc(c)}" class="${c===state.category?'active':''}">${esc(c)}</button>`).join("");
  $("#filters").querySelectorAll("button").forEach(b => b.onclick = () => {
    state.category = b.dataset.cat; state.index = 0;
    state.filtered = state.category === "ALL" ? state.all : state.all.filter(x=>x.category===state.category);
    renderFilters(); render();
  });
}

function setHeroImage(item){
  const img = $("#heroImage"), fb = $("#heroFallback");
  if(item.image){
    img.src = item.image; img.hidden = false; fb.hidden = true;
    img.onerror = () => { img.hidden = true; fb.hidden = false; };
  } else {
    img.removeAttribute("src"); img.hidden = true; fb.hidden = false;
  }
}

function render(){
  if(!state.filtered.length){
    $("#heroTitle").textContent = "表示できるニュースがありません";
    $("#heroSummary").textContent = "data/news.json の更新を確認してください。";
    return;
  }
  state.index = (state.index + state.filtered.length) % state.filtered.length;
  const item = state.filtered[state.index];
  setHeroImage(item);
  $("#heroCategory").textContent = item.category || "NEWS";
  $("#heroPriority").textContent = `重要度 ${"★".repeat(Math.max(1, Math.min(5, item.priority||3)))}`;
  $("#heroSource").textContent = item.source || "";
  $("#heroAge").textContent = ageLabel(item.published_at);
  $("#heroTitle").textContent = item.title || "";
  $("#heroSummary").textContent = item.summary || "";
  $("#openArticle").href = item.url || "#";

  const next = [];
  for(let i=1;i<=Math.min(7,state.filtered.length-1);i++) next.push(state.filtered[(state.index+i)%state.filtered.length]);
  $("#queue").innerHTML = next.map((q,i)=>`
    <div class="qitem" data-offset="${i+1}">
      ${q.image ? `<img class="qthumb" src="${esc(q.image)}" alt="">` : `<div class="qthumb qplaceholder">NEWS</div>`}
      <div><div class="qcat">${esc(q.category||"NEWS")}</div>
      <div class="qtitle">${esc(q.title)}</div>
      <div class="qmeta">${esc(q.source||"")} · ${esc(ageLabel(q.published_at))}</div></div>
    </div>`).join("");
  $("#queue").querySelectorAll(".qitem").forEach(el => el.onclick = () => {
    state.index = (state.index + Number(el.dataset.offset)) % state.filtered.length; render(); resetTimer();
  });
}

function resetTimer(){
  clearInterval(state.timer);
  if(!state.paused) state.timer = setInterval(()=>{ state.index++; render(); }, state.switchMs);
}

async function loadNews(){
  try{
    const r = await fetch(`./data/news.json?t=${Date.now()}`, {cache:"no-store"});
    if(!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    state.all = (data.items || []).sort((a,b) => (b.score||0)-(a.score||0) || new Date(b.published_at)-new Date(a.published_at));
    state.filtered = state.category==="ALL" ? state.all : state.all.filter(x=>x.category===state.category);
    $("#updatedAt").textContent = data.updated_at ? `更新 ${new Date(data.updated_at).toLocaleString("ja-JP")}` : "";
    $("#feedStatus").textContent = `${state.all.length}件 / ${data.source_count||0}ソース`;
    renderFilters(); render();
  }catch(e){
    $("#feedStatus").textContent = `ニュース読込エラー: ${e.message}`;
  }
}

async function loadMarket(){
  try{
    const r = await fetch(`./data/stocks.json?t=${Date.now()}`, {cache:"no-store"});
    const data = await r.json();
    $("#marketStatus").textContent = data.status || "";
    $("#ticker").innerHTML = (data.items||[]).map(x => {
      const cls = x.change_pct > 0 ? "pos" : x.change_pct < 0 ? "neg" : "";
      const sign = x.change_pct > 0 ? "+" : "";
      return `<div class="tick"><div class="sym">${esc(x.symbol)} · ${esc(x.name||"")}</div>
        <div class="val">${esc(x.price ?? "—")}</div><div class="chg ${cls}">${sign}${esc(x.change_pct ?? "—")}%</div></div>`;
    }).join("") || `<div class="tick"><div class="sym">MARKET</div><div class="val">未設定</div><div class="chg">APIキー設定後に有効化</div></div>`;
  }catch(e){ $("#marketStatus").textContent = "market unavailable"; }
}

$("#prevBtn").onclick = ()=>{state.index--;render();resetTimer()};
$("#nextBtn").onclick = ()=>{state.index++;render();resetTimer()};
$("#pauseBtn").onclick = ()=>{
  state.paused = !state.paused;
  $("#pauseBtn").textContent = state.paused ? "再開" : "一時停止";
  resetTimer();
};

setInterval(()=> $("#clock").textContent = new Date().toLocaleString("ja-JP",{hour:"2-digit",minute:"2-digit",second:"2-digit"}),1000);
$("#switchSeconds").textContent = state.switchMs/1000;
loadNews(); loadMarket(); resetTimer();
setInterval(loadNews, 5*60*1000);
setInterval(loadMarket, 5*60*1000);
