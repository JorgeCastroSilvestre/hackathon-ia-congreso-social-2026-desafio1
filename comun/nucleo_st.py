"""
🔒 NÚCLEO COMÚN · Plantillas Hackathon IA Congreso Social UC 2026 · Desafío 2
Misma lógica que las plantillas del Desafío 3 (G. Pinto): app pública + código y clave de
equipo + planilla de Google por equipo (pestaña `config` con campos + pestaña de extras).

Los equipos NO editan este código. Protecciones fijas:
  · aviso de uso de IA                 · código/clave de equipo y clave de IA ocultos (secrets)
  · registro de consultas y respuestas · límite de consultas por equipo
  · reglas fijas en los prompts        · validación de respuestas · modo demostración
"""
from __future__ import annotations
import datetime, hashlib, io, json, os, re, threading, time
from pathlib import Path
import pandas as pd
import requests
import base64
import streamlit as st

AVISO_IA = ("⚠️ **Esta herramienta usa inteligencia artificial.** Puede equivocarse y **no reemplaza el criterio "
            "de una persona**: la decisión final siempre es humana. Lo que se consulta y responde queda registrado "
            "para la revisión de la hackathon. Prototipo con datos ficticios.")
AVISO_DEMO = ("Se muestra una respuesta de demostración: la IA no respondió. Esperen un minuto y prueben de nuevo; "
              "si persiste, avisen a su mentor.")
# Proveedores compatibles con la API de OpenAI. Para sumar otro (por ejemplo, si la organización consigue una nueva clave)
# basta con agregarlo en secrets: [ia.<nombre>] api_key, modelos = [...] y, si no está en esta lista, url = ".../chat/completions".
PROVEEDORES = {
    "anthropic":  {"url": "sdk", "modelos": ["claude-haiku-5-5"]},   # Claude: usa el SDK oficial de Anthropic (no la URL)
    "groq":       {"url": "https://api.groq.com/openai/v1/chat/completions", "modelos": ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]},
    "mistral":    {"url": "https://api.mistral.ai/v1/chat/completions", "modelos": ["mistral-small-latest", "ministral-8b-latest"]},
    "openai":     {"url": "https://api.openai.com/v1/chat/completions", "modelos": ["gpt-4o-mini"]},
    "gemini":     {"url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "modelos": ["gemini-2.5-flash"]},
    "openrouter": {"url": "https://openrouter.ai/api/v1/chat/completions", "modelos": ["openai/gpt-oss-120b"]},
    "cerebras":   {"url": "https://api.cerebras.ai/v1/chat/completions", "modelos": ["gpt-oss-120b"]},
    "together":   {"url": "https://api.together.xyz/v1/chat/completions", "modelos": ["openai/gpt-oss-120b"]},
    "deepseek":   {"url": "https://api.deepseek.com/chat/completions", "modelos": ["deepseek-chat"]},
}
PAUSA_SATURADO, PAUSA_INVALIDO = 45, 600   # segundos que se salta un modelo saturado (429) o con clave/modelo inválido (401/403/404)
_VOSEO = {"elegís": "eliges", "tenés": "tienes", "podés": "puedes", "querés": "quieres", "sabés": "sabes", "sentís": "sientes",
          "contás": "cuentas", "decís": "dices", "necesitás": "necesitas", "preferís": "prefieres", "decidís": "decides", "escribís": "escribes", "pedís": "pides", "estás vos": "estás tú", "vos ": "tú "}

def tutear(texto: str) -> str:
    """Corrige el voseo que a veces usan los modelos (elegís → eliges): las apps hablan en español de Chile."""
    for v, t in _VOSEO.items():
        texto = re.sub(rf"\b{v}", lambda m, t=t: t.capitalize() if m.group(0)[0].isupper() else t, texto, flags=re.I)
    return texto
REGISTRO = Path(os.environ.get("REGISTRO_IA", "registro_ia.jsonl"))

def _secret(ruta, defecto=None):
    try:
        n = st.secrets
        for p in ruta.split("."):
            n = n[p]
        return n
    except Exception:
        return defecto

@st.cache_resource
def _global():
    return {"lock": threading.Lock(), "consultas": {}, "equipos": {}}

def estado_equipo(clave: str) -> dict:
    g = _global()
    with g["lock"]:
        return g["equipos"].setdefault(f"{st.session_state.get('_app')}|{st.session_state.get('_equipo')}|{clave}", {})

