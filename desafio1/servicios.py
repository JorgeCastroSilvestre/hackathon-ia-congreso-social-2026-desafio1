"""Catálogo de servicios de apoyo para personas mayores y quienes las cuidan: base fija + filas que agrega el equipo en `servicios_extra`."""
import re
import pandas as pd
import validaciones as V

CATEGORIAS = {"compania", "salud", "tramites", "cuidado", "cuidadores", "maltrato", "estafas"}
ORIGENES = {"real", "sintético", "sintetico"}
BASE_IDS = {f"S{i:02d}" for i in range(1, 11)}

def validar_servicio(fila) -> str:
    g = lambda c: str(fila.get(c, "")).strip()
    if not re.fullmatch(r"[A-Za-z]{1,3}\d{1,3}", g("id_servicio")): return "id_servicio debe ser 1 a 3 letras y 1 a 3 números, por ejemplo X01"
    if g("id_servicio").upper() in BASE_IDS: return "ese id ya existe en el catálogo base (usen X01, X02…)"
    if g("categoria").lower() not in CATEGORIAS: return f"categoria debe ser una de: {', '.join(sorted(CATEGORIAS))}"
    for c in ("nombre", "para_que_sirve", "cuando_sugerirlo", "como_acceder"):
        if not g(c): return f"falta completar '{c}'"
        if V.texto_inseguro(g(c)): return f"'{c}' no cumple las protecciones de salud o trato respetuoso"
    if not g("fuente_url").startswith("http"): return "fuente_url debe ser un enlace (http…) a la fuente del servicio"
    if g("origen_dato").lower() not in ORIGENES: return "origen_dato debe ser 'real' o 'sintético'"
    return ""

def catalogo(aqui, extra: pd.DataFrame) -> pd.DataFrame:
    base = pd.read_csv(aqui / "datos" / "catalogo_servicios.csv", dtype=str)
    if extra is not None and len(extra):
        ex = extra.copy(); ex["id_servicio"] = ex["id_servicio"].str.strip().str.upper()
        base = pd.concat([base, ex[base.columns]], ignore_index=True).drop_duplicates("id_servicio")
    return base

def texto(cat: pd.DataFrame) -> str:
    return "\n".join(f"- [{r.id_servicio}] {r.nombre} ({r.categoria}): {r.para_que_sirve}. Sugerir si: {r.cuando_sugerirlo}. Cómo acceder: {r.como_acceder}"
                     for r in cat.itertuples())
