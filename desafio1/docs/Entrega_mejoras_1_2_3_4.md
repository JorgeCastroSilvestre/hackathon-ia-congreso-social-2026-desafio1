# Cambios 1, 2, 3 y 4 · preparados para revisión

Base: `main`, commit `cb8fdcd5e8d775ade5e2fb60f09f7bad6f848ccc`.
Rama local: `codex/seguridad-persistencia-d1`. No se ha publicado ni reiniciado ninguna app.

## Archivos y lugares exactos

Los archivos Python entregados contienen el código completo listo para reemplazar
los archivos equivalentes del repositorio; no requieren ensamblar fragmentos.
El documento `Bloques_completos_1_2_3_4.md` reproduce además cada bloque superior
modificado completo, con su ubicación en la versión entregada.

| Archivo | Función o bloque | Cambio |
|---|---|---|
| `comun/nucleo_st.py` | Importaciones; desde `identidad_equipo()` hasta `cerrar_sesion()` | Identidad por código, recuperación y guardado del estado, limpieza completa de sesión |
| `comun/nucleo_st.py` | `registrar()`, `_copiar_central()`, `registro_equipo()` | Código de equipo en registro local, manejo de error local, escritura RAW y separación de las pestañas de registro y estado |
| `comun/nucleo_st.py` | `acceso()` | Limpieza al ingresar; código explícito para DEMO |
| `comun/nucleo_st.py` | `IA._k()`, `IA.proveedores()` y `pie()` | Cuota por código, texto sin emoji, respaldo JSON y salida con limpieza completa |
| `comun/persistencia.py` | Archivo nuevo completo | Eventos de un elemento; reconstrucción por app/equipo; IDs estables para reintentos |
| `comun/validaciones.py` | Archivo nuevo completo | Filtros adicionales y normalización de JSON |
| `desafio1/app_a_conectamayor.py` | Importaciones, ampliación de `_MALTRATO` / `_EMERGENCIA`, inicialización de `bandeja` | Conserva las expresiones fijas originales y agrega expresiones concretas; recupera estado |
| `desafio1/app_a_conectamayor.py` | `reiniciar()`, `nuevo_caso()`, `inseguro()` | Un ID por conversación, reintento y bloqueo de textos inseguros |
| `desafio1/app_a_conectamayor.py` | Pantalla principal completa, desde `N.encabezado(...)` hasta `N.pie(ia)` | Casos pendientes de guardar, reemplazo de edadismo, JSON validado, envío único, persistencia de decisión y respaldo |
| `desafio1/app_b_redcuida.py` | Importaciones, `validar()`, inicialización de `decisiones_completas` | Medicación y edadismo; recuperación de decisiones completas |
| `desafio1/app_b_redcuida.py` | Pantalla principal completa, desde `N.encabezado(...)` hasta `N.pie(ia)` | Valida el texto editado, bloquea registro inválido, persiste decisión, nota y propuesta |
| `tests/test_seguridad.py`, `tests/test_streamlit.py` | Archivos nuevos completos | Pruebas sin llamadas a IA ni escrituras en Google |

**Toca el núcleo común. Se deben reiniciar las dos apps después del despliegue,
una vez respaldado el trabajo actual y preparada la planilla central.**
No cambia el contrato de `config` ni de `servicios_extra`. No agrega dependencias.
No cambia pesos, cupos, catálogo ni reglas fijas del prompt.

## Antes de desplegar: rescatar lo que está en las apps actuales

La versión anterior solo mantiene la bandeja y las decisiones en memoria.
Actualizar el código puede reiniciar el proceso: no hacer push antes del respaldo.
La nueva versión no puede recuperar memoria que ya se perdió.

1. En cada código de equipo con trabajo que se quiera conservar, descargar el
   registro actual. En A, copiar además la tabla de bandeja, el resumen y la
   conversación completa de cada caso; en B, copiar decisión, nota y texto editado.
   El registro viejo por sí solo NO es un respaldo completo: la copia central
   omite caso/id_persona y los eventos de creación no contienen todo el caso.
2. Guardar esas copias fuera de Streamlit y comprobar que se pueden abrir.
3. Desplegar solo después. Esta entrega no incluye una importación automática
   de datos antiguos: conservar las copias como evidencia y planificar su carga
   si se necesita continuar esos casos dentro de la nueva app. Las sesiones
   de conversación que no generaron caso tampoco se recuperan automáticamente.

## Preparar la persistencia gratuita

Usar una planilla **central privada**, distinta de las copias públicas de
configuración de los equipos. Compartirla como Editor solo con el correo de la
cuenta de servicio y con las personas responsables de administrarla.

1. Conservar la pestaña actual del registro como primera pestaña. Si se crea una
   planilla nueva, crear primero `registro`, con las columnas históricas:

   ```text
   marca_tiempo | app | equipo | tipo | tarea | modo | proveedor | entrada | salida | decision | nota
   ```

2. Agregar una pestaña nueva llamada exactamente `estado_d1_v1`. En A1:G1 poner,
   una columna por celda y en este orden:

   ```text
   evento_id | fecha_utc | app | equipo_codigo | coleccion | elemento_id | datos_json
   ```

   No dejar columnas adicionales en la cabecera ni editar manualmente los eventos.
   La app valida el esquema y no crea ni modifica pestañas automáticamente.

3. En **Settings → Secrets de ambas apps**, configurar el mismo
   `[registro] sheet_id` y el bloque completo `[gcp_service_account]` de la cuenta
   de servicio, siguiendo el formato de gspread. Conservar el resto de secrets.
   No pegar credenciales en código, planillas públicas o GitHub.

