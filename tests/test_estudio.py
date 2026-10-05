"""El estudio: agentes, compuertas, plan, carrera, jueces y sala.

La prueba que importa de verdad es la ultima, `SemanaContraCompuertas`: cruza
el plan con las compuertas y comprueba que la semana canonica pasa su propia
compuerta de variacion sin retocar nada a mano. Es la misma forma de prueba que
la que cruza `dataset` con `citability` en el resto del repositorio — si el
plan que se vende no pasa las compuertas que se venden con el, una de las dos
cosas es un folleto.
"""

import unittest
from datetime import date

from estudio import herramientas as H
from estudio.agentes import PLANTILLA, SALA, agente, compuertas_de_la_sala
from estudio.carrera import (CAMBIO, PUERTA_ACTUAL, PUERTA_NUEVA, Carrera,
                             comparar_rutas, puerta_vigente)
from estudio.compuertas import (MAX_SIMILITUD_ENTRE_PIEZAS, Fuente, Persona,
                                Pieza, Plano, cadencia, dato_propio,
                                declaracion, difamacion, fuentes, gancho,
                                licencias, politica_ia, promesa, revisar,
                                saturacion, variacion)
from estudio.jueces import (CANDIDATAS, JUECES, UMBRAL_ENMIENDA, Estrategia,
                            fallo, puntuar, tabla)
from estudio.plan import (SEMANA, calendario, carga_por_agente,
                          cuello_de_botella, horas_semana, publicaciones,
                          veredicto_cadencia)
from estudio.sala import (BLOQUEADO, ENTREGADO, ESPERANDO, LIBRE, TRABAJANDO,
                          Sala)

HOY = date(2026, 10, 5)


def pieza_buena(**cambios) -> Pieza:
    base = dict(
        clave="d5",
        formato="documental",
        tipo="caso",
        titulo="El fraude bancario que quebro mil cuentas",
        guion=("El fraude bancario dejo 1.240 cuentas vacias. La mediana de "
               "perdida por cuenta fue de 14.237 euros, y quebro el banco en "
               "once meses. Quien firmo la ultima auditoria?"),
        gancho=("Durante diez anios fueron intocables. Los peritos encontraron "
                "14.237 euros de perdida mediana en 1.240 cuentas. Y lo peor no "
                "fue el robo: fue quien firmo. Quien firmo?"),
        duracion_min=22.0,
        fuentes=[
            Fuente("boe.es", "Sentencia 112/2019", primaria=True, consultada="2026-10-01"),
            Fuente("elpais.com", "Cronica del juicio", consultada="2026-10-01"),
            Fuente("cnmv.es", "Expediente sancionador", primaria=True, consultada="2026-10-02"),
        ],
        personas=[Persona("Juan Perez", viva=True, registro="Sentencia 112/2019 AP Madrid")],
        planos=[Plano("archivo del juicio", licencia="Archivo RTVE, uso citado")],
        dato_propio="14.237 euros de perdida mediana por cuenta",
        metodo="mediana de las 42 declaraciones del expediente",
        n_muestra=42,
        temas=("finanzas",),
        voz_sintetica=False,
        canales_que_lo_cuentan=12,
        angulo_propio="la mediana por cuenta, que nadie habia agregado",
    )
    base.update(cambios)
    return Pieza(**base)


class Agentes(unittest.TestCase):
    def test_cada_compuerta_tiene_un_solo_dueno(self):
        duenos = compuertas_de_la_sala()
        self.assertEqual(len(duenos), len(set(duenos)))
        self.assertEqual(duenos["variacion"], "troceador")
        self.assertEqual(duenos["politica_ia"], "abogado")

    def test_el_medidor_no_bloquea(self):
        """Mide y recomienda. Si bloqueara, decidiria el contenido."""
        self.assertFalse(agente("medidor").puede_bloquear)
        self.assertTrue(agente("abogado").puede_bloquear)

    def test_la_sala_es_el_indice_de_la_plantilla(self):
        self.assertEqual(len(SALA), len(PLANTILLA))
        self.assertEqual(set(SALA), {a.clave for a in PLANTILLA})

    def test_agente_desconocido_falla_con_la_clave_escrita(self):
        with self.assertRaises(KeyError) as ctx:
            agente("guionsta")
        self.assertIn("guionsta", str(ctx.exception))


