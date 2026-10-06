"""La interfaz. Un solo documento, sin red externa.

Sin fuentes de Google ni CDN: es una herramienta que se levanta en local y
tiene que funcionar sin internet. Pila de fuentes del sistema y todo el CSS y
el JS en el propio documento.
"""

from __future__ import annotations

from urllib.parse import quote

STYLE = """
:root{
  --ground:#f3f4f6; --panel:#fff; --edge:#d7dbe2; --ink:#171c26;
  --soft:#5a6376; --faint:#8b94a6;
  --measured:#9a5b00; --measured-bg:#fdf3e3;
  --signal:#1d5fb4; --signal-bg:#e8f0fb;
  --good:#1a6b45; --warn:#9a6a00; --bad:#a32f2f;
  --good-bg:#e6f2eb; --warn-bg:#fcf3e0; --bad-bg:#fbeaea;
  --sans:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono:ui-monospace,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;
  color-scheme:light;
}
@media (prefers-color-scheme:dark){:root{
  --ground:#0f1319; --panel:#171c24; --edge:#2b323d; --ink:#e6eaf1;
  --soft:#9aa3b4; --faint:#6b7486;
  --measured:#e5a953; --measured-bg:#2a2013;
  --signal:#6fa8e8; --signal-bg:#15212f;
  --good:#5cc08c; --warn:#dfae4e; --bad:#e58080;
  --good-bg:#122218; --warn-bg:#241c0d; --bad-bg:#2a1414;
  color-scheme:dark;
}}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font-family:var(--sans);
  font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased}
.wrap{max-width:1000px;margin:0 auto;padding:0 20px 64px}
header.top{padding:26px 0 18px;border-bottom:1px solid var(--edge);margin-bottom:22px}
h1{margin:0;font-size:22px;letter-spacing:-.01em}
h1 small{display:block;font-size:13px;font-weight:400;color:var(--soft);
  margin-top:4px;letter-spacing:0}
h2{margin:0 0 4px;font-size:18px}
h3{margin:0 0 6px;font-size:15px}
p{margin:0 0 12px}
.m{font-family:var(--mono);font-variant-numeric:tabular-nums}
.note{font-size:13px;color:var(--faint);max-width:72ch}
nav.tabs{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:20px}
nav.tabs button{font:inherit;font-size:13px;cursor:pointer;padding:8px 14px;
  border:1px solid var(--edge);background:var(--panel);color:var(--soft);
  border-radius:6px}
nav.tabs button[aria-selected="true"]{background:var(--signal-bg);
  border-color:var(--signal);color:var(--signal);font-weight:600}
.panel{background:var(--panel);border:1px solid var(--edge);border-radius:8px;
  padding:18px;margin-bottom:16px}
label{display:block;font-family:var(--mono);font-size:11px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--faint);margin-bottom:6px}
/* La clase explicita manda; el `:has` es solo para no tener que acordarse
   de ponerla. Depender de `:has` a secas ataria el estilo al navegador. */
label.check,
label:has(input[type=checkbox]){font-family:inherit;font-size:13px;
  letter-spacing:0;text-transform:none;color:var(--soft);margin-bottom:4px;
  display:flex;gap:8px;align-items:flex-start;line-height:1.45}
label input[type=checkbox]{margin:3px 0 0;flex:none}
blockquote.nota{margin:12px 0 0;padding:8px 0 8px 13px;
  border-left:3px solid var(--edge);color:var(--soft);font-size:13px}
input[type=text],input[type=number],textarea,select{width:100%;font:inherit;
  padding:9px 11px;border:1px solid var(--edge);border-radius:6px;
  background:var(--ground);color:var(--ink)}
textarea{font-family:var(--mono);font-size:13px;min-height:150px;resize:vertical}
input[type=number]{max-width:140px}
input:focus-visible,textarea:focus-visible,button:focus-visible,
select:focus-visible{outline:2px solid var(--signal);outline-offset:2px}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;margin-top:12px}
.row>div{min-width:0}
.grow{flex:1 1 220px}
button.go{font:inherit;font-size:14px;font-weight:600;cursor:pointer;
  padding:10px 18px;border-radius:6px;border:1px solid var(--signal);
  background:var(--signal);color:#fff}
button.go:disabled{opacity:.55;cursor:progress}
button.ghost{font:inherit;font-size:13px;cursor:pointer;padding:8px 13px;
  border-radius:6px;border:1px solid var(--edge);background:var(--panel);
  color:var(--ink)}
button.ghost[aria-pressed="true"]{background:var(--signal-bg);
  border-color:var(--signal);color:var(--signal)}
.bar{height:8px;background:var(--edge);border-radius:5px;overflow:hidden;
  margin:14px 0 6px}
.bar i{display:block;height:100%;background:var(--signal);width:0;
  transition:width .3s ease}
.err{background:var(--bad-bg);border:1px solid var(--bad);color:var(--bad);
  padding:10px 13px;border-radius:6px;font-size:14px;margin-top:12px}
.ok{background:var(--good-bg);border:1px solid var(--good);color:var(--good);
  padding:10px 13px;border-radius:6px;font-size:14px;margin-top:12px}
.tiles{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));
  margin-bottom:14px}
.tile{background:var(--panel);border:1px solid var(--edge);border-radius:8px;
  padding:12px 14px}
.tile b{display:block;font-family:var(--mono);font-size:23px;font-weight:600;
  font-variant-numeric:tabular-nums;line-height:1.15}
.tile span{display:block;font-size:12px;color:var(--soft);margin-top:3px}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px;min-width:580px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--edge);
  vertical-align:top}
th{font-family:var(--mono);font-size:11px;letter-spacing:.06em;
  text-transform:uppercase;color:var(--faint);font-weight:500;white-space:nowrap}
td.n{font-family:var(--mono);text-align:right;font-variant-numeric:tabular-nums}
tr.hub td{background:var(--good-bg)}
.pill{font-family:var(--mono);font-size:11px;padding:2px 7px;border-radius:10px;
  display:inline-block;white-space:nowrap}
.pill.g{background:var(--good-bg);color:var(--good)}
.pill.w{background:var(--warn-bg);color:var(--warn)}
.pill.b{background:var(--bad-bg);color:var(--bad)}
.pill.n{background:var(--signal-bg);color:var(--signal)}
.action{border-left:3px solid var(--warn);background:var(--warn-bg);
  padding:11px 13px;border-radius:0 6px 6px 0;margin-top:10px;font-size:13px}
.action.b{border-left-color:var(--bad);background:var(--bad-bg)}
.action h4{margin:0 0 5px;font-size:14px}
.action ul{margin:7px 0 0;padding-left:18px}
.action .ver{font-family:var(--mono);font-size:11px;color:var(--soft);
  display:block;margin-top:7px;word-break:break-all}
.quote{border-left:3px solid var(--good);background:var(--good-bg);
  padding:10px 12px;border-radius:0 6px 6px 0;margin-top:9px;font-size:13px}
.quote.no{border-left-color:var(--bad);background:var(--bad-bg)}
.quote .tag{display:block;font-family:var(--mono);font-size:11px;
  color:var(--soft);margin-bottom:5px}
.quote ul{margin:7px 0 0;padding-left:18px;color:var(--soft)}
.bars{display:grid;gap:7px;margin:14px 0}
.fb{display:grid;grid-template-columns:116px 1fr 38px;gap:10px;
  align-items:center;font-size:12px}
.fb .t{height:7px;background:var(--edge);border-radius:4px;overflow:hidden}
.fb .t i{display:block;height:100%;background:var(--signal);
  transition:width .35s ease}
.fb em{font-style:normal;font-family:var(--mono);text-align:right;
  color:var(--soft);font-variant-numeric:tabular-nums}
.fix{display:flex;gap:9px;font-size:13px;padding:7px 0;
  border-bottom:1px solid var(--edge)}
.fix:last-child{border-bottom:0}
.fix b{font-family:var(--mono);color:var(--measured);flex:0 0 auto}
ol.rank{list-style:none;padding:0;margin:12px 0 0;counter-reset:r;display:grid;
  gap:6px}
ol.rank li{counter-increment:r;display:grid;grid-template-columns:26px 1fr auto;
  gap:10px;align-items:center;padding:9px 11px;border:1px solid var(--edge);
  border-radius:6px;background:var(--panel);font-size:13px}
ol.rank li::before{content:counter(r);font-family:var(--mono);font-weight:600;
  color:var(--faint)}
ol.rank li.up{border-color:var(--good);background:var(--good-bg)}
ol.rank li.down{border-color:var(--bad);background:var(--bad-bg)}
ol.rank .v{font-family:var(--mono);font-weight:600;white-space:nowrap;
  font-variant-numeric:tabular-nums}
details{margin-top:12px;font-size:13px}
details summary{cursor:pointer;color:var(--signal);font-weight:500}
pre{background:var(--ground);border:1px solid var(--edge);border-radius:6px;
  padding:12px;overflow-x:auto;font-family:var(--mono);font-size:12px;
  line-height:1.5;max-height:420px}
.muted{color:var(--faint);font-size:13px}
.mal{color:var(--bad)}
.reparto{display:inline-flex;width:92px;height:9px;border-radius:5px;
  overflow:hidden;vertical-align:middle;margin-right:7px;
  border:1px solid var(--edge)}
.reparto i{display:block;height:100%}
.reparto i:nth-child(1){background:var(--signal)}
.reparto i:nth-child(2){background:var(--measured)}
.reparto i:nth-child(3){background:var(--faint)}
td.n b{font-weight:700}
#tar-planes input{margin:0}
#tar-planes td{padding:4px 6px}

/* --- 7. la sala -------------------------------------------------------- */
.sala{display:grid;grid-template-columns:repeat(auto-fill,minmax(166px,1fr));gap:9px}
.ag{border:1px solid var(--edge);border-radius:8px;padding:9px 9px 7px;
  background:var(--panel);transition:border-color .25s,background .25s,opacity .25s}
.ag[data-estado="trabajando"]{border-color:var(--signal);background:var(--signal-bg)}
.ag[data-estado="entregado"]{border-color:var(--good);background:var(--good-bg)}
.ag[data-estado="bloqueado"]{border-color:var(--bad);background:var(--bad-bg)}
.ag[data-estado="libre"]{opacity:.42}
.ag h4{margin:0 0 1px;font-size:12.5px;text-align:center}
.ag .ofi{font-size:10.5px;color:var(--faint);text-align:center;display:block;
  margin-bottom:5px}
.ag .que{font-size:11px;color:var(--soft);line-height:1.35;min-height:44px}
.ag[data-estado="bloqueado"] .que{color:var(--bad)}
.ag .pg{height:4px;background:var(--ground);border-radius:3px;overflow:hidden;
  margin-top:6px;border:1px solid var(--edge)}
.ag .pg i{display:block;height:100%;width:0;background:var(--signal);
  transition:width .3s linear}
.ag[data-estado="entregado"] .pg i{background:var(--good)}
.ag[data-estado="bloqueado"] .pg i{background:var(--bad)}
.ag .reloj{font-family:var(--mono);font-size:10.5px;color:var(--faint);
  display:block;text-align:right;margin-top:3px}
.mu{width:50px;height:50px;display:block;margin:0 auto 2px}
.mu .brazo{transform-origin:16px 29px}
.ag[data-estado="trabajando"] .mu .brazo{animation:pica .62s ease-in-out infinite alternate}
.ag[data-estado="trabajando"] .mu .cabeza{animation:asiente 1.9s ease-in-out infinite}
.ag[data-estado="bloqueado"] .mu{animation:niega .5s ease-in-out infinite}
.ag[data-estado="esperando"] .mu{opacity:.72}
@keyframes pica{from{transform:rotate(-16deg)}to{transform:rotate(20deg)}}
@keyframes asiente{0%,100%{transform:translateY(0)}50%{transform:translateY(1.4px)}}
@keyframes niega{0%,100%{transform:translateX(-1.2px)}50%{transform:translateX(1.2px)}}
.mandos{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-bottom:10px}
.mandos button{font:inherit;font-size:12px;cursor:pointer;padding:5px 9px;
  border:1px solid var(--edge);border-radius:6px;background:var(--panel);
  color:var(--ink)}
.mandos button[aria-pressed="true"]{background:var(--signal-bg);
  border-color:var(--signal);color:var(--signal)}
.mandos .hora{font-family:var(--mono);font-size:12px;color:var(--soft);
  margin-left:auto}
.relevo{font-size:12px;color:var(--signal);background:var(--signal-bg);
  border:1px solid var(--edge);border-radius:6px;padding:6px 9px;margin-top:9px}
.relevo.vacio{color:var(--soft);background:var(--ground)}
tr.gana td{background:var(--good-bg)}
tr.vetada td{background:var(--bad-bg);text-decoration:line-through}
tr.vetada td:last-child{text-decoration:none}
.enm{border-left:3px solid var(--warn);padding:6px 10px;margin:7px 0;
  background:var(--warn-bg);font-size:13px}
.cond{border-left:3px solid var(--signal);padding:6px 10px;margin:7px 0;
  background:var(--signal-bg);font-size:13px}
@media (prefers-reduced-motion:reduce){.mu *,.mu{animation:none!important}}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""

SCRIPT = r"""
var $ = function(s){ return document.querySelector(s); };
var $$ = function(s){ return Array.prototype.slice.call(document.querySelectorAll(s)); };
function esc(s){ return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
function sp(n){ return Number(n).toLocaleString("es-ES"); }

async function post(ruta, cuerpo){
  var r = await fetch(ruta, {method:"POST", headers:{"Content-Type":"application/json"},
                            body: JSON.stringify(cuerpo)});
  var d = await r.json().catch(function(){ return {error:"Respuesta ilegible del servidor."}; });
  if (!r.ok) throw new Error(d.error || ("HTTP " + r.status));
  return d;
}
async function pedir(ruta){
  var r = await fetch(ruta);
  var d = await r.json().catch(function(){ return {error:"Respuesta ilegible del servidor."}; });
  if (!r.ok) throw new Error(d.error || ("HTTP " + r.status));
  return d;
}
function fallo(donde, e){
  $(donde).innerHTML = '<div class="err">' + esc(e.message || e) + '</div>';
}

/* --- pestañas --------------------------------------------------------- */
function abrir(nombre){
  $$("[data-panel]").forEach(function(p){ p.hidden = p.getAttribute("data-panel") !== nombre; });
  $$("nav.tabs button").forEach(function(b){
    b.setAttribute("aria-selected", String(b.getAttribute("data-tab") === nombre));
  });
  try { location.hash = nombre; } catch(e){}
}

/* --- fichero a textarea ---------------------------------------------- */
function conectarFichero(inputSel, areaSel){
  var input = $(inputSel);
  if (!input) return;
  input.addEventListener("change", function(){
    var f = input.files && input.files[0];
    if (!f) return;
    var lector = new FileReader();
    lector.onload = function(){ $(areaSel).value = String(lector.result); };
    lector.readAsText(f);
  });
}

/* --- 1. auditoría ----------------------------------------------------- */
var ACCION = {
  desactivar_archivo: ["Desactivar el archivo completo", "b"],
  recategorizar: ["Recategorizar (preferido)", ""],
  noindex: ["Poner en noindex", ""],
  ninguna: ["Sin accion", "g"]
};

async function auditar(){
  var boton = $("#aud-go");
  boton.disabled = true;
  $("#aud-out").innerHTML = "";
  $("#aud-prog").hidden = false;
  $("#aud-bar").style.width = "0%";
  $("#aud-step").textContent = "Arrancando...";
  try{
    var trabajo = await post("/api/auditoria", {
      site: $("#aud-site").value,
      thin_words: Number($("#aud-thin").value) || 600,
      interval: Number($("#aud-int").value) || 1,
      max_archives: Number($("#aud-max").value) || 40
    });
    var datos = await esperar(trabajo.id);
    pintarAuditoria(datos.result);
  } catch(e){ fallo("#aud-out", e); }
  finally{ boton.disabled = false; $("#aud-prog").hidden = true; }
}

function esperar(id){
  return new Promise(function(resolver, rechazar){
    var tic = setInterval(async function(){
      try{
        var r = await fetch("/api/job/" + id);
        var j = await r.json();
        if (!r.ok) throw new Error(j.error || "El trabajo se perdio.");
        var pct = j.total ? Math.min(99, Math.round(100 * j.done / j.total)) : 5;
        $("#aud-bar").style.width = pct + "%";
        $("#aud-step").textContent = j.step + "  ·  " + j.elapsed + " s";
        if (j.state === "corriendo") return;
        clearInterval(tic);
        if (j.state === "fallo") return rechazar(new Error(j.error));
        var res = await fetch("/api/job/" + id + "/resultado");
        var d = await res.json();
        if (!res.ok) return rechazar(new Error(d.error));
        $("#aud-bar").style.width = "100%";
        resolver(d);
      } catch(e){ clearInterval(tic); rechazar(e); }
    }, 400);
  });
}

function pintarAuditoria(r){
  var s = r.summary, h = "";
  h += '<div class="tiles">' +
    tile(s.archives, "archivos medidos") +
    tile(s.indexable, "indexables") +
    tile(s.actions, "acciones pendientes") +
    tile(s.posts, "articulos en sitemap") +
    tile(s.requests, "peticiones hechas") + "</div>";

  if (s.intent && Object.keys(s.intent).length){
    var info = s.intent.informational || 0;
    h += '<p class="note">Contenido informacional puro: <strong class="m">' + info +
      '%</strong>. Las consultas informacionales tienen 99,9% de cobertura de AI ' +
      'Overviews y 74,3% acaba sin clic, asi que ese porcentaje es la parte del ' +
      'contenido que puede rankear sin recibir la visita.</p>';
  }

  h += '<div class="scroll"><table><thead><tr><th>Archivo</th><th>Tipo</th>' +
    '<th>HTTP</th><th>Indexable</th><th>Posts</th><th>Palabras</th>' +
    '<th>Veredicto</th><th>Accion</th></tr></thead><tbody>';
  r.archives.forEach(function(a){
    var etiqueta = ACCION[a.action] || [a.action, ""];
    var clasePill = a.verdict === "hub" ? "g" : a.verdict === "duplicado" ? "b" : "w";
    h += "<tr" + (a.verdict === "hub" ? ' class="hub"' : "") + ">" +
      '<td class="m">' + esc(rutaDe(a.url)) + "</td><td>" + a.kind + "</td>" +
      '<td class="n">' + a.status + "</td><td>" + (a.indexable ? "si" : "no (noindex)") +
      '</td><td class="n">' + a.posts + '</td><td class="n">' + sp(a.words) + "</td>" +
      '<td><span class="pill ' + clasePill + '">' + a.verdict + "</span></td><td>" +
      (a.action === "ninguna" ? '<span class="muted">—</span>' : esc(etiqueta[0])) +
      "</td></tr>";
  });
  h += "</tbody></table></div>";

  var pendientes = r.archives.filter(function(a){ return a.action !== "ninguna"; });
  if (pendientes.length){
    h += "<h3 style='margin-top:22px'>Acciones, por prioridad</h3>";
    pendientes.forEach(function(a, i){
      var etiqueta = ACCION[a.action] || [a.action, ""];
      h += '<div class="action ' + etiqueta[1] + '"><h4>' + (i+1) + ". " +
        esc(etiqueta[0]) + " — <span class='m'>" + esc(rutaDe(a.url)) + "</span></h4>" +
        esc(a.reason);
      if (a.candidates && a.candidates.length){
        h += "<ul>" + a.candidates.map(function(c){
          return "<li class='m'>" + esc(rutaDe(c)) + "</li>"; }).join("") + "</ul>";
      }
      h += '<span class="ver">' + esc(a.verification) + "</span></div>";
    });
  } else {
    h += '<p class="note" style="margin-top:18px">Ningun archivo necesita accion. ' +
      'Los que hay son hubs legitimos o ya estan en noindex.</p>';
  }

  if (r.warnings && r.warnings.length){
    h += "<h3 style='margin-top:22px'>Avisos</h3><ul class='note'>" +
      r.warnings.map(function(w){ return "<li>" + esc(w) + "</li>"; }).join("") + "</ul>";
  }
  if (r.notes && r.notes.length){
    h += "<ul class='note'>" + r.notes.map(function(n){
      return "<li>" + esc(n) + "</li>"; }).join("") + "</ul>";
  }
  h += '<details><summary>Ver el informe completo en markdown</summary><pre>' +
    esc(r.markdown) + "</pre></details>";
  $("#aud-out").innerHTML = h;
}

function tile(valor, texto){
  return '<div class="tile"><b>' + sp(valor) + "</b><span>" + texto + "</span></div>";
}
function rutaDe(u){
  try { var p = new URL(u); return p.pathname + (p.search || ""); } catch(e){ return u; }
}

/* --- 2. citabilidad --------------------------------------------------- */
var FACTORES = [["Extraibilidad","ext"],["Atribuibilidad","atr"],
                ["Escasez","esc"],["Alineacion","ali"]];

async function medirCitabilidad(){
  var boton = $("#cit-go"); boton.disabled = true;
  try{
    var r = await post("/api/citabilidad", {text: $("#cit-text").value});
    var h = '<div class="tiles">' +
      '<div class="tile"><b style="color:' + colorNota(r.score) + '">' + r.score +
      '</b><span>citabilidad sobre 100</span></div>' +
      tile(r.liftable.length, "frases citables") +
      tile(r.candidates, "frases con cifra") +
      tile(r.question_headings, "encabezados pregunta") + "</div>";

    h += '<div class="bars">';
    FACTORES.forEach(function(f){
      var todas = r.liftable.concat(r.worst);
      var vals = todas.map(function(q){ return q[f[1]]; });
      var avg = vals.length ? Math.round(vals.reduce(function(a,b){return a+b;},0)/vals.length) : 0;
      h += '<div class="fb"><span>' + f[0] + '</span><div class="t"><i style="width:' +
        avg + '%' + (f[1]==="esc" ? ";background:var(--measured)" : "") +
        '"></i></div><em>' + avg + "</em></div>";
    });
    h += "</div>";

    if (r.liftable.length){
      h += "<h3>Frases que un modelo levantaria</h3>";
      r.liftable.forEach(function(q){ h += cita(q, false); });
    } else {
      h += "<h3>Ninguna frase es citable tal como esta escrita</h3>";
      r.worst.forEach(function(q){ h += cita(q, true); });
    }
    if (r.fixes.length){
      h += "<h3 style='margin-top:20px'>Arreglos, por cuantas frases afectan</h3>";
      r.fixes.forEach(function(f){
        h += '<div class="fix"><b>x' + f.count + "</b><span>" + esc(f.fix) + "</span></div>";
      });
    }
    h += '<p class="note" style="margin-top:16px">' + esc(r.describe) + "</p>";
    $("#cit-out").innerHTML = h;
  } catch(e){ fallo("#cit-out", e); }
  finally{ boton.disabled = false; }
}
function colorNota(n){
  return n >= 60 ? "var(--good)" : n >= 30 ? "var(--warn)" : "var(--bad)";
}
function cita(q, malo){
  var h = '<div class="quote' + (malo ? " no" : "") + '"><span class="tag">' +
    q.total + "/100 · ext " + q.ext + " · atr " + q.atr + " · esc " + q.esc +
    " · ali " + q.ali + "</span>" + esc(q.text);
  if (malo && q.blockers && q.blockers.length){
    h += "<ul>" + q.blockers.map(function(b){
      return "<li>" + esc(b) + "</li>"; }).join("") + "</ul>";
  }
  return h + "</div>";
}

/* --- 3. oportunidad --------------------------------------------------- */
var OPORT = null, MODO = "valor";

async function medirOportunidad(){
  var boton = $("#opo-go"); boton.disabled = true;
  try{
    OPORT = await post("/api/oportunidad", {csv: $("#opo-csv").value});
    pintarOportunidad();
  } catch(e){ fallo("#opo-out", e); }
  finally{ boton.disabled = false; }
}

function pintarOportunidad(){
  if (!OPORT) return;
  var r = OPORT;
  var lista = MODO === "valor" ? r.by_value : r.by_clicks;
  var porClics = r.by_clicks.map(function(o){ return o.subject; });
  var h = '<div class="tiles">' +
    tile(Math.round(r.totals.adjusted), "clics/mes estimados") +
    '<div class="tile"><b style="color:var(--bad)">' + sp(Math.round(r.totals.lost)) +
    '</b><span>clics que se queda la respuesta generada</span></div>' +
    tile(r.demoted.length, "filas que bajan por valor") +
    tile(r.totals.skipped, "descartadas por volumen bajo") + "</div>";

  h += '<div class="row" style="margin:0 0 4px">' +
    '<button class="ghost" id="opo-clics" aria-pressed="' + (MODO!=="valor") +
    '">Por clics (SEO clasico)</button>' +
    '<button class="ghost" id="opo-valor" aria-pressed="' + (MODO==="valor") +
    '">Por valor esperado</button></div>';

  h += '<ol class="rank">';
  lista.forEach(function(o, i){
    var antes = porClics.indexOf(o.subject) + 1, ahora = i + 1;
    var clase = MODO === "valor" && ahora - antes >= 2 ? "down"
      : MODO === "valor" && antes - ahora >= 2 ? "up" : "";
    h += '<li class="' + clase + '"><div><strong>' + esc(o.subject) + "</strong><br>" +
      '<span class="note m">' + sp(o.impressions) + " impresiones · posicion " +
      o.position + " · " + o.intent + " · " + o.band + "</span></div>" +
      '<span class="v">' + (MODO === "valor" ? o.value + " valor" : "+" + o.raw + " clics") +
      "</span></li>";
  });
  h += "</ol>";

  if (r.demoted.length || r.promoted.length){
    h += "<h3 style='margin-top:20px'>Lo que cambia respecto a priorizar por clics</h3>";
    h += "<ul class='note'>";
    r.promoted.forEach(function(m){
      h += "<li><strong>sube</strong> «" + esc(m.subject) + "»: puesto " +
        m.before + " → " + m.after + "</li>"; });
    r.demoted.forEach(function(m){
      h += "<li><strong>baja</strong> «" + esc(m.subject) + "»: puesto " +
        m.before + " → " + m.after + "</li>"; });
    h += "</ul>";
  }
  h += '<p class="note">' + esc(r.describe) + "</p>";
  $("#opo-out").innerHTML = h;
  $("#opo-valor").addEventListener("click", function(){ MODO="valor"; pintarOportunidad(); });
  $("#opo-clics").addEventListener("click", function(){ MODO="clics"; pintarOportunidad(); });
}

/* --- 4. clusters ------------------------------------------------------ */
async function medirClusters(){
  var boton = $("#clu-go"); boton.disabled = true;
  try{
    var r = await post("/api/clusters", {csv: $("#clu-csv").value,
                                         cap: Number($("#clu-cap").value) || 24});
    var s = r.summary;
    var h = '<div class="tiles">' +
      tile(s.keywords, "keywords leidas") +
      tile(s.clusters, "clusters") +
      tile(s.pages, "paginas") +
      tile(s.merged, "keywords fusionadas") +
      tile(s.months, "meses de plan") + "</div>";

    h += '<p class="note">Solape cero: ninguna keyword primaria se asigna a dos ' +
      'paginas, y las casi duplicadas se fusionan (' + s.merged + ') en vez de ' +
      'generar dos paginas que compiten. ' + s.covered + ' de ' + s.keywords +
      ' keywords cubiertas, ' + s.links + ' enlaces pilar-satelite.</p>';

    var mix = Object.keys(r.intent_mix).map(function(k){
      return k + " " + r.intent_mix[k] + "%"; }).join(" · ");
    if (mix) h += '<p class="note">Mezcla de intencion: ' + esc(mix) + "</p>";

    h += '<h3 style="margin-top:18px">Validacion ' +
      (r.validation.passed ? '<span class="pill g">pasa</span>'
                           : '<span class="pill b">bloqueada</span>') + "</h3>";
    if (!r.validation.findings.length){
      h += '<p class="note">Sin hallazgos.</p>';
    } else {
      h += "<ul class='note'>" + r.validation.findings.map(function(f){
        return "<li><span class='pill " + (f.blocking ? "b" : "w") + "'>" +
          f.severity + "</span> <code>" + f.code + "</code> — " + esc(f.message) +
          "</li>"; }).join("") + "</ul>";
    }

    r.months.forEach(function(m){
      h += "<h3 style='margin-top:20px'>Mes " + m.month + " — " + m.pages.length +
        " paginas</h3><div class='scroll'><table><thead><tr><th>Pagina</th>" +
        "<th>Rol</th><th>Cluster</th><th>Intencion</th><th>Min. palabras</th>" +
        "<th>Prioridad</th></tr></thead><tbody>";
      m.pages.forEach(function(p){
        h += "<tr><td>" + esc(p.term) +
          (p.secondary.length ? "<br><span class='note'>+ " +
            esc(p.secondary.join(", ")) + "</span>" : "") +
          '</td><td><span class="pill ' + (p.role === "pillar" ? "n" : "") + '">' +
          p.role + "</span></td><td class='m'>" + esc(p.cluster) + "</td><td>" +
          p.intent + '</td><td class="n">' + sp(p.min_words) +
          '</td><td class="n">' + sp(p.priority) + "</td></tr>";
      });
      h += "</tbody></table></div>";
    });
    $("#clu-out").innerHTML = h;
  } catch(e){ fallo("#clu-out", e); }
  finally{ boton.disabled = false; }
}

/* --- 5. memoria -------------------------------------------------------
 *
 * Esta pestana es la unica del banco que escribe en disco. Las otras cuatro
 * miden y se olvidan; esta acumula, y por eso es la que hace que el sistema
 * mejore con el uso en vez de repetir el mismo trabajo cada mes.
 */
function cliente(){ return ($("#mem-cliente").value || "").trim().toLowerCase(); }

async function verMemoria(){
  var c = cliente();
  if (!c){ fallo("#mem-out", new Error("Escribe un nombre de cliente.")); return; }
  try {
    var r = await fetch("/api/memoria?cliente=" + encodeURIComponent(c));
    var d = await r.json();
    if (!r.ok) throw new Error(d.error || ("HTTP " + r.status));
    pintarMemoria(d);
  } catch(e){ fallo("#mem-out", e); }
}

function pintarMemoria(d){
  var obs = d.metricas.reduce(function(a,m){ return a + m.medidas; }, 0);
  var h = '<div class="tiles">' +
    tile(d.paginas.length, "paginas en el corpus") +
    tile(obs, "observaciones medidas") +
    tile(d.rechazos.total, "rechazos registrados") +
    tile(d.rechazos.al_brief.length, "instrucciones al brief") +
    "</div>";

  h += '<div class="panel"><h3>Huella del sitio</h3><p class="note">' +
    sp(d.huella.hashes) + " hashes sobre " + sp(d.huella.fragmentos) +
    " fragmentos" + (d.huella.estimada ? " (estimado)" : " (exacto)") +
    ". El almacen no guarda ni una frase del contenido: solo hashes." +
    "</p></div>";

  if (d.migraciones && d.migraciones.length){
    h += '<div class="panel"><h3>Migrado al abrir</h3><p class="note m">' +
      esc(d.migraciones.join(", ")) + "</p></div>";
  }

  if (d.paginas.length){
    h += '<div class="panel"><h3>Paginas que cuentan para el solape</h3>' +
      '<div class="scroll"><table><thead><tr><th>Slug</th><th>Rol</th>' +
      '<th class="n">Palabras</th><th class="n">Fragmentos</th>' +
      '<th>Firma</th><th>Guardada</th></tr></thead><tbody>';
    d.paginas.forEach(function(p){
      h += "<tr><td>" + esc(p.slug) + "</td><td>" + esc(p.rol || "—") +
        '</td><td class="n">' + sp(p.palabras) + '</td><td class="n">' +
        sp(p.fragmentos) + "</td><td>" + (p.exacta ? "exacta" : "estimada") +
        '</td><td class="m">' + esc((p.guardada || "").slice(0,16)) +
        "</td></tr>";
    });
    h += "</tbody></table></div></div>";
  } else {
    h += '<div class="panel"><h3>Corpus vacio</h3><p class="note">Sin ninguna ' +
      "pagina guardada, la compuerta de solape no puede comprobar nada y lo " +
      "dice en el informe en vez de dar la pagina por limpia.</p></div>";
  }

  if (d.metricas.length){
    h += '<div class="panel"><h3>Lo que el sistema ha medido, y lo que solo se ha declarado</h3>' +
      '<div class="scroll"><table><thead><tr><th>Metrica</th>' +
      '<th class="n">Medidas</th><th class="n">Media medida</th>' +
      '<th class="n">Declaradas</th></tr></thead><tbody>';
    d.metricas.forEach(function(m){
      h += "<tr><td>" + esc(m.nombre) + '</td><td class="n">' +
        sp(m.medidas) + '</td><td class="n">' +
        (m.media === null ? "—" : m.media) + '</td><td class="n">' +
        (m.declaradas ? sp(m.declaradas) : "—") + "</td></tr>";
    });
    h += "</tbody></table></div><p class='note'>Un prior de peso 20 sigue " +
      "mandando hasta que llegan ~60 observaciones medidas. Las declaradas se " +
      "guardan pero no cuentan: la media de esta tabla es solo de lo medido." +
      "</p></div>";
  }

  if (d.rechazos.total){
    h += '<div class="panel"><h3>Rechazos del revisor</h3><p class="note">' +
      esc(d.rechazos.tendencia) + "</p>";
    if (d.rechazos.al_brief.length){
      h += "<h4>Lo que vuelve al brief</h4><ul>";
      d.rechazos.al_brief.forEach(function(i){ h += "<li>" + esc(i) + "</li>"; });
      h += "</ul>";
    }
    h += "</div>";
  }
  $("#mem-out").innerHTML = h;
}

async function comprobarBorrador(){
  var boton = $("#mem-check");
  boton.disabled = true;
  try {
    var r = await post("/api/memoria/comprobar",
                       {cliente: cliente(), text: $("#mem-text").value});
    var s = r.sitio;
    var h = '<div class="panel"><h3>Contra este sitio</h3><div class="tiles">' +
      '<div class="tile"><b>' + Math.round(s.valor * 100) +
      '%</b><span>solape maximo</span></div>' +
      tile(s.comparadas, "paginas comparadas") +
      '</div><p class="note">' + esc(s.lectura) + "</p></div>";

    if (r.cartera.length){
      h += '<div class="panel"><h3>Contra el resto de la cartera</h3>' +
        '<p class="note">Es la guarda del quinto patron de scaled content ' +
        "abuse: repartir la misma salida entre varios sitios para ocultar la " +
        "escala. Se comprueba antes de publicar, no despues.</p>" +
        '<div class="scroll"><table><thead><tr><th>Sitio</th>' +
        '<th class="n">Frases</th><th class="n">Esqueleto</th><th>Veredicto</th>' +
        "</tr></thead><tbody>";
      r.cartera.forEach(function(x){
        h += "<tr><td>" + esc(x.otro) + '</td><td class="n">' +
          (x.frases * 100).toFixed(1) + '%</td><td class="n">' +
          Math.round(x.esqueleto * 100) + "%</td><td>" +
          (x.bloquea ? "<b>BLOQUEA</b>" : "ok") + "</td></tr>";
      });
      h += "</tbody></table></div></div>";
    }
    $("#mem-check-out").innerHTML = h;
  } catch(e){ fallo("#mem-check-out", e); }
  finally { boton.disabled = false; }
}

async function guardarPagina(){
  var boton = $("#mem-save");
  boton.disabled = true;
  try {
    var r = await post("/api/memoria/pagina", {
      cliente: cliente(), slug: $("#mem-slug").value,
      text: $("#mem-text").value, url: $("#mem-url").value,
      role: $("#mem-role").value});
    $("#mem-check-out").innerHTML = '<div class="ok"><b>Guardada ' +
      esc(r.guardada.slug) + "</b> — " + sp(r.guardada.palabras) +
      " palabras, " + sp(r.guardada.fragmentos) + " fragmentos. " +
      esc(r.solape_previo.lectura) + " El corpus tiene ya " + r.paginas +
      " pagina(s).</div>";
    verMemoria();
  } catch(e){ fallo("#mem-check-out", e); }
  finally { boton.disabled = false; }
}

async function guardarObservacion(){
  var boton = $("#mem-obs-go");
  boton.disabled = true;
  try {
    var r = await post("/api/memoria/observacion", {
      cliente: cliente(), metrica: $("#mem-metrica").value,
      valor: $("#mem-valor").value, fuente: $("#mem-fuente").value,
      nota: $("#mem-nota").value});
    $("#mem-obs-out").innerHTML = '<div class="ok">Apunte ' + r.guardada.seq +
      " guardado. " + r.vigentes + " vigente(s), " + r.medidas + " medida(s)." +
      (r.aviso ? " <b>" + esc(r.aviso) + "</b>" : "") + "</div>";
    verMemoria();
  } catch(e){ fallo("#mem-obs-out", e); }
  finally { boton.disabled = false; }
}

/* --- 6. negocio -------------------------------------------------------
 *
 * Las cifras de aqui no son una recomendacion de precio: son un calculo. Lo
 * que vale es lo que pasa al mover una palanca, que es lo que distingue un
 * plan de una tarifa escrita en una servilleta.
 */
function numero(sel, defecto){
  var v = parseFloat($(sel).value);
  return isFinite(v) ? v : defecto;
}

function planesDelFormulario(){
  return $$("#tar-planes tr[data-plan]").map(function(fila){
    var c = fila.querySelectorAll("input");
    return {nombre: c[0].value, precio_mes: parseFloat(c[1].value),
            paginas: parseInt(c[2].value, 10),
            minutos_revision: parseFloat(c[3].value)};
  });
}

async function calcularTarifa(){
  var boton = $("#tar-go");
  boton.disabled = true;
  try {
    var r = await post("/api/tarifa", {
      planes: planesDelFormulario(),
      coste_hora: numero("#tar-hora", 45),
      herramientas_mes: numero("#tar-herr", 120),
      reparaciones: numero("#tar-rep", 0.6),
      fijos_mes: numero("#tar-fijos", 4000),
      minutos_medidos: $("#tar-cron").checked,
      lotes: $("#tar-lotes").checked,
    });
    pintarTarifa(r);
  } catch(e){ fallo("#tar-out", e); }
  finally { boton.disabled = false; }
}

function pintarTarifa(r){
  var h = '<div class="panel"><h3>Margen por plan</h3>' +
    '<div class="scroll"><table><thead><tr><th>Plan</th>' +
    '<th class="n">$/mes</th><th class="n">Paginas</th><th class="n">$/pagina</th>' +
    '<th class="n">Coste/pagina</th><th class="n">Margen</th>' +
    "<th>Reparto del coste</th></tr></thead><tbody>";
  r.planes.forEach(function(p){
    h += "<tr><td>" + esc(p.nombre) + '</td><td class="n">' + sp(p.precio_mes) +
      '</td><td class="n">' + sp(p.paginas) + '</td><td class="n">' +
      p.precio_pagina.toFixed(2) + '</td><td class="n">' +
      p.coste_pagina.toFixed(2) + '</td><td class="n">' +
      (p.sano ? "" : "<b>") + p.margen_pct.toFixed(0) + "%" +
      (p.sano ? "" : "</b>") + "</td><td>" + barras(p.reparto) + "</td></tr>";
  });
  h += "</tbody></table></div>";

  var peor = r.planes.slice().sort(function(a,b){
    return b.reparto.revision - a.reparto.revision; })[0];
  if (peor){
    h += '<p class="note">El reparto es la conclusion, no el margen: en «' +
      esc(peor.nombre) + "» el modelo es el " + peor.reparto.modelo +
      "% del coste y la revision el " + peor.reparto.revision +
      "%. Competir en precio de tokens es optimizar la parte barata, y bajar " +
      "de modelo no ahorra: sube los minutos de revision, que es la cara.</p>";
  }
  h += "</div>";

  h += '<div class="panel"><h3>Que pasa si se mueve una palanca</h3>' +
    '<p class="note">Un plan con buen margen que se rompe al cronometrar la ' +
    "revision no es un plan con buen margen: es un plan que depende de una " +
    "cifra que nadie ha medido.</p>";
  Object.keys(r.sensibilidad).forEach(function(nombre){
    h += "<h4>" + esc(nombre) + "</h4><ul>";
    r.sensibilidad[nombre].forEach(function(c){
      var pts = Math.round(Math.abs(c.caida));
      h += "<li>" + esc(c.palanca) + ": de " + esc(c.desde) + " a " +
        esc(c.hasta) + ", el margen " + (c.caida > 0 ? "cae " : "sube ") +
        pts + (pts === 1 ? " punto" : " puntos") + " hasta " +
        c.despues.toFixed(0) + "%" +
        (c.rompe ? ' <b class="mal">rompe el plan</b>' : "") + "</li>";
    });
    h += "</ul>";
  });
  if (r.fragiles.length){
    h += '<div class="err">Frágiles: ' + esc(r.fragiles.join(", ")) +
      ". Un solo cambio razonable los deja por debajo del margen minimo.</div>";
  }
  h += "</div>";

  var claves = Object.keys(r.punto_muerto || {});
  if (claves.length){
    h += '<div class="panel"><h3>Punto muerto</h3><p class="note">Es la unica ' +
      "cifra que decide si esto es un negocio o un trabajo: si hacen falta " +
      "mas clientes de los que una persona puede atender, el plan esta mal " +
      "puesto por bonito que sea el margen.</p><ul>";
    claves.forEach(function(k){
      h += "<li>" + esc(r.punto_muerto[k].lectura) + "</li>";
    });
    h += "</ul></div>";
  }

  h += '<div class="panel"><h3>Lo que este calculo NO cuenta</h3>' +
    '<p class="note">Estas partidas no caben en un coste por pagina porque no ' +
    "escalan con las paginas sino con los clientes. Son las que convierten un " +
    "margen de folleto en el margen real.</p><ul>" +
    "<li><b>Captacion.</b> Reparte sobre la vida del contrato, no sobre el mes.</li>" +
    "<li><b>Alta y auditoria inicial.</b> El primer mes de un cliente no se " +
    "parece a los siguientes.</li>" +
    "<li><b>Gestion de cuenta.</b> Crece con clientes, no con paginas.</li>" +
    "<li><b>Bajas.</b> Sin tasa de bajas medida, el valor de vida es un deseo.</li>" +
    '</ul><p class="note">' + r.medido + "% de las cifras de este calculo son " +
    "mediciones; el resto son supuestos declarados.</p></div>";

  h += '<details><summary>Ver la tarifa completa en markdown</summary><pre>' +
    esc(r.markdown) + "</pre></details>";
  $("#tar-out").innerHTML = h;
}

function barras(rep){
  var partes = [["modelo", rep.modelo], ["revision", rep.revision],
                ["herram.", rep.herramientas]];
  return '<span class="reparto">' + partes.map(function(x){
    return '<i style="width:' + Math.max(x[1], 0) + '%" title="' + x[0] + " " +
      x[1] + '%"></i>';
  }).join("") + "</span> " + partes.filter(function(x){ return x[1] >= 10; })
    .map(function(x){ return x[0] + " " + x[1] + "%"; }).join(" · ");
}

async function generarInforme(){
  var boton = $("#inf-go");
  boton.disabled = true;
  try {
    var r = await post("/api/informe", {
      cliente: ($("#inf-cliente").value || "").trim().toLowerCase(),
      periodo: $("#inf-periodo").value,
      site: $("#inf-site").value,
      pages_blocked: numero("#inf-bloq", 0),
      publishable_as_is: numero("#inf-pub", 0),
      monthly_cap: numero("#inf-tope", 24),
      languages: ($("#inf-idiomas").value || "").split(",")
        .map(function(s){ return s.trim(); }).filter(Boolean),
      languages_human_reviewed: ($("#inf-revisados").value || "").split(",")
        .map(function(s){ return s.trim(); }).filter(Boolean),
    });
    pintarInforme(r);
  } catch(e){ fallo("#inf-out", e); }
  finally { boton.disabled = false; }
}

var ORIGENES = {medido: "medido", estimado: "estimado", supuesto: "SUPUESTO"};

function pintarInforme(r){
  var h = '<div class="tiles">' +
    '<div class="tile"><b>' + r.medido + '%</b><span>de las cifras son ' +
    "mediciones</span></div>" +
    '<div class="tile"><b>' + (r.entregable ? "si" : "no") +
    '</b><span>el mes se puede cerrar</span></div>' +
    tile(r.incognitas.length, "cosas que no sabemos") + "</div>";
  h += '<div class="panel"><h3>' + esc(r.titular) + "</h3></div>";

  r.secciones.forEach(function(s){
    h += '<div class="panel"><h3>' + esc(s.titulo) + "</h3>";
    if (s.cifras.length){
      h += '<div class="scroll"><table><thead><tr><th>Dato</th><th>Valor</th>' +
        "<th>Procedencia</th><th>De donde sale</th></tr></thead><tbody>";
      s.cifras.forEach(function(f){
        var marca = ORIGENES[f.origen] || f.origen;
        h += "<tr><td>" + esc(f.label) + "</td><td><b>" + esc(f.valor) +
          "</b></td><td>" + (f.origen === "supuesto"
            ? '<b class="mal">' + marca + "</b>" : marca) +
          '</td><td class="muted">' + esc(f.base || "") + "</td></tr>";
      });
      h += "</tbody></table></div>";
    }
    s.lineas.forEach(function(l){
      // El `>` es marca de cita de markdown. En HTML no se enseña: se cita.
      h += /^>\s/.test(l)
        ? '<blockquote class="nota">' + esc(l.replace(/^>\s*/, "")) + "</blockquote>"
        : '<p class="note">' + esc(l) + "</p>";
    });
    h += "</div>";
  });

  h += '<div class="panel"><h3>Lo que todavia no sabemos</h3>';
  if (r.incognitas.length){
    h += '<p class="note">Esta seccion la genera el sistema. No se puede ' +
      "quitar sin quitar los datos que la producen.</p><ul>";
    r.incognitas.forEach(function(u){ h += "<li>" + esc(u) + "</li>"; });
    h += "</ul>";
  } else {
    h += '<p class="note">Nada pendiente de medir en el alcance contratado.</p>';
  }
  h += "</div>";

  h += '<div class="panel"><h3>Que haria cambiar la recomendacion</h3><ul>';
  r.alternativas.forEach(function(w){ h += "<li>" + esc(w) + "</li>"; });
  h += "</ul></div>";

  if (r.bloqueantes.length){
    h += '<div class="err"><b>Sin resolver:</b><ul>';
    r.bloqueantes.forEach(function(b){ h += "<li>" + esc(b) + "</li>"; });
    h += "</ul></div>";
  }
  h += '<details><summary>Ver el informe completo en markdown, listo para ' +
    'enviar</summary><pre>' + esc(r.markdown) + "</pre></details>";
  $("#inf-out").innerHTML = h;
}


/* --- 7. el estudio del canal ------------------------------------------ */
var PROPS = {
  lupa: '<circle cx="37" cy="19" r="5" fill="none" stroke="currentColor" stroke-width="2"/>' +
        '<line x1="41" y1="23" x2="45" y2="27" stroke="currentColor" stroke-width="2"/>',
  archivo: '<rect x="32" y="14" width="12" height="12" rx="1.5" fill="none" stroke="currentColor" stroke-width="2"/>' +
           '<line x1="32" y1="18" x2="44" y2="18" stroke="currentColor" stroke-width="2"/>',
  calculadora: '<rect x="33" y="13" width="11" height="15" rx="1.5" fill="none" stroke="currentColor" stroke-width="2"/>' +
    '<rect x="35" y="15" width="7" height="3" fill="currentColor" opacity=".5"/>' +
    '<circle cx="36.5" cy="21.5" r="1" fill="currentColor"/><circle cx="40.5" cy="21.5" r="1" fill="currentColor"/>' +
    '<circle cx="36.5" cy="25" r="1" fill="currentColor"/><circle cx="40.5" cy="25" r="1" fill="currentColor"/>',
  balanza: '<line x1="38" y1="12" x2="38" y2="27" stroke="currentColor" stroke-width="2"/>' +
    '<line x1="31" y1="16" x2="45" y2="16" stroke="currentColor" stroke-width="2"/>' +
    '<path d="M31 16 l-2.5 6 h5 z" fill="currentColor"/><path d="M45 16 l-2.5 6 h5 z" fill="currentColor"/>',
  pluma: '<line x1="32" y1="28" x2="43" y2="14" stroke="currentColor" stroke-width="2"/>' +
         '<path d="M32 28 l1 -4.5 l3 1.8 z" fill="currentColor"/>',
  microfono: '<rect x="35" y="12" width="6" height="11" rx="3" fill="none" stroke="currentColor" stroke-width="2"/>' +
    '<line x1="38" y1="23" x2="38" y2="27" stroke="currentColor" stroke-width="2"/>' +
    '<line x1="34" y1="27" x2="42" y2="27" stroke="currentColor" stroke-width="2"/>',
  tijeras: '<line x1="33" y1="13" x2="42" y2="24" stroke="currentColor" stroke-width="2"/>' +
    '<line x1="42" y1="13" x2="33" y2="24" stroke="currentColor" stroke-width="2"/>' +
    '<circle cx="32" cy="26" r="2.2" fill="none" stroke="currentColor" stroke-width="1.6"/>' +
    '<circle cx="43" cy="26" r="2.2" fill="none" stroke="currentColor" stroke-width="1.6"/>',
  trozos: '<rect x="31" y="13" width="6" height="6" rx="1" fill="currentColor"/>' +
    '<rect x="39" y="17" width="6" height="6" rx="1" fill="currentColor" opacity=".65"/>' +
    '<rect x="33" y="22" width="6" height="6" rx="1" fill="currentColor" opacity=".4"/>',
  marco: '<rect x="31" y="14" width="13" height="12" rx="1.5" fill="none" stroke="currentColor" stroke-width="2"/>' +
    '<rect x="34" y="17" width="7" height="6" fill="currentColor" opacity=".45"/>',
  calendario: '<rect x="31" y="14" width="13" height="12" rx="1.5" fill="none" stroke="currentColor" stroke-width="2"/>' +
    '<line x1="31" y1="18" x2="44" y2="18" stroke="currentColor" stroke-width="2"/>' +
    '<circle cx="35" cy="22" r="1.1" fill="currentColor"/><circle cx="39.5" cy="22" r="1.1" fill="currentColor"/>',
  grafico: '<rect x="32" y="21" width="3.4" height="7" fill="currentColor" opacity=".55"/>' +
    '<rect x="37" y="17" width="3.4" height="11" fill="currentColor" opacity=".8"/>' +
    '<rect x="42" y="13" width="3.4" height="15" fill="currentColor"/>'
};

function munequito(a){
  return '<svg class="mu" viewBox="0 0 48 48" style="color:' + a.color + '" aria-hidden="true">' +
    '<path d="M7 42 V30 a9 9 0 0 1 18 0 V42 Z" fill="' + a.color + '" opacity=".55"/>' +
    '<g class="brazo"><rect x="15" y="27.3" width="15" height="3.4" rx="1.7" fill="' + a.color + '"/></g>' +
    '<g class="cabeza"><circle cx="16" cy="13" r="6" fill="' + a.color + '"/></g>' +
    (PROPS[a.figura] || "") + "</svg>";
}

function etiquetaReloj(e){
  if (e.e === "trabajando") return "quedan " + e.r + " min";
  if (e.e === "esperando") return "entra en " + e.r + " min";
  if (e.e === "entregado") return "entregado";
  if (e.e === "bloqueado") return "parado";
  return "libre";
}

var SALA = {dia:1, cuadro:0, ms:240, corriendo:false, visible:false,
            timer:null, pelis:{}, peli:null, pidiendo:false};
var PASO = 5;

function pintarFotograma(){
  var peli = SALA.peli;
  if (!peli) return;
  var f = peli.fotogramas[Math.min(SALA.cuadro, peli.fotogramas.length - 1)];
  var h = "";
  peli.agentes.forEach(function(a, i){
    var e = f.estados[i];
    var texto = (e.e === "bloqueado" && a.motivo) ? a.motivo : a.tarea;
    h += '<div class="ag" data-estado="' + e.e + '" title="' +
      esc(a.responsable_de) + '">' + munequito(a) +
      "<h4>" + esc(a.nombre) + '</h4><span class="ofi">' + esc(a.rol) + "</span>" +
      '<div class="que">' + esc(texto) + "</div>" +
      '<div class="pg"><i style="width:' + Math.round(e.p * 100) + '%"></i></div>' +
      '<span class="reloj">' + etiquetaReloj(e) + "</span></div>";
  });
  $("#sal-grid").innerHTML = h;

  var hora = ("0" + Math.floor(peli.dia.hora / 60)).slice(-2) + ":" +
             ("0" + (peli.dia.hora % 60)).slice(-2);
  $("#sal-hora").textContent = peli.dia.nombre + " · minuto " + f.minuto +
    " de " + peli.jornada + " · publica a las " + hora;

  if (f.relevo){
    $("#sal-relevo").className = "relevo";
    $("#sal-relevo").textContent = "Relevo: " + f.relevo.de + " entrega «" +
      f.relevo.entrega + "» a " + f.relevo.a;
  } else {
    $("#sal-relevo").className = "relevo vacio";
    $("#sal-relevo").textContent = f.resumen;
  }
  $$("#sal-dias button").forEach(function(b){
    b.setAttribute("aria-pressed", String(Number(b.getAttribute("data-dia")) === SALA.dia));
  });
}

async function cargarDia(dia){
  if (SALA.pelis[dia]){
    SALA.peli = SALA.pelis[dia];
    pintarFotograma();
    return;
  }
  if (SALA.pidiendo) return;
  SALA.pidiendo = true;
  try {
    var peli = await pedir("/api/estudio/pelicula?dia=" + dia + "&paso=" + PASO);
    SALA.pelis[dia] = peli;
    SALA.peli = peli;
    pintarFotograma();
  } catch(e){
    fallo("#sal-relevo", e);
    SALA.corriendo = false;
  } finally {
    SALA.pidiendo = false;
  }
}

function ticSala(){
  if (!SALA.corriendo || !SALA.visible || !SALA.peli) return;
  SALA.cuadro += 1;
  if (SALA.cuadro >= SALA.peli.fotogramas.length){
    SALA.cuadro = 0;
    SALA.dia = SALA.dia % 7 + 1;
    cargarDia(SALA.dia);
    return;
  }
  pintarFotograma();
}

function marchaSala(correr){
  SALA.corriendo = correr;
  $("#sal-play").setAttribute("aria-pressed", String(correr));
  $("#sal-play").textContent = correr ? "Pausa" : "Seguir";
}

function ritmoSala(ms){
  SALA.ms = ms;
  if (SALA.timer) clearInterval(SALA.timer);
  SALA.timer = setInterval(ticSala, SALA.ms);
}

function salaVisible(visible){
  SALA.visible = visible;
  if (!visible) return;
  if (!SALA.timer) ritmoSala(SALA.ms);
  cargarDia(SALA.dia);
}

/* --- el tribunal, el plan, la carrera y la pila ----------------------- */
var JUECES_COL = ["algoritmo", "riesgo", "operacion"];

function pintarTribunal(d){
  var h = '<div class="scroll"><table><thead><tr><th>Estrategia</th>' +
    "<th>Cadencia</th><th>J1 algoritmo</th><th>J2 riesgo</th>" +
    "<th>J3 operacion</th><th>Media</th></tr></thead><tbody>";
  d.tabla.forEach(function(f){
    var clase = f.ganadora ? "gana" : (f.vetada ? "vetada" : "");
    h += '<tr class="' + clase + '"><td><b>' + esc(f.nombre) + "</b></td><td>" +
      esc(f.cadencia) + "</td>";
    JUECES_COL.forEach(function(j){
      h += '<td class="n">' + f[j].toFixed(2) + "</td>";
    });
    h += '<td class="n"><b>' + f.media.toFixed(2) + "</b>" +
      (f.vetada ? ' <span class="mal">vetada</span>' : "") + "</td></tr>";
  });
  h += "</tbody></table></div>";

  h += '<p class="note" style="margin-top:10px">' + esc(d.fallo.resumen) + "</p>";
  d.fallo.enmiendas.forEach(function(e){
    h += '<div class="enm"><b>Enmienda de ' + esc(e.juez) + "</b> — " +
      esc(e.criterio) + ", " + e.nota + "/5: " + esc(e.enmienda) +
      '<br><span class="muted">' + esc(e.porque) + "</span></div>";
  });
  d.fallo.condiciones.forEach(function(c){
    h += '<div class="cond"><b>Condicion</b> — ' + esc(c) + "</div>";
  });

  d.jueces.forEach(function(j){
    var punto = d.fallo.puntuaciones.filter(function(p){
      return p.juez === j.clave && p.estrategia === d.fallo.ganadora;
    })[0];
    h += "<details><summary>" + esc(j.nombre + " · " + j.oficio) +
      " — rubrica y notas de la ganadora</summary>" +
      '<p class="note">' + esc(j.mira) +
      (j.veto ? " <b>Tiene veto por debajo de " + j.veto.toFixed(1) + ".</b>" : "") +
      '</p><div class="scroll"><table><thead><tr><th>Criterio</th><th>Peso</th>' +
      "<th>Nota</th><th>Por que</th></tr></thead><tbody>";
    punto.desglose.forEach(function(f){
      h += "<tr><td>" + esc(f.pregunta) + '</td><td class="n">' +
        Math.round(f.peso * 100) + '%</td><td class="n">' + f.nota + "/5</td><td>" +
        esc(f.porque) + (f.enmienda ? ' <b class="mal">enmienda</b>' : "") + "</td></tr>";
    });
    h += "</tbody></table></div></details>";
  });
  $("#est-tribunal").innerHTML = h;
}

function pintarSemana(d){
  var h = tile(d.plan.horas_semana, "horas a la semana de una persona") +
    tile(d.plan.dias.filter(function(x){ return x.formato !== "short"; }).length,
         "largos a la semana") +
    tile(d.plan.dias.filter(function(x){ return x.formato === "short"; }).length,
         "Shorts a la semana");
  h = '<div class="tiles">' + h + "</div>";
  h += '<p class="note">' + esc(d.plan.resumen) + "</p>";
  h += '<div class="scroll"><table><thead><tr><th>Dia</th><th>Hora</th>' +
    "<th>Formato</th><th>Angulo</th><th>Trabajo</th><th>Publica</th>" +
    "</tr></thead><tbody>";
  d.plan.dias.forEach(function(x){
    var hora = ("0" + Math.floor(x.hora / 60)).slice(-2) + ":" +
               ("0" + (x.hora % 60)).slice(-2);
    h += "<tr><td>" + esc(x.nombre) + "</td><td>" + hora + "</td><td>" +
      esc(x.formato) + "</td><td>" + esc(x.tipo) + '</td><td class="n">' +
      x.minutos + " min</td><td>" + esc(x.titulo) + "</td></tr>";
  });
  h += "</tbody></table></div>";

  h += "<h3>Carga por agente</h3><p class='note'>El cuello de botella decide " +
    "que herramienta merece la pena pagar, y no al contrario.</p>";
  var tope = Math.max.apply(null, Object.keys(d.plan.carga).map(function(k){
    return d.plan.carga[k];
  }));
  h += '<div class="scroll"><table><tbody>';
  Object.keys(d.plan.carga).forEach(function(k){
    var m = d.plan.carga[k];
    h += "<tr><td>" + esc(k) + '</td><td style="width:62%">' +
      '<div class="pg" style="height:9px"><i style="width:' +
      Math.round(m / tope * 100) + '%"></i></div></td><td class="n">' + m +
      " min</td></tr>";
  });
  h += "</tbody></table></div>";
  d.plan.cadencia.forEach(function(v){
    h += '<p class="note">' + (v.pasa ? "✓ " : "✗ ") + esc(v.motivo) + "</p>";
  });
  $("#est-semana").innerHTML = h;
}

function pintarCarrera(d){
  var c = d.carrera, r = d.rutas;
  var h = '<div class="tiles">' +
    tile(c.dias_hasta_el_cambio, "dias hasta que sube el liston") +
    tile(c.vistas_necesarias, "vistas de documental para la puerta") +
    tile(c.minutos_por_vista, "minutos vistos por vista") +
    tile(r.veces_mas_vistas, "veces mas vistas pide la ruta de Shorts") +
    "</div>";
  h += '<p class="note"><b>' + esc(c.veredicto) + "</b></p>";
  h += '<div class="scroll"><table><thead><tr><th>Ruta a la misma puerta</th>' +
    "<th>Vistas necesarias</th><th>Publicidad que dejan</th><th>RPM</th>" +
    "</tr></thead><tbody>";
  [["Documentales (horas de visualizacion)", r.ruta_horas],
   ["Shorts (vistas en 90 dias)", r.ruta_shorts]].forEach(function(par){
    var x = par[1];
    h += "<tr><td>" + par[0] + '</td><td class="n">' + sp(x.vistas) +
      '</td><td class="n">' + sp(x.ingreso[0]) + "–" + sp(x.ingreso[1]) +
      ' $</td><td class="n">' + x.rpm[0] + "–" + x.rpm[1] + "</td></tr>";
  });
  h += "</tbody></table></div>";
  h += '<p class="note"><span class="medido">NO MEDIDO</span> Los RPM son ' +
    esc(r.fuente_rpm) + ". La hipotesis de vistas por documental la pone quien " +
    "la escribe: hasta que haya tres meses de datos propios, esto es una " +
    "ecuacion y no una prevision.</p>";
  $("#est-carrera").innerHTML = h;
}

function pintarPila(d){
  var p = d.herramientas;
  var h = '<div class="tiles">' +
    tile(p.coste_mes, "euros al mes de pila") +
    tile(p.horas_sin_herramientas, "horas sin herramientas") +
    tile(p.horas_semana, "horas con la pila") +
    tile(p.coste_por_hora_ahorrada, "euros por hora ahorrada") +
    "</div>";
  h += '<p class="note">' + esc(p.resumen) + "</p>";
  h += '<div class="scroll"><table><thead><tr><th>Herramienta</th><th>Oficio</th>' +
    "<th>Coste/mes</th><th>Quita</th><th>Para que</th></tr></thead><tbody>";
  function fila(x, dentro){
    var coste = x.coste_mes === null ? "NO VERIFICADO"
      : (x.coste_mes ? sp(x.coste_mes) + " €" : "gratis");
    return "<tr" + (dentro ? "" : ' class="muted"') + "><td><b>" + esc(x.nombre) +
      "</b></td><td>" + esc(x.oficio) + "</td><td" +
      (x.precio_verificado ? ' class="n"' : ' class="n medido"') + ">" + coste +
      '</td><td class="n">' + (x.minutos ? x.minutos + " min" : "—") + "</td><td>" +
      esc(x.nota) + (x.riesgo ? '<br><b class="mal">Riesgo:</b> ' + esc(x.riesgo) : "") +
      "</td></tr>";
  }
  p.elegidas.forEach(function(x){ h += fila(x, true); });
  p.sin_precio.forEach(function(x){ h += fila(x, false); });
  p.descartadas.forEach(function(x){ h += fila(x, false); });
  h += "</tbody></table></div>";
  h += '<p class="note">Las descartadas y las de precio no verificado salen en ' +
    "gris: no cuentan en el ahorro. Un precio aproximado en una hoja de costes " +
    "es el error que este repositorio existe para no cometer.</p>";
  $("#est-pila").innerHTML = h;
}

function pintarCalendario(d){
  var h = '<div class="scroll"><table><thead><tr><th>Fecha</th><th>Dia</th>' +
    "<th>Semana</th><th>Hora</th><th>Formato</th><th>Que se publica</th>" +
    "</tr></thead><tbody>";
  d.calendario.forEach(function(e){
    if (!e.publica){
      h += '<tr class="muted"><td>' + e.fecha + "</td><td>" + esc(e.dia_semana) +
        "</td><td>0</td><td>—</td><td>reserva</td><td>" + esc(e.nota) + "</td></tr>";
      return;
    }
    var hora = ("0" + Math.floor(e.hora / 60)).slice(-2) + ":" +
               ("0" + (e.hora % 60)).slice(-2);
    h += "<tr><td>" + e.fecha + "</td><td>" + esc(e.dia_semana) + "</td><td>" +
      e.semana + "</td><td>" + hora + "</td><td>" + esc(e.formato) + " · " +
      esc(e.tipo) + "</td><td>" + esc(e.titulo) + "</td></tr>";
  });
  h += "</tbody></table></div>";
  $("#est-calendario").innerHTML = h;
}

async function verEstudio(){
  var boton = $("#est-go");
  boton.disabled = true;
  try {
    var d = await pedir("/api/estudio?presupuesto=" +
      encodeURIComponent($("#est-presupuesto").value || 0) + "&vistas=" +
      encodeURIComponent($("#est-vistas").value || 0));
    pintarTribunal(d);
    pintarSemana(d);
    pintarCarrera(d);
    pintarPila(d);
    pintarCalendario(d);
  } catch(e){
    fallo("#est-tribunal", e);
  } finally {
    boton.disabled = false;
  }
}

/* --- arranque --------------------------------------------------------- */
$$("nav.tabs button").forEach(function(b){
  b.addEventListener("click", function(){
    var nombre = b.getAttribute("data-tab");
    abrir(nombre);
    salaVisible(nombre === "estudio");
  });
});
$("#aud-go").addEventListener("click", auditar);
$("#aud-site").addEventListener("keydown", function(e){ if (e.key === "Enter") auditar(); });
$("#cit-go").addEventListener("click", medirCitabilidad);
$("#opo-go").addEventListener("click", medirOportunidad);
$("#clu-go").addEventListener("click", medirClusters);
conectarFichero("#opo-file", "#opo-csv");
conectarFichero("#clu-file", "#clu-csv");
$("#mem-go").addEventListener("click", verMemoria);
$("#mem-check").addEventListener("click", comprobarBorrador);
$("#mem-save").addEventListener("click", guardarPagina);
$("#mem-obs-go").addEventListener("click", guardarObservacion);
$("#tar-go").addEventListener("click", calcularTarifa);
$("#inf-go").addEventListener("click", generarInforme);
$("#est-go").addEventListener("click", verEstudio);
$("#est-vistas").addEventListener("keydown", function(e){ if (e.key === "Enter") verEstudio(); });
$("#sal-play").addEventListener("click", function(){ marchaSala(!SALA.corriendo); });
$("#sal-paso").addEventListener("change", function(){
  ritmoSala(Number($("#sal-paso").value) || 240);
});
$$("#sal-dias button").forEach(function(b){
  b.addEventListener("click", function(){
    SALA.dia = Number(b.getAttribute("data-dia"));
    SALA.cuadro = 0;
    cargarDia(SALA.dia);
  });
});

var EJEMPLO_CIT = "# Coste de un sistema septico aerobico\n\n" +
  "## Cuanto cuesta instalar un sistema aerobico en Texas?\n\n" +
  "La instalacion completa costo 14.237 $ de mediana en Texas en 2026, sobre una muestra propia de 40 presupuestos reales.\n\n" +
  "## Y el permiso del condado?\n\n" +
  "Este cuesta unos 500 $ mas, aproximadamente.\n";
$("#cit-text").value = EJEMPLO_CIT;
$("#opo-csv").value = "Consulta,Clics,Impresiones,Posicion\n" +
  "que es un sistema septico aerobico,160,10000,12\n" +
  "cuanto cuesta un sistema septico aerobico,40,2200,13\n" +
  "instalador septico cerca de mi,12,900,11.5\n" +
  "como funciona la nitrificacion,50,4000,14\n" +
  "mejor bomba de aire septica,9,700,9\n";
$("#clu-csv").value = "Keyword,Search Volume,CPC\n" +
  "sistema septico aerobico,5000,6\n" +
  "cuanto cuesta un sistema septico aerobico,2000,14\n" +
  "precio sistema septico aerobico,1500,13\n" +
  "alarma septica pitando,900,3\n" +
  "alarma septica no para de pitar,400,3\n" +
  "mejor bomba de aire septica,700,9\n" +
  "bomba de aire septica opiniones,300,8\n" +
  "que es nitrificacion,12000,0.5\n" +
  "instalador septico cerca de mi,1100,18\n" +
  "mantenimiento septico aerobico,800,7\n";

var inicial = (location.hash || "#auditoria").slice(1);
abrir(["auditoria","citabilidad","oportunidad","clusters","memoria","negocio",
       "estudio"].indexOf(inicial) >= 0
      ? inicial : "auditoria");
medirCitabilidad();
verEstudio();
marchaSala(true);
salaVisible(inicial === "estudio");
"""

BODY = """
<div class="wrap">
<header class="top">
  <h1>Banco de pruebas SEO-GEO
    <small>Auditoria, citabilidad, oportunidad y plan de clusters. Corre en tu
    maquina, sin dependencias y sin enviar nada a ningun sitio.</small></h1>
</header>

<nav class="tabs" role="tablist">
  <button data-tab="auditoria" aria-selected="true">1 · Auditoria</button>
  <button data-tab="citabilidad" aria-selected="false">2 · Citabilidad</button>
  <button data-tab="oportunidad" aria-selected="false">3 · Oportunidad</button>
  <button data-tab="clusters" aria-selected="false">4 · Clusters</button>
  <button data-tab="memoria" aria-selected="false">5 · Memoria</button>
  <button data-tab="negocio" aria-selected="false">6 · Negocio</button>
  <button data-tab="estudio" aria-selected="false">7 · Estudio</button>
</nav>

<!-- 1 -->
<div data-panel="auditoria">
  <div class="panel">
    <h2>Que le pasa a este sitio</h2>
    <p class="note">Mide el sitio en vivo: archivos indexables finos de autor,
    categoria y etiqueta, canonicals duplicados, sitemap declarado en robots.txt
    y reparto de intencion del contenido. Cada afirmacion lleva su respuesta HTTP
    y su hora de consulta.</p>
    <div class="row">
      <div class="grow">
        <label for="aud-site">Dominio</label>
        <input type="text" id="aud-site" placeholder="ejemplo.com"
               autocomplete="off" spellcheck="false">
      </div>
      <div>
        <label for="aud-thin">Umbral fino</label>
        <input type="number" id="aud-thin" value="600" min="100" max="5000" step="50">
      </div>
      <div>
        <label for="aud-int">Intervalo (s)</label>
        <input type="number" id="aud-int" value="1" min="0.1" max="5" step="0.1">
      </div>
      <div>
        <label for="aud-max">Max. archivos</label>
        <input type="number" id="aud-max" value="40" min="1" max="200">
      </div>
      <div><button class="go" id="aud-go" type="button">Auditar</button></div>
    </div>
    <div id="aud-prog" hidden>
      <div class="bar"><i id="aud-bar"></i></div>
      <p class="note m" id="aud-step"></p>
    </div>
    <p class="note" style="margin-top:10px">El intervalo no es un detalle: una
    rafaga contra el sitio de un cliente es una forma de rompérselo. Por defecto
    1 segundo entre peticiones.</p>
  </div>
  <div id="aud-out"></div>
</div>

<!-- 2 -->
<div data-panel="citabilidad" hidden>
  <div class="panel">
    <h2>Que frases puede citar un buscador</h2>
    <p class="note">Un modelo no cita paginas: cita frases que puede levantar
    enteras, atribuir a alguien y que no encuentra en otras cincuenta fuentes.
    Esto puntua las cuatro condiciones y lista las frases concretas.</p>
    <label for="cit-text">Texto en markdown</label>
    <textarea id="cit-text" spellcheck="false"></textarea>
    <div class="row"><button class="go" id="cit-go" type="button">Medir</button></div>
  </div>
  <div id="cit-out"></div>
</div>

<!-- 3 -->
<div data-panel="oportunidad" hidden>
  <div class="panel">
    <h2>Donde esta la oportunidad de verdad</h2>
    <p class="note">Exportacion de Search Console. Descuenta lo que se queda la
    respuesta generada y ordena por valor esperado, no por clics: un clic
    informacional no vale lo que uno transaccional.</p>
    <label for="opo-csv">CSV de Search Console (consulta o pagina, impresiones, posicion)</label>
    <textarea id="opo-csv" spellcheck="false"></textarea>
    <div class="row">
      <div><button class="go" id="opo-go" type="button">Analizar</button></div>
      <div><label for="opo-file">o sube el fichero</label>
        <input type="file" id="opo-file" accept=".csv,text/csv"></div>
    </div>
  </div>
  <div id="opo-out"></div>
</div>

<!-- 4 -->
<div data-panel="clusters" hidden>
  <div class="panel">
    <h2>Plan de contenido con solape cero</h2>
    <p class="note">CSV de keywords de Semrush, Ahrefs, DataForSEO o a mano.
    Agrupa en clusters, asigna pilares y satelites sin repetir ninguna keyword
    primaria, y reparte en meses respetando el tope.</p>
    <label for="clu-csv">CSV de keywords</label>
    <textarea id="clu-csv" spellcheck="false"></textarea>
    <div class="row">
      <div><button class="go" id="clu-go" type="button">Planificar</button></div>
      <div><label for="clu-cap">Tope mensual</label>
        <input type="number" id="clu-cap" value="24" min="1" max="120"></div>
      <div><label for="clu-file">o sube el fichero</label>
        <input type="file" id="clu-file" accept=".csv,text/csv"></div>
    </div>
    <p class="note" style="margin-top:10px">El tope de 24 es una decision de
    riesgo, no una limitacion tecnica: cuatro paginas al dia en un dominio sin
    revision es el patron que Google penaliza como scaled content abuse.</p>
  </div>
  <div id="clu-out"></div>
</div>
<!-- 5 -->
<div data-panel="memoria" hidden>
  <div class="panel">
    <h2>Lo que el sistema recuerda</h2>
    <p class="note">Las otras cuatro pestanas miden y se olvidan. Esta acumula:
    el corpus con el que se detecta que una pagina nueva es una reescritura de
    otra, las observaciones que van apagando los priores, y los rechazos del
    revisor que vuelven convertidos en instrucciones del brief. Es lo que hace
    que el sistema mejore con el uso en vez de repetir el mismo trabajo cada
    mes.</p>
    <div class="row">
      <div class="grow">
        <label for="mem-cliente">Cliente</label>
        <input type="text" id="mem-cliente" value="demo" autocomplete="off"
               spellcheck="false" placeholder="minusculas, numeros, guion">
      </div>
      <div><button class="go" id="mem-go" type="button">Ver memoria</button></div>
    </div>
    <p class="note" style="margin-top:10px">El almacen guarda firmas, no texto:
    una pagina de 1.500 palabras ocupa ~5 KB en vez de ~85 KB, y el fichero no
    contiene ninguna frase del contenido. Se puede abrir y leer.</p>
  </div>
  <div id="mem-out"></div>

  <div class="panel">
    <h3>Comprobar un borrador antes de publicarlo</h3>
    <p class="note">Contra lo ya publicado de este sitio y contra el resto de la
    cartera. Comprobar despues de publicar encuentra el problema cuando ya esta
    indexado.</p>
    <label for="mem-text">Borrador en markdown</label>
    <textarea id="mem-text" spellcheck="false"></textarea>
    <div class="row">
      <div><button class="go" id="mem-check" type="button">Comprobar</button></div>
      <div><label for="mem-slug">Slug</label>
        <input type="text" id="mem-slug" placeholder="coste-instalacion"
               autocomplete="off" spellcheck="false"></div>
      <div><label for="mem-role">Rol</label>
        <input type="text" id="mem-role" placeholder="pilar" autocomplete="off"></div>
      <div class="grow"><label for="mem-url">URL publicada</label>
        <input type="text" id="mem-url" placeholder="/coste-instalacion"
               autocomplete="off" spellcheck="false"></div>
      <div><button class="ghost" id="mem-save" type="button">Guardar como publicada</button></div>
    </div>
  </div>
  <div id="mem-check-out"></div>

  <div class="panel">
    <h3>Anotar una observacion</h3>
    <p class="note">Una observacion medida diluye el prior correspondiente. Una
    declarada se guarda igual pero <b>no</b> alimenta nada: si una estimacion
    pudiera apagar una suposicion, el informe dejaria de distinguir lo que sabe
    de lo que supone, que es lo unico que se vende aqui.</p>
    <div class="row">
      <div class="grow"><label for="mem-metrica">Metrica</label>
        <input type="text" id="mem-metrica" value="ctr_posicion_1"
               autocomplete="off" spellcheck="false"></div>
      <div><label for="mem-valor">Valor</label>
        <input type="number" id="mem-valor" step="any" value="0.21"></div>
      <div><label for="mem-fuente">Fuente</label>
        <select id="mem-fuente">
          <option value="medido">medido</option>
          <option value="declarado">declarado</option>
        </select></div>
      <div class="grow"><label for="mem-nota">Nota</label>
        <input type="text" id="mem-nota" placeholder="de donde sale el numero"
               autocomplete="off"></div>
      <div><button class="go" id="mem-obs-go" type="button">Anotar</button></div>
    </div>
    <p class="note" style="margin-top:10px">El historico es de solo anadir. Una
    medicion equivocada se corrige anadiendo la correccion, no borrando el
    error: borrar el pasado deja un sistema que no puede explicar como llego a
    sus numeros.</p>
  </div>
  <div id="mem-obs-out"></div>
</div>
<!-- 6 -->
<div data-panel="negocio" hidden>
  <div class="panel">
    <h2>Que cuesta esto y donde esta el margen</h2>
    <p class="note">Un precio que no sale de un coste medido es una cifra de
    folleto: dura hasta el primer cliente que pide veinte paginas al mes y
    descubre que el margen se lo come la revision. Esto calcula el coste por
    sus partes y, lo que importa mas, dice cual de ellas manda y que pasa al
    moverla.</p>
    <div class="scroll"><table id="tar-planes"><thead><tr>
      <th>Plan</th><th>Precio/mes</th><th>Paginas</th><th>Min. revision</th>
    </tr></thead><tbody>
      <tr data-plan><td><input type="text" value="Inicio"></td>
        <td><input type="number" value="490" min="0" step="10"></td>
        <td><input type="number" value="8" min="1" step="1"></td>
        <td><input type="number" value="14" min="0" step="1"></td></tr>
      <tr data-plan><td><input type="text" value="Crecimiento"></td>
        <td><input type="number" value="1290" min="0" step="10"></td>
        <td><input type="number" value="24" min="1" step="1"></td>
        <td><input type="number" value="12" min="0" step="1"></td></tr>
      <tr data-plan><td><input type="text" value="Cartera"></td>
        <td><input type="number" value="2900" min="0" step="10"></td>
        <td><input type="number" value="60" min="1" step="1"></td>
        <td><input type="number" value="9" min="0" step="1"></td></tr>
    </tbody></table></div>
    <div class="row">
      <div><label for="tar-hora">Coste/hora revision</label>
        <input type="number" id="tar-hora" value="45" min="0" step="1"></div>
      <div><label for="tar-herr">Herramientas/mes</label>
        <input type="number" id="tar-herr" value="120" min="0" step="10"></div>
      <div><label for="tar-rep">Reparaciones/pagina</label>
        <input type="number" id="tar-rep" value="0.6" min="0" step="0.1"></div>
      <div><label for="tar-fijos">Estructura/mes</label>
        <input type="number" id="tar-fijos" value="4000" min="0" step="100"></div>
      <div><button class="go" id="tar-go" type="button">Calcular</button></div>
    </div>
    <p class="note" style="margin-top:10px">
      <label class="check"><input type="checkbox" id="tar-lotes" checked> API de lotes
      (50% de descuento; generar contenido no es sensible a latencia)</label><br>
      <label class="check"><input type="checkbox" id="tar-cron"> Los minutos de revision
      estan cronometrados, no estimados</label>
    </p>
  </div>
  <div id="tar-out"></div>

  <div class="panel">
    <h3>Informe mensual del cliente</h3>
    <p class="note">Se ensambla desde el almacen de la pestana 5. Ninguna cifra
    se teclea: si no esta medida, no aparece o aparece marcada. Lleva una
    seccion de lo que no sabemos, generada, que no se puede quitar sin quitar
    los datos que la producen.</p>
    <div class="row">
      <div class="grow"><label for="inf-cliente">Cliente</label>
        <input type="text" id="inf-cliente" value="demo" autocomplete="off"
               spellcheck="false"></div>
      <div><label for="inf-periodo">Periodo</label>
        <input type="text" id="inf-periodo" value="2026-10" autocomplete="off"></div>
      <div class="grow"><label for="inf-site">Dominio</label>
        <input type="text" id="inf-site" placeholder="cliente.com"
               autocomplete="off" spellcheck="false"></div>
      <div><button class="go" id="inf-go" type="button">Generar</button></div>
    </div>
    <div class="row">
      <div><label for="inf-bloq">Bloqueadas</label>
        <input type="number" id="inf-bloq" value="0" min="0"></div>
      <div><label for="inf-pub">Publicables tal cual</label>
        <input type="number" id="inf-pub" value="0" min="0"></div>
      <div><label for="inf-tope">Tope mensual</label>
        <input type="number" id="inf-tope" value="24" min="1"></div>
      <div class="grow"><label for="inf-idiomas">Idiomas publicados</label>
        <input type="text" id="inf-idiomas" value="es" autocomplete="off"></div>
      <div class="grow"><label for="inf-revisados">Con revision nativa</label>
        <input type="text" id="inf-revisados" value="es" autocomplete="off"></div>
    </div>
  </div>
  <div id="inf-out"></div>
</div>

<!-- 7 -->
<div data-panel="estudio" hidden>
  <div class="panel">
    <h2>El estudio del canal: once agentes y una compuerta cada uno</h2>
    <p class="note">Mismo motor que el resto del banco, aplicado a video: el
    plan no es un calendario, son turnos con minutos; la estrategia no es una
    opinion, es una rubrica con pesos y un veto; y la publicacion diaria no se
    sostiene con disciplina, se sostiene con una semana de reserva por delante.
    Las cifras de esta pestana salen del paquete <span class="m">estudio/</span>
    y estan probadas aparte: ninguna se teclea aqui.</p>
    <div class="row">
      <div><label for="est-vistas">Hipotesis: vistas por documental</label>
        <input type="number" id="est-vistas" value="1500" min="0" step="100"></div>
      <div><label for="est-presupuesto">Presupuesto de herramientas (€/mes)</label>
        <input type="number" id="est-presupuesto" value="25" min="0" step="5"></div>
      <div><button class="go" id="est-go" type="button">Recalcular</button></div>
    </div>
    <p class="note" style="margin-top:8px">La hipotesis de vistas es lo unico de
    esta pantalla que no sale de ningun dato: la pone quien la asume, y el
    veredicto de la carrera dice con esas palabras que no es una prevision.</p>
  </div>

  <div class="panel">
    <h3>La sala, en vivo</h3>
    <p class="note">Cada munequito es un oficio con una entrada, una salida y
    —nueve de los once— una compuerta que puede parar el dia. Azul es
    trabajando, verde entregado, rojo parado por una compuerta, y en gris los
    que hoy no les toca. El reloj no es la hora: es el minuto de la jornada, y
    el estado es deterministico — el mismo minuto da siempre lo mismo.</p>
    <div class="mandos">
      <span id="sal-dias">
        <button type="button" data-dia="1" aria-pressed="true">L</button>
        <button type="button" data-dia="2" aria-pressed="false">M</button>
        <button type="button" data-dia="3" aria-pressed="false">X</button>
        <button type="button" data-dia="4" aria-pressed="false">J</button>
        <button type="button" data-dia="5" aria-pressed="false">V</button>
        <button type="button" data-dia="6" aria-pressed="false">S</button>
        <button type="button" data-dia="7" aria-pressed="false">D</button>
      </span>
      <button type="button" id="sal-play" aria-pressed="true">Pausa</button>
      <label class="check" for="sal-paso">velocidad
        <select id="sal-paso">
          <option value="620">lenta</option>
          <option value="240" selected>normal</option>
          <option value="90">rapida</option>
        </select></label>
      <span class="hora" id="sal-hora">cargando...</span>
    </div>
    <div class="sala" id="sal-grid"></div>
    <div class="relevo vacio" id="sal-relevo">—</div>
  </div>

  <div class="panel">
    <h3>El tribunal: tres rubricas, un veto y un fallo aritmetico</h3>
    <p class="note">Tres jueces puntuan de 0 a 5 los criterios de su oficio con
    pesos declarados. El de riesgo tiene veto: por debajo de 2,5 una estrategia
    queda fuera aunque gane las otras dos rubricas. Y las enmiendas no las
    escribe nadie — se activan solas cuando la ganadora saca menos de 3 en un
    criterio, con el nombre del juez que la impone.</p>
  </div>
  <div id="est-tribunal"></div>

  <div class="panel">
    <h3>La semana canonica</h3>
    <p class="note">Una investigacion, siete publicaciones: el documental del
    viernes y el expediente del martes, que es donde viven los minutos vistos, y
    cinco Shorts de cinco angulos distintos, que es lo que comprueba la
    compuerta de variacion. Lo que se publica esta semana se produjo la
    anterior.</p>
  </div>
  <div id="est-semana"></div>

  <div class="panel">
    <h3>La carrera contra la puerta</h3>
    <p class="note">El 01-02-2027 el liston de entrada al Programa de Socios
    pasa de 4.000 a 8.000 horas de visualizacion en 365 dias, y de 10 a 20
    millones de vistas de Shorts en 90 dias. Quien ya esta dentro no se ve
    afectado, asi que la fecha no es un detalle: es el plazo.</p>
  </div>
  <div id="est-carrera"></div>

  <div class="panel">
    <h3>Herramientas: se paga lo que quita minutos de un turno</h3>
    <p class="note">La pregunta «cual es la mejor herramienta de edicion» no
    tiene respuesta sin saber cual es el cuello de botella. Aqui el cuello esta
    calculado turno a turno, y la pila se ordena por minutos ahorrados entre
    euro al mes. Los minutos que dice que quita cada una son hipotesis
    declaradas, no mediciones: la primera vez que se cronometra un montaje, se
    corrigen.</p>
  </div>
  <div id="est-pila"></div>

  <div class="panel">
    <h3>Calendario: la semana 0 produce y no publica</h3>
    <p class="note">La enmienda del tercer juez, puesta en fechas. Sin el
    colchon, un dia malo es un dia sin publicar y la cadencia depende de que a
    una persona no le pase nada siete dias seguidos.</p>
  </div>
  <div id="est-calendario"></div>
</div>
</div>
"""


# SVG de 16 bytes utiles: un cuadrado con el acento de la interfaz. En linea en
# la propia pagina, asi que no hay peticion extra ni 404 en la consola.
FAVICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
    '<rect width="16" height="16" rx="3" fill="#111"/>'
    '<rect x="3" y="7" width="3" height="6" fill="#4f8cc9"/>'
    '<rect x="7" y="4" width="3" height="9" fill="#4f8cc9"/>'
    '<rect x="11" y="9" width="2" height="4" fill="#5c6670"/>'
    "</svg>"
)


def page() -> str:
    return (
        "<!doctype html>\n<html lang=\"es\">\n<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="robots" content="noindex, nofollow">\n'
        '<link rel="icon" href="data:image/svg+xml,'
        + quote(FAVICON) + '">\n'
        "<title>Banco de pruebas SEO-GEO</title>\n"
        f"<style>{STYLE}</style>\n</head>\n<body>\n{BODY}\n"
        f"<script>{SCRIPT}</script>\n</body>\n</html>\n"
    )
