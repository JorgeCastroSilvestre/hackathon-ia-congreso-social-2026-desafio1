"""Pruebas del propósito educativo: avisos de demo y simulación, recorrido, guía de adaptación y límites."""
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

TEMPORAL = "Los casos y decisiones temporales se borran al reiniciar."
SIMULACION = "Ninguna acción de esta demo contacta a personas ni activa servicios reales"


class Hoja:
    def __init__(self): self.filas = [P.COLUMNAS.copy()]
    def get_all_values(self): return [f.copy() for f in self.filas]
    def append_row(self, fila, value_input_option): self.filas.append(fila)


def textos(at):
    """Todo el texto visible que AppTest expone (markdown, avisos, captions y títulos de los paneles plegables)."""
    partes = [m.value for m in at.markdown] + [c.value for c in at.caption] + [i.value for i in at.info]
    partes += [e.label for e in at.expander]
    return "\n".join(str(p) for p in partes)


class Educativo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(N, "REGISTRO", Path(self.tmp.name) / "registro.jsonl"),
                        # AppTest 1.50 no serializa segmented_control: se ejercitan los mismos contenedores.
                        patch.object(N, "pestanas", side_effect=lambda opciones, clave: [st.container() for _ in opciones])]
        for p in self.patches: p.start()
        N._global.clear()

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()

    def entrar(self, archivo, hoja=None):
        with patch.object(N, "_hoja_estado", return_value=hoja):
            at = AppTest.from_file(str(RAIZ / "desafio1" / archivo), default_timeout=30)
            at.run()
            self.assertIn(SIMULACION, textos(at))  # visible antes de comenzar, en la pantalla de ingreso
            at.text_input[0].set_value("demo"); at.text_input[1].set_value("demo")
            next(b for b in at.button if b.label == "Entrar").click().run()
            self.assertFalse(at.exception)
            return at

    def test_a_modo_temporal_con_recorrido_guia_y_limites(self):
        at = self.entrar("app_a_conectamayor.py")
        t = textos(at)
        for esperado in (TEMPORAL, SIMULACION, "Recorrido sugerido", "Límites de esta demo", "Cómo adaptar esta demo",
                         "La decisión final siempre es humana", "Elija un perfil ficticio", "Bandeja simulada"):
            self.assertIn(esperado, t)

    def test_b_modo_temporal_con_recorrido_guia_y_limites(self):
        at = self.entrar("app_b_redcuida.py")
        t = textos(at)
        for esperado in (TEMPORAL, SIMULACION, "Recorrido sugerido", "Cómo adaptar esta demo",
                         "El puntaje solo lee las casillas marcadas", "Menos registros no significa necesariamente menos necesidad",
                         "Observe la equidad"):
            self.assertIn(esperado, t)

    def test_no_dice_temporal_si_el_estado_se_guarda(self):
        at = self.entrar("app_a_conectamayor.py", hoja=Hoja())
        t = textos(at)
        self.assertNotIn(TEMPORAL, t)
        self.assertIn("se guardan en una planilla central", t)

    def test_protocolo_no_simula_una_accion_real(self):
        with patch.object(N, "_hoja_estado", return_value=None):
            at = self.entrar("app_a_conectamayor.py")
            at.checkbox[0].check().run()
            next(b for b in at.button if b.label == "Comenzar").click().run()
            at.chat_input[0].set_value("mi sobrino cobra mi pensión y no me da plata").run()
            self.assertFalse(at.exception)
            respuesta = next(m.value for m in at.markdown if "Fono Mayor" in m.value)
            self.assertNotIn("Avisé", respuesta)
            self.assertIn("no se contacta a nadie", respuesta)
            self.assertIn("800 400 035", respuesta)  # se conservan las vías de ayuda
            self.assertEqual(at.metric[0].value, "1")  # el caso quedó en la bandeja simulada

    def test_respuesta_preparada_se_identifica(self):
        with patch.object(N, "_hoja_estado", return_value=None):
            at = self.entrar("app_b_redcuida.py")
            next(b for b in at.button if b.label == "Preparar próximo contacto").click().run()
            self.assertFalse(at.exception)
            self.assertIn("Respuesta preparada de ejemplo", textos(at))


if __name__ == "__main__":
    unittest.main()
