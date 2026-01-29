import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import io
import hashlib
import os
import time
import base64
import ast
import socket
from PIL import Image as PILImage
import matplotlib
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from streamlit_drawable_canvas import st_canvas
import openpyxl 

# Manejo seguro de librería QR
try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

# Configuración Matplotlib
matplotlib.use('Agg')

# ==============================================================================
# 1. CONFIGURACIÓN E INTERCEPTOR MÓVIL (QR)
# ==============================================================================
st.set_page_config(page_title="SGSST ERP MASTER", layout="wide", page_icon="🏗️")

DB_NAME = 'sgsst_v128_final_syntax.db'
COLOR_PRIMARY = "#8B0000"
COLOR_SECONDARY = "#2C3E50"

# --- MODO KIOSCO (FIRMA MÓVIL) ---
query_params = st.query_params
if "mobile_sign" in query_params and query_params["mobile_sign"] == "true":
    cap_id_mobile = query_params.get("cap_id", None)
    st.markdown(f"<h2 style='text-align: center; color: {COLOR_PRIMARY}'>✍️ Firma de Asistencia</h2>", unsafe_allow_html=True)
    
    if cap_id_mobile:
        conn = sqlite3.connect(DB_NAME)
        try:
            cap_data = pd.read_sql("SELECT tema, fecha FROM capacitaciones WHERE id=?", conn, params=(cap_id_mobile,))
            if not cap_data.empty:
                st.info(f"Actividad: {cap_data.iloc[0]['tema']} ({cap_data.iloc[0]['fecha']})")
                with st.form("mobile_sign_form"):
                    rut_input = st.text_input("Ingresa tu RUT (con guión)", placeholder="12345678-9")
                    st.write("Firma aquí:")
                    canvas_mobile = st_canvas(
                        stroke_width=2, 
                        stroke_color="black", 
                        background_color="#eee", 
                        height=200, 
                        width=300, 
                        key="mobile_c",
                        drawing_mode="freedraw"
                    )
                    
                    if st.form_submit_button("ENVIAR FIRMA"):
                        if rut_input and canvas_mobile.image_data is not None:
                            check = pd.read_sql("SELECT id FROM asistencia_capacitacion WHERE capacitacion_id=? AND trabajador_rut=?", conn, params=(cap_id_mobile, rut_input))
                            if not check.empty:
                                img = PILImage.fromarray(canvas_mobile.image_data.astype('uint8'), 'RGBA'); b = io.BytesIO(); img.save(b, format='PNG'); img_str = base64.b64encode(b.getvalue()).decode()
                                conn.execute("UPDATE asistencia_capacitacion SET estado='FIRMADO', firma_b64=? WHERE capacitacion_id=? AND trabajador_rut=?", (img_str, cap_id_mobile, rut_input))
                                conn.commit()
                                st.success("✅ Firma registrada. Gracias.")
                            else: st.error("❌ RUT no inscrito en esta capacitación.")
                        else: st.warning("⚠️ Faltan datos.")
            else: st.error("Capacitación no encontrada.")
        except: st.error("Error de conexión con DB Móvil.")
        conn.close()
    st.stop() 

# --- ESTILOS CSS ---
st.markdown("""
    <style>
    .main-header {font-size: 2.0rem; font-weight: 700; color: #2C3E50; border-bottom: 3px solid #8B0000; margin-bottom: 15px;}
    .alert-box {padding: 10px; border-radius: 5px; margin-bottom: 5px; font-size: 0.9rem; font-weight: 500;}
    .alert-high {background-color: #ffebee; color: #b71c1c; border-left: 5px solid #d32f2f;}
    .alert-ok {background-color: #e8f5e9; color: #2e7d32; border-left: 5px solid #388e3c;}
    </style>
""", unsafe_allow_html=True)

LISTA_CARGOS = ["GERENTE GENERAL", "PREVENCIONISTA DE RIESGOS", "JEFE DE PATIO", "OPERADOR DE ASERRADERO", "OPERADOR DE MAQUINARIA", "MOTOSIERRISTA", "ESTROBERO", "MECANICO", "ADMINISTRATIVO"]
LISTA_PROBABILIDAD = [1, 2, 4]
LISTA_CONSECUENCIA = [1, 2, 4]

