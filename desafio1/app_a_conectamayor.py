"""Desafío 1 · Variante A · ConectaMayor IA (conversación de orientación para personas mayores o quien las acompaña).
Los equipos la personalizan en su copia de la planilla (pestañas `config` y `servicios_extra`)."""
import json, re, sys
from pathlib import Path
AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI.parent / "comun")); sys.path.insert(0, str(AQUI))
import pandas as pd, streamlit as st
import streamlit.components.v1 as components
import nucleo_st as N
import servicios as S

N.iniciar("D1-A", "ConectaMayor IA", "🤝", subtitulo="Envejecer con autonomía · Hackathon IA Aplicada · Congreso Social UC 2026", chip="Desafío 1 · Personas mayores")
N.acceso()
cfg, extra = N.configuracion(str(AQUI / "planillas" / "Plantilla_config_D1_Variante_A.xlsx"), "servicios_extra", S.validar_servicio)
catalogo = S.catalogo(AQUI, extra)
SERV = dict(zip(catalogo.id_servicio, catalogo.nombre))
ACCESO = dict(zip(catalogo.id_servicio, catalogo.como_acceder))
personas = pd.read_csv(AQUI / "datos" / "personas_conectamayor.csv", dtype=str)
try: MAX_TURNOS = max(3, min(15, int(cfg.get("max_turnos", "8"))))
except ValueError: MAX_TURNOS = 8
LETRA = {"normal": "1rem", "grande": "1.2rem", "muy grande": "1.45rem"}.get(cfg.get("tamano_letra", "grande").strip().lower(), "1.2rem")
RAPIDAS = [r.strip() for r in cfg.get("respuestas_rapidas", "").split(";") if r.strip()][:6]
CATEGORIAS = sorted(S.CATEGORIAS) + ["ninguna"]
QUIEN = {"Hablo por mí": "la propia persona mayor", "Hablo por alguien a quien acompaño": "un familiar, vecino o persona cercana que acompaña a una persona mayor"}
st.markdown(f"<style>[data-testid='stChatMessage'] p,[data-testid='stChatMessage'] li,.card .c-txt{{font-size:{LETRA};line-height:1.6}}"
            f"div[data-testid='stButton'] button p{{font-size:{LETRA}}}</style>", unsafe_allow_html=True)

