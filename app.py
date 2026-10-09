import hmac
import json
import tempfile
from urllib.parse import quote

import requests
import time
from pathlib import Path

import streamlit as st
import google.generativeai as ai

# ---------------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------------
st.set_page_config(page_title="Buscador HIS MINSA", page_icon="🏥", layout="centered")

REPO_API = "https://api.github.com/repos/jsarevalo88-hash/manuales/contents/"
REPO_RAW = "https://raw.githubusercontent.com/jsarevalo88-hash/manuales/main/"
CARPETA_LOCAL = Path(tempfile.gettempdir()) / "manuales_his"
CARPETA_LOCAL.mkdir(exist_ok=True)
MODELO = "gemini-flash-latest"
MAX_MANUALES = 4              # máximo de manuales leídos por consulta
VIGENCIA_SEG = 40 * 3600      # los archivos en Google duran 48 h; renovamos a las 40 h

try:
    ai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception:
    st.warning("⚠️ Falta configurar la clave API de Gemini en los secretos del servidor.")

PROMPT_SISTEMA = (
    "Eres un asistente experto en codificación HIS y CIE-10 del Ministerio de Salud del Perú (MINSA).\n"
    "Tu única tarea es extraer de los manuales proporcionados la forma exacta de registrar la atención solicitada.\n"
    "Si la atención tiene varias formas de registro según el contexto (edad, sexo, gestante, estrategia, etc.), "
    "presenta TODAS las opciones, una fila por opción.\n"
    "Si la consulta es un código (CIE-10, CPT), indica a qué atención corresponde y cómo se registra.\n\n"
    "Estructura tu respuesta estrictamente con este formato markdown:\n\n"
    "### 📋 FICHA DE REGISTRO HIS\n"
    "**- Actividad / Estrategia:** [Nombre de la estrategia sanitaria]\n"
    "**- Tipo de Diagnóstico:** [P / D / R]\n\n"
    "### 🔢 CÓDIGOS Y CAMPOS LAB\n"
    "| Diagnóstico / Actividad | Campo LAB | Código CIE-10 / CPT | Fuente (manual y página) |\n"
    "| :--- | :--- | :--- | :--- |\n"
    "| [Actividad] | [Valor LAB] | [Código] | [Nombre del manual, pág. X] |\n\n"
    "### 📍 NOTAS / REQUISITOS\n"
    "[Observación importante del manual, indicando manual y página]\n\n"
    "REGLAS CRÍTICAS:\n"
    "1. Cada dato debe indicar el manual y la página de donde proviene (página del visor PDF).\n"
    "2. Si los documentos no contienen la información específica, responde únicamente: "
    "'La atención solicitada no se encuentra registrada en los manuales consultados.'\n"
    "3. Está estrictamente prohibido inventar códigos, campos LAB o páginas."
)

# ---------------------------------------------------------------
# FUNCIONES
# ---------------------------------------------------------------
def nombre_corto(archivo: str) -> str:
    return archivo.replace("Manual-", "").replace(".pdf", "").replace("_", " ")


@st.cache_resource
def registro_archivos() -> dict:
    """Memoria compartida de archivos ya subidos a Google (evita resubirlos)."""
    return {}


@st.cache_data(ttl=600)
def listar_manuales() -> list:
    try:
        r = requests.get(REPO_API, timeout=20)
        r.raise_for_status()
        return sorted(x["name"] for x in r.json() if x["name"].lower().endswith(".pdf"))
    except Exception:
        return []


def descargar_manual(nombre: str) -> Path:
    destino = CARPETA_LOCAL / nombre
    if not destino.exists():
        r = requests.get(REPO_RAW + quote(nombre), timeout=120)
        r.raise_for_status()
        destino.write_bytes(r.content)
    return destino


def subir_manual(nombre: str):
    """Sube el PDF a Google una sola vez y reutiliza el archivo mientras esté vigente."""
    reg = registro_archivos()
    ahora = time.time()
    info = reg.get(nombre)

    if info and ahora - info["t"] < VIGENCIA_SEG:
        try:
            f = ai.get_file(info["name"])
            if f.state.name == "ACTIVE":
                return f
        except Exception:
            pass

    f = ai.upload_file(
        path=str(descargar_manual(nombre)),
        mime_type="application/pdf",
        display_name=nombre,
    )
    while f.state.name == "PROCESSING":
        time.sleep(2)
        f = ai.get_file(f.name)
    if f.state.name != "ACTIVE":
        raise RuntimeError(f"No se pudo procesar el manual {nombre}")

    reg[nombre] = {"name": f.name, "t": ahora}
    return f


