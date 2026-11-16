/* CP bar: classifica dei Championship Points da Pokédata (Europa, VG Masters) con la soglia stimata per gli inviti.
   Si carica solo quando si apre dal menu laterale. I dati li prepara il collettore nella seconda repo (dati/cp/). */
(function(){
"use strict";
var URLD=String(window.VGCS_CP||"https://rakings.github.io/VGCdatiAK/dati/cp/vg-europe-masters.json");
var POKEDATA="https://www.pokedata.ovh/2027/?game=VG&region=Europe&division=Masters";
var D=null,OV=null,ONC=null,S={q:"",f:"all",st:null,lim:150},BASE=URLD.replace(/[^\/]*$/,""),IX=null,IXP=null,DC={},TC={},TP={},CUR=[];
var PASSO=150; /* righe mostrate alla volta: 6.000 righe insieme bloccherebbero i telefoni */
function E(x){return String(x).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
function pn(s){return String(s||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/\s+/g," ").trim()}
/* Traduzioni della CP bar (stesso ordine delle lingue del sito: it en es pt fr de ja ko). La lingua si legge a ogni disegno. */
var LGS=["it","en","es","pt","fr","de","ja","ko"];
function lg(){var l="it";try{l=(typeof LANG==="string"&&LANG)||localStorage.getItem("vgc-lang")||"it"}catch(e){}return LGS.indexOf(l)<0?"it":l}
function li(){return LGS.indexOf(lg())}
var TX={
nodet:["Nessun dettaglio disponibile","No details available","Sin detalles disponibles","Sem detalhes disponíveis","Aucun détail disponible","Keine Details verfügbar","詳細はありません","상세 정보 없음"],
eur:["Europa","Europe","Europa","Europa","Europe","Europa","ヨーロッパ","유럽"],
chiudi:["Chiudi","Close","Cerrar","Fechar","Fermer","Schließen","閉じる","닫기"],
cls:["Classifica CP","CP ranking","Clasificación CP","Classificação CP","Classement CP","CP-Rangliste","CPランキング","CP 순위"],
soglia:["soglia","cutoff","corte","corte","seuil","Grenze","ボーダー","커트라인"],
taglio:["Soglia stimata: {cp} CP · {o}","Estimated cutoff: {cp} CP · {o}","Corte estimado: {cp} CP · {o}","Corte estimado: {cp} CP · {o}","Seuil estimé : {cp} CP · {o}","Geschätzte Grenze: {cp} CP · {o}","推定ボーダー: {cp} CP · {o}","예상 커트라인: {cp} CP · {o}"],
altri:["Mostra altri ({n})","Show more ({n})","Mostrar más ({n})","Mostrar mais ({n})","Afficher plus ({n})","Mehr anzeigen ({n})","さらに表示 ({n})","더 보기 ({n})"],
tutta:["Mostra tutta la classifica","Show the full ranking","Mostrar toda la clasificación","Mostrar a classificação completa","Afficher tout le classement","Ganze Rangliste anzeigen","ランキングをすべて表示","전체 순위 보기"],
carico:["Carico tutta la classifica…","Loading the full ranking…","Cargando toda la clasificación…","Carregando a classificação completa…","Chargement du classement complet…","Ganze Rangliste wird geladen…","ランキングを読み込み中…","전체 순위 불러오는 중…"],
nessuno:["Nessun giocatore trovato","No player found","Ningún jugador encontrado","Nenhum jogador encontrado","Aucun joueur trouvé","Kein Spieler gefunden","プレイヤーが見つかりません","플레이어를 찾을 수 없음"],
traprimi:[" tra i primi {n}"," in the top {n}"," entre los primeros {n}"," entre os primeiros {n}"," parmi les {n} premiers"," unter den ersten {n}"," (上位{n}人中)"," (상위 {n}명 중)"],
anchesu:[". La classifica è anche su {a}.",". The ranking is also on {a}.",". La clasificación también está en {a}.",". A classificação também está no {a}.",". Le classement est aussi sur {a}.",". Die Rangliste gibt es auch auf {a}.","。ランキングは{a}でも見られます。",". 순위는 {a}에서도 볼 수 있습니다."],
ita:["Italiani","Italians","Italianos","Italianos","Italiens","Italiener","イタリア人","이탈리아인"],
tutti:["Tutti","All","Todos","Todos","Tous","Alle","すべて","전체"],
tuttii:["tutti i {n}","all {n}","los {n}","todos os {n}","les {n}","alle {n}","全{n}人","전체 {n}명"],
nodisp:["{cp} CP · {o}. Dettaglio non ancora disponibile: vedi {a}.","{cp} CP · {o}. Details not available yet: see {a}.","{cp} CP · {o}. Detalle aún no disponible: mira {a}.","{cp} CP · {o}. Detalhes ainda indisponíveis: veja {a}.","{cp} CP · {o}. Détail pas encore disponible : voir {a}.","{cp} CP · {o}. Details noch nicht verfügbar: siehe {a}.","{cp} CP · {o}。詳細はまだありません: {a} を見てください。","{cp} CP · {o}. 상세 정보 아직 없음: {a} 참고."],
cerco:["Cerco il torneo…","Looking up the tournament…","Buscando el torneo…","Procurando o torneio…","Recherche du tournoi…","Turnier wird gesucht…","大会を検索中…","대회 찾는 중…"],
incorso:["in corso","current","en curso","em andamento","en cours","laufend","進行中","진행 중"],
finale:["finale","final","final","final","final","final","確定","최종"],
sstim:["soglia stimata","estimated cutoff","corte estimado","corte estimado","seuil estimé","geschätzte Grenze","推定ボーダー","예상 커트라인"],
stima:["Stima non ufficiale","Unofficial estimate","Estimación no oficial","Estimativa não oficial","Estimation non officielle","Inoffizielle Schätzung","非公式の推定","비공식 추정"],
ingioc:["{n} giocatori in classifica","{n} players ranked","{n} jugadores en la clasificación","{n} jogadores na classificação","{n} joueurs classés","{n} Spieler in der Rangliste","ランキング{n}人","순위 {n}명"],
cfin:["Classifica finale {s}","Final ranking {s}","Clasificación final {s}","Classificação final {s}","Classement final {s}","Endstand {s}","最終ランキング {s}","최종 순위 {s}"],
chiusa:["chiusa il {d}","closed on {d}","cerrada el {d}","encerrada em {d}","clôturé le {d}","abgeschlossen am {d}","{d}に締切","{d} 마감"],
ultimo:["ultimo aggiornamento {d}","last update {d}","última actualización {d}","última atualização {d}","dernière mise à jour {d}","letztes Update {d}","最終更新 {d}","마지막 업데이트 {d}"],
contr:["controllata il {d}","checked {d}","comprobada el {d}","verificada em {d}","vérifié le {d}","geprüft am {d}","{d}に確認","{d} 확인"],
cambiati:["punti cambiati il {d}","points changed {d}","puntos cambiados el {d}","pontos alterados em {d}","points modifiés le {d}","Punkte geändert am {d}","{d}にポイント変動","{d} 포인트 변경"],
aggiorn:["aggiornata il {d}","updated {d}","actualizada el {d}","atualizada em {d}","mise à jour le {d}","aktualisiert am {d}","{d}に更新","{d} 업데이트"],
cerca:["Cerca un giocatore","Search a player","Buscar un jugador","Buscar um jogador","Chercher un joueur","Spieler suchen","プレイヤーを検索","플레이어 검색"],
dati:["Dati","Data","Datos","Dados","Données","Daten","データ","데이터"],
nonuff:["classifica non ufficiale","unofficial ranking","clasificación no oficial","classificação não oficial","classement non officiel","inoffizielle Rangliste","非公式ランキング","비공식 순위"],
primi:["primi {n}","top {n}","primeros {n}","primeiros {n}","{n} premiers","erste {n}","上位{n}","상위 {n}"],
di:[" di {n}"," of {n}"," de {n}"," de {n}"," sur {n}"," von {n}"," / {n}"," / {n}"],
piede:[" giocatori. La soglia è una stima: il {o} dell'elenco. Torneo e piazzamento si ricavano dai nostri risultati (nome e data): mancano per gli eventi che non sono nel sito."," players. The cutoff is an estimate: the {o} on the list. Tournament and placing come from our results (name and date): they're missing for events not on the site."," jugadores. El corte es una estimación: el {o} de la lista. Torneo y posición salen de nuestros resultados (nombre y fecha): faltan para los eventos que no están en el sitio."," jogadores. O corte é uma estimativa: o {o} da lista. Torneio e colocação vêm dos nossos resultados (nome e data): faltam para eventos que não estão no site."," joueurs. Le seuil est une estimation : la {o} de la liste. Tournoi et classement viennent de nos résultats (nom et date) : ils manquent pour les événements absents du site."," Spieler. Die Grenze ist eine Schätzung: {o} der Liste. Turnier und Platzierung stammen aus unseren Ergebnissen (Name und Datum): Sie fehlen bei Events, die nicht auf der Seite sind.","人。ボーダーは推定です: リストの{o}。大会と順位はこのサイトの結果(名前と日付)から求めています。サイトにない大会は表示されません。","명. 커트라인은 추정치입니다: 목록의 {o}. 대회와 순위는 우리 결과(이름과 날짜)에서 가져오며, 사이트에 없는 대회는 빠져 있습니다."],
carica:["Caricamento…","Loading…","Cargando…","Carregando…","Chargement…","Wird geladen…","読み込み中…","불러오는 중…"],
nondisp:["La classifica non è disponibile in questo momento. Riprova tra poco.","The ranking isn't available right now. Try again shortly.","La clasificación no está disponible ahora. Inténtalo en un rato.","A classificação não está disponível agora. Tente de novo em breve.","Le classement n'est pas disponible pour le moment. Réessaie bientôt.","Die Rangliste ist gerade nicht verfügbar. Versuch es gleich nochmal.","現在ランキングを表示できません。しばらくして再度お試しください。","지금은 순위를 볼 수 없습니다. 잠시 후 다시 시도하세요."],
kind:[["Mondiale","Internazionale","Special Event","Nazionale","Regionale","Mond","Int","Spec","Naz","Reg"],["World Championships","International","Special Event","National","Regional","WC","Int","Spec","Nat","Reg"],["Mundial","Internacional","Special Event","Nacional","Regional","Mund","Int","Spec","Nac","Reg"],["Mundial","Internacional","Special Event","Nacional","Regional","Mund","Int","Spec","Nac","Reg"],["Championnats du monde","International","Special Event","National","Régional","Monde","Int","Spec","Nat","Rég"],["Weltmeisterschaft","International","Special Event","National","Regional","WM","Int","Spec","Nat","Reg"],["世界大会","インターナショナル","スペシャルイベント","ナショナル","リージョナル","世界","Int","Spec","国内","Reg"],["월드 챔피언십","인터내셔널","스페셜 이벤트","내셔널","리저널","월드","Int","Spec","내셔널","Reg"]]
};
function t(k,o){var a=TX[k],s=a[li()];if(k==="kind")return s;if(o)Object.keys(o).forEach(function(x){s=s.split("{"+x+"}").join(o[x])});return s}
function ordp(n){n=Number(n);switch(lg()){case"en":var v=n%100,sfx=(v>=11&&v<=13)?"th":["th","st","nd","rd"][n%10]||"th";return n+sfx+" place";case"es":return n+".º puesto";case"pt":return n+".º lugar";case"fr":return n+(n===1?"re":"e")+" place";case"de":return n+". Platz";case"ja":return n+"位";case"ko":return n+"위";default:return n+"° posto"}}
function loc(){var l=lg();return l==="en"?"en-GB":l}
function num(n){return Number(n).toLocaleString(loc())}
function dm(d){try{var x=new Date(d+"T12:00:00");return isNaN(x.getTime())?String(d||""):x.toLocaleDateString(loc(),{day:"numeric",month:"short"})}catch(e){return String(d||"")}}
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
".cp-d{padding:3px 2px 7px 10px;font-size:.78rem;border-bottom:1px solid var(--line,#5a2a2e)}.cp-e{display:flex;flex-wrap:nowrap;align-items:center;gap:0 7px;padding:3px 0;white-space:nowrap;overflow:hidden}.cp-ed{flex:none;min-width:36px;color:var(--mute,#c9a0a2)}.cp-e>b{flex:none}.cp-e>i{flex:none;font-style:normal;font-weight:700;color:#4ade80}.cp-ev{display:flex;align-items:center;gap:5px;flex:1 1 0;min-width:0;overflow:hidden}.cp-ev .tag{flex:none;font-size:.6rem;padding:1px 6px}.cp-ev b{min-width:0;overflow:hidden;text-overflow:ellipsis}.cp-ev small{flex:none;color:var(--mute,#c9a0a2)}.cp-no{color:var(--mute,#c9a0a2);font-style:italic}"+
".cp-piu{display:block;width:100%;margin:10px 0 0;padding:9px;border-radius:12px;border:1.5px solid var(--line,#5a2a2e);background:var(--card,#2c1316);color:inherit;font:inherit;font-weight:700;cursor:pointer}.cp-st{display:flex;gap:6px;margin:8px 0 0}.cp-vuoto{color:var(--mute,#c9a0a2);padding:16px 4px}.cp-f{font-size:.72rem;color:var(--mute,#c9a0a2);margin:14px 4px 0}.cp-f a{color:inherit;text-decoration:underline}";
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
function tagDi(e){var k=String(e.kind||""),K=t("kind"),i=/world/i.test(k)?0:/international/i.test(k)?1:/special/i.test(k)?2:/national/i.test(k)?3:4;return[K[i],K[i+5],["t-ww","t-int","t-reg","t-gc","t-rg"][i]]}
function linee(r,ab){var st=(r.storia||[]).slice().sort(function(a,b){return a.data<b.data?-1:1}),h="",prev=0;
st.forEach(function(s,i){var m=ab?ab[i].m:[],ev="";
if(m.length===1){var x=m[0],tg=tagDi(x.e);ev='<span class="cp-ev"><span class="tag '+tg[2]+'" title="'+E(tg[0])+'">'+tg[1]+"</span><b>"+E(x.e.city||x.e.name)+"</b><span>· "+E(x.pl)+"°</span>"+(x.w!=null?" <small>("+x.w+"-"+x.l+")</small>":"")+"</span>"}
else if(m.length>1)ev='<span class="cp-ev"><b>'+m.map(function(x){return E(x.e.city||x.e.name)+" "+E(x.pl)+"°"}).join(" · ")+"</b></span>";
h+='<div class="cp-e"><span class="cp-ed">'+E(dm(s.data))+"</span><b>"+num(s.cp)+" CP</b>"+(s.cp>prev?"<i>+"+num(s.cp-prev)+"</i>":"")+ev+"</div>";prev=s.cp});return h||'<div class="cp-e cp-no">'+t("nodet")+'</div>'}
function load(st){var k=st||"_";if(DC[k])return Promise.resolve(DC[k]);return fetch(file(st),{cache:"no-cache"}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json()}).then(function(j){if(!j||!Array.isArray(j.righe)||!j.righe.length)throw new Error("vuoto");DC[k]=j;return j})}
/* Classifica completa (tutti i giocatori, file leggero <nome>-tutti.json): si scarica SOLO quando serve (ricerca, filtro Italia, «Mostra altri»).
   I primi della lista restano quelli del file principale, con la storia dei punti; gli altri hanno solo posto, nome, paese e punti. */
function kst(){return S.st||"_"}
function tutti(){var k=kst();if(TC[k])return Promise.resolve(TC[k]);if(TP[k])return TP[k];if(!D||!D.tutti)return Promise.resolve(null);
TP[k]=fetch(file(S.st).replace(/[^\/]*$/,"")+D.tutti,{cache:"no-cache"}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(j){
if(!j||!Array.isArray(j.r))throw 0;var top={};D.righe.forEach(function(r){top[r.pos]=r});
TC[k]=j.r.map(function(x){return top[x[0]]||{pos:x[0],rank:x[1],name:x[2],country:x[3],cp:x[4],storia:null}});return TC[k]}).catch(function(){TP[k]=null;return null});return TP[k]}
/* Storia dei punti di TUTTI i giocatori (<nome>-storie.json): si scarica solo quando tocchi un giocatore oltre i primi della lista. */
var SC={},SP={};function storie(){var k=kst();if(SC[k])return Promise.resolve(SC[k]);if(SP[k])return SP[k];if(!D||!D.tutti)return Promise.resolve(null);
 SP[k]=fetch(file(S.st).replace(/[^\/]*$/,"")+D.tutti.replace(/-tutti\.json$/,"-storie.json"),{cache:"no-cache"}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(j){if(!j||!j.s)throw 0;SC[k]=j.s;return j.s}).catch(function(){SP[k]=null;return null});return SP[k]}
function tutte(){return TC[kst()]||D.righe}
function head(){return'<div class="cp-h"><b>CP bar</b><span>'+t("eur")+' · VG Masters '+E((D&&D.stagione)||"2027")+'</span><button type="button" class="cp-x" data-cp="x" aria-label="'+t("chiudi")+'">×</button></div>'}
function ov(){if(OV)return OV;OV=document.createElement("div");OV.id="cpov";OV.hidden=true;OV.setAttribute("role","dialog");OV.setAttribute("aria-modal","true");OV.setAttribute("aria-label",t("cls"));document.body.appendChild(OV);
OV.addEventListener("click",function(e){var t=e.target.closest("[data-cp]");if(!t)return;var a=t.getAttribute("data-cp");
if(a==="x")close(true);else if(a==="s"){var st=t.getAttribute("data-v");if(st!==S.st){S.st=st;S.q="";S.lim=PASSO;load(st).then(function(x){D=x;draw()}).catch(function(){})}}else if(a==="m"){S.lim+=PASSO;lista()}else if(a==="f"){S.f=t.getAttribute("data-v");S.lim=PASSO;[].forEach.call(OV.querySelectorAll(".cp-chip"),function(b){b.setAttribute("aria-pressed",String(b.getAttribute("data-v")===S.f))});lista()}else if(a==="r")tog(t)});
OV.addEventListener("input",function(e){if(e.target.id==="cp-q"){S.q=e.target.value;S.lim=PASSO;lista()}});return OV}
function riga(r,i,sg,max){var sotto=sg.cp!=null&&r.cp<sg.cp,dd=sg.cp==null?"":(r.cp>sg.cp?"+"+(r.cp-sg.cp):r.cp===sg.cp?t("soglia"):"−"+(sg.cp-r.cp)),cl=r.cp>sg.cp?"cp-su":r.cp===sg.cp?"cp-pa":"cp-gi";
return'<button type="button" class="cp-r'+(sotto?" cp-sotto":"")+'" data-cp="r" data-i="'+i+'" aria-expanded="false"><span class="cp-pos">'+E(r.pos)+'</span><span class="cp-n"><b>'+E(r.name)+"</b><small>"+E(r.country||"")+'</small></span><span class="cp-cp"><b>'+num(r.cp)+'</b><small class="'+cl+'">'+E(dd)+'</small></span><i class="cp-bar"><u style="width:'+Math.max(2,Math.round(r.cp/max*100))+'%"></u></i></button>'}
function lista(){var el=document.getElementById("cp-list");if(!el||!D)return;var sg=D.soglia||{},max=Math.max.apply(null,D.righe.map(function(r){return r.cp}))||1,q=pn(S.q),h="",cut=false,
caricata=!!TC[kst()],serve=!caricata&&D.tutti&&(q||S.f==="it"||S.lim>D.righe.length);
if(serve){tutti().then(function(x){if(x&&OV&&!OV.hidden){lista();etichette()}});}
var L=tutte().filter(function(r){return!(S.f==="it"&&r.country!=="ITA")&&!(q&&pn(r.name).indexOf(q)<0)});CUR=L.slice(0,S.lim);
CUR.forEach(function(r,i){if(!cut&&sg.posizione&&r.pos>sg.posizione){h+='<div class="cp-cut"><span>'+t("taglio",{cp:num(sg.cp),o:ordp(sg.posizione)})+"</span></div>";cut=true}h+=riga(r,i,sg,max)});
var resto=L.length-CUR.length;
if(resto>0)h+='<button type="button" class="cp-piu" data-cp="m">'+t("altri",{n:num(resto)})+"</button>";
else if(!caricata&&D.tutti&&!serve)h+='<button type="button" class="cp-piu" data-cp="m">'+t("tutta")+'</button>';
if(serve)h+='<p class="cp-vuoto">'+t("carico")+'</p>';
else if(!L.length)h='<p class="cp-vuoto">'+t("nessuno")+(caricata?"":t("traprimi",{n:D.righe.length}))+t("anchesu",{a:'<a href="'+POKEDATA+'" target="_blank" rel="noopener">Pokédata</a>'})+'</p>';
el.innerHTML=h}
function etichette(){var b=OV&&OV.querySelector('[data-cp="f"][data-v="it"]'),c=TC[kst()];if(b&&c)b.textContent=t("ita")+" ("+num(c.filter(function(r){return r.country==="ITA"}).length)+")";
var f=OV&&OV.querySelector(".cp-f b");if(f&&c)f.textContent=t("tuttii",{n:num(c.length)})}
function tog(btn){var nx=btn.nextElementSibling;if(nx&&nx.classList.contains("cp-d")){nx.remove();btn.setAttribute("aria-expanded","false");return}
var r=CUR[Number(btn.getAttribute("data-i"))],d=document.createElement("div");d.className="cp-d";
if(!r)return;if(r.storia===null){d.innerHTML='<div class="cp-e cp-no">…</div>';btn.parentNode.insertBefore(d,btn.nextSibling);btn.setAttribute("aria-expanded","true");
 storie().then(function(m){var v=m&&m[String(r.pos)];if(v){r.storia=v.map(function(x){return{cp:x[0],delta:x[1],data:x[2]}});mostra(r,d)}
 else d.innerHTML='<div class="cp-e cp-no">'+t("nodisp",{cp:num(r.cp),o:ordp(E(r.pos)),a:'<a href="'+POKEDATA+'&search='+encodeURIComponent(r.name)+'" target="_blank" rel="noopener">Pokédata</a>'})+'</div>'});return}
btn.parentNode.insertBefore(d,btn.nextSibling);btn.setAttribute("aria-expanded","true");mostra(r,d)}
function mostra(r,d){d.innerHTML=linee(r,null)+(GJ?"":'<div class="cp-e cp-no">'+t("cerco")+'</div>');
var stag=D.stagione;dati().then(function(ok){if(!d.isConnected)return;var t=ok?trova(r,stag):{k:"nd"};d.innerHTML=linee(r,t.k==="ok"?t.righe:null)})}
function draw(){var o=ov(),sg=D.soglia||{},nIt=tutte().filter(function(r){return r.country==="ITA"}).length,fin=D.finale===true,
sel=IX&&IX.stagioni.length>1?'<div class="cp-st">'+IX.stagioni.map(function(v){return'<button type="button" class="cp-chip" data-cp="s" data-v="'+E(v.stagione)+'" aria-pressed="'+(v.stagione===S.st)+'">'+E(v.stagione)+" · "+(v.stato==="in corso"?t("incorso"):t("finale"))+"</button>"}).join("")+"</div>":"";
o.innerHTML='<div class="cp-w">'+head()+sel+
'<div class="cp-sum"><div class="cp-big"><b>'+(sg.cp!=null?num(sg.cp)+" CP":"—")+"</b><span>"+t("sstim")+(sg.posizione?" ("+ordp(sg.posizione)+")":"")+'</span></div>'+
'<div class="cp-note">'+t("stima")+' · '+(D.giocatori_totali?t("ingioc",{n:num(D.giocatori_totali)})+" · ":"")+(fin?t("cfin",{s:E(D.stagione)})+(D.chiusa?" · "+t("chiusa",{d:E(dm(D.chiusa))}):"")+" · "+t("ultimo",{d:E(dh(D.aggiornato))}):D.controllato?t("contr",{d:E(dh(D.controllato))})+(D.aggiornato&&D.aggiornato!==D.controllato?" · "+t("cambiati",{d:E(dh(D.aggiornato))}):""):t("aggiorn",{d:E(dh(D.aggiornato))}))+"</div></div>"+
'<div class="cp-ctl"><input id="cp-q" type="search" placeholder="'+t("cerca")+'" aria-label="'+t("cerca")+'" value="'+E(S.q)+'"><button type="button" class="cp-chip" data-cp="f" data-v="all" aria-pressed="'+(S.f==="all")+'">'+t("tutti")+'</button><button type="button" class="cp-chip" data-cp="f" data-v="it" aria-pressed="'+(S.f==="it")+'">'+t("ita")+(TC[kst()]||!D.tutti?" ("+nIt+")":"")+"</button></div>"+
'<div id="cp-list"></div><p class="cp-f">'+t("dati")+': <a href="'+POKEDATA+'" target="_blank" rel="noopener">Pokédata</a> · '+t("nonuff")+' · <b>'+(TC[kst()]?t("tuttii",{n:num(TC[kst()].length)}):t("primi",{n:D.righe.length})+(D.giocatori_totali?t("di",{n:num(D.giocatori_totali)}):""))+"</b>"+t("piede",{o:ordp(sg.posizione||90)})+"</p></div>";lista()}
function open(onclose){ONC=onclose||null;css();var o=ov();o.hidden=false;o.scrollTop=0;
o.innerHTML='<div class="cp-w">'+head()+'<p class="cp-vuoto">'+t("carica")+'</p></div>';
indice().then(function(){S.st=IX?IX.corrente:null;return load(S.st)}).then(function(x){D=x;if(!o.hidden)draw()}).catch(function(){if(!o.hidden)o.innerHTML='<div class="cp-w">'+head()+'<p class="cp-vuoto">'+t("nondisp")+'</p></div>'})}
function close(utente){if(OV)OV.hidden=true;if(utente&&ONC){var f=ONC;ONC=null;f()}}
window.CPBAR={open:open,close:function(){close(false)}};
})();