# 🔒 Reglas fijas (los equipos solo agregan personalización desde la planilla)
REGLAS = """Eres "ConectaMayor", un asistente de orientación para personas mayores en Chile y para quienes las acompañan.
Tu objetivo: entender qué necesita la persona y orientarla hacia apoyo HUMANO del catálogo. No resuelves por ella ni decides por ella.
Estás conversando con: {quien}.
REGLAS FIJAS:
1. Trato de persona adulta: nunca uses diminutivos ni apodos como "abuelito", "abuelita", "viejito" o "mi reina". No infantilices.
2. Lenguaje claro: frases cortas, palabras simples, una sola pregunta por mensaje.
3. NO eres profesional de salud: no diagnosticas, no nombras enfermedades y NUNCA indicas cómo tomar, cambiar, juntar o suspender un medicamento.
   Ante dudas de salud o remedios, menciona Salud Responde.
4. Solo mencionas servicios del catálogo, por su nombre. No prometes beneficios, montos ni resultados.
5. Para explicar cómo acceder a un servicio, usa SOLO lo que dice "Cómo acceder" en el catálogo: no inventes teléfonos, direcciones, plazos ni requisitos.
6. Respeta la autonomía: las decisiones son de la persona mayor. Si conversas con alguien que la acompaña, recuerda contar con la opinión de la persona mayor.
7. No pides datos personales (RUT, dirección, claves, datos bancarios). Si alguien cuenta que le pidieron claves o datos bancarios, explica con calma que puede ser una estafa.
8. Escribe en español de Chile. Usa el trato (tú o usted) que indique el tono del equipo; nunca uses voseo ("tenés", "querés").
9. SEÑALES GRAVES, aunque se digan de forma indirecta o suave:
   - Si la persona describe maltrato, abandono, encierro, miedo a alguien con quien vive, o que le quitan o controlan su dinero, sus remedios o sus salidas:
     responde SOLO con la palabra [MALTRATO]. Ejemplos: "no sé qué pasa con mi pensión desde que mi yerno vive acá y no me atrevo a preguntar";
     "me dejaron sola por dos semanas y no puedo cocinar"; "mi hijo decide todo por mí y no me deja opinar". Ante la duda, usa [MALTRATO]:
     una persona revisará el caso con cuidado.
   - Si describe una emergencia de salud, una caída en la que no pudo levantarse, ganas de morir, de no despertar o de desaparecer, o sentirse una carga
     para los demás: responde SOLO con la palabra [EMERGENCIA].
   La app reemplaza esa palabra por un mensaje fijo con los teléfonos de ayuda.
Catálogo:
{catalogo}"""
CLASIFICAR = """Lee la conversación y responde SOLO con un JSON con estas claves:
"necesidades": lista con una o más de: {categorias};
"urgencia": "baja", "media" o "alta";
"resumen": 2 frases neutrales para la persona de la red de apoyo, sin juicios ni diagnósticos;
"servicio_sugerido": código del catálogo (ej. "S02") o "ninguno";
"hoja_de_ruta": lista de 2 o 3 pasos muy cortos, en lectura fácil, para la persona que conversó. Usa SOLO lo que dice "Cómo acceder" en el catálogo.
Catálogo:
{catalogo}
Conversación:
{conv}"""
DIAGNOSTICO = re.compile(r"\b(tiene|tienes|sufre|sufres|padece|padeces|parece que tiene|parece que tienes|podr[ií]a tener)\s+(demencia|alzh?eimer|depresi[oó]n|ansiedad|parkinson|un trastorno|deterioro cognitivo)|\bdiagn[oó]stic", re.I)
MEDICAMENTO = re.compile(r"\b\d+(?:[.,]\d+)?\s?(mg|ml|gotas|comprimidos|pastillas)\b|\b(deje|dejar|deja|suspenda|suspender|suspende|aumente|aumentar|aumenta|disminuya|baje|bajar|junte|juntar)\s+(de tomar|la dosis|el remedio|los remedios|el medicamento|la pastilla|las pastillas)", re.I)
EDADISMO = re.compile(r"\b(abuelit[oa]s?|viejit[oa]s?|mi reina|mijit[oa]|tatita)\b", re.I)
SIN_SALUD = ("No puedo darle indicaciones de salud ni de medicamentos: eso lo debe ver una persona de salud. Puede llamar a **Salud Responde, 600 360 7777**, "
             "todos los días a toda hora. ¿Hay algo más en que le pueda orientar?")
# 🔒 Protocolos fijos: se activan antes de consultar a la IA
_FAMILIA = r"(mi|su|el|la) (hij|nuer|yern|sobrin|niet|espos|pareja|marido|herman|cuidador|familia)"
_MALTRATO = [r"(me|le) (pega|pegan|golpea|golpean|empuja|empujan|zamarrea|insulta|insultan|grita|gritan|humilla|humillan|amenaza|amenazan)\b",
             r"(me|le) (tiene|tienen|deja|dejan) encerrad", r"\bencerrad[oa]\b", r"no (me|le) (deja|dejan) (salir|usar el tel[eé]fono|ver a|hablar con)",
             r"(me|le) (quita|quitan|saca|sacan|cobra|cobran) (la |mi |su )?(plata|pensi[oó]n|tarjeta|platita|jubilaci[oó]n)",
             r"(maneja|manejan|administra|administran|controla|controlan) (mi|su) (plata|pensi[oó]n|dinero|tarjeta|jubilaci[oó]n)",
             r"ya no (veo|ve) (mi|su) (plata|pensi[oó]n|dinero)", r"no (me|le) (da|dan|pasa|pasan) (de )?(comer|mis remedios|sus remedios|los remedios)",
             rf"miedo (a|de) {_FAMILIA}", r"miedo cuando (llega|viene|est[aá]|se enoja)", r"me tratan (como|mal)", r"\bun estorbo\b", r"maltrat", r"abus[oa]"]