# ==============================================================================
# 2. CAPA DE DATOS (SQL)
# ==============================================================================
def get_conn(): return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    # --- 1. CREACIÓN DE TABLAS (Mantenemos todo lo que tenías) ---
    c.execute('''CREATE TABLE IF NOT EXISTS personal (rut TEXT PRIMARY KEY, nombre TEXT, cargo TEXT, centro_costo TEXT, fecha_contrato DATE, estado TEXT, vigencia_examen_medico DATE, email TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS matriz_iper (id INTEGER PRIMARY KEY AUTOINCREMENT, proceso TEXT, tipo_proceso TEXT, puesto_trabajo TEXT, tarea TEXT, es_rutinaria TEXT, peligro_factor TEXT, riesgo_asociado TEXT, tipo_riesgo TEXT, probabilidad INTEGER, consecuencia INTEGER, vep INTEGER, nivel_riesgo TEXT, medida_control TEXT, genero_obs TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS capacitaciones (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tema TEXT, tipo_actividad TEXT, responsable_rut TEXT, estado TEXT, duracion INTEGER, lugar TEXT, metodologia TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS asistencia_capacitacion (id INTEGER PRIMARY KEY AUTOINCREMENT, capacitacion_id INTEGER, trabajador_rut TEXT, nombre_trabajador TEXT, cargo_trabajador TEXT, estado TEXT, firma_b64 TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS registro_epp (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrega DATE, rut_trabajador TEXT, nombre_trabajador TEXT, cargo TEXT, lista_productos TEXT, firma_b64 TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS registro_riohs (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrega DATE, rut_trabajador TEXT, nombre_trabajador TEXT, tipo_entrega TEXT, firma_b64 TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS incidentes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tipo TEXT, descripcion TEXT, area TEXT, severidad TEXT, rut_afectado TEXT, nombre_afectado TEXT, parte_cuerpo TEXT, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS inventario_epp (id INTEGER PRIMARY KEY AUTOINCREMENT, producto TEXT, stock_actual INTEGER, stock_minimo INTEGER, ubicacion TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS extintores (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, tipo TEXT, capacidad TEXT, ubicacion TEXT, fecha_vencimiento DATE, estado_inspeccion TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS programa_anual (id INTEGER PRIMARY KEY AUTOINCREMENT, actividad TEXT, responsable TEXT, fecha_programada DATE, estado TEXT, fecha_ejecucion DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS contratistas (id INTEGER PRIMARY KEY AUTOINCREMENT, rut_empresa TEXT, razon_social TEXT, estado_documental TEXT, fecha_vencimiento_f30 DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT, rol TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS auditoria (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATETIME, usuario TEXT, accion TEXT, detalle TEXT)''')

    # --- 2. CARGA DE DATOS INICIAL (AQUÍ ESTABA EL ERROR, CORREGIDO) ---
    
    # Verificación segura de Usuarios
    c.execute("SELECT count(*) FROM usuarios")
    data_u = c.fetchone()
    if data_u is None or data_u[0] == 0:
        c.execute("INSERT INTO usuarios VALUES (?,?,?)", ("admin", hashlib.sha256("1234".encode()).hexdigest(), "ADMINISTRADOR"))

    # Verificación segura de Inventario
    c.execute("SELECT count(*) FROM inventario_epp")
    data_i = c.fetchone()
    if data_i is None or data_i[0] == 0:
        c.executemany("INSERT INTO inventario_epp (producto, stock_actual, stock_minimo, ubicacion) VALUES (?,?,?,?)", [("Casco", 50, 5, "Bodega"), ("Lentes", 100, 10, "Bodega")])

    # Verificación segura de Personal (SOLUCIÓN DEL PROBLEMA DE REEMPLAZO)
    c.execute("SELECT count(*) FROM personal")
    data_p = c.fetchone()
    # Solo insertamos a Juan Perez si la tabla está TOTALMENTE VACÍA (0 registros) o devuelve error (None)
    if data_p is None or data_p[0] == 0:
        c.execute("INSERT INTO personal VALUES (?,?,?,?,?,?,?,?)", ("12.345.678-9", "JUAN PEREZ", "OPERADOR DE MAQUINARIA", "FAENA", date.today(), "ACTIVO", None, "juan@empresa.cl"))

    # Verificación segura de Matriz
    c.execute("SELECT count(*) FROM matriz_iper")
    data_m = c.fetchone()
    if data_m is None or data_m[0] == 0:
        c.execute("INSERT INTO matriz_iper (proceso, tipo_proceso, puesto_trabajo, tarea, es_rutinaria, peligro_factor, riesgo_asociado, tipo_riesgo, probabilidad, consecuencia, vep, nivel_riesgo, medida_control, genero_obs) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 ("Cosecha", "Operativo", "Operador", "Tala", "SI", "Pendiente", "Volcamiento", "Seguridad", 2, 4, 8, "IMPORTANTE", "Cabina ROPS", "Sin Obs"))

    conn.commit()
    conn.close()

def registrar_auditoria(usuario, accion, detalle):
    try: conn = get_conn(); conn.execute("INSERT INTO auditoria (fecha, usuario, accion, detalle) VALUES (?,?,?,?)", (datetime.now(), usuario, accion, detalle)); conn.commit(); conn.close()
    except: pass

def calcular_nivel_riesgo(vep):
    if vep <= 2: return "TOLERABLE"
    elif vep == 4: return "MODERADO"
    elif vep == 8: return "IMPORTANTE"
    elif vep >= 16: return "INTOLERABLE"
    return "NO CLASIFICADO"

def get_alertas():
    conn = get_conn(); alertas = []; hoy = date.today()
    trabs = pd.read_sql("SELECT rut, nombre FROM personal WHERE estado='ACTIVO'", conn)
    for i, t in trabs.iterrows():
        falta = []
        if pd.read_sql("SELECT count(*) FROM asistencia_capacitacion WHERE trabajador_rut=?", conn, params=(t['rut'],)).iloc[0,0] == 0: falta.append("IRL")
        if pd.read_sql("SELECT count(*) FROM registro_riohs WHERE rut_trabajador=?", conn, params=(t['rut'],)).iloc[0,0] == 0: falta.append("RIOHS")
        if falta: alertas.append(f"⚠️ {t['nombre']}: Falta {', '.join(falta)}")
    
    stock = pd.read_sql("SELECT producto FROM inventario_epp WHERE stock_actual <= stock_minimo", conn)
    for i, s in stock.iterrows(): alertas.append(f"📦 Stock Bajo: {s['producto']}")
    conn.close(); return alertas

def get_incidentes_mes():
    conn = get_conn()
    try:
        mes = datetime.now().strftime('%m'); anio = datetime.now().strftime('%Y')
        res = pd.read_sql(f"SELECT count(*) FROM incidentes WHERE strftime('%m', fecha)='{mes}' AND strftime('%Y', fecha)='{anio}'", conn).iloc[0,0]
    except: res = 0
    conn.close(); return res

# ==============================================================================
# 3. MOTOR DOCUMENTAL (ESTÁNDAR UNIFICADO)
# ==============================================================================
class DocumentosLegalesPDF:
    def __init__(self, titulo_doc, codigo_doc):
        self.buffer = io.BytesIO(); self.doc = SimpleDocTemplate(self.buffer, pagesize=letter, topMargin=40); self.elements = []
        self.styles = getSampleStyleSheet(); self.titulo = titulo_doc; self.codigo = codigo_doc; self.logo_path = "logo_empresa.png"

    def _header(self):
        logo = Paragraph("<b>LOGO</b>", self.styles['Normal'])
        if os.path.exists(self.logo_path):
            try: logo = RLImage(self.logo_path, width=80, height=35)
            except: pass
        data = [[logo, Paragraph(f"SISTEMA DE GESTIÓN SST - DS44<br/><b>{self.titulo}</b>", ParagraphStyle('T', alignment=TA_CENTER, fontSize=11, fontName='Helvetica-Bold')), Paragraph(f"CÓDIGO: {self.codigo}<br/>VER: 08<br/>FECHA: {datetime.now().strftime('%d/%m/%Y')}", ParagraphStyle('C', alignment=TA_CENTER, fontSize=7))]]
        t = Table(data, colWidths=[90, 340, 90]); t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
        self.elements.append(t); self.elements.append(Spacer(1, 20))

    def _signature_block(self, firma_b64, label="FIRMA TRABAJADOR"):
        sig_img = Paragraph("", self.styles['Normal'])
        if firma_b64:
            try: sig_img = RLImage(io.BytesIO(base64.b64decode(firma_b64)), width=120, height=50)
            except: pass
        data = [[sig_img, "HUELLA\nDACTILAR"], [label, ""]]; t = Table(data, colWidths=[200, 60], rowHeights=[60, 20])
        t.setStyle(TableStyle([('ALIGN', (0,0), (0,0), 'CENTER'), ('VALIGN', (0,0), (0,0), 'BOTTOM'), ('LINEABOVE', (0,1), (0,1), 1, colors.black), ('GRID', (1,0), (1,1), 0.5, colors.grey), ('VALIGN', (1,0), (1,0), 'MIDDLE'), ('ALIGN', (1,0), (1,0), 'CENTER'), ('FONTSIZE', (1,0), (1,0), 6)]))
        main = Table([[t]], colWidths=[500]); main.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')])); self.elements.append(Spacer(1, 20)); self.elements.append(main)

    def generar_epp(self, data):
        self._header(); self.elements.append(Paragraph("I. ANTECEDENTES", self.styles['Heading3']))
        t_info = Table([[f"NOMBRE: {data['nombre']}", f"RUT: {data['rut']}"], [f"CARGO: {data['cargo']}", f"FECHA: {data['fecha']}"]], colWidths=[260, 260]); t_info.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke)]))
        self.elements.append(t_info); self.elements.append(Spacer(1, 15))
        try: items = ast.literal_eval(data['lista'])
        except: items = []
        t_data = [["CANT", "ELEMENTO", "MOTIVO"]]; 
        for i in items: t_data.append([str(i.get('cant','1')), i.get('prod','EPP'), i.get('mot','-')])
        t_prod = Table(t_data, colWidths=[40, 280, 200]); t_prod.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 0.5, colors.black)]))
        self.elements.append(t_prod); self.elements.append(Spacer(1, 25)); self.elements.append(Paragraph("Declaro recibir conforme (DS594).", self.styles['Normal'])); self.elements.append(Spacer(1, 30))
        self._signature_block(data['firma_b64']); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_riohs(self, data):
        self._header(); self.elements.append(Paragraph(f"ENTREGA RIOHS: {data['nombre']}", self.styles['Heading3']))
        self.elements.append(Spacer(1, 20)); self.elements.append(Paragraph("Certifico recepción RIOHS (Art 156 CT).", self.styles['Normal']))
        self.elements.append(Spacer(1, 40)); self._signature_block(data['firma_b64']); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_irl(self, data, riesgos):
        self._header(); self.elements.append(Paragraph(f"IRL: {data['nombre']}", self.styles['Heading3']))
        r_data = [["PELIGRO", "RIESGO", "MEDIDA"]]; 
        for r in riesgos: r_data.append([Paragraph(r[0], ParagraphStyle('s', fontSize=8)), Paragraph(r[1], ParagraphStyle('s', fontSize=8)), Paragraph(r[2], ParagraphStyle('s', fontSize=8))])
        t = Table(r_data, colWidths=[130, 130, 250]); t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white)]))
        self.elements.append(t); self.elements.append(Spacer(1, 30)); self.elements.append(Paragraph("Recibí información (DS44).", self.styles['Normal'])); self.elements.append(Spacer(1, 30)); self._signature_block(None); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_asistencia_capacitacion(self, data, asis):
        self._header(); self.elements.append(Paragraph("I. ANTECEDENTES", self.styles['Heading3']))
        tc = Table([[f"TEMA: {data['tema']}", f"TIPO: {data['tipo']}"], [f"RELATOR: {data['resp']}", f"FECHA: {data['fecha']}"]], colWidths=[260, 260]); tc.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black)]))
        self.elements.append(tc); self.elements.append(Spacer(1, 15)); self.elements.append(Paragraph("II. ASISTENCIA", self.styles['Heading3']))
        a_data = [["NOMBRE", "RUT", "FIRMA"]]; row_h = [20]
        for a in asis: 
            f_img = ""
            if a.get('firma_b64'):
                try: f_img = RLImage(io.BytesIO(base64.b64decode(a['firma_b64'])), width=100, height=30)
                except: pass
            a_data.append([a['nombre'], a['rut'], f_img]); row_h.append(40)
        t = Table(a_data, colWidths=[200, 100, 150], rowHeights=row_h, repeatRows=1)
        t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        self.elements.append(t); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_diat(self, data):
        self._header(); self.elements.append(Paragraph("DIAT", self.styles['Title'])); self.elements.append(Paragraph(f"AFECTADO: {data['nombre']}", self.styles['Heading3']))
        self.elements.append(Spacer(1, 20)); self.elements.append(Paragraph(data['descripcion'], self.styles['Normal'])); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