class Compuertas(unittest.TestCase):
    def test_la_pieza_completa_pasa_entera(self):
        parte = revisar(pieza_buena())
        self.assertTrue(parte.pasa, parte.describe())

    def test_dos_periodicos_no_son_tres_fuentes(self):
        pocas = pieza_buena(fuentes=[
            Fuente("elpais.com", "Cronica", consultada="2026-10-01"),
            Fuente("elmundo.es", "Cronica", consultada="2026-10-01"),
        ])
        v = fuentes(pocas)
        self.assertFalse(v.pasa)
        self.assertIn("2 dominios independientes", v.motivo)

    def test_sin_documento_primario_no_pasa(self):
        v = fuentes(pieza_buena(fuentes=[
            Fuente("elpais.com", "A", consultada="2026-10-01"),
            Fuente("elmundo.es", "B", consultada="2026-10-01"),
            Fuente("abc.es", "C", consultada="2026-10-01"),
        ]))
        self.assertFalse(v.pasa)
        self.assertIn("primario", v.motivo)

    def test_fuente_sin_fecha_de_consulta_no_pasa(self):
        mala = pieza_buena()
        mala.fuentes[1].consultada = ""
        self.assertFalse(fuentes(mala).pasa)

    def test_una_cifra_redonda_no_es_un_dato_propio(self):
        """«Unos 14.000 euros» lo sabe cualquiera; «14.237» lo contaste tu."""
        v = dato_propio(pieza_buena(dato_propio="unos 14.000 euros de perdida"))
        self.assertFalse(v.pasa)
        self.assertIn("redonda", v.motivo)

    def test_dato_propio_sin_metodo_no_pasa(self):
        self.assertFalse(dato_propio(pieza_buena(metodo="")).pasa)

    def test_muestra_de_tres_no_agrega_nada(self):
        self.assertFalse(dato_propio(pieza_buena(n_muestra=3)).pasa)

    def test_el_gancho_no_se_gasta_en_presentarse(self):
        v = gancho(pieza_buena(gancho="Bienvenidos al canal. Hoy, 14.237 euros. Quien?"))
        self.assertFalse(v.pasa)
        self.assertIn("presentacion", v.motivo)

    def test_un_gancho_de_ciento_cuarenta_palabras_no_es_un_gancho(self):
        largo = " ".join(["palabra"] * 140) + " 14.237 euros. Quien firmo?"
        v = gancho(pieza_buena(gancho=largo))
        self.assertFalse(v.pasa)
        self.assertIn("treinta segundos", v.motivo)

    def test_al_gancho_sin_cifra_le_falta_la_cifra(self):
        v = gancho(pieza_buena(gancho="Fueron intocables durante anios. Quien firmo?"))
        self.assertFalse(v.pasa)
        self.assertIn("cifra medida", v.motivo)

    def test_voz_sintetica_sin_declarar_bloquea(self):
        v = declaracion(pieza_buena(voz_sintetica=True, voz_declarada=False))
        self.assertFalse(v.pasa)

    def test_persona_sintetica_hablando_de_finanzas_sin_autor_humano(self):
        """La combinacion que la plataforma limita, y este nicho la roza siempre."""
        v = politica_ia(pieza_buena(voz_sintetica=True, voz_declarada=True,
                                    autor_humano_visible=False))
        self.assertFalse(v.pasa)
        self.assertIn("finanzas", v.motivo)

    def test_con_autor_humano_y_dato_propio_si_pasa(self):
        v = politica_ia(pieza_buena(voz_sintetica=True, voz_declarada=True,
                                    autor_humano_visible=True))
        self.assertTrue(v.pasa)

    def test_voz_propia_no_activa_la_politica_de_ia(self):
        self.assertTrue(politica_ia(pieza_buena(voz_sintetica=False)).pasa)

    def test_la_miniatura_no_puede_prometer_lo_que_no_esta(self):
        v = promesa(pieza_buena(titulo="El asesinato del notario portugues"))
        self.assertFalse(v.pasa)
        self.assertIn("cebo", v.motivo)

    def test_nombre_sin_registro_publico_bloquea(self):
        v = difamacion(pieza_buena(personas=[Persona("Juan Perez", viva=True)]))
        self.assertFalse(v.pasa)
        self.assertIn("Juan Perez", v.motivo)

    def test_persona_muerta_no_pide_registro(self):
        v = difamacion(pieza_buena(personas=[Persona("Charles Ponzi", viva=False)]))
        self.assertTrue(v.pasa)

    def test_plano_sin_licencia_bloquea(self):
        v = licencias(pieza_buena(planos=[Plano("archivo suelto")]))
        self.assertFalse(v.pasa)

    def test_caso_contado_por_cincuenta_canales_sin_dato_propio(self):
        v = saturacion(pieza_buena(canales_que_lo_cuentan=60, dato_propio=""))
        self.assertFalse(v.pasa)
        self.assertIn("cincuenta y uno", v.motivo)

    def test_el_parte_dice_quien_bloquea(self):
        parte = revisar(pieza_buena(metodo="", planos=[Plano("suelto")]))
        self.assertFalse(parte.pasa)
        culpables = {v.dueno for v in parte.bloqueantes}
        self.assertEqual(culpables, {"contable", "montador"})
        self.assertIn("contable", parte.describe())

    def test_el_parte_cuenta_aparte_las_automaticas(self):
        """Nueve compuertas, seis automaticas. Contarlas todas seria el folleto."""
        parte = revisar(pieza_buena())
        self.assertEqual(len(parte.veredictos), 9)
        self.assertEqual(parte.automaticas, 6)