_EMERGENCIA = [r"ca[ií]\w*.{0,60}no (me|se|le) (pude|pudo|puedo|puede|pod[ií]a)\w* (levantar|parar)", r"no (me|se) (pude|pudo|puedo|puede) (levantar|parar) del suelo",
               r"(dolor|apret[oó]n|puntada) (fuerte )?en el pecho", r"no (puedo|puede|pod[ií]a) respirar", r"me ahogo",
               r"se (me|le) (durmi[oó]|torci[oó]|cay[oó]) (la cara|un lado|el brazo|la boca)", r"no (despierta|reacciona)", r"(perdi[oó]|perd[ií]) el conocimiento", r"se desmay",
               r"cansad[oa] de vivir", r"(mejor|prefiero|quisiera) no despertar", r"no despertar m[aá]s", r"para qu[eé] seguir( viviendo)?", r"ya no quiero (estar|seguir)",
               r"(estar[ií]an|vivir[ií]an) (mejor|m[aá]s tranquil\w*) sin m[ií]", r"(soy|ser) una carga", r"\bdesaparecer\b", r"morirme", r"quiero morir"]
MARCA = re.compile(r"\[(MALTRATO|EMERGENCIA)\]")
MENSAJE_MALTRATO = ("Gracias por contarlo. Nadie tiene derecho a maltratar, amenazar ni quitarle su dinero a una persona mayor.\n\n"
                    "• **Fono Mayor 800 400 035** (gratuito, SENAMA): orienta y recibe denuncias de maltrato, abandono o abuso económico.\n"
                    "• Si hay peligro ahora: **133 (Carabineros)**.\n\n"
                    "Avisé a la red de apoyo para que una persona se comunique, con cuidado y respetando su decisión. "
                    "_(En la hackathon es una simulación: no se contacta a nadie real.)_")
MENSAJE_EMERGENCIA = ("Esto necesita ayuda de una persona ahora, no de una IA.\n\n"
                      "• **Emergencia de salud** (caída con dolor fuerte, dolor en el pecho, dificultad para respirar o hablar): llame al **131 (SAMU)**.\n"
                      "• Si piensa en hacerse daño: **Línea de Prevención del Suicidio \\*4141** (gratuita) o **Salud Responde 600 360 7777**.\n"
                      "• Peligro inmediato: **133 (Carabineros)**.\n\n"
                      "Avisé a la red de apoyo para que una persona se comunique. _(En la hackathon es una simulación: no se contacta a nadie real.)_")
def protocolo(t):
    t = (t or "").lower()
    if any(re.search(p, t) for p in _EMERGENCIA) or (N.crisis(t) and not any(re.search(p, t) for p in _MALTRATO)): return "CRISIS"
    if any(re.search(p, t) for p in _MALTRATO): return "MALTRATO"
    return None

DEMO = {"chat": {
    "P1_1": "Gracias por contarme. Debe ser muy difícil pasar tanto tiempo sola desde que falleció su esposo. ¿Le gustaría que le cuente de lugares donde puede compartir con otras personas?",
    "P1_2": "En muchas comunas existe el **Programa Vínculos**, que visita a personas mayores que viven solas. Para eso puede preguntar en la Oficina del Adulto Mayor de la municipalidad. ¿Quiere que alguien de la red le llame para ayudarle?",
    "P2_1": "Hizo muy bien en no entregar la clave. Los bancos nunca piden claves por teléfono: es muy probable que fuera un intento de estafa. ¿Alcanzó a entregar algún otro dato?",
    "P3_1": "Gracias por contarlo. Cuidar a su mamá todos los días sin reemplazo es muy agotador. ¿Le gustaría saber qué apoyos existen para personas cuidadoras?",
    "P4_1": "Es una muy buena pregunta, pero sobre cómo tomar los remedios solo le puede orientar una persona de salud. Puede llamar a **Salud Responde, 600 360 7777**. ¿Le cuesta recordar los horarios de los remedios?",
    "P6_1": "¡Qué bueno que quiera hacer actividades! Hay **clubes de personas mayores** con talleres y paseos. ¿Qué tipo de actividades le gustan?",
    "_por_defecto": "Gracias por contármelo. ¿Me puede contar un poco más sobre lo que necesita?"}, "clasificar": {}}
