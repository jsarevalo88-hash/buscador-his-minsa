import streamlit as st
import google.generativeai as ai

# 1. Configuración visual de la página
st.set_page_config(page_title="Buscador HIS MINSA", page_icon="🏥", layout="centered")

# 2. Conexión segura con la Inteligencia Artificial de Google
try:
    ai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception:
    st.warning("⚠️ Falta configurar la clave API de Gemini en los secretos del servidor.")

# 3. Panel de Administración Lateral para subir PDFs
with st.sidebar:
    st.header("⚙️ Panel de Administración")
    st.subheader("Cargar o Actualizar Manuales HIS")
    
    archivos_subidos = st.file_uploader(
        "Sube los manuales oficiales en formato PDF:", 
        type=["pdf"], 
        accept_multiple_files=True,
        help="Los archivos subidos se procesarán para alimentar el buscador inteligente."
    )
    
    if archivos_subidos:
        st.success(f"📚 {len(archivos_subidos)} manual(es) cargado(s) temporalmente.")
        st.info("La IA procesará estos documentos como contexto para responder las consultas.")

# 4. Interfaz Principal del Buscador
st.title("🏥 Buscador Inteligente de Codificación HIS")
st.subheader("Encuentra la forma correcta de registrar tus atenciones médicas")

consulta = st.text_input(
    "¿Qué atención deseas registrar?", 
    placeholder="Ej: atención inmediata del recién nacido, tamizaje de depresión, etc."
)

if st.button("🔍 Buscar Forma de Registro", use_container_width=True):
    if consulta.strip() == "":
        st.error("Por favor, escribe una atención para poder ayudarte.")
    else:
        with st.spinner("Analizando los manuales del MINSA cargados..."):
            try:
                # Usamos el modelo estándar definitivo compatible con la versión actual
                model = ai.GenerativeModel('gemini-2.5-flash')
                
                prompt_sistema = (
                    "Eres un asistente experto en codificación HIS y CIE-10 del Ministerio de Salud del Perú (MINSA).\n"
                    "Tu única tarea es extraer de los documentos proporcionados la forma exacta de registrar la atención solicitada.\n\n"
                    "Estructura tu respuesta estrictamente con el siguiente formato markdown:\n\n"
                    "### 📋 FICHA DE REGISTRO HIS\n"
                    "**- Actividad / Estrategia:** [Nombre de la estrategia sanitaria]\n"
                    "**- Tipo de Diagnóstico:** [P / D / R]\n\n"
                    "### 🔢 CÓDIGOS Y CAMPOS LAB\n"
                    "| Diagnóstico / Actividad | Campo LAB | Código CIE-10 / CPT |\n"
                    "| :--- | :--- | :--- |\n"
                    "| [Nombre de la actividad] | [Valor de campo LAB] | [Código] |\n\n"
                    "### 📍 NOTAS / REQUISITOS\n"
                    "[Observación importante del manual]\n\n"
                    "**REGLA CRÍTICA:** Si los documentos adjuntos no contienen la información específica, responde "
                    "únicamente: 'La atención solicitada no se encuentra registrada en los manuales actualmente cargados.' "
                    "Está estrictamente prohibido inventar códigos o suponer campos LAB."
                )
                
                contenido_consulta = []
                
                # Adjuntamos los PDFs cargados de forma compatible
                if archivos_subidos:
                    for pdf in archivos_subidos:
                        bytes_data = pdf.read()
                        contenido_consulta.append({
                            "mime_type": "application/pdf",
                            "data": bytes_data
                        })
                else:
                    st.warning("⚠️ Nota: Actualmente no hay manuales subidos en el panel lateral. Las respuestas se basarán en el conocimiento general del modelo hasta que cargues tus PDFs oficiales.")

                # Sumamos las instrucciones y la consulta del médico
                contenido_consulta.append(prompt_sistema)
                contenido_consulta.append(f"Consulta del usuario: {consulta}")
                
                # Generamos el contenido analizando los PDFs reales
                respuesta = model.generate_content(contenido_consulta)
                
                st.success("¡Información localizada con éxito!")
                st.markdown(respuesta.text)
                
            except Exception as e:
                st.error(f"Hubo un problema al procesar la consulta: {e}")

# 5. Pie de página institucional
st.markdown("---")
st.caption("📌 Nota administrativa: Los cambios y manuales subidos se mantienen vigentes mientras la sesión de la aplicación web permanezca activa.")
