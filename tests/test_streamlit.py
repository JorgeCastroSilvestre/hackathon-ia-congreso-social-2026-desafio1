"""Pruebas de interacción con Streamlit 1.50; IA y Google reemplazados por dobles locales."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "comun"))
from streamlit.testing.v1 import AppTest
import streamlit as st
import nucleo_st as N
import persistencia as P


class Hoja:
    def __init__(self): self.filas = [P.COLUMNAS.copy()]
    def get_all_values(self): return [f.copy() for f in self.filas]
    def append_row(self, fila, value_input_option):
        assert value_input_option == "RAW"
        self.filas.append(fila)


def por_etiqueta(elementos, etiqueta):
    return next(e for e in elementos if e.label == etiqueta)


class Interfaz(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.hoja = Hoja()
        self.patches = [patch.object(N, "_hoja_estado", return_value=self.hoja),
                        patch.object(N, "REGISTRO", Path(self.tmp.name) / "registro.jsonl"),
                        # AppTest 1.50 no serializa correctamente segmented_control.
                        # Se ejercitan los mismos contenedores, sin probar navegación/CSS.
                        patch.object(N, "pestanas", side_effect=lambda opciones, clave: [st.container() for _ in opciones])]
        for p in self.patches: p.start()
        N._global.clear()

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()

    def iniciar(self, archivo):
        at = AppTest.from_file(str(RAIZ / "desafio1" / archivo), default_timeout=30)
        at.secrets["equipos"] = {"M01": {"nombre": "Mentor prueba", "clave": "prueba"},
                                 "M02": {"nombre": "Mentor prueba", "clave": "prueba"}}
        at.run()
        por_etiqueta(at.text_input, "Código de equipo").set_value("M01")
        por_etiqueta(at.text_input, "Clave").set_value("prueba")
        por_etiqueta(at.button, "Entrar").click().run()
        self.assertFalse(at.exception)
        return at

    def test_a_protocolo_persiste_sin_ia_y_salir_limpia(self):
        at = self.iniciar("app_a_conectamayor.py")
        at.checkbox[0].check().run()
        por_etiqueta(at.button, "Comenzar").click().run()
        at.chat_input[0].set_value("Me dejaron sin comida y no puedo cocinar").run()
        self.assertFalse(at.exception)
        casos = P.reconstruir(self.hoja.filas, "D1-A", "M01", "bandeja")
        self.assertEqual(len(casos), 1)
        self.assertEqual(next(iter(casos.values()))["urgencia"], "MALTRATO")
        self.assertEqual(N._global()["consultas"], {})
        por_etiqueta(at.button, "Salir").click().run()
        self.assertFalse(at.exception)
        self.assertNotIn("hist", at.session_state)
        por_etiqueta(at.text_input, "Código de equipo").set_value("M02")
        por_etiqueta(at.text_input, "Clave").set_value("prueba")
        por_etiqueta(at.button, "Entrar").click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state["hist"], [])
        self.assertEqual(por_etiqueta(at.metric, "Casos en la bandeja").value, "0")
        self.assertFalse(P.reconstruir(self.hoja.filas, "D1-A", "M02", "bandeja"))

    def test_a_conserva_protocolo_si_google_falla_y_reintenta(self):
        at = self.iniciar("app_a_conectamayor.py")
        at.checkbox[0].check().run()
        por_etiqueta(at.button, "Comenzar").click().run()
        with patch.object(self.hoja, "append_row", side_effect=TimeoutError("Google sin conexión")):
            at.chat_input[0].set_value("Me dejaron sin comida y no puedo cocinar").run()
        self.assertFalse(at.exception)
        self.assertTrue(at.session_state["_casos_por_guardar"])
        self.assertEqual(len(self.hoja.filas), 1)
        self.assertTrue(por_etiqueta(at.button, "Salir").disabled)
        self.assertTrue(any("Gracias por contarlo" in m.value for m in at.markdown))
        por_etiqueta(at.button, "Reintentar guardado de casos").click().run()
        self.assertFalse(at.exception)
        self.assertFalse(at.session_state["_casos_por_guardar"])
        self.assertEqual(len(P.reconstruir(self.hoja.filas, "D1-A", "M01", "bandeja")), 1)

    def test_b_bloquea_texto_editado_y_recupera_decision(self):
        at = self.iniciar("app_b_redcuida.py")
        # N.pestanas ejecuta todos los contenedores; los no activos se ocultan con CSS.
        por_etiqueta(at.button, "Preparar próximo contacto").click().run()
        self.assertFalse(at.exception)
        original = at.text_area[0].value
        at.text_area[0].set_value(original + " Tome dos pastillas juntas.").run()
        por_etiqueta(at.radio, "¿Qué decides?").set_value("Visitar esta semana").run()
        por_etiqueta(at.button, "Registrar decisión").click().run()
        self.assertFalse(at.exception)
        self.assertTrue(at.error)
        self.assertFalse(P.reconstruir(self.hoja.filas, "D1-B", "M01", "decisiones"))
        at.text_area[0].set_value(original).run()
        por_etiqueta(at.button, "Registrar decisión").click().run()
        self.assertFalse(at.exception)
        datos = P.reconstruir(self.hoja.filas, "D1-B", "M01", "decisiones")
        self.assertEqual(len(datos), 1)
        self.assertEqual(next(iter(datos.values()))["decision"], "Visitar esta semana")
        # Pérdida de estado del proceso: una sesión nueva se reconstruye desde la hoja.
        N._global.clear()
        nuevo = self.iniciar("app_b_redcuida.py")
        self.assertFalse(nuevo.exception)
        self.assertTrue(any("Visitar esta semana" in m.value for m in nuevo.markdown))


if __name__ == "__main__":
    unittest.main()
