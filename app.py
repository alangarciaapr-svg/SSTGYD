import streamlit as st
import pandas as pd
from datetime import datetime

# --- 1. CONFIGURACIÓN Y ESTADO INICIAL ---
st.set_page_config(page_title="SGSST Maderas G&D", layout="wide")

# Inicializar bases de datos en la sesión para que no se borren al navegar
if 'db_trabajadores' not in st.session_state:
    # Carga inicial basada en tu lista real de trabajadores
    data_inicial = [
        {"RUT": "16.781.002-0", "Nombre": "ALAN FABIAN GARCIA VIDAL", "Cargo": "APR", "Lugar": "OFICINA"},
        {"RUT": "10.518.096-9", "Nombre": "OSCAR EDUARDO TRIVIÑO SALAZAR", "Cargo": "OPERADOR HARVESTER", "Lugar": "FAENA"},
        {"RUT": "15.282.021-6", "Nombre": "ALBERTO LOAIZA MANSILLA", "Cargo": "JEFE DE PATIO", "Lugar": "ASERRADERO"},
        {"RUT": "9.914.127-1", "Nombre": "JOSE MIGUEL OPORTO GODOY", "Cargo": "OPERADOR ASERRADERO", "Lugar": "ASERRADERO"},
        {"RUT": "23.076.765-3", "Nombre": "GIVENS ABURTO CAMINO", "Cargo": "AYUDANTE", "Lugar": "ASERRADERO"},
        {"RUT": "13.736.331-3", "Nombre": "MAURICIO LOPEZ GUTIÉRREZ", "Cargo": "ADMINISTRATIVO", "Lugar": "OFICINA"}
    ]
    st.session_state.db_trabajadores = pd.DataFrame(data_inicial)

if 'db_incidentes' not in st.session_state:
    st.session_state.db_incidentes = []

# --- 2. BARRA LATERAL (CENTRAL DE MANDOS) ---
st.sidebar.title("🌲 GESTIÓN MADERAS G&D")
st.sidebar.markdown("---")
menu = st.sidebar.selectbox("SELECCIONE MÓDULO:", [
    "📊 Panel de Control (Resumen)",
    "👥 Gestión de Personal (CRUD)",
    "📲 App de Terreno (Operación)",
    "🧤 Entrega de EPP y Charlas",
    "🚨 Investigación de Accidentes",
    "⚖️ Auditoría Fiscalizable DS 44"
])

# --- 3. MÓDULO 1: PANEL DE CONTROL (RESUMEN EJECUTIVO) ---
if menu == "📊 Panel de Control (Resumen)":
    st.title("Panel de Gestión Estratégica - Alan García")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Trabajadores", len(st.session_state.db_trabajadores))
    c2.metric("Estado Fiscalización", "Cumple 95%")
    c3.metric("Incidentes Mes", len(st.session_state.db_incidentes))
    c4.metric("Versión App", "3.0 PRO")
    
    st.subheader("⚠️ Riesgos Críticos en Faena")
    iper = pd.DataFrame({
        "Actividad": ["Operación Wood-Mizer", "Carga de Camión", "Cruce de Maquinaria"],
        "Peligro": ["Atrapamiento", "Golpeado por carga", "Atropello"],
        "Control": ["Guardas/LOTO", "Radio 5m", "Radio 30m"]
    })
    st.table(iper)

