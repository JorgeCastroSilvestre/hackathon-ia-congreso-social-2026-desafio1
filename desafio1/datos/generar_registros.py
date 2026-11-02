"""Genera registros SINTÉTICOS de seguimiento comunitario de personas mayores para el
Desafío 1 (RedCuida IA) de la Hackathon IA Congreso Social UC 2026.

Ningún registro corresponde a una persona real. Simula 12 semanas de un equipo de monitores
y voluntarios que visita, llama y ve en talleres a 120 personas mayores de una comuna ficticia.

Decisiones de diseño (documentadas para que los equipos las descubran y discutan):
- Cada persona sigue una TRAYECTORIA oculta: estable, mejora, deterioro gradual, evento agudo
  (caída), aislamiento progresivo o sobrecarga de quien la cuida. Solo existe en los datos
  sintéticos y permite medir si la priorización detecta a quienes están cambiando.
- Las señales se registran solo en contactos logrados, y 1 de cada 4 queda SOLO EN LA NOTA
  (el monitor no marcó la casilla): el puntaje no la ve, pero una persona o la IA que lea la nota sí.
- Sesgo de registro: las personas rurales o sin teléfono tienen menos contactos, así que
  generan menos señales aunque les pase lo mismo.
"""
import numpy as np
import pandas as pd

SEMANAS = 12
SENALES = ["caida", "desorientacion", "come_poco", "animo_bajo", "medicamentos", "aislamiento", "cuidador_agotado", "sospecha_maltrato"]
TRAYECTORIAS = {"estable": 0.45, "mejora": 0.10, "deterioro_gradual": 0.13, "evento_agudo": 0.10, "aislamiento": 0.12, "sobrecarga_cuidador": 0.10}
NOTAS = {
    "caida": ["Se cayó en el baño hace unos días; tiene un moretón en el brazo.", "Cuenta que se resbaló en la cocina, dice que no fue nada.",
              "La vecina dice que la encontró en el suelo del patio."],
    "desorientacion": ["Me preguntó dos veces qué día era.", "Se confundió con el nombre de su nieta.", "No recordaba que habíamos quedado de vernos."],
    "come_poco": ["El refrigerador estaba casi vacío.", "Dice que no tiene hambre; se ve más delgad{a}.", "Dejó la mitad del almuerzo, dice que cocinar le cansa."],
    "animo_bajo": ["L{a} noté triste, dice que ya no le dan ganas de nada.", "Habló poco y se emocionó al recordar a su pareja.",
                   "Dice que se siente una carga para su familia."],
    "medicamentos": ["Tenía las pastillas mezcladas en una bolsa, no sabe cuáles tomó.", "Se le acabaron los remedios y no ha ido a buscarlos al CESFAM.",
                     "No se acuerda si tomó la pastilla de la presión."],
    "aislamiento": ["Dice que no ha salido de la casa en toda la semana.", "Dejó de ir al club, dice que le da flojera.", "Cuenta que nadie l{a} ha visitado en semanas."],
    "cuidador_agotado": ["Quien l{a} cuida dice que no duerme bien hace semanas y está agotad{c}.", "Quien l{a} cuida dice que no da más y no tiene reemplazo.",
                         "Quien l{a} cuida se puso a llorar en la puerta; dice que no tiene tiempo para nada."],
    "sospecha_maltrato": ["Comenta que un familiar le maneja la pensión y no le da plata.", "Tenía un moretón y no quiso explicar cómo se lo hizo; el familiar respondió por {e}.",
                          "Dice que en la casa le gritan cuando pide ayuda."],
}
NEUTRAS = ["Conversamos un rato, está tranquil{a} y content{a} con su huerto.", "Fue al taller de memoria y le gustó.", "Me contó de sus nietos, se ve bien.",
           "Todo en orden, pidió que volvamos la próxima semana.", "Está animad{a}, fue a la feria con una vecina.", "Sin novedades; se queja un poco del frío."]