Si ambos valores están ausentes, la app funciona en modo temporal y lo advierte.
Si solo existe uno, la pestaña no existe, el esquema es incorrecto o falla Google,
se avisa del error y no se confirma un guardado remoto. Un caso de protocolo
pendiente se conserva en la sesión y puede descargarse para respaldo y reintentarse.
La memoria de esa sesión sigue dependiendo del navegador/proceso hasta guardarlo.

Se agrega una fila por operación y por elemento, sin reemplazar toda la bandeja.
Casos distintos no se sobrescriben. Para dos decisiones simultáneas sobre el
mismo elemento prevalece la última fila aceptada por Sheets; no hay control de
versiones ni bloqueo entre procesos. Un timeout puede dejar una escritura aceptada
sin confirmación: el reintento conserva el ID y comprueba si ya se escribió.
Las cuotas y latencia de Google siguen aplicando; es una solución para el evento,
no una base de datos de producción.

## Pruebas manuales en las apps publicadas

Son pruebas pendientes de realizar tras desplegar, con datos ficticios y un
código de mentor autorizado. Las pruebas locales no validan los permisos reales
de la planilla ni el despliegue de Community Cloud.

### 1 · Aislamiento de sesión

1. Ingresar como M01, aceptar consentimiento en A y generar una conversación;
   en B preparar y editar una ficha. Salir en cada app.
2. Ingresar como otro mentor autorizado. Confirmar ausencia del historial,
   consentimiento, propuesta editada y URL de configuración anteriores.
3. Volver a M01: sus casos/decisiones confirmados deben recuperarse desde Google;
   el chat en curso y el consentimiento deben comenzar de nuevo.

### 2 · Validación del texto y del resumen

1. En la copia de configuración de prueba de A, pedir en `instrucciones_extra`
   lenguaje infantilizante; en B generar una ficha y editarla agregando
   «Tome dos pastillas juntas» o «su abuelita tiene demencia».
2. En A, si el modelo produce ese lenguaje, comprobar que se reemplaza y queda
   el evento de validación. En B, intentar registrar: debe impedirlo y mostrar
   los motivos. La IA puede obedecer las reglas fijas y no producir el texto:
   eso también es correcto; la ruta de reemplazo se prueba de forma local.
3. Corregir B, elegir una decisión humana y guardar. Restaurar la personalización
   de A. La robustez ante JSON mal tipado se cubre en pruebas locales, porque no
   se puede exigir una respuesta malformada reproducible al proveedor real.

### 3 · Persistencia y fallos de conexión

1. Con el mentor, crear un caso en A y registrar una decisión en B. Verificar sus
   eventos, código de equipo e identificadores en `estado_d1_v1`; descargar respaldos.
2. Reiniciar las dos apps en Manage app → Reboot. Reingresar con el mismo código:
   deben recuperarse casos, decisiones y notas. Otro mentor no debe ver esos casos.
3. Solo en un despliegue de prueba, retirar temporalmente el permiso de la cuenta
   de servicio: intentar guardar debe mostrar error sin éxito. Restaurar permisos,
   recargar y reintentar; debe recuperarse y no duplicarse el caso. No retirar
   permisos de la planilla compartida durante la actividad de los equipos.

### 4 · Protocolos y duplicados

1. En A, iniciar conversación con consentimiento y escribir «Me dejaron sin comida
   y no puedo cocinar». Confirmar respuesta fija, caso prioritario y contador de IA
   sin aumentar por ese mensaje.
2. Terminar y solicitar contacto. Repetir interacciones: debe mantenerse un solo
   identificador de caso para esa conversación. Abrir una nueva conversación y
   comprobar que usa otro identificador.
3. Probar «Vivo sola y cocino todos los días»: no debe activar el protocolo fijo.
   La IA puede reconocer otras señales del contexto; usar una conversación nueva.

## Límites que siguen vigentes

- Los filtros por expresiones no garantizan detectar todo el maltrato o toda
  indicación médica. Se preservan los patrones antiguos, incluidos sus falsos
  positivos conocidos; las nuevas expresiones se prueban con ejemplos cotidianos.
- Los mensajes fijos de ayuda permanecen intactos. Esta entrega no verifica
  vigencia, alcance ni horarios de los servicios de ayuda del catálogo.
- La cuota de IA sigue en memoria y se reinicia con el proceso. Lo persistido aquí
  son casos y decisiones, no contadores de facturación ni chats inconclusos.
- No se publican ni reinician apps desde esta entrega. Hace falta verificar la
  planilla real y ejecutar las pruebas manuales con el mentor antes de usarlas.

## Verificación local realizada

Python 3.12 y Streamlit 1.50.0, con las dependencias de `requirements.txt`.
Pasaron **13 pruebas**: diez de lógica y tres de interacción con AppTest.
También pasaron la compilación de los módulos y `git diff --check`.

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q comun desafio1 tests
```

Las pruebas de interacción usan una hoja simulada y modo demostración, sin
consumir IA ni escribir en Google. Incluyen códigos M01/M02 con el mismo nombre
visible para comprobar que el aislamiento depende del código. La navegación
`N.pestanas` se sustituye solo dentro de esas pruebas por contenedores: AppTest
1.50 tiene una limitación al serializar `segmented_control`. No se verifica con
AppTest la navegación, el CSS, un celular real ni el audio. La función de
navegación del producto sigue intacta.
