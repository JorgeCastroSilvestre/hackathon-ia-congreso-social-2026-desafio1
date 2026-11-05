"""Eventos de estado en una pestaña privada; sin dependencias de Streamlit.

Cada escritura agrega un evento completo de UN elemento, nunca una foto de todo
el equipo. Dos personas que deciden casos distintos no se pisan entre sí.
Para el mismo elemento, prevalece el último evento en el orden de la planilla.
"""
import datetime
import json
import uuid

COLUMNAS = ["evento_id", "fecha_utc", "app", "equipo_codigo", "coleccion", "elemento_id", "datos_json"]
PESTANA = "estado_d1_v1"


def evento(app, equipo, coleccion, elemento, datos, evento_id=None):
    contenido = json.dumps(datos, ensure_ascii=False, allow_nan=False)
    # No truncar conversaciones: una celda de Sheets admite hasta 50.000 caracteres.
    if len(contenido) > 45000:
        raise ValueError("El caso excede el tamaño admitido; no se guardó ni se recortó.")
    return [evento_id or uuid.uuid4().hex,
            datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            app, equipo, coleccion, elemento, contenido]


def reconstruir(filas, app, equipo, coleccion):
    if not filas or filas[0] != COLUMNAS:
        raise ValueError("La pestaña de estado no tiene las columnas esperadas.")
    estado, vistos = {}, set()
    for fila in filas[1:]:
        if not any(fila):
            continue
        if len(fila) < 6:
            raise ValueError("Hay una fila de estado incompleta; revisar la planilla central.")
        if fila[2:5] != [app, equipo, coleccion]:
            continue
        if len(fila) != len(COLUMNAS) or not fila[0] or not fila[5]:
            raise ValueError("Hay un evento del equipo incompleto.")
        if fila[0] in vistos:
            continue
        datos = json.loads(fila[6])
        if not isinstance(datos, dict):
            raise ValueError("El estado debe ser un objeto JSON.")
        estado[fila[5]] = datos
        vistos.add(fila[0])
    return estado


def guardar(ws, fila):
    """RAW evita interpretar texto del usuario como fórmulas.

    El ID se conserva al reintentar tras un timeout. Si el servidor alcanzó a
    escribir, no se vuelve a agregar el evento ni se revierte una decisión nueva.
    """
    filas = ws.get_all_values()
    if not filas or filas[0] != COLUMNAS:
        raise ValueError("Cabecera de estado inválida.")
    if any(r and r[0] == fila[0] for r in filas[1:]):
        return
    ws.append_row(fila, value_input_option="RAW")
