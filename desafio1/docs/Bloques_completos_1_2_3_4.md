# Bloques completos de las mejoras 1, 2, 3 y 4

Base: cb8fdcd. Ubicaciones referidas a los archivos entregados.
Los bloques superiores (pantalla principal incluida) se reproducen completos.
Los archivos Python completos son la fuente lista para reemplazar.

## comun/nucleo_st.py

### Import · linea 18

```python
import persistencia as P

```

### identidad_equipo · linea 62

```python
def identidad_equipo() -> str:
    return st.session_state.get("_codigo") or st.session_state.get("_equipo", "demo")

```

### _clave_estado · linea 66

```python
def _clave_estado(clave):
    return f"{st.session_state.get('_app')}|{identidad_equipo()}|{clave}"

```

### _hoja_estado · linea 70

```python
def _hoja_estado():
    sid, cred = _secret("registro.sheet_id"), _secret("gcp_service_account")
    if not sid and not cred:
        return None
    if not sid or not cred:
        raise ValueError("Falta registro.sheet_id o gcp_service_account.")
    # No guardar este cliente en session_state: se descarta al salir y no se
    # reutiliza una conexión con otra configuración de secrets.
    import gspread
    libro = gspread.service_account_from_dict(dict(cred)).open_by_key(sid)
    return libro.worksheet(P.PESTANA)

```

### estado_equipo · linea 83

```python
def estado_equipo(clave: str) -> dict:
    """Recupera estado confirmado. La pestaña se prepara antes del despliegue."""
    g = _global()
    with g["lock"]:
        anterior = dict(g["equipos"].setdefault(_clave_estado(clave), {}))
    try:
        ws = _hoja_estado()
        if ws is None:
            st.warning("Modo temporal: sin planilla central, los casos y decisiones se pierden al reiniciar. Descargue el respaldo antes de salir.")
            return anterior
        datos = P.reconstruir(ws.get_all_values(), st.session_state.get("_app"), identidad_equipo(), clave)
        if clave == "bandeja":
            campos = ("caso", "persona", "conversa", "origen", "urgencia", "necesidades", "servicio_sugerido", "resumen_ia", "conversacion", "decision")
            if any(any(not isinstance(d.get(c), str) for c in campos) or d["caso"] != i for i, d in datos.items()):
                raise ValueError("Hay un caso con estructura inválida.")
        if clave == "decisiones" and any(not isinstance(d.get("decision"), str) for d in datos.values()):
            raise ValueError("Hay una decisión con estructura inválida.")
        with g["lock"]:
            g["equipos"][_clave_estado(clave)] = datos
        st.session_state.pop("_error_estado", None)
        st.caption("Casos y decisiones recuperados de la planilla central.")
        return dict(datos)
    except Exception:
        st.session_state["_error_estado"] = True
        st.error("No se pudo leer el estado central. La vista puede estar incompleta. No se confirmarán cambios hasta recuperar la conexión; revise la pestaña estado_d1_v1 y sus permisos.")
        return anterior

```

### guardar_elemento · linea 111

```python
def guardar_elemento(coleccion, elemento, datos) -> bool:
    """Solo confirma la operación después de persistir; conserva el ID al reintentar."""
    g = _global()
    firma = hashlib.sha256(json.dumps([coleccion, elemento, datos], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    pendientes = st.session_state.setdefault("_eventos_pendientes", {})
    try:
        fila = pendientes.setdefault(firma, P.evento(st.session_state.get("_app"), identidad_equipo(), coleccion, elemento, datos))
        ws = _hoja_estado()
        if ws is not None:
            if st.session_state.get("_error_estado"):
                raise ValueError("No se pudo verificar la lectura de estado.")
            P.guardar(ws, fila)
        with g["lock"]:
            g["equipos"].setdefault(_clave_estado(coleccion), {})[elemento] = dict(datos)
        for clave, pendiente in list(pendientes.items()):
            if pendiente[2:6] == fila[2:6]: pendientes.pop(clave, None)
        return True
    except Exception:
        st.error("No se confirmó el guardado. Mantenga esta sesión abierta y reintente cuando vuelva la conexión. No reinicie la app todavía.")
        return False

```

### cerrar_sesion · linea 133

```python
def cerrar_sesion():
    # Incluye consentimientos, historial, widgets, propuestas y clientes antiguos.
    for clave in list(st.session_state):
        del st.session_state[clave]

```

### registrar · linea 140

```python
def registrar(ev: dict):
    ev = {"marca_tiempo": datetime.datetime.now().isoformat(timespec="seconds"), "app": st.session_state.get("_app"),
          "equipo_codigo": identidad_equipo(),
          "equipo": st.session_state.get("_equipo"), "planilla": st.session_state.get("_sheet_url", ""), **ev}
    try:
        with _lock:
            with open(REGISTRO, "a", encoding="utf-8") as f:
                f.write(json.dumps(ev, ensure_ascii=False, default=str) + "\n")
    except OSError:
        st.session_state["_aviso_reg"] = "No se pudo escribir el registro local; revise el respaldo central antes de reiniciar."
    _copiar_central(ev)

```

### _copiar_central · linea 152

```python
def _copiar_central(ev):
    sid, cred = _secret("registro.sheet_id"), _secret("gcp_service_account")
    if not sid or not cred:
        return
    try:
        import gspread  # type: ignore
        if "_ws" not in st.session_state:
            libro = gspread.service_account_from_dict(dict(cred)).open_by_key(sid)
            # El registro histórico nunca debe escribir dentro de la nueva pestaña de estado.
            st.session_state["_ws"] = next(h for h in libro.worksheets() if h.title != P.PESTANA)
        st.session_state["_ws"].append_row([str(ev.get(k, ""))[:45000] for k in
                                            ("marca_tiempo", "app", "equipo", "tipo", "tarea", "modo", "proveedor", "entrada", "salida", "decision", "nota")], value_input_option="RAW")
    except Exception as e:
        st.session_state["_aviso_reg"] = f"No se pudo copiar el registro a la planilla central: {str(e)[:80]}"

```

### registro_equipo · linea 167

```python
def registro_equipo() -> pd.DataFrame:
    if not REGISTRO.exists():
        return pd.DataFrame()
    filas = []
    for l in REGISTRO.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(l)
        except Exception:
            continue
        if e.get("equipo_codigo") == identidad_equipo() and e.get("app") == st.session_state.get("_app"):
            filas.append(e)
    return pd.DataFrame(filas)

```

