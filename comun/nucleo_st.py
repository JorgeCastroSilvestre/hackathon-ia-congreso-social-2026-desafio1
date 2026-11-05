"""
NÚCLEO COMÚN · Plantillas Hackathon IA Congreso Social UC 2026 · Desafío 2
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
import persistencia as P
import validaciones as V

AVISO_IA = ("**Esta herramienta usa inteligencia artificial.** Puede equivocarse y **no reemplaza el criterio "
            "de una persona**: la decisión final siempre es humana. Lo que se consulta y responde queda registrado "
            "para la revisión de la hackathon. Prototipo con datos ficticios.")
AVISO_DEMO = ("Se muestra una respuesta preparada de ejemplo: la IA no respondió. Esperen un minuto y prueben de nuevo; "
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

def identidad_equipo() -> str:
    return st.session_state.get("_codigo") or st.session_state.get("_equipo", "demo")


def _clave_estado(clave):
    return f"{st.session_state.get('_app')}|{identidad_equipo()}|{clave}"


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


def estado_equipo(clave: str) -> dict:
    """Recupera estado confirmado. La pestaña se prepara antes del despliegue."""
    st.session_state["_modo_estado"] = "sin_verificar"
    g = _global()
    with g["lock"]:
        anterior = dict(g["equipos"].setdefault(_clave_estado(clave), {}))
    try:
        ws = _hoja_estado()
        if ws is None:  # modalidad básica de la demo: estado temporal en memoria (lo explica aviso_demo)
            st.session_state["_modo_estado"] = "temporal"
            st.session_state.pop("_error_estado", None)
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
        st.session_state["_modo_estado"] = "central"
        return dict(datos)
    except Exception:
        st.session_state["_error_estado"] = True
        st.session_state["_modo_estado"] = "error"
        st.error("No se pudo leer el estado central. La vista puede estar incompleta. No se confirmarán cambios hasta recuperar la conexión; revise la pestaña estado_d1_v1 y sus permisos.")
        return anterior


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


def cerrar_sesion():
    # Incluye consentimientos, historial, widgets, propuestas y clientes antiguos.
    for clave in list(st.session_state):
        del st.session_state[clave]

# ------------------------------------------------------------------ registro
_lock = threading.Lock()
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

# ------------------------------------------------------------------ apariencia
_CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&family=Source+Sans+3:wght@400;600;700&display=swap');
:root{--azul:#0A2B5C;--azul2:#1F4E8C;--azul-claro:#E8EEF7;--oro:#D9A400;--oro-claro:#FBF3D9;--tinta:#13213A;--gris:#5B6475;--borde:#D9DEE7;--fondo:#F6F7F9}
html,body,[class*="css"],.stMarkdown,.stTextInput,.stButton,.stRadio,.stSelectbox{font-family:'Source Sans 3',system-ui,sans-serif}
h1,h2,h3,h4{font-family:'Source Serif 4',Georgia,serif !important;color:var(--azul) !important;font-weight:700 !important;letter-spacing:-.005em}
.block-container{padding-top:1.2rem;padding-bottom:3rem;max-width:1200px}
.marca{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:10px 16px;padding:6px 0 12px 0;margin:0 0 18px 0;border-bottom:1px solid var(--borde)}
.marca .m-centro{order:3;flex-basis:100%;text-align:center;color:var(--gris);font-size:.78rem;letter-spacing:.08em;text-transform:uppercase}
.hero{background:#fff;border:1px solid var(--borde);border-top:4px solid var(--azul);border-radius:6px;padding:22px 28px 16px;margin:0 0 16px 0}
.hero .h-ceja{color:var(--oro);font-size:.76rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin:0 0 6px 0}
.hero .h-tit{font-family:'Source Serif 4',Georgia,serif;color:var(--azul);font-size:2rem;font-weight:700;line-height:1.15;margin:0 0 8px 0}
.hero .h-sub{color:var(--gris);font-size:1.04rem;line-height:1.5;margin:0 0 12px 0;max-width:880px}
.chip{display:inline-block;background:var(--azul-claro);color:var(--azul);border-radius:4px;padding:3px 10px;margin:0 6px 6px 0;font-size:.8rem;font-weight:600}
.card{background:#fff;border:1px solid var(--borde);border-radius:6px;padding:14px 18px;margin:0 0 12px 0;color:var(--tinta)}
.card .c-tit{font-weight:700;font-size:1rem;margin:0 0 6px 0;color:var(--azul)}
.card .c-txt{font-size:.96rem;line-height:1.55;color:var(--tinta)}
.card.guia{padding:10px 16px}.card.guia .c-txt,.card.guia .c-txt li{font-size:var(--letra-demo,.96rem);line-height:1.6}
.card.ok{border-left:4px solid #2E7D4F}.card.warn{border-left:4px solid var(--oro)}.card.bad{border-left:4px solid #B3261E}.card.info{border-left:4px solid var(--azul2)}.card.gray{border-left:4px solid #A3ABB8}
.badge{display:inline-block;border-radius:4px;padding:2px 9px;font-size:.78rem;font-weight:600;margin:0 6px 5px 0;white-space:nowrap}
.b-green{background:#E3F1E8;color:#1F5C38}.b-amber{background:var(--oro-claro);color:#7A5A00}.b-red{background:#F8E1DF;color:#8C1D18}.b-teal{background:var(--azul-claro);color:var(--azul)}.b-gray{background:#EEF0F3;color:#3D4554}
.quote{border-left:3px solid var(--oro);padding:8px 12px;color:var(--tinta);font-style:italic;background:var(--oro-claro);border-radius:0 4px 4px 0;margin:4px 0 10px 0}
div[data-testid="stMetric"]{background:#fff;border:1px solid var(--borde);border-radius:6px;padding:10px 16px}
div[data-testid="stMetricLabel"] p{font-size:.8rem;color:var(--gris);text-transform:uppercase;letter-spacing:.04em}
div[data-testid="stMetricValue"]{color:var(--azul);font-family:'Source Serif 4',Georgia,serif}
.stTabs [data-baseweb="tab-list"]{gap:0;border-bottom:1px solid var(--borde)}
.stTabs [data-baseweb="tab"]{background:transparent;padding:8px 18px;color:var(--gris);font-weight:600}
.stTabs [aria-selected="true"]{color:var(--azul) !important}
.stTabs [data-baseweb="tab-highlight"]{background-color:var(--oro) !important;height:3px}
div[class*="st-key-oculto_"]{display:none !important}
div[class*="st-key-nav_"]{border-bottom:1px solid var(--borde);padding-bottom:10px;margin-bottom:6px}
div[class*="st-key-nav_"] button{border-radius:4px !important;font-weight:600}
div[data-testid="stAlert"]{border-radius:6px}
.stButton button,.stDownloadButton button{border-radius:4px;font-weight:600}
section[data-testid="stSidebar"]{background:#fff;border-right:1px solid var(--borde)}
.pie-nota{color:var(--gris);font-size:.78rem;margin-top:28px;padding-top:12px;border-top:1px solid var(--borde);text-align:center}
</style>"""


