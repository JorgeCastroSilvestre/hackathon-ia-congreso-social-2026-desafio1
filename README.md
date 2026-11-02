# Hackathon IA Aplicada · Congreso Social UC 2026 · Desafío 1 · Envejecer con autonomía

Plantillas del Desafío 1 (IA para el cuidado comunitario de personas mayores). Cada equipo recibe una app que **ya funciona** y la adapta a un usuario real desde una planilla de Google, sin programar. Usa la misma base técnica que las plantillas del [Desafío 2](https://github.com/Giocrisrai/hackathon-ia-congreso-social-2026-desafio2): código y clave por equipo, pestaña `config`, pestaña `servicios_extra` con fila EJEMPLO, botón "Recargar configuración" y un límite de consultas a la IA por equipo.

**Versión demo. Todos los datos son ficticios.**

| Variante | Para quién | Qué hace |
|---|---|---|
| A · ConectaMayor IA | Persona mayor o alguien cercano que la acompaña | Conversación en lenguaje claro que entiende la necesidad, entrega una hoja de ruta y, si la persona quiere, deja el caso en una bandeja para una persona |
| B · RedCuida IA | Quien coordina un equipo comunitario de cuidados | Lee 12 semanas de registros de visitas y llamadas, ordena a quién le está cambiando algo, explica por qué y prepara el próximo contacto |

**Principio de diseño:** la IA orienta y aporta evidencia; las personas deciden, acompañan y cuidan.

## Documentación
| Para | Documento |
|---|---|
| Descripción completa, protecciones, datos y limitaciones | [README del Desafío 1](desafio1/docs/README_Desafio1.md) |
| Rutas de mejora | [Variante A](desafio1/docs/Rutas_de_mejora_Variante_A.md) · [Variante B](desafio1/docs/Rutas_de_mejora_Variante_B.md) |

## Estructura
```
comun/nucleo_st.py              núcleo común: acceso por equipo, lectura de la planilla, IA multi-proveedor,
                                registro, límite de consultas, protocolo de crisis y diseño
desafio1/app_a_conectamayor.py  Variante A · ConectaMayor IA
desafio1/app_b_redcuida.py      Variante B · RedCuida IA
desafio1/servicios.py           catálogo de servicios y validación de servicios_extra
desafio1/datos/                 catálogo, perfiles para simular y generador de registros sintéticos (semilla 2026)
desafio1/planillas/             planilla base de cada variante, un CSV por pestaña
desafio1/docs/                  documentación del desafío
.streamlit/                     tema visual y plantilla de secrets (secrets.toml nunca se sube)
```

## Ejecutar en local
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run desafio1/app_a_conectamayor.py   # o desafio1/app_b_redcuida.py
```
Sin `.streamlit/secrets.toml` se entra con código `demo` y clave `demo`, y la app usa respuestas de demostración. Para conectar la IA, copien `.streamlit/secrets.example.toml` como `.streamlit/secrets.toml` y agreguen su clave (por ejemplo, de Groq).

## Despliegue
1. En https://share.streamlit.io, crear dos apps desde este repositorio, rama `main`, Python 3.12, con *Main file* `desafio1/app_a_conectamayor.py` y `desafio1/app_b_redcuida.py`.
2. En cada app, **Settings → Secrets**: pegar `.streamlit/secrets.example.toml` con las claves de IA y un bloque `[equipos.EXX]` por equipo.
3. Subir las planillas base (`desafio1/planillas/`) a Google Drive como Hojas de cálculo, con las pestañas `config` y `servicios_extra`, y compartirlas como Lector.

## Antes del evento
- Verificar con fuentes oficiales y con la organización beneficiaria la forma de acceso de cada servicio del catálogo (`desafio1/datos/catalogo_servicios.csv`).
- Completar la ficha de línea base, el diccionario de datos, los riesgos éticos, la guía de mentores y la prueba piloto.

## Licencia
Código bajo licencia MIT; datos sintéticos, planillas y documentación bajo CC BY 4.0. Ver [LICENSE](LICENSE). El núcleo común (`comun/`) proviene de las plantillas del Desafío 2.