### acceso · linea 282

```python
def acceso() -> str:
    """Código y clave de equipo, guardados en secrets:
    [equipos.E01]  nombre = "Equipo 01"  clave = "..."   (sin secrets: código 'demo', clave 'demo')."""
    if st.session_state.get("_equipo"):
        return st.session_state["_equipo"]
    equipos = {k: dict(v) for k, v in dict(_secret("equipos", {}) or {}).items() if hasattr(v, "keys")}
    _, centro, _ = st.columns([1, 2, 1])
    with centro:
        encabezado(st.session_state.get("_titulo_app", "Hackathon IA · Desafío 2"),
                   st.session_state.get("_subtitulo_acceso", "Ninguno se queda atrás · Hackathon IA Aplicada · Congreso Social UC 2026"),
                   [st.session_state.get("_chip_acceso", "Desafío 2 · Educación")])
        aviso_ia()
        with st.container(border=True):
            st.markdown("#### Ingreso del equipo")
            c1, c2 = st.columns(2)
            cod = c1.text_input("Código de equipo", placeholder="Ej: E01").strip().upper()
            cla = c2.text_input("Clave", type="password").strip()
            if st.button("Entrar", type="primary", width="stretch"):
                if cod in equipos and cla == str(equipos[cod].get("clave", "")):
                    cerrar_sesion()
                    st.session_state["_equipo"] = equipos[cod].get("nombre", cod)
                    st.session_state["_codigo"] = cod
                    registrar({"tipo": "ingreso"}); st.rerun()
                elif not equipos and cod == "DEMO" and cla == "demo":
                    cerrar_sesion()
                    st.session_state["_equipo"] = "demo"; st.session_state["_codigo"] = "DEMO"; st.rerun()
                else:
                    st.error("Código o clave incorrectos. Los entrega su mentor.")
            st.caption("El código y la clave los entrega su mentor." if equipos else "Instalación de prueba: código `demo`, clave `demo`.")
    st.stop()

```

### IA · linea 391

```python
class IA:
    def __init__(self, respuestas_demo: dict | None = None):
        self.orden = [str(p) for p in _secret("ia.orden", ["groq", "mistral", "openai"])]
        self.prov = {}
        for p in self.orden:
            base = PROVEEDORES.get(p, {"url": "", "modelos": []})
            modelos = _secret(f"ia.{p}.modelos")
            if not modelos:  # formato anterior: modelo + modelo_respaldo
                modelos = [m for m in (_secret(f"ia.{p}.modelo"), _secret(f"ia.{p}.modelo_respaldo")) if m] or base["modelos"]
            self.prov[p] = {"proveedor": p, "clave": str(_secret(f"ia.{p}.api_key", "") or ""), "url": _secret(f"ia.{p}.url", base["url"]),
                            "modelos": [str(m) for m in modelos]}
        self.cadena = [(p, m) for p in self.orden if self.prov[p]["clave"] and self.prov[p]["url"] for m in self.prov[p]["modelos"]]
        self.limite = int(_secret("ia.limite_consultas_por_equipo", 120))
        self.sin_claves = not self.cadena
        self.demo = respuestas_demo or {}

    def _pk(self, p, modelo):  # la pausa depende también de la clave: si se corrige la clave en secrets, se vuelve a probar de inmediato
        return (p, modelo, hashlib.sha1(self.prov[p]["clave"].encode()).hexdigest()[:8])

    def _k(self): return f"{st.session_state.get('_app')}|{identidad_equipo()}"
    def usadas(self): return _global()["consultas"].get(self._k(), 0)

    def estado(self):
        if self.sin_claves: return "Modo demostración (sin conexión a la IA)"
        if self.usadas() >= self.limite: return f"Límite de {self.limite} consultas alcanzado: modo demostración"
        quien = "de tu código de mentor" if str(st.session_state.get("_codigo", "")).startswith("M") else "del equipo"
        return f"Consultas {quien}: {self.usadas()}/{self.limite}"

    def proveedores(self) -> str:
        pausas = _global().get("pausas", {})
        return " → ".join(f"{'En pausa: ' if pausas.get(self._pk(p, m), 0) > time.time() else ''}{p}/{m.split('/')[-1]}" for p, m in self.cadena) or "ninguno"

    def llamar(self, mensajes, tarea, clave_demo="", json_mode=False, temperatura=0.3, max_tokens=700):
        info = {"tipo": "llamada_ia", "tarea": tarea, "entrada": mensajes[-1]["content"],
                "prompt_hash": hashlib.sha1(mensajes[0]["content"].encode()).hexdigest()[:10]}
        motivo = "demo (sin claves)"
        if not self.sin_claves:
            if self.usadas() >= self.limite:
                motivo = "demo (límite de consultas)"
            else:
                pausas = _global().setdefault("pausas", {})
                for p, modelo in self.cadena:  # orden de secrets: proveedor por proveedor y, dentro de cada uno, modelo por modelo
                    if pausas.get(self._pk(p, modelo), 0) > time.time():
                        info.setdefault("saltados", []).append(f"{p}/{modelo}"); continue
                    t0 = time.time()
                    try:
                        texto = tutear(self._post({**self.prov[p], "modelo": modelo}, mensajes, json_mode, temperatura, max_tokens))
                        g = _global()
                        with g["lock"]: g["consultas"][self._k()] = g["consultas"].get(self._k(), 0) + 1
                        info.update(modo="real", proveedor=p, modelo=modelo, latencia_s=round(time.time() - t0, 2), salida=texto)
                        registrar(info); return texto, info
                    except Exception as e:
                        cod = getattr(getattr(e, "response", None), "status_code", None)
                        if cod == 429: pausas[self._pk(p, modelo)] = time.time() + PAUSA_SATURADO
                        elif cod in (401, 403, 404): pausas[self._pk(p, modelo)] = time.time() + PAUSA_INVALIDO
                        info.setdefault("errores", []).append(f"{p}/{modelo}: {str(e)[:150]}")
                motivo = "demo (falla de conexión)"
        b = self.demo.get(tarea, {})
        texto = (b.get(str(clave_demo)) or b.get("_por_defecto") or "[Demostración] Sin respuesta preparada.") if isinstance(b, dict) else str(b)
        info.update(modo=motivo, proveedor="-", salida=texto); registrar(info)
        return texto, info

    @staticmethod
    def _claude(c, mensajes, max_tokens):
        """Claude con el SDK oficial de Anthropic. El pensamiento queda activo (no se puede apagar en los modelos actuales):
        se usa esfuerzo bajo y margen de tokens para que alcance la respuesta. Las reglas de formato JSON ya van en el prompt."""
        import anthropic  # importación aquí: si falta el paquete, solo falla este proveedor y la app pasa al siguiente
        sistema = "\n\n".join(m["content"] for m in mensajes if m["role"] == "system")
        conv = [{"role": m["role"], "content": m["content"]} for m in mensajes if m["role"] in ("user", "assistant")]
        if conv and conv[0]["role"] == "assistant":  # la conversación de A parte con el saludo del asistente
            conv.insert(0, {"role": "user", "content": "(La persona abre la conversación.)"})
        cliente = anthropic.Anthropic(api_key=c["clave"], timeout=60.0, max_retries=1)
        pedido = dict(model=c["modelo"], max_tokens=max_tokens + 4000, system=sistema, messages=conv,
                      output_config={"effort": str(_secret("ia.anthropic.esfuerzo", "low"))})
        r = None
        if c["modelo"] in ("claude-opus-5-5", "claude-sonnet-5-5"):  # Haiku no tiene respaldo ante rechazos
            try:  # si Claude declina por seguridad, la API reintenta sola con el modelo de respaldo adecuado
                r = cliente.beta.messages.create(**pedido, betas=["server-side-fallback-2026-07-01"], fallbacks="default")
            except TypeError:  # versión del SDK sin ese parámetro: se pide sin respaldo
                r = None
        if r is None:
            r = cliente.messages.create(**pedido)
        if r.stop_reason == "refusal":
            raise ValueError("Claude no respondió esta consulta (rechazo por seguridad)")
        texto = "".join(b.text for b in r.content if getattr(b, "type", "") == "text").strip()
        if not texto: raise ValueError(f"Claude devolvió una respuesta vacía ({r.stop_reason})")
        return texto

    @staticmethod
    def _post(c, mensajes, json_mode, temperatura, max_tokens):
        if c.get("proveedor") == "anthropic":
            return IA._claude(c, mensajes, max_tokens)
        cuerpo = {"model": c["modelo"], "messages": mensajes, "temperature": temperatura, "max_tokens": max_tokens}
        if "gpt-oss" in str(c["modelo"]):  # modelos que razonan antes de responder: razonamiento corto y margen de tokens
            # "medium" respeta mejor el TONO de la planilla; "low" gasta menos. Se elige en secrets: [ia] razonamiento
            cuerpo.update(reasoning_effort=str(_secret("ia.razonamiento", "medium")), max_tokens=max_tokens + 2000)
        if json_mode: cuerpo["response_format"] = {"type": "json_object"}
        for i in range(2):
            r = requests.post(c["url"], json=cuerpo, timeout=40, headers={"Authorization": f"Bearer {c['clave']}"})
            if r.status_code == 429 and i == 0:  # saturado: reintenta solo si la espera es corta; si no, pasa al siguiente modelo
                try: espera = float(r.headers.get("retry-after", 2))
                except ValueError: espera = 2
                if espera <= 3: time.sleep(max(espera, 0.5)); continue
            r.raise_for_status()
            texto = (r.json()["choices"][0]["message"].get("content") or "").strip()
            if not texto: raise ValueError("la IA devolvió una respuesta vacía")
            return texto
        r.raise_for_status()

```