class Variacion(unittest.TestCase):
    def test_dos_angulos_iguales_seguidos_bloquean(self):
        a = pieza_buena(clave="s1", formato="short", tipo="cifra", guion="Uno uno uno.")
        b = pieza_buena(clave="s2", formato="short", tipo="cifra", guion="Dos dos dos.")
        v = variacion([a, b])
        self.assertFalse(v.pasa)
        self.assertIn("mismo tipo", v.motivo)

    def test_el_mismo_guion_con_otro_tipo_tambien_bloquea(self):
        texto = ("La mediana de perdida por cuenta fue de 14.237 euros en 1.240 "
                 "cuentas, y el banco quebro en once meses despues de la auditoria.")
        a = pieza_buena(clave="s1", formato="short", tipo="cifra", guion=texto)
        b = pieza_buena(clave="s2", formato="short", tipo="documento", guion=texto)
        v = variacion([a, b])
        self.assertFalse(v.pasa)
        self.assertIn("comparten", v.motivo)

    def test_una_pieza_sola_no_tiene_con_que_compararse(self):
        self.assertTrue(variacion([pieza_buena()]).pasa)

    def test_el_umbral_es_mas_flojo_que_el_de_cartera(self):
        """Cinco Shorts del mismo caso comparten nombres y cifras por necesidad."""
        self.assertGreater(MAX_SIMILITUD_ENTRE_PIEZAS, 0.08)


class Cadencia(unittest.TestCase):
    def test_un_dia_sin_publicar_bloquea(self):
        v = cadencia({"lunes": 1, "martes": 0}, [840, 840])
        self.assertFalse(v.pasa)
        self.assertIn("martes", v.motivo)

    def test_una_rafaga_bloquea(self):
        v = cadencia({"lunes": 5}, [840])
        self.assertFalse(v.pasa)
        self.assertIn("rafaga", v.motivo)

    def test_la_hora_que_baila_avisa_pero_no_bloquea(self):
        v = cadencia({"lunes": 1, "martes": 1}, [600, 1140])
        self.assertFalse(v.pasa)
        self.assertFalse(v.bloqueante)