# ==============================================================================
# 4. FRONTEND
# ==============================================================================
init_db()

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user' not in st.session_state: st.session_state['user'] = "Invitado"

if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.title("🔐 SGSST ERP")
        u = st.text_input("Usuario"); p = st.text_input("Contraseña", type="password")
        if st.button("Ingresar", use_container_width=True):
            if u == "admin" and p == "1234": 
                st.session_state['logged_in'] = True; st.session_state['user'] = u; registrar_auditoria(u, "LOGIN", "Acceso OK"); st.rerun()
            else: st.error("Error")
    st.stop()

with st.sidebar:
    st.title("MADERAS GÁLVEZ")
    st.caption("V128 - FIXED SYNTAX")
    menu = st.radio("MENÚ", ["📊 Dashboard", "🛡️ Matriz IPER (ISP)", "👥 Gestión Personas", "⚖️ Gestor Documental", "🦺 Logística EPP", "🎓 Capacitaciones", "🚨 Incidentes & DIAT", "📅 Plan Anual", "🧯 Extintores", "🏗️ Contratistas"])
    if st.button("Cerrar Sesión"): st.session_state['logged_in'] = False; st.rerun()

# --- 1. DASHBOARD ---
if menu == "📊 Dashboard":
    st.markdown("<div class='main-header'>Cuadro de Mando</div>", unsafe_allow_html=True)
    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.subheader("🔔 Estado de Cumplimiento")
        alertas = get_alertas()
        if alertas:
            with st.container(height=200):
                for a in alertas: st.markdown(f"<div class='alert-box alert-high'>{a}</div>", unsafe_allow_html=True)
        else: st.markdown("<div class='alert-box alert-ok'>✅ Todo al día</div>", unsafe_allow_html=True)
    with col_b:
        inc_count = get_incidentes_mes()
        st.metric("Incidentes", inc_count)
        st.metric("Stock Crítico", f"{len([a for a in alertas if 'Stock' in a])} Items")

