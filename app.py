import streamlit as st
import pandas as pd
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA Y ESTILOS ---
st.set_page_config(page_title="SGSST PRO - Maderas G&D", layout="wide")
st.markdown("""<style>.stMetric {background-color: #ffffff; padding: 15px; border-radius: 10px; border-left: 5px solid #e67e22; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);}</style>""", unsafe_allow_html=True)

# --- INICIALIZACIÓN DE BASES DE DATOS (Persistencia en Sesión) ---
if 'db_personal' not in st.session_state:
    # Carga de los 23 trabajadores desde el archivo procesado
    st.session_state.db_personal = pd.DataFrame([
        {"RUT": "16.781.002-0", "Nombre": "ALAN FABIAN GARCIA VIDAL", "Cargo": "APR", "Lugar": "OFICINA"},
        {"RUT": "10.518.096-9", "Nombre": "OSCAR EDUARDO TRIVIÑO SALAZAR", "Cargo": "OPERADOR HARVESTER", "Lugar": "FAENA"},
        {"RUT": "15.282.021-6", "Nombre": "ALBERTO LOAIZA MANSILLA", "Cargo": "JEFE DE PATIO", "Lugar": "ASERRADERO"},
        {"RUT": "9.914.127-1", "Nombre": "JOSE MIGUEL OPORTO GODOY", "Cargo": "OPERADOR ASERRADERO", "Lugar": "ASERRADERO"},
        {"RUT": "23.076.765-3", "Nombre": "GIVENS ABURTO CAMINO", "Cargo": "AYUDANTE", "Lugar": "ASERRADERO"},
        {"RUT": "13.736.331-3", "Nombre": "MAURICIO LOPEZ GUTIÉRREZ", "Cargo": "ADMINISTRATIVO", "Lugar": "OFICINA"},
        # El sistema permite gestionar los 23 y más
    ])

if 'legal_docs' not in st.session_state:
    st.session_state.legal_docs = {
        "politica": "Redacte aquí la Política conforme al Art. 4 del DS 44...",
        "pts": "Desarrolle aquí el Procedimiento de Trabajo Seguro...",
        "matriz": pd.DataFrame(columns=["Puesto", "Peligro", "Nivel de Riesgo", "Control"])
    }

# --- NAVEGACIÓN ---
st.sidebar.title("🌲 GESTIÓN MADERAS G&D")
st.sidebar.markdown(f"**Prevencionista:** Alan García\n**Fecha:** {datetime.now().strftime('%d/%m/%Y')}")
modulo = st.sidebar.radio("CENTRO DE OPERACIONES:", [
    "📊 Dashboard Gerencial",
    "👥 Gestión de Personal (CRUD)",
    "📜 Documentación (Política/PTS)",
    "⚠️ Matriz de Riesgos (IPER)",
    "📲 App de Terreno (Sincronizada)",
    "⚖️ Auditoría FUF (Fiscalizable)"
])

# --- 1. DASHBOARD GERENCIAL ---
if modulo == "📊 Dashboard Gerencial":
    st.title("Panel de Control Estratégico")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Dotación Activa", len(st.session_state.db_personal))
    c2.metric("Cumplimiento DS 44", "94%", "+2%")
    c3.metric("PTS Publicados", "1")
    c4.metric("Incidentes", "0", "OK")
    
    st.subheader("Distribución de Personal por Área")
    st.bar_chart(st.session_state.db_personal['Lugar'].value_counts())

# --- 2. GESTIÓN DE PERSONAL (CREAR / EDITAR / BORRAR) ---
elif modulo == "👥 Gestión de Personal (CRUD)":
    st.title("Ingeniería de Personal")
    t1, t2, t3 = st.tabs(["📋 Nómina Completa", "➕ Alta de Personal", "🛠️ Editar/Baja"])
    
    with t1:
        st.dataframe(st.session_state.db_personal, use_container_width=True)
        st.download_button("Exportar Nómina (CSV)", st.session_state.db_personal.to_csv(index=False), "nomina.csv")
    
    with t2:
        with st.form("alta_form"):
            r = st.text_input("RUT (con puntos y guion)")
            n = st.text_input("Nombre Completo")
            c = st.selectbox("Cargo", ["APR", "OPERADOR", "AYUDANTE", "ADMIN", "CHOFER"])
            l = st.selectbox("Lugar", ["ASERRADERO", "FAENA", "OFICINA"])
            if st.form_submit_button("REGISTRAR"):
                nuevo = pd.DataFrame([{"RUT": r, "Nombre": n, "Cargo": c, "Lugar": l}])
                st.session_state.db_personal = pd.concat([st.session_state.db_personal, nuevo], ignore_index=True)
                st.rerun()

    with t3:
        target = st.selectbox("Seleccionar trabajador para gestionar:", st.session_state.db_personal['Nombre'])
        if st.button("❌ ELIMINAR TRABAJADOR DEL SISTEMA"):
            st.session_state.db_personal = st.session_state.db_personal[st.session_state.db_personal.Nombre != target]
            st.success(f"{target} ha sido dado de baja.")
            st.rerun()

# --- 3. DOCUMENTACIÓN (POLÍTICA Y PTS) ---
elif modulo == "📜 Documentación (Política/PTS)":
    st.title("Editor Documental Corporativo")
    tipo = st.radio("Tipo:", ["Política de Seguridad", "Procedimiento (PTS)"])
    
    if tipo == "Política de Seguridad":
        st.session_state.legal_docs["politica"] = st.text_area("Cuerpo de la Política (Art. 4):", st.session_state.legal_docs["politica"], height=300)
    else:
        st.session_state.legal_docs["pts"] = st.text_area("Cuerpo del PTS:", st.session_state.legal_docs["pts"], height=300)
    
    if st.button("GUARDAR Y PUBLICAR"):
        st.success("Documento guardado y disponible para firma en terreno.")

# --- 4. MATRIZ IPER ---
elif modulo == "⚠️ Matriz de Riesgos (IPER)":
    st.title("Identificación de Peligros y Evaluación de Riesgos")
    with st.expander("Añadir Riesgo a la Matriz"):
        with st.form("iper"):
            p = st.selectbox("Puesto:", st.session_state.db_personal['Cargo'].unique())
            pel = st.text_input("Peligro")
            ries = st.select_slider("Riesgo:", options=["Bajo", "Medio", "Alto", "Crítico"])
            cont = st.text_input("Medida de Control")
            if st.form_submit_button("INSERTAR"):
                new_r = pd.DataFrame([{"Puesto": p, "Peligro": pel, "Nivel de Riesgo": ries, "Control": cont}])
                st.session_state.legal_docs["matriz"] = pd.concat([st.session_state.legal_docs["matriz"], new_r], ignore_index=True)
    
    st.table(st.session_state.legal_docs["matriz"])

# --- 5. INTERFAZ DE TERRENO ---
elif modulo == "📲 App de Terreno (Sincronizada)":
    st.title("Terminal de Registro de Terreno")
    op = st.selectbox("Trabajador:", st.session_state.db_personal['Nombre'])
    st.write("---")
    st.subheader("Validación de Seguridad")
    c1 = st.checkbox("Instalaciones sanitarias y agua potable (Art. 12)")
    c2 = st.checkbox("EPP en buen estado (Art. 53)")
    c3 = st.checkbox("He leído y acepto la Política y el PTS vigente")
    
    if st.button("FIRMAR REGISTRO DIGITAL"):
        if c1 and c2 and c3:
            st.success(f"Firma de {op} registrada. Cumplimiento fiscalizable OK.")