class CarreraPuerta(unittest.TestCase):
    def test_la_puerta_cambia_el_uno_de_febrero(self):
        self.assertEqual(puerta_vigente(date(2027, 1, 31)), PUERTA_ACTUAL)
        self.assertEqual(puerta_vigente(CAMBIO), PUERTA_NUEVA)
        self.assertEqual(PUERTA_NUEVA.horas, 2 * PUERTA_ACTUAL.horas)

    def test_los_minutos_por_vista_son_duracion_por_retencion(self):
        c = Carrera(hoy=HOY, duracion_min=22.0, retencion=0.45)
        self.assertEqual(c.minutos_por_vista, 9.9)
        self.assertEqual(c.minutos_objetivo, 240_000)
        self.assertEqual(c.vistas_necesarias, 24_243)

    def test_doblar_la_duracion_parte_en_dos_las_vistas_necesarias(self):
        """La decision que ordena el canal: los minutos son lineales, las vistas no."""
        corto = Carrera(hoy=HOY, duracion_min=11.0)
        largo = Carrera(hoy=HOY, duracion_min=22.0)
        self.assertAlmostEqual(corto.vistas_necesarias / largo.vistas_necesarias,
                               2.0, places=2)

    def test_la_ruta_de_shorts_pide_cientos_de_veces_mas_vistas(self):
        c = Carrera(hoy=HOY)
        self.assertGreater(c.ventaja_sobre_shorts, 100)
        rutas = comparar_rutas(c)
        self.assertEqual(rutas["ruta_shorts"]["vistas"], 10_000_000)
        self.assertIn("sin medir", rutas["fuente_rpm"])

    def test_sin_hipotesis_de_vistas_el_veredicto_dice_no_medido(self):
        self.assertIn("NO MEDIDO", Carrera(hoy=HOY).veredicto())

    def test_una_hipotesis_floja_no_llega_al_cambio(self):
        c = Carrera(hoy=HOY)
        self.assertTrue(c.llega_al_cambio(1500))
        self.assertFalse(c.llega_al_cambio(400))

    def test_las_horas_ya_hechas_descuentan(self):
        c = Carrera(hoy=HOY, horas_acumuladas=4000)
        self.assertEqual(c.minutos_que_faltan, 0)
        self.assertEqual(c.vistas_necesarias, 0)

    def test_retencion_imposible_falla(self):
        with self.assertRaises(ValueError):
            Carrera(hoy=HOY, retencion=1.4)
        with self.assertRaises(ValueError):
            Carrera(hoy=HOY, duracion_min=0)


