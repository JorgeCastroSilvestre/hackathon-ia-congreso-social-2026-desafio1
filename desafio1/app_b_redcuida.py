"""Desafío 1 · Variante B · RedCuida IA (panel de seguimiento para un equipo comunitario de cuidados).
Los equipos la personalizan en su copia de la planilla (pestañas `config` y `servicios_extra`)."""
import re, sys
from pathlib import Path
AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI.parent / "comun")); sys.path.insert(0, str(AQUI)); sys.path.insert(0, str(AQUI / "datos"))
import altair as alt
import numpy as np, pandas as pd, streamlit as st
import nucleo_st as N
import servicios as S
import generar_registros as G

N.iniciar("D1-B", "RedCuida IA", "", subtitulo="Envejecer con autonomía · Hackathon IA Aplicada · Congreso Social UC 2026", chip="Desafío 1 · Personas mayores")
N.acceso()
cfg, extra = N.configuracion(str(AQUI / "planillas" / "Plantilla_config_D1_Variante_B.xlsx"), "servicios_extra", S.validar_servicio)
catalogo = S.catalogo(AQUI, extra)

def numero(campo, defecto, lo, hi):
    try: return min(hi, max(lo, float(str(cfg.get(campo, defecto)).replace(",", "."))))
    except ValueError: return defecto
CUPO = int(numero("visitas_semana", 15, 5, 40))
PESOS = {s: numero(f"peso_{s}", d, 0, 10) for s, d in
         {"caida": 5, "desorientacion": 3, "come_poco": 2, "animo_bajo": 2, "medicamentos": 2, "aislamiento": 2, "cuidador_agotado": 3,
          "sospecha_maltrato": 5, "sin_contacto": 1.5, "vive_sola": 1}.items()}
VENTANA = 3  # semanas que cuentan como "recientes"
ETIQUETAS = {"caida": "caída", "desorientacion": "olvidos o desorientación", "come_poco": "come poco", "animo_bajo": "ánimo bajo",
             "medicamentos": "problemas con los remedios", "aislamiento": "no sale o dejó sus actividades", "cuidador_agotado": "quien cuida está agotado",
             "sospecha_maltrato": "sospecha de maltrato", "sin_contacto": "semanas sin contacto logrado", "vive_sola": "vive sola"}
ALERTAS = ("caida", "sospecha_maltrato")
CAMBIO = {"deterioro_gradual", "evento_agudo", "aislamiento", "sobrecarga_cuidador"}
GRUPOS = {"sector": "Sector", "tiene_telefono": "Teléfono", "vive_sola": "Vive sola", "sexo": "Sexo", "autonomia": "Autonomía"}
VALORES = {"tiene_telefono": {0: "Sin teléfono", 1: "Con teléfono"}, "vive_sola": {0: "Vive acompañada", 1: "Vive sola"}, "sexo": {"F": "Mujeres", "M": "Hombres"}}

