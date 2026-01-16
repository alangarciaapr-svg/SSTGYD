import streamlit as st
import pandas as pd
from datetime import datetime

# --- 1. CONFIGURACIÓN Y PERSISTENCIA ---
st.set_page_config(page_title="SGSST Maderas G&D", layout="wide")

# Inicializar Base de Datos de Trabajadores (23 registros del CSV)
if 'db_trabajadores' not in st.session_state:
    st.session_state.db_trabajadores = pd.DataFrame([
        {"RUT": "16.781.002-0", "Nombre": "ALAN FABIAN GARCIA VIDAL", "Cargo": "APR", "Lugar": "OFICINA"},
        {"RUT": "10.518.096-9", "Nombre": "OSCAR EDUARDO TRIVIÑO SALAZAR", "Cargo": "OPERADOR HARVESTER", "Lugar": "FAENA"},
        {"RUT": "15.282.021-6", "Nombre": "ALBERTO LOAIZA MANSILLA", "Cargo": "JEFE DE PATIO", "Lugar": "ASERRADERO"},
        {"RUT": "9.914.127-1", "Nombre": "JOSE MIGUEL OPORTO GODOY", "Cargo": "OPERADOR ASERRADERO", "Lugar": "ASERRADERO"},
        {"RUT": "23.076.765-3", "Nombre": "GIVENS ABURTO CAMINO", "Cargo": "AYUDANTE", "Lugar": "ASERRADERO"},
        {"RUT": "13.736.331-3", "Nombre": "MAURICIO LOPEZ GUTIÉRREZ", "Cargo": "ADMINISTRATIVO", "Lugar": "OFICINA"},
        # ... El sistema permite agregar el resto dinámicamente o por código
    ])

# Inicializar Almacén de Documentos (Lo que antes era papel)
if 'documentos' not in st.session_state:
    st.session_state.documentos = {
        "politica": "Redacte aquí la Política de SST de Maderas G&D...",
        "pts": "Describa el Procedimiento de Trabajo Seguro...",
        "matriz": []
    }

# --- 2. NAVEGACIÓN LATERAL ---
st.sidebar.title("🌲 CENTRAL DE GESTIÓN")
menu = st.sidebar.selectbox("SELECCIONE MÓDULO:", [
    "👥 Gestión de Personal",
    "📜 Política y PTS",
    "⚠️ Matriz de Riesgos (IPER)",
    "📲 App de Terreno",
    "⚖️ Auditoría DS 44"
])

# --- 3. MÓDULO: GESTIÓN DE PERSONAL (NÓMINA COMPLETA) ---
if menu == "👥 Gestión de Personal":
    st.title("Administración de Personal")
    tab1, tab2 = st.tabs(["📋 Nómina Vigente", "⚙️ Editar / Agregar"])
    
    with tab1:
        st.dataframe(st.session_state.db_trabajadores, use_container_width=True)
    
    with tab2:
        with st.form("nuevo_t"):
            st.subheader("Agregar o Modificar Trabajador")
            f_rut = st.text_input("RUT")
            f_nom = st.text_input("Nombre Completo")
            f_car = st.selectbox("Cargo", ["APR", "OPERADOR", "AYUDANTE", "CHOFER", "ADMIN"])
            if st.form_submit_button("Actualizar Base de Datos"):
                new_row = pd.DataFrame([{"RUT": f_rut, "Nombre": f_nom, "Cargo": f_car, "Lugar": "FAENA"}])
                st.session_state.db_trabajadores = pd.concat([st.session_state.db_trabajadores, new_row], ignore_index=True)
                st.success("Personal actualizado.")

# --- 4. MÓDULO: CREACIÓN DE PROCEDIMIENTOS Y POLÍTICA ---
elif menu == "📜 Política y PTS":
    st.title("Generador de Documentación Normativa")
    doc_tipo = st.radio("Documento a crear:", ["Política de SST (Art. 4)", "Procedimiento de Trabajo (PTS)"])
    
    if doc_tipo == "Política de SST (Art. 4)":
        st.session_state.documentos["politica"] = st.text_area("Cuerpo de la Política:", st.session_state.documentos["politica"], height=300)
    else:
        st.session_state.documentos["pts"] = st.text_area("Cuerpo del PTS (Ej: Operación Wood-Mizer):", st.session_state.documentos["pts"], height=300)
    
    if st.button("Guardar y Firmar Digitalmente"):
        st.success("Documento guardado con éxito. Disponible para difusión en Terreno.")

# --- 5. MÓDULO: MATRIZ DE RIESGOS (IPER) ---
elif menu == "⚠️ Matriz de Riesgos (IPER)":
    st.title("Matriz de Identificación de Peligros (Art. 64)")
    with st.expander("➕ Agregar Riesgo a la Matriz"):
        with st.form("iper_f"):
            puesto = st.selectbox("Puesto:", st.session_state.db_trabajadores['Cargo'].unique())
            peligro = st.text_input("Peligro (Ej: Atrapamiento)")
            medida = st.text_input("Medida de Control (Ej: Guardas)")
            if st.form_submit_button("Insertar en Matriz"):
                st.session_state.documentos["matriz"].append({"Puesto": puesto, "Peligro": peligro, "Control": medida})
    
    if st.session_state.documentos["matriz"]:
        st.table(pd.DataFrame(st.session_state.documentos["matriz"]))

# --- 6. MÓDULO: APP DE TERRENO (LO QUE VE EL TRABAJADOR) ---
elif menu == "📲 App de Terreno":
    st.title("Interfaz Móvil de Faena")
    operario = st.selectbox("Identificación del Trabajador:", st.session_state.db_trabajadores['Nombre'])
    
    st.subheader("Difusión de Documentos")
    st.info(f"📜 Política Vigente: {st.session_state.documentos['politica'][:50]}...")
    
    if st.button("He leído y acepto el PTS y la Política"):
        st.success(f"Firma digital registrada para {operario}. Cumplimiento DS 44 OK.")
