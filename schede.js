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
var CHIUDI=null,PUB=null,TEAM=null,LOAD=null,CPP=null,IDX={},NICK={};
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
  PUB=a[0]||{};TEAM=a[1]||{};IDX={};NICK={};Object.keys(PUB).forEach(function(id){var s=PUB[id];s.id=id;s.cc=codice(s.paese);(IDX[pn(s.nome)]=IDX[pn(s.nome)]||[]).push(s);
  if(s.nick_vr&&pn(s.nick_vr))(NICK[pn(s.nick_vr)]=NICK[pn(s.nick_vr)]||[]).push(s)});return PUB}).catch(function(){PUB={};TEAM={};return PUB});return LOAD}
/* scheda di un giocatore della ricerca (nome + paese): stesso nome; se ci sono omonimi decide il paese */
function trova(nome,cc){var l=IDX[pn(nome)];if(!l||!l.length){var n=NICK[pn(nome)];return n&&n.length===1?n[0]:null}   /* nei VR la ricerca mostra il nickname Battlefy/VR */if(l.length===1)return(!cc||!l[0].cc||l[0].cc===cc)?l[0]:null;
  return l.filter(function(s){return s.cc&&s.cc===cc})[0]||null}
function avatarHtml(s,cls){var ini=E(String(s.nome||"?").split(/\s+/).map(function(w){return w.charAt(0)}).join("").slice(0,2).toUpperCase());
  return s.avatar?'<img class="'+cls+'" alt="" loading="lazy" src="'+BASE+'img/'+E(s.id)+'.webp?v='+(s.aggiornata||0)+'">':'<span class="'+cls+' sk-ini">'+ini+'</span>'}