### pie · linea 545

```python
def pie(ia: IA):
    with st.sidebar:
        st.divider(); st.caption(ia.estado())
        st.caption(f"Modelos de IA en orden de uso: {ia.proveedores()}")
        if st.session_state.get("_aviso_reg"): st.warning(st.session_state["_aviso_reg"])
        df = registro_equipo()
        st.download_button("Descargar registro del equipo", df.to_csv(index=False).encode("utf-8"),
                           file_name=f"registro_{st.session_state.get('_app')}_{st.session_state.get('_equipo')}.csv",
                           mime="text/csv", width="stretch", disabled=df.empty)
        g = _global()
        with g["lock"]:
            respaldo = {c: dict(g["equipos"].get(_clave_estado(c), {})) for c in ("bandeja", "decisiones")}
        st.download_button("Descargar respaldo del estado", json.dumps({"app": st.session_state.get("_app"), "equipo_codigo": identidad_equipo(),
                           "estado": respaldo, "eventos_sin_confirmar": list(st.session_state.get("_eventos_pendientes", {}).values()),
                           "casos_sin_confirmar": st.session_state.get("_casos_por_guardar", {})}, ensure_ascii=False, indent=2),
                           file_name="respaldo_estado.json", mime="application/json", width="stretch")
        pendientes = bool(st.session_state.get("_casos_por_guardar") or st.session_state.get("_eventos_pendientes"))
        if pendientes: st.warning("Hay cambios sin confirmar. Guárdelos antes de salir.")
        if st.session_state.get("_eventos_pendientes") and not st.session_state.get("_casos_por_guardar"):
            if st.button("Reintentar cambios pendientes", width="stretch"):
                for fila in list(st.session_state["_eventos_pendientes"].values()):
                    guardar_elemento(fila[4], fila[5], json.loads(fila[6]))
                st.rerun()
        st.button("Salir", width="stretch", disabled=pendientes, on_click=cerrar_sesion)
    st.markdown('<div class="pie-nota">Prototipo con datos ficticios · Hackathon IA Aplicada · Congreso Social UC 2026 · '
                'La decisión final siempre es de una persona.</div>', unsafe_allow_html=True)

```

## comun/persistencia.py

Archivo nuevo completo, desde linea 1.

```python
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

```

## comun/validaciones.py

Archivo nuevo completo, desde linea 1.

```python
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

```

## desafio1/app_a_conectamayor.py

### Import · linea 3

```python
import json, re, sys, uuid

```

### Import · linea 11

```python
import validaciones as V

```

### AugAssign · linea 85

