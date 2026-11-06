/* CP bar: classifica dei Championship Points da Pokédata (Europa, VG Masters) con la soglia stimata per gli inviti.
   Si carica solo quando si apre dal menu laterale. I dati li prepara il collettore nella seconda repo (dati/cp/). */
(function(){
"use strict";
var URLD=String(window.VGCS_CP||"https://rakings.github.io/VGCdatiAK/dati/cp/vg-europe-masters.json");
var POKEDATA="https://www.pokedata.ovh/2027/?game=VG&region=Europe&division=Masters";
var D=null,OV=null,ONC=null,S={q:"",f:"all",st:null},BASE=URLD.replace(/[^\/]*$/,""),IX=null,IXP=null,DC={};
function E(x){return String(x).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
function pn(s){return String(s||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/\s+/g," ").trim()}
function num(n){return Number(n).toLocaleString("it")}
function dm(d){try{var x=new Date(d+"T12:00:00");return isNaN(x.getTime())?String(d||""):x.toLocaleDateString("it",{day:"numeric",month:"short"})}catch(e){return String(d||"")}}
function dh(s){var m=/^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})/.exec(s||"");return m?dm(m[1])+", "+m[2]+" UTC":String(s||"")}
function css(){if(document.getElementById("cp-css"))return;var st=document.createElement("style");st.id="cp-css";
st.textContent="#cpov{position:fixed;inset:0;z-index:40;background:var(--bg,#1d0b0d);color:var(--ink,#fff1ef);overflow:auto;-webkit-overflow-scrolling:touch}#cpov[hidden]{display:none}"+
"html.cp-open,html.cp-open body{overflow:hidden}html.cp-open #vgc-up{display:none!important}"+
".cp-w{max-width:640px;margin:0 auto;padding:0 12px calc(24px + env(safe-area-inset-bottom,0px))}"+
".cp-h{position:sticky;top:0;z-index:2;display:flex;align-items:center;gap:10px;padding:8px 0;background:var(--bg,#1d0b0d);border-bottom:1px solid var(--line,#5a2a2e)}"+
".cp-h b{font-size:1.15rem}.cp-h span{flex:1;font-size:.82rem;color:var(--mute,#c9a0a2)}"+
".cp-x{width:34px;height:34px;border-radius:50%;border:1.5px solid var(--line,#5a2a2e);background:var(--card,#2c1316);color:inherit;font-size:1.3rem;line-height:1;cursor:pointer}"+
".cp-sum{margin:8px 0;border:2px solid var(--coin,#ffd21f);border-radius:12px;padding:7px 12px}.cp-big{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}"+
".cp-big b{font-size:1.5rem;color:var(--coin,#ffd21f)}.cp-big span{font-size:.88rem}.cp-note{font-size:.74rem;color:var(--mute,#c9a0a2);margin-top:2px;line-height:1.3}"+
".cp-ctl{display:flex;gap:6px;margin:0 0 6px}.cp-ctl input{flex:1 1 100px;min-width:0;padding:7px 10px;border-radius:12px;border:1.5px solid var(--line,#5a2a2e);background:var(--card,#2c1316);color:inherit;font:inherit}"+
".cp-chip{padding:6px 11px;font-size:.82rem;white-space:nowrap;border-radius:999px;border:1.5px solid var(--line,#5a2a2e);background:transparent;color:inherit;font:inherit;font-weight:700;cursor:pointer}.cp-chip[aria-pressed=true]{background:var(--coin,#ffd21f);color:#4a3600;border-color:var(--coin,#ffd21f)}"+
".cp-r{display:grid;grid-template-columns:34px 1fr auto;gap:2px 8px;align-items:center;width:100%;text-align:left;padding:5px 4px 3px;background:transparent;border:0;border-bottom:1px solid var(--line,#5a2a2e);color:inherit;font:inherit;cursor:pointer}"+
".cp-pos{font-weight:800;color:var(--mute,#c9a0a2);text-align:right}.cp-n{display:flex;flex-direction:column;min-width:0}.cp-n b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.95rem}.cp-n small{font-size:.7rem;color:var(--mute,#c9a0a2)}"+
".cp-cp{display:flex;flex-direction:column;align-items:flex-end}.cp-cp b{font-size:.98rem}.cp-cp small{font-size:.72rem;font-weight:700}.cp-su{color:#4ade80}.cp-gi{color:#ff6b78}.cp-pa{color:var(--coin,#ffd21f)}"+
".cp-bar{grid-column:1/-1;display:block;height:5px;border-radius:3px;background:rgba(255,255,255,.08);overflow:hidden}.cp-bar u{display:block;height:100%;background:var(--coin,#ffd21f);border-radius:3px}.cp-sotto .cp-bar u{background:#ff6b78;opacity:.75}"+
".cp-cut{margin:10px 0;border-top:2px dashed #ff6b78;position:relative;height:0}.cp-cut span{position:absolute;right:0;top:-11px;background:#ff6b78;color:#fff;font-size:.72rem;font-weight:800;padding:2px 10px;border-radius:999px}"+
".cp-d{padding:4px 4px 8px 42px;font-size:.78rem;border-bottom:1px solid var(--line,#5a2a2e)}.cp-e{display:flex;flex-wrap:wrap;align-items:center;gap:1px 8px;padding:3px 0}.cp-ed{min-width:44px;color:var(--mute,#c9a0a2)}.cp-e i{font-style:normal;font-weight:700;color:#4ade80}.cp-ev{display:flex;align-items:center;gap:6px;flex:1 1 auto}.cp-ev .tag{font-size:.66rem;padding:1px 7px}.cp-ev small{color:var(--mute,#c9a0a2)}.cp-no{color:var(--mute,#c9a0a2);font-style:italic}"+
".cp-st{display:flex;gap:6px;margin:8px 0 0}.cp-vuoto{color:var(--mute,#c9a0a2);padding:16px 4px}.cp-f{font-size:.72rem;color:var(--mute,#c9a0a2);margin:14px 4px 0}.cp-f a{color:inherit;text-decoration:underline}";
(document.head||document.documentElement).appendChild(st)}
/* Archivio per stagione: indice.json elenca le stagioni (quella in corso e le chiuse). Se l'indice non c'e', si legge l'ultima classifica come prima. */
function indice(){if(IXP)return IXP;IXP=fetch(BASE+"indice.json",{cache:"no-cache"}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(j){if(!j||!Array.isArray(j.stagioni)||!j.stagioni.length)throw 0;IX=j;return j}).catch(function(){IX=null;return null});return IXP}
function file(st){var v=IX&&st?IX.stagioni.filter(function(x){return x.stagione===st})[0]:null;return v?BASE+v.file:URLD}
/* Torneo e piazzamento di ogni voce di punti: Pokedata da' solo totale e data (e il cognome abbreviato, es. «Giuseppe M»), quindi si incrociano
   con i NOSTRI risultati (vgcstats/giocatori.json + index.json): stesso nome, evento finito nei 14 giorni prima della data della voce. Se non c'e', si dice. */
var CC2={ITA:"IT",FRA:"FR",ESP:"ES",DEU:"DE",GBR:"GB",NLD:"NL",POL:"PL",PRT:"PT",BEL:"BE",CHE:"CH",AUT:"AT",SWE:"SE",NOR:"NO",DNK:"DK",FIN:"FI",IRL:"IE",CZE:"CZ",HUN:"HU",GRC:"GR",ROU:"RO",BGR:"BG",SVK:"SK",SVN:"SI",HRV:"HR",LTU:"LT",LVA:"LV",EST:"EE",ISL:"IS",MLT:"MT",UKR:"UA",SRB:"RS",LUX:"LU",CYP:"CY",TUR:"TR",ISR:"IL"};
var GJ=null,EVI=null,GJP=null,ALIAS={};
function dati(){if(GJP)return GJP;function J(u){return fetch(u,{cache:"no-cache"}).then(function(r){if(!r.ok)throw 0;return r.json()})}
GJP=Promise.all([J("vgcstats/giocatori.json"),J("vgcstats/index.json"),J(BASE+"alias.json").catch(function(){return{}})]).then(function(a){if(!a[0]||!Array.isArray(a[0].p)||!Array.isArray(a[0].ids))throw 0;GJ=a[0];EVI={};((a[1]&&a[1].events)||[]).forEach(function(e){EVI[e.id]=e});ALIAS={};if(a[2]&&typeof a[2]==="object")Object.keys(a[2]).forEach(function(k){ALIAS[pn(k)]=pn(a[2][k])});return true}).catch(function(){GJ=null;return false});return GJP}
function giorni(a,b){return Math.round((new Date(b+"T12:00:00")-new Date(a+"T12:00:00"))/864e5)}
function subseq(a,b){var i=0;b.forEach(function(x){if(i<a.length&&a[i]===x)i++});return i===a.length}
/* Chi e' questo giocatore nei nostri risultati: 1) alias scritto a mano (dati/cp/alias.json, per i nomi utente); 2) cognome abbreviato («Giuseppe M»);
   3) stesso nome con un secondo nome o cognome in piu' o in meno («Shai Raba» / «Shai Giuseppe Raba»). Il paese aiuta a scegliere. */
function candidati(r){var nr=pn(r.name),t=nr.split(" "),L=t[t.length-1],ini=L.length===1&&t.length>=2,base=t.slice(0,-1),cc=CC2[r.country]||"",out=[],al=ALIAS[nr];
if(al){GJ.p.forEach(function(p){if(pn(p[0])===al)out.push(p)});if(out.length)return out}
GJ.p.forEach(function(p){var np=pn(p[0]),pt=np.split(" "),ok;
if(ini)ok=pt.length>base.length&&pt.slice(0,base.length).join(" ")===base.join(" ")&&pt[base.length].charAt(0)===L;
else if(np===nr)ok=true;else ok=t.length>=2&&pt.length>=2&&pt[0]===t[0]&&(subseq(t,pt)||subseq(pt,t));
if(ok)out.push(p)});
var f=out.filter(function(p){return(p[1]==="UK"?"GB":p[1])===cc});return f.length?f:out}
function assegna(r,p,stag){var st=(r.storia||[]).slice().sort(function(a,b){return a.data<b.data?-1:1}),da=(Number(stag)-1)+"-09-01",ev=[];
p[2].forEach(function(t){var e=EVI[GJ.ids[t[0]]];if(e&&e.end&&e.end>=da)ev.push({e:e,pl:t[1],w:t[2],l:t[3]})});ev.sort(function(a,b){return a.e.end<b.e.end?-1:1});
var usati={},n=0,out=st.map(function(s){var m=ev.filter(function(x){var g=giorni(x.e.end,s.data);return!usati[x.e.id]&&g>=0&&g<=14});m.forEach(function(x){usati[x.e.id]=1;n++});return{s:s,m:m}});return{righe:out,n:n}}
/* Ritorna {k, righe}: k = ok (giocatore e almeno un torneo trovati) | nessuno (riconosciuto, ma nessun nostro torneo nelle date) | ambiguo | non riconosciuto */
function trova(r,stag){if(!GJ||!EVI)return{k:"nd"};var c=candidati(r);if(!c.length)return{k:"non riconosciuto"};var best=null,tie=false;
c.forEach(function(p){var a=assegna(r,p,stag);if(!best||a.n>best.n){best=a;tie=false}else if(a.n===best.n)tie=true});
if(tie&&best.n>0)return{k:"ambiguo"};if(c.length>1&&best.n===0)return{k:"ambiguo"};if(best.n===0)return{k:"nessuno"};return{k:"ok",righe:best.righe}}
function tagDi(e){var k=String(e.kind||"");return/world/i.test(k)?["Mondiale","t-ww"]:/international/i.test(k)?["Internazionale","t-int"]:/special/i.test(k)?["Special Event","t-reg"]:/national/i.test(k)?["Nazionale","t-gc"]:["Regionale","t-rg"]}
function linee(r,ab){var st=(r.storia||[]).slice().sort(function(a,b){return a.data<b.data?-1:1}),h="",prev=0;
st.forEach(function(s,i){var m=ab?ab[i].m:[],ev="";
m.forEach(function(x){var tg=tagDi(x.e);ev+='<span class="cp-ev"><span class="tag '+tg[1]+'">'+tg[0]+"</span><b>"+E(x.e.city||x.e.name)+"</b> · "+E(x.pl)+"°"+(x.w!=null?" <small>("+x.w+"-"+x.l+")</small>":"")+"</span>"});
h+='<div class="cp-e"><span class="cp-ed">'+E(dm(s.data))+"</span><b>"+num(s.cp)+" CP</b>"+(s.cp>prev?"<i>+"+num(s.cp-prev)+"</i>":"")+ev+"</div>";prev=s.cp});return h||'<div class="cp-e cp-no">Nessun dettaglio disponibile</div>'}
function load(st){var k=st||"_";if(DC[k])return Promise.resolve(DC[k]);return fetch(file(st),{cache:"no-cache"}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json()}).then(function(j){if(!j||!Array.isArray(j.righe)||!j.righe.length)throw new Error("vuoto");DC[k]=j;return j})}
function head(){return'<div class="cp-h"><b>CP bar</b><span>Europa · VG Masters '+E((D&&D.stagione)||"2027")+'</span><button type="button" class="cp-x" data-cp="x" aria-label="Chiudi">×</button></div>'}
function ov(){if(OV)return OV;OV=document.createElement("div");OV.id="cpov";OV.hidden=true;OV.setAttribute("role","dialog");OV.setAttribute("aria-modal","true");OV.setAttribute("aria-label","Classifica CP");document.body.appendChild(OV);
OV.addEventListener("click",function(e){var t=e.target.closest("[data-cp]");if(!t)return;var a=t.getAttribute("data-cp");
if(a==="x")close(true);else if(a==="s"){var st=t.getAttribute("data-v");if(st!==S.st){S.st=st;S.q="";load(st).then(function(x){D=x;draw()}).catch(function(){})}}else if(a==="f"){S.f=t.getAttribute("data-v");[].forEach.call(OV.querySelectorAll(".cp-chip"),function(b){b.setAttribute("aria-pressed",String(b.getAttribute("data-v")===S.f))});lista()}else if(a==="r")tog(t)});
OV.addEventListener("input",function(e){if(e.target.id==="cp-q"){S.q=e.target.value;lista()}});return OV}
function riga(r,i,sg,max){var sotto=sg.cp!=null&&r.cp<sg.cp,dd=sg.cp==null?"":(r.cp>sg.cp?"+"+(r.cp-sg.cp):r.cp===sg.cp?"soglia":"−"+(sg.cp-r.cp)),cl=r.cp>sg.cp?"cp-su":r.cp===sg.cp?"cp-pa":"cp-gi";
return'<button type="button" class="cp-r'+(sotto?" cp-sotto":"")+'" data-cp="r" data-i="'+i+'" aria-expanded="false"><span class="cp-pos">'+E(r.pos)+'</span><span class="cp-n"><b>'+E(r.name)+"</b><small>"+E(r.country||"")+'</small></span><span class="cp-cp"><b>'+num(r.cp)+'</b><small class="'+cl+'">'+E(dd)+'</small></span><i class="cp-bar"><u style="width:'+Math.max(2,Math.round(r.cp/max*100))+'%"></u></i></button>'}
function lista(){var el=document.getElementById("cp-list");if(!el||!D)return;var sg=D.soglia||{},max=Math.max.apply(null,D.righe.map(function(r){return r.cp}))||1,q=pn(S.q),h="",cut=false,n=0;
D.righe.forEach(function(r,i){if(S.f==="it"&&r.country!=="ITA")return;if(q&&pn(r.name).indexOf(q)<0)return;
if(!cut&&sg.posizione&&r.pos>sg.posizione){h+='<div class="cp-cut"><span>Soglia stimata: '+num(sg.cp)+" CP · "+sg.posizione+"° posto</span></div>";cut=true}
n++;h+=riga(r,i,sg,max)});
if(!n)h='<p class="cp-vuoto">Nessun giocatore trovato tra i primi '+D.righe.length+'. La classifica completa è su <a href="'+POKEDATA+'" target="_blank" rel="noopener">Pokédata</a>.</p>';
el.innerHTML=h}
function tog(btn){var nx=btn.nextElementSibling;if(nx&&nx.classList.contains("cp-d")){nx.remove();btn.setAttribute("aria-expanded","false");return}
var r=D.righe[Number(btn.getAttribute("data-i"))],d=document.createElement("div");d.className="cp-d";d.innerHTML=linee(r,null)+(GJ?"":'<div class="cp-e cp-no">Cerco il torneo…</div>');btn.parentNode.insertBefore(d,btn.nextSibling);btn.setAttribute("aria-expanded","true");
var stag=D.stagione;dati().then(function(ok){if(!d.isConnected)return;var t=ok?trova(r,stag):{k:"nd"};d.innerHTML=linee(r,t.k==="ok"?t.righe:null)})}
function draw(){var o=ov(),sg=D.soglia||{},nIt=D.righe.filter(function(r){return r.country==="ITA"}).length,fin=D.finale===true,
sel=IX&&IX.stagioni.length>1?'<div class="cp-st">'+IX.stagioni.map(function(v){return'<button type="button" class="cp-chip" data-cp="s" data-v="'+E(v.stagione)+'" aria-pressed="'+(v.stagione===S.st)+'">'+E(v.stagione)+" · "+(v.stato==="in corso"?"in corso":"finale")+"</button>"}).join("")+"</div>":"";
o.innerHTML='<div class="cp-w">'+head()+sel+
'<div class="cp-sum"><div class="cp-big"><b>'+(sg.cp!=null?num(sg.cp)+" CP":"—")+"</b><span>soglia stimata"+(sg.posizione?" ("+sg.posizione+"° posto)":"")+'</span></div>'+
'<div class="cp-note">Stima non ufficiale · '+(D.giocatori_totali?num(D.giocatori_totali)+" giocatori in classifica · ":"")+(fin?"Classifica finale "+E(D.stagione)+(D.chiusa?" · chiusa il "+E(dm(D.chiusa)):"")+" · ultimo aggiornamento "+E(dh(D.aggiornato)):D.controllato?"controllata il "+E(dh(D.controllato))+(D.aggiornato&&D.aggiornato!==D.controllato?" · punti cambiati il "+E(dh(D.aggiornato)):""):"aggiornata il "+E(dh(D.aggiornato)))+"</div></div>"+
'<div class="cp-ctl"><input id="cp-q" type="search" placeholder="Cerca un giocatore" aria-label="Cerca un giocatore" value="'+E(S.q)+'"><button type="button" class="cp-chip" data-cp="f" data-v="all" aria-pressed="'+(S.f==="all")+'">Tutti</button><button type="button" class="cp-chip" data-cp="f" data-v="it" aria-pressed="'+(S.f==="it")+'">Italiani ('+nIt+")</button></div>"+
'<div id="cp-list"></div><p class="cp-f">Dati: <a href="'+POKEDATA+'" target="_blank" rel="noopener">Pokédata</a> · classifica non ufficiale · primi '+D.righe.length+(D.giocatori_totali?" di "+num(D.giocatori_totali):"")+" giocatori. La soglia è una stima: il "+(sg.posizione||90)+"° posto dell'elenco. Torneo e piazzamento si ricavano dai nostri risultati (nome e data): mancano per gli eventi che non sono nel sito.</p></div>";lista()}
function open(onclose){ONC=onclose||null;css();var o=ov();o.hidden=false;o.scrollTop=0;
o.innerHTML='<div class="cp-w">'+head()+'<p class="cp-vuoto">Caricamento…</p></div>';
indice().then(function(){S.st=IX?IX.corrente:null;return load(S.st)}).then(function(x){D=x;if(!o.hidden)draw()}).catch(function(){if(!o.hidden)o.innerHTML='<div class="cp-w">'+head()+'<p class="cp-vuoto">La classifica non è disponibile in questo momento. Riprova tra poco.</p></div>'})}
function close(utente){if(OV)OV.hidden=true;if(utente&&ONC){var f=ONC;ONC=null;f()}}
window.CPBAR={open:open,close:function(){close(false)}};
})();