@st.cache_resource(show_spinner="Ordenando los registros de la semana…")
def preparar(pesos: tuple, cupo: int):
    rp, rc = AQUI / "datos" / "personas_mayores_sinteticas.csv", AQUI / "datos" / "contactos_sinteticos.csv"
    if not (rp.exists() and rc.exists()):  # los CSV no se versionan: se regeneran iguales (semilla fija) la primera vez
        per, con = G.generar(); per.to_csv(rp, index=False, encoding="utf-8"); con.to_csv(rc, index=False, encoding="utf-8")
    per, con = pd.read_csv(rp), pd.read_csv(rc)
    pesos = dict(pesos)
    rec, ant = con[con.semana > G.SEMANAS - VENTANA], con[con.semana <= G.SEMANAS - VENTANA]
    ids = per.id_persona
    contrib = pd.DataFrame(index=ids)
    nuevas = {}
    for s in G.SENALES:
        n_rec = rec.groupby("id_persona")[s].sum().reindex(ids, fill_value=0)
        n_ant = ant.groupby("id_persona")[s].sum().reindex(ids, fill_value=0)
        nuevas[s] = (n_rec > 0) & (n_ant == 0)
        contrib[s] = pesos[s] * n_rec.clip(upper=2) * np.where(nuevas[s], 1.5, 1)  # una señal nueva para esa persona pesa más
    ultima = con[con.logrado == 1].groupby("id_persona").semana.max().reindex(ids, fill_value=0)
    per["semanas_sin_contacto"] = (G.SEMANAS - ultima).to_numpy()
    contrib["sin_contacto"] = pesos["sin_contacto"] * np.minimum(per.semanas_sin_contacto.to_numpy(), 6)
    contrib["vive_sola"] = pesos["vive_sola"] * per.vive_sola.to_numpy()
    per["puntaje"] = contrib.sum(axis=1).round(1).to_numpy()
    per["alerta"] = [", ".join(ETIQUETAS[s] for s in ALERTAS if rec[(rec.id_persona == i) & (rec[s] == 1)].shape[0]) for i in ids]
    def por_que(i):
        fila = contrib.loc[i]
        return "; ".join(ETIQUETAS[c] + (" (nuevo)" if c in nuevas and nuevas[c][i] else "") + (f": {per.set_index('id_persona').semanas_sin_contacto[i]}" if c == "sin_contacto" else "")
                         for c in fila.sort_values(ascending=False).index[:3] if fila[c] > 0)
    per["por_que"] = [por_que(i) for i in ids]
    per["contactos_registrados"] = con.groupby("id_persona").size().reindex(ids, fill_value=0).to_numpy()
    resto = per[per.alerta == ""].sort_values("puntaje", ascending=False)
    cola = pd.concat([per[per.alerta != ""].sort_values("puntaje", ascending=False), resto.head(cupo)]).reset_index(drop=True)
    cola["n"] = range(1, len(cola) + 1)
    # Equidad: a quién ve la lista (la trayectoria real solo se conoce en datos sintéticos)
    per["_en_lista"] = per.id_persona.isin(cola.id_persona)
    filas = []
    for col, nom in GRUPOS.items():
        for v, d in per.groupby(col):
            cam = d[d.trayectoria.isin(CAMBIO)]
            filas.append({"Grupo": nom, "Valor": VALORES.get(col, {}).get(v, str(v)), "Personas": len(d),
                          "Contactos por persona": round(d.contactos_registrados.mean(), 1), "En la lista (%)": round(100 * d._en_lista.mean(), 1),
                          "Cambios reales detectados (%)": round(100 * cam._en_lista.mean(), 1) if len(cam) else None})
    detect = per[per.trayectoria != "estable"].groupby("trayectoria").agg(Personas=("id_persona", "size"), Detectadas=("_en_lista", "sum")).reset_index()
    return cola.drop(columns=["trayectoria", "semana_inicio_cambio"]), con, pd.DataFrame(filas), detect, len(per)

cola, contactos, equidad, deteccion, n_total = preparar(tuple(PESOS.items()), CUPO)
cola = cola.copy()  # la caché es compartida entre equipos: cada sesión trabaja sobre su propia copia

def bitacora(pid, semanas=6):
    d = contactos[(contactos.id_persona == pid) & (contactos.semana > G.SEMANAS - semanas)]
    return "\n".join(f"- Semana {r.semana} · {r.tipo} ({r.registrado_por}){'' if r.logrado else ' · NO LOGRADO'}: {r.nota}"
                     + (f" [marcado: {', '.join(ETIQUETAS[s] for s in G.SENALES if getattr(r, s) == 1)}]" if any(getattr(r, s) == 1 for s in G.SENALES) else "")
                     for r in d.itertuples()) or "(sin contactos registrados en estas semanas)"
perfil_txt = lambda f: (f"- Edad: {f['edad']}\n- Sector: {f['sector']}\n- Vive sola: {'sí' if f['vive_sola'] else 'no'}\n- Teléfono: {'sí' if f['tiene_telefono'] else 'no'}\n"
                        f"- Autonomía: {f['autonomia']}\n- Quién la cuida: {f['cuidador_principal']}\n- Semanas sin contacto logrado: {f['semanas_sin_contacto']}\n"
                        f"- Monitor/a asignado/a: {f.get('monitor_asignado', 'sin dato')}")