class Plan(unittest.TestCase):
    def test_siete_dias_y_una_publicacion_por_dia(self):
        self.assertEqual(len(SEMANA), 7)
        self.assertEqual(set(publicaciones().values()), {1})

    def test_dos_largos_y_cinco_shorts(self):
        largos = [d for d in SEMANA if d.formato != "short"]
        self.assertEqual(len(largos), 2)
        self.assertEqual(len(SEMANA) - len(largos), 5)

    def test_la_cadencia_del_plan_pasa_por_formato(self):
        """Mezclar las horas de los dos formatos daba un bloqueo falso."""
        for v in veredicto_cadencia():
            self.assertTrue(v.pasa, v.motivo)

    def test_los_turnos_de_un_dia_no_se_solapan(self):
        for dia in SEMANA:
            fin = 0
            for turno in dia.turnos:
                self.assertGreaterEqual(turno.inicio, fin,
                                        f"{dia.nombre}: {turno.agente} se solapa")
                fin = turno.fin

    def test_todos_los_turnos_son_de_agentes_que_existen(self):
        for dia in SEMANA:
            for turno in dia.turnos:
                self.assertIn(turno.agente, SALA)
                if turno.relevo:
                    self.assertIn(turno.relevo, SALA)

    def test_la_carga_semanal_es_la_suma_de_los_turnos(self):
        self.assertEqual(sum(carga_por_agente().values()),
                         sum(d.minutos for d in SEMANA))
        self.assertEqual(horas_semana(), round(sum(d.minutos for d in SEMANA) / 60, 1))

    def test_el_cuello_de_botella_es_el_guion(self):
        clave, minutos = cuello_de_botella()
        self.assertEqual(clave, "guionista")
        self.assertEqual(minutos, max(carga_por_agente().values()))

    def test_el_calendario_arranca_en_lunes_y_con_semana_de_reserva(self):
        cal = calendario(date(2026, 10, 8), semanas=2)  # un jueves
        self.assertEqual(cal[0].fecha, date(2026, 10, 5))  # el lunes de su semana
        reserva = [e for e in cal if e.semana == 0]
        self.assertEqual(len(reserva), 7)
        self.assertFalse(any(e.publica for e in reserva))
        self.assertTrue(all(e.publica for e in cal if e.semana > 0))

    def test_sin_reserva_el_calendario_publica_desde_el_primer_dia(self):
        cal = calendario(date(2026, 10, 5), semanas=1, con_reserva=False)
        self.assertEqual(len(cal), 7)
        self.assertTrue(cal[0].publica)


class Jueces(unittest.TestCase):
    def test_los_pesos_de_cada_rubrica_suman_uno(self):
        for juez in JUECES:
            self.assertAlmostEqual(sum(c.peso for c in juez.criterios), 1.0)

    def test_una_rubrica_que_no_suma_uno_no_se_puede_construir(self):
        from estudio.jueces import Criterio, Juez
        with self.assertRaises(ValueError):
            Juez(clave="malo", nombre="J", oficio="x", mira="y",
                 criterios=(Criterio("a", "?", 0.5, "e"),))

    def test_la_fabrica_queda_vetada_por_riesgo(self):
        f = fallo()
        vetadas = [nombre for nombre, _ in f.vetadas]
        self.assertEqual(len(vetadas), 1)
        self.assertIn("fabrica", vetadas[0].lower())

    def test_el_veto_pesa_mas_que_la_media(self):
        """Una compuerta bloquea; si solo restara nota, A seguiria en carrera."""
        f = fallo()
        self.assertNotEqual(f.ganadora.clave, "fabrica")
        self.assertLess(f.nota("riesgo", "fabrica"), 2.5)

    def test_gana_el_catalogo_compuesto(self):
        f = fallo()
        self.assertEqual(f.ganadora.clave, "catalogo")
        self.assertEqual(max(f.medias.values()), f.medias["catalogo"])

    def test_los_jueces_no_estan_de_acuerdo_y_el_fallo_lo_dice(self):
        f = fallo()
        self.assertEqual(f.mayoria, "dossier")
        self.assertTrue(f.hubo_discrepancia)
        self.assertIn("agregado", f.describe())

    def test_las_enmiendas_salen_de_las_notas_bajas_de_la_ganadora(self):
        f = fallo()
        self.assertTrue(f.enmiendas)
        for e in f.enmiendas:
            self.assertLess(e["nota"], UMBRAL_ENMIENDA)
            self.assertTrue(e["enmienda"])
        self.assertEqual({e["juez"] for e in f.enmiendas}, {"Juez 3"})

    def test_la_ganadora_lleva_condiciones_escritas(self):
        self.assertTrue(fallo().ganadora.condiciones)

    def test_una_candidata_sin_nota_en_un_criterio_falla(self):
        coja = Estrategia(clave="coja", nombre="X", resumen="", cadencia="",
                          notas={"minutos_por_publicacion": (3, "por")})
        with self.assertRaises(KeyError) as ctx:
            puntuar(JUECES[0], coja)
        self.assertIn("siembra_en_frio", str(ctx.exception))

    def test_una_nota_fuera_de_rango_falla(self):
        notas = dict(CANDIDATAS[0].notas)
        notas["siembra_en_frio"] = (9, "imposible")
        with self.assertRaises(ValueError):
            puntuar(JUECES[0], Estrategia(clave="x", nombre="X", resumen="",
                                          cadencia="", notas=notas))

    def test_la_tabla_trae_una_fila_por_candidata(self):
        filas = tabla()
        self.assertEqual(len(filas), len(CANDIDATAS))
        self.assertEqual(sum(1 for f in filas if f["ganadora"]), 1)


