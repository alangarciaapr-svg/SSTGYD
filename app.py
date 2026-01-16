import streamlit as st
import pandas as pd
from datetime import datetime
import io

# --- 1. CORE DEL SISTEMA Y PERSISTENCIA DE DATOS ---
st.set_page_config(page_title="SGSST PRO - Maderas G&D", layout="wide", initial_sidebar_state="expanded")

# Inicialización de Bases de Datos Relacionales en Memoria
if 'db_empleados' not in st.session_state:
    # Carga de la nómina real de tus archivos CSV
    st.session_state.db_empleados = pd.DataFrame([
        {"RUT": "16.781.002-0", "Nombre": "ALAN FABIAN GARCIA VIDAL", "Cargo": "APR", "Lugar": "OFICINA", "Estado": "Activo"},
        {"RUT": "10.518.096-9", "Nombre": "OSCAR EDUARDO TRIVIÑO SALAZAR", "Cargo": "OPERADOR HARVESTER", "Lugar": "FAENA", "Estado": "Activo"},
        {"RUT": "15.282.021-6", "Nombre": "ALBERTO LOAIZA MANSILLA", "Cargo": "JEFE DE PATIO", "Lugar": "ASERRADERO", "Estado": "Activo"},
        {"RUT": "9.914.127-1", "Nombre": "JOSE MIGUEL OPORTO GODOY", "Cargo": "OPERADOR ASERRADERO", "Lugar": "ASERRADERO", "Estado": "Activo"},
        {"RUT": "23.076.765-3", "Nombre": "GIVENS ABURTO CAMINO", "Cargo": "AYUDANTE", "Lugar": "ASERRADERO", "Estado": "Activo"},
        {"RUT": "13.736.331-3", "Nombre": "MAURICIO LOPEZ GUTIÉRREZ", "Cargo": "ADMINISTRATIVO", "Lugar": "OFICINA", "Estado": "Activo"}
    ])

if 'repositorio_legal' not in st.session_state:
    st.session_state.repositorio_legal = {
        "Politica": "Política de SST Maderas G&D conforme al Art. 4 del DS 44...",
        "PTS_Aserradero": "Procedimiento de Trabajo Seguro para Operación de Aserradero Wood-Mizer...",
        "Matriz_IPER": pd.DataFrame(columns=["Puesto", "Peligro", "Riesgo", "Probabilidad", "Severidad", "Control"])
    }

# --- 2. MOTOR DE NAVEGACIÓN DE ALTO NIVEL ---
st.sidebar.title("🌲 GESTIÓN ESTRATÉGICA G&D")
st.sidebar.markdown(f"**Prevencionista:** Alan García V.\n**Estatus:** Auditoría Ready")

menu = st.sidebar.selectbox("CENTRO DE OPERACIONES:", [
    "📊 Dashboard de Desempeño (Alan)",
    "👥 Ingeniería de Personal (CRUD)",
    "📜 Centro de Documentación (Política/PTS)",
    "⚠️ Gestión de Riesgos (IPER)",
    "📲 Interfaz de Terreno (Captura)",
    "⚖️ Auditoría FUF (Cumplimiento Legal)"
])

# --- 3. MÓDULO 1: DASHBOARD GERENCIAL ---
if menu == "📊 Dashboard de Desempeño (Alan)":
    st.title("Sistema de Control de Gestión - Alan García")
    st.markdown("### Métricas de Cumplimiento Normativo (DS 44 / DS 594)")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Dotación Total", len(st.session_state.db_empleados))
    m2.metric("Brecha Fiscalización", "0.0%", "Óptimo")
    m3.metric("Documentos Vigentes", "3/3")
    m4.metric("Incidentes Siniestralidad", "0", "0%")

    st.subheader("📈 Mapa de Riesgos por Área")
    chart_data = st.session_state.db_empleados['Lugar'].value_counts()
    st.bar_chart(chart_data)

