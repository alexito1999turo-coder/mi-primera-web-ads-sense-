"""Incrusta el motor JS de economia en el banco de pruebas.

El artefacto lleva una copia del motor para funcionar en el navegador
sin instalar nada. La copia se genera desde `economia.js`, que es el
unico sitio donde se toca: `tests/test_puerto_js.py` falla si las dos
copias se desvian, y tambien si el motor JS se desvia del Python.

Es idempotente solo sobre un banco sin la pestana: para regenerar,
parte del HTML anterior a este parche.
"""

from pathlib import Path
p = Path(__file__).resolve().parent / "banco.html"
t = p.read_text(encoding="utf-8")
motor = (Path(__file__).resolve().parent / "economia.js").read_text(encoding="utf-8")
motor = motor.split("if (typeof module")[0].rstrip()

# 1. pestana
viejo = '  <button data-tab="datos" aria-selected="false">Datos propios</button>'
assert viejo in t
t = t.replace(viejo, viejo + '\n  <button data-tab="economia" aria-selected="false">Economía</button>', 1)

# 2. panel
panel = '''
<div data-panel="economia" hidden>
  <div class="panel">
    <h3>Qué cuesta cada página y dónde está el margen de verdad</h3>
    <p class="note">Un precio que no sale de un coste medido es una cifra de
    folleto: dura hasta el primer cliente que pide veinte páginas al mes. Esto
    calcula el coste por sus partes con el consumo real de tokens, y dice
    <strong>cuál de ellas manda</strong> y qué pasa al moverla. Es el mismo
    motor que corre en el sistema, comprobado contra él caso por caso.</p>

    <div class="scroll"><table id="eco-planes" class="eco">
      <thead><tr><th>Plan</th><th>Precio/mes</th><th>Páginas</th><th>Min. revisión</th></tr></thead>
      <tbody>
        <tr data-plan><td><input type="text" value="Core"></td>
          <td><input type="number" value="299" min="0" step="10"></td>
          <td><input type="number" value="12" min="1" step="1"></td>
          <td><input type="number" value="12" min="0" step="1"></td></tr>
        <tr data-plan><td><input type="text" value="Scale"></td>
          <td><input type="number" value="699" min="0" step="10"></td>
          <td><input type="number" value="24" min="1" step="1"></td>
          <td><input type="number" value="12" min="0" step="1"></td></tr>
      </tbody>
    </table></div>

    <div class="row" style="margin-top:12px">
      <div><label for="eco-hora">Coste/hora de revisión</label>
        <input type="number" id="eco-hora" value="45" min="0" step="1"></div>
      <div><label for="eco-herr">Herramientas/mes</label>
        <input type="number" id="eco-herr" value="120" min="0" step="10"></div>
      <div><label for="eco-rep">Reparaciones/página</label>
        <input type="number" id="eco-rep" value="0.6" min="0" step="0.1"></div>
      <div><label for="eco-cartera">Páginas/mes en toda la cartera</label>
        <input type="number" id="eco-cartera" value="300" min="0" step="10"></div>
      <div><label for="eco-fijos">Estructura/mes</label>
        <input type="number" id="eco-fijos" value="4000" min="0" step="100"></div>
    </div>
    <p class="note" style="margin-top:10px">Las <strong>páginas de cartera</strong>
    son el detalle que más cambia el resultado, y el que yo mismo tenía mal: las
    herramientas son coste fijo del <em>negocio</em>, no del cliente. Ponlo a 0
    para ver qué pasa cuando solo tienes un cliente.</p>
  </div>
  <div id="eco-out"></div>
</div>
'''
ancla = '\n<div data-panel="datos" hidden>'
assert ancla in t
# insertar despues del panel de datos: buscar su cierre antes de </div> del wrap
cierre = '  <div id="dat-out"></div>\n</div>'
assert cierre in t
t = t.replace(cierre, cierre + "\n" + panel.lstrip("\n"), 1)

# 3. CSS
css_ancla = "@media (prefers-reduced-motion:reduce){*{transition:none!important}}"
extra = '''table.eco{width:100%;border-collapse:collapse;font-size:13px;min-width:460px}
table.eco th{text-align:left;font-size:10px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--faint);font-weight:600;padding:0 6px 4px}
table.eco td{padding:3px 6px}
table.eco input{width:100%;font:inherit;font-size:13px;padding:7px 9px;
  border:1px solid var(--edge);border-radius:5px;background:var(--ground);
  color:var(--ink)}
table.eco td{border-bottom:none}
.rep{display:inline-flex;width:86px;height:9px;border-radius:5px;
  overflow:hidden;vertical-align:middle;margin-right:7px;
  border:1px solid var(--edge)}
.rep i{display:block;height:100%}
.rep i:nth-child(1){background:var(--signal)}
.rep i:nth-child(2){background:var(--measured)}
.rep i:nth-child(3){background:var(--ink-faint)}
ul.lista{margin:10px 0 0;padding-left:20px;font-size:14px;
  color:var(--ink-soft);line-height:1.55}
ul.lista li{margin-bottom:6px}
ul.lista b{color:var(--ink);font-weight:600}
.rompe{color:var(--bad);font-weight:600}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}'''
if css_ancla in t:
    t = t.replace(css_ancla, extra, 1)
