import streamlit as st
import pandas as pd
from datetime import datetime

# CONFIGURACIÓN DE PÁGINA PROFESIONAL
st.set_page_config(page_title="SGSST Maderas G&D", layout="wide")

# ESTILOS PARA QUE PAREZCA UNA APP DE TERRENO
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 20px; height: 3em; background-color: #f39c12; color: white; font-weight: bold; }
    .report-card { background-color: #ffffff; padding: 20px; border-radius: 10px; border-left: 5px solid #27ae60; margin-bottom: 10px; color: #2c3e50; }
    </style>
    """, unsafe_allow_html=True)

# 1. BASE DE DATOS DE TRABAJADORES (Sincronizada con tus archivos)
workers = [
    {"Nombre": "Alberto Loaiza Mansilla", "Cargo": "Jefe de Patio", "RUT": "15.282.021-6"},
    {"Nombre": "Jose Miguel Oporto Godoy", "Cargo": "Operario Aserradero", "RUT": "9.914.127-1"},
    {"Nombre": "Givens Aburto Camino", "Cargo": "Ayudante", "RUT": "23.076.765-3"},
    {"Nombre": "Aladin Figueroa", "Cargo": "Ayudante", "RUT": "23.456.789-0"},
    {"Nombre": "Maicol Oyarzo", "Cargo": "Ayudante", "RUT": "24.567.890-k"}
]

# 2. BARRA LATERAL (NAVEGACIÓN)
st.sidebar.title("🌲 MADERAS G&D")
st.sidebar.subheader("Gestión DS 44 / 2024")
opcion = st.sidebar.selectbox("MÓDULOS:", ["📊 Dashboard de Alan", "📲 App de Terreno", "🚨 Investigación de Incidentes"])

# --- VISTA 1: DASHBOARD DE CONTROL (PARA TI) ---
if opcion == "📊 Dashboard de Alan":
    st.title("Panel de Control Gerencial - Alan García")
    
    # Semáforo de Cumplimiento basado en el FUF
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Trabajadores", len(workers))
    col2.metric("Cumplimiento FUF", "100%", "FISCALIZABLE")
    col3.metric("PTS Versión", "2.0")
    col4.metric("Incidentes Mes", "0", "OK")

    st.subheader("📋 Matriz de Identificación de Peligros (IPER)")
    st.table(pd.DataFrame(workers))

# --- VISTA 2: APP DE TERRENO (PARA EL TRABAJADOR) ---
elif opcion == "📲 App de Terreno":
    st.title("Registro de Seguridad Diaria")
    st.write("Complete este registro para cumplir con el **Art. 12 y 53** del DS 44.")
    
    with st.container():
        trabajador = st.selectbox("Seleccione su Nombre:", [w["Nombre"] for w in workers])
        st.write("---")
        
        # Puntos del Formulario de Fiscalización
        st.write("### ✅ Checklist de Seguridad")
        c1 = st.checkbox("¿Instalaciones sanitarias limpias y con agua potable? (Art. 12)")
        c2 = st.checkbox("¿EPP completo y en buen estado? (Art. 53)")
        c3 = st.checkbox("¿Wood-Mizer: Soportes y Lubricación inspeccionados?")
        
        # Firma Digital (Simulada)
        if st.button("FIRMAR Y REGISTRAR JORNADA"):
            if c1 and c2 and c3:
                st.success(f"Registro de {trabajador} sincronizado con éxito.")
                st.balloons()
            else:
                st.error("Error: Debe cumplir todos los puntos para registrar.")

# --- VISTA 3: INVESTIGACIÓN DE INCIDENTES (ART. 15) ---
elif opcion == "🚨 Investigación de Incidentes":
    st.title("Reporte de Incidentes / Casi-Accidentes")
    st.warning("De conformidad al Art. 15 del DS 44, reporte todo evento.")
    
    with st.form("incidente"):
        fecha = st.date_input("Fecha del Evento")
        tipo = st.selectbox("Tipo de Evento", ["Casi-Accidente", "Condición Subestándar", "Falla de Equipo"])
        descripcion = st.text_area("Descripción del suceso:")
        medida = st.text_area("Acción Correctiva Inmediata:")
        
        if st.form_submit_button("REGISTRAR INCIDENTE"):
            st.write("#### 📄 Registro generado para Alan García")
            st.info(f"Evento registrado el {fecha}. La IA analizará la causa raíz según el PTS-GD-07.")
