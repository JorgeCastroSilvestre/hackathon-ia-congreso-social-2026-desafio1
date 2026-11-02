# Desafío 1 · Envejecer con autonomía

Hackathon IA Aplicada · Congreso Social UC 2026 · **Versión demo**

Dos plantillas que **ya funcionan** para que equipos interdisciplinarios las adapten a una persona real desde una planilla de Google, sin programar. Usan la misma base técnica que el Desafío 2 (`comun/nucleo_st.py`: acceso por equipo, planilla, IA con varios proveedores, registro, límite de consultas y modo demo), pero el problema, los datos y las protecciones son propios del cuidado de personas mayores.

**Principio de diseño:** la IA orienta y aporta evidencia; las personas deciden, acompañan y cuidan. **Todos los datos son ficticios.**

| | A · ConectaMayor IA | B · RedCuida IA |
|---|---|---|
| Archivo | `desafio1/app_a_conectamayor.py` | `desafio1/app_b_redcuida.py` |
| Usuario | Persona mayor o alguien cercano que la acompaña | Coordinadora de un equipo comunitario (monitores y voluntarios) |
| Qué hace | Conversación en lenguaje claro que entiende la necesidad, entrega una **hoja de ruta** y, si la persona quiere, deja el caso en una bandeja para una persona | Lee 12 semanas de registros de visitas y llamadas de 120 personas, ordena **a quién le está cambiando algo**, explica por qué y prepara el próximo contacto |
| Quién decide | La persona mayor (pide o no contacto) y la red de apoyo (revisa la bandeja) | Quien coordina registra la decisión |

## Cómo ejecutarlas en local
```powershell
.\.venv\Scripts\Activate.ps1
streamlit run desafio1/app_a_conectamayor.py   # o desafio1/app_b_redcuida.py
```
Sin `[equipos.*]` en `.streamlit/secrets.toml` se entra con código `demo` y clave `demo`. Sin clave de IA, la app responde con textos de demostración.

## Variante A · ConectaMayor IA
- **Antes de empezar:** consentimiento y elección de quién conversa (*hablo por mí* / *hablo por alguien a quien acompaño*); cambia las instrucciones de la IA.
- **Accesibilidad:** tamaño de letra configurable, botones con frases listas para quien no quiere escribir y botón **🔊 Escuchar** (voz del navegador, sin costo).
- **Al terminar:** hoja de ruta de 2 a 3 pasos en lectura fácil, servicio sugerido con su forma de acceso y pregunta voluntaria de contacto.
- **Medición incluida:** palabras por frase de la IA (referencia de lectura fácil: 15 o menos).

### Protecciones fijas (no se cambian desde la planilla)
- **Protocolo de maltrato** (golpes, gritos, encierro, le controlan la pensión o los remedios, miedo a un familiar…): mensaje fijo con **Fono Mayor 800 400 035** y **133**, y caso prioritario en la bandeja.
- **Protocolo de emergencia** (caída sin poder levantarse, dolor en el pecho, ganas de morir o de no despertar, sentirse una carga): **131 SAMU**, **\*4141**, **Salud Responde 600 360 7777**, **133**.
- **Dos redes de detección:** primero, una lista de frases revisada en el código antes de consultar a la IA; después, si la IA reconoce una señal dicha de forma indirecta, responde con una marca (`[MALTRATO]` o `[EMERGENCIA]`) que la app reemplaza por el mismo mensaje fijo. En ambos casos el texto de ayuda no lo escribe la IA.
- **Sin indicaciones de salud:** si la IA nombra un diagnóstico o da instrucciones sobre medicamentos (dosis, suspender, juntar pastillas), la respuesta se reemplaza por una derivación a Salud Responde.
- **Sin edadismo:** las reglas prohíben diminutivos ("abuelito", "viejita"); si aparecen, queda registrado y se avisa.
- Solo servicios del catálogo y solo la forma de acceso escrita en el catálogo.