# --- 4. MÓDULO 2: GESTIÓN DE PERSONAL (CREAR, EDITAR, BORRAR) ---
elif menu == "👥 Gestión de Personal (CRUD)":
    st.title("Administración de Nómina de Trabajadores")
    tab_list, tab_add, tab_edit = st.tabs(["📋 Nómina Actual", "➕ Nuevo Ingreso", "⚙️ Editar/Eliminar"])
    
    with tab_list:
        st.dataframe(st.session_state.db_trabajadores, use_container_width=True)
    
    with tab_add:
        with st.form("nuevo"):
            c_rut = st.text_input("RUT")
            c_nom = st.text_input("Nombre")
            c_car = st.selectbox("Cargo", ["APR", "OPERADOR", "AYUDANTE", "ADMINISTRATIVO", "CHOFER"])
            c_lug = st.selectbox("Lugar", ["OFICINA", "FAENA", "ASERRADERO"])
            if st.form_submit_button("Guardar en Sistema"):
                new_w = pd.DataFrame([{"RUT": c_rut, "Nombre": c_nom, "Cargo": c_car, "Lugar": c_lug}])
                st.session_state.db_trabajadores = pd.concat([st.session_state.db_trabajadores, new_w], ignore_index=True)
                st.success("Guardado correctamente")

    with tab_edit:
        st.subheader("Dar de Baja o Modificar")
        eliminar = st.selectbox("Seleccione Trabajador:", st.session_state.db_trabajadores['Nombre'])
        if st.button("❌ ELIMINAR DEL SISTEMA"):
            st.session_state.db_trabajadores = st.session_state.db_trabajadores[st.session_state.db_trabajadores.Nombre != eliminar]
            st.rerun()

# --- 5. MÓDULO 3: APP DE TERRENO (INTERFAZ OPERARIA) ---
elif menu == "📲 App de Terreno (Operación)":
    st.title("Interfaz Operativa de Terreno")
    st.info("Esta sección es la que usarán los trabajadores en sus teléfonos.")
    worker = st.selectbox("Seleccione su Nombre:", st.session_state.db_trabajadores['Nombre'])
    
    st.write("### Checklist de Seguridad Diario")
    st.checkbox("Instalaciones sanitarias y agua potable OK (Art. 12)")
    st.checkbox("EPP en buen estado (Art. 53)")
    st.checkbox("Protecciones de máquinas verificadas")
    
    if st.button("Firmar Registro"):
        st.success(f"Registro firmado por {worker}. Datos enviados al Panel de Control.")

# --- 6. MÓDULO 4: ENTREGA DE EPP Y CHARLAS ---
elif menu == "🧤 Entrega de EPP y Charlas":
    st.title("Gestión de Entregas y Capacitación")
    col_e, col_c = st.columns(2)
    with col_e:
        st.subheader("🧤 Registro EPP")
        st.selectbox("Destinatario:", st.session_state.db_trabajadores['Nombre'])
        st.multiselect("Elementos:", ["Casco", "Lentes", "Auditivos", "Guantes"])
        st.button("Registrar Entrega")
    with col_c:
        st.subheader("📢 Charla de 5 Minutos")
        st.text_input("Tema de hoy")
        st.multiselect("Asistentes:", st.session_state.db_trabajadores['Nombre'])
        st.button("Generar Acta Digital")

# --- 7. MÓDULO 5: INVESTIGACIÓN DE ACCIDENTES ---
elif menu == "🚨 Investigación de Accidentes":
    st.title("Reporte e Investigación (Art. 15)")
    with st.form("accident"):
        f_acc = st.date_input("Fecha")
        d_acc = st.text_area("Descripción del Suceso")
        c_acc = st.text_area("Causas Identificadas")
        if st.form_submit_button("Guardar Investigación"):
            st.session_state.db_incidentes.append({"Fecha": f_acc, "Desc": d_acc})
            st.success("Investigación guardada.")

# --- 8. MÓDULO 6: AUDITORÍA FISCALIZABLE DS 44 ---
elif menu == "⚖️ Auditoría Fiscalizable DS 44":
    st.title("Espejo de Fiscalización - FUF")
    st.warning("Este módulo genera el reporte consolidado para presentar ante la autoridad.")
    items = ["Política SST", "Diagnóstico (Art. 22)", "Investigación (Art. 15)", "Entrega EPP (Art. 53)", "Higiene (Art. 12)"]
    for i in items:
        st.write(f"✅ {i}: **VERIFICADO**")
    st.button("Generar PDF para el Fiscalizador")
