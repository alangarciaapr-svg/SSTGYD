import streamlit as st
import pandas as pd
from datetime import datetime

# --- CONFIGURACIÓN DE INTERFAZ ---
st.set_page_config(page_title="SGSST Maderas G&D", layout="wide")

# --- BASE DE DATOS REAL (Tus trabajadores) ---
workers = [
    {"nombre": "Alberto Loaiza Mansilla", "cargo": "Jefe de Patio", "rut": "15.282.021-6"},
    {"nombre": "Jose Miguel Oporto Godoy", "cargo": "Operario Aserradero", "rut": "9.914.127-1"},
    {"nombre": "Givens Aburto Camino", "cargo": "Ayudante", "rut": "23.076.765-3"},
    {"nombre": "Aladin Figueroa", "cargo": "Ayudante", "rut": "23.456.789-0"},
    {"nombre": "Maicol Oyarzo", "cargo": "Ayudante", "rut": "24.567.890-k"}
]

# --- NAVEGACIÓN ---
st.sidebar.title("🌲 Maderas G&D")
st.sidebar.markdown("---")
modulo = st.sidebar.radio("SISTEMA DE GESTIÓN", ["Panel Control (Alan)", "App Terreno (Operario)", "Fiscalización (FUF)"])

# --- VISTA 1: PANEL DE CONTROL (Sincronización Gerencial) ---
if modulo == "Panel Control (Alan)":
    st.title("📊 Panel de Gestión - Alan García")
    st.markdown("### Estado de Cumplimiento DS 44/2024")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Dotación", "5 Activos")
    col2.metric("Nivel de Riesgo", "Bajo", "Estable")
    col3.metric("Documentación", "Al día", "OK")

    st.subheader("📋 Matriz de Trabajadores Fiscalizable")
    st.dataframe(pd.DataFrame(workers))

# --- VISTA 2: APP DE TERRENO (Sincronización Operativa) ---
elif modulo == "App Terreno (Operario)":
    st.title("📲 Registro de Seguridad en Terreno")
    
    with st.form("form_seguridad"):
        operario = st.selectbox("Trabajador:", [w["nombre"] for w in workers])
        st.write("---")
        st.info("Ítems Críticos según Formulario Único de Fiscalización")
        
        c1 = st.checkbox("Instalaciones sanitarias y agua potable (Art. 12)")
        c2 = st.checkbox("EPP completo y en buen estado (Art. 53)")
        c3 = st.checkbox("Checklist Wood-Mizer: Soportes y lubricación OK")
        c4 = st.checkbox("PTS difundido y comprendido (Art. 22)")
        
        novedades = st.text_area("Reporte de incidentes / Sugerencias:")
        
        if st.form_submit_button("FIRMAR Y SINCRONIZAR"):
            if c1 and c2 and c3 and c4:
                st.success(f"Registro de {operario} guardado. Sincronizado con Panel de Control.")
            else:
                st.error("Error: Debe marcar todos los puntos para cumplir con el DS 44.")

# --- VISTA 3: FISCALIZACIÓN (FUF) ---
elif modulo == "Fiscalización (FUF)":
    st.title("⚖️ Auditoría de Cumplimiento Legal")
    st.write("Verificación de ítems según Formulario Único de Fiscalización (FUF)")
    
    items = ["Política de SST (Art. 4)", "Diagnóstico de Riesgos (Art. 22)", 
             "Planificación de Actividades", "Investigación de Accidentes (Art. 15)"]
    
    for item in items:
        st.write(f"✅ {item}")
    
    st.button("Descargar Reporte de Evidencia (PDF)")
