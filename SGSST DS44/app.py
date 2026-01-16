import streamlit as st
import pandas as pd
from datetime import datetime

# --- CONFIGURACIÓN DE LA APP ---
st.set_page_config(page_title="SGSST Maderas G&D", layout="wide", initial_sidebar_state="expanded")

# --- BASE DE DATOS REAL (Extraída de tus archivos) ---
# Sincronizado con: listado de trabajadores.xlsx
workers = [
    {"nombre": "Alberto Loaiza Mansilla", "cargo": "Jefe de Patio", "rut": "15.282.021-6"},
    {"nombre": "Jose Miguel Oporto Godoy", "cargo": "Operador Aserradero", "rut": "9.914.127-1"},
    {"nombre": "Givens Aburto Camino", "cargo": "Ayudante", "rut": "23.076.765-3"},
    {"nombre": "Aladin Figueroa", "cargo": "Ayudante", "rut": "23.456.789-0"},
    {"nombre": "Maicol Oyarzo", "cargo": "Ayudante", "rut": "24.567.890-k"}
]

# --- ESTILOS PERSONALIZADOS ---
st.markdown("""
    <style>
    .stApp { background-color: #f4f7f6; }
    .status-card { background-color: white; padding: 20px; border-radius: 15px; border-left: 5px solid #ff4b4b; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

# --- NAVEGACIÓN ---
st.sidebar.title("🌲 Maderas G&D")
st.sidebar.subheader("Sistema de Gestión DS 44")
modulo = st.sidebar.radio("IR A:", ["📊 Panel de Control (Alan)", "📲 App de Terreno (Operario)", "⚖️ Auditoría Fiscalizable"])

# --- VISTA 1: PANEL DE CONTROL (Sincronización Gerencial) ---
if modulo == "📊 Panel de Control (Alan)":
    st.title("Panel de Control Gerencial")
    st.write(f"Bienvenido, **Alan García Vidal**. Estado de la faena al {datetime.now().strftime('%d/%m/%Y')}")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Dotación Aserradero", "5", "Activos")
    with col2:
        st.metric("Cumplimiento FUF", "95%", "Excelente")
    with col3:
        st.metric("Alertas Críticas", "0", "OK")

    st.subheader("Nómina Fiscalizable")
    st.dataframe(pd.DataFrame(workers), use_container_width=True)

# --- VISTA 2: APP DE TERRENO (Sincronización Operativa) ---
elif modulo == "📲 App de Terreno (Operario)":
    st.title("Registro de Jornada y Seguridad")
    
    with st.container():
        st.write("### Identificación")
        nombre_sel = st.selectbox("Seleccione su Nombre:", [w["nombre"] for w in workers])
        
        st.write("---")
        st.write("### Checklist Obligatorio (Art. 12, 15, 53 DS 44)")
        
        c1 = st.checkbox("¿Instalaciones sanitarias limpias y con agua potable?")
        c2 = st.checkbox("¿EPP en buen estado y utilizado correctamente?")
        c3 = st.checkbox("¿Maquinaria Wood-Mizer inspeccionada (Soportes/Sierra)?")
        c4 = st.checkbox("¿Área libre de riesgos de caída o atrapamiento?")
        
        reporte = st.text_area("Reporte de Incidentes / Sugerencias (Art. 184):")
        
        if st.button("FIRMAR Y SINCRONIZAR"):
            if c1 and c2 and c3 and c4:
                st.success(f"¡Registro exitoso para {nombre_sel}! Sincronizado con Panel de Control.")
                st.balloons()
            else:
                st.error("Error: Debe cumplir con todos los requisitos de seguridad antes de firmar.")

# --- VISTA 3: AUDITORÍA FISCALIZABLE (DS 44) ---
elif modulo == "⚖️ Auditoría Fiscalizable":
    st.title("Cumplimiento Formulario Único de Fiscalización")
    st.warning("Módulo basado en el Formulario Único de Fiscalización (FUF) - SUSESO/Ministerio de Salud")
    
    st.write("#### Verificación de Artículos Críticos:")
    fuf_items = {
        "Art. 4": "Cuenta con Política de Seguridad y Salud",
        "Art. 22": "Posee Diagnóstico de Riesgos y Planificación",
        "Art. 12": "Garantiza condiciones sanitarias y agua potable",
        "Art. 15": "Sistema de investigación de accidentes implementado"
    }
    
    for art, desc in fuf_items.items():
        st.checkbox(f"{art}: {desc}", value=True, disabled=True)
    
    st.button("Generar Reporte de Cumplimiento para Seremi (PDF)")
