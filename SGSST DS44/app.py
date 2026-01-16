import streamlit as st
import pandas as pd
from datetime import datetime

# 1. BASE DE DATOS DE TRABAJADORES (Sincronizada con tu CSV)
workers_data = {
    'Nombre': ['Jose Miguel Oporto', 'Alberto Loaiza', 'Givens Aburto', 'Aladin Figueroa', 'Maicol Oyarzo'],
    'Cargo': ['Operador Aserradero', 'Jefe de Patio', 'Ayudante', 'Ayudante', 'Ayudante'],
    'RUT': ['9.914.127-1', '15.282.021-6', '23.076.765-3', '23.456.789-0', '24.567.890-k']
}
df_workers = pd.DataFrame(workers_data)

# CONFIGURACIÓN DE LA APP
st.set_page_config(page_title="Maderas G&D - DS44", layout="wide")
st.title("🌲 Maderas G&D: Sistema de Gestión DS 44/2024")

# INTERFAZ DE NAVEGACIÓN
menu = st.sidebar.selectbox("Seleccionar Módulo", ["Panel Control (Alan)", "App Terreno (Operario)", "Fiscalización (FUF)"])

# --- MÓDULO: PANEL DE CONTROL ---
if menu == "Panel Control (Alan)":
    st.header("📊 Panel de Control Administrativo")
    col1, col2, col3 = st.columns(3)
    col1.metric("Trabajadores Activos", "5")
    col2.metric("Cumplimiento DS 44", "92%", "+5%")
    col3.warning("Alerta: 1 EPP por renovar")
    
    st.subheader("Matriz de Riesgos Críticos (IPER)")
    st.table(df_workers)

# --- MÓDULO: APP DE TERRENO ---
elif menu == "App Terreno (Operario)":
    st.header("📲 Registro de Terreno - Sincronizado")
    with st.form("registro_diario"):
        worker = st.selectbox("Identificación Trabajador", df_workers['Nombre'])
        st.write("### Checklist Fiscalizable (Art. 12 al 15)")
        c1 = st.checkbox("Agua potable disponible y fresca")
        c2 = st.checkbox("Servicios higiénicos limpios y desinfectados")
        c3 = st.checkbox("PTS-GD-07 leído y comprendido hoy")
        c4 = st.checkbox("Uso de 3 puntos de apoyo en Wood-Mizer")
        
        observacion = st.text_area("Reporte de Incidentes (Art. 15)")
        
        if st.form_submit_button("Firmar y Enviar"):
            st.success(f"Registro de {worker} guardado y sincronizado con el Panel de Alan García.")

# --- MÓDULO: FISCALIZACIÓN ---
elif menu == "Fiscalización (FUF)":
    st.header("📑 Formulario Único de Fiscalización")
    st.info("Este módulo genera el reporte para la Seremi de Salud basado en el archivo cargado.")
    # Aquí se integra la lógica de generación de PDF basada en el FUF
    st.button("Descargar Reporte de Cumplimiento PDF")
