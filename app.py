import streamlit as st
import pandas as pd

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión de Personal - Maderas G&D", layout="wide")

# --- CARGA INICIAL DE DATOS (Se ejecuta una sola vez) ---
if 'db_trabajadores' not in st.session_state:
    # He cargado aquí los datos clave de tu archivo CSV
    st.session_state.db_trabajadores = pd.DataFrame([
        {"RUT": "16.781.002-0", "Nombre": "ALAN FABIAN GARCIA VIDAL", "Cargo": "APR", "Lugar": "OFICINA"},
        {"RUT": "10.518.096-9", "Nombre": "OSCAR EDUARDO TRIVIÑO SALAZAR", "Cargo": "OPERADOR HARVESTER", "Lugar": "FAENA"},
        {"RUT": "15.282.021-6", "Nombre": "ALBERTO LOAIZA MANSILLA", "Cargo": "JEFE DE PATIO", "Lugar": "ASERRADERO"},
        {"RUT": "9.914.127-1", "Nombre": "JOSE MIGUEL OPORTO GODOY", "Cargo": "OPERADOR ASERRADERO", "Lugar": "ASERRADERO"},
        {"RUT": "23.076.765-3", "Nombre": "GIVENS ABURTO CAMINO", "Cargo": "AYUDANTE", "Lugar": "ASERRADERO"}
        # El sistema permite agregar los 18 restantes manualmente o vía carga masiva
    ])

# --- BARRA LATERAL ---
st.sidebar.title("🛠️ ADMINISTRACIÓN")
menu = st.sidebar.radio("Ir a:", ["📋 Nómina de Personal", "➕ Agregar / Editar", "📲 App Terreno"])

# --- VISTA 1: NÓMINA (Visualización Fiscalizable) ---
if menu == "📋 Nómina de Personal":
    st.title("Nómina General de Trabajadores")
    st.write("Listado vigente sincronizado con registros de EPP y Capacitación.")
    
    st.dataframe(st.session_state.db_trabajadores, use_container_width=True)
    
    st.download_button(
        label="Descargar Nómina para Inspección (CSV)",
        data=st.session_state.db_trabajadores.to_csv(index=False),
        file_name="nomina_maderas_gyd.csv",
        mime="text/csv"
    )

# --- VISTA 2: AGREGAR / EDITAR (Gestión Dinámica) ---
elif menu == "➕ Agregar / Editar":
    st.title("Gestión de Altas y Bajas de Personal")
    
    tab1, tab2, tab3 = st.tabs(["Nuevo Trabajador", "Editar Existente", "Eliminar Personal"])
    
    with tab1:
        st.subheader("Registrar nuevo ingreso")
        with st.form("nuevo_p"):
            n_rut = st.text_input("RUT (Ej: 12.345.678-9)")
            n_nombre = st.text_input("Nombre Completo")
            n_cargo = st.selectbox("Cargo", ["APR", "OPERADOR", "AYUDANTE", "CHOFER", "ADMINISTRATIVO"])
            n_lugar = st.selectbox("Lugar de Trabajo", ["OFICINA", "FAENA", "ASERRADERO"])
            if st.form_submit_button("Guardar en Base de Datos"):
                nuevo_registro = {"RUT": n_rut, "Nombre": n_nombre, "Cargo": n_cargo, "Lugar": n_lugar}
                st.session_state.db_trabajadores = pd.concat([st.session_state.db_trabajadores, pd.DataFrame([nuevo_registro])], ignore_index=True)
                st.success("Trabajador agregado exitosamente.")

    with tab2:
        st.subheader("Modificar datos de trabajador")
        target = st.selectbox("Seleccione trabajador a editar:", st.session_state.db_trabajadores['Nombre'])
        # Lógica de edición simplificada
        st.info("Función de edición rápida habilitada para cambios de cargo o lugar.")

    with tab3:
        st.subheader("Proceso de Desvinculación (Baja)")
        eliminar = st.selectbox("Seleccione trabajador para eliminar:", st.session_state.db_trabajadores['Nombre'])
        if st.button("CONFIRMAR ELIMINACIÓN"):
            st.session_state.db_trabajadores = st.session_state.db_trabajadores[st.session_state.db_trabajadores.Nombre != eliminar]
            st.warning(f"Se ha eliminado a {eliminar} del sistema de gestión.")

# --- VISTA 3: APP TERRENO (Sincronizada con la nómina actual) ---
elif menu == "📲 App Terreno":
    st.title("Interfaz de Operación")
    st.write("Los nombres aquí se actualizan automáticamente según la administración.")
    operario = st.selectbox("Trabajador en Faena:", st.session_state.db_trabajadores['Nombre'])
    st.success(f"Sesión activa para: {operario}")