class SalaEnVivo(unittest.TestCase):
    def test_los_estados_en_los_bordes_del_turno(self):
        s = Sala.del_dia(3)
        por_clave = {e.clave: e for e in s.estado(0)}
        self.assertEqual(por_clave["guionista"].estado, TRABAJANDO)
        self.assertEqual(por_clave["abogado"].estado, ESPERANDO)
        self.assertEqual(por_clave["cazador"].estado, LIBRE)

        al_cerrar = {e.clave: e for e in s.estado(s.jornada)}
        self.assertEqual(al_cerrar["guionista"].estado, ENTREGADO)
        self.assertEqual(al_cerrar["publicador"].estado, ENTREGADO)

    def test_el_progreso_va_de_cero_a_uno_dentro_del_turno(self):
        s = Sala.del_dia(4)
        montador = next(e for e in s.estado(90) if e.clave == "montador")
        self.assertEqual(montador.estado, TRABAJANDO)
        self.assertAlmostEqual(montador.progreso, 0.5, places=2)
        self.assertEqual(montador.minutos_restantes, 90)

    def test_el_mismo_minuto_da_el_mismo_estado(self):
        """La pagina lo anima a la velocidad que quiera: no depende del reloj."""
        a = Sala.del_dia(5).to_dict(120)
        b = Sala.del_dia(5).to_dict(120)
        self.assertEqual(a, b)

    def test_una_compuerta_cerrada_pone_al_dueno_en_rojo(self):
        parte = revisar(pieza_buena(metodo=""))
        s = Sala.desde_parte(2, parte)
        contable = next(e for e in s.estado(40) if e.clave == "contable")
        self.assertEqual(contable.estado, BLOQUEADO)
        self.assertIn("metodo", contable.motivo)
        self.assertTrue(s.to_dict(40)["bloqueada"])
        self.assertIn("parada en", s.describe(40))

    def test_el_bloqueo_no_adelanta_la_hora_del_turno(self):
        """Antes del turno, un agente bloqueado sigue esperando: no ha tocado nada."""
        s = Sala.del_dia(3, {"voz": "no hay narracion"})
        voz = next(e for e in s.estado(10) if e.clave == "voz")
        self.assertEqual(voz.estado, ESPERANDO)

    def test_el_relevo_se_ve_durante_unos_minutos(self):
        s = Sala.del_dia(1)
        self.assertIsNone(s.relevo_en(5))
        relevo = s.relevo_en(27)
        self.assertEqual((relevo["de"], relevo["a"]), ("medidor", "cazador"))

    def test_un_relevo_hacia_un_bloqueado_no_es_un_relevo(self):
        s = Sala.del_dia(1, {"cazador": "caso saturado"})
        self.assertIsNone(s.relevo_en(27))

    def test_el_minuto_se_recorta_a_la_jornada(self):
        s = Sala.del_dia(6)
        self.assertEqual(s.to_dict(99_999)["minuto"], s.jornada)
        self.assertEqual(s.to_dict(-10)["minuto"], 0)

    def test_un_dia_que_no_existe_falla(self):
        with self.assertRaises(ValueError):
            Sala.del_dia(8)

    def test_la_sala_en_texto_trae_los_once(self):
        lineas = Sala.del_dia(5).lineas(120)
        self.assertEqual(len(lineas), len(PLANTILLA))