# --- 2. MATRIZ IPER (VISUAL ISP) ---
elif menu == "🛡️ Matriz IPER (ISP)":
    st.markdown("<div class='main-header'>Matriz de Riesgos (ISP 2024)</div>", unsafe_allow_html=True)
    tab_ver, tab_carga, tab_crear = st.tabs(["👁️ Ver Matriz", "📂 Carga Masiva", "➕ Crear Riesgo"])
    conn = get_conn()
    with tab_ver:
        # Consulta para Visualización Tipo "Sábana" (Anexo 6)
        query = """SELECT id, proceso as 'PROCESO', puesto_trabajo as 'PUESTO', tarea as 'TAREA', es_rutinaria as 'RUTINARIA', peligro_factor as 'PELIGRO (GEMA)', riesgo_asociado as 'RIESGO', probabilidad as 'P', consecuencia as 'C', vep as 'VEP', nivel_riesgo as 'NIVEL', medida_control as 'MEDIDAS DE CONTROL' FROM matriz_iper"""
        df_matriz = pd.read_sql(query, conn)
        def h_risk(val):
            if val=='INTOLERABLE': return 'background-color: #d32f2f; color: white'
            elif val=='IMPORTANTE': return 'background-color: #e57373'
            elif val=='MODERADO': return 'background-color: #ffb74d'
            return 'background-color: #81c784'
        
        # Edición de P y C Directa en Tabla
        edited_df = st.data_editor(df_matriz, use_container_width=True, 
            column_config={
                "P": st.column_config.NumberColumn("P", min_value=1, max_value=4), 
                "C": st.column_config.NumberColumn("C", min_value=1, max_value=4), 
                "VEP": st.column_config.NumberColumn("VEP", disabled=True), 
                "NIVEL": st.column_config.TextColumn("NIVEL", disabled=True)
            }, hide_index=True, key="matriz_ed")
            
        if st.button("💾 Guardar y Recalcular"):
            c = conn.cursor()
            for i, r in edited_df.iterrows():
                np = int(r['P']); nc = int(r['C']); nvep = np*nc; nniv = calcular_nivel_riesgo(nvep)
                c.execute("UPDATE matriz_iper SET probabilidad=?, consecuencia=?, vep=?, nivel_riesgo=?, medida_control=? WHERE id=?", (np, nc, nvep, nniv, r['MEDIDAS DE CONTROL'], r['id']))
            conn.commit(); st.success("Actualizado"); st.rerun()
        
        # Exportar
        b = io.BytesIO(); 
        with pd.ExcelWriter(b, engine='openpyxl') as w: edited_df.to_excel(w, index=False)
        st.download_button("📥 Excel Matriz", b.getvalue(), "MIPER.xlsx")

    with tab_carga:
        plantilla = {'Proceso':['Cosecha'], 'Puesto':['Operador'], 'Peligro':['Pendiente'], 'Riesgo':['Volcamiento'], 'Probabilidad':[2], 'Consecuencia':[4], 'Medida':['ROPS']}
        b2 = io.BytesIO(); 
        with pd.ExcelWriter(b2, engine='openpyxl') as w: pd.DataFrame(plantilla).to_excel(w, index=False)
        st.download_button("📥 Plantilla Carga", b2.getvalue(), "plantilla_iper.xlsx")
        
        up = st.file_uploader("Subir Excel", type=['xlsx'])
        if up:
            try:
                df = pd.read_excel(up)
                if st.button("Procesar"):
                    c = conn.cursor()
                    for i, r in df.iterrows():
                        p = int(r.get('Probabilidad',1)); co = int(r.get('Consecuencia',1)); v = p*co; n = calcular_nivel_riesgo(v)
                        c.execute("INSERT INTO matriz_iper (proceso, puesto_trabajo, peligro_factor, riesgo_asociado, probabilidad, consecuencia, vep, nivel_riesgo, medida_control) VALUES (?,?,?,?,?,?,?,?,?)", (r.get('Proceso',''), r.get('Puesto',''), r.get('Peligro',''), r.get('Riesgo',''), p, co, v, n, r.get('Medida','')))
                    conn.commit(); st.success("Cargado")
            except: st.error("Error en archivo")

    with tab_crear:
        with st.form("risk"):
            c1, c2 = st.columns(2); pro = c1.text_input("Proceso"); pue = c2.text_input("Puesto")
            c3, c4 = st.columns(2); pel = c3.text_input("Peligro"); rie = c4.text_input("Riesgo")
            c5, c6 = st.columns(2); pr = c5.selectbox("P", [1,2,4]); co = c6.selectbox("C", [1,2,4])
            med = st.text_area("Medida")
            if st.form_submit_button("Guardar"):
                v = pr*co; ni = calcular_nivel_riesgo(v)
                conn.execute("INSERT INTO matriz_iper (proceso, puesto_trabajo, peligro_factor, riesgo_asociado, probabilidad, consecuencia, vep, nivel_riesgo, medida_control) VALUES (?,?,?,?,?,?,?,?,?)", (pro, pue, pel, rie, pr, co, v, ni, med))
                conn.commit(); st.success("Guardado"); st.rerun()
    conn.close()