def elegir_manuales(consulta: str, disponibles: list) -> list:
    """Paso 1: la IA decide qué manuales conviene leer, según su nombre."""
    modelo = ai.GenerativeModel(
        MODELO,
        generation_config={"temperature": 0, "response_mime_type": "application/json"},
    )
    lista = "\n".join(f"- {n}" for n in disponibles)
    pedido = (
        "Eres un experto en el sistema HIS del MINSA Perú. Según la consulta, elige los manuales "
        f"donde es más probable encontrar cómo registrar la atención (máximo {MAX_MANUALES}).\n"
        "Responde SOLO con un arreglo JSON con los nombres de archivo exactos de la lista.\n\n"
        f"Consulta: {consulta}\n\nManuales disponibles:\n{lista}"
    )
    try:
        datos = json.loads(modelo.generate_content(pedido).text)
        return [n for n in datos if n in disponibles][:MAX_MANUALES]
    except Exception:
        return []


# ---------------------------------------------------------------
# PANEL DE ADMINISTRACIÓN (con contraseña)
# ---------------------------------------------------------------
if "admin" not in st.session_state:
    st.session_state.admin = False

with st.sidebar:
    st.header("⚙️ Administración")

    if not st.session_state.admin:
        clave = st.text_input("Contraseña de administrador", type="password")
        if clave:
            esperada = st.secrets.get("ADMIN_PASSWORD", "")
            if esperada and hmac.compare_digest(clave, esperada):
                st.session_state.admin = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta.")
    else:
        st.success("Sesión de administrador activa")
        extras = st.file_uploader(
            "Manuales adicionales (solo esta sesión):",
            type=["pdf"],
            accept_multiple_files=True,
        )
        if extras:
            st.info(f"📎 {len(extras)} manual(es) adicional(es) cargado(s).")
        st.caption(f"Manuales fijos en el servidor: {len(listar_manuales())}")
        if st.button("Cerrar sesión de administrador"):
            st.session_state.admin = False
            st.rerun()

extras_admin = extras if st.session_state.admin and "extras" in locals() and extras else []

# ---------------------------------------------------------------
# INTERFAZ PRINCIPAL
# ---------------------------------------------------------------
st.title("🏥 Buscador Inteligente de Codificación HIS")
st.subheader("Encuentra la forma correcta de registrar tus atenciones médicas")

disponibles = listar_manuales()
if not disponibles:
    st.error("No se encontraron manuales en la carpeta 'manuales/' del repositorio.")

consulta = st.text_input(
    "¿Qué atención o código deseas consultar?",
    placeholder="Ej: biopsia de mama, tamizaje de depresión, C50.9...",
)

manuales_manual = st.multiselect(
    "Filtrar por manual (opcional; si lo dejas vacío, la IA elige los más relevantes):",
    options=disponibles,
    format_func=nombre_corto,
    max_selections=MAX_MANUALES,
)

if st.button("🔍 Buscar Forma de Registro", use_container_width=True):
    if consulta.strip() == "":
        st.error("Por favor, escribe una atención para poder ayudarte.")
    elif not disponibles and not extras_admin:
        st.error("No hay manuales disponibles para consultar.")
    else:
        try:
            # Paso 1: decidir qué manuales leer
            if manuales_manual:
                elegidos = manuales_manual
            else:
                with st.spinner("Identificando los manuales más relevantes..."):
                    elegidos = elegir_manuales(consulta, disponibles)

            if not elegidos and not extras_admin:
                st.warning("No pude identificar el manual adecuado. Selecciónalo en el filtro de arriba.")
                st.stop()

            # Paso 2: preparar los documentos
            contenido = []
            with st.spinner("Preparando los manuales (la primera vez puede tardar un poco)..."):
                for nombre in elegidos:
                    contenido.append(subir_manual(nombre))
                for pdf in extras_admin:
                    contenido.append({"mime_type": "application/pdf", "data": pdf.getvalue()})

            contenido.append(f"Consulta del usuario: {consulta}")

            # Paso 3: respuesta estricta (temperature 0)
            with st.spinner("Analizando los manuales..."):
                modelo = ai.GenerativeModel(
                    model_name=MODELO,
                    system_instruction=PROMPT_SISTEMA,
                    generation_config={"temperature": 0},
                )
                respuesta = modelo.generate_content(contenido)

            st.success("¡Consulta procesada!")
            if elegidos:
                st.caption("📚 Manuales consultados: " + " · ".join(nombre_corto(n) for n in elegidos))
            st.markdown(respuesta.text)
            st.warning(
                "⚠️ Verifica siempre el dato en la norma técnica vigente antes de registrar. "
                "Esta herramienta es un apoyo y puede cometer errores."
            )

        except Exception as e:
            st.error(f"Hubo un problema al procesar la consulta: {e}")

# ---------------------------------------------------------------
# PIE DE PÁGINA
# ---------------------------------------------------------------
st.markdown("---")
st.caption("📌 Herramienta de apoyo basada en los manuales HIS del MINSA cargados en el servidor.")