```python
_MALTRATO += [
    r"\b(me|le) (dejaron|dejan|dej[oó]) sin (comida|agua|alimentos|cuidados|remedios)\b",
    r"\bno (me|le) permiten (comer|salir|pedir ayuda)\b",
    r"\b(me|le) (obliga|obligan|oblig[oó]) a (firmar|entregar (mi|su|la) (clave|tarjeta|pensi[oó]n))\b",
    r"\b(me|le) (esconde|esconden|retiene|retienen) (mis |sus |los |las )?(remedios|medicamentos|tarjetas)\b",
    r"\b(me|le|la|lo) (dejaron|dejan) sol[oa].{0,50}\b(no (puedo|puede) (cocinar|comer|moverme|moverse)|sin (comida|cuidados))\b",
]

```

### AugAssign · linea 92

```python
_EMERGENCIA += [
    r"\b(me ca[ií]|se cay[oó]).{0,60}\b(sigo|sigue|estoy|est[aá]) (tirad[oa]|en el suelo)\b",
    r"\b(no puedo|no puede) (hablar|mover un brazo|mover una pierna) de repente\b",
    r"\b(quiero|quiere|pienso en) (quitarme|quitarse) la vida\b",
]

```

### Assign · linea 144

```python
bandeja = list(N.estado_equipo("bandeja").values())

```

### reiniciar · linea 151

```python
def reiniciar():
    ss.hist, ss.turno, ss.clasif, ss.ultimo_info = [], 0, None, {}
    for clave in ("_caso_id", "_respuesta_enviada", "_pendiente", "_aviso_val"):
        ss.pop(clave, None)
    ss["_n_conv"] = ss.get("_n_conv", 0) + 1

```

### nuevo_caso · linea 157

```python
def nuevo_caso(pid, c, origen):
    cid = ss.setdefault("_caso_id", "C-" + uuid.uuid4().hex)
    existente = next((b for b in bandeja if b["caso"] == cid), None)
    if existente and origen == "conversación":
        return cid  # el protocolo ya creó el caso de esta conversación
    caso = {"caso": cid, "persona": pid, "conversa": "Persona mayor" if ss.quien == list(QUIEN)[0] else "Apoyo cercano", "origen": origen,
                    "urgencia": c.get("urgencia", "-"), "necesidades": ", ".join(c.get("necesidades", [])), "servicio_sugerido": c.get("servicio_sugerido", "-"),
                    "resumen_ia": c.get("resumen", ""), "conversacion": conv_txt(ss.hist), "decision": "Pendiente"}
    if existente:
        caso["decision"] = existente["decision"]
        caso["nota_decision"] = existente.get("nota_decision", "")
        # Una señal posterior de maltrato no baja una emergencia existente.
        if existente["urgencia"] == "CRISIS": caso["urgencia"] = "CRISIS"
    if not N.guardar_elemento("bandeja", cid, caso):
        ss.setdefault("_casos_por_guardar", {})[cid] = caso
        return None
    ss.setdefault("_casos_por_guardar", {}).pop(cid, None)
    if existente: existente.update(caso)
    else: bandeja.append(caso)
    N.registrar({"tipo": "caso_creado", "caso": cid, "origen": origen, "urgencia": c.get("urgencia")})
    return cid

```

### inseguro · linea 180

```python
def inseguro(texto):
    return bool(DIAGNOSTICO.search(texto) or V.DIAGNOSTICO.search(texto) or MEDICAMENTO.search(texto) or V.MEDICACION.search(texto) or EDADISMO.search(texto) or V.EDADISMO.search(texto))

```

### Pantalla principal completa · linea 194

