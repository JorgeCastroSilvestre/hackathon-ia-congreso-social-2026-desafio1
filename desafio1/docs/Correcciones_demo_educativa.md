# Correcciones de la revisión de la demo educativa

Base: `7864b14`. Rama local: `codex/correcciones-demo-educativa`.
Los cambios se entregan localmente; no se hizo push ni se reiniciaron las apps publicadas.

## Cambios aplicados

| Hallazgo | Archivo y función o bloque | Resultado |
|---|---|---|
| Texto editable sin validar | `comun/nucleo_st.py`, `configuracion()`; `comun/validaciones.py`, `texto_inseguro()`; `desafio1/servicios.py`, `validar_servicio()` | Títulos, bienvenida, botón, saludo inicial, consentimiento y respuestas rápidas se revisan antes de mostrarse. Se usa la plantilla segura o un respaldo fijo si se detecta un problema. Las filas extra de servicios con texto inseguro se rechazan. El reemplazo de configuración queda registrado una vez por contenido y sesión. |
| Emergencia pendiente pierde prioridad | `desafio1/app_a_conectamayor.py`, `nuevo_caso()` | Se consideran tanto los casos confirmados como los pendientes. Se conserva la urgencia mayor junto con su resumen, origen y servicio; la conversación se actualiza. El reintento mantiene un solo caso. |
| Aviso de persistencia incorrecto | `comun/nucleo_st.py`, `estado_equipo()` y `aviso_demo()` | Estados explícitos: sin verificar, temporal, central y error. Una lectura fallida no reutiliza un modo anterior ni se presenta como temporal. La recuperación limpia el error previo. |
| Origen del contenido incorrecto | `desafio1/app_a_conectamayor.py`, historial, respuesta y clasificación; `desafio1/app_b_redcuida.py`, edición y decisión; `comun/nucleo_st.py`, `aviso_si_demo()` | Cada mensaje del asistente identifica su origen. La hoja de ruta reemplazada por clasificación local se identifica como local. Una propuesta editada en B se identifica como edición humana y guarda ese origen junto con la decisión. Los metadatos del historial no se envían al proveedor de IA. |
| Falsos positivos en medicación | `comun/validaciones.py`, `MEDICACION` | Una pregunta como «Pregúntele si toma medicamentos» o una descripción como «La persona toma sus medicamentos con apoyo» no se confunde con una indicación. Se conservan los filtros de dosis y órdenes de suspender, aumentar o juntar medicamentos, y se prueban instrucciones directas de toma. |
| Guías con letra pequeña forzada | `comun/nucleo_st.py`, CSS `.card.guia`; `desafio1/app_a_conectamayor.py`, estilo de accesibilidad | Las guías usan la variable de tamaño configurada en A, sin imponer `.88rem !important`. |

No se cambian nombres de campos, columnas de las planillas, dependencias ni
patrones fijos de maltrato/emergencia. No se agregan claves ni servicios externos.
Los filtros de lenguaje siguen siendo reglas heurísticas: no garantizan detectar
todas las formas posibles de una indicación o una expresión problemática.

## Verificación

Resultado local: **28 de 28 pruebas aprobadas**, compilación correcta y
`git diff --check` sin errores.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q comun desafio1 tests
git diff --check
```

Las pruebas nuevas están en `tests/test_correcciones_demo.py`. Ejercitan los
fallos reproducidos con AppTest, planillas simuladas e IA simulada; no consumen
cuota ni escriben en Google. Incluyen preguntas descriptivas permitidas e
indicaciones bloqueadas, edición humana y exclusión de metadatos del prompt.

La navegación real no se sustituye en el producto. En AppTest se conserva el
doble de contenedores del conjunto anterior por la limitación de
`segmented_control`. La comprobación visual local de A confirmó letra de
19,2 px en las tres guías con la configuración «grande», y se inspeccionó la
vista de 390 px de ancho. No se completó el recorrido manual móvil ni se
verificaron las pantallas internas publicadas, Google real o IA real.

## Pruebas manuales para el mentor

1. **Textos de planilla:** en una copia de prueba, cambiar `mensaje_inicial` por
   un texto infantilizante o una indicación de medicamentos y recargar. Iniciar
   conversación: debe aparecer un aviso de reemplazo y un saludo seguro. Repetir
   con un saludo respetuoso: debe conservarse e identificarse como configuración.
2. **Emergencia y reintento:** en una instalación de prueba, provocar un fallo de
   escritura y simular una emergencia; después enviar una frase de maltrato.
   Recuperar la conexión y reintentar: debe quedar un único caso con urgencia de
   emergencia. No retirar permisos de la instalación compartida durante el evento.
3. **Aviso de almacenamiento:** en una instalación de prueba con central,
   provocar una lectura fallida después de una exitosa. Debe mostrar almacenamiento
   no verificado; al recuperar la conexión debe volver a central. Una instalación
   realmente sin configuración debe indicar temporal.
4. **Origen:** en A, comparar el saludo, una respuesta preparada y un protocolo:
   cada uno debe identificar su origen. En B, generar una ficha, editarla y
   registrar una decisión: debe indicarse edición humana.
5. **Medicación:** en B, agregar «Pregúntele si toma medicamentos» a una ficha
   válida y registrar una decisión: debe permitirse. Sustituirla por «Tome dos
   pastillas juntas»: debe bloquearse.
6. **Letra:** configurar A con «muy grande» y recargar. Revisar aviso, recorrido,
   límites y conversación en un celular y en escritorio: deben respetar el tamaño
   seleccionado.

## Despliegue

**Se modifica el núcleo común: al publicar, reiniciar ambas apps.**
Antes de publicar, descargar el respaldo del estado y el registro de cada equipo
con trabajo que se quiera conservar. En modo temporal, el reinicio borra casos y
decisiones; descargarlos no equivale a importarlos automáticamente después.
La configuración de Google y las pruebas con mentor se deben verificar en la
instalación real. Esta entrega no ejecuta el despliegue.
