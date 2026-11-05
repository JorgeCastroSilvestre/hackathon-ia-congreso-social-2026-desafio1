"""Validaciones adicionales compartidas; conservan los filtros fijos de las apps."""
import re

DIAGNOSTICO = re.compile(r"\b(demencia|alzh?eimer|depresi[oó]n|parkinson|deterioro cognitivo|trastorno)\b|\bdiagn[oó]stic", re.I)
EDADISMO = re.compile(r"\b(abuelit[oa]s?|viejit[oa]s?|mi reina|mijit[oa]|tatita|caso problema|paciente dif[ií]cil)\b", re.I)

MEDICACION = re.compile(
    r"\b\d+(?:[.,]\d+)?\s?(mg|ml|gotas|comprimidos|pastillas)\b|"
    r"\b(deje|dejar|deja|suspenda|suspender|suspende|aumente|aumentar|aumenta|"
    r"disminuya|baje|bajar|junte|juntar)\s+(de tomar|la dosis|el remedio|los remedios|"
    r"el medicamento|la pastilla|las pastillas)|"
    r"\b(tom[ae]|tomar|tome[n]?|dupliqu[ae]|duplicar|reduzca|reducir|mezcl[ae]|mezclar|"
    r"suspend[ae]|suspender|aument[ae]|aumentar|disminuy[ae]|disminuir)\b"
    r"[^.!?\n]{0,70}\b(dosis|pastillas?|medicamentos?|remedios?|comprimidos?|gotas|insulina)\b",
    re.I)


def normalizar_clasificacion(c, respaldo, categorias, servicios, inseguro):
    """JSON mal tipado o sin pasos utilizables vuelve a clasificación local segura."""
    if not isinstance(c, dict):
        return respaldo
    necesidades, pasos = c.get("necesidades"), c.get("hoja_de_ruta")
    if (not isinstance(necesidades, list) or not all(isinstance(n, str) for n in necesidades)
            or not isinstance(pasos, list) or not pasos or not all(isinstance(p, str) and p.strip() for p in pasos)
            or not isinstance(c.get("resumen"), str)
            or not isinstance(c.get("servicio_sugerido"), str)
            or not isinstance(c.get("urgencia"), str)):
        return respaldo
    # Resumen y hoja de ruta se muestran a personas: validar ambos.
    if any(inseguro(t) for t in [c["resumen"], *pasos]):
        return respaldo
    return {"necesidades": [n for n in necesidades if n in categorias] or ["ninguna"],
            "urgencia": c["urgencia"] if c["urgencia"] in ("baja", "media", "alta") else "media",
            "resumen": c["resumen"],
            "servicio_sugerido": c["servicio_sugerido"] if c["servicio_sugerido"] in servicios else "ninguno",
            "hoja_de_ruta": pasos[:3]}