def estilos():
    st.markdown(_CSS, unsafe_allow_html=True)

def pestanas(opciones, clave):
    """Reemplazo de st.tabs que recuerda la sección abierta: st.tabs vuelve a la primera pestaña después de
    presionar un botón. Devuelve un contenedor por opción; los no elegidos se ocultan con CSS."""
    elegida = st.segmented_control("Sección", opciones, default=opciones[0], key=f"nav_{clave}",
                                   label_visibility="collapsed") or opciones[0]
    return [st.container() if o == elegida else st.container(key=f"oculto_{clave}_{i}") for i, o in enumerate(opciones)]

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
        st.markdown(f'''<div class="marca">
            <img src="data:image/png;base64,{uc}" alt="Pontificia Universidad Católica de Chile" style="height:52px;width:auto">
            <div class="m-centro">Hackathon de Inteligencia Artificial Aplicada · Congreso Social UC 2026</div>
            <img src="data:image/png;base64,{duoc}" alt="Duoc UC" style="height:32px;width:auto"></div>''', unsafe_allow_html=True)

def encabezado(titulo, bienvenida, chips=(), ceja="Desafío 1 · Envejecer con autonomía"):
    logos()
    ch = "".join(f'<span class="chip">{md(c)}</span>' for c in chips if c)
    st.markdown(f'<div class="hero"><div class="h-ceja">{md(ceja)}</div><div class="h-tit">{md(titulo)}</div>'
                f'<div class="h-sub">{md(bienvenida)}</div>{ch}</div>', unsafe_allow_html=True)