```python
N.encabezado(cfg["titulo_app"], cfg["texto_bienvenida"],
             [f"{st.session_state.get('_equipo')}", f"Usuario: {N.corto(cfg.get('usuario'), 70)}", f"Hasta {MAX_TURNOS} mensajes", f"Letra {cfg.get('tamano_letra', 'grande')}"])
N.aviso_ia()
if ss.get("_casos_por_guardar"):
    st.error("Hay casos pendientes de guardar. Mantenga esta sesión abierta hasta confirmarlos.")
    st.download_button("Respaldar casos sin confirmar", json.dumps(list(ss["_casos_por_guardar"].values()), ensure_ascii=False, indent=2),
                       file_name="casos_sin_confirmar.json", mime="application/json")
    if st.button("Reintentar guardado de casos"):
        for cid, caso in list(ss["_casos_por_guardar"].items()):
            if N.guardar_elemento("bandeja", cid, caso): ss["_casos_por_guardar"].pop(cid)
        st.rerun()
pend = sum(b["decision"] == "Pendiente" for b in bandeja)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Casos en la bandeja", len(bandeja))
m2.metric("Pendientes de revisión", pend)
m3.metric("Emergencias o maltrato", sum(b["urgencia"] in ("CRISIS", "MALTRATO") for b in bandeja))
m4.metric("Consultas a la IA", f"{ia.usadas()} de {ia.limite}")

t1, t2 = N.pestanas(["1 · Conversación (vista de la persona)", "2 · Bandeja de la red de apoyo"], "a")
with t1:
    chat, lado = st.columns([1.7, 1], gap="large")
    with lado:
        with st.container(border=True):
            st.markdown("**Simular como** · solo para pruebas del equipo")
            opciones = ["(escribir libremente)"] + [f"{r.id_persona} · {r.nombre_ficticio}, {r.edad} años ({r.quien_conversa.lower()})" for r in personas.itertuples()]
            sel = st.selectbox("Perfil ficticio", opciones, label_visibility="collapsed")
            pid = sel.split(" · ")[0] if sel.startswith("P") else "libre"
            if pid != "libre":
                st.markdown(f'<div class="quote">{N.md(personas[personas.id_persona == pid].iloc[0]["contexto_para_simular"])}</div>', unsafe_allow_html=True)
                st.caption("Este contexto es para que actúes el papel: no se envía a la IA.")
        if ss.hist:
            st.progress(min(ss.turno / MAX_TURNOS, 1.0), text=f"Mensajes de la persona: {min(ss.turno, MAX_TURNOS)} de {MAX_TURNOS}")
            dichos = [m["content"] for m in ss.hist if m["role"] == "assistant"]
            st.metric("Lectura fácil · palabras por frase de la IA", palabras_por_frase(dichos), help="Referencia de lectura fácil: 15 palabras o menos por frase.")
        N.tarjeta("Qué hace esta conversación",
                  "Escucha, orienta hacia <b>personas y servicios</b> del catálogo y, si la persona quiere, deja el caso en la bandeja de la red de apoyo. "
                  "<b>No da indicaciones de salud</b> y <b>la persona decide</b>.", "gray")
    with chat:
        if not ss.hist:
            zona = st.empty()
            with zona.container(border=True):
                st.markdown("#### Antes de empezar")
                ss.quien = st.radio("¿Quién conversa?", list(QUIEN), horizontal=True, key=f"quien_{ss.get('_n_conv', 0)}")
                ok = st.checkbox(cfg["texto_consentimiento"], key=f"consent_{ss.get('_n_conv', 0)}")
                if st.button(cfg["texto_boton"], type="primary", width="stretch"):
                    if not ok: st.warning("Para comenzar hay que aceptar el aviso de consentimiento.")
                    else:
                        N.registrar({"tipo": "consentimiento", "persona": pid, "conversa": ss.quien})
                        ss.hist = [{"role": "assistant", "content": cfg["mensaje_inicial"]}]
            if ss.hist: zona.empty()
        for m in ss.hist: st.chat_message(m["role"], avatar=AVATAR[m["role"]]).markdown(m["content"])
        if ss.hist and ss.hist[-1]["role"] == "assistant": escuchar(ss.hist[-1]["content"])
        if ss.ultimo_info: N.aviso_si_demo(ss.ultimo_info)
        if ss.get("_aviso_val"): st.caption(ss.pop("_aviso_val"))
        if ss.hist and ss.clasif is None:
            if RAPIDAS and ss.turno == 0:
                st.caption("Puede tocar una frase o escribir con sus palabras:")
                cols = st.columns(min(len(RAPIDAS), 2))
                for i, r in enumerate(RAPIDAS): cols[i % len(cols)].button(r, key=f"rap_{i}", width="stretch", on_click=enviar, args=(r,))
            msg = st.chat_input("Escriba aquí…") or ss.pop("_pendiente", None)
            if msg:
                ss.hist.append({"role": "user", "content": msg}); ss.turno += 1; ss.ultimo_info = {}
                tipo = protocolo(msg)
                if tipo:  # [fijo] protocolo fijo: no pasa por la IA
                    activar_protocolo(tipo, msg, pid, "protocolo fijo")
                elif ss.turno > MAX_TURNOS:
                    ss.hist.append({"role": "assistant", "content": "Llegamos al final de la conversación. Presione **Terminar** para ver su resumen."})
                else:
                    sistema = REGLAS.format(quien=QUIEN[ss.quien], catalogo=S.texto(catalogo)) + "\n\n" + N.personalizacion(cfg)
                    with st.spinner("ConectaMayor está escribiendo…"):
                        texto, info = ia.llamar([{"role": "system", "content": sistema}] + ss.hist, "chat", f"{pid}_{ss.turno}", temperatura=0.5, max_tokens=350)
                    marca = MARCA.search(texto)
                    if marca:  # [fijo] la IA reconoció una señal grave dicha de forma indirecta: se aplica el mismo protocolo fijo
                        activar_protocolo("CRISIS" if marca.group(1) == "EMERGENCIA" else "MALTRATO", msg, pid, "señal indirecta reconocida por la IA")
                        ss.ultimo_info = info
                    else:
                        if DIAGNOSTICO.search(texto) or V.DIAGNOSTICO.search(texto) or MEDICAMENTO.search(texto) or V.MEDICACION.search(texto):  # [fijo] validación
                            N.registrar({"tipo": "validacion", "tarea": "chat", "salida": texto, "nota": "indicación de salud bloqueada"})
                            texto = SIN_SALUD
                            ss["_aviso_val"] = "La validación reemplazó la respuesta de la IA porque daba indicaciones de salud o medicamentos."
                        elif EDADISMO.search(texto) or V.EDADISMO.search(texto):
                            N.registrar({"tipo": "validacion", "tarea": "chat", "salida": texto, "nota": "lenguaje infantilizante"})
                            texto = "Estoy aquí para orientarle con respeto. ¿Qué apoyo necesita?"
                            ss["_aviso_val"] = "La validación reemplazó una respuesta con lenguaje infantilizante (queda registrado)."
                        ss.hist.append({"role": "assistant", "content": texto}); ss.ultimo_info = info
                st.rerun()
            if len(ss.hist) > 1 and st.button("Terminar conversación"):
                solo = " ".join(m["content"] for m in ss.hist if m["role"] == "user")
                DEMO["clasificar"]["actual"] = json.dumps(clasif_local(solo), ensure_ascii=False)
                with st.spinner("Preparando su resumen…"):
                    texto, info = ia.llamar([{"role": "system", "content": "Respondes solo JSON válido. " + N.personalizacion(cfg)},
                                             {"role": "user", "content": CLASIFICAR.format(categorias=", ".join(CATEGORIAS), catalogo=S.texto(catalogo), conv=conv_txt(ss.hist))}],
                                            "clasificar", "actual", json_mode=True, temperatura=0)
                original = N.extraer_json(texto)
                c = V.normalizar_clasificacion(original, clasif_local(solo), CATEGORIAS, SERV, inseguro)
                if c != original:
                    N.registrar({"tipo": "validacion", "tarea": "clasificar", "nota": "JSON normalizado o reemplazado por clasificación local"})
                    ss["_aviso_val"] = "El resumen fue revisado; se corrigió su estructura o se usó la clasificación local segura."
                ss.clasif = c; ss.ultimo_info = info; st.rerun()
        if ss.clasif:
            c = ss.clasif
            pasos = "".join(f"<li>{N.md(p)}</li>" for p in c["hoja_de_ruta"])
            N.tarjeta("Su hoja de ruta", f"<ol style='margin:0;padding-left:1.3em'>{pasos}</ol>", "ok")
            escuchar(" ".join(c["hoja_de_ruta"]))
            if c["servicio_sugerido"] in SERV:
                N.tarjeta(f"Apoyo que podría servirle · {SERV[c['servicio_sugerido']]}", "<b>Cómo acceder:</b> " + N.md(ACCESO.get(c["servicio_sugerido"], "")), "info")
            with st.container(border=True):
                q = st.radio("¿Quiere que **una persona** de la red de apoyo se comunique con usted? Es voluntario.", ["Sí, quiero que me contacten", "No, gracias"], index=None)
                util = st.select_slider("¿Le sirvió esta conversación?", ["Nada", "Poco", "Algo", "Mucho"], value="Algo")
                if st.button("Enviar respuesta", type="primary", disabled=ss.get("_respuesta_enviada", False)):
                    if not q: st.warning("Seleccione si quiere que le contacten.")
                    else:
                        cid = nuevo_caso(pid, c, "conversación") if q.startswith("Sí") else None
                        if not q.startswith("Sí") or cid:
                            ss["_respuesta_enviada"] = True
                            N.registrar({"tipo": "decision_persona", "decision": q, "utilidad": util, "caso": cid})
                            st.rerun()
                if ss.get("_respuesta_enviada"):
                    st.success("Respuesta registrada. En esta demostración no se contacta a nadie real.")
            st.button("Nueva conversación", on_click=reiniciar, disabled=bool(ss.get("_casos_por_guardar")))
with t2:
    st.caption("Aquí llegan los casos. **La IA no contacta a nadie:** una persona de la red de apoyo revisa y decide. La bandeja la comparten todos los integrantes del equipo.")
    if not bandeja:
        N.tarjeta("La bandeja está vacía", "Cuando alguien termine una conversación y pida contacto, o se active un protocolo fijo, el caso aparecerá aquí.", "gray")
    else:
        PRIO = {"CRISIS": 0, "MALTRATO": 1, "alta": 2, "media": 3, "baja": 4}
        ordenados = sorted(bandeja, key=lambda x: (x["decision"] != "Pendiente", PRIO.get(x["urgencia"], 5), x["caso"]))
        df = pd.DataFrame(ordenados)
        df["Urgencia"] = df.urgencia.map(lambda u: URG.get(u, (u, ""))[0])
        df["Servicio"] = df.servicio_sugerido.map(lambda s: SERV.get(s, "—"))
        st.dataframe(df[["caso", "persona", "conversa", "origen", "Urgencia", "necesidades", "Servicio", "decision"]].rename(columns={
            "caso": "Caso", "persona": "Persona", "conversa": "Quién conversó", "origen": "Origen", "necesidades": "Necesidades", "decision": "Decisión"}),
            hide_index=True, width="stretch")
        st.caption("Orden: pendientes primero y, dentro de ellos, emergencias y maltrato.")
        cid = st.selectbox("Caso a revisar", [b["caso"] for b in ordenados],
                           format_func=lambda c: next(f"{x['caso']} · {URG.get(x['urgencia'], (x['urgencia'],))[0]}" for x in bandeja if x["caso"] == c))
        b = next(x for x in bandeja if x["caso"] == cid)
        etiqueta, color = URG.get(b["urgencia"], (b["urgencia"], "gray"))
        N.tarjeta(f"{cid} · {b['persona']} · {b['conversa']} · {b['origen']}",
                  N.badge(etiqueta, color) + "".join(N.badge(n.strip(), "teal") for n in b["necesidades"].split(",") if n.strip()) +
                  f"<br><b>Servicio sugerido:</b> {N.md(SERV.get(b['servicio_sugerido'], 'ninguno'))}<br><b>Resumen de la IA (verifícalo):</b> {N.md(b['resumen_ia'])}",
                  "bad" if b["urgencia"] in ("CRISIS", "MALTRATO") else "warn" if b["urgencia"] == "alta" else "info")
        if b["urgencia"] == "MALTRATO":
            st.warning("Posible maltrato: antes de contactar, piensa si el contacto podría ponerla en riesgo (por ejemplo, si quien maltrata contesta el teléfono).")
        with st.expander("Conversación completa"): st.text(b["conversacion"])
        with st.container(border=True):
            dec = st.radio("Decisión humana (obligatoria)", ["Llamar hoy", "Visitar esta semana", "Derivar a otro servicio", "Cerrar sin acción"],
                           index=None, key=f"d_{cid}", horizontal=True)
            nota = st.text_input("Nota (opcional)", key=f"n_{cid}")
            if st.button("Registrar decisión", type="primary"):
                if not dec: st.warning("Elige una decisión: la IA no decide por ti.")
                else:
                    actualizado = {**b, "decision": dec, "nota_decision": nota}
                    if N.guardar_elemento("bandeja", cid, actualizado):
                        N.registrar({"tipo": "decision_humana", "caso": cid, "decision": dec, "nota": nota})
                        ss["_flash"] = f"{cid}: decisión registrada · **{dec}**"; st.rerun()
        st.download_button("Respaldar bandeja completa", json.dumps(bandeja, ensure_ascii=False, indent=2),
                           file_name="bandeja_conectamayor.json", mime="application/json")
        if ss.get("_flash"): st.success(ss.pop("_flash"))
N.pie(ia)

```