# ------------------------------------------------------------------ registro
_lock = threading.Lock()
def registrar(ev: dict):
    ev = {"marca_tiempo": datetime.datetime.now().isoformat(timespec="seconds"), "app": st.session_state.get("_app"),
          "equipo": st.session_state.get("_equipo"), "planilla": st.session_state.get("_sheet_url", ""), **ev}
    with _lock:
        with open(REGISTRO, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False, default=str) + "\n")
    _copiar_central(ev)

def _copiar_central(ev):
    sid, cred = _secret("registro.sheet_id"), _secret("gcp_service_account")
    if not sid or not cred:
        return
    try:
        import gspread  # type: ignore
        if "_ws" not in st.session_state:
            st.session_state["_ws"] = gspread.service_account_from_dict(dict(cred)).open_by_key(sid).sheet1
        st.session_state["_ws"].append_row([str(ev.get(k, ""))[:45000] for k in
                                            ("marca_tiempo", "app", "equipo", "tipo", "tarea", "modo", "proveedor", "entrada", "salida", "decision", "nota")])
    except Exception as e:
        st.session_state["_aviso_reg"] = f"No se pudo copiar el registro a la planilla central: {str(e)[:80]}"

def registro_equipo() -> pd.DataFrame:
    if not REGISTRO.exists():
        return pd.DataFrame()
    filas = []
    for l in REGISTRO.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(l)
        except Exception:
            continue
        if e.get("equipo") == st.session_state.get("_equipo") and e.get("app") == st.session_state.get("_app"):
            filas.append(e)
    return pd.DataFrame(filas)

# ------------------------------------------------------------------ apariencia
_CSS = """<style>
.block-container{padding-top:1.4rem;padding-bottom:3rem;max-width:1240px}
.hero{background:linear-gradient(135deg,#0F766E 0%,#155E75 100%);border-radius:18px;padding:22px 28px 16px;margin:0 0 14px 0;box-shadow:0 6px 18px rgba(15,118,110,.18)}
.hero .h-tit{color:#fff;font-size:1.85rem;font-weight:700;line-height:1.2;margin:0 0 6px 0}
.hero .h-sub{color:#E6FFFA;font-size:1.02rem;margin:0 0 10px 0;max-width:900px}
.chip{display:inline-block;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.25);color:#fff;border-radius:999px;padding:3px 12px;margin:0 6px 6px 0;font-size:.82rem}
.card{background:#fff;border:1px solid #E2E8F0;border-radius:14px;padding:14px 18px;margin:0 0 12px 0;box-shadow:0 1px 3px rgba(15,23,42,.05);color:#0F172A}
.card .c-tit{font-weight:700;font-size:.98rem;margin:0 0 6px 0;color:#0F172A}
.card .c-txt{font-size:.95rem;line-height:1.5;color:#1E293B}
.card.ok{border-left:6px solid #16A34A}.card.warn{border-left:6px solid #D97706}.card.bad{border-left:6px solid #DC2626}.card.info{border-left:6px solid #0F766E}.card.gray{border-left:6px solid #94A3B8}
.badge{display:inline-block;border-radius:999px;padding:2px 10px;font-size:.78rem;font-weight:600;margin:0 6px 5px 0;white-space:nowrap}
.b-green{background:#DCFCE7;color:#166534}.b-amber{background:#FEF3C7;color:#92400E}.b-red{background:#FEE2E2;color:#991B1B}.b-teal{background:#CCFBF1;color:#115E59}.b-gray{background:#F1F5F9;color:#334155}
.quote{border-left:4px solid #5EEAD4;padding:8px 12px;color:#334155;font-style:italic;background:#F0FDFA;border-radius:0 10px 10px 0;margin:4px 0 10px 0}
div[data-testid="stMetric"]{background:#fff;border:1px solid #E2E8F0;border-radius:14px;padding:10px 16px;box-shadow:0 1px 3px rgba(15,23,42,.05)}
div[data-testid="stMetricLabel"] p{font-size:.85rem;color:#475569}
.stTabs [data-baseweb="tab-list"]{gap:6px}
.stTabs [data-baseweb="tab"]{background:#fff;border:1px solid #E2E8F0;border-radius:10px 10px 0 0;padding:6px 14px}
.stTabs [aria-selected="true"]{background:#F0FDFA;border-color:#99F6E4}
.pie-nota{color:#64748B;font-size:.8rem;margin-top:24px;text-align:center}
</style>"""

def estilos():
    st.markdown(_CSS, unsafe_allow_html=True)

def md(texto) -> str:
    """Texto de la planilla o de la IA → HTML seguro (escapa todo y solo respeta **negritas** y saltos de línea)."""
    import html as _h
    t = _h.escape(str(texto or ""))
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return t.replace("\n", "<br>")