class Herramientas(unittest.TestCase):
    def test_la_pila_gratuita_no_cuesta_nada_y_quita_horas(self):
        r = H.pila(0.0)
        self.assertEqual(r["coste_mes"], 0.0)
        self.assertLess(r["horas_semana"], r["horas_sin_herramientas"])

    def test_el_presupuesto_se_respeta(self):
        r = H.pila(20.0)
        self.assertLessEqual(r["coste_mes"], 20.0)
        self.assertTrue(r["descartadas"])

    def test_el_precio_no_verificado_no_entra_en_la_cuenta(self):
        """Un precio aproximado en una hoja de costes es el error de siempre."""
        r = H.pila(200.0)
        sin_precio = {h["nombre"] for h in r["sin_precio"]}
        self.assertIn("ElevenLabs", sin_precio)
        self.assertNotIn("ElevenLabs", {h["nombre"] for h in r["elegidas"]})

    def test_ninguna_herramienta_quita_mas_del_tope_del_turno(self):
        carga = carga_por_agente()
        quitado = H.ahorro(list(H.CATALOGO))
        for clave, minutos in quitado.items():
            self.assertLessEqual(minutos, int(carga[clave] * H.TOPE_AHORRO))

    def test_las_herramientas_apuntan_a_agentes_que_existen(self):
        for herramienta in H.CATALOGO:
            for clave in herramienta.quita:
                self.assertIn(clave, SALA)

    def test_las_dos_de_riesgo_dicen_que_compuerta_encienden(self):
        riesgos = {r["nombre"]: r["riesgo"] for r in H.riesgos()}
        self.assertIn("variacion", riesgos["OpusClip"])
        self.assertIn("politica_ia", riesgos["ElevenLabs"])

    def test_el_ahorro_se_declara_como_hipotesis(self):
        self.assertFalse(any(h.medido for h in H.CATALOGO))


class SemanaContraCompuertas(unittest.TestCase):
    """El plan que se vende tiene que pasar las compuertas que se venden con el.

    Si la semana canonica no pasara su propia compuerta de variacion, el plan
    seria un folleto: siete publicaciones al dia de la misma investigacion es
    justo el patron de riesgo, y decir que las compuertas lo contienen obliga a
    comprobarlo sin retocar nada a mano.
    """

    def piezas_de_la_semana(self) -> list[Pieza]:
        return [
            pieza_buena(
                clave=f"d{d.indice}",
                formato=d.formato,
                tipo=d.tipo,
                titulo=d.titulo,
                guion=f"{d.titulo}. " + " ".join(
                    f"{d.tipo} {d.nombre} apunte {i}" for i in range(40)
                ) + " La mediana fue de 14.237 euros. Quien firmo?",
            )
            for d in SEMANA
        ]

    def test_los_siete_angulos_son_distintos(self):
        tipos = [d.tipo for d in SEMANA]
        self.assertEqual(len(tipos), len(set(tipos)))

    def test_la_semana_pasa_su_propia_compuerta_de_variacion(self):
        v = variacion(self.piezas_de_la_semana())
        self.assertTrue(v.pasa, v.motivo)

    def test_repetir_un_angulo_rompe_la_semana(self):
        piezas = self.piezas_de_la_semana()
        piezas[3] = pieza_buena(clave="d4", formato="short", tipo=piezas[2].tipo,
                                guion=piezas[3].guion)
        self.assertFalse(variacion(piezas).pasa)

    def test_el_dia_del_documental_cuadra_con_la_carrera(self):
        """22 minutos en el plan y 22 en la hipotesis de la carrera: un numero."""
        from estudio.plan import DURACION
        viernes = next(d for d in SEMANA if d.formato == "documental")
        self.assertEqual(DURACION[viernes.formato], Carrera(hoy=HOY).duracion_min)


if __name__ == "__main__":
    unittest.main()