## desafio1/app_b_redcuida.py

### Import · linea 12

```python
import validaciones as V

```

### validar · linea 115

```python
def validar(texto):
    problemas = []
    codigos = set(re.findall(r"\[([A-Z]{1,3}\d{1,3})\]", texto))
    malos = sorted(c for c in codigos if c not in set(catalogo.id_servicio))
    if malos: problemas.append(f"cita servicios que no existen en el catálogo: {', '.join(malos)}")
    if not codigos: problemas.append("no cita ningún servicio del catálogo con su código")
    if DIAGNOSTICO.search(texto): problemas.append("nombra enfermedades o diagnósticos")
    if EDADISMO.search(texto) or V.EDADISMO.search(texto): problemas.append("usa lenguaje infantilizante o etiquetas")
    if V.MEDICACION.search(texto): problemas.append("incluye posibles indicaciones de medicamentos")
    if not re.search(r"semana\s+\d", texto, re.I): problemas.append("no cita la semana de los registros")
    return problemas

```

### Assign · linea 147

```python
decisiones_completas = N.estado_equipo("decisiones")

```

### Assign · linea 148

```python
decisiones = {pid: d["decision"] for pid, d in decisiones_completas.items()}

```

### Pantalla principal completa · linea 153

```python
N.encabezado(cfg["titulo_app"], cfg["texto_bienvenida"],
             [f"{st.session_state.get('_equipo')}", f"Usuario: {N.corto(cfg.get('usuario'), 70)}", f"Cupo semanal: {CUPO} personas"])
N.aviso_ia()
n_alertas = int((cola.alerta != "").sum())
hechas = int((cola.decision != "Pendiente").sum())
m1, m2, m3, m4 = st.columns(4)
m1.metric("En la lista de la semana", len(cola), help=f"{n_alertas} alertas + {len(cola) - n_alertas} por orden, de {n_total} personas acompañadas (ficticias)")
m2.metric("Alertas (no esperan cupo)", n_alertas)
m3.metric("Decisiones registradas", f"{hechas} de {len(cola)}")
m4.metric("Consultas a la IA", f"{ia.usadas()} de {ia.limite}")

t1, t2, t3 = N.pestanas(["1 · Lista de la semana", "2 · Ficha y decisión", "3 · ¿A quién no estamos viendo?"], "b")
with t1:
    st.markdown(N.badge("Se compara a cada persona con sus propias semanas anteriores", "teal") + N.badge("El orden no usa sexo, edad ni sector", "teal") +
                N.badge("El puntaje no es un diagnóstico", "gray") + N.badge("Solo lee las casillas marcadas, no las notas", "amber"), unsafe_allow_html=True)
    if n_alertas:
        N.tarjeta(f"{n_alertas} alerta(s): caída o sospecha de maltrato en las últimas {VENTANA} semanas",
                  "Estas personas aparecen primero y <b>no ocupan cupo</b>: requieren aplicar el protocolo del equipo, no esperar la cola.", "bad")
    f1, f2 = st.columns([3, 1], vertical_alignment="bottom")
    fs = f1.pills("Sector", sorted(cola.sector.unique()), selection_mode="multi")
    solo = f2.toggle("Solo pendientes")
    vista = cola[cola.sector.isin(fs) if fs else cola.sector.notna()]
    if solo: vista = vista[vista.decision == "Pendiente"]
    st.dataframe(vista.assign(Alerta=vista.alerta)[
        ["n", "id_persona", "nombre_ficticio", "sector", "Alerta", "por_que", "puntaje", "decision"]].rename(columns={
        "n": "N°", "id_persona": "Persona", "nombre_ficticio": "Nombre", "sector": "Sector", "por_que": "¿Por qué aparece?", "puntaje": "Puntaje", "decision": "Decisión"}),
        hide_index=True, width="stretch", height=460,
        column_config={"N°": st.column_config.NumberColumn(width="small"), "¿Por qué aparece?": st.column_config.TextColumn(width="large")})
    st.caption(f"Puntaje = suma de (peso de la planilla × veces que se marcó la señal en las últimas {VENTANA} semanas; ×1,5 si es nueva para esa persona) "
               "+ semanas sin contacto + vive sola. Cambien los pesos en su planilla y vean cómo cambia la lista.")

with t2:
    NUM = dict(zip(cola.id_persona, cola.n))
    sel = st.selectbox("Persona", list(cola.id_persona), key="per_sel", format_func=lambda i: f"N° {NUM.get(i, '?')} · {i} · {cola.set_index('id_persona').nombre_ficticio[i]}")
    f = cola[cola.id_persona == sel].iloc[0]
    izq, der = st.columns([1, 1.35], gap="large")
    with izq:
        N.tarjeta(f"{sel} · {f['nombre_ficticio']}, {int(f['edad'])} años",
                  N.badge(f["sector"], "teal") + N.badge(f["autonomia"], "gray") + (N.badge("Vive sola", "amber") if f["vive_sola"] else "") +
                  (N.badge("Sin teléfono", "amber") if not f["tiene_telefono"] else "") + N.badge(f"Cuida: {f['cuidador_principal']}", "gray") +
                  (f"<br>{N.badge('Alerta: ' + f['alerta'], 'red')}" if f["alerta"] else "") +
                  "<br>Decisión: " + N.badge(decisiones.get(sel, "Pendiente"), "gray" if sel not in decisiones else "green"), "bad" if f["alerta"] else "info")
        d = contactos[contactos.id_persona == sel]
        a1, a2 = st.columns(2)
        a1.metric("Contactos logrados (12 sem.)", f"{int(d.logrado.sum())} de {len(d)}")
        a2.metric("Semanas sin contacto logrado", int(f["semanas_sin_contacto"]))
        st.markdown("**¿Por qué aparece?** " + "".join(N.badge(x.strip(), "amber") for x in f["por_que"].split(";") if x.strip()), unsafe_allow_html=True)
        sem = pd.DataFrame({"semana": range(1, G.SEMANAS + 1)})
        sem["Logrados"] = sem.semana.map(d[d.logrado == 1].groupby("semana").size()).fillna(0)
        sem["No logrados"] = sem.semana.map(d[d.logrado == 0].groupby("semana").size()).fillna(0)
        sem["Señales marcadas"] = sem.semana.map(d.groupby("semana")[G.SENALES].sum().sum(axis=1)).fillna(0)
        largo = sem.melt("semana", var_name="Medida", value_name="Cantidad")
        st.altair_chart(alt.Chart(largo).mark_bar(cornerRadiusEnd=3).encode(
            x=alt.X("semana:O", title="Semana"), y=alt.Y("Cantidad:Q", title=None), xOffset="Medida:N",
            color=alt.Color("Medida:N", scale=alt.Scale(domain=["Logrados", "No logrados", "Señales marcadas"], range=["#0A2B5C", "#A3ABB8", "#D9A400"]),
                            legend=alt.Legend(orient="top", title=None)), tooltip=["semana", "Medida", "Cantidad"]).properties(height=170), use_container_width=True)
        with st.expander("Bitácora completa (12 semanas)"):
            st.dataframe(d[["semana", "tipo", "registrado_por", "logrado", "nota"]].rename(columns={
                "semana": "Sem.", "tipo": "Tipo", "registrado_por": "Quién", "logrado": "Logrado", "nota": "Nota"}).sort_values("Sem.", ascending=False),
                hide_index=True, width="stretch", column_config={"Nota": st.column_config.TextColumn(width="large")})
    with der:
        clave = f"prop_{sel}"
        if st.button(cfg["texto_boton"], type="primary", width="stretch") and not (
                N.repetido(f"ficha|{sel}") and clave in st.session_state):
            sistema = REGLAS + "\n\n" + N.personalizacion(cfg)
            pet = PETICION.format(perfil=perfil_txt(f), factores=f["por_que"] or "(ninguna)", bitacora=bitacora(sel), catalogo=S.texto(catalogo))
            with st.spinner("La IA está leyendo los registros…"):
                texto, info = ia.llamar([{"role": "system", "content": sistema}, {"role": "user", "content": pet}], "ficha", sel)
            st.session_state[clave] = (texto, info)
            st.session_state.pop(f"ta_{sel}", None)
        if clave not in st.session_state:
            N.tarjeta("Propuesta de la IA", "Presiona el botón para que la IA lea las notas de las últimas semanas y prepare el próximo contacto: "
                      "qué muestran los registros, qué apoyos del catálogo podrían servir y qué hacer en la próxima visita o llamada.", "gray")
        else:
            texto, info = st.session_state[clave]
            N.aviso_si_demo(info)
            with st.expander("Revisar y editar el texto antes de usarlo", expanded=bool(validar(texto))):
                texto = st.text_area("Propuesta de la IA", texto, height=260, key=f"ta_{sel}", label_visibility="collapsed")
            prob = validar(texto)
            if prob:
                st.error("La validación detectó problemas. Corrige el texto antes de usarlo: " + "; ".join(prob))
            else:
                st.markdown(N.badge("Validación superada: cita registros y servicios del catálogo, sin diagnósticos", "green"), unsafe_allow_html=True)
            sec = secciones(texto)
            if sec and not prob:
                cods = [c for c in dict.fromkeys(re.findall(r"\[([A-Z]{1,3}\d{1,3})\]", sec[1])) if c in set(catalogo.id_servicio)]
                acceso = "".join(f"<br>{N.badge(c, 'teal')} {N.md(r.como_acceder)}" for c in cods for r in catalogo[catalogo.id_servicio == c].itertuples())
                N.tarjeta("1 · Lo que muestran los registros", N.md(sec[0]), "info")
                N.tarjeta("2 · Apoyos posibles", N.md(sec[1]) + (f"<br><br><b>Cómo se accede:</b>{acceso}" if acceso else ""), "ok")
                N.tarjeta("3 · Sugerencia para el próximo contacto", N.md(sec[2]), "warn" if prob else "ok")
            with st.container(border=True):
                st.markdown("#### Decisión humana (obligatoria)")
                dec = st.radio("¿Qué decides?", OPCIONES, index=None, key=f"dec_{sel}", horizontal=True)
                util = st.select_slider("¿La propuesta te ahorró trabajo?", ["Nada", "Poco", "Algo", "Mucho"], value="Algo", key=f"ut_{sel}")
                nota = st.text_input("Nota (opcional)", key=f"nota_{sel}")
                if st.button("Registrar decisión", width="stretch"):
                    problemas = validar(st.session_state.get(f"ta_{sel}", texto))
                    if problemas:
                        st.error("Corrige la propuesta antes de registrarla: " + "; ".join(problemas))
                        N.registrar({"tipo": "validacion", "tarea": "ficha", "id_persona": sel, "nota": "; ".join(problemas)})
                    elif not dec: st.warning("Elige una decisión: la IA no decide por ti.")
                    else:
                        datos = {"decision": dec, "utilidad": util, "nota": nota, "salida": texto}
                        if N.guardar_elemento("decisiones", sel, datos):
                            N.registrar({"tipo": "decision_humana", "tarea": "ficha", "id_persona": sel, **datos})
                            st.session_state["_flash"] = f"Decisión registrada para {sel}: **{dec}**"
                            st.rerun()
                if st.session_state.get("_flash"): st.success(st.session_state.pop("_flash"))

with t3:
    st.markdown("El equipo solo ve lo que alguien registra. Quien vive lejos o no tiene teléfono **tiene menos contactos y por lo tanto menos señales**, "
                "aunque le pase lo mismo. Aquí se ve **a quién incluye la lista** y **qué parte de las personas a las que realmente les está cambiando algo "
                "detecta**. Cambien los pesos o el cupo en su planilla y comparen.")
    grupo = st.radio("Comparar por", list(GRUPOS.values()), horizontal=True)
    d = equidad[equidad.Grupo == (grupo or "Sector")]
    largo = d.melt(id_vars=["Valor", "Personas"], value_vars=["En la lista (%)", "Cambios reales detectados (%)"], var_name="Medida", value_name="Porcentaje")
    base = alt.Chart(largo).encode(
        y=alt.Y("Valor:N", title=None, sort=list(d.Valor)), yOffset=alt.YOffset("Medida:N", sort=["En la lista (%)", "Cambios reales detectados (%)"]),
        x=alt.X("Porcentaje:Q", title="% del grupo", scale=alt.Scale(domain=[0, 100])),
        color=alt.Color("Medida:N", scale=alt.Scale(domain=["En la lista (%)", "Cambios reales detectados (%)"], range=["#0A2B5C", "#D9A400"]),
                        legend=alt.Legend(orient="top", title=None)),
        tooltip=["Valor", "Medida", alt.Tooltip("Porcentaje:Q", format=".1f"), "Personas"])
    graf = (base.mark_bar(cornerRadiusEnd=4) + base.mark_text(align="left", dx=4, fontSize=12, color="#0F172A").encode(text=alt.Text("Porcentaje:Q", format=".1f")))
    st.altair_chart(graf.properties(height=alt.Step(24)).configure_axis(grid=False, labelFontSize=13).configure_view(stroke=None), use_container_width=True)
    st.dataframe(d[["Valor", "Personas", "Contactos por persona"]].rename(columns={"Valor": grupo}), hide_index=True)
    if len(d) >= 2 and d["Cambios reales detectados (%)"].notna().sum() >= 2:
        dd = d.dropna(subset=["Cambios reales detectados (%)"])
        alto, bajo = dd.loc[dd["Cambios reales detectados (%)"].idxmax()], dd.loc[dd["Cambios reales detectados (%)"].idxmin()]
        N.tarjeta("Para discutir en el equipo",
                  f"De las personas a las que realmente les está cambiando algo, la lista detecta al <b>{alto['Cambios reales detectados (%)']:.0f}%</b> "
                  f"en «{N.md(alto.Valor)}» y al <b>{bajo['Cambios reales detectados (%)']:.0f}%</b> en «{N.md(bajo.Valor)}». "
                  "¿Es un problema de los pesos, de los registros o de cómo trabaja el equipo en terreno?", "warn")
    st.markdown("**¿Qué tipo de cambios detecta la lista?**")
    st.dataframe(deteccion.assign(**{"Detectadas (%)": (100 * deteccion.Detectadas / deteccion.Personas).round(0)}).rename(columns={"trayectoria": "Lo que realmente le pasa"}),
                 hide_index=True)
    st.caption("Datos sintéticos: lo que «realmente le pasa» a cada persona solo se conoce porque los datos son inventados. "
               "Sirve para diseñar criterios, no para evaluar personas.")
N.pie(ia)

```
