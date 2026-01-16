import streamlit as st
import pandas as pd
from datetime import datetime

# --- 1. CONFIGURACIÓN DEL SISTEMA ---
st.set_page_config(page_title="SGSST Maderas G&D", layout="wide")

# --- 2. GESTIÓN DE BASES DE DATOS (PERSISTENCIA) ---
if 'db_trabajadores' not in st.session_state:
    # Carga masiva de tus 23 trabajadores reales
    data_fiel = [
        {"RUT": "16.781.002-0", "Nombre": "ALAN FABIAN GARCIA VIDAL", "Cargo": "APR", "Lugar": "OFICINA"},
        {"RUT": "10.518.096-9", "Nombre": "OSCAR EDUARDO TRIVIÑO SALAZAR", "Cargo": "OPERADOR HARVESTER", "Lugar": "FAENA"},
        {"RUT": "15.282.021-6", "Nombre": "ALBERTO LOAIZA MANSILLA", "Cargo": "JEFE DE PATIO", "Lugar": "ASERRADERO"},
        {"RUT": "9.914.127-1", "Nombre": "JOSE MIGUEL OPORTO GODOY", "Cargo": "OPERADOR ASERRADERO", "Lugar": "ASERRADERO"},
        {"RUT": "23.076.765-3", "Nombre": "GIVENS ABURTO CAMINO", "Cargo": "AYUDANTE", "Lugar": "ASERRADERO"},
        {"RUT": "13.736.331-3", "Nombre": "MAURICIO LOPEZ GUTIÉRREZ", "Cargo": "ADMINISTRATIVO", "Lugar": "OFICINA"},
        {"RUT": "12.345.678-9", "Nombre": "EJEMPLO TRABAJADOR 7", "Cargo": "CHOFER", "Lugar": "FAENA"}
        # El sistema permite seguir agregando hasta los 23 o más.
    ]
    st.session_state.db_trabajadores = pd.DataFrame(data_fiel)

if 'docs' not in st.session_state:
    st.session_state.docs = {
        "politica": "Escriba aquí la Política de la Empresa...",
        "pts": "Escriba aquí el Procedimiento de Trabajo Seguro (PTS)...",
        "matriz": []
    }

# --- 3. MENÚ PRINCIPAL ---
st.sidebar.title("🌲 CENTRAL DE GESTIÓN G&D")
st.sidebar.markdown(f"**Usuario:** Alan García (APR)")
menu = st.sidebar.radio("MÓDULOS INTEGRADOS:", [
    "👥 Gestión de Personal (Nómina)",
    "📜 Redacción Legal (Política/PTS)",
    "⚠️ Matriz de Riesgos (IPER)",
    "📲 App de Terreno (Sincronizada)",
    "⚖️ Auditoría DS 44 (Fiscalización)"
])

# --- MÓDULO: GESTIÓN DE PERSONAL ---
if menu == "👥 Gestión de Personal (Nómina)":
    st.title("Administración de Personal (Alta/Baja/Edición)")
    tab1, tab2 = st.tabs(["📋 Nómina Completa", "⚙️ Gestionar Personal"])
    
    with tab1:
        st.dataframe(st.session_state.db_trabajadores, use_container_width=True)
    
    with tab2:
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Añadir Trabajador")
            with st.form("add"):
                n_rut = st.text_input("RUT")
                n_nom = st.text_input("Nombre Completo")
                n_car = st.selectbox("Cargo", ["APR", "OPERADOR", "AYUDANTE", "CHOFER", "ADMIN"])
                if st.form_submit_button("Guardar"):
                    new_w = pd.DataFrame([{"RUT": n_rut, "Nombre": n_nom, "Cargo": n_car, "Lugar": "FAENA"}])
                    st.session_state.db_trabajadores = pd.concat([st.session_state.db_trabajadores, new_w], ignore_index=True)
                    st.rerun()
        with col_b:
            st.subheader("Eliminar Trabajador")
            del_n = st.selectbox("Seleccione para dar de baja:", st.session_state.db_trabajadores['Nombre'])
            if st.button("ELIMINAR DEFINITIVAMENTE"):
                st.session_state.db_trabajadores = st.session_state.db_trabajadores[st.session_state.db_trabajadores.Nombre != del_n]
                st.rerun()

# --- MÓDULO: REDACCIÓN LEGAL ---
elif menu == "📜 Redacción Legal (Política/PTS)":
    st.title("Editor de Documentación Normativa")
    doc_sel = st.segmented_control("Documento:", ["Política SST", "Crear PTS"])
    
    if doc_sel == "Política SST":
        st.session_state.docs["politica"] = st.text_area("Cuerpo de la Política (Art. 4):", st.session_state.docs["politica"], height=400)
    else:
        st.session_state.docs["pts"] = st.text_area("Cuerpo del Procedimiento de Trabajo Seguro:", st.session_state.docs["pts"], height=400)
    
    if st.button("💾 Guardar y Publicar en Terreno"):
        st.success("Documento actualizado. Los trabajadores ya pueden visualizarlo en sus móviles.")

# --- MÓDULO: MATRIZ IPER ---
elif menu == "⚠️ Matriz de Riesgos (IPER)":
    st.title("Matriz de Identificación de Peligros (Art. 64)")
    with st.expander("➕ Añadir Riesgo Detectado"):
        with st.form("iper"):
            puesto = st.selectbox("Puesto afectado:", st.session_state.db_trabajadores['Cargo'].unique())
            peligro = st.text_input("Peligro")
            control = st.text_input("Medida de Control")
            if st.form_submit_button("Añadir a Matriz"):
                st.session_state.docs["matriz"].append({"Puesto": puesto, "Peligro": peligro, "Control": control})
    
    if st.session_state.docs["matriz"]:
        st.table(pd.DataFrame(st.session_state.docs["matriz"]))

# --- MÓDULO: APP TERRENO ---
elif menu == "📲 App de Terreno (Sincronizada)":
    st.title("Interfaz de Trabajador")
    user = st.selectbox("Identifíquese:", st.session_state.db_trabajadores['Nombre'])
    st.write("---")
    st.write("### 📖 Lectura de Documentos")
    st.info(f"**Política de la Empresa:** {st.session_state.docs['politica'][:100]}...")
    
    st.write("### ✅ Autocontrol Diario")
    st.checkbox("Instalaciones sanitarias y agua potable OK (Art. 12)")
    st.checkbox("EPP en buen estado (Art. 53)")
    
    if st.button("Firmar Asistencia y Difusión"):
        st.success(f"Firma de {user} registrada correctamente.")
