/* ---------- 5. economia unitaria ----------
 *
 * Puerto fiel de pricing/unit.py y pricing/plans.py. «Fiel» no es una
 * promesa: hay un comparador que corre los dos sobre los mismos casos y
 * falla si difieren mas de un centimo. Un puerto que se desvia del motor
 * ensena numeros que el sistema no respalda, que es peor que no tenerlo.
 */
var TARIFAS = {
  "claude-opus-5-5":   {in:15.0, out:75.0, cw:18.75, cr:1.50},
  "claude-sonnet-5-5": {in:3.0,  out:15.0, cw:3.75,  cr:0.30},
  "claude-haiku-4-5":  {in:1.0,  out:5.0,  cw:1.25,  cr:0.10}
};
var TARIFAS_REVISADAS = "2026-10-04";
var DESCUENTO_LOTES = 0.50;
var MARGEN_MINIMO = 0.35;

function r4(x){ return Math.round(x * 1e4) / 1e4; }
function r2(x){ return Math.round(x * 1e2) / 1e2; }
function r6(x){ return Math.round(x * 1e6) / 1e6; }

function costeModelo(u, modelo, lotes){
  var t = TARIFAS[modelo || "claude-opus-5-5"];
  if (!t) throw new Error("No hay tarifa declarada para «" + modelo + "».");
  var bruto = ((u.input||0) * t.in + (u.output||0) * t.out +
               (u.cacheWrite||0) * t.cw + (u.cacheRead||0) * t.cr) / 1e6;
  if (lotes) bruto *= DESCUENTO_LOTES;
  return r6(bruto);
}

function porPagina(o){
  var coste = {modelo:0, revision:0, herramientas:0, entradas:[]};
  var u = o.usage;
  if (u && (u.calls || 0) > 0){
    var bruto = costeModelo(u, o.modelo, o.lotes);
    var llamadas = Math.max(u.calls || 1, 1);
    coste.modelo = r4(bruto / llamadas * (1 + (o.reparaciones || 0)));
    coste.entradas.push({medida:true});
  } else {
    coste.entradas.push({medida:false});
  }
  coste.revision = r4((o.minutosRevision || 0) / 60 * (o.costeHora || 0));
  coste.entradas.push({medida: !!o.minutosMedidos});
  coste.entradas.push({medida:false});          // coste por hora

  // El reparto de herramientas es sobre la cartera entera cuando se declara:
  // es coste fijo del negocio, no del cliente.
  var den = (o.paginasCartera > 0) ? o.paginasCartera : (o.paginasMes || 0);
  if (den > 0 && o.herramientasMes){
    coste.herramientas = r4(o.herramientasMes / den);
    coste.entradas.push({medida:false});
  }
  coste.total = r4(coste.modelo + coste.revision + coste.herramientas);
  var tot = coste.total;
  coste.reparto = tot <= 0 ? {modelo:0, revision:0, herramientas:0} : {
    modelo: Math.round(100 * coste.modelo / tot),
    revision: Math.round(100 * coste.revision / tot),
    herramientas: Math.round(100 * coste.herramientas / tot)
  };
  coste.medido = coste.entradas.length
    ? Math.round(100 * coste.entradas.filter(function(e){ return e.medida; }).length
                 / coste.entradas.length) : 0;
  return coste;
}

function opciones(plan, kw){
  var o = {};
  Object.keys(kw || {}).forEach(function(k){ o[k] = kw[k]; });
  if (o.minutosRevision === undefined) o.minutosRevision = plan.minutosRevision;
  o.paginasMes = plan.paginas;
  return o;
}

function evaluar(plan, kw){
  var coste = porPagina(opciones(plan, kw));
  var costeMes = r2(coste.total * plan.paginas);
  var margen = r2(plan.precioMes - costeMes);
  var pct = plan.precioMes ? Math.round(1000 * margen / plan.precioMes) / 10 : 0;
  return {plan:plan, costePagina:coste.total, costeMes:costeMes,
          margenMes:margen, margenPct:pct, reparto:coste.reparto,
          medido:coste.medido, sano: pct >= MARGEN_MINIMO * 100,
          precioPagina: plan.paginas ? r2(plan.precioMes / plan.paginas) : 0};
}

