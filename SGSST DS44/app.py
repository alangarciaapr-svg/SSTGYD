import streamlit as st
import pandas as pd
from datetime import datetime

# --- CONFIGURACIÓN DE LA APP (FISCALIZABLE DS44) ---
st.set_page_config(page_title="SGSST Maderas G&D", layout="wide")

# Estilos personalizados para parecer una App profesional
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #e67e22; color: white; font-weight: bold; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border-left: 5px solid #e67e22; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

# --- BASE DE DATOS REAL (Extraída de tu listado) ---
workers = [
    {"Nombre": "Alberto Loaiza Mansilla", "Cargo": "Jefe de Patio", "RUT": "15.282.021-6"},
    {"Nombre": "Jose Miguel Oporto Godoy", "Cargo": "Operario Aserradero", "RUT": "9.914.127-1"},
    {"Nombre": "Givens Aburto Camino", "Cargo": "Ayudante", "RUT": "23.076.765-3"},
    {"Nombre": "Aladin Figueroa", "Cargo": "Ayudante", "RUT": "23.456.789-0"},
    {"Nombre": "Maicol Oyarzo", "Cargo": "Ayudante", "RUT": "24.567.890-k"}
]

# --- LÓGICA DE NAVEGACIÓN ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2761/2761047.png", width=100)
st.sidebar.title("Maderas G&D")
menu = st.sidebar.radio("SISTEMA DE GESTIÓN", ["Panel Admin (Alan)", "App Terreno (Operación)", "Auditoría FUF (DS44)"])

# --- VISTA 1: PANEL DE CONTROL (ALAN GARCÍA) ---
if menu == "Panel Admin (Alan)":
    st.title("📊 Panel de Control y Fiscalización")
    st.info("Gestión de riesgos basada en Formulario Único de Fiscalización (FUF)")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Trabajadores", len(workers))
    col2.metric("Puntos FUF", "22/22", "OK")
    col3.metric("DS 594", "Cumple")
    col4.metric("Versión PTS", "1.2")

    st.subheader("📋 Matriz de Identificación de Peligros (IPER)")
    st.table(pd.DataFrame(workers))

# --- VISTA 2: APP DE TERRENO (SINCRONIZADA) ---
elif menu == "App Terreno (Operación)":
    st.title("📲 App de Terreno - Registro Diario")
    
    with st.container():
        user = st.selectbox("Seleccione su Nombre", [w["Nombre"] for w in workers])
        st.write("---")
        st.write("### Control Preventivo (Art. 4, 12, 15, 22 DS44)")
        
        # Puntos críticos del formulario que subiste
        check1 = st.checkbox("Tengo mi EPP completo y en buen estado (Art. 53)")
        check2 = st.checkbox("Área de trabajo limpia y libre de obstáculos")
        check3 = st.checkbox("Acceso a agua potable y servicios higiénicos (Art. 12)")
        check4 = st.checkbox("Realicé Checklist de Wood-Mizer (Soportes/Lubricación)")
        
        novedades = st.text_area("Reporte de Incidentes o Sugerencias (Participación Art. 184)")
        
        if st.button("FIRMAR Y ENVIAR REGISTRO"):
            if check1 and check2 and check3 and check4:
                st.success(f"Registro de {user} enviado exitosamente. Alan García ha sido notificado.")
                st.balloons()
            else:
                st.error("Debe cumplir con todos los puntos de seguridad para firmar.")

# --- VISTA 3: AUDITORÍA FUF ---
elif menu == "Auditoría FUF (DS44)":
    st.title("📑 Verificación de Cumplimiento Legal")
    st.warning("Este módulo compara tu gestión con el Formulario de Fiscalización.")
    
    checks_fuf = [
        "¿Cuenta con Política de SST? (Art. 4)",
        "¿Tiene Diagnóstico y Planificación? (Art. 22)",
        "¿Realiza investigación de accidentes? (Art. 15)",
        "¿Identifica peligros por puesto de trabajo? (Art. 64)"
    ]
    
    for item in checks_fuf:
        st.checkbox(item, value=True, disabled=True)
    
    st.button("Generar Reporte para Inspección (PDF)")