def badge(texto, color="gray") -> str:
    return f'<span class="badge b-{color}">{md(texto)}</span>'

def tarjeta(titulo, cuerpo_html, tono="info"):
    st.markdown(f'<div class="card {tono}"><div class="c-tit">{md(titulo)}</div><div class="c-txt">{cuerpo_html}</div></div>',
                unsafe_allow_html=True)

_LOGOS = Path(__file__).resolve().parent / "logos"

@st.cache_data
def _logo_b64(nombre: str) -> str:
    try:
        return base64.b64encode((_LOGOS / nombre).read_bytes()).decode()
    except Exception:
        return ""

def logos():
    """Instituciones organizadoras: PUC a la izquierda, Duoc UC a la derecha."""
    uc, duoc = _logo_b64("logo_uc.png"), _logo_b64("logo_duoc.png")
    if uc and duoc:
        st.markdown(f'''<div style="display:flex;justify-content:space-between;align-items:center;gap:16px;margin:0 0 8px 0">
            <img src="data:image/png;base64,{uc}" alt="Pontificia Universidad Católica de Chile" style="height:56px;width:auto">
            <img src="data:image/png;base64,{duoc}" alt="Duoc UC" style="height:34px;width:auto"></div>''', unsafe_allow_html=True)

def encabezado(titulo, bienvenida, chips=()):
    logos()
    ch = "".join(f'<span class="chip">{md(c)}</span>' for c in chips if c)
    st.markdown(f'<div class="hero"><div class="h-tit">{md(titulo)}</div><div class="h-sub">{md(bienvenida)}</div>{ch}</div>',
                unsafe_allow_html=True)

def corto(texto, n=60) -> str:
    t = " ".join(str(texto or "").split())
    return t if len(t) <= n else t[:n - 1].rstrip() + "…"

# ------------------------------------------------------------------ página y acceso
def iniciar(app_id: str, titulo: str, icono: str,
            subtitulo: str = "Ninguno se queda atrás · Hackathon IA Aplicada · Congreso Social UC 2026", chip: str = "Desafío 2 · Educación"):
    st.set_page_config(page_title=titulo, page_icon=icono, layout="wide")
    st.session_state["_app"] = app_id
    st.session_state["_titulo_app"] = f"{icono} {titulo}"
    st.session_state["_subtitulo_acceso"], st.session_state["_chip_acceso"] = subtitulo, chip
    estilos()

def aviso_ia():
    st.info(AVISO_IA)

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
            st.markdown("#### 🔐 Ingreso del equipo")
            c1, c2 = st.columns(2)
            cod = c1.text_input("Código de equipo", placeholder="Ej: E01").strip().upper()
            cla = c2.text_input("Clave", type="password").strip()
            if st.button("Entrar", type="primary", width="stretch"):
                if cod in equipos and cla == str(equipos[cod].get("clave", "")):
                    st.session_state["_equipo"] = equipos[cod].get("nombre", cod)
                    st.session_state["_codigo"] = cod
                    registrar({"tipo": "ingreso"}); st.rerun()
                elif not equipos and cod == "DEMO" and cla == "demo":
                    st.session_state["_equipo"] = "demo"; st.rerun()
                else:
                    st.error("Código o clave incorrectos. Los entrega su mentor.")
            st.caption("El código y la clave los entrega su mentor." if equipos else "Instalación de prueba: código `demo`, clave `demo`.")
    st.stop()

# ------------------------------------------------------------------ planilla del equipo
_ID = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")

