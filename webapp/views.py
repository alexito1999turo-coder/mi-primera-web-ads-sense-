"""La interfaz. Un solo documento, sin red externa.

Sin fuentes de Google ni CDN: es una herramienta que se levanta en local y
tiene que funcionar sin internet. Pila de fuentes del sistema y todo el CSS y
el JS en el propio documento.
"""

from __future__ import annotations

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
a{color:var(--signal)}
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

/* --- arranque --------------------------------------------------------- */
$$("nav.tabs button").forEach(function(b){
  b.addEventListener("click", function(){ abrir(b.getAttribute("data-tab")); });
});
$("#aud-go").addEventListener("click", auditar);
$("#aud-site").addEventListener("keydown", function(e){ if (e.key === "Enter") auditar(); });
$("#cit-go").addEventListener("click", medirCitabilidad);
$("#opo-go").addEventListener("click", medirOportunidad);
$("#clu-go").addEventListener("click", medirClusters);
conectarFichero("#opo-file", "#opo-csv");
conectarFichero("#clu-file", "#clu-csv");

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
abrir(["auditoria","citabilidad","oportunidad","clusters"].indexOf(inicial) >= 0
      ? inicial : "auditoria");
medirCitabilidad();
"""

BODY = """
<div class="wrap">
<header class="top">
  <h1>Banco de pruebas SEO-GEO
    <small>Auditoria, citabilidad, oportunidad y plan de clusters. Corre en tu
    maquina, sin dependencias y sin enviar nada a ningun sitio.</small></h1>
  <p class="note" style="margin-top:9px"><a href="/oferta">Qué se vende, y
  cuánto cuesta</a> · los tres planes, y lo que está medido y lo que no.</p>
</header>

<nav class="tabs" role="tablist">
  <button data-tab="auditoria" aria-selected="true">1 · Auditoria</button>
  <button data-tab="citabilidad" aria-selected="false">2 · Citabilidad</button>
  <button data-tab="oportunidad" aria-selected="false">3 · Oportunidad</button>
  <button data-tab="clusters" aria-selected="false">4 · Clusters</button>
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
</div>
"""


def page() -> str:
    return (
        "<!doctype html>\n<html lang=\"es\">\n<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="robots" content="noindex, nofollow">\n'
        "<title>Banco de pruebas SEO-GEO</title>\n"
        f"<style>{STYLE}</style>\n</head>\n<body>\n{BODY}\n"
        f"<script>{SCRIPT}</script>\n</body>\n</html>\n"
    )