/* pulsante nella ricerca, accanto al nome */
/* Schede nascoste da questo telefono (blocco richiesto da Google Play per i contenuti degli utenti): restano solo qui, nel telefono */
var NASC={};try{(JSON.parse(localStorage.getItem("vgc-sch-nasc")||"[]")||[]).forEach(function(k){NASC[k]=1})}catch(x){}
function nascSalva(){try{localStorage.setItem("vgc-sch-nasc",JSON.stringify(Object.keys(NASC)))}catch(x){}}
function chipNasc(s,nome,cc){return '<button type="button" class="pr-sch pr-sch-nas" data-schn="'+E(s.id)+'" data-n="'+E(nome||s.nome||"")+'" data-c="'+E(cc||"")+'" aria-label="Scheda nascosta: tocca per mostrarla di nuovo"><span>Scheda nascosta</span></button>'}
function bottone(nome,cc){var s=trova(nome,cc);if(!s)return"";
  if(NASC[s.id])return chipNasc(s,nome,cc);
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
'.sk-nm{font-size:1.4rem;font-weight:900;line-height:1.1;margin:0}.sk-nk{font-weight:700;margin:3px 0 0;opacity:.95}.sk-ng{font-size:.8rem;margin:3px 0 0;text-shadow:0 1px 0 rgba(0,0,0,.8),0 0 6px rgba(0,0,0,.7)}.sk-ng b{font-weight:800}.sk-nn{font-size:1.25rem;font-weight:900;line-height:1.15;margin:2px 0 0;letter-spacing:.01em;text-shadow:0 1px 0 rgba(0,0,0,.7),0 0 10px rgba(0,0,0,.55)}.sk-ok{color:#bfffe0;font-size:.75rem;font-weight:800}.sk-fr{font-style:italic;margin:6px 0 0;font-size:.92rem}'+
'.sk-lv{border:0;cursor:pointer;font-family:inherit;display:inline-flex;align-items:center;gap:5px;background:#ff6b78;color:#2a0508;font-weight:900;font-size:.72rem;letter-spacing:.06em;border-radius:999px;padding:3px 9px;text-shadow:none}.sk-lv:before{content:"";width:7px;height:7px;border-radius:50%;background:#2a0508;animation:skp 1.2s infinite}@keyframes skp{50%{opacity:.25}}'+
'.sk-tp{display:inline-flex;gap:6px;margin-top:8px;flex-wrap:wrap}.sk-tp span{font-size:.7rem;font-weight:900;letter-spacing:.04em;border-radius:7px;padding:3px 9px;border:1.5px solid rgba(255,255,255,.5)}'+
'.sk-tm{display:inline-flex;align-items:center;gap:6px;margin-top:8px;padding:4px 10px 4px 4px;border-radius:999px;background:rgba(0,0,0,.35);border:1px solid rgba(255,255,255,.35);color:#fff;font-weight:800;font-size:.85rem;cursor:pointer}.sk-tm img,.sk-tm i{width:24px;height:24px;border-radius:7px;object-fit:cover;display:grid;place-items:center;font-style:normal;font-size:.7rem;background:rgba(255,255,255,.2)}'+
'.sk-so{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}.sk-so a small{font-weight:600;opacity:.9;margin-left:7px}.sk-so a svg{width:19px;height:19px;flex:none;filter:drop-shadow(0 1px 1px rgba(0,0,0,.5))}.sk-so a.sk-s-instagram{background:linear-gradient(45deg,rgba(254,218,117,0.63),rgba(250,126,30,0.63) 25%,rgba(214,41,118,0.63) 55%,rgba(150,47,191,0.63) 80%,rgba(79,91,213,0.63));border-color:#e1306c}.sk-so a.sk-s-facebook{background:rgba(8,102,255,0.58);border-color:#0866ff}.sk-so a.sk-s-x{background:rgba(0,0,0,0.68);border-color:#e7e9ea}.sk-so a.sk-s-twitch{background:rgba(145,70,255,0.58);border-color:#9146ff}.sk-so a.sk-s-youtube{background:rgba(255,0,0,0.55);border-color:#ff0000}.sk-so a.sk-s-tiktok{background:linear-gradient(90deg,rgba(37,244,238,0.48),rgba(0,0,0,0.63) 50%,rgba(254,44,85,0.53));border-color:#fe2c55}.sk-so a{box-shadow:inset 0 0 0 99px rgba(0,0,0,.12);backdrop-filter:blur(2px);-webkit-backdrop-filter:blur(2px);text-shadow:0 1px 2px rgba(0,0,0,.6)}.sk-so a{display:inline-flex;align-items:center;padding:5px 11px;border-radius:999px;background:rgba(0,0,0,.35);border:1.5px solid rgba(255,255,255,.4);color:#fff;text-decoration:none;font-weight:700;font-size:.85rem}'+
'.sk-l{font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:#e0aaa6;font-weight:800;margin:0 0 8px}'+
'.sk-cp{display:flex;align-items:center;gap:12px}.sk-cp b.n{font-size:1.6rem;font-weight:900;color:#ffd21f;white-space:nowrap}.sk-bar{height:10px;border-radius:99px;background:#3a1b1f;margin-top:8px;overflow:hidden}.sk-bar b{display:block;height:100%;background:linear-gradient(90deg,#ffd21f,#ff6b78);border-radius:99px}'+
'.sk-sm{font-size:.8rem;color:#e0aaa6}.sk-r{display:flex;gap:8px;align-items:baseline;border-top:1px solid rgba(255,255,255,.12);padding:7px 2px;font-size:.88rem}.sk-r:first-of-type{border-top:0}.sk-r b{min-width:62px}.sk-rb{width:100%;background:none;border:0;border-top:1px solid rgba(255,255,255,.12);color:inherit;font:inherit;text-align:left;cursor:pointer}.sk-rb:first-of-type{border-top:0}.sk-rb i{margin-left:auto;font-style:normal;opacity:.7;font-size:1.1rem}.sk-rb:active{background:rgba(255,255,255,.06)}.sk-r .t{font-size:.65rem;font-weight:800;border-radius:6px;padding:1px 6px;white-space:nowrap}.sk-r .t0{background:rgba(255,255,255,.12)}'+
'.sk-tag{display:inline-block;font-size:.68rem;font-weight:800;border:1.5px dashed #e0aaa6;color:#e0aaa6;border-radius:999px;padding:1px 8px;margin-left:6px;vertical-align:middle}'+
'.pr-sch.pr-sch-nas{background:rgba(255,255,255,.06);border:1px dashed rgba(255,255,255,.28);color:#bfb3b6;font-size:.62rem;font-weight:700;padding:3px 8px;border-radius:999px}'+
'.sk-segc{padding:8px 10px}.sk-seg{display:flex;flex-wrap:wrap;justify-content:center;gap:2px 10px}.sk-seg{text-align:center;margin:4px 0 2px}.sk-seg button{background:none;border:0;color:#e0aaa6;font:inherit;font-size:.78rem;text-decoration:underline;cursor:pointer;padding:6px}'+
'.sk-sqd{border:1.5px solid rgba(255,255,255,.18);border-radius:14px;background:rgba(74,18,32,.55);margin-top:8px;overflow:hidden}.sk-sqd summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:8px;padding:10px 12px;font-weight:800}.sk-sqd summary::-webkit-details-marker{display:none}'+
'.sk-sqd summary b{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.sk-sqd summary small{color:#e0aaa6;font-weight:700;font-size:.75rem;white-space:nowrap}.sk-sqd summary i{margin-left:auto;font-style:normal;transition:transform .2s}.sk-sqd[open] summary i{transform:rotate(180deg)}.sk-sqd .sk-team{margin:0;padding:0 10px 10px}'+
'.sk select{width:100%;padding:10px 12px;border-radius:12px;border:1.5px solid rgba(255,255,255,.2);background:#4a1220;color:#fff;font:inherit;font-weight:700}'+
'.sk-team{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:10px}@media(min-width:700px){.sk-team{grid-template-columns:repeat(3,minmax(0,1fr))}}'+
'.sk-mon{min-width:0;border:1.5px solid rgba(255,255,255,.14);border-radius:14px;padding:8px 10px;background:rgba(0,0,0,.15)}.sk-mon .h{display:flex;align-items:center;gap:6px;min-width:0}.sk-mon .h>div{min-width:0}'+
'.sk-mon .ph{flex:none}.sk-mon b{display:block;font-size:.85rem;line-height:1.15;overflow-wrap:break-word}.sk-mon small{display:block;font-size:.72rem;color:#e0aaa6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'+
'.sk-mon .ab{font-size:.72rem;color:#e0aaa6;margin-top:4px}.sk-mon .te{float:right;font-size:.62rem;font-weight:800;border-radius:6px;padding:1px 6px;background:rgba(255,255,255,.15);color:#fff}'+
'.sk-mon ul{list-style:none;padding:0;margin:6px 0 0;display:grid;grid-template-columns:1fr;gap:3px}.sk-mon li{font-size:.72rem;line-height:1.2;background:#4a1220;border-radius:6px;padding:3px 6px;overflow-wrap:break-word}'+
'.pr-sch.pr-schl{margin-left:auto;padding:3px 8px;border:0;border-radius:999px;background:linear-gradient(135deg,#e11d2e,#6d28d9);color:#fff;font-size:.64rem;font-weight:800;white-space:nowrap}.pr-sch.pr-schl+.pr-sch{margin-left:6px}.pr-sch{display:inline-flex;align-items:center;gap:5px;margin-left:auto;padding:2px 9px 2px 2px;border-radius:999px;border:1.5px solid currentColor;background:transparent;color:inherit;font:inherit;font-size:.78rem;font-weight:800;cursor:pointer}.pr-sav{width:22px;height:22px;border-radius:50%;object-fit:cover;display:inline-grid;place-items:center;font-size:.6rem;font-weight:900;background:linear-gradient(135deg,#e11d2e,#6d28d9);color:#fff}';
function stile(){if(document.getElementById("sk-css"))return;var st=document.createElement("style");st.id="sk-css";st.textContent=CSS;document.head.appendChild(st)}
function fondo(t,dove){var c=COL[t]||COL.normal;if(t==="fighting")return 'url("'+TIPI_DIR+'fighting.webp") center '+dove+'/100% auto no-repeat,radial-gradient(circle at 50% '+(dove==="bottom"?"85%":"15%")+',#ffd21a,#ff5a00 55%,#c41a00)';
  return 'url("'+TIPI_DIR+t+'.webp") 0 0/320px auto repeat,linear-gradient(160deg,'+c[0]+','+c[1]+')'}
/* nickname del social ricavato dal link: «@mario.rossi», «mariork» */
/* loghi dei social (Simple Icons, CC0) */
var ICO_SOC={"instagram":["FF0069","M7.0301.084c-1.2768.0602-2.1487.264-2.911.5634-.7888.3075-1.4575.72-2.1228 1.3877-.6652.6677-1.075 1.3368-1.3802 2.127-.2954.7638-.4956 1.6365-.552 2.914-.0564 1.2775-.0689 1.6882-.0626 4.947.0062 3.2586.0206 3.6671.0825 4.9473.061 1.2765.264 2.1482.5635 2.9107.308.7889.72 1.4573 1.388 2.1228.6679.6655 1.3365 1.0743 2.1285 1.38.7632.295 1.6361.4961 2.9134.552 1.2773.056 1.6884.069 4.9462.0627 3.2578-.0062 3.668-.0207 4.9478-.0814 1.28-.0607 2.147-.2652 2.9098-.5633.7889-.3086 1.4578-.72 2.1228-1.3881.665-.6682 1.0745-1.3378 1.3795-2.1284.2957-.7632.4966-1.636.552-2.9124.056-1.2809.0692-1.6898.063-4.948-.0063-3.2583-.021-3.6668-.0817-4.9465-.0607-1.2797-.264-2.1487-.5633-2.9117-.3084-.7889-.72-1.4568-1.3876-2.1228C21.2982 1.33 20.628.9208 19.8378.6165 19.074.321 18.2017.1197 16.9244.0645 15.6471.0093 15.236-.005 11.977.0014 8.718.0076 8.31.0215 7.0301.0839m.1402 21.6932c-1.17-.0509-1.8053-.2453-2.2287-.408-.5606-.216-.96-.4771-1.3819-.895-.422-.4178-.6811-.8186-.9-1.378-.1644-.4234-.3624-1.058-.4171-2.228-.0595-1.2645-.072-1.6442-.079-4.848-.007-3.2037.0053-3.583.0607-4.848.05-1.169.2456-1.805.408-2.2282.216-.5613.4762-.96.895-1.3816.4188-.4217.8184-.6814 1.3783-.9003.423-.1651 1.0575-.3614 2.227-.4171 1.2655-.06 1.6447-.072 4.848-.079 3.2033-.007 3.5835.005 4.8495.0608 1.169.0508 1.8053.2445 2.228.408.5608.216.96.4754 1.3816.895.4217.4194.6816.8176.9005 1.3787.1653.4217.3617 1.056.4169 2.2263.0602 1.2655.0739 1.645.0796 4.848.0058 3.203-.0055 3.5834-.061 4.848-.051 1.17-.245 1.8055-.408 2.2294-.216.5604-.4763.96-.8954 1.3814-.419.4215-.8181.6811-1.3783.9-.4224.1649-1.0577.3617-2.2262.4174-1.2656.0595-1.6448.072-4.8493.079-3.2045.007-3.5825-.006-4.848-.0608M16.953 5.5864A1.44 1.44 0 1 0 18.39 4.144a1.44 1.44 0 0 0-1.437 1.4424M5.8385 12.012c.0067 3.4032 2.7706 6.1557 6.173 6.1493 3.4026-.0065 6.157-2.7701 6.1506-6.1733-.0065-3.4032-2.771-6.1565-6.174-6.1498-3.403.0067-6.156 2.771-6.1496 6.1738M8 12.0077a4 4 0 1 1 4.008 3.9921A3.9996 3.9996 0 0 1 8 12.0077"],"facebook":["0866FF","M9.101 23.691v-7.98H6.627v-3.667h2.474v-1.58c0-4.085 1.848-5.978 5.858-5.978.401 0 .955.042 1.468.103a8.68 8.68 0 0 1 1.141.195v3.325a8.623 8.623 0 0 0-.653-.036 26.805 26.805 0 0 0-.733-.009c-.707 0-1.259.096-1.675.309a1.686 1.686 0 0 0-.679.622c-.258.42-.374.995-.374 1.752v1.297h3.919l-.386 2.103-.287 1.564h-3.246v8.245C19.396 23.238 24 18.179 24 12.044c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.628 3.874 10.35 9.101 11.647Z"],"x":["fff","M14.234 10.162 22.977 0h-2.072l-7.591 8.824L7.251 0H.258l9.168 13.343L.258 24H2.33l8.016-9.318L16.749 24h6.993zm-2.837 3.299-.929-1.329L3.076 1.56h3.182l5.965 8.532.929 1.329 7.754 11.09h-3.182z"],"twitch":["9146FF","M11.571 4.714h1.715v5.143H11.57zm4.715 0H18v5.143h-1.714zM6 0L1.714 4.286v15.428h5.143V24l4.286-4.286h3.428L22.286 12V0zm14.571 11.143l-3.428 3.428h-3.429l-3 3v-3H6.857V1.714h13.714Z"],"youtube":["FF0000","M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"],"tiktok":["fff","M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"]};
function icoSocial(k){var i=ICO_SOC[k];return i?'<svg viewBox="0 0 24 24" aria-hidden="true" style="fill:#fff"><path d="'+i[1]+'"/></svg>':'<b>'+E(k)+'</b>'}
function nomeSocial(k,u){try{var p=new URL(u).pathname.split("/").filter(Boolean);if(!p.length||/^(profile\.php|channel|c|user|people|pages)$/i.test(p[0])&&k!=="youtube")return"";
  var h=decodeURIComponent(p[p[0]==="c"||p[0]==="user"?1:0]||"");if(!h||h.length>30)return"";return(k==="twitch"||k==="facebook"||h.charAt(0)==="@")?h:"@"+h}catch(e){return""}}
function bollino(n){return typeof window.phHtml==="function"?window.phHtml(n,true):'<span class="ph" style="width:26px;height:26px;border-radius:50%;background:#666;display:inline-block"></span>'}
function squadraHtml(q){return '<div class="sk-team">'+(q.pokemon||[]).map(function(p){return '<div class="sk-mon"><div class="h">'+bollino(p.pokemon)+'<div><b>'+E(p.pokemon)+'</b><small>'+E(p.strumento||"—")+'</small></div></div>'+
  '<div class="ab">'+E(p.abilita||"")+(p.tera?'<span class="te">'+E(p.tera)+'</span>':'')+'</div><ul>'+(p.mosse||[]).map(function(m){return '<li>'+E(m)+'</li>'}).join("")+'</ul></div>'}).join("")+'</div>'}

/* apre la scheda: ctx = giocatore della ricerca (nome, cc, rows dei risultati, live) */
function apri(id,ctx){var s=PUB&&PUB[id];if(!s)return;stile();ctx=ctx||{};
  var tp=(s.tipi||[]).length?s.tipi:[];var t1=tp[0],t2=tp[1]||tp[0];
  var ov=document.createElement("div");ov.className="sk-ov";ov.setAttribute("role","dialog");ov.setAttribute("aria-label","Scheda di "+s.nome);
  var team=s.team&&TEAM[s.team]?TEAM[s.team]:null;
  var soc=s.social||{},NS={instagram:"Instagram",facebook:"Facebook",x:"X",twitch:"Twitch",youtube:"YouTube",tiktok:"TikTok"};
  var righe=(ctx.rows||[]).slice(0,60);
  var h='<div class="sk" style="'+(t1?'--b1:'+E(fondo(t1,"top"))+';--b2:'+E(fondo(t2,"bottom")):'--b1:linear-gradient(160deg,#4a1220,#1d0b0d);--b2:linear-gradient(160deg,#2c1316,#1d0b0d)')+'">'+
  '<button type="button" class="sk-x" aria-label="Chiudi">×</button>'+
  '<div class="sk-c sk-hero"><div class="sk-hd"><div class="sk-avw">'+avatarHtml(s,"sk-av")+(ctx.live?'<button type="button" class="sk-lv" data-live="" aria-label="Apri il live">LIVE ›</button>':'')+'</div><div>'+
  '<p class="sk-nm">'+E(s.nome)+' '+bandiera(s.cc)+'</p>'+(s.nickname?'<p class="sk-nn" style="color:'+(/^#[0-9a-f]{6}$/i.test(s.colore||"")?s.colore:"#fff")+'">'+E(s.nickname)+'</p>':'')+((s.nick_vr||s.nick_gioco)?'<p class="sk-ng">'+(s.nick_vr?'Battlefy/VR: <b>'+E(s.nick_vr)+'</b>':'')+(s.nick_vr&&s.nick_gioco?' · ':'')+(s.nick_gioco?'In game: <b>'+E(s.nick_gioco)+'</b>':'')+'</p>':'')+'<p class="sk-nk"><span class="sk-ok">✔ profilo verificato</span></p>'+
  (s.frase?'<p class="sk-fr">«'+E(s.frase)+'»</p>':'')+(tp.length?'<div class="sk-tp">'+tp.filter(function(t,i,l){return l.indexOf(t)===i}).map(function(t){return '<span style="background:'+(COL[t]||COL.normal)[0]+'">'+E((NOMI[t]||t).toUpperCase())+'</span>'}).join("")+'</div>':'')+
  (team?'<div><button type="button" class="sk-tm" data-tm="1">'+(team.logo?'<img alt="" src="'+BASE+'team/'+E(s.team)+'.webp">':'<i>'+E(String(team.nome).slice(0,2).toUpperCase())+'</i>')+E(team.nome)+'</button></div>':'')+
  '</div></div>'+(Object.keys(soc).length?'<div class="sk-so">'+Object.keys(soc).map(function(k){var h=nomeSocial(k,soc[k]);return '<a class="sk-s-'+E(k)+'" href="'+E(soc[k])+'" target="_blank" rel="noopener" aria-label="'+E(NS[k]||k)+'" title="'+E(NS[k]||k)+'">'+icoSocial(k)+(h?'<small>'+E(h)+'</small>':'<small>'+E(NS[k]||k)+'</small>')+'</a>'}).join("")+'</div>':'')+'</div>'+
  '<div class="sk-c"><p class="sk-l">Championship Points</p><div class="sk-cpv"><span class="sk-sm">Carico…</span></div></div>'+
  (righe.length?'<div class="sk-c"><p class="sk-l">Risultati</p>'+righe.map(function(r,i){var tag=r.tag?'<span class="t '+E(r.tag[1]||"t0")+'">'+E(r.tag[0])+'</span>':'',
    dentro=(r.live&&r.id?'<span class="sk-lv">LIVE</span>':'')+'<b>'+E(r.res||"")+'</b><span>'+tag+' '+E(r.nome)+(r.data?' · <span class="sk-sm">'+E(r.data)+'</span>':'')+'</span>';
    return r.man?'<div class="sk-r">'+dentro+'</div>':'<button type="button" class="sk-r sk-rb" data-ri="'+i+'">'+dentro+'<i>›</i></button>'}).join("")+'</div>':'')+
  ((s.squadre||[]).length?'<div class="sk-c"><p class="sk-l">Squadre preferite</p>'+s.squadre.map(function(q,i){   /* una tendina per squadra: la prima aperta */
    var tit=q.nome||q.formato||("Squadra "+(i+1)),sub=q.nome&&q.formato&&q.formato!==q.nome?q.formato:"";
    return '<details class="sk-sqd"'+(i?'':' open')+'><summary><b>'+E(tit)+'</b>'+(sub?'<small>'+E(sub)+'</small>':'')+'<i>⌄</i></summary>'+squadraHtml(q)+'</details>'}).join("")+
    '<p class="sk-sm" style="margin-top:8px">Open teamsheet: niente EV né statistiche.</p></div>':'')+
  '<div class="sk-c sk-segc"><p class="sk-seg">'+(typeof window.segApri==="function"?'<button type="button" data-seg="">⚑ Segnala questa scheda</button>':'')+'<button type="button" data-nasc="">🚫 Nascondi questa scheda</button></p>'+
  '<p class="sk-sm" style="text-align:center;margin:0 0 4px">Nascondere una scheda vale solo su questo telefono: non la vedrai più nelle ricerche. · <a href="regole-schede.html" target="_blank" rel="noopener" style="color:inherit">Regole delle schede</a></p></div>'+
  '</div>';
  ov.innerHTML=h;document.body.appendChild(ov);var prev=document.body.style.overflow;document.body.style.overflow="hidden";
  function chiudi(){ov.remove();document.body.style.overflow=prev;document.removeEventListener("keydown",esc);if(CHIUDI===chiudi)CHIUDI=null}
  if(CHIUDI)CHIUDI();CHIUDI=chiudi;
  function esc(e){if(e.key==="Escape")chiudi()}
  document.addEventListener("keydown",esc);
  ov.addEventListener("click",function(e){if(e.target===ov||e.target.closest(".sk-x")){chiudi();return}
    var rb=e.target.closest("[data-ri]");if(rb){                 /* risultato: chiude la scheda e apre il torneo, come la riga nella ricerca */
      var box=document.querySelector('.pr-nasc[data-sch-r="'+id+'"]'),el=box&&box.children[+rb.getAttribute("data-ri")];chiudi();
      if(el&&el.tagName==="BUTTON")el.click();return}
    var nb=e.target.closest("[data-nasc]");if(nb){                /* blocco: primo tocco chiede conferma, il secondo nasconde la scheda su questo telefono */
      if(!nb.dataset.ok){nb.dataset.ok="1";nb.textContent="Tocca di nuovo per nasconderla";return}
      NASC[id]=1;nascSalva();chiudi();
      Array.prototype.forEach.call(document.querySelectorAll('.pr-sch[data-sch="'+id+'"]'),function(b){if(b.classList.contains("pr-schl")){b.remove();return}b.outerHTML=chipNasc(s,s.nome,s.cc)});return}
    if(e.target.closest("[data-seg]")){                           /* segnalazione: stessa finestra di «Segnala un problema», arriva in admin → Statistiche */
      window.segApri({titolo:"Segnala questa scheda",pre:"[Scheda "+(s.nome||"")+" · "+(s.id||"")+"] ",ph:"Es. non è lui, foto non sua, logo di un altro team, frase offensiva…"});return}
    var lv=e.target.closest("[data-live]");if(lv){                /* LIVE: chiude la scheda e apre il live, come la riga del torneo nella ricerca */
      var lid=lv.getAttribute("data-live")||((ctx.rows||[]).filter(function(r){return r.live&&r.id})[0]||{}).id;chiudi();
      var riga=lid&&Array.prototype.filter.call(document.querySelectorAll(".pr-r[data-pid]"),function(b){return b.getAttribute("data-pid")===lid&&b.getAttribute("data-pn")===ctx.nome})[0];
      if(riga)riga.click();return}
    var tb=e.target.closest("[data-tm]");if(tb&&team){var nomi=(team.membri||[]).map(function(m){return PUB[m]&&PUB[m].nome}).filter(Boolean);
      var box=ov.querySelector(".sk-tml");if(box){box.remove();return}box=document.createElement("p");box.className="sk-sm sk-tml";box.style.marginTop="6px";box.textContent=(nomi.length>1?"Nel team: ":"Unico giocatore del team con la scheda: ")+nomi.join(" · ");tb.parentNode.appendChild(box)}});

  cpTrova(s).then(function(c){var el=ov.querySelector(".sk-cpv");if(!el)return;
    if(!c){el.innerHTML='<span class="sk-cp"><b class="n">CP: non identificato</b></span>';return}
    var pc=c.soglia?Math.min(100,Math.round(c.cp*100/c.soglia)):100;
    el.innerHTML='<div class="sk-cp"><b class="n">'+c.cp+' CP</b><div><b>'+String(c.pos).replace(/\D/g,"")+'° in '+E(c.zona)+'</b><br><span class="sk-sm">'+(c.soglia?(c.manca?"Soglia stimata "+c.soglia+" CP · mancano "+c.manca:"Sopra la soglia stimata di "+c.soglia+" CP"):"")+'</span></div></div><div class="sk-bar"><b style="width:'+pc+'%"></b></div>'});
}
/* «indietro» (Android) e pulsante Indietro (iPhone): prima si chiude la scheda */
/* scheda nascosta: primo tocco chiede conferma, il secondo la mostra di nuovo */
document.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("[data-schn]");if(!b)return;e.preventDefault();e.stopPropagation();
  if(!b.dataset.ok){b.dataset.ok="1";b.querySelector("span").textContent="Mostrarla di nuovo?";return}
  delete NASC[b.dataset.schn];nascSalva();var h=bottone(b.dataset.n,b.dataset.c);if(h)b.outerHTML=h;else b.remove()},true);
window.SCHEDE={carica:carica,trova:trova,bottone:bottone,apri:apri,aperta:function(){return !!CHIUDI},chiudi:function(){if(CHIUDI){CHIUDI();return true}return false}};
})();