@st.cache_data(ttl=600, show_spinner=False)
def _descargar(sheet_id: str) -> dict:
    """Descarga la planilla completa como .xlsx (todas las pestañas, texto tal cual)."""
    r = requests.get(f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx", timeout=25)
    if r.status_code in (401, 403) or "text/html" in r.headers.get("Content-Type", "") or not r.content.startswith(b"PK"):
        raise ValueError("No se pudo leer la planilla: compártanla como 'Cualquier persona con el vínculo · Lector'.")
    r.raise_for_status()
    return {k.strip(): v.fillna("").astype(str) for k, v in pd.read_excel(io.BytesIO(r.content), sheet_name=None, dtype=str).items()}

@st.cache_data(show_spinner=False)
def _base(ruta: str) -> dict:
    """Plantilla base: carpeta con un CSV por pestaña (versionable en GitHub) o, si no existe, el .xlsx."""
    carpeta = Path(ruta).with_suffix("")
    if carpeta.is_dir():
        return {f.stem: pd.read_csv(f, dtype=str).fillna("") for f in sorted(carpeta.glob("*.csv"))}
    return {k: v.fillna("").astype(str) for k, v in pd.read_excel(ruta, sheet_name=None, dtype=str).items()}

def configuracion(ruta_plantilla: str, pestana_extra: str, validar_fila) -> tuple[dict, pd.DataFrame]:
    """Devuelve (config: campo→valor, filas_extra válidas). Valores vacíos → valor de la plantilla base.
    validar_fila(fila) devuelve '' si la fila es válida, o el motivo para ignorarla."""
    base = _base(ruta_plantilla)
    with st.sidebar:
        st.markdown(f"**Equipo:** {st.session_state.get('_equipo')}")
        url = st.text_input("🔗 URL de la copia de su planilla", value=st.session_state.get("_sheet_url", ""))
        if st.button("🔄 Recargar configuración", width="stretch"):
            st.session_state["_sheet_url"] = url.strip()
            _descargar.clear()
            registrar({"tipo": "recarga_configuracion", "entrada": url.strip()})
    hojas, origen = {}, "plantilla base"
    m = _ID.search(st.session_state.get("_sheet_url", ""))
    if m:
        try:
            hojas, origen = _descargar(m.group(1)), "su planilla"
        except Exception as e:
            st.sidebar.error(str(e)[:160])
    cfg_base = dict(zip(base["config"]["campo"].str.strip(), base["config"]["valor"]))
    cfg = dict(cfg_base)
    if "config" in hojas and {"campo", "valor"} <= set(hojas["config"].columns):
        for c, v in zip(hojas["config"]["campo"].str.strip(), hojas["config"]["valor"]):
            if c in cfg and str(v).strip():
                cfg[c] = str(v).strip()
    extra = hojas.get(pestana_extra, base.get(pestana_extra, pd.DataFrame()))
    validas, ignoradas = [], []
    for i, fila in extra.iterrows():
        idf = str(fila.iloc[0]).strip() if len(fila) else ""
        if not idf or idf.upper() == "EJEMPLO":
            continue
        motivo = validar_fila(fila)
        (ignoradas.append(f"Fila {i + 2} ({idf}): {motivo}") if motivo else validas.append(fila))
    extra_ok = pd.DataFrame(validas).reset_index(drop=True) if validas else pd.DataFrame(columns=extra.columns)
    with st.sidebar:
        st.caption(f"Configuración leída desde: **{origen}**")
        st.caption(f"Pestaña `{pestana_extra}`: {len(extra_ok)} fila(s) agregada(s)")
        if ignoradas:
            with st.expander(f"⚠️ {len(ignoradas)} fila(s) ignorada(s) · qué corregir"):
                for x in ignoradas: st.write("• " + x)
        cambiados = [c for c in cfg if cfg[c] != cfg_base.get(c)]
        with st.expander(f"🎛️ Personalización · {len(cambiados)} cambio(s)"):
            for c, etiqueta in (("usuario", "Usuario"), ("tono", "Tono"), ("largo_respuesta", "Largo"),
                                ("instrucciones_extra", "Reglas del equipo"), ("ejemplos", "Ejemplos")):
                marca = " ✏️" if c in cambiados else ""
                st.markdown(f"**{etiqueta}{marca}:** {corto(cfg.get(c, '') or '(vacío)', 140)}")
            st.caption("✏️ = cambiado por el equipo respecto de la plantilla base.")
    return cfg, extra_ok

def personalizacion(cfg: dict) -> str:
    """Bloque que se agrega al prompt fijo con los campos que edita el equipo."""
    return (f"PERSONALIZACIÓN DEL EQUIPO (no puede contradecir las reglas fijas anteriores):\n"
            f"- Usuario: {cfg.get('usuario', '')}\n- Tono: {cfg.get('tono', '')}\n- Largo de la respuesta: {cfg.get('largo_respuesta', '')}\n"
            f"- Reglas extra del equipo: {cfg.get('instrucciones_extra', '') or '(ninguna)'}\n"
            f"- Ejemplos de respuesta ideal (imita el estilo, NO copies los datos): {cfg.get('ejemplos', '') or '(ninguno)'}\n"
            f"ESTILO OBLIGATORIO: escribe TODO para el usuario indicado, con el tono y el tipo de lenguaje pedidos "
            f"(\"{cfg.get('tono', '')}\") y el largo indicado. El tono cambia CÓMO lo dices, nunca los datos ni las reglas fijas.")

# ------------------------------------------------------------------ IA
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

    def _k(self): return f"{st.session_state.get('_app')}|{st.session_state.get('_equipo')}"
    def usadas(self): return _global()["consultas"].get(self._k(), 0)

    def estado(self):
        if self.sin_claves: return "🟡 Modo demostración (sin conexión a la IA)"
        if self.usadas() >= self.limite: return f"🟠 Límite de {self.limite} consultas alcanzado: modo demostración"
        quien = "de tu código de mentor" if str(st.session_state.get("_codigo", "")).startswith("M") else "del equipo"
        return f"🟢 Consultas {quien}: {self.usadas()}/{self.limite}"

    def proveedores(self) -> str:
        pausas = _global().get("pausas", {})
        return " → ".join(f"{'⏸️ ' if pausas.get(self._pk(p, m), 0) > time.time() else ''}{p}/{m.split('/')[-1]}" for p, m in self.cadena) or "ninguno"

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

def aviso_si_demo(info: dict):
    modo = str(info.get("modo", ""))
    if modo == "real":
        st.caption(f"🤖 Respondió {info.get('proveedor')} · {str(info.get('modelo', '')).split('/')[-1]} · {info.get('latencia_s', '?')} s")
        return
    if not modo:
        return
    if "límite" in modo:
        st.warning("Se alcanzó el límite de consultas del equipo: se muestra una respuesta de demostración. Avisen a su mentor.")
    elif "sin claves" in modo:
        st.caption("🟡 Respuesta de demostración (instalación sin conexión a la IA).")
    else:
        st.warning(AVISO_DEMO)

def extraer_json(texto):
    """Primer objeto JSON de la respuesta (los modelos a veces agregan texto o devuelven una lista con el objeto adentro)."""
    t = (texto or "").strip()
    for patron in (r"\{.*\}", r"\[.*\]"):
        m = re.search(patron, t, re.S)
        if not m: continue
        try: d = json.loads(m.group(0))
        except Exception: continue
        if isinstance(d, list): d = next((x for x in d if isinstance(x, dict)), None)
        if isinstance(d, dict): return d
    return None

# ------------------------------------------------------------------ filtros fijos
_CRISIS = [r"suicid", r"matarme", r"quitarme la vida", r"no quiero (seguir )?vivir", r"hacerme da[ñn]o", r"autolesi", r"cortarme",
           r"terminar con todo", r"me quiero morir", r"me pega", r"me golpea", r"abus[oa]", r"violaci"]
MENSAJE_CRISIS = (
    "Gracias por contarlo. Lo que describes es importante y mereces apoyo de una persona ahora, no de una IA.\n\n"
    "• Si piensas en hacerte daño, llama a la **Línea de Prevención del Suicidio \\*4141** (gratuita, desde celulares) "
    "o a **Salud Responde 600 360 7777**.\n• En una emergencia, llama al **131 (SAMU)** o acude a urgencias.\n\n"
    "Avisé al equipo de apoyo para que una persona te contacte. _(En la hackathon es una simulación: no se contacta a nadie real.)_")
def crisis(texto): return any(re.search(p, (texto or "").lower()) for p in _CRISIS)

# ------------------------------------------------------------------ barra lateral común
def repetido(firma: str, segundos: int = 20) -> bool:
    """True si es la misma acción que se acaba de pedir (doble clic): no gasta otra consulta."""
    ultima, ahora = st.session_state.get("_ultima_accion"), time.time()
    if ultima and ultima[0] == firma and ahora - ultima[1] < segundos:
        return True
    st.session_state["_ultima_accion"] = (firma, ahora)
    return False

def pie(ia: IA):
    with st.sidebar:
        st.divider(); st.caption(ia.estado())
        st.caption(f"🤖 IA en orden de uso: {ia.proveedores()}")
        if st.session_state.get("_aviso_reg"): st.warning(st.session_state["_aviso_reg"])
        df = registro_equipo()
        st.download_button("📥 Descargar registro del equipo", df.to_csv(index=False).encode("utf-8"),
                           file_name=f"registro_{st.session_state.get('_app')}_{st.session_state.get('_equipo')}.csv",
                           mime="text/csv", width="stretch", disabled=df.empty)
        if st.button("Salir", width="stretch"):
            for k in ["_equipo", "_codigo", "_sheet_url"]: st.session_state.pop(k, None)
            st.rerun()
    st.markdown('<div class="pie-nota">Prototipo con datos ficticios · Hackathon IA Aplicada · Congreso Social UC 2026 · '
                'La decisión final siempre es de una persona.</div>', unsafe_allow_html=True)
