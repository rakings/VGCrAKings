/* VGC Stats - sezione del sito rAKings VGC. Caricata solo quando si apre il pulsante "VGC Stats".
   Legge i file in vgcstats/ (creati da vgc_stats.py). Fonte dei dati: Pokedata (dati RK9). */
(function(){
"use strict";
var BASE="vgcstats/";
var S={sec:"arc",ev:null,treg:null,reg:"all",q:"",pq:"",sq:"",g:"all",s:"cnt",fp:false,mon:null,open:{},shown:80,onlyIt:false,msg:"",ready:false,fail:false};
var OQ=[],POS={},PEND=null;
function setOpen(id,on){S.open[id]=!!on;var i=OQ.indexOf(id);if(i>=0)OQ.splice(i,1);if(on)OQ.push(id)}
function vkey(){return S.sec==="arc"?"arc":S.sec+"|"+S.ev+"|"+(S.mon||"")}
function savePos(){POS[vkey()]=window.scrollY}
function applyPos(){if(PEND!=null){var y=PEND;PEND=null;window.scrollTo(0,y)}}
function closeMon(){var k=S.sec+"|"+S.ev+"|";PEND=POS[k]!=null?POS[k]:null;S.mon=null;drawRes()}
var host=null,IDX=null,WIN={},C={},D={},TOT={};
function E(x){return window.esc?window.esc(x):String(x).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
function J(p,fresh){var k=p+(fresh?"#"+Date.now():"");if(!fresh&&C[p])return C[p];var q=fetch(BASE+p+(fresh?"?t="+Date.now():""),{cache:"no-cache"}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json()});if(!fresh){C[p]=q;q.catch(function(){delete C[p]})}return q}
function pc(n,t){return t?Math.round(n/t*100):0}
function wr(w,l){return w+l?(100*w/(w+l)).toFixed(1).replace(".",",")+"%":"–"}
function dot(n){return window.phHtml?window.phHtml(n):""}
function regLabel(r){return r==="old"?"Regolamenti precedenti":"Regolamento "+r}
function dfmt(d){try{return new Date(d+"T12:00:00").toLocaleDateString("it",{day:"numeric",month:"short",year:"numeric"})}catch(e){return d||""}}
function evOf(id){return (IDX.events||[]).filter(function(e){return e.id===id})[0]}
function pastRegs(){var o=[];(IDX.events||[]).forEach(function(e){if(e.reg!==IDX.current&&o.indexOf(e.reg)<0)o.push(e.reg)});return o}
function italia(cc){return cc==="IT"?' <span class="tag t-it">Italia</span>':""}

/* ---------- dati ---------- */
function loadEv(id,fresh){if(D[id]&&!fresh)return Promise.resolve(D[id]);
return Promise.all(["meta","players","pokemon","teams","swiss"].map(function(f){return J(id+"/"+f+".json",fresh)})).then(function(a){var d={m:a[0],pl:a[1],pk:a[2],tm:a[3],sw:a[4],by:{}};a[1].forEach(function(p){d.by[p[0]]=p});D[id]=d;return d})}
function loadTot(reg){if(TOT[reg])return Promise.resolve(TOT[reg]);
var ids=(IDX.events||[]).filter(function(e){return e.reg===reg&&e.collected}).map(function(e){return e.id});
return Promise.all(ids.map(function(i){return Promise.all([J(i+"/meta.json"),J(i+"/pokemon.json")])})).then(function(a){
var m={},sz={all:0,top:0,ph2:0,cut:0};
a.forEach(function(x){var meta=x[0];sz.all+=meta.players;sz.top+=Math.min(meta.top||256,meta.players);sz.ph2+=meta.day2_players||0;sz.cut+=meta.cut_players||0;
x[1].forEach(function(p){var t=m[p.slug]||(m[p.slug]={slug:p.slug,name:p.name,count:0,wins:0,losses:0,top256:0,day2:0,cut:0,sample:0,partners:{},nature:{},item:{},ability:{},moves:{},extra:{}});
["count","wins","losses","top256","day2","cut","sample"].forEach(function(k){t[k]+=p[k]||0});
function add(o,arr){(arr||[]).forEach(function(z){o[z[0]]=(o[z[0]]||0)+z[1]})}
add(t.partners,p.partners);add(t.nature,p.nature);add(t.item,p.item);add(t.ability,p.ability);add(t.moves,p.moves);
Object.keys(p.extra||{}).forEach(function(k){t.extra[k]=t.extra[k]||{};add(t.extra[k],p.extra[k])})})});
function arr(o,n){return Object.keys(o).map(function(k){return[k,o[k]]}).sort(function(x,y){return y[1]-x[1]}).slice(0,n||999)}
var list=Object.keys(m).map(function(k){var t=m[k];t.partners=arr(t.partners,15);t.nature=arr(t.nature);t.item=arr(t.item);t.ability=arr(t.ability);t.moves=arr(t.moves);Object.keys(t.extra).forEach(function(x){t.extra[x]=arr(t.extra[x])});return t}).sort(function(x,y){return y.count-x.count});
return TOT[reg]={n:ids.length,sz:sz,pk:list}})}
function cur(){if(S.ev==="tot")return loadTot(S.treg).then(function(t){return{tot:true,m:{players:t.sz.all,day2_players:t.sz.ph2,cut_players:t.sz.cut,top:256},sz:t.sz,pk:t.pk,n:t.n}});
if(!S.ev)return Promise.resolve(null);return loadEv(S.ev)}

/* ---------- elementi comuni ---------- */
function evSel(tot){var og={},ord=[];(IDX.events||[]).forEach(function(e){var g=e.reg;if(!og[g]){og[g]=[];ord.push(g)}og[g].push(e)});
ord.sort(function(a,b){return a===IDX.current?-1:b===IDX.current?1:0});
var h='<select id="vg-ev" aria-label="Regionale">';
if(tot)h+='<option value="tot"'+(S.ev==="tot"?" selected":"")+'>Tutti i regionali ('+E(regLabel(S.treg||IDX.current))+')</option>';
ord.forEach(function(g){h+='<optgroup label="'+E(regLabel(g)+(g===IDX.current?" (attuale)":""))+'">'+og[g].map(function(e){return'<option value="'+e.id+'"'+(S.ev===e.id?" selected":"")+(e.collected?"":" disabled")+'>'+E(e.city)+(e.collected?"":" · da raccogliere")+'</option>'}).join("")+"</optgroup>"});
return h+"</select>"}
function foot(){return'<p class="vg-foot">Fonte: <a href="https://www.pokedata.ovh" target="_blank" rel="noopener">Pokedata</a> (dati RK9) · classifica non ufficiale</p>'}
function liveBox(m){if(!m||m.complete)return"";return'<div class="vg-box vg-live"><b>In corso</b> · aggiornato alle '+E((m.updated||"").slice(11))+' UTC <button class="btn sm" type="button" data-vg="refresh">Aggiorna</button></div>'}
function paste(id,pid){var t=D[id]&&D[id].tm[pid];if(!t)return"";return t.map(function(m){var ex=m[6]||{};return m[1]+(m[2]?" @ "+m[2]:"")+"\n"+(m[3]?"Ability: "+m[3]+"\n":"")+(ex["Tera Type"]?"Tera Type: "+ex["Tera Type"]+"\n":"")+(m[4]?m[4]+" Nature\n":"")+(m[5]||[]).map(function(x){return"- "+x}).join("\n")}).join("\n\n")}
function copyBtn(id,pid){var t=paste(id,pid);return t?'<button class="btn sm" type="button" data-copy="'+E(t)+'">Copia la squadra</button>':'<span class="vg-mute">Squadra non pubblicata</span>'}

/* ---------- Archivio ---------- */
function ctlArc(){var pr=pastRegs();return'<input class="vg-in" id="vg-q" type="search" value="'+E(S.q)+'" placeholder="Cerca un regionale, per esempio Frankfurt" aria-label="Cerca un regionale"><div class="vg-chips"><button type="button" class="btn sm" data-vg="reg" data-v="all" aria-pressed="'+(S.reg==="all")+'">Tutti</button><button type="button" class="btn sm" data-vg="reg" data-v="'+E(IDX.current)+'" aria-pressed="'+(S.reg===IDX.current)+'">'+E(regLabel(IDX.current))+' (attuale)</button>'+(pr.length?'<select id="vg-pr" aria-label="Regolamenti passati"'+(S.reg!=="all"&&S.reg!==IDX.current?' class="on"':"")+'><option value="">Regolamenti passati</option>'+pr.map(function(r){return'<option value="'+E(r)+'"'+(S.reg===r?" selected":"")+">"+E(regLabel(r))+"</option>"}).join("")+"</select>":"")+"</div>"}
function resArc(){var f=S.q.toLowerCase(),h="";
if(S.msg)h+='<div class="vg-box">'+S.msg+"</div>";
if(S.reg!=="all"){var all=IDX.events.filter(function(e){return e.reg===S.reg}),n=all.filter(function(e){return e.collected}).length;
h+='<button type="button" class="vg-ev" data-vg="tot" data-v="'+E(S.reg)+'"><span><b>Totali '+E(regLabel(S.reg))+'</b><small>'+all.length+' regionali · '+n+' con dati</small></span><span class="vg-bd'+(n?" ok":"")+'">'+(n?"Apri":"Nessun dato")+"</span></button>"}
var k=0;IDX.events.forEach(function(e){if(f&&(e.city+" "+e.kind).toLowerCase().indexOf(f)<0)return;if(S.reg!=="all"&&e.reg!==S.reg)return;k++;
var w=(WIN[e.id]||{}).winners||e.winners||{},m=w.masters,line="";
if(m&&m.name)line='Vincitore: <b>'+E(m.name)+"</b>"+(m.cc?" ("+E(m.cc)+")":"")+italia(m.cc);else if(e.winner)line="Vincitore: <b>"+E(e.winner)+"</b>";
["seniors","juniors"].forEach(function(d){var p=w[d];if(p&&p.cc==="IT")line+=' · '+(d==="seniors"?"Seniors":"Juniors")+": <b>"+E(p.name)+"</b>"+italia("IT")});
var st=e.status==="running"?'<span class="vg-bd live">In corso</span>':e.collected?'<span class="vg-bd ok">Dati pronti</span>':'<span class="vg-bd">Da raccogliere</span>';
h+='<button type="button" class="vg-ev" data-vg="ev" data-id="'+e.id+'"><span><b>'+E(e.city)+'</b><small>'+E(dfmt(e.start))+' · '+e.players+' giocatori · '+E(regLabel(e.reg))+"</small>"+(line?"<small>"+line+"</small>":"")+"</span>"+st+"</button>"});
if(!k)h+='<p class="vg-mute">Nessun regionale trovato.</p>';
return h+'<p class="vg-foot">Ogni regionale finito compare qui da solo e si apre con un tocco.</p>'+foot()}

/* ---------- Pokémon ---------- */
var GR={all:"Tutti",top:"Top 256",ph2:"Fase 2",cut:"Top cut"},SO={cnt:"Più usati",wr:"Win rate",top:"Top 256",ph2:"Fase 2"};
function ctlPok(){return evSel(true)+'<div class="vg-row"><input class="vg-in" id="vg-pq" type="search" value="'+E(S.pq)+'" placeholder="Cerca un Pokémon, per esempio Primarina" aria-label="Cerca un Pokémon"><button class="btn vg-f" type="button" data-vg="fp" aria-pressed="'+S.fp+'">Filtra</button></div>'+(S.fp?'<div class="vg-box"><b class="vg-lab">Giocatori considerati</b><div class="vg-chips">'+Object.keys(GR).map(function(k){return'<button type="button" class="btn sm" data-vg="g" data-v="'+k+'" aria-pressed="'+(S.g===k)+'">'+GR[k]+"</button>"}).join("")+'</div><b class="vg-lab">Ordina per</b><div class="vg-chips">'+Object.keys(SO).map(function(k){return'<button type="button" class="btn sm" data-vg="s" data-v="'+k+'" aria-pressed="'+(S.s===k)+'">'+SO[k]+"</button>"}).join("")+"</div></div>":"")}
function val(p){return S.g==="all"?p.count:S.g==="top"?p.top256:S.g==="ph2"?p.day2:p.cut}
function szOf(d){if(d.sz)return d.sz;var m=d.m;return{all:m.players,top:Math.min(m.top||256,m.players),ph2:m.day2_players||0,cut:m.cut_players||0}}
function bars(t,a,tot){if(!a||!a.length)return"";var mx=a[0][1],h='<div class="vg-box"><h3>'+E(t)+"</h3>";a.forEach(function(x){h+='<div class="vg-bar"><span>'+E(x[0])+'</span><i style="width:'+Math.max(3,Math.round(x[1]/mx*100))+'%"></i><span>'+x[1]+" · "+pc(x[1],tot)+"%</span></div>"});return h+"</div>"}
function resPok(d){if(!d)return'<p class="vg-mute">Scegli un regionale dal menu.</p>';
if(S.mon)return detail(d);var sz=szOf(d),tot=sz[S.g]||0,f=S.pq.toLowerCase();
var a=d.pk.filter(function(p){return!f||p.name.toLowerCase().indexOf(f)>=0});
var key={cnt:val,wr:function(p){return p.wins+p.losses?p.wins/(p.wins+p.losses):0},top:function(p){return p.top256},ph2:function(p){return p.day2}}[S.s];
a=a.slice().sort(function(x,y){return key(y)-key(x)});
var h=(d.tot?'<div class="vg-box"><span class="vg-mute">Somma di '+d.n+' regionali con dati. Strumenti e mosse sono sulla Top 256 di ciascuno.</span></div>':liveBox(d.m))+'<p class="vg-sum">'+sz.all+" giocatori"+(sz.ph2?" · "+sz.ph2+" in fase 2":"")+" · strumenti, mosse e nature sulla Top 256</p>";
h+='<div class="vg-tw"><table class="vg-t"><thead><tr><th>Pokémon</th><th>'+(S.g==="all"?"Usati":"Usati ("+GR[S.g]+")")+"</th><th>Vitt.</th><th>Top 256</th><th>Fase 2</th></tr></thead><tbody>";
h+=a.map(function(p){return'<tr class="vg-r" data-vg="mon" data-id="'+E(p.slug)+'"><td>'+dot(p.name)+" "+E(p.name)+"</td><td>"+val(p)+(tot?" · "+pc(val(p),tot)+"%":"")+"</td><td>"+wr(p.wins,p.losses)+"</td><td>"+p.top256+"</td><td>"+p.day2+"</td></tr>"}).join("")||'<tr><td colspan="5">Nessun Pokémon trovato. Controlla il nome.</td></tr>';
return h+"</tbody></table></div>"+foot()}
function detail(d){var p=d.pk.filter(function(x){return x.slug===S.mon})[0];if(!p)return"";var sz=szOf(d),h='<button class="vg-back" type="button" data-vg="bkm">← Torna all’elenco</button><h2 class="vg-h">'+dot(p.name)+" "+E(p.name)+"</h2>";
h+='<div class="vg-grid"><div><b>'+p.count+"</b><small>Usati ("+pc(p.count,sz.all)+"%)</small></div><div><b>"+wr(p.wins,p.losses)+"</b><small>Vittorie</small></div><div><b>"+p.top256+"</b><small>Top 256</small></div><div><b>"+p.day2+"</b><small>Fase 2</small></div><div><b>"+p.cut+"</b><small>Top cut</small></div><div><b>"+pc(p.day2,p.count)+"%</b><small>Arrivo in fase 2</small></div></div>";
if(p.sample){h+='<p class="vg-mute">Nella Top 256: '+p.sample+" giocatori con "+E(p.name)+". Ogni voce con il suo numero.</p>"+bars("Natura",p.nature,p.sample)+bars("Strumento",p.item,p.sample)+bars("Abilità",p.ability,p.sample)+bars("Mosse",p.moves,p.sample);Object.keys(p.extra||{}).forEach(function(k){h+=bars(k,p.extra[k],p.sample)})}
else h+='<div class="vg-box vg-mute">Per questo Pokémon non ci sono squadre pubblicate nella Top 256.</div>';
if(p.partners&&p.partners.length)h+=bars("Compagni di squadra",p.partners.map(function(x){return[nameOf(d,x[0]),x[1]]}),p.count);
if(!d.tot&&p.players&&p.players.length){h+='<div class="vg-box"><h3>Giocatori che lo hanno usato</h3>'+p.players.map(function(id){return d.by[id]}).filter(Boolean).sort(function(a,b){return a[3]-b[3]}).map(function(r){return'<div class="vg-pl"><span><b>'+r[3]+"°</b> "+E(r[1])+' <small class="vg-mute">'+E(r[2])+" · "+r[4]+"-"+r[5]+"</small>"+italia(r[2])+'</span><span class="vg-btns"><button class="btn sm" type="button" data-vg="gosw" data-id="'+r[0]+'">Swiss</button>'+copyBtn(S.ev,r[0])+"</span></div>"}).join("")+"</div>"}
return h+foot()}
function nameOf(d,slug){var f=d.pk.filter(function(x){return x.slug===slug})[0];return f?f.name:slug.replace(/-/g," ").replace(/\b\w/g,function(c){return c.toUpperCase()})}

/* ---------- Swiss ---------- */
function ctlSwi(){return evSel(false)+'<input class="vg-in" id="vg-sq" type="search" value="'+E(S.sq)+'" placeholder="Cerca un giocatore o un paese (es. IT)" aria-label="Cerca un giocatore"><div class="vg-chips"><button type="button" class="btn sm" data-vg="it" aria-pressed="'+S.onlyIt+'">Solo italiani</button></div>'}
function parse(x){var m=/^(-?\d+)([WLTB?])$/.exec(x||"");return m?{o:+m[1],r:m[2]}:null}
var RES={W:"Vittoria",L:"Sconfitta",T:"Pareggio",B:"Bye","?":"–"};
function panel(d,id){var p=d.by[id],rows=(d.sw.p[id]||[]),h='<div class="vg-pan"><table class="vg-sw"><tbody>';
rows.forEach(function(x,i){var e=parse(x);if(!e){h+='<tr><td>R'+(i+1)+'</td><td colspan="3" class="vg-mute">–</td></tr>';return}
var o=e.o>0?d.by[e.o]:null;h+='<tr><td>R'+(i+1)+"</td><td>"+(e.r==="B"?'<span class="vg-mute">Bye</span>':o?'<button class="vg-lnk" type="button" data-vg="opp" data-id="'+o[0]+'">'+E(o[1])+'</button> <small class="vg-mute">'+E(o[2])+"</small>":'<span class="vg-mute">Avversario non identificato</span>')+'</td><td class="vg-mute">'+(o?o[4]+"-"+o[5]:"")+'</td><td class="'+(e.r==="L"?"L":e.r==="W"||e.r==="B"?"W":"")+'">'+RES[e.r]+"</td></tr>"});
h+="</tbody></table>";
var t=d.tm[id];if(t){h+='<div class="vg-team"><div class="vg-trow"><b>Squadra</b>'+copyBtn(S.ev,id)+"</div>"+t.map(function(m){return'<div class="vg-mon">'+dot(m[1])+" <b>"+E(m[1])+'</b> <small class="vg-mute">'+E([m[2],m[3],m[4]].filter(Boolean).join(" · "))+"</small></div>"}).join("")+"</div>"}
else if(p&&p[8])h+='<div class="vg-team"><b>Squadra</b><div class="vg-mute">'+E(p[8].split(",").map(function(s){return nameOf(d,s)}).join(" · "))+"</div></div>";
return h+"</div>"}
function resSwi(d){if(!d)return'<p class="vg-mute">Scegli un regionale dal menu.</p>';var f=S.sq.toLowerCase(),a=d.pl.filter(function(r){return(!f||r[1].toLowerCase().indexOf(f)>=0||r[2].toLowerCase()===f)&&(!S.onlyIt||r[2]==="IT")});
var h=liveBox(d.m)+'<p class="vg-sum">'+a.length+" giocatori · tocca un giocatore per aprire o chiudere la sua swiss</p>";
a.slice(0,S.shown).forEach(function(r){var id=r[0],o=!!S.open[id];h+='<div class="vg-p" id="vgp-'+id+'"><button type="button" class="vg-pr" data-vg="tp" data-id="'+id+'" aria-expanded="'+o+'"><b>'+r[3]+"°</b><span>"+E(r[1])+' <small class="vg-mute">'+E(r[2])+" · "+r[4]+"-"+r[5]+"</small>"+italia(r[2])+'</span><small class="vg-mute">'+(r[7]?"Top cut":r[6]?"Fase 2":"")+"</small></button>"+(o?panel(d,id):"")+"</div>"});
if(a.length>S.shown)h+='<button type="button" class="btn" data-vg="more">Mostra altri '+Math.min(80,a.length-S.shown)+"</button>";
return h+foot()}

/* ---------- disegno ---------- */
function seg(){return'<div class="vg-seg">'+[["arc","Archivio"],["pok","Pokémon"],["swi","Swiss"]].map(function(x){return'<button type="button" data-vg="sec" data-v="'+x[0]+'" aria-pressed="'+(S.sec===x[0])+'">'+x[1]+"</button>"}).join("")+"</div>"}
function ctl(){return S.sec==="arc"?ctlArc():S.sec==="pok"?ctlPok():ctlSwi()}
function drawRes(){var el=host.querySelector("#vg-res");if(!el)return;
if(S.sec==="arc"){el.innerHTML=resArc();return}
el.style.minHeight=el.offsetHeight+"px";el.innerHTML='<p class="vg-mute">Caricamento…</p>';var sec=S.sec,ev=S.ev;
cur().then(function(d){if(S.sec!==sec||S.ev!==ev||!host||!host.contains(el)){el.style.minHeight="";return}el.innerHTML=sec==="pok"?resPok(d):resSwi(d);el.style.minHeight="";applyPos()}).catch(function(){el.style.minHeight="";el.innerHTML='<p class="vg-mute">Non riesco a leggere i dati di questo regionale. Riprova tra poco.</p>'})}
function draw(){if(!host)return;if(!S.ready){host.innerHTML='<p class="vg-mute">'+(S.fail?"I dati di VGC Stats non sono ancora disponibili. Torna a trovarci presto.":"Caricamento…")+"</p>";return}
host.innerHTML='<h2 class="vg-title">VGC Stats</h2><p class="vg-sub">Statistiche dei regionali VGC: Pokémon, strumenti, nature, mosse e swiss di ogni giocatore.</p>'+seg()+'<div id="vg-ctl">'+ctl()+'</div><div id="vg-res"></div>';drawRes()}
function drawKeep(){var y=window.scrollY;draw();window.scrollTo(0,y)}

/* ---------- eventi ---------- */
function act(t){var a=t.dataset.vg,v=t.dataset.v,id=t.dataset.id;savePos();PEND=null;
if(a==="sec"){S.sec=v;S.mon=null;if(v==="swi"&&S.ev==="tot")S.ev=firstEv();draw()}
else if(a==="reg"){S.reg=v;S.msg="";draw()}
else if(a==="ev"){var e=evOf(id);if(e&&e.collected){S.ev=id;S.mon=null;S.sec="pok";draw();window.scrollTo(0,0)}else{S.msg="“"+E(e?e.city:"")+"” non è ancora stato raccolto: comparirà qui appena i dati saranno pronti.";drawKeep()}}
else if(a==="tot"){S.treg=v;S.ev="tot";S.mon=null;S.sec="pok";draw();window.scrollTo(0,0)}
else if(a==="fp"){S.fp=!S.fp;drawKeep()}
else if(a==="g"){S.g=v;drawKeep()}else if(a==="s"){S.s=v;drawKeep()}
else if(a==="mon"){S.mon=id;drawRes();window.scrollTo(0,host.offsetTop)}
else if(a==="bkm"){closeMon()}
else if(a==="it"){S.onlyIt=!S.onlyIt;S.shown=80;drawKeep()}
else if(a==="more"){S.shown+=80;drawRes()}
else if(a==="tp"){setOpen(id,!S.open[id]);drawRes()}
else if(a==="opp"||a==="gosw"){S.sq="";S.onlyIt=false;setOpen(id,true);if(a==="gosw"){S.sec="swi";S.mon=null}
var d=D[S.ev],i=d?d.pl.findIndex(function(r){return String(r[0])===String(id)}):0;if(i>=S.shown)S.shown=i+1;draw();
setTimeout(function(){var el=document.getElementById("vgp-"+id);if(el){el.scrollIntoView({block:"start"});el.classList.add("hl");setTimeout(function(){el.classList.remove("hl")},1600)}},120)}
else if(a==="refresh"){var x=S.ev;delete D[x];Object.keys(C).forEach(function(k){if(k.indexOf(x+"/")===0)delete C[k]});loadEv(x,true).then(function(d){D[x]=d;drawRes()}).catch(drawRes)}}
function firstEv(){var e=IDX.events.filter(function(x){return x.collected&&x.reg===IDX.current})[0]||IDX.events.filter(function(x){return x.collected})[0];return e?e.id:null}
function onClick(ev){var t=ev.target.closest("[data-vg]");if(!t||!host||!host.contains(t))return;act(t)}
function onInput(ev){var t=ev.target,id=t.id;if(id==="vg-q"){S.q=t.value.trim();drawRes()}else if(id==="vg-pq"){S.pq=t.value.trim();drawRes()}else if(id==="vg-sq"){S.sq=t.value.trim();S.shown=80;drawRes()}}
function onChange(ev){var t=ev.target;if(t.id==="vg-ev"){S.ev=t.value==="tot"?"tot":t.value;if(S.ev==="tot")S.treg=S.treg||IDX.current;S.mon=null;draw()}
else if(t.id==="vg-pr"){S.reg=t.value||"all";S.msg="";draw()}}

/* ---------- avvio ---------- */
function init(){return J("index.json").then(function(x){IDX=x;S.treg=x.current;return J("vincitori.json").then(function(w){(w.events||[]).forEach(function(e){WIN[e.id]=e})}).catch(function(){})}).then(function(){S.ev=firstEv();S.ready=true}).catch(function(){S.fail=true})}
window.VGCS={mount:function(h){if(host&&host!==h){host.removeEventListener("click",onClick);host.removeEventListener("input",onInput);host.removeEventListener("change",onChange)}
host=h;h.addEventListener("click",onClick);h.addEventListener("input",onInput);h.addEventListener("change",onChange);
if(S.ready||S.fail){draw();return}draw();init().then(draw)},
back:function(){if(!host||!S.ready||S.fail)return false;
if(S.sec==="swi"){for(var i=OQ.length-1;i>=0;i--){var id=OQ[i],el=document.getElementById("vgp-"+id);if(S.open[id]&&el&&host.contains(el)){setOpen(id,false);drawRes();setTimeout(function(){var e2=document.getElementById("vgp-"+id);if(e2){var r=e2.getBoundingClientRect();if(r.top<0||r.top>window.innerHeight)e2.scrollIntoView({block:"nearest"})}},60);return true}}}
if(S.mon){closeMon();return true}
if(S.sec!=="arc"){savePos();S.sec="arc";S.mon=null;draw();var y=POS.arc;window.scrollTo(0,y!=null?y:0);return true}
return false}};
})();