else:
    raise SystemExit("no encuentro el ancla de CSS")

# 4. JS: motor + pintura
pintura = '''

/* ---------- economia: la pintura ---------- */
function planesEco(){
  return $$("#eco-planes tr[data-plan]").map(function(f){
    var c = f.querySelectorAll("input");
    return {nombre: c[0].value || "Plan", precioMes: parseFloat(c[1].value) || 0,
            paginas: Math.max(parseInt(c[2].value, 10) || 1, 1),
            minutosRevision: parseFloat(c[3].value) || 0};
  });
}
function numEco(sel, d){ var v = parseFloat($(sel).value); return isFinite(v) ? v : d; }

function calcularEconomia(){
  var u = {input:4000, output:6000, cacheWrite:3000, cacheRead:24000, calls:1};
  var cartera = numEco("#eco-cartera", 0);
  var kw = {usage:u, costeHora:numEco("#eco-hora",45),
            herramientasMes:numEco("#eco-herr",120),
            reparaciones:numEco("#eco-rep",0.6), lotes:true};
  if (cartera > 0) kw.paginasCartera = cartera;
  var fijos = numEco("#eco-fijos", 4000);
  var planes = planesEco();
  var h = "";

  h += '<div class="panel"><h3>Margen por plan</h3><div class="scroll"><table>' +
    '<thead><tr><th>Plan</th><th class="n">$/mes</th><th class="n">Páginas</th>' +
    '<th class="n">$/página</th><th class="n">Coste/página</th>' +
    '<th class="n">Margen</th><th>Reparto del coste</th></tr></thead><tbody>';
  var resultados = planes.map(function(p){ return evaluar(p, kw); });
  resultados.forEach(function(r){
    h += "<tr><td>" + esc(r.plan.nombre) + '</td><td class="n">' +
      r.plan.precioMes.toFixed(0) + '</td><td class="n">' + r.plan.paginas +
      '</td><td class="n">' + r.precioPagina.toFixed(2) + '</td><td class="n">' +
      r.costePagina.toFixed(2) + '</td><td class="n">' +
      (r.sano ? "" : '<span class="rompe">') + r.margenPct.toFixed(0) + "%" +
      (r.sano ? "" : "</span>") + "</td><td>" + barrasEco(r.reparto) + "</td></tr>";
  });
  h += "</tbody></table></div>";
  var peor = resultados.slice().sort(function(a,b){
    return b.reparto.revision - a.reparto.revision; })[0];
  if (peor) h += '<p class="note">El reparto es la conclusión, no el margen: en «' +
    esc(peor.plan.nombre) + "» el modelo es el " + peor.reparto.modelo +
    "% del coste y la revisión el " + peor.reparto.revision +
    "%. Competir en precio de tokens es optimizar la parte barata, y bajar de " +
    "modelo no ahorra: sube los minutos de revisión, que es lo caro.</p>";
  h += "</div>";

  h += '<div class="panel"><h3>Qué pasa si se mueve una palanca</h3>' +
    '<p class="note">Un plan con buen margen que se rompe al cronometrar la ' +
    "revisión no es un plan con buen margen: es un plan que depende de una " +
    "cifra que nadie ha medido.</p>";
  planes.forEach(function(p){
    h += "<h4 style='margin:14px 0 4px;font-size:14px'>" + esc(p.nombre) + "</h4><ul class='lista'>";
    sensibilidad(p, kw).forEach(function(c){
      var pts = Math.round(Math.abs(c.caida));
      h += "<li>" + esc(c.palanca) + ": de " + esc(c.desde) + " a " + esc(c.hasta) +
        ", el margen " + (c.caida > 0 ? "cae " : "sube ") +
        pts + (pts === 1 ? " punto" : " puntos") + " hasta " + c.despues.toFixed(0) +
        "%" + (c.rompe ? ' <span class="rompe">rompe el plan</span>' : "") + "</li>";
    });
    h += "</ul>";
  });
  h += "</div>";

  h += '<div class="panel"><h3>Viabilidad según el tamaño de la cartera</h3>' +
    '<p class="note">Las herramientas son coste fijo del negocio: el primer ' +
    "cliente las carga enteras. Por eso un plan pequeño puede parecer inviable " +
    "mirándolo aislado, y la decisión correcta no es subir la tarifa por lo que " +
    "se ve en el cliente uno.</p>";
  var kwSin = {}; Object.keys(kw).forEach(function(k){ kwSin[k] = kw[k]; });
  delete kwSin.paginasCartera;
  planes.forEach(function(p){
    var cu = curvaDeCartera(p, kwSin);
    h += "<h4 style='margin:14px 0 6px;font-size:14px'>" + esc(p.nombre) + " — " +
      (cu.umbralClientes === null
        ? "no llega al 35% ni con la cartera más grande probada: el problema no es la escala, es el precio o el alcance"
        : cu.umbralClientes === 1
          ? "rentable desde el primer cliente"
          : "hace falta llegar a " + cu.umbralClientes + " clientes para pasar del 35%") +
      "</h4>";
    h += '<div class="scroll"><table><thead><tr><th class="n">Clientes</th>' +
      '<th class="n">Coste/página</th><th class="n">Margen</th></tr></thead><tbody>';
    cu.puntos.slice(0, 6).forEach(function(pt){
      h += '<tr><td class="n">' + pt.clientes + '</td><td class="n">' +
        pt.costePagina.toFixed(2) + ' $</td><td class="n">' +
        (pt.sano ? "" : '<span class="rompe">') + pt.margenPct.toFixed(0) + "%" +
        (pt.sano ? "" : "</span>") + "</td></tr>";
    });
    h += "</tbody></table></div>";
  });
  h += "</div>";

  h += '<div class="panel"><h3>Punto muerto</h3><p class="note">Es la única ' +
    "cifra que decide si esto es un negocio o un trabajo: si hacen falta más " +
    "clientes de los que una persona puede atender, el plan está mal puesto por " +
    "bonito que sea el margen.</p><ul class='lista'>";
  planes.forEach(function(p){
    var pm = puntoMuerto(p, fijos, kw);
    h += "<li>" + (pm.clientes === null
      ? "<b>" + esc(p.nombre) + "</b> pierde dinero por cliente: no hay punto muerto, hay un agujero que crece con las ventas."
      : "<b>" + esc(pm.clientes) + " cliente(s) de «" + esc(p.nombre) + "»</b> cubren " +
        fijos.toFixed(0) + " $/mes de estructura. Son " + pm.paginasMes +
        " páginas y " + pm.horasRevisionMes + " horas de revisión al mes.") + "</li>";
  });
  h += "</ul></div>";

  h += '<div class="panel"><h3>Lo que este cálculo NO cuenta</h3>' +
    '<p class="note">No caben en un coste por página porque no escalan con las ' +
    "páginas, sino con los clientes. Son justo las partidas que convierten un " +
    "margen de folleto en el margen real.</p><ul class='lista'>" +
    "<li><b>Captación.</b> Reparte sobre la vida del contrato, no sobre el mes.</li>" +
    "<li><b>Alta y auditoría inicial.</b> El primer mes de un cliente no se parece a los siguientes.</li>" +
    "<li><b>Gestión de cuenta.</b> Crece con clientes, no con páginas.</li>" +
    "<li><b>Bajas.</b> Sin tasa de bajas medida, el valor de vida es un deseo.</li>" +
    '</ul><p class="note">Tarifas de modelo revisadas el ' + TARIFAS_REVISADAS +
    ". Si esa fecha tiene más de un trimestre, el cálculo sigue corriendo pero " +
    "los números ya no son los de la factura.</p></div>";

  $("#eco-out").innerHTML = h;
}
function barrasEco(rep){
  var partes = [["modelo", rep.modelo], ["revisión", rep.revision],
                ["herram.", rep.herramientas]];
  return '<span class="rep">' + partes.map(function(x){
    return '<i style="width:' + Math.max(x[1],0) + '%"></i>'; }).join("") +
    "</span> " + partes.filter(function(x){ return x[1] >= 10; })
      .map(function(x){ return x[0] + " " + x[1] + "%"; }).join(" · ");
}
'''

marca = "/* ---------- arranque ---------- */"
assert marca in t
t = t.replace(marca, motor + pintura + "\n" + marca, 1)

# 5. listeners
t = t.replace('''$("#clu-go").addEventListener("click", medirClusters);''',
'''$("#clu-go").addEventListener("click", medirClusters);
$$("#eco-planes input, #eco-hora, #eco-herr, #eco-rep, #eco-cartera, #eco-fijos")
  .forEach(function(i){ i.addEventListener("input", calcularEconomia); });''', 1)

# 6. arranque inicial
if "calcularEconomia();" not in t:
    t = t.replace("medirCitabilidad();\n", "medirCitabilidad();\ncalcularEconomia();\n", 1)

p.write_text(t, encoding="utf-8")
print("banco parcheado:", len(t), "bytes")
for m in ('data-panel="economia"', "calcularEconomia", "curvaDeCartera", "table.eco"):
    print("  ", "OK " if m in t else "FALTA ", m)