def corto(texto, n=60) -> str:
    t = " ".join(str(texto or "").split())
    return t if len(t) <= n else t[:n - 1].rstrip() + "…"

# ------------------------------------------------------------------ página y acceso
def iniciar(app_id: str, titulo: str, icono: str,
            subtitulo: str = "Ninguno se queda atrás · Hackathon IA Aplicada · Congreso Social UC 2026", chip: str = "Desafío 2 · Educación"):
    st.set_page_config(page_title=titulo, page_icon=str(_LOGOS / "logo_uc.png") if (_LOGOS / "logo_uc.png").exists() else None, layout="wide")
    st.session_state["_app"] = app_id
    st.session_state["_titulo_app"] = titulo
    st.session_state["_subtitulo_acceso"], st.session_state["_chip_acceso"] = subtitulo, chip
    estilos()

def aviso_ia():
    st.info(AVISO_IA)

# ------------------------------------------------------------------ guía educativa (demo)
AVISO_DEMO_TEMPORAL = "Solo utiliza datos ficticios. Los casos y decisiones temporales se borran al reiniciar."
AVISO_DEMO_CENTRAL = "Solo utiliza datos ficticios. Los casos y decisiones de esta instalación se guardan en una planilla central."
AVISO_SIMULACION = "Ninguna acción de esta demo contacta a personas ni activa servicios reales: todo es una simulación."

def aviso_demo():
    """Aviso breve y visible. Se llama después de leer el estado, para no decir 'temporal' si de verdad se guarda."""
    modo = st.session_state.get("_modo_estado", "sin_verificar")
    aviso = {"central": AVISO_DEMO_CENTRAL, "temporal": AVISO_DEMO_TEMPORAL,
             "error": "Solo utiliza datos ficticios. No se pudo verificar el almacenamiento central. La vista puede estar incompleta y hay que confirmar cualquier guardado pendiente.",
             "sin_verificar": "Solo utiliza datos ficticios. El almacenamiento todavía no se ha verificado."}
    tarjeta("Demostración educativa", md(aviso.get(modo, aviso["sin_verificar"])) + "<br>" + md(AVISO_SIMULACION), "warn guia")

def recorrido(pasos, limites):
    """Recorrido sugerido (pasos numerados) y límites de la demo, lado a lado y sin saturar la pantalla."""
    c1, c2 = st.columns([1.6, 1], gap="medium")
    with c1:
        lista = "".join(f"<li>{md(p)}</li>" for p in pasos)
        tarjeta("Recorrido sugerido", f"<ol style='margin:0;padding-left:1.2em'>{lista}</ol>", "info guia")
    with c2:
        lista = "".join(f"<li>{md(l)}</li>" for l in limites)
        tarjeta("Límites de esta demo", f"<ul style='margin:0;padding-left:1.1em'>{lista}</ul>", "gray guia")