# [fijo] Reglas fijas del prompt (los equipos solo agregan la personalización desde la planilla)
REGLAS = """Eres un asistente que apoya a quien coordina el acompañamiento comunitario de personas mayores en Chile a PREPARAR el próximo
contacto con una persona. No juzgas, no diagnosticas y no decides.
REGLAS FIJAS:
1. Lenguaje respetuoso: nunca uses diminutivos ("abuelito", "viejita") ni etiquetas como "caso problema" o "paciente difícil".
2. Describe solo lo que dicen los registros, citando la semana (por ejemplo, "semana 10"). No inventes causas ni datos. No nombres enfermedades ni diagnósticos.
3. Lee las notas completas: si una nota menciona algo importante que NO quedó marcado, dilo explícitamente.
4. Sugiere SOLO servicios del catálogo, citando su código entre corchetes, por ejemplo [S05].
5. La persona mayor decide sobre su vida: la sugerencia incluye conversar con ella directamente, no solo con su familia.
6. Si hay una posible caída o sospecha de maltrato, dilo primero y sugiere activar el protocolo del equipo; no investigues por tu cuenta.
7. La decisión final es de quien coordina.
8. Escribe en español de Chile, tuteando con "tú" a quien coordina (nunca "vos" ni formas como "elegís" o "tenés").
FORMATO: tres secciones con estos títulos: "1. Lo que muestran los registros", "2. Apoyos posibles", "3. Sugerencia para el próximo contacto"."""
PETICION = """Persona (ficticia):
{perfil}
Señales que más pesaron en el orden: {factores}
Registros de las últimas 6 semanas (nota escrita por quien hizo el contacto; entre corchetes, las casillas que marcó):
{bitacora}
Catálogo de servicios:
{catalogo}

Recuerda: cita la semana de cada registro que menciones y usa solo lo que dice el catálogo."""

DIAGNOSTICO = re.compile(r"\b(demencia|alzh?eimer|depresi[oó]n|parkinson|deterioro cognitivo|trastorno)\b|\bdiagn[oó]stic", re.I)
EDADISMO = re.compile(r"\b(abuelit[oa]s?|viejit[oa]s?|tatita|caso problema|paciente dif[ií]cil)\b", re.I)
def validar(texto):
    problemas = []
    codigos = set(re.findall(r"\[([A-Z]{1,3}\d{1,3})\]", texto))
    malos = sorted(c for c in codigos if c not in set(catalogo.id_servicio))
    if malos: problemas.append(f"cita servicios que no existen en el catálogo: {', '.join(malos)}")
    if not codigos: problemas.append("no cita ningún servicio del catálogo con su código")
    if DIAGNOSTICO.search(texto): problemas.append("nombra enfermedades o diagnósticos")
    if EDADISMO.search(texto): problemas.append("usa lenguaje infantilizante o etiquetas")
    if not re.search(r"semana\s+\d", texto, re.I): problemas.append("no cita la semana de los registros")
    return problemas

def secciones(texto):
    """Separa la propuesta en sus tres secciones para mostrarlas como tarjetas (si la IA no respetó el formato, devuelve None)."""
    partes = re.split(r"(?m)^\s*\**\s*([123])\.\s*", texto or "")
    if len(partes) < 7: return None
    d = {partes[i]: partes[i + 1].strip() for i in range(1, len(partes) - 1, 2)}
    limpiar = lambda s: re.sub(r"^(Lo que muestran los registros|Apoyos posibles|Sugerencia para el próximo contacto)\**\s*:?\s*", "", s, flags=re.I).strip()
    return [limpiar(d.get(k, "")) for k in "123"] if set(d) >= {"1", "2", "3"} else None