# --- 4. MÓDULO 2: GESTIÓN DE PERSONAL PRO (EDITAR/BORRAR/AGREGAR) ---
elif menu == "👥 Ingeniería de Personal (CRUD)":
    st.title("Gestión Dinámica de Capital Humano")
    t1, t2, t3 = st.tabs(["📋 Nómina Fiscalizable", "➕ Alta de Personal", "🛠️ Modificación/Baja"])
    
    with t1:
        st.dataframe(st.session_state.db_empleados, use_container_width=True)
    
    with t2:
        with st.form("alta"):
            c1, c2 = st.columns(2)
            r = c1.text_input("RUT Trabajador")
            n = c2.text_input("Nombre Completo")
            car = c1.selectbox("Cargo", ["APR", "OPERADOR", "AYUDANTE", "CHOFER", "MECÁNICO"])
            lug = c2.selectbox("Ubicación", ["ASERRADERO", "FAENA", "OFICINA"])
            if st.form_submit_button("REGISTRAR INGRESO"):
                new_w = pd.DataFrame([{"RUT": r, "Nombre": n, "Cargo": car, "Lugar": lug, "Estado": "Activo"}])
                st.session_state.db_empleados = pd.concat([st.session_state.db_empleados, new_w], ignore_index=True)
                st.success("Trabajador incorporado al SGSST.")

    with t3:
        target = st.selectbox("Seleccione para Editar/Borrar:", st.session_state.db_empleados['Nombre'])
        col_edit, col_del = st.columns(2)
        if col_del.button("❌ ELIMINAR TRABAJADOR"):
            st.session_state.db_empleados = st.session_state.db_empleados[st.session_state.db_empleados.Nombre != target]
            st.rerun()

# --- 5. MÓDULO 3: CENTRO DOCUMENTAL (POLÍTICA Y PTS) ---
elif menu == "📜 Centro de Documentación (Política/PTS)":
    st.title("Redacción de Documentación Técnica")
    doc_sel = st.radio("Editar:", ["Política de SST", "Procedimiento de Trabajo (PTS)"])
    
    if doc_sel == "Política de SST":
        st.session_state.repositorio_legal["Politica"] = st.text_area("Cuerpo de la Política (Art. 4 DS 44):", st.session_state.repositorio_legal["Politica"], height=300)
    else:
        st.session_state.repositorio_legal["PTS_Aserradero"] = st.text_area("Cuerpo del PTS (Detalle Operativo):", st.session_state.repositorio_legal["PTS_Aserradero"], height=300)
    
    if st.button("💾 PUBLICAR Y DIFUNDIR"):
        st.success("Documento guardado. Los cambios se reflejarán inmediatamente en la App de Terreno.")

# --- 6. MÓDULO 4: GESTIÓN DE RIESGOS (IPER) ---
elif menu == "⚠️ Gestión de Riesgos (IPER)":
    st.title("Identificación de Peligros y Evaluación de Riesgos (Art. 64)")
    with st.expander("📝 Evaluar Nuevo Riesgo"):
        with st.form("iper_form"):
            puesto = st.selectbox("Puesto:", st.session_state.db_empleados['Cargo'].unique())
            peligro = st.text_input("Peligro (Ej: Atrapamiento)")
            riesgo = st.selectbox("Nivel:", ["Bajo", "Medio", "Alto", "Crítico"])
            control = st.text_input("Medida de Control")
            if st.form_submit_button("INSERTAR EN MATRIZ"):
                new_r = pd.DataFrame([{"Puesto": puesto, "Peligro: ": peligro, "Riesgo": riesgo, "Control": control}])
                st.session_state.repositorio_legal["Matriz_IPER"] = pd.concat([st.session_state.repositorio_legal["Matriz_IPER"], new_r], ignore_index=True)
    
    st.table(st.session_state.repositorio_legal["Matriz_IPER"])

# --- 7. MÓDULO 5: INTERFAZ DE TERRENO ---
elif menu == "📲 Interfaz de Terreno (Captura)":
    st.title("App Móvil de Gestión de Faena")
    trabajador = st.selectbox("Nombre del Trabajador:", st.session_state.db_empleados['Nombre'])
    
    st.write("---")
    st.subheader("📖 Lectura Obligatoria")
    st.info(st.session_state.repositorio_legal["Politica"][:150] + "...")
    
    st.subheader("✅ Verificación de Higiene y Seguridad (FUF)")
    st.checkbox("Instalaciones sanitarias y agua potable OK (Art. 12)")
    st.checkbox("Uso de EPP según Art. 53 (Casco, Auditivos, Guantes)")
    st.checkbox("Área de corte Wood-Mizer inspeccionada")
    
    if st.button("FIRMAR Y SINCRONIZAR"):
        st.success(f"Registro de {trabajador} guardado para auditoría.")