def como_adaptar(editables, protecciones, codigo):
    """Panel plegable: qué pueden cambiar los equipos, qué deben conservar y dónde está cada parte en el código."""
    with st.expander("Cómo adaptar esta demo"):
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            st.markdown("**Pueden adaptar** (desde su copia de la planilla, sin programar)")
            st.markdown("\n".join(f"- {e}" for e in editables))
        with c2:
            st.markdown("**Deben conservar** (protecciones fijas)")
            st.markdown("\n".join(f"- {p}" for p in protecciones))
        st.markdown("**Dónde está cada parte, si quieren crear su propia versión**")
        st.markdown("\n".join(f"- {c}" for c in codigo))
        st.caption("Pueden copiar o imitar cualquier parte de esta demo para su propio desarrollo. "
                   "Si construyen otra herramienta, mantengan protecciones equivalentes.")

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
        tarjeta("Demostración educativa", md("Esta plataforma es una **referencia** para que los equipos la exploren, la imiten o copien lo que les sirva. "
                                              "Solo utiliza datos ficticios.") + "<br>" + md(AVISO_SIMULACION), "warn")
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
        url = st.text_input("URL de la copia de su planilla", value=st.session_state.get("_sheet_url", ""))
        if st.button("Recargar configuración", width="stretch"):
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
    # Los prompts y ejemplos del equipo se conservan para sus pruebas. Los
    # textos que se muestran directamente a la persona también deben validarse.
    fallbacks = {"titulo_app": "Demostración educativa", "texto_bienvenida": "Explore esta demostración con datos ficticios.",
                 "texto_boton": "Comenzar", "mensaje_inicial": "Hola, soy un asistente de inteligencia artificial. ¿Qué apoyo necesita?",
                 "texto_consentimiento": "Entiendo que converso con una inteligencia artificial, que la conversación queda registrada y que puedo dejar de responder cuando quiera.",
                 "respuestas_rapidas": "Quiero conocer los apoyos disponibles"}
    for campo, seguro in fallbacks.items():
        if campo in cfg and V.texto_inseguro(cfg[campo]):
            original = cfg[campo]
            base_segura = cfg_base.get(campo, seguro)
            cfg[campo] = seguro if V.texto_inseguro(base_segura) else base_segura
            st.sidebar.warning(f"Se reemplazó el campo {campo}: no cumple las protecciones de salud o trato respetuoso.")
            firma = hashlib.sha256((campo + original).encode()).hexdigest()
            vistos = st.session_state.setdefault("_config_bloqueada", set())
            if firma not in vistos:
                registrar({"tipo": "validacion", "tarea": "configuracion", "nota": f"Texto de pantalla bloqueado: {campo}"})
                vistos.add(firma)
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
            with st.expander(f"{len(ignoradas)} fila(s) ignorada(s) · qué corregir"):
                for x in ignoradas: st.write("• " + x)
        cambiados = [c for c in cfg if cfg[c] != cfg_base.get(c)]
        with st.expander(f"Personalización · {len(cambiados)} cambio(s)"):
            for c, etiqueta in (("usuario", "Usuario"), ("tono", "Tono"), ("largo_respuesta", "Largo"),
                                ("instrucciones_extra", "Reglas del equipo"), ("ejemplos", "Ejemplos")):
                marca = " (modificado)" if c in cambiados else ""
                st.markdown(f"**{etiqueta}{marca}:** {corto(cfg.get(c, '') or '(vacío)', 140)}")
            st.caption("(modificado) = cambiado por el equipo respecto de la plantilla base.")
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

def aviso_si_demo(info: dict):
    modo = str(info.get("modo", ""))
    fijos = {"configuracion": "Mensaje inicial de la configuración: no generado por IA.",
             "protocolo": "Protocolo fijo de seguridad: no generado por IA.",
             "proteccion": "Respuesta reemplazada por una protección fija: no generada por IA.",
             "clasificacion_local": "Hoja de ruta preparada por clasificación local: no generada por IA.",
             "limite_turnos": "Aviso fijo del límite de conversación: no generado por IA."}
    if modo in fijos:
        st.caption(fijos[modo])
        return
    if modo == "edicion_humana":
        base = "IA conectada" if info.get("modo_base") == "real" else "ejemplo preparado"
        st.caption(f"Propuesta editada por una persona. Origen del borrador: {base}.")
        return
    if modo == "real":
        st.caption(f"Respuesta generada por IA conectada: {info.get('proveedor')} · {str(info.get('modelo', '')).split('/')[-1]} · "
                   f"{info.get('latencia_s', '?')} s. Puede equivocarse: revísala.")
        return
    if not modo:
        return
    if "límite" in modo:
        st.warning("Se alcanzó el límite de consultas del equipo: se muestra una respuesta preparada de ejemplo, no generada por IA. Avisen a su mentor.")
    elif "sin claves" in modo:
        st.caption("Respuesta preparada de ejemplo: esta instalación no tiene IA conectada.")
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
    "_En un servicio real, una persona del equipo de apoyo revisaría este caso. En esta demostración no se contacta a nadie._")
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