PAL = {"compania": ["sol", "nadie", "no salgo", "aburr", "actividad", "jubil"], "salud": ["remedio", "pastilla", "medicamento", "doctor", "dolor", "presión", "consultorio", "cesfam"],
       "tramites": ["pensión", "pgu", "trámite", "tramite", "registro social", "beneficio", "bono", "ayuda"],
       "cuidado": ["bañar", "vestir", "se cayó", "ayuda en la casa", "no puede"], "cuidadores": ["cansad", "agotad", "cuido a", "no duermo", "reemplaz"],
       "maltrato": ["grita", "pega", "quita la plata", "pensión y no", "miedo"], "estafas": ["llamada", "clave", "banco", "premio", "estafa", "me pidieron"]}
SC = {"maltrato": "S01", "compania": "S02", "cuidado": "S05", "salud": "S07", "cuidadores": "S08", "tramites": "S09", "estafas": "S10"}
def clasif_local(t):
    t = t.lower(); nec = [c for c, ps in PAL.items() if any(p in t for p in ps)] or ["ninguna"]; s = SC.get(nec[0], "ninguno")
    return {"necesidades": nec, "urgencia": "media" if len(nec) > 1 else "baja", "resumen": f"Clasificación por palabras clave: {', '.join(nec)}.",
            "servicio_sugerido": s, "hoja_de_ruta": [f"Puede recurrir a: {SERV[s]}.", f"Cómo: {ACCESO[s]}", "Si lo prefiere, pida a una persona de confianza que le acompañe."]
            if s in SERV else ["Si lo desea, una persona de la red de apoyo puede llamarle para conversar."]}
ia = N.IA(DEMO)

def escuchar(texto, alto=46):
    """Botón que lee el texto en voz alta con la voz del navegador (sin costo y sin enviar el audio a ningún servicio)."""
    limpio = json.dumps(re.sub(r"[*_#>\\]", "", texto))
    components.html(f"""<button id="b" style="font-size:16px;padding:6px 14px;border-radius:10px;border:1px solid #0F766E;background:#F0FDFA;color:#0F766E;cursor:pointer">🔊 Escuchar</button>
<script>document.getElementById('b').onclick=()=>{{const u=new SpeechSynthesisUtterance({limpio});u.lang='es-CL';u.rate=0.9;speechSynthesis.cancel();speechSynthesis.speak(u);}};</script>""", height=alto)

def palabras_por_frase(textos):
    frases = [f for t in textos for f in re.split(r"[.!?¿¡]+\s*", re.sub(r"[*_]", "", t)) if len(f.split()) > 1]
    return round(sum(len(f.split()) for f in frases) / len(frases), 1) if frases else 0

bandeja = N.estado_equipo("bandeja").setdefault("casos", [])
ss = st.session_state
ss.setdefault("hist", []); ss.setdefault("turno", 0); ss.setdefault("clasif", None); ss.setdefault("ultimo_info", {}); ss.setdefault("quien", list(QUIEN)[0])
conv_txt = lambda h: "\n".join(f"{'Persona' if m['role'] == 'user' else 'Asistente'}: {m['content']}" for m in h)
URG = {"CRISIS": ("🔴 Emergencia", "red"), "MALTRATO": ("🟣 Posible maltrato", "red"), "alta": ("🟠 Alta", "amber"), "media": ("🟡 Media", "amber"), "baja": ("🟢 Baja", "green")}
AVATAR = {"assistant": "🤝", "user": "🧓"}

def reiniciar():
    ss.hist, ss.turno, ss.clasif, ss.ultimo_info = [], 0, None, {}
    ss["_n_conv"] = ss.get("_n_conv", 0) + 1

