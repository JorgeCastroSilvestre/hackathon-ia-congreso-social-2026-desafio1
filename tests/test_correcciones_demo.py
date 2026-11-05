"""Regresiones de la revisión de 7864b14. Sin conexiones a Google ni a IA."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desafio1"))
import test_streamlit as T
from test_streamlit import por_etiqueta
from test_educativo import textos
import nucleo_st as N
import validaciones as V
import servicios as S


class CorreccionesInterfaz(unittest.TestCase):
    def setUp(self):
        self.entorno = T.Interfaz()
        self.entorno.setUp()

    def tearDown(self):
        self.entorno.tearDown()

    def comenzar(self):
        at = self.entorno.iniciar("app_a_conectamayor.py")
        at.checkbox[0].check().run()
        por_etiqueta(at.button, "Comenzar").click().run()
        return at

    def test_saludo_de_planilla_no_evade_protecciones_y_registra_una_vez(self):
        import pandas as pd
        at = self.entorno.iniciar("app_a_conectamayor.py")
        at.session_state["_sheet_url"] = "https://docs.google.com/spreadsheets/d/planilla_ficticia"
        hoja = {"config": pd.DataFrame({"campo": ["mensaje_inicial"],
                                        "valor": ["Hola abuelita. Tome dos pastillas juntas."]})}
        with patch.object(N, "_descargar", return_value=hoja):
            at.run()
            at.checkbox[0].check().run()
            por_etiqueta(at.button, "Comenzar").click().run()
        self.assertFalse(at.exception)
        self.assertFalse(V.texto_inseguro(at.session_state["hist"][0]["content"]))
        self.assertEqual(at.session_state["hist"][0]["info"]["modo"], "configuracion")
        registros = [json.loads(l) for l in N.REGISTRO.read_text(encoding="utf-8").splitlines()]
        bloqueos = [r for r in registros if r.get("tarea") == "configuracion"]
        self.assertEqual(len(bloqueos), 1)
        self.assertNotIn("Hola abuelita", textos(at))

    def test_emergencia_pendiente_no_baja_por_maltrato_y_no_duplica(self):
        at = self.comenzar()
        with patch.object(self.entorno.hoja, "append_row", side_effect=TimeoutError("Fallo simulado")):
            at.chat_input[0].set_value("Me caí y sigo en el suelo").run()
            emergencia = next(iter(at.session_state["_casos_por_guardar"].values())).copy()
            at.chat_input[0].set_value("Mi hijo me grita").run()
        pendientes = at.session_state["_casos_por_guardar"]
        self.assertEqual(len(pendientes), 1)
        caso = next(iter(pendientes.values()))
        self.assertEqual(caso["urgencia"], "CRISIS")
        self.assertEqual(caso["resumen_ia"], emergencia["resumen_ia"])
        self.assertEqual(caso["servicio_sugerido"], emergencia["servicio_sugerido"])
        self.assertIn("Mi hijo me grita", caso["conversacion"])
        por_etiqueta(at.button, "Reintentar guardado de casos").click().run()
        self.assertFalse(at.exception)
        casos = N.P.reconstruir(self.entorno.hoja.filas, "D1-A", "M01", "bandeja")
        self.assertEqual(len(casos), 1)
        self.assertEqual(next(iter(casos.values()))["urgencia"], "CRISIS")
        self.assertFalse(at.session_state["_eventos_pendientes"])

    def test_fallo_central_no_reutiliza_modo_anterior_y_se_recupera(self):
        at = self.entorno.iniciar("app_a_conectamayor.py")
        self.assertEqual(at.session_state["_modo_estado"], "central")
        with patch.object(N, "_hoja_estado", side_effect=OSError("Fallo simulado")):
            at.run()
        self.assertEqual(at.session_state["_modo_estado"], "error")
        self.assertIn("No se pudo verificar el almacenamiento central", textos(at))
        self.assertNotIn(N.AVISO_DEMO_CENTRAL, textos(at))
        self.assertNotIn(N.AVISO_DEMO_TEMPORAL, textos(at))
        at.run()
        self.assertEqual(at.session_state["_modo_estado"], "central")
        self.assertNotIn("_error_estado", at.session_state)

    def test_primer_fallo_no_se_presenta_como_temporal(self):
        with patch.object(N, "_hoja_estado", side_effect=OSError("Fallo inicial simulado")):
            at = self.entorno.iniciar("app_a_conectamayor.py")
        self.assertEqual(at.session_state["_modo_estado"], "error")
        self.assertNotIn(N.AVISO_DEMO_TEMPORAL, textos(at))
        # Pasar a una instalación temporal real no deja un error de conexión viejo.
        with patch.object(N, "_hoja_estado", return_value=None): at.run()
        self.assertEqual(at.session_state["_modo_estado"], "temporal")
        self.assertNotIn("_error_estado", at.session_state)

    def test_json_invalido_identifica_clasificacion_local(self):
        at = self.comenzar()
        info = {"modo": "real", "proveedor": "doble local", "modelo": "prueba", "latencia_s": 0}
        with patch.object(N.IA, "llamar", return_value=("Respuesta sin JSON", info)):
            at.chat_input[0].set_value("Necesito compañía").run()
            por_etiqueta(at.button, "Terminar conversación").click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state["_info_clasif"]["modo"], "clasificacion_local")
        self.assertIn("Hoja de ruta preparada por clasificación local", textos(at))

    def test_reemplazo_tiene_origen_fijo_y_metadatos_no_llegan_al_proveedor(self):
        at = self.comenzar()
        info = {"modo": "real", "proveedor": "doble local", "modelo": "prueba", "latencia_s": 0}
        with patch.object(N.IA, "llamar", return_value=("Hola abuelita", info)) as llamada:
            at.chat_input[0].set_value("Quiero conversar").run()
            self.assertEqual(at.session_state["hist"][-1]["info"]["modo"], "proteccion")
            self.assertIn("Respuesta reemplazada por una protección fija", textos(at))
            self.assertNotIn("Respuesta generada por IA conectada", textos(at))
            at.chat_input[0].set_value("Quiero conocer apoyos").run()
            mensajes = llamada.call_args.args[0]
            self.assertTrue(all(set(m) == {"role", "content"} for m in mensajes))
        self.assertFalse(at.exception)

    def test_b_permite_pregunta_descriptiva_y_guarda_origen_editado(self):
        at = self.entorno.iniciar("app_b_redcuida.py")
        por_etiqueta(at.button, "Preparar próximo contacto").click().run()
        original = at.text_area[0].value
        at.text_area[0].set_value(original + " Pregúntele si toma medicamentos.").run()
        self.assertIn("Propuesta editada por una persona", textos(at))
        por_etiqueta(at.radio, "¿Qué decides?").set_value("Visitar esta semana").run()
        por_etiqueta(at.button, "Registrar decisión").click().run()
        self.assertFalse(at.exception)
        datos = N.P.reconstruir(self.entorno.hoja.filas, "D1-B", "M01", "decisiones")
        self.assertEqual(next(iter(datos.values()))["origen"]["modo"], "edicion_humana")


class TextosConfigurables(unittest.TestCase):
    def test_preguntas_descriptivas_sin_indicaciones(self):
        for texto in ("Pregúntele si toma medicamentos.", "La persona toma sus medicamentos con apoyo.",
                      "No recuerda si toma el remedio.", "Consulte al equipo de salud cómo tomar sus medicamentos."):
            with self.subTest(texto=texto): self.assertFalse(V.MEDICACION.search(texto))

    def test_indicaciones_y_dosis_siguen_bloqueadas(self):
        for texto in ("Tome dos pastillas juntas.", "Aumente la dosis.", "Deje de tomar el remedio.",
                      "Toma una pastilla ahora.", "Debe tomar dos pastillas juntas.", "Le recomiendo tomar el medicamento.",
                      "Tomar las pastillas por la noche.", "Use 5 mg."):
            with self.subTest(texto=texto): self.assertTrue(V.MEDICACION.search(texto))

    def test_servicio_extra_no_introduce_texto_inseguro(self):
        fila = {"id_servicio": "X01", "categoria": "salud", "nombre": "Orientación ficticia",
                "para_que_sirve": "Orientación de una persona", "cuando_sugerirlo": "Necesita apoyo",
                "como_acceder": "Consultar en el centro comunitario", "fuente_url": "https://example.org",
                "origen_dato": "sintético"}
        self.assertEqual(S.validar_servicio(fila), "")
        for texto in ("Tome dos pastillas juntas.", "Hola abuelita."):
            with self.subTest(texto=texto):
                self.assertTrue(S.validar_servicio({**fila, "como_acceder": texto}))


if __name__ == "__main__": unittest.main()
