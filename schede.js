/* Schede giocatore (create dai giocatori con il bot Telegram @rakings_vgc_bot e approvate dall'admin).
   Si carica solo quando si cerca un giocatore. Dati: schede/pubbliche.json, schede/team.json, avatar in schede/img/,
   loghi in schede/team/, sfondi dei tipi in img/tipi/. CP dalla CP bar (seconda repo, tutte le zone elencate in CP_ZONE).
   Niente immagini dei Pokémon: le squadre usano i bollini colorati del sito (phHtml). */
(function(){
"use strict";
var BASE="schede/",TIPI_DIR="img/tipi/";
var CPD="https://rakings.github.io/VGCdatiAK/dati/cp/";
/* zone della CP bar: per ora solo l'Europa; le altre si aggiungono qui quando il collettore le prepara */
var CP_ZONE=[{file:"vg-europe-masters",zona:"Europa"}];
var PUB=null,TEAM=null,LOAD=null,CPP=null,IDX={};
var COL={normal:["#bdbc8e","#77764f"],fire:["#F7A04B","#c2410c"],water:["#4f7fe0","#173d9e"],electric:["#e8c51a","#8a6a00"],grass:["#8fd65c","#3f8f22"],ice:["#8cc3e0","#2f6f98"],fighting:["#ff7a00","#c41a00"],poison:["#c25bc0","#6b1f6a"],ground:["#ecd08a","#a8812c"],flying:["#7aa7ff","#2c5bd6"],psychic:["#fb7aa2","#c21e58"],bug:["#c0d23a","#6d7c0c"],rock:["#cbb84e","#7c6d13"],ghost:["#9478b8","#4a2f6e"],dragon:["#8f5cff","#3d14b8"],dark:["#3b2a6a","#0b0b26"],steel:["#5a5a66","#1a1a20"],fairy:["#eba3c6","#b04a82"]};
var NOMI={normal:"Normale",fire:"Fuoco",water:"Acqua",electric:"Elettro",grass:"Erba",ice:"Ghiaccio",fighting:"Lotta",poison:"Veleno",ground:"Terra",flying:"Volante",psychic:"Psico",bug:"Coleottero",rock:"Roccia",ghost:"Spettro",dragon:"Drago",dark:"Buio",steel:"Acciaio",fairy:"Folletto"};
/* paesi: nome (it/en) -> [alpha-2, alpha-3]; la CP bar usa alpha-3, la ricerca alpha-2 */
var PAESI={IT:"ITA",ES:"ESP",FR:"FRA",DE:"DEU",GB:"GBR",PT:"PRT",NL:"NLD",BE:"BEL",CH:"CHE",AT:"AUT",PL:"POL",CZ:"CZE",SK:"SVK",HU:"HUN",RO:"ROU",BG:"BGR",GR:"GRC",HR:"HRV",SI:"SVN",RS:"SRB",IE:"IRL",DK:"DNK",SE:"SWE",NO:"NOR",FI:"FIN",IS:"ISL",EE:"EST",LV:"LVA",LT:"LTU",UA:"UKR",TR:"TUR",LU:"LUX",MT:"MLT",CY:"CYP",US:"USA",CA:"CAN",MX:"MEX",BR:"BRA",AR:"ARG",CL:"CHL",CO:"COL",PE:"PER",UY:"URY",JP:"JPN",KR:"KOR",CN:"CHN",TW:"TWN",HK:"HKG",SG:"SGP",MY:"MYS",PH:"PHL",TH:"THA",ID:"IDN",AU:"AUS",NZ:"NZL",ZA:"ZAF",SA:"SAU",AE:"ARE",IL:"ISR",SM:"SMR",VA:"VAT",MC:"MCO",AD:"AND"};
function E(x){return String(x==null?"":x).replace(/[&<>"']/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
function pn(s){return String(s||"").normalize("NFD").replace(/[̀-ͯ]/g,"").toLowerCase().replace(/[^a-z0-9 ]+/g," ").replace(/\s+/g," ").trim()}
function app(){try{return sessionStorage.getItem("vgc-inapp")==="1"}catch(e){return false}}
var NOMEPAESE=null;
function codice(paese){paese=pn(paese);if(!paese)return"";if(paese.length===2&&PAESI[paese.toUpperCase()])return paese.toUpperCase();
  if(!NOMEPAESE){NOMEPAESE={};["it","en","es","fr","de","pt"].forEach(function(l){var dn;try{dn=new Intl.DisplayNames([l],{type:"region"})}catch(e){return}
    Object.keys(PAESI).forEach(function(c){try{NOMEPAESE[pn(dn.of(c))]=c}catch(e){}})});NOMEPAESE["inghilterra"]="GB";NOMEPAESE["england"]="GB";NOMEPAESE["uk"]="GB";NOMEPAESE["usa"]="US";NOMEPAESE["stati uniti"]="US"}
  return NOMEPAESE[paese]||""}
function bandiera(cc){if(!cc||cc.length!==2)return"";return String.fromCodePoint(127397+cc.charCodeAt(0),127397+cc.charCodeAt(1))}
function J(u){return fetch(u+(u.indexOf("?")<0?"?":"&")+"t="+Math.floor(Date.now()/300000),{cache:"no-cache"}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json()})}

/* carica le schede pubbliche una volta: indice per nome normalizzato */
function carica(){stile();if(LOAD)return LOAD;LOAD=Promise.all([J(BASE+"pubbliche.json").catch(function(){return{}}),J(BASE+"team.json").catch(function(){return{}})]).then(function(a){
  PUB=a[0]||{};TEAM=a[1]||{};IDX={};Object.keys(PUB).forEach(function(id){var s=PUB[id];s.id=id;s.cc=codice(s.paese);(IDX[pn(s.nome)]=IDX[pn(s.nome)]||[]).push(s)});return PUB}).catch(function(){PUB={};TEAM={};return PUB});return LOAD}
/* scheda di un giocatore della ricerca (nome + paese): stesso nome; se ci sono omonimi decide il paese */
function trova(nome,cc){var l=IDX[pn(nome)];if(!l||!l.length)return null;if(l.length===1)return(!cc||!l[0].cc||l[0].cc===cc)?l[0]:null;
  return l.filter(function(s){return s.cc&&s.cc===cc})[0]||null}
function avatarHtml(s,cls){var ini=E(String(s.nome||"?").split(/\s+/).map(function(w){return w.charAt(0)}).join("").slice(0,2).toUpperCase());
  return s.avatar?'<img class="'+cls+'" alt="" loading="lazy" src="'+BASE+'img/'+E(s.id)+'.webp?v='+(s.aggiornata||0)+'">':'<span class="'+cls+' sk-ini">'+ini+'</span>'}
/* pulsante nella ricerca, accanto al nome */
function bottone(nome,cc){var s=trova(nome,cc);if(!s)return"";
  return '<button type="button" class="pr-sch" data-sch="'+E(s.id)+'" aria-label="Apri la scheda di '+E(s.nome)+'">'+avatarHtml(s,"pr-sav")+'<span>Scheda</span></button>'}

/* CP: cerca il giocatore in tutte le zone; Pokédata a volte accorcia il cognome («Francesco Pio P») */
function cpCarica(){if(CPP)return CPP;CPP=Promise.all(CP_ZONE.map(function(z){return Promise.all([J(CPD+z.file+".json").catch(function(){return null}),J(CPD+z.file+"-tutti.json").catch(function(){return null})]).then(function(a){return{zona:z.zona,base:a[0],tutti:a[1]}})}));return CPP}
function stessoNome(cpNome,nome){var a=pn(cpNome),b=pn(nome);if(!a||!b)return false;if(a===b)return true;var ta=a.split(" "),tb=b.split(" ");
  if(ta[ta.length-1].length===1&&ta.length<=tb.length){var ok=ta.slice(0,-1).every(function(w,i){return w===tb[i]});return ok&&tb[ta.length-1]&&tb[ta.length-1].charAt(0)===ta[ta.length-1]}return false}
function cpTrova(s){return cpCarica().then(function(zone){var cc3=s.cc?PAESI[s.cc]:"";for(var i=0;i<zone.length;i++){var z=zone[i];if(!z.tutti||!z.tutti.r)continue;
  var c=z.tutti.campi||["pos","rank","name","country","cp"],iN=c.indexOf("name"),iC=c.indexOf("country"),iP=c.indexOf("cp"),iR=c.indexOf("pos")>-1?c.indexOf("pos"):0;
  var hit=z.tutti.r.filter(function(r){return stessoNome(r[iN<0?2:iN],s.nome)&&(!cc3||!r[iC<0?3:iC]||r[iC<0?3:iC]===cc3)});
  if(hit.length===1){var r=hit[0],cp=r[iP<0?4:iP],sg=z.base&&z.base.soglia?z.base.soglia.cp:null;if(!cp)return null;
    return{cp:cp,pos:r[iR],zona:z.zona,soglia:sg,manca:sg&&cp<sg?sg-cp:0}}}
  return null}).catch(function(){return null})}

var CSS='.sk-ov{position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.72);overflow:auto;-webkit-overflow-scrolling:touch;padding:14px 10px 40px}'+
'.sk{position:relative;max-width:760px;margin:0 auto;border-radius:24px;padding:8px 8px 2px;overflow:hidden;isolation:isolate;color:#fff1ef;font:15px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif}'+
'.sk:before,.sk:after{content:"";position:absolute;inset:0;z-index:-1}.sk:before{background:var(--b1);clip-path:polygon(0 0,100% 0,0 100%)}.sk:after{background:var(--b2);clip-path:polygon(100% 0,100% 100%,0 100%)}'+
'.sk-x{position:absolute;top:10px;right:10px;z-index:3;width:38px;height:38px;border-radius:50%;border:0;background:rgba(0,0,0,.55);color:#fff;font-size:20px;cursor:pointer}'+
'.sk-c{background:rgba(29,11,13,.8);border:1.5px solid rgba(255,255,255,.18);border-radius:18px;padding:12px;margin:10px 0 14px}'+
'.sk-hero{background:linear-gradient(180deg,rgba(0,0,0,.05),rgba(0,0,0,.35));border:0;padding:14px 8px 18px;text-shadow:0 1px 3px rgba(0,0,0,.6)}'+
'.sk-hd{display:flex;gap:14px;align-items:center}.sk-avw{flex:none;display:flex;flex-direction:column;align-items:center;gap:7px}'+
'.sk-av{width:92px;height:92px;border-radius:50%;object-fit:cover;border:3px solid rgba(255,255,255,.85);background:#3a1b1f}.sk-ini{display:grid;place-items:center;font-weight:900;font-size:1.6rem;background:linear-gradient(135deg,#e11d2e,#6d28d9)}'+
'.sk-nm{font-size:1.4rem;font-weight:900;line-height:1.1;margin:0}.sk-nk{font-weight:700;margin:3px 0 0;opacity:.95}.sk-ok{color:#bfffe0;font-size:.75rem;font-weight:800}.sk-fr{font-style:italic;margin:6px 0 0;font-size:.92rem}'+
'.sk-lv{display:inline-flex;align-items:center;gap:5px;background:#ff6b78;color:#2a0508;font-weight:900;font-size:.72rem;letter-spacing:.06em;border-radius:999px;padding:3px 9px;text-shadow:none}.sk-lv:before{content:"";width:7px;height:7px;border-radius:50%;background:#2a0508;animation:skp 1.2s infinite}@keyframes skp{50%{opacity:.25}}'+
'.sk-tp{display:inline-flex;gap:6px;margin-top:8px;flex-wrap:wrap}.sk-tp span{font-size:.7rem;font-weight:900;letter-spacing:.04em;border-radius:7px;padding:3px 9px;border:1.5px solid rgba(255,255,255,.5)}'+
'.sk-tm{display:inline-flex;align-items:center;gap:6px;margin-top:8px;padding:4px 10px 4px 4px;border-radius:999px;background:rgba(0,0,0,.35);border:1px solid rgba(255,255,255,.35);color:#fff;font-weight:800;font-size:.85rem;cursor:pointer}.sk-tm img,.sk-tm i{width:24px;height:24px;border-radius:7px;object-fit:cover;display:grid;place-items:center;font-style:normal;font-size:.7rem;background:rgba(255,255,255,.2)}'+
'.sk-so{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}.sk-so a{display:inline-flex;padding:5px 11px;border-radius:999px;background:rgba(0,0,0,.35);border:1.5px solid rgba(255,255,255,.4);color:#fff;text-decoration:none;font-weight:700;font-size:.85rem}'+
'.sk-l{font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:#e0aaa6;font-weight:800;margin:0 0 8px}'+
'.sk-cp{display:flex;align-items:center;gap:12px}.sk-cp b.n{font-size:1.6rem;font-weight:900;color:#ffd21f;white-space:nowrap}.sk-bar{height:10px;border-radius:99px;background:#3a1b1f;margin-top:8px;overflow:hidden}.sk-bar b{display:block;height:100%;background:linear-gradient(90deg,#ffd21f,#ff6b78);border-radius:99px}'+
'.sk-sm{font-size:.8rem;color:#e0aaa6}.sk-r{display:flex;gap:8px;align-items:baseline;border-top:1px solid rgba(255,255,255,.12);padding:7px 2px;font-size:.88rem}.sk-r:first-of-type{border-top:0}.sk-r b{min-width:62px}.sk-r .t{font-size:.65rem;font-weight:800;border-radius:6px;padding:1px 6px;background:rgba(255,255,255,.12)}'+
'.sk-tag{display:inline-block;font-size:.68rem;font-weight:800;border:1.5px dashed #e0aaa6;color:#e0aaa6;border-radius:999px;padding:1px 8px;margin-left:6px;vertical-align:middle}'+
'.sk select{width:100%;padding:10px 12px;border-radius:12px;border:1.5px solid rgba(255,255,255,.2);background:#4a1220;color:#fff;font:inherit;font-weight:700}'+
'.sk-team{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:10px}@media(min-width:700px){.sk-team{grid-template-columns:repeat(3,minmax(0,1fr))}}'+
'.sk-mon{min-width:0;border:1.5px solid rgba(255,255,255,.14);border-radius:14px;padding:8px 10px;background:rgba(0,0,0,.15)}.sk-mon .h{display:flex;align-items:center;gap:6px;min-width:0}.sk-mon .h>div{min-width:0}'+
'.sk-mon .ph{flex:none}.sk-mon b{display:block;font-size:.85rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sk-mon small{display:block;font-size:.72rem;color:#e0aaa6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'+
'.sk-mon .ab{font-size:.72rem;color:#e0aaa6;margin-top:4px}.sk-mon .te{float:right;font-size:.62rem;font-weight:800;border-radius:6px;padding:1px 6px;background:rgba(255,255,255,.15);color:#fff}'+
'.sk-mon ul{list-style:none;padding:0;margin:6px 0 0;display:grid;grid-template-columns:1fr 1fr;gap:3px}.sk-mon li{font-size:.72rem;background:#4a1220;border-radius:6px;padding:2px 5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'+
'.pr-sch{display:inline-flex;align-items:center;gap:5px;margin-left:auto;padding:2px 9px 2px 2px;border-radius:999px;border:1.5px solid currentColor;background:transparent;color:inherit;font:inherit;font-size:.78rem;font-weight:800;cursor:pointer}.pr-sav{width:22px;height:22px;border-radius:50%;object-fit:cover;display:inline-grid;place-items:center;font-size:.6rem;font-weight:900;background:linear-gradient(135deg,#e11d2e,#6d28d9);color:#fff}';
function stile(){if(document.getElementById("sk-css"))return;var st=document.createElement("style");st.id="sk-css";st.textContent=CSS;document.head.appendChild(st)}
function fondo(t,dove){var c=COL[t]||COL.normal;if(t==="fighting")return 'url("'+TIPI_DIR+'fighting.webp") center '+dove+'/100% auto no-repeat,radial-gradient(circle at 50% '+(dove==="bottom"?"85%":"15%")+',#ffd21a,#ff5a00 55%,#c41a00)';
  return 'url("'+TIPI_DIR+t+'.webp") 0 0/320px auto repeat,linear-gradient(160deg,'+c[0]+','+c[1]+')'}
function bollino(n){return typeof window.phHtml==="function"?window.phHtml(n):'<span class="ph" style="width:26px;height:26px;border-radius:50%;background:#666;display:inline-block"></span>'}
function squadraHtml(q){return '<div class="sk-team">'+(q.pokemon||[]).map(function(p){return '<div class="sk-mon"><div class="h">'+bollino(p.pokemon)+'<div><b>'+E(p.pokemon)+'</b><small>'+E(p.strumento||"—")+'</small></div></div>'+
  '<div class="ab">'+E(p.abilita||"")+(p.tera?'<span class="te">'+E(p.tera)+'</span>':'')+'</div><ul>'+(p.mosse||[]).map(function(m){return '<li>'+E(m)+'</li>'}).join("")+'</ul></div>'}).join("")+'</div>'}

/* apre la scheda: ctx = giocatore della ricerca (nome, cc, rows dei risultati, live) */
function apri(id,ctx){var s=PUB&&PUB[id];if(!s)return;stile();ctx=ctx||{};
  var tp=(s.tipi||[]).length?s.tipi:[];var t1=tp[0],t2=tp[1]||tp[0];
  var ov=document.createElement("div");ov.className="sk-ov";ov.setAttribute("role","dialog");ov.setAttribute("aria-label","Scheda di "+s.nome);
  var team=s.team&&TEAM[s.team]?TEAM[s.team]:null;
  var soc=s.social||{},NS={instagram:"Instagram",facebook:"Facebook",x:"X",twitch:"Twitch",youtube:"YouTube",tiktok:"TikTok"};
  var righe=(ctx.rows||[]).slice(0,12);
  var h='<div class="sk" style="'+(t1?'--b1:'+E(fondo(t1,"top"))+';--b2:'+E(fondo(t2,"bottom")):'--b1:linear-gradient(160deg,#4a1220,#1d0b0d);--b2:linear-gradient(160deg,#2c1316,#1d0b0d)')+'">'+
  '<button type="button" class="sk-x" aria-label="Chiudi">×</button>'+
  '<div class="sk-c sk-hero"><div class="sk-hd"><div class="sk-avw">'+avatarHtml(s,"sk-av")+(ctx.live?'<span class="sk-lv">LIVE</span>':'')+'</div><div>'+
  '<p class="sk-nm">'+E(s.nome)+' '+bandiera(s.cc)+'</p>'+(s.nickname?'<p class="sk-nk">@'+E(s.nickname)+' · <span class="sk-ok">✔ profilo verificato</span></p>':'<p class="sk-nk"><span class="sk-ok">✔ profilo verificato</span></p>')+
  (s.frase?'<p class="sk-fr">«'+E(s.frase)+'»</p>':'')+(tp.length?'<div class="sk-tp">'+tp.filter(function(t,i,l){return l.indexOf(t)===i}).map(function(t){return '<span style="background:'+(COL[t]||COL.normal)[0]+'">'+E((NOMI[t]||t).toUpperCase())+'</span>'}).join("")+'</div>':'')+
  (team?'<div><button type="button" class="sk-tm" data-tm="1">'+(team.logo?'<img alt="" src="'+BASE+'team/'+E(s.team)+'.webp">':'<i>'+E(String(team.nome).slice(0,2).toUpperCase())+'</i>')+E(team.nome)+'</button></div>':'')+
  '</div></div>'+(Object.keys(soc).length?'<div class="sk-so">'+Object.keys(soc).map(function(k){return '<a href="'+E(soc[k])+'" target="_blank" rel="noopener">'+E(NS[k]||k)+'</a>'}).join("")+'</div>':'')+'</div>'+
  '<div class="sk-c"><p class="sk-l">Championship Points</p><div class="sk-cpv"><span class="sk-sm">Carico…</span></div></div>'+
  (righe.length?'<div class="sk-c"><p class="sk-l">Risultati</p>'+righe.map(function(r){return '<div class="sk-r">'+(r.live?'<span class="sk-lv">LIVE</span>':'')+'<b>'+E(r.res||"")+'</b><span>'+E(r.nome)+(r.data?' · <span class="sk-sm">'+E(r.data)+'</span>':'')+'</span></div>'}).join("")+'</div>':'')+
  ((s.risultati||[]).length?'<div class="sk-c"><p class="sk-l">Altri risultati <span class="sk-tag">dichiarati dal giocatore</span></p>'+s.risultati.map(function(r){return '<div class="sk-r"><span>'+E(r)+'</span></div>'}).join("")+'<p class="sk-sm">Non verificati: tornei che non sono nel nostro archivio.</p></div>':'')+
  ((s.squadre||[]).length?'<div class="sk-c"><p class="sk-l">Squadre preferite</p>'+(s.squadre.length>1?'<select class="sk-sq">'+s.squadre.map(function(q,i){return '<option value="'+i+'">'+E(q.formato)+'</option>'}).join("")+'</select>':'<p class="sk-sm">'+E(s.squadre[0].formato)+'</p>')+
    '<div class="sk-sqv">'+squadraHtml(s.squadre[0])+'</div><p class="sk-sm" style="margin-top:8px">Open teamsheet: niente EV né statistiche.</p></div>':'')+
  '</div>';
  ov.innerHTML=h;document.body.appendChild(ov);var prev=document.body.style.overflow;document.body.style.overflow="hidden";
  function chiudi(){ov.remove();document.body.style.overflow=prev;document.removeEventListener("keydown",esc)}
  function esc(e){if(e.key==="Escape")chiudi()}
  document.addEventListener("keydown",esc);
  ov.addEventListener("click",function(e){if(e.target===ov||e.target.closest(".sk-x")){chiudi();return}
    var tb=e.target.closest("[data-tm]");if(tb&&team){var nomi=(team.membri||[]).map(function(m){return PUB[m]&&PUB[m].nome}).filter(Boolean);
      var box=ov.querySelector(".sk-tml");if(box){box.remove();return}box=document.createElement("p");box.className="sk-sm sk-tml";box.style.marginTop="6px";box.textContent=(nomi.length>1?"Nel team: ":"Unico giocatore del team con la scheda: ")+nomi.join(" · ");tb.parentNode.appendChild(box)}});
  var sel=ov.querySelector(".sk-sq");if(sel)sel.addEventListener("change",function(){ov.querySelector(".sk-sqv").innerHTML=squadraHtml(s.squadre[+sel.value]||s.squadre[0])});
  cpTrova(s).then(function(c){var el=ov.querySelector(".sk-cpv");if(!el)return;
    if(!c){el.innerHTML='<span class="sk-cp"><b class="n">CP: non identificato</b></span>';return}
    var pc=c.soglia?Math.min(100,Math.round(c.cp*100/c.soglia)):100;
    el.innerHTML='<div class="sk-cp"><b class="n">'+c.cp+' CP</b><div><b>'+String(c.pos).replace(/\D/g,"")+'° in '+E(c.zona)+'</b><br><span class="sk-sm">'+(c.soglia?(c.manca?"Soglia stimata "+c.soglia+" CP · mancano "+c.manca:"Sopra la soglia stimata di "+c.soglia+" CP"):"")+'</span></div></div><div class="sk-bar"><b style="width:'+pc+'%"></b></div>'});
}
window.SCHEDE={carica:carica,trova:trova,bottone:bottone,apri:apri};
})();