## Variante B · RedCuida IA
- **Lista de la semana:** primero las **alertas** (caída o sospecha de maltrato en las últimas 3 semanas), que no ocupan cupo; después las personas con mayor puntaje hasta completar `visitas_semana`.
- **Puntaje transparente con pesos editables:** suma de *peso × veces que se marcó la señal en las últimas 3 semanas* (×1,5 si es nueva para esa persona) + semanas sin contacto logrado + vive sola. Se compara a cada persona con su propia historia. No usa sexo, edad ni sector.
- **Ficha con IA:** lee las notas de las últimas 6 semanas y prepara *Lo que muestran los registros · Apoyos posibles · Sugerencia para el próximo contacto*. La validación exige citar la semana y servicios del catálogo, y bloquea diagnósticos y lenguaje infantilizante.
- **¿A quién no estamos viendo?:** compara por sector, teléfono, vive sola, sexo y autonomía cuántos contactos tiene cada grupo, cuántos entran en la lista y qué parte de las personas a las que **realmente** les está cambiando algo detecta.

## Qué cambian los equipos
| Pestaña | A · ConectaMayor | B · RedCuida |
|---|---|---|
| `config` (van al prompt) | usuario, tono (incluido **tú o usted**), largo_respuesta, ejemplos, instrucciones_extra | usuario, tono, largo_respuesta, ejemplos, instrucciones_extra |
| `config` (solo pantalla y reglas de la app) | títulos, mensaje_inicial, texto_consentimiento, max_turnos, **tamano_letra**, **respuestas_rapidas** | títulos, **visitas_semana**, **10 pesos** del puntaje |
| `servicios_extra` | Servicios reales de su comuna, con fuente oficial | Ídem |

## Datos
| Archivo | Contenido |
|---|---|
| `datos/catalogo_servicios.csv` | 10 servicios base (S01–S10), compartidos por ambas variantes |
| `datos/personas_conectamayor.csv` | 7 perfiles ficticios para simular conversaciones (A) |
| `datos/generar_registros.py` | Generador de 120 personas y unas 1.200 notas de contacto en 12 semanas (B), semilla 2026. Los CSV se crean solos la primera vez y no se versionan |

El generador incluye a propósito lo que hace difícil el cuidado comunitario real:
- **Trayectorias ocultas** (estable, mejora, deterioro gradual, caída, aislamiento progresivo, sobrecarga de quien cuida) para medir si la lista detecta a quien cambia.
- **1 de cada 4 señales queda solo en la nota** (no se marcó la casilla): el puntaje no la ve; la IA y las personas sí, si leen.
- **Sesgo de registro:** las personas rurales tienen unos 5 contactos en 12 semanas frente a unos 12 en zonas urbanas, y las que no tienen teléfono solo reciben visitas.

## Limitaciones conocidas (base para las rutas de mejora)
Con la configuración base:
- **B:** la lista detecta a 1 de 8 personas en aislamiento progresivo y a 2 de 12 con sobrecarga de quien cuida; las caídas de las semanas 8 y 9 quedan fuera de la ventana de 3 semanas.
- **B:** las señales que solo están en las notas no suben el puntaje.
- **A:** la red de seguridad no es perfecta. En pruebas, la lista de frases reconoció 12 de 12 frases de maltrato o emergencia, con 1 falso positivo en 8 frases parecidas ("me grita el vendedor de la feria"). La IA reconoció formas indirectas de abuso económico y de sentirse una carga, pero no un caso de abandono ("me dejaron sola dos semanas y no puedo cocinar"). Su respuesta además varía de una vez a otra.
- **A y B:** el catálogo es genérico; la forma de acceso de cada servicio **debe verificarse** con fuentes oficiales y con la organización beneficiaria antes del evento.

## Pendiente para la versión final
Rutas de mejora: listas en [Rutas_de_mejora_Variante_A.md](Rutas_de_mejora_Variante_A.md) y [Rutas_de_mejora_Variante_B.md](Rutas_de_mejora_Variante_B.md), 6 por variante.

Falta: README de una página por variante, ficha de línea base, diccionario de datos, riesgos éticos, guía de mentores, prueba piloto de inclusión y despliegue en Streamlit Cloud.