def nuevo_caso(pid, c, origen):
    cid = f"C{len(bandeja) + 1:03d}"
    bandeja.append({"caso": cid, "persona": pid, "conversa": "Persona mayor" if ss.quien == list(QUIEN)[0] else "Apoyo cercano", "origen": origen,
                    "urgencia": c.get("urgencia", "-"), "necesidades": ", ".join(c.get("necesidades", [])), "servicio_sugerido": c.get("servicio_sugerido", "-"),
                    "resumen_ia": c.get("resumen", ""), "conversacion": conv_txt(ss.hist), "decision": "Pendiente"})
    N.registrar({"tipo": "caso_creado", "caso": cid, "origen": origen, "urgencia": c.get("urgencia")}); return cid

def activar_protocolo(tipo, msg, pid, origen):
    texto = MENSAJE_EMERGENCIA if tipo == "CRISIS" else MENSAJE_MALTRATO
    ss.hist.append({"role": "assistant", "content": texto})
    N.registrar({"tipo": "protocolo_" + tipo.lower(), "entrada": msg, "salida": texto, "nota": origen})
    nuevo_caso(pid, {"urgencia": tipo, "necesidades": ["maltrato" if tipo == "MALTRATO" else "salud"], "servicio_sugerido": "S01" if tipo == "MALTRATO" else "-",
                     "resumen": f"Señal grave ({origen}): contacto humano prioritario."}, origen)

def enviar(texto):
    ss["_pendiente"] = texto

# ------------------------------------------------------------------ pantalla
N.encabezado(cfg["titulo_app"], cfg["texto_bienvenida"],
             [f"👥 {st.session_state.get('_equipo')}", f"🎯 Para: {N.corto(cfg.get('usuario'), 70)}", f"💬 Hasta {MAX_TURNOS} mensajes", f"🔠 Letra {cfg.get('tamano_letra', 'grande')}"])
N.aviso_ia()
pend = sum(b["decision"] == "Pendiente" for b in bandeja)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Casos en la bandeja", len(bandeja))
m2.metric("Pendientes de revisión", pend)
m3.metric("Emergencias o maltrato", sum(b["urgencia"] in ("CRISIS", "MALTRATO") for b in bandeja))
m4.metric("Consultas a la IA", f"{ia.usadas()} de {ia.limite}")