def demo(f):
    sug = {"caída": "S06", "maltrato": "S01", "olvidos": "S04", "come poco": "S05", "ánimo": "S02", "remedios": "S07", "no sale": "S03",
           "agotado": "S08", "sin contacto": "S02", "vive sola": "S02"}
    cods = list(dict.fromkeys(c for k, c in sug.items() if k in f["por_que"]))[:2] or ["S02"]
    nom = dict(zip(catalogo.id_servicio, catalogo.nombre))
    ult = contactos[contactos.id_persona == f["id_persona"]].semana.max()
    return (f"1. Lo que muestran los registros\nEn las últimas semanas (hasta la semana {ult if pd.notna(ult) else G.SEMANAS}) aparecen: {f['por_que']}. "
            f"Vive en sector {str(f['sector']).lower()}. Los registros no dicen por qué ocurre.\n\n2. Apoyos posibles\n" +
            "\n".join(f"- [{c}] {nom.get(c, '')}" for c in cods) +
            "\n\n3. Sugerencia para el próximo contacto\nVisitarla esta semana, preguntarle directamente cómo ha estado y qué necesita, "
            "y acordar con ella el siguiente paso.")
ia = N.IA({"ficha": {r["id_persona"]: demo(r) for _, r in cola.iterrows()}})
decisiones = N.estado_equipo("decisiones")
cola["decision"] = cola.id_persona.map(lambda i: decisiones.get(i, "Pendiente"))
OPCIONES = ["Visitar esta semana", "Llamar esta semana", "Activar protocolo", "Derivar a un servicio", "Seguir observando"]

# ------------------------------------------------------------------ pantalla
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
        if clave not in st.session_state:
            N.tarjeta("Propuesta de la IA", "Presiona el botón para que la IA lea las notas de las últimas semanas y prepare el próximo contacto: "
                      "qué muestran los registros, qué apoyos del catálogo podrían servir y qué hacer en la próxima visita o llamada.", "gray")
        else:
            texto, info = st.session_state[clave]
            N.aviso_si_demo(info)
            prob = validar(texto)
            if prob:
                st.error("La validación detectó problemas. Corrige el texto antes de usarlo: " + "; ".join(prob))
                N.registrar({"tipo": "validacion", "tarea": "ficha", "id_persona": sel, "nota": "; ".join(prob)})
            else:
                st.markdown(N.badge("Validación superada: cita registros y servicios del catálogo, sin diagnósticos", "green"), unsafe_allow_html=True)
            sec = secciones(texto)
            if sec:
                cods = [c for c in dict.fromkeys(re.findall(r"\[([A-Z]{1,3}\d{1,3})\]", sec[1])) if c in set(catalogo.id_servicio)]
                acceso = "".join(f"<br>{N.badge(c, 'teal')} {N.md(r.como_acceder)}" for c in cods for r in catalogo[catalogo.id_servicio == c].itertuples())
                N.tarjeta("1 · Lo que muestran los registros", N.md(sec[0]), "info")
                N.tarjeta("2 · Apoyos posibles", N.md(sec[1]) + (f"<br><br><b>Cómo se accede:</b>{acceso}" if acceso else ""), "ok")
                N.tarjeta("3 · Sugerencia para el próximo contacto", N.md(sec[2]), "warn" if prob else "ok")
            with st.expander("Revisar y editar el texto antes de usarlo", expanded=not sec):
                st.text_area("Propuesta de la IA", texto, height=260, key=f"ta_{sel}", label_visibility="collapsed")
            with st.container(border=True):
                st.markdown("#### Decisión humana (obligatoria)")
                dec = st.radio("¿Qué decides?", OPCIONES, index=None, key=f"dec_{sel}", horizontal=True)
                util = st.select_slider("¿La propuesta te ahorró trabajo?", ["Nada", "Poco", "Algo", "Mucho"], value="Algo", key=f"ut_{sel}")
                nota = st.text_input("Nota (opcional)", key=f"nota_{sel}")
                if st.button("Registrar decisión", width="stretch"):
                    if not dec: st.warning("Elige una decisión: la IA no decide por ti.")
                    else:
                        decisiones[sel] = dec
                        N.registrar({"tipo": "decision_humana", "tarea": "ficha", "id_persona": sel, "decision": dec, "utilidad": util,
                                     "nota": nota, "salida": st.session_state.get(f"ta_{sel}", texto)})
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