# --- MÓDULO GESTIÓN PERSONAS PROFESIONAL (CORREGIDO) ---
elif menu == "👥 Gestión Personas":
    st.markdown("<div class='main-header'>Gestión de Capital Humano</div>", unsafe_allow_html=True)
    conn = get_conn()
    
    # 1. KPIs (Indicadores Rápidos)
    try:
        total = pd.read_sql("SELECT count(*) FROM personal", conn).iloc[0,0]
        activos = pd.read_sql("SELECT count(*) FROM personal WHERE estado='ACTIVO'", conn).iloc[0,0]
    except: total=0; activos=0
    
    k1, k2, k3 = st.columns(3)
    k1.metric("Dotación Total", total)
    k2.metric("Personal Activo", activos)
    k3.metric("Bajas / Inactivos", total - activos)
    st.markdown("---")

    tab_list, tab_carga, tab_new, tab_dig = st.tabs(["📋 Nómina Interactiva", "📂 Carga Masiva", "➕ Ingreso Manual", "🗂️ Carpeta Digital"])
    
    # PESTAÑA 1: EDICIÓN PROFESIONAL
    with tab_list:
        st.info("💡 Puedes editar directamente en la tabla. Recuerda guardar los cambios.")
        df_p = pd.read_sql("SELECT rut, nombre, cargo, centro_costo, email, fecha_contrato, estado FROM personal", conn)
        
        # --- CORRECCIÓN DEL ERROR DE TIPO DE FECHA ---
        # Convertimos la columna texto a formato fecha real para que st.data_editor no falle
        df_p['fecha_contrato'] = pd.to_datetime(df_p['fecha_contrato'], errors='coerce')
        # ---------------------------------------------
        
        edited = st.data_editor(
            df_p,
            key="pro_editor",
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "rut": st.column_config.TextColumn("RUT", disabled=True),
                "nombre": st.column_config.TextColumn("Nombre Completo"),
                "cargo": st.column_config.SelectboxColumn("Cargo", options=LISTA_CARGOS, required=True),
                "estado": st.column_config.SelectboxColumn("Estado", options=["ACTIVO", "INACTIVO", "LICENCIA"], required=True),
                "fecha_contrato": st.column_config.DateColumn("Fecha Contrato", format="DD/MM/YYYY"),
                "email": st.column_config.TextColumn("Email")
            }
        )
        
        if st.button("💾 Guardar Cambios en Nómina"):
            c = conn.cursor()
            for i, r in edited.iterrows():
                # Corrección de fecha para evitar error NaT al guardar
                fec = r['fecha_contrato']
                if pd.isna(fec) or str(fec) == 'NaT': fec = date.today()
                
                c.execute("""UPDATE personal SET nombre=?, cargo=?, centro_costo=?, email=?, estado=?, fecha_contrato=? WHERE rut=?""", 
                          (r['nombre'], r['cargo'], r['centro_costo'], r['email'], r['estado'], fec, r['rut']))
            conn.commit()
            st.success("✅ Nómina actualizada correctamente")
            time.sleep(1)
            st.rerun()

    # PESTAÑA 2: CARGA MASIVA CON PLANTILLA
    with tab_carga:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown("##### 1. Descargar Plantilla")
            df_t = pd.DataFrame({'RUT':['11.111.111-1'], 'NOMBRE':['Ejemplo'], 'CARGO':['OPERADOR'], 'EMAIL':['correo@x.cl'], 'FECHA DE CONTRATO':['2024-01-01']})
            b = io.BytesIO()
            with pd.ExcelWriter(b, engine='openpyxl') as w: df_t.to_excel(w, index=False)
            st.download_button("📥 Bajar Excel Ejemplo", b.getvalue(), "plantilla_personal.xlsx")
            
        with c2:
            st.markdown("##### 2. Subir Archivo")
            up = st.file_uploader("Seleccione archivo Excel o CSV", type=['xlsx','csv'])
            if up:
                if st.button("🚀 Procesar Carga"):
                    try:
                        df = pd.read_excel(up) if up.name.endswith('xlsx') else pd.read_csv(up)
                        c = conn.cursor()
                        count = 0
                        for i, r in df.iterrows():
                            # Limpieza y validación de fecha
                            rut = str(r.get('RUT','')).strip()
                            try: fec = pd.to_datetime(r.get('FECHA DE CONTRATO'), errors='coerce').date()
                            except: fec = date.today()
                            if pd.isna(fec): fec = date.today()
                            
                            if len(rut) > 5: # Validación mínima de RUT
                                c.execute("""INSERT OR REPLACE INTO personal (rut, nombre, cargo, email, fecha_contrato, estado) 
                                             VALUES (?,?,?,?,?,?)""", 
                                          (rut, r.get('NOMBRE'), r.get('CARGO'), r.get('EMAIL'), fec, 'ACTIVO'))
                                count += 1
                        conn.commit()
                        st.success(f"✅ Se cargaron/actualizaron {count} trabajadores exitosamente.")
                    except Exception as e:
                        st.error(f"Error en la carga: {e}")

    # PESTAÑA 3: INGRESO MANUAL
    with tab_new:
        st.subheader("Ficha de Nuevo Ingreso")
        with st.form("new_p"):
            c1, c2 = st.columns(2)
            r = c1.text_input("RUT (con puntos y guión)")
            n = c2.text_input("Nombre Completo")
            c3, c4 = st.columns(2)
            ca = c3.selectbox("Cargo", LISTA_CARGOS)
            em = c4.text_input("Email Corporativo")
            fec = st.date_input("Fecha de Contrato")
            
            if st.form_submit_button("Registrar Trabajador"):
                if r and n:
                    try:
                        conn.execute("INSERT INTO personal (rut, nombre, cargo, email, fecha_contrato, estado) VALUES (?,?,?,?,?,?)", (r, n, ca, em, fec, 'ACTIVO'))
                        conn.commit()
                        st.success("Trabajador registrado")
                    except: st.error("Error: El RUT ya existe")
                else: st.warning("Faltan datos obligatorios")

    # PESTAÑA 4: CARPETA DIGITAL
    with tab_dig:
        st.subheader("Visor de Carpeta Digital")
        df_all = pd.read_sql("SELECT rut, nombre FROM personal", conn)
        if not df_all.empty:
            sel = st.selectbox("Buscar Trabajador:", df_all['rut'] + " - " + df_all['nombre'])
            rut_sel = sel.split(" - ")[0]
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Estado Documental:**")
                docs = {
                    "ODI/IRL": pd.read_sql("SELECT count(*) FROM asistencia_capacitacion WHERE trabajador_rut=?", conn, params=(rut_sel,)).iloc[0,0] > 0,
                    "RIOHS": pd.read_sql("SELECT count(*) FROM registro_riohs WHERE rut_trabajador=?", conn, params=(rut_sel,)).iloc[0,0] > 0,
                    "Entrega EPP": pd.read_sql("SELECT count(*) FROM registro_epp WHERE rut_trabajador=?", conn, params=(rut_sel,)).iloc[0,0] > 0
                }
                for doc, ok in docs.items():
                    st.write(f"{'✅' if ok else '❌'} {doc}")
            
            with col_b:
                if QR_AVAILABLE:
                    st.write("**Credencial QR:**")
                    qr = qrcode.make(f"SGSST|{rut_sel}")
                    b_qr = io.BytesIO(); qr.save(b_qr, format='PNG')
                    st.image(b_qr.getvalue(), width=120)
    
    conn.close()