t1, t2 = st.tabs(["💬 1 · Conversación (vista de la persona)", "📥 2 · Bandeja de la red de apoyo"])
with t1:
    chat, lado = st.columns([1.7, 1], gap="large")
    with lado:
        with st.container(border=True):
            st.markdown("**🎭 Simular como** · solo para pruebas del equipo")
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
                st.markdown("#### 👋 Antes de empezar")
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
                if tipo:  # 🔒 protocolo fijo: no pasa por la IA
                    activar_protocolo(tipo, msg, pid, "protocolo fijo")
                elif ss.turno > MAX_TURNOS:
                    ss.hist.append({"role": "assistant", "content": "Llegamos al final de la conversación. Presione **Terminar** para ver su resumen."})
                else:
                    sistema = REGLAS.format(quien=QUIEN[ss.quien], catalogo=S.texto(catalogo)) + "\n\n" + N.personalizacion(cfg)
                    with st.spinner("ConectaMayor está escribiendo…"):
                        texto, info = ia.llamar([{"role": "system", "content": sistema}] + ss.hist, "chat", f"{pid}_{ss.turno}", temperatura=0.5, max_tokens=350)
                    marca = MARCA.search(texto)
                    if marca:  # 🔒 la IA reconoció una señal grave dicha de forma indirecta: se aplica el mismo protocolo fijo
                        activar_protocolo("CRISIS" if marca.group(1) == "EMERGENCIA" else "MALTRATO", msg, pid, "señal indirecta reconocida por la IA")
                        ss.ultimo_info = info
                    else:
                        if DIAGNOSTICO.search(texto) or MEDICAMENTO.search(texto):  # 🔒 validación: sin diagnósticos ni indicaciones de medicamentos
                            N.registrar({"tipo": "validacion", "tarea": "chat", "salida": texto, "nota": "indicación de salud bloqueada"})
                            texto = SIN_SALUD
                            ss["_aviso_val"] = "🔒 La validación reemplazó la respuesta de la IA porque daba indicaciones de salud o medicamentos."
                        elif EDADISMO.search(texto):
                            N.registrar({"tipo": "validacion", "tarea": "chat", "salida": texto, "nota": "lenguaje infantilizante"})
                            ss["_aviso_val"] = "⚠️ La validación detectó lenguaje infantilizante en la respuesta de la IA (queda registrado)."
                        ss.hist.append({"role": "assistant", "content": texto}); ss.ultimo_info = info
                st.rerun()
            if len(ss.hist) > 1 and st.button("✅ Terminar"):
                solo = " ".join(m["content"] for m in ss.hist if m["role"] == "user")
                DEMO["clasificar"]["actual"] = json.dumps(clasif_local(solo), ensure_ascii=False)
                with st.spinner("Preparando su resumen…"):
                    texto, info = ia.llamar([{"role": "system", "content": "Respondes solo JSON válido. " + N.personalizacion(cfg)},
                                             {"role": "user", "content": CLASIFICAR.format(categorias=", ".join(CATEGORIAS), catalogo=S.texto(catalogo), conv=conv_txt(ss.hist))}],
                                            "clasificar", "actual", json_mode=True, temperatura=0)
                c = N.extraer_json(texto)
                if not isinstance(c, dict): c = clasif_local(solo)
                c["necesidades"] = [n for n in c.get("necesidades", []) if n in CATEGORIAS] or ["ninguna"]
                if c.get("servicio_sugerido") not in SERV: c["servicio_sugerido"] = "ninguno"
                pasos = c.get("hoja_de_ruta") or []
                c["hoja_de_ruta"] = [str(p) for p in (pasos if isinstance(pasos, list) else [pasos])][:3]
                if any(MEDICAMENTO.search(p) or DIAGNOSTICO.search(p) for p in c["hoja_de_ruta"]): c["hoja_de_ruta"] = [SIN_SALUD]
                ss.clasif = c; ss.ultimo_info = info; st.rerun()
        if ss.clasif:
            c = ss.clasif
            pasos = "".join(f"<li>{N.md(p)}</li>" for p in c["hoja_de_ruta"])
            N.tarjeta("🧭 Su hoja de ruta", f"<ol style='margin:0;padding-left:1.3em'>{pasos}</ol>", "ok")
            escuchar(" ".join(c["hoja_de_ruta"]))
            if c["servicio_sugerido"] in SERV:
                N.tarjeta(f"Apoyo que podría servirle · {SERV[c['servicio_sugerido']]}", "<b>Cómo acceder:</b> " + N.md(ACCESO.get(c["servicio_sugerido"], "")), "info")
            with st.container(border=True):
                q = st.radio("¿Quiere que **una persona** de la red de apoyo se comunique con usted? Es voluntario.", ["Sí, quiero que me contacten", "No, gracias"], index=None)
                util = st.select_slider("¿Le sirvió esta conversación?", ["Nada", "Poco", "Algo", "Mucho"], value="Algo")
                if st.button("Enviar respuesta", type="primary") and q:
                    N.registrar({"tipo": "decision_persona", "decision": q, "utilidad": util})
                    if q.startswith("Sí"): st.success(f"Listo. Se creó el caso {nuevo_caso(pid, c, 'conversación')}. Una persona lo revisará.")
                    else: st.info("Gracias por conversar. Si cambia de opinión, puede volver cuando quiera.")
            st.button("🔄 Nueva conversación", on_click=reiniciar)
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
            dec = st.radio("👤 Decisión humana (obligatoria)", ["Llamar hoy", "Visitar esta semana", "Derivar a otro servicio", "Cerrar sin acción"],
                           index=None, key=f"d_{cid}", horizontal=True)
            nota = st.text_input("Nota (opcional)", key=f"n_{cid}")
            if st.button("Registrar decisión", type="primary"):
                if not dec: st.warning("Elige una decisión: la IA no decide por ti.")
                else:
                    b["decision"] = dec; N.registrar({"tipo": "decision_humana", "caso": cid, "decision": dec, "nota": nota})
                    ss["_flash"] = f"{cid}: decisión registrada · **{dec}**"; st.rerun()
            if ss.get("_flash"): st.success(ss.pop("_flash"))
N.pie(ia)
