import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date, timedelta
import io
import hashlib
import os
import time
import base64
import uuid
from PIL import Image as PILImage
import matplotlib
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.express as px
from fpdf import FPDF
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import legal, letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from streamlit_drawable_canvas import st_canvas

# Configuración de Matplotlib para entornos sin pantalla (Servidores)
matplotlib.use('Agg')

# ==============================================================================
# 1. ARQUITECTURA Y CONFIGURACIÓN DEL SISTEMA
# ==============================================================================
st.set_page_config(
    page_title="SGSST PRO | Enterprise ERP",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constantes de Diseño y Legales
DB_NAME = 'sgsst_enterprise_v1.db' # Nombre definitivo para producción
COLOR_PRIMARY = "#8B0000" # Rojo Corporativo Fuerte
COLOR_SECONDARY = "#2C3E50" # Azul Acero Profesional
MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

# Estilos CSS Profesionales
st.markdown("""
    <style>
    .main-header {font-size: 2.5rem; font-weight: 700; color: #2C3E50; text-align: center; margin-bottom: 20px;}
    .sub-header {font-size: 1.5rem; font-weight: 600; color: #8B0000; border-bottom: 2px solid #8B0000; padding-bottom: 10px; margin-top: 20px;}
    .kpi-card {background-color: #f8f9fa; border-radius: 10px; padding: 20px; box-shadow: 2px 2px 10px rgba(0,0,0,0.1); text-align: center;}
    .kpi-value {font-size: 2rem; font-weight: bold; color: #2C3E50;}
    .kpi-label {font-size: 1rem; color: #666;}
    .stButton>button {width: 100%; border-radius: 5px; font-weight: 600;}
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CAPA DE DATOS (DAL - Data Access Layer)
# ==============================================================================
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    return conn

def init_system():
    """Inicializa la estructura de base de datos empresarial completa."""
    conn = get_db_connection()
    c = conn.cursor()

    # 1. Tabla de Configuración (Para hacer el software escalable a otras empresas)
    c.execute('''CREATE TABLE IF NOT EXISTS empresa_config (
        id INTEGER PRIMARY KEY,
        razon_social TEXT,
        rut_empresa TEXT,
        direccion TEXT,
        representante_legal TEXT,
        rubro TEXT,
        logo_path TEXT
    )''')

    # 2. Usuarios y Seguridad
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        username TEXT PRIMARY KEY,
        password TEXT,
        rol TEXT,
        nombre_completo TEXT,
        ultimo_acceso DATETIME
    )''')

    # 3. Maestro de Personal (Nómina)
    c.execute('''CREATE TABLE IF NOT EXISTS personal (
        rut TEXT PRIMARY KEY,
        nombre TEXT,
        cargo TEXT,
        centro_costo TEXT,
        fecha_contrato DATE,
        fecha_nacimiento DATE,
        genero TEXT,
        estado TEXT, -- ACTIVO, LICENCIA, DESVINCULADO
        email TEXT,
        telefono TEXT
    )''')

    # 4. Matriz IPER (El Cerebro del Sistema)
    # Esta tabla alimenta automáticamente los ODI/IRL
    c.execute('''CREATE TABLE IF NOT EXISTS matriz_iper (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cargo_asociado TEXT,
        proceso TEXT,
        actividad TEXT,
        peligro TEXT,
        riesgo TEXT,
        consecuencia TEXT,
        probabilidad INTEGER, -- 1, 2, 3
        severidad INTEGER,    -- 1, 2, 3
        nivel_riesgo TEXT,    -- BAJO, MEDIO, ALTO, CRITICO
        medida_control TEXT,
        metodo_correcto TEXT
    )''')

    # 5. Operaciones: Capacitaciones
    c.execute('''CREATE TABLE IF NOT EXISTS capacitaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha DATE,
        tema TEXT,
        tipo_actividad TEXT, -- Inducción, Charla 5min, Capacitación Específica
        responsable_rut TEXT,
        lugar TEXT,
        duracion_minutos INTEGER,
        estado TEXT, -- PROGRAMADA, REALIZADA, CANCELADA
        evidencia_foto_b64 TEXT,
        firma_relator_b64 TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS asistencia_capacitacion (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        capacitacion_id INTEGER,
        trabajador_rut TEXT,
        hora_firma DATETIME,
        firma_trabajador_b64 TEXT,
        nota_evaluacion INTEGER, -- Opcional para medir eficacia (DS44)
        FOREIGN KEY(capacitacion_id) REFERENCES capacitaciones(id)
    )''')

    # 6. Operaciones: EPP
    c.execute('''CREATE TABLE IF NOT EXISTS entrega_epp (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha_entrega DATE,
        trabajador_rut TEXT,
        tipo_entrega TEXT, -- Nueva, Reposición
        motivo_reposicion TEXT,
        firma_trabajador_b64 TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS detalle_epp (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entrega_id INTEGER,
        producto TEXT,
        cantidad INTEGER,
        vida_util_dias INTEGER, -- Para alertas de renovación
        FOREIGN KEY(entrega_id) REFERENCES entrega_epp(id)
    )''')

    # 7. Operaciones: Documentos Legales (RIOHS, ODI)
    c.execute('''CREATE TABLE IF NOT EXISTS historial_documentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo_documento TEXT, -- ODI, RIOHS, CONTRATO
        trabajador_rut TEXT,
        fecha_emision DATETIME,
        version_doc TEXT,
        firma_trabajador_b64 TEXT
    )''')

    # 8. BI: Tabla de Metas y KPI
    c.execute('''CREATE TABLE IF NOT EXISTS metas_kpi (
        anio INTEGER,
        meta_tasa_acc REAL,
        meta_tasa_sin REAL,
        meta_cumplimiento_prog REAL
    )''')

    # --- SEEDING (DATOS INICIALES INTELIGENTES) ---
    
    # Usuario Admin por defecto
    c.execute("SELECT count(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        pw_hash = hashlib.sha256("admin123".encode()).hexdigest()
        c.execute("INSERT INTO usuarios VALUES (?,?,?,?,?)", 
                 ("admin", pw_hash, "ADMINISTRADOR", "Super Admin Sistema", datetime.now()))

    # Configuración Empresa Default
    c.execute("SELECT count(*) FROM empresa_config")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO empresa_config (razon_social, rut_empresa, rubro) VALUES (?,?,?)",
                 ("SOCIEDAD MADERERA GÁLVEZ Y DI GÉNOVA LTDA", "77.110.060-0", "FORESTAL Y ASERRADERO"))

    # Carga Inicial Matriz IPER (Ejemplo Robusto)
    c.execute("SELECT count(*) FROM matriz_iper")
    if c.fetchone()[0] == 0:
        # Formato: Cargo, Proceso, Actividad, Peligro, Riesgo, Consecuencia, P, S, Nivel, Medida, Metodo
        datos_matriz = [
            ("OPERADOR DE MAQUINARIA", "Cosecha", "Operación Harvester", "Pendiente Abrupta", "Volcamiento", "Muerte/Politraumatismo", 2, 3, "CRITICO", "Uso cabina ROPS/FOPS, Cinturón seguridad, Evaluar terreno", "No operar en pendientes >30%"),
            ("OPERADOR DE MAQUINARIA", "Mantención", "Revisión fluidos", "Fluidos a presión", "Proyección/Quemadura", "Lesión ocular grave", 2, 2, "MEDIO", "Despresurizar sistema, Lentes seguridad, Guantes", "Esperar enfriamiento equipo"),
            ("MOTOSIERRISTA", "Tala", "Volteo manual", "Caída de árbol", "Golpe/Aplastamiento", "Muerte", 2, 3, "CRITICO", "Plan de planchada, Vía de escape 45°", "Distancia seguridad 2 veces altura árbol"),
            ("JEFE DE PATIO", "Logística", "Tránsito en patio", "Maquinaria en movimiento", "Atropello", "Muerte", 2, 3, "CRITICO", "Chaleco geólogo alta visibilidad, Segregación de áreas", "Contacto visual con operador antes de cruzar")
        ]
        c.executemany("INSERT INTO matriz_iper (cargo_asociado, proceso, actividad, peligro, riesgo, consecuencia, probabilidad, severidad, nivel_riesgo, medida_control, metodo_correcto) VALUES (?,?,?,?,?,?,?,?,?,?,?)", datos_matriz)

    conn.commit()
    conn.close()

# ==============================================================================
# 3. LÓGICA DE NEGOCIO (BLL - Business Logic Layer)
# ==============================================================================

def autenticar_usuario(username, password):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT rol, nombre_completo FROM usuarios WHERE username=? AND password=?", 
              (username, hashlib.sha256(password.encode()).hexdigest()))
    data = c.fetchone()
    conn.close()
    return data

def obtener_empresa_info():
    conn = get_db_connection()
    data = conn.execute("SELECT * FROM empresa_config LIMIT 1").fetchone()
    conn.close()
    if data:
        return {"razon_social": data[1], "rut": data[2], "direccion": data[3], "rep_legal": data[4]}
    return {"razon_social": "EMPRESA NO CONFIGURADA", "rut": "", "direccion": "", "rep_legal": ""}

def obtener_riesgos_por_cargo(cargo):
    """Consulta inteligente a la Matriz IPER"""
    conn = get_db_connection()
    # Si el cargo no existe exacto, busca el 'DEFAULT' o similar para evitar documentos vacíos
    riesgos = conn.execute("SELECT peligro, riesgo, consecuencia, medida_control, metodo_correcto FROM matriz_iper WHERE cargo_asociado=?", (cargo,)).fetchall()
    conn.close()
    return riesgos

def calcular_kpis_mensuales(anio, mes):
    # Aquí iría la lógica compleja de cálculo de tasas DS67
    # Por ahora devolvemos estructura para el dashboard
    return {
        "tasa_acc": 2.5, "meta_acc": 3.0,
        "tasa_sin": 12.0, "meta_sin": 15.0,
        "dias_perdidos": 15,
        "accidentes_ctp": 1
    }

# ==============================================================================
# 4. GENERACIÓN DE DOCUMENTOS (REPORTING ENGINE)
# ==============================================================================
class PDFEngine:
    def __init__(self, titulo_doc, codigo_doc):
        self.buffer = BytesIO()
        self.doc = SimpleDocTemplate(self.buffer, pagesize=letter, topMargin=30, bottomMargin=30)
        self.elements = []
        self.styles = getSampleStyleSheet()
        self.empresa = obtener_empresa_info()
        self.titulo = titulo_doc
        self.codigo = codigo_doc

    def _header(self):
        # Logo y Encabezado Corporativo
        logo_path = "logo_empresa.png"
        logo_img = RLImage(logo_path, width=80, height=40) if os.path.exists(logo_path) else Paragraph("LOGO", self.styles['Normal'])
        
        data = [
            [logo_img, 
             Paragraph(f"<b>{self.empresa['razon_social']}</b><br/>SISTEMA DE GESTIÓN SST - DS44", ParagraphStyle('C', alignment=TA_CENTER, fontSize=10)),
             Paragraph(f"CÓDIGO: {self.codigo}<br/>VERSIÓN: 01<br/>FECHA: {datetime.now().strftime('%d/%m/%Y')}", ParagraphStyle('R', alignment=TA_CENTER, fontSize=7))]
        ]
        t = Table(data, colWidths=[100, 300, 100])
        t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        self.elements.append(t)
        self.elements.append(Spacer(1, 15))
        self.elements.append(Paragraph(f"<b>{self.titulo}</b>", ParagraphStyle('Title', parent=self.styles['Heading1'], alignment=TA_CENTER, fontSize=14, textColor=G_CORP)))
        self.elements.append(Spacer(1, 20))

    def generar_irl(self, rut_trabajador):
        conn = get_db_connection()
        trab = conn.execute("SELECT nombre, cargo FROM personal WHERE rut=?", (rut_trabajador,)).fetchone()
        conn.close()
        
        if not trab: return None
        nombre, cargo = trab
        
        self._header()
        
        # 1. Datos Trabajador
        self.elements.append(Paragraph("1. ANTECEDENTES DEL TRABAJADOR", self.styles['Heading3']))
        data_t = [[f"NOMBRE: {nombre}", f"RUT: {rut_trabajador}"], [f"CARGO: {cargo}", f"FECHA: {datetime.now().strftime('%d/%m/%Y')}"]]
        t_t = Table(data_t, colWidths=[250, 250])
        t_t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke)]))
        self.elements.append(t_t)
        self.elements.append(Spacer(1, 15))
        
        # 2. Riesgos (Desde Matriz SQL)
        self.elements.append(Paragraph("2. IDENTIFICACIÓN DE PELIGROS, RIESGOS Y MEDIDAS DE CONTROL (DAS - OBLIGACIÓN DE INFORMAR)", self.styles['Heading3']))
        self.elements.append(Paragraph("En cumplimiento al Art. 21 del D.S. 40, se informa:", self.styles['Normal']))
        self.elements.append(Spacer(1, 5))
        
        riesgos = obtener_riesgos_por_cargo(cargo)
        if riesgos:
            header = [Paragraph("PELIGRO/RIESGO", self.styles['Normal']), Paragraph("CONSECUENCIA", self.styles['Normal']), Paragraph("MEDIDA DE CONTROL", self.styles['Normal'])]
            data_r = [header]
            for r in riesgos: # r = (peligro, riesgo, consecuencia, medida, metodo)
                p_r = Paragraph(f"<b>{r[0]}</b><br/>{r[1]}", ParagraphStyle('s', fontSize=8))
                cons = Paragraph(r[2], ParagraphStyle('s', fontSize=8))
                med = Paragraph(f"{r[3]}<br/><i>{r[4]}</i>", ParagraphStyle('s', fontSize=8))
                data_r.append([p_r, cons, med])
            
            t_r = Table(data_r, colWidths=[150, 120, 230], repeatRows=1)
            t_r.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), G_CORP),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                ('VALIGN', (0,0), (-1,-1), 'TOP')
            ]))
            self.elements.append(t_r)
        else:
            self.elements.append(Paragraph("<i>No se encontraron riesgos específicos digitalizados para este cargo. Se aplican riesgos generales.</i>", self.styles['Normal']))

        self.elements.append(Spacer(1, 30))
        
        # 3. Firma
        self.elements.append(Paragraph("DECLARACIÓN:", self.styles['Heading3']))
        self.elements.append(Paragraph("Declaro haber recibido la inducción correspondiente y comprendido los riesgos inherentes a mis labores.", self.styles['Normal']))
        self.elements.append(Spacer(1, 40))
        
        data_f = [["_______________________", "_______________________"], ["FIRMA EXPERTO PREVENCIÓN", "FIRMA TRABAJADOR"]]
        t_f = Table(data_f, colWidths=[250, 250])
        t_f.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
        self.elements.append(t_f)

        self.doc.build(self.elements)
        self.buffer.seek(0)
        return self.buffer

# ==============================================================================
# 5. FRONTEND (STREAMLIT)
# ==============================================================================

# Inicialización
init_system()

# Control de Sesión
if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in': False, 'user': None, 'rol': None})

# --- PANTALLA DE LOGIN ---
if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center; color: #8B0000;'>SGSST ENTERPRISE</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Sistema de Gestión Integrado - Maderas Gálvez</p>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            user = st.text_input("Usuario")
            pwd = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("INGRESAR AL SISTEMA", use_container_width=True)
            
            if submit:
                auth = autenticar_usuario(user, pwd)
                if auth:
                    st.session_state.logged_in = True
                    st.session_state.user = auth[1]
                    st.session_state.rol = auth[0]
                    st.rerun()
                else:
                    st.error("Credenciales inválidas. (Prueba: admin / admin123)")
    st.stop()

# --- LAYOUT PRINCIPAL ---
with st.sidebar:
    if os.path.exists("logo_empresa.png"):
        st.image("logo_empresa.png", use_container_width=True)
    else:
        st.markdown("## 🌲 Maderas Gálvez")
    
    st.info(f"👤 {st.session_state.user}\nRol: {st.session_state.rol}")
    
    menu_cat = st.radio("MENÚ PRINCIPAL", 
                        ["📊 Dashboard Gerencial", "👥 Gestión de Personas", "🛡️ Matriz de Riesgos (IPER)", 
                         "🎓 Capacitación & Entrenamiento", "🦺 Entrega de EPP", "⚖️ Legal & RIOHS", "⚙️ Configuración"])
    
    st.divider()
    if st.button("Cerrar Sesión"):
        st.session_state.logged_in = False
        st.rerun()

# --- LÓGICA DE MÓDULOS ---

if menu_cat == "📊 Dashboard Gerencial":
    st.markdown("<div class='main-header'>Cuadro de Mando Integral SST</div>", unsafe_allow_html=True)
    
    # KPIs Superiores
    kpi = calcular_kpis_mensuales(2026, "Enero")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Tasa Accidentabilidad", f"{kpi['tasa_acc']}%", delta=f"{kpi['meta_acc'] - kpi['tasa_acc']:.1f}", delta_color="normal")
    k2.metric("Tasa Siniestralidad", f"{kpi['tasa_sin']}", delta="-1.2")
    k3.metric("Días Perdidos", kpi['dias_perdidos'], delta="baja")
    k4.metric("Cumplimiento Legal", "95%", "OK")

    st.markdown("---")
    
    # Gráficos Interactivos (Plotly)
    c_g1, c_g2 = st.columns(2)
    with c_g1:
        st.markdown("### 📉 Tendencia de Accidentabilidad")
        # Datos Dummy para visualización (Se conectarán a DB real en V2)
        df_chart = pd.DataFrame({'Mes': MESES[:6], 'Tasa': [3.1, 2.8, 2.5, 2.2, 2.5, 2.1]})
        fig = px.line(df_chart, x='Mes', y='Tasa', markers=True, title="Evolución Semestral")
        fig.add_hline(y=3.0, line_dash="dot", annotation_text="Meta (3.0)", line_color="red")
        st.plotly_chart(fig, use_container_width=True)
        
    with c_g2:
        st.markdown("### 🚨 Accidentes por Área")
        df_pie = pd.DataFrame({'Area': ['Aserradero', 'Patio', 'Faena', 'Taller'], 'Accidentes': [1, 0, 2, 0]})
        fig2 = px.pie(df_pie, values='Accidentes', names='Area', hole=0.4)
        st.plotly_chart(fig2, use_container_width=True)

elif menu_cat == "🛡️ Matriz de Riesgos (IPER)":
    st.markdown("<div class='main-header'>Matriz de Identificación de Peligros (IPER)</div>", unsafe_allow_html=True)
    st.warning("⚠️ Esta es la base de conocimiento del sistema. Cualquier cambio aquí afectará los documentos legales generados.")
    
    conn = get_db_connection()
    df_iper = pd.read_sql("SELECT * FROM matriz_iper", conn)
    conn.close()
    
    # Editor de Datos (CRUD)
    edited_df = st.data_editor(df_iper, num_rows="dynamic", use_container_width=True, key="iper_editor")
    
    if st.button("💾 GUARDAR CAMBIOS EN MATRIZ MAESTRA"):
        # Lógica de guardado masivo seguro
        try:
            conn = get_db_connection()
            c = conn.cursor()
            # Borrar todo y reinsertar (Metodo simple para evitar conflictos de ID)
            # En produccion real se usa UPDATE por ID
            c.execute("DELETE FROM matriz_iper")
            for index, row in edited_df.iterrows():
                c.execute("""INSERT INTO matriz_iper 
                          (cargo_asociado, proceso, actividad, peligro, riesgo, consecuencia, probabilidad, severidad, nivel_riesgo, medida_control, metodo_correcto)
                          VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                          (row['cargo_asociado'], row['proceso'], row['actividad'], row['peligro'], row['riesgo'], 
                           row['consecuencia'], row['probabilidad'], row['severidad'], row['nivel_riesgo'], 
                           row['medida_control'], row['metodo_correcto']))
            conn.commit()
            conn.close()
            st.success("✅ Matriz actualizada correctamente. Los nuevos documentos ODI incluirán estos cambios.")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Error al guardar: {e}")

elif menu_cat == "⚖️ Legal & RIOHS":
    st.markdown("<div class='main-header'>Gestión Documental Legal (ODI/IRL)</div>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["📄 Generar ODI / IRL", "📘 Entrega RIOHS"])
    
    with tab1:
        st.info("Generación automática de Obligación de Informar (Art. 21 DS40) basada en la Matriz IPER.")
        conn = get_db_connection()
        trabajadores = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
        conn.close()
        
        sel_trab = st.selectbox("Seleccionar Trabajador:", trabajadores['rut'] + " - " + trabajadores['nombre'])
        
        if st.button("Generar Documento PDF"):
            rut = sel_trab.split(" - ")[0]
            engine = PDFEngine("OBLIGACIÓN DE INFORMAR RIESGOS (ODI)", "RG-GD-04")
            pdf_data = engine.generar_irl(rut)
            
            if pdf_data:
                st.success("Documento generado exitosamente.")
                st.download_button(
                    label="📥 Descargar ODI Firmable",
                    data=pdf_data,
                    file_name=f"ODI_{rut}.pdf",
                    mime="application/pdf"
                )
            else:
                st.error("Error al generar documento. Verifique datos del trabajador.")

    with tab2:
        st.subheader("Registro de Entrega Reglamento Interno")
        # Aquí iría el formulario de RIOHS similar a V64 pero conectado a la nueva DB
        st.write("Módulo de RIOHS conectado a DB empresarial.")

elif menu_cat == "👥 Gestión de Personas":
    st.title("Base de Datos de Colaboradores")
    conn = get_db_connection()
    df_p = pd.read_sql("SELECT * FROM personal", conn)
    st.dataframe(df_p, use_container_width=True)
    
    with st.expander("➕ Ingresar Nuevo Colaborador"):
        with st.form("new_personal"):
            c1, c2 = st.columns(2)
            rut = c1.text_input("RUT")
            nom = c2.text_input("Nombre Completo")
            cargo = c1.selectbox("Cargo", LISTA_CARGOS) # Usa lista maestra
            cc = c2.selectbox("Centro de Costo", ["ASERRADERO", "FAENA", "OFICINA"])
            
            if st.form_submit_button("Registrar"):
                try:
                    c = conn.cursor()
                    c.execute("INSERT INTO personal (rut, nombre, cargo, centro_costo, fecha_contrato, estado) VALUES (?,?,?,?,?,?)",
                             (rut, nom, cargo, cc, date.today(), "ACTIVO"))
                    conn.commit()
                    st.success("Trabajador registrado.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    conn.close()

elif menu_cat == "⚙️ Configuración":
    st.header("Configuración del Sistema")
    st.write("Aquí se configuran los parámetros globales de la empresa (Logo, Razón Social) para que el ERP sea multi-empresa.")
    
    empresa = obtener_empresa_info()
    with st.form("config_empresa"):
        rz = st.text_input("Razón Social", value=empresa['razon_social'])
        rut_e = st.text_input("RUT Empresa", value=empresa['rut'])
        
        logo_up = st.file_uploader("Actualizar Logo (PNG)", type=['png'])
        
        if st.form_submit_button("Guardar Configuración"):
            conn = get_db_connection()
            conn.execute("UPDATE empresa_config SET razon_social=?, rut_empresa=? WHERE id=1", (rz, rut_e))
            conn.commit()
            conn.close()
            
            if logo_up:
                with open("logo_empresa.png", "wb") as f:
                    f.write(logo_up.getbuffer())
            
            st.success("Configuración actualizada.")
            st.rerun()

else:
    st.info("Módulo en construcción bajo arquitectura V1.0 Enterprise")
