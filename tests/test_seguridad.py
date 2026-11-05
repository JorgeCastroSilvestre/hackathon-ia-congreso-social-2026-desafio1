import ast
import copy
import json
from pathlib import Path
import re
import sys
import unittest
import uuid
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "comun"))
import persistencia as P
import validaciones as V


def extraer(ruta, nombres, entorno=None):
    """Ejecuta solo funciones/constantes puras sin iniciar la interfaz ni la IA."""
    arbol = ast.parse((RAIZ / ruta).read_text(encoding="utf-8"))
    nodos = []
    for n in arbol.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in nombres:
            nodos.append(n)
        elif isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in nombres for t in n.targets):
            nodos.append(n)
        elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name) and n.target.id in nombres:
            nodos.append(n)
    ns = {"re": re, "V": V, **(entorno or {})}
    exec(compile(ast.Module(body=nodos, type_ignores=[]), ruta, "exec"), ns)
    return ns


class Hoja:
    def __init__(self):
        self.filas = [P.COLUMNAS.copy()]
        self.timeout = False

    def get_all_values(self):
        return copy.deepcopy(self.filas)

    def append_row(self, fila, value_input_option):
        assert value_input_option == "RAW"
        self.filas.append(fila)
        if self.timeout:
            self.timeout = False
            raise TimeoutError("Respuesta perdida después de guardar")


class Persistencia(unittest.TestCase):
    def test_recuperacion_aislada_y_decisiones_concurrentes(self):
        ws = Hoja()
        for app, equipo, pid, dec in [("A", "M01", "C1", "Visitar"), ("A", "M01", "C2", "Llamar"),
                                      ("A", "M02", "C1", "Otro equipo"), ("B", "M01", "C1", "Otra app")]:
            P.guardar(ws, P.evento(app, equipo, "bandeja", pid, {"decision": dec}))
        # Reconstrucción desde cero después de perder la memoria del proceso.
        self.assertEqual(P.reconstruir(ws.filas, "A", "M01", "bandeja"),
                         {"C1": {"decision": "Visitar"}, "C2": {"decision": "Llamar"}})

    def test_timeout_reintento_no_revierte_decision_posterior(self):
        ws = Hoja()
        fila = P.evento("A", "M01", "bandeja", "C1", {"decision": "Visitar"})
        ws.timeout = True
        with self.assertRaises(TimeoutError): P.guardar(ws, fila)
        P.guardar(ws, P.evento("A", "M01", "bandeja", "C1", {"decision": "Llamar"}))
        P.guardar(ws, fila)
        self.assertEqual(len(ws.filas), 3)
        self.assertEqual(P.reconstruir(ws.filas, "A", "M01", "bandeja")["C1"]["decision"], "Llamar")

    def test_no_recorta_conversaciones_ni_ejecuta_formulas(self):
        ws = Hoja()
        datos = {"conversacion": '=IMPORTXML("ejemplo")\nTexto con tildes y "comillas"'}
        P.guardar(ws, P.evento("A", "M01", "bandeja", "C1", datos))
        self.assertEqual(P.reconstruir(ws.filas, "A", "M01", "bandeja")["C1"], datos)
        with self.assertRaises(ValueError): P.evento("A", "M01", "b", "C", {"texto": "x" * 50000})
        with self.assertRaises(ValueError): P.reconstruir([["cabecera incorrecta"]], "A", "M01", "b")


class Validacion(unittest.TestCase):
    def test_clasificacion_malformada_no_rompe_y_no_filtra_indicaciones(self):
        base = {"necesidades": ["salud"], "urgencia": "media", "resumen": "Solicita orientación.",
                "servicio_sugerido": "S07", "hoja_de_ruta": ["Consultar el catálogo."]}
        for cambios in [{"necesidades": None}, {"necesidades": [{}]}, {"hoja_de_ruta": 5},
                        {"hoja_de_ruta": []}, {"resumen": {}}, {"servicio_sugerido": []},
                        {"hoja_de_ruta": ["Tome dos pastillas juntas."]}, {"resumen": "Su abuelita necesita apoyo."}]:
            with self.subTest(cambios=cambios):
                c = {**base, **cambios}
                seguro = V.normalizar_clasificacion(c, base, {"salud"}, {"S07"},
                                                    lambda t: V.MEDICACION.search(t) or V.EDADISMO.search(t))
                self.assertEqual(seguro, base)

    def test_b_revalida_medicacion_y_lenguaje(self):
        cat = SimpleNamespace(id_servicio=["S07"])
        validar = extraer("desafio1/app_b_redcuida.py", {"DIAGNOSTICO", "EDADISMO", "validar"}, {"catalogo": cat})["validar"]
        bien = "Semana 12: necesita orientación. [S07] Salud Responde. Conversar con la persona."
        self.assertFalse(validar(bien))
        for texto in ["Tome dos pastillas juntas.", "Aumente la dosis.", "Su abuelita tiene demencia.", "Mi reina, tome 5 mg."]:
            with self.subTest(texto=texto): self.assertTrue(validar(bien + " " + texto))


