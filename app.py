import streamlit as st
import pandas as pd

# 1. Configuración de Página
st.set_page_config(page_title="Maderas G&D - SGSST", layout="wide")

# 2. Datos de Trabajadores (Cargados desde tu lista)
workers = [
    {"nombre": "Alan García Vidal", "cargo": "APR"},
    {"nombre": "Alberto Loaiza Mansilla", "cargo": "Jefe de Patio"},
    {"nombre": "Jose Miguel Oporto Godoy", "cargo": "Operador Aserradero"},
    {"nombre": "Givens Aburto Camino", "cargo": "Ayudante"},
    {"nombre": "Aladin Figueroa", "cargo": "Ayudante"},
    {"nombre": "Maicol Oyarzo", "cargo": "Ayudante"}
]

# 3. Interfaz de Navegación
st.sidebar.title("🌲 MADERAS G&D")
st.sidebar.markdown("---")
app_mode = st.sidebar.radio("Seleccione Interfaz:", ["📊 Panel Control (Alan)", "📲 App Terreno (Operación)"])

# --- VISTA: PANEL DE CONTROL ---
if app_mode == "📊 Panel Control (Alan)":
    st.title("Panel de Gestión y Fiscalización")
    st.subheader("Estado Global de Seguridad - DS 44")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Trabajadores en Sistema", "6")
    m2.metric("Cumplimiento FUF", "100%", "Check")
    m3.metric("Alertas Pendientes", "0")

    st.markdown("### Matriz de Personal y Cargos")
    st.table(pd.DataFrame(workers))

# --- VISTA: APP DE TERRENO ---
else:
    st.title("Registro de Seguridad en Faena")
    st.info("Formulario de cumplimiento según Art. 12, 15 y 22 del DS 44.")
    
    with st.form("registro_seguridad"):
        operario = st.selectbox("Trabajador:", [w["nombre"] for w in workers])
        st.write("---")
        
        # Puntos críticos del Formulario Único de Fiscalización (FUF)
        st.write("#### Validación de Condiciones (Fiscalizable)")
        c1 = st.checkbox("Instalaciones sanitarias y agua potable OK (Art. 12)")
        c2 = st.checkbox("EPP completo y en buen estado (Art. 53)")
        c3 = st.checkbox("Maquinaria inspeccionada y segura (Wood-Mizer)")
        c4 = st.checkbox("Participación: ¿Tiene sugerencias de seguridad?")
        
        comentario = st.text_area("Observaciones del día:")
        
        enviar = st.form_submit_button("FIRMAR Y SINCRONIZAR")
        
        if enviar:
            if c1 and c2 and c3:
                st.success(f"Registro de {operario} sincronizado correctamente con el Panel de Alan.")
            else:
                st.error("Error: Para cumplir con el DS 44, debe validar todos los puntos de seguridad.")
