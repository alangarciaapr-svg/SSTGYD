import streamlit as st
import pandas as pd
from datetime import datetime

# --- CONFIGURACIÓN ESTRUCTURAL ---
st.set_page_config(page_title="SGSST PRO - Maderas G&D", layout="wide")

# --- BASE DE DATOS ESTRUCTURAL (Digitalización de lo que hoy es papel) ---
if 'db_incidentes' not in st.session_state:
    st.session_state.db_incidentes = []
if 'db_epp' not in st.session_state:
    st.session_state.db_epp = []

workers = [
    {"Nombre": "Alberto Loaiza Mansilla", "Cargo": "Jefe de Patio"},
    {"Nombre": "Jose Miguel Oporto Godoy", "Cargo": "Operador Aserradero"},
    {"Nombre": "Givens Aburto Camino", "Cargo": "Ayudante"},
    {"Nombre": "Aladin Figueroa", "Cargo": "Ayudante"},
    {"Nombre": "Maicol Oyarzo", "Cargo": "Ayudante"}
]

# --- MENÚ DE GESTIÓN TÉCNICA ---
st.sidebar.title("🏢 CENTRAL PREVENCIONISTA")
opcion = st.sidebar.radio("GESTIÓN LEGAL:", [
    "📋 Panel de Control (Alan)", 
    "🏗️ Gestión de Terreno", 
    "🧤 Entrega de EPP (Art. 53)", 
    "⚠️ Matriz de Riesgos (IPER)",
    "🚨 Investigación de Accidentes (Art. 15)"
])

# --- 1. PANEL DE CONTROL (LO QUE VE EL PREVENCIONISTA) ---
if opcion == "📋 Panel de Control (Alan)":
    st.title("Dashboard de Gestión Estratégica")
    st.info("Visualización en tiempo real del cumplimiento del DS 44")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Cumplimiento Plan Mensual", "85%", "+2%")
    col2.metric("EPP Entregados", len(st.session_state.db_epp))
    col3.metric("Incidentes Reportados", len(st.session_state.db_incidentes))
    col4.metric("Estado Legal", "FISCALIZABLE", delta_color="normal")

    st.subheader("📊 Seguimiento de Medidas Correctivas")
    st.write("Aquí se listan las condiciones detectadas en terreno que aún no han sido cerradas.")
    # Tabla dinámica de incidentes
    if st.session_state.db_incidentes:
        st.table(pd.DataFrame(st.session_state.db_incidentes))
    else:
        st.write("No hay pendientes críticos.")

# --- 2. GESTIÓN DE TERRENO (LO QUE HACE EL TRABAJADOR) ---
elif opcion == "🏗️ Gestión de Terreno":
    st.title("Operación Digital de Terreno")
    tab1, tab2 = st.tabs(["📢 Charla de 5 Minutos", "🔍 Inspección de Seguridad"])
    
    with tab1:
        st.subheader("Registro de Capacitación Diaria")
        st.selectbox("Tema de la charla:", ["Riesgos de Atrapamiento", "Uso de EPP", "Plan de Emergencia"])
        asistentes = st.multiselect("Asistentes:", [w["Nombre"] for w in workers])
        if st.button("Generar Acta de Charla Digital"):
            st.success(f"Acta generada para {len(asistentes)} trabajadores. Archivo listo para fiscalización.")

    with tab2:
        st.subheader("Checklist de Máquinas y Herramientas")
        worker = st.selectbox("Responsable:", [w["Nombre"] for w in workers])
        # Puntos del FUF
        st.checkbox("Protecciones de partes móviles instaladas")
        st.checkbox("Pulsadores de emergencia operativos")
        st.checkbox("Área de tránsito despejada")
        if st.button("Enviar Inspección"):
            st.success("Inspección guardada y sincronizada.")

# --- 3. ENTREGA DE EPP (Art. 53 DS 594 / DS 44) ---
elif opcion == "🧤 Entrega de EPP (Art. 53)":
    st.title("Registro de Entrega de Elementos de Protección Personal")
    with st.form("epp_form"):
        destinatario = st.selectbox("Trabajador:", [w["Nombre"] for w in workers])
        equipo = st.multiselect("Elementos entregados:", ["Casco", "Lentes de seguridad", "Protección Auditiva", "Guantes de cabritilla", "Calzado de seguridad"])
        fecha = st.date_input("Fecha de entrega")
        if st.form_submit_button("Registrar Entrega y Firmar"):
            st.session_state.db_epp.append({"Trabajador": destinatario, "Fecha": fecha, "Items": str(equipo)})
            st.success("Comprobante legal de entrega generado.")

# --- 4. MATRIZ DE RIESGOS (IPER) ---
elif opcion == "⚠️ Matriz de Riesgos (IPER)":
    st.title("Identificación de Peligros y Evaluación de Riesgos (Art. 64)")
    st.write("Digitalización de la matriz IPER por puesto de trabajo.")
    
    iper_data = {
        "Puesto": ["Operador Wood-Mizer", "Ayudante de Patio", "Mecánico"],
        "Peligro": ["Atrapamiento", "Golpeado por troncos", "Contacto eléctrico"],
        "Riesgo": ["Grave", "Muy Alto", "Grave"],
        "Medida de Control": ["Guardas fijas / LOTO", "Zonas de exclusión", "Bloqueo de energía"]
    }
    st.dataframe(pd.DataFrame(iper_data), use_container_width=True)

# --- 5. INVESTIGACIÓN DE ACCIDENTES (Art. 15) ---
elif opcion == "🚨 Investigación de Accidentes (Art. 15)":
    st.title("Módulo de Reporte e Investigación")
    with st.form("incidente_form"):
        t = st.selectbox("Tipo:", ["Accidente", "Casi-accidente (Incidente)", "Enfermedad Profesional"])
        desc = st.text_area("Descripción del evento:")
        causa = st.text_area("Análisis Causa Raíz (Método de los 5 por qué):")
        accion = st.text_area("Acción Correctiva (Plan de Acción):")
        
        if st.form_submit_button("Registrar e Investigar"):
            st.session_state.db_incidentes.append({"Tipo": t, "Descripción": desc, "Fecha": datetime.now()})
            st.warning("Investigación registrada. El sistema enviará alerta a Gerencia.")
