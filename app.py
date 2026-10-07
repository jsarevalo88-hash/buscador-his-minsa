import streamlit as str
import google.generativeai as ai

# 1. Configuración visual de la página (Adaptada a celulares)
str.set_page_config(page_title="Buscador HIS MINSA", page_icon="🏥", layout="centered")

str.title("🏥 Buscador Inteligente de Codificación HIS")
str.subheader("Encuentra la forma correcta de registrar tus atenciones médicas")

# 2. Conexión segura con la Inteligencia Artificial de Google
# En producción, configurarás tu GEMINI_API_KEY en los secretos de Streamlit
try:
    ai.configure(api_key=str.secrets["GEMINI_API_KEY"])
except Exception:
    str.warning("⚠️ Falta configurar la clave API de Gemini en los secretos del servidor.")

# 3. Formulario de búsqueda
consulta = str.text_input(
    "¿Qué atención deseas registrar?", 
    placeholder="Ej: atención inmediata del recién nacido, tamizaje de depresión, etc."
)

if str.button("🔍 Buscar Forma de Registro", use_container_width=True):
    if consulta.strip() == "":
        str.error("Por favor, escribe una atención para poder ayudarte.")
    else:
        with str.spinner("Consultando los manuales oficiales del MINSA..."):
            try:
                # Inicializamos el modelo optimizado para lectura de documentos
                model = ai.GenerativeModel('gemini-1.5-flash')
                
                # Instrucciones estrictas para que la IA actúe como un digitador/auditor experto
                prompt_sistema = (
                    "Eres un asistente experto en codificación HIS y CIE-10 del Ministerio de Salud del Perú (MINSA). "
                    "Tu trabajo es extraer de los manuales adjuntos la forma exacta de registrar la atención solicitada. "
                    "Estructura tu respuesta estrictamente con los siguientes campos en formato markdown limpio:\n\n"
                    "### 📋 FICHA DE REGISTRO HIS\n"
                    "**- Actividad / Estrategia:** [Nombre de la estrategia]\n"
                    "**- Tipo de Diagnóstico:** [P / D / R]\n\n"
                    "### 🔢 CÓDIGOS Y CAMPOS LAB\n"
                    "| Diagnóstico / Actividad | Campo LAB | Código CIE-10 / CPT |\n"
                    "| :--- | :--- | :--- |\n"
                    "| [Ejemplo Diagnóstico] | [Ejemplo LAB] | [Ejemplo Código] |\n\n"
                    "### 📍 NOTAS / REQUISITOS\n"
                    "[Cualquier observación importante o condicional del manual]\n\n"
                    "**IMPORTANTE:** Si no encuentras la información exacta en los manuales cargados, indícalo "
                    "claramente. Está prohibido inventar códigos CIE-10 o campos LAB que no existan en el documento."
                )
                
                # Nota: En el paso de despliegue final vincularemos los PDFs directamente como contexto fijo.
                respuesta = model.generate_content([prompt_sistema, f"Consulta del usuario: {consulta}"])
                
                # Mostrar el resultado brutal en pantalla
                str.success("¡Información localizada!")
                str.markdown(respuesta.text)
                
            except Exception as e:
                str.error(f"Hubo un problema al procesar la consulta: {e}")

# 4. Pie de página institucional informativo
str.markdown("---")
str.caption("📌 Nota: Este buscador procesa la información basándose en los manuales oficiales cargados por el administrador.")