function sensibilidad(plan, kw){
  var partida = evaluar(plan, kw).margenPct;
  var out = [];
  var mins = (kw && kw.minutosRevision !== undefined)
    ? kw.minutosRevision : plan.minutosRevision;

  var peor = opciones(plan, kw); peor.minutosRevision = mins * 1.5;
  out.push(caso("Minutos de revision por pagina", mins.toFixed(0),
    (mins * 1.5).toFixed(0), partida,
    evaluar(plan, Object.assign({}, kw, {minutosRevision: mins * 1.5})).margenPct));

  var rep = (kw && kw.reparaciones) || 0;
  out.push(caso("Reparaciones por pagina", rep.toFixed(1), (rep + 1).toFixed(1),
    partida, evaluar(plan, Object.assign({}, kw, {reparaciones: rep + 1})).margenPct));

  var rebajado = {nombre:plan.nombre, precioMes: plan.precioMes * 0.85,
                  paginas: plan.paginas, minutosRevision: plan.minutosRevision};
  out.push(caso("Precio negociado", plan.precioMes.toFixed(0) + " $",
    (plan.precioMes * 0.85).toFixed(0) + " $", partida,
    evaluar(rebajado, kw).margenPct));
  return out;
}
function caso(palanca, desde, hasta, antes, despues){
  return {palanca:palanca, desde:desde, hasta:hasta, antes:antes,
          despues:despues, caida: Math.round((antes - despues) * 10) / 10,
          rompe: despues < MARGEN_MINIMO * 100};
}

function puntoMuerto(plan, fijosMes, kw){
  var r = evaluar(plan, kw);
  if (r.margenMes <= 0) return {clientes:null, margenCliente:r.margenMes};
  var clientes = Math.ceil(fijosMes / r.margenMes);
  var paginas = clientes * plan.paginas;
  var mins = (kw && kw.minutosRevision !== undefined)
    ? kw.minutosRevision : plan.minutosRevision;
  return {clientes:clientes, margenCliente:r.margenMes, paginasMes:paginas,
          horasRevisionMes: Math.round(paginas * mins / 60 * 10) / 10};
}

function curvaDeCartera(plan, kw, volumenes){
  volumenes = volumenes || [1, 2, 3, 5, 8, 12, 20, 40];
  var puntos = [], umbral = null;
  volumenes.forEach(function(c){
    var cartera = c * plan.paginas;
    var r = evaluar(plan, Object.assign({}, kw, {paginasCartera: cartera}));
    var sano = r.margenPct >= MARGEN_MINIMO * 100;
    puntos.push({clientes:c, paginasCartera:cartera, costePagina:r.costePagina,
                 margenPct:r.margenPct, sano:sano});
    if (umbral === null && sano) umbral = c;
  });
  return {puntos:puntos, umbralClientes:umbral};
}

function paginasMaximas(plan, kw, objetivo){
  objetivo = objetivo === undefined ? MARGEN_MINIMO : objetivo;
  // Punto fijo, no division: el coste por pagina depende de cuantas paginas
  // tiene el plan, porque el coste fijo se reparte entre ellas.
  for (var n = plan.paginas; n >= 1; n--){
    var t = {nombre:plan.nombre, precioMes:plan.precioMes, paginas:n,
             minutosRevision:plan.minutosRevision};
    if (evaluar(t, kw).margenPct >= objetivo * 100) return {paginas:n, sobran: plan.paginas - n};
  }
  return {paginas:0, sobran: plan.paginas};
}

function precioMinimo(plan, kw, objetivo, robusto){
  objetivo = objetivo === undefined ? MARGEN_MINIMO : objetivo;
  robusto = robusto !== false;
  var coste = porPagina(opciones(plan, kw)).total * plan.paginas;
  var base = coste / (1 - objetivo);
  var precio = base;
  if (robusto){
    var mins = (kw && kw.minutosRevision !== undefined)
      ? kw.minutosRevision : plan.minutosRevision;
    var o = opciones(plan, kw); o.minutosRevision = mins * 1.5;
    precio = Math.max(base, porPagina(o).total * plan.paginas / (1 - objetivo));
  }
  precio = Math.round(precio / 10) * 10 || 10;
  return {precio:precio, actual:plan.precioMes, subida: r2(precio - plan.precioMes)};
}

if (typeof module !== "undefined") module.exports = {
  costeModelo, porPagina, evaluar, sensibilidad, puntoMuerto,
  curvaDeCartera, paginasMaximas, precioMinimo, TARIFAS, MARGEN_MINIMO};