FALLIDOS = {"Llamada": ["No contestó el teléfono.", "El teléfono sonaba apagado."],
            "Visita": ["Fui a la casa y nadie abrió.", "No estaba en la casa; un vecino no sabía dónde estaba."],
            "Taller": ["No vino al taller esta semana."]}
NOMBRES = {"F": ["Rosa", "María", "Carmen", "Ana", "Luisa", "Elena", "Teresa", "Gladys", "Juana", "Olga", "Silvia", "Marta", "Inés", "Raquel", "Norma"],
           "M": ["José", "Luis", "Juan", "Pedro", "Hernán", "Manuel", "Jorge", "Sergio", "Raúl", "Héctor", "Carlos", "Mario"]}


def generar() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Regenera personas y contactos (semilla fija 2026: siempre el mismo resultado)."""
    rng = np.random.default_rng(2026)
    N = 120
    per = pd.DataFrame({"id_persona": [f"PM-{i:03d}" for i in range(1, N + 1)]})
    per["sexo"] = rng.choice(["F", "M"], N, p=[0.6, 0.4])
    per["nombre_ficticio"] = [f"{rng.choice(NOMBRES[s])} {chr(65 + rng.integers(0, 26))}." for s in per.sexo]
    per["edad"] = np.clip(65 + rng.gamma(2.2, 5.5, N), 65, 97).round().astype(int)
    per["sector"] = rng.choice(["Urbano centro", "Urbano periferia", "Rural"], N, p=[0.40, 0.35, 0.25])
    per["vive_sola"] = (rng.random(N) < np.where(per.sexo == "F", 0.40, 0.28)).astype(int)
    p_tel = np.where(per.sector == "Rural", 0.65, 0.88) - np.where(per.edad >= 85, 0.15, 0)
    per["tiene_telefono"] = (rng.random(N) < p_tel).astype(int)
    p_dep = np.clip((per.edad - 65) / 40, 0, 0.8)
    per["autonomia"] = [rng.choice(["Autovalente", "Dependencia leve", "Dependencia moderada", "Dependencia severa"],
                                   p=[1 - d, d * 0.5, d * 0.35, d * 0.15]) for d in p_dep]
    per["cuidador_principal"] = [("Ninguno" if rng.random() < 0.8 else rng.choice(["Hija/o", "Pareja"])) if a == "Autovalente"
                                 else rng.choice(["Hija/o", "Pareja", "Vecina/o", "Cuidadora pagada", "Ninguno"], p=[0.4, 0.2, 0.1, 0.1, 0.2])
                                 for a in per.autonomia]
    per["monitor_asignado"] = [f"Monitor/a {rng.integers(1, 7)}" for _ in range(N)]
    t = rng.choice(list(TRAYECTORIAS), N, p=list(TRAYECTORIAS.values()))
    con_cuidador = (per.cuidador_principal != "Ninguno").to_numpy()
    t = np.where(con_cuidador & (rng.random(N) < 0.3), "sobrecarga_cuidador", t)  # la sobrecarga solo existe si alguien cuida
    per["trayectoria"] = np.where((t == "sobrecarga_cuidador") & ~con_cuidador, "estable", t)
    per["semana_inicio_cambio"] = rng.integers(4, 9, N)
    per.loc[per.trayectoria == "evento_agudo", "semana_inicio_cambio"] = rng.integers(8, 12, (per.trayectoria == "evento_agudo").sum())
    per.loc[per.trayectoria.isin(["estable", "mejora"]), "semana_inicio_cambio"] = 0

    filas = []
    for p in per.itertuples():
        g = {"a": "a" if p.sexo == "F" else "o", "e": "ella" if p.sexo == "F" else "él",
             "c": "a" if p.cuidador_principal in ("Hija/o", "Vecina/o", "Cuidadora pagada") else "o"}
        lam = 1.1 * (0.5 if p.sector == "Rural" else 1) * (1 if p.tiene_telefono else 0.6)
        tipos = ["Visita"] + (["Llamada"] if p.tiene_telefono else []) + (["Taller"] if p.autonomia in ("Autovalente", "Dependencia leve") else [])
        for w in range(1, SEMANAS + 1):
            ini = p.semana_inicio_cambio
            rampa = (w - ini + 1) / (SEMANAS - ini + 1) if ini and w >= ini else 0
            prob = {s: 0.02 for s in SENALES}
            prob["sospecha_maltrato"] = 0.003
            prob["cuidador_agotado"] = 0.03 if p.cuidador_principal != "Ninguno" else 0
            p_logrado = 0.9
            if p.trayectoria == "deterioro_gradual":
                for s in ("desorientacion", "come_poco", "medicamentos"): prob[s] += 0.55 * rampa
                prob["animo_bajo"] += 0.25 * rampa
            elif p.trayectoria == "evento_agudo" and w >= ini:
                prob["caida"] = 0.95 if w == ini else 0.05
                if w > ini:
                    prob["animo_bajo"] += 0.35; prob["aislamiento"] += 0.30; prob["come_poco"] += 0.20
            elif p.trayectoria == "aislamiento":
                prob["aislamiento"] += 0.5 * rampa; prob["animo_bajo"] += 0.35 * rampa; p_logrado = 0.9 - 0.5 * rampa
            elif p.trayectoria == "sobrecarga_cuidador":
                prob["cuidador_agotado"] += 0.6 * rampa
                if w >= ini + 3: prob["sospecha_maltrato"] += 0.12
            elif p.trayectoria == "mejora" and w <= 5:
                prob["animo_bajo"] += 0.40; prob["aislamiento"] += 0.35; prob["come_poco"] += 0.20
            n = min(3, rng.poisson(lam))
            if p.trayectoria == "evento_agudo" and w == ini: n = max(n, 1)  # la caída queda registrada en algún contacto
            for _ in range(n):
                tipo = rng.choice(tipos)
                fila = {"id_persona": p.id_persona, "semana": w, "tipo": tipo,
                        "registrado_por": rng.choice(["Monitor/a", "Voluntario/a"], p=[0.7, 0.3]) if tipo != "Taller" else "Monitor/a de taller",
                        "logrado": int(rng.random() < p_logrado), **{s: 0 for s in SENALES}}
                if not fila["logrado"]:
                    fila["nota"] = rng.choice(FALLIDOS[tipo]); filas.append(fila); continue
                factor = {"Visita": 1, "Llamada": 0.7, "Taller": 0.5}[tipo]
                ocurren = [s for s in SENALES if rng.random() < prob[s] * factor and not (tipo == "Taller" and s in ("caida", "come_poco", "medicamentos"))]
                if p.trayectoria == "evento_agudo" and w == ini and "caida" not in ocurren: ocurren.append("caida")
                frases = []
                for s in ocurren:
                    frases.append(rng.choice(NOTAS[s]).format(**g))
                    fila[s] = int(rng.random() < 0.75)  # 1 de cada 4 señales queda solo en la nota
                fila["nota"] = " ".join(frases) if frases else rng.choice(NEUTRAS).format(**g)
                filas.append(fila)
    con = pd.DataFrame(filas)
    return per, con


if __name__ == "__main__":
    from pathlib import Path
    aqui = Path(__file__).parent
    per, con = generar()
    per.to_csv(aqui / "personas_mayores_sinteticas.csv", index=False, encoding="utf-8")
    con.to_csv(aqui / "contactos_sinteticos.csv", index=False, encoding="utf-8")
    print(f"{len(per)} personas, {len(con)} contactos")
    print(per.trayectoria.value_counts().to_string())
    print("Contactos por persona según sector:", con.groupby("id_persona").size().reindex(per.id_persona, fill_value=0).groupby(per.sector.values).mean().round(1).to_dict())