# --- 5. LOGISTICA EPP ---
elif menu == "🦺 Logística EPP":
    st.markdown("<div class='main-header'>EPP</div>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["Entrega", "Inventario"])
    conn = get_conn()
    
    with t2:
        ed = st.data_editor(pd.read_sql("SELECT * FROM inventario_epp", conn), key="inv", num_rows="dynamic")
        if st.button("Actualizar Stock"):
            conn.execute("DELETE FROM inventario_epp") 
            for i,r in ed.iterrows(): conn.execute("INSERT INTO inventario_epp (producto, stock_actual, stock_minimo, ubicacion) VALUES (?,?,?,?)", (r['producto'], r['stock_actual'], r['stock_minimo'], r['ubicacion']))
            conn.commit(); st.success("OK"); st.rerun()
            
    with t1:
        # CORRECCIÓN DE LA LÍNEA DEL SELECTBOX (Syntax Error Fixed)
        df_workers = pd.read_sql("SELECT rut, nombre FROM personal", conn)
        worker_options = df_workers['rut'] + " | " + df_workers['nombre']
        sel = st.selectbox("Trabajador", worker_options)
        
        inv = pd.read_sql("SELECT producto FROM inventario_epp WHERE stock_actual > 0", conn)
        
        if 'cart' not in st.session_state: st.session_state.cart = []
        c1, c2 = st.columns(2); p = c1.selectbox("Prod", inv['producto']); q = c2.number_input("Cant", 1)
        if st.button("Agregar"): st.session_state.cart.append({'prod': p, 'cant': q})
        st.table(st.session_state.cart)
        
        can = st_canvas(stroke_width=2, height=150, key="epp")
        if st.button("Confirmar"):
            if can.image_data is not None:
                img = PILImage.fromarray(can.image_data.astype('uint8'), 'RGBA'); b = io.BytesIO(); img.save(b, format='PNG'); ib64 = base64.b64encode(b.getvalue()).decode()
                rut = sel.split(" | ")[0]; nom = sel.split(" | ")[1]
                conn.execute("INSERT INTO registro_epp (fecha_entrega, rut_trabajador, nombre_trabajador, lista_productos, firma_b64) VALUES (?,?,?,?,?)", (date.today(), rut, nom, str(st.session_state.cart), ib64))
                for i in st.session_state.cart: conn.execute("UPDATE inventario_epp SET stock_actual = stock_actual - ? WHERE producto=?", (i['cant'], i['prod']))
                conn.commit()
                pdf = DocumentosLegalesPDF("EPP", "RG-GD-01").generar_epp({'nombre': nom, 'rut': rut, 'cargo': 'OP', 'fecha': date.today(), 'lista': str(st.session_state.cart), 'firma_b64': ib64})
                st.download_button("PDF", pdf.getvalue(), "EPP.pdf"); st.session_state.cart = []
    conn.close()

# --- 6. CAPACITACIONES (CON QR FIXED) ---
elif menu == "🎓 Capacitaciones":
    st.markdown("<div class='main-header'>Capacitaciones</div>", unsafe_allow_html=True)
    t1, t2, t3 = st.tabs(["Nueva", "QR Firma", "Historial"])
    conn = get_conn()
    with t1:
        with st.form("cap"):
            t = st.text_input("Tema"); tp = st.selectbox("Tipo", ["Inducción", "Charla"]); lug = st.text_input("Lugar"); dur = st.number_input("Horas", 1); rel = st.text_input("Relator")
            asis = st.multiselect("Asistentes", pd.read_sql("SELECT rut, nombre FROM personal", conn)['rut'] + " | " + pd.read_sql("SELECT rut, nombre FROM personal", conn)['nombre'])
            if st.form_submit_button("Guardar"):
                c = conn.cursor(); c.execute("INSERT INTO capacitaciones (fecha, tema, tipo_actividad, responsable_rut, lugar, duracion) VALUES (?,?,?,?,?,?)", (date.today(), t, tp, rel, lug, dur)); cid = c.lastrowid
                for a in asis: c.execute("INSERT INTO asistencia_capacitacion (capacitacion_id, trabajador_rut, nombre_trabajador, estado) VALUES (?,?,?,?)", (cid, a.split(" | ")[0], a.split(" | ")[1], "PENDIENTE"))
                conn.commit(); st.success("OK")
    with t2:
        caps = pd.read_sql("SELECT id, tema FROM capacitaciones ORDER BY id DESC", conn)
        if not caps.empty:
            sel_qr = st.selectbox("Seleccionar:", caps['id'].astype(str) + " - " + caps['tema'])
            cap_id = sel_qr.split(" - ")[0]
            
            # --- FIX QR URL ---
            try:
                # Detectar IP local para facilitar pruebas
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip_local = s.getsockname()[0]
                s.close()
                default_url = f"http://{ip_local}:8501"
            except:
                default_url = "https://tu-app-en-la-nube.streamlit.app"

            st.warning("⚠️ Importante: Si estás en la nube (Streamlit Cloud), borra la dirección de abajo y pega la URL de tu navegador.")
            url_base = st.text_input("URL Base de la App", value=default_url)
            
            link = f"{url_base}/?mobile_sign=true&cap_id={cap_id}"
            if QR_AVAILABLE:
                qr = qrcode.make(link); b = io.BytesIO(); qr.save(b, format='PNG')
                st.image(b.getvalue(), width=250)
            st.write(f"Link directo: {link}")

    with t3:
        caps = pd.read_sql("SELECT * FROM capacitaciones", conn); st.dataframe(caps)
        sel_pdf = st.selectbox("PDF:", caps['id'].astype(str) + " - " + caps['tema'])
        if st.button("Generar Lista"):
            cid = int(sel_pdf.split(" - ")[0])
            c_data = pd.read_sql("SELECT * FROM capacitaciones WHERE id=?", conn, params=(cid,)).iloc[0]
            a_data = pd.read_sql("SELECT * FROM asistencia_capacitacion WHERE capacitacion_id=?", conn, params=(cid,)).to_dict('records')
            pdf = DocumentosLegalesPDF("CAPACITACION", "RG-GD-02").generar_asistencia_capacitacion({'tema':c_data['tema'], 'tipo':c_data['tipo_actividad'], 'resp':c_data['responsable_rut'], 'fecha':c_data['fecha'], 'lugar':c_data['lugar'], 'duracion':c_data['duracion']}, a_data)
            st.download_button("PDF", pdf.getvalue(), "Lista.pdf")
    conn.close()

# --- 7. OTROS ---
elif menu == "🚨 Incidentes & DIAT":
    st.title("Incidentes"); conn = get_conn()
    with st.form("inc"):
        f = st.date_input("Fecha"); d = st.text_area("Descripción"); a = st.text_input("Afectado")
        if st.form_submit_button("Guardar"): conn.execute("INSERT INTO incidentes (fecha, descripcion, nombre_afectado) VALUES (?,?,?)", (f, d, a)); conn.commit(); st.success("OK")
    if st.button("Generar DIAT"):
        pdf = DocumentosLegalesPDF("DIAT", "LEGAL").generar_diat({'nombre': 'Ejemplo', 'rut': '1-9', 'fecha': str(date.today()), 'tipo': 'Accidente', 'descripcion': 'Detalle...'})
        st.download_button("DIAT", pdf.getvalue(), "DIAT.pdf")
    conn.close()
elif menu == "📅 Plan Anual":
    st.title("Plan Anual"); conn = get_conn(); st.data_editor(pd.read_sql("SELECT * FROM programa_anual", conn), key="plan", num_rows="dynamic"); conn.close()
elif menu == "🧯 Extintores":
    st.title("Extintores"); conn = get_conn(); st.data_editor(pd.read_sql("SELECT * FROM extintores", conn), key="ext", num_rows="dynamic"); conn.close()
elif menu == "🏗️ Contratistas":
    st.title("Contratistas"); conn = get_conn(); st.data_editor(pd.read_sql("SELECT * FROM contratistas", conn), key="con", num_rows="dynamic"); conn.close()