class Protocolos(unittest.TestCase):
    def setUp(self):
        crisis = extraer("comun/nucleo_st.py", {"_CRISIS", "crisis"})["crisis"]
        self.ns = extraer("desafio1/app_a_conectamayor.py", {"_FAMILIA", "_MALTRATO", "_EMERGENCIA", "protocolo"},
                          {"N": SimpleNamespace(crisis=crisis)})

    def test_senales_directas_e_indirectas_sin_ia(self):
        for frase, esperado in [("Me dejaron sin comida y no puedo cocinar", "MALTRATO"),
                                ("Me dejaron sola dos semanas y no puedo cocinar", "MALTRATO"),
                                ("Mi hijo me obliga a firmar", "MALTRATO"),
                                ("Me esconden mis remedios", "MALTRATO"),
                                ("Me caí y sigo en el suelo", "CRISIS"),
                                ("Me pega y quiero quitarme la vida", "CRISIS"),
                                ("Mi sobrino cobra mi pensión y no me da plata", "MALTRATO")]:
            with self.subTest(frase=frase): self.assertEqual(self.ns["protocolo"](frase), esperado)

    def test_frases_cotidianas_no_activan(self):
        for frase in ["Vivo sola y cocino todos los días", "Quiero firmar un documento", "Mi hijo me ayuda con los trámites",
                      "Tengo comida para dos semanas", "Necesito organizar mis remedios", "Fui al taller de prevención de caídas"]:
            with self.subTest(frase=frase): self.assertIsNone(self.ns["protocolo"](frase))

    def test_se_conservan_todos_los_patrones_fijos_originales(self):
        anteriores = json.loads((RAIZ / "tests" / "patrones_base.json").read_text(encoding="utf-8"))
        for clave in ("_MALTRATO", "_EMERGENCIA"):
            for patron in anteriores[clave]: self.assertIn(patron, self.ns[clave])


class Sesion(unittest.TestCase):
    def test_salir_borra_historial_consentimiento_widgets_y_cliente(self):
        ss = {"_equipo": "A", "_codigo": "M01", "hist": ["privado"], "consent_0": True,
              "ta_PM-001": "texto", "_ws": object(), "_sheet_url": "planilla", "_pendiente": "mensaje"}
        cerrar = extraer("comun/nucleo_st.py", {"cerrar_sesion"}, {"st": SimpleNamespace(session_state=ss)})["cerrar_sesion"]
        cerrar()
        self.assertEqual(ss, {})


class Casos(unittest.TestCase):
    def test_una_conversacion_no_duplica_casos_y_no_confirma_fallo(self):
        class Estado(dict):
            def __getattr__(self, k): return self[k]
        ss = Estado(quien="Hablo por mí", hist=[{"role": "user", "content": "Necesito ayuda"}])
        guardados = {}
        n = SimpleNamespace(guardar_elemento=lambda col, cid, caso: guardados.setdefault(cid, caso), registrar=lambda ev: None)
        ns = extraer("desafio1/app_a_conectamayor.py", {"nuevo_caso"},
                     {"N": n, "ss": ss, "bandeja": [], "uuid": uuid,
                      "QUIEN": {"Hablo por mí": "persona"}, "conv_txt": lambda h: "Necesito ayuda"})
        crear = ns["nuevo_caso"]
        c = {"necesidades": ["salud"], "urgencia": "media"}
        cid = crear("libre", c, "conversación")
        self.assertEqual(crear("libre", c, "conversación"), cid)
        self.assertEqual(len(ns["bandeja"]), 1)
        self.assertEqual(len(guardados), 1)
        # Otra conversación, escritura rechazada: no se muestra como guardada.
        ss.pop("_caso_id")
        n.guardar_elemento = lambda *args: False
        self.assertIsNone(crear("libre", c, "conversación"))
        self.assertEqual(len(ns["bandeja"]), 1)
        self.assertEqual(len(ss["_casos_por_guardar"]), 1)


if __name__ == "__main__":
    unittest.main()
