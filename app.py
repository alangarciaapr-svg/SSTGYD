import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date, timedelta
import io
import hashlib
import os
import time
import base64
from PIL import Image as PILImage
import matplotlib
import matplotlib.pyplot as plt
import plotly.express as px
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter, legal
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from streamlit_drawable_canvas import st_canvas

# Manejo seguro de librería QR
try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

# Configuración Matplotlib
matplotlib.use('Agg')

# ==============================================================================
# 1. CONFIGURACIÓN DEL SISTEMA
# ==============================================================================
st.set_page_config(page_title="SGSST GLOBAL SUITE", layout="wide", page_icon="🏗️")

DB_NAME = 'sgsst_v108_global.db'
COLOR_PRIMARY = "#8B0000"
COLOR_SECONDARY = "#2C3E50"
MESES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']

# Estilos CSS
st.markdown("""
    <style>
    .main-header {font-size: 2.0rem; font-weight: 700; color: #2C3E50; border-bottom: 2px solid #8B0000; margin-bottom: 15px;}
    .alert-box {padding: 8px 12px; border-radius: 4px; margin-bottom: 6px; font-size: 0.85rem; font-weight: 500; display: flex; align-items: center;}
    .alert-high {background-color: #ffebee; color: #b71c1c; border-left: 4px solid #d32f2f;}
    .alert-med {background-color: #fff3e0; color: #ef6c00; border-left: 4px solid #ff9800;}
    .alert-ok {background-color: #e8f5e9; color: #2e7d32; border-left: 4px solid #388e3c;}
    </style>
""", unsafe_allow_html=True)

# LISTAS MAESTRAS
LISTA_CARGOS = ["GERENTE GENERAL", "PREVENCIONISTA DE RIESGOS", "JEFE DE PATIO", "OPERADOR DE ASERRADERO", "OPERADOR DE MAQUINARIA", "MOTOSIERRISTA", "ESTROBERO", "MECANICO"]

# ==============================================================================
# 2. CAPA DE DATOS (SQL)
# ==============================================================================
def get_conn():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    # --- MÓDULOS BASE (V107) ---
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT, rol TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS auditoria (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATETIME, usuario TEXT, accion TEXT, detalle TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS personal (rut TEXT PRIMARY KEY, nombre TEXT, cargo TEXT, centro_costo TEXT, fecha_contrato DATE, estado TEXT, vigencia_examen_medico DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS matriz_iper (id INTEGER PRIMARY KEY AUTOINCREMENT, cargo_asociado TEXT, proceso TEXT, peligro TEXT, riesgo TEXT, consecuencia TEXT, medida_control TEXT, metodo_correcto TEXT, criticidad TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS capacitaciones (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tema TEXT, tipo_actividad TEXT, responsable_rut TEXT, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS asistencia_capacitacion (id INTEGER PRIMARY KEY AUTOINCREMENT, capacitacion_id INTEGER, trabajador_rut TEXT, nombre_trabajador TEXT, cargo_trabajador TEXT, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS registro_riohs (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrega DATE, rut_trabajador TEXT, nombre_trabajador TEXT, tipo_entrega TEXT, firma_b64 TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS cphs_actas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_reunion DATE, nro_acta INTEGER, tipo_reunion TEXT, acuerdos TEXT, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS extintores (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, tipo TEXT, capacidad TEXT, ubicacion TEXT, fecha_vencimiento DATE, estado_inspeccion TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS programa_anual (id INTEGER PRIMARY KEY AUTOINCREMENT, actividad TEXT, responsable TEXT, fecha_programada DATE, estado TEXT, fecha_ejecucion DATE)''')

    # --- MODIFICACIONES Y NUEVOS MÓDULOS (V108) ---
    
    # 1. Registro EPP (Ahora vinculado a Inventario)
    c.execute('''CREATE TABLE IF NOT EXISTS registro_epp (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrega DATE, rut_trabajador TEXT, nombre_trabajador TEXT, cargo TEXT, lista_productos TEXT, firma_b64 TEXT)''')
    
    # 2. Inventario EPP (Stock)
    c.execute('''CREATE TABLE IF NOT EXISTS inventario_epp (id INTEGER PRIMARY KEY AUTOINCREMENT, producto TEXT, stock_actual INTEGER, stock_minimo INTEGER, ubicacion TEXT)''')
    
    # 3. Protocolos MINSAL
    c.execute('''CREATE TABLE IF NOT EXISTS protocolos_minsal (id INTEGER PRIMARY KEY AUTOINCREMENT, protocolo TEXT, area TEXT, fecha_medicion DATE, resultado TEXT, estado TEXT, vigencia DATE)''')
    
    # 4. Contratistas
    c.execute('''CREATE TABLE IF NOT EXISTS contratistas (id INTEGER PRIMARY KEY AUTOINCREMENT, rut_empresa TEXT, razon_social TEXT, estado_documental TEXT, fecha_vencimiento_f30 DATE)''')
    
    # 5. Incidentes (Mejorado con Parte del Cuerpo)
    c.execute('''CREATE TABLE IF NOT EXISTS incidentes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tipo TEXT, descripcion TEXT, area TEXT, severidad TEXT, rut_afectado TEXT, nombre_afectado TEXT, parte_cuerpo TEXT, estado TEXT)''')

    # Seed Inicial
    c.execute("SELECT count(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO usuarios VALUES (?,?,?)", ("admin", hashlib.sha256("1234".encode()).hexdigest(), "ADMINISTRADOR"))
        
        # Seed Inventario
        c.executemany("INSERT INTO inventario_epp (producto, stock_actual, stock_minimo, ubicacion) VALUES (?,?,?,?)", [
            ("Casco Seguridad", 50, 10, "Bodega 1"),
            ("Lentes Seguridad", 100, 20, "Bodega 1"),
            ("Guantes Cabritilla", 200, 30, "Bodega 2"),
            ("Zapatos Seguridad", 40, 5, "Bodega 1"),
            ("Protector Auditivo", 80, 15, "Bodega 2")
        ])
        
        # Seed Contratistas
        c.execute("INSERT INTO contratistas (rut_empresa, razon_social, estado_documental, fecha_vencimiento_f30) VALUES (?,?,?,?)", ("76.111.222-3", "TRANS-FORESTAL SPA", "AL DIA", date(2026, 6, 30)))

    conn.commit()
    conn.close()

def registrar_auditoria(usuario, accion, detalle):
    try:
        conn = get_conn()
        conn.execute("INSERT INTO auditoria (fecha, usuario, accion, detalle) VALUES (?,?,?,?)", (datetime.now(), usuario, accion, detalle))
        conn.commit(); conn.close()
    except: pass

def get_alertas():
    conn = get_conn()
    alertas = []
    hoy = date.today()
    
    # Alertas Personales
    trabs = pd.read_sql("SELECT rut, nombre FROM personal WHERE estado='ACTIVO'", conn)
    for i, t in trabs.iterrows():
        rut = t['rut']
        falta = []
        irl = pd.read_sql("SELECT count(*) FROM asistencia_capacitacion WHERE trabajador_rut=?", conn, params=(rut,)).iloc[0,0] > 0
        riohs = pd.read_sql("SELECT count(*) FROM registro_riohs WHERE rut_trabajador=?", conn, params=(rut,)).iloc[0,0] > 0
        if not irl: falta.append("IRL")
        if not riohs: falta.append("RIOHS")
        if falta: alertas.append(f"⚠️ <b>{t['nombre']}</b>: Falta {', '.join(falta)}")
    
    # Alertas Stock EPP (NUEVO)
    stock = pd.read_sql("SELECT producto, stock_actual, stock_minimo FROM inventario_epp", conn)
    for i, s in stock.iterrows():
        if s['stock_actual'] <= s['stock_minimo']:
            alertas.append(f"📦 <b>Stock Crítico:</b> {s['producto']} ({s['stock_actual']} unid.)")

    conn.close()
    return alertas

# ==============================================================================
# 3. MOTOR DOCUMENTAL (REPORTLAB) - MANTENIDO
# ==============================================================================
class DocumentosLegalesPDF:
    def __init__(self, titulo_doc, codigo_doc):
        self.buffer = io.BytesIO()
        self.doc = SimpleDocTemplate(self.buffer, pagesize=letter, topMargin=30, bottomMargin=30)
        self.elements = []
        self.styles = getSampleStyleSheet()
        self.titulo = titulo_doc
        self.codigo = codigo_doc
        self.logo_path = "logo_empresa.png"

    def _header(self):
        logo = Paragraph("<b>MADERAS GÁLVEZ</b>", self.styles['Normal'])
        if os.path.exists(self.logo_path):
            try: logo = RLImage(self.logo_path, width=90, height=40)
            except: pass
        data = [[logo, Paragraph(f"SISTEMA DE GESTIÓN SST - DS44<br/><b>{self.titulo}</b>", ParagraphStyle('T', alignment=TA_CENTER, fontSize=12, fontName='Helvetica-Bold')), 
                 Paragraph(f"CÓDIGO: {self.codigo}<br/>VER: 03<br/>FECHA: {datetime.now().strftime('%d/%m/%Y')}", ParagraphStyle('C', alignment=TA_CENTER, fontSize=8))]]
        t = Table(data, colWidths=[100, 320, 100])
        t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
        self.elements.append(t); self.elements.append(Spacer(1, 20))

    def _signature_block(self, firma_b64, label="FIRMA TRABAJADOR"):
        if firma_b64:
            try:
                img_data = base64.b64decode(firma_b64)
                img = RLImage(io.BytesIO(img_data), width=140, height=50)
                self.elements.append(Spacer(1, 10)); self.elements.append(img)
            except: pass
        self.elements.append(Paragraph(f"__________________________<br/>{label}", ParagraphStyle('C', alignment=TA_CENTER)))

    def generar_epp(self, data):
        self._header()
        items = eval(data['lista'])
        t_data = [["CANT", "DESCRIPCIÓN EPP"]]
        for i in items: t_data.append([str(i['cant']), i['prod']])
        t = Table(t_data, colWidths=[60, 460])
        t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 0.5, colors.black)]))
        self.elements.append(Paragraph(f"ENTREGA EPP A: {data['nombre']} - RUT: {data['rut']}", self.styles['Heading3']))
        self.elements.append(Spacer(1,10)); self.elements.append(t); self.elements.append(Spacer(1,30))
        self.elements.append(Paragraph("Declaro recibir conforme (Art 53 DS594).", self.styles['Normal'])); self.elements.append(Spacer(1,30))
        self._signature_block(data['firma_b64']); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_riohs(self, data):
        self._header()
        self.elements.append(Paragraph(f"ENTREGA RIOHS A: {data['nombre']} - RUT: {data['rut']}", self.styles['Heading3']))
        self.elements.append(Spacer(1,20)); self.elements.append(Paragraph("Recibo Reglamento Interno (Art 156 CT).", self.styles['Normal']))
        self.elements.append(Spacer(1,40)); self._signature_block(data['firma_b64']); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_irl(self, data, riesgos):
        self._header()
        self.elements.append(Paragraph(f"IRL - {data['nombre']} ({data['cargo']})", self.styles['Heading3']))
        self.elements.append(Spacer(1,10))
        r_data = [["PELIGRO", "RIESGO", "MEDIDA"]]
        for r in riesgos: r_data.append([Paragraph(r[0], ParagraphStyle('s', fontSize=8)), Paragraph(r[1], ParagraphStyle('s', fontSize=8)), Paragraph(r[3], ParagraphStyle('s', fontSize=8))])
        t = Table(r_data, colWidths=[120, 150, 250])
        t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white)]))
        self.elements.append(t); self.elements.append(Spacer(1,30))
        self.elements.append(Paragraph("Recibí información de riesgos (DS44/DS40).", self.styles['Normal'])); self.elements.append(Spacer(1,30))
        self._signature_block(None); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_asistencia_capacitacion(self, data, asis):
        self._header()
        self.elements.append(Paragraph(f"CAPACITACIÓN: {data['tema']}", self.styles['Heading3']))
        a_data = [["NOMBRE", "RUT", "FIRMA"]]
        for a in asis: a_data.append([a['nombre'], a['rut'], "_______"])
        t = Table(a_data, colWidths=[200, 100, 150])
        t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white)]))
        self.elements.append(Spacer(1,10)); self.elements.append(t); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_diat(self, data):
        self._header()
        self.elements.append(Paragraph("DENUNCIA INDIVIDUAL DE ACCIDENTE DEL TRABAJO (DIAT)", self.styles['Title']))
        self.elements.append(Paragraph(f"AFECTADO: {data['nombre']} RUT: {data['rut']}", self.styles['Normal']))
        self.elements.append(Spacer(1,20)); self.elements.append(Paragraph(data['descripcion'], self.styles['Normal']))
        self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

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
    st.caption("V108 - GLOBAL SUITE")
    menu = st.radio("MENÚ", ["📊 Dashboard", "👥 Gestión Personas", "🛡️ Matriz IPER", "🩺 Protocolos MINSAL", "📦 Logística EPP", "🏗️ Contratistas", "⚖️ Documental", "🚨 Incidentes", "🎓 Capacitaciones", "📅 Plan Anual", "🧯 Extintores"])
    if st.button("Cerrar Sesión"): st.session_state['logged_in'] = False; st.rerun()

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.markdown("<div class='main-header'>Cuadro de Mando Integral</div>", unsafe_allow_html=True)
    
    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.subheader("🔔 Estado de Cumplimiento")
        alertas = get_alertas()
        if alertas:
            with st.container(height=150):
                for a in alertas: st.markdown(f"<div class='alert-box alert-high'>{a}</div>", unsafe_allow_html=True)
        else: st.markdown("<div class='alert-box alert-ok'>✅ Sistema al día.</div>", unsafe_allow_html=True)
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Accidentabilidad", "2.1%", "-0.2%")
        k2.metric("Siniestralidad", "12.5", "0%")
        k3.metric("Stock Crítico", f"{len([a for a in alertas if 'Stock' in a])} Items", "Logística")

    with col_b:
        st.write("**Mapa de Calor (Lesiones)**")
        conn = get_conn()
        df_inc = pd.read_sql("SELECT parte_cuerpo, count(*) as total FROM incidentes GROUP BY parte_cuerpo", conn)
        if not df_inc.empty:
            fig = px.pie(df_inc, values='total', names='parte_cuerpo', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        else: st.info("Sin datos de lesiones.")
        conn.close()

# --- PROTOCOLOS MINSAL (NUEVO) ---
elif menu == "🩺 Protocolos MINSAL":
    st.markdown("<div class='main-header'>Salud Ocupacional (MINSAL)</div>", unsafe_allow_html=True)
    conn = get_conn()
    
    c1, c2 = st.columns(2)
    with c1:
        with st.form("minsal"):
            proto = st.selectbox("Protocolo", ["PREXOR (Ruido)", "TMERT (Musculoesquelético)", "MMC (Cargas)", "UV (Radiación)", "PSICOSOCIAL"])
            area = st.selectbox("Área/GES", ["ASERRADERO", "CANCHA", "OFICINA"])
            fec = st.date_input("Fecha Medición")
            res = st.selectbox("Resultado", ["BAJO", "MEDIO", "ALTO/CRITICO"])
            if st.form_submit_button("Registrar Medición"):
                conn.execute("INSERT INTO protocolos_minsal (protocolo, area, fecha_medicion, resultado, estado) VALUES (?,?,?,?,?)", (proto, area, fec, res, "VIGENTE"))
                conn.commit(); st.success("Registrado"); st.rerun()
    
    with c2:
        df = pd.read_sql("SELECT * FROM protocolos_minsal ORDER BY fecha_medicion DESC", conn)
        st.dataframe(df, use_container_width=True)
    conn.close()

# --- CONTRATISTAS (NUEVO) ---
elif menu == "🏗️ Contratistas":
    st.markdown("<div class='main-header'>Control de Contratistas (Ley 20.123)</div>", unsafe_allow_html=True)
    conn = get_conn()
    
    c1, c2 = st.columns([1, 2])
    with c1:
        with st.form("contra"):
            rut = st.text_input("RUT Empresa")
            raz = st.text_input("Razón Social")
            f30 = st.date_input("Vencimiento F30-1")
            est = st.selectbox("Estado", ["AL DIA", "PENDIENTE", "BLOQUEADO"])
            if st.form_submit_button("Registrar Empresa"):
                conn.execute("INSERT INTO contratistas (rut_empresa, razon_social, estado_documental, fecha_vencimiento_f30) VALUES (?,?,?,?)", (rut, raz, est, f30))
                conn.commit(); st.success("Registrado"); st.rerun()
    
    with c2:
        df = pd.read_sql("SELECT * FROM contratistas", conn)
        # Semáforo Visual
        if not df.empty:
            st.dataframe(df.style.applymap(lambda v: 'background-color: #ffcdd2' if v == 'BLOQUEADO' else ('background-color: #c8e6c9' if v == 'AL DIA' else ''), subset=['estado_documental']), use_container_width=True)
    conn.close()

# --- LOGISTICA EPP (MEJORADO: STOCK) ---
elif menu == "📦 Logística EPP":
    st.markdown("<div class='main-header'>Gestión de EPP e Inventario</div>", unsafe_allow_html=True)
    conn = get_conn()
    
    tab_ent, tab_inv = st.tabs(["Entrega a Trabajador", "Gestión de Stock"])
    
    with tab_inv:
        st.subheader("Inventario Bodega")
        df_inv = pd.read_sql("SELECT * FROM inventario_epp", conn)
        edited_inv = st.data_editor(df_inv, key="editor_inv", use_container_width=True)
        if st.button("Actualizar Inventario"):
            c = conn.cursor()
            c.execute("DELETE FROM inventario_epp")
            for i, r in edited_inv.iterrows():
                c.execute("INSERT INTO inventario_epp (producto, stock_actual, stock_minimo, ubicacion) VALUES (?,?,?,?)", (r['producto'], r['stock_actual'], r['stock_minimo'], r['ubicacion']))
            conn.commit(); st.success("Inventario Actualizado"); st.rerun()

    with tab_ent:
        df_p = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
        sel = st.selectbox("Trabajador:", df_p['rut'] + " | " + df_p['nombre'])
        
        # Selectbox dinámico desde inventario
        items_inv = pd.read_sql("SELECT producto, stock_actual FROM inventario_epp WHERE stock_actual > 0", conn)
        
        if not items_inv.empty:
            if 'epp_c' not in st.session_state: st.session_state.epp_c = []
            
            c1, c2 = st.columns(2)
            prod = c1.selectbox("Producto Disponible", items_inv['producto'] + " (Stock: " + items_inv['stock_actual'].astype(str) + ")")
            cant = c2.number_input("Cantidad", 1, 5, 1)
            
            if st.button("Agregar a Entrega"):
                p_name = prod.split(" (")[0]
                st.session_state.epp_c.append({'prod': p_name, 'cant': cant})
            
            if st.session_state.epp_c:
                st.write("Resumen Entrega:", st.session_state.epp_c)
                canvas = st_canvas(stroke_width=2, height=150, key="epp_s")
                if st.button("Confirmar Entrega y Descontar Stock"):
                    if canvas.image_data is not None:
                        # 1. Descontar Stock
                        c = conn.cursor()
                        for item in st.session_state.epp_c:
                            c.execute("UPDATE inventario_epp SET stock_actual = stock_actual - ? WHERE producto = ?", (item['cant'], item['prod']))
                        
                        # 2. Registrar
                        rut = sel.split(" | ")[0]; nom = sel.split(" | ")[1]
                        cargo = df_p[df_p['rut']==rut]['cargo'].values[0]
                        img = PILImage.fromarray(canvas.image_data.astype('uint8'), 'RGBA'); b = io.BytesIO(); img.save(b, format='PNG'); img_str = base64.b64encode(b.getvalue()).decode()
                        c.execute("INSERT INTO registro_epp (fecha_entrega, rut_trabajador, nombre_trabajador, cargo, lista_productos, firma_b64) VALUES (?,?,?,?,?,?)", (date.today(), rut, nom, cargo, str(st.session_state.epp_c), img_str))
                        conn.commit()
                        
                        # 3. PDF
                        pdf = DocumentosLegalesPDF("COMPROBANTE EPP", "RG-GD-01").generar_epp({'nombre': nom, 'rut': rut, 'cargo': cargo, 'fecha': date.today(), 'lista': str(st.session_state.epp_c), 'firma_b64': img_str})
                        st.download_button("Descargar PDF", pdf, "EPP.pdf")
                        st.session_state.epp_c = []
                        st.success("Entrega Procesada y Stock Actualizado")
        else:
            st.error("No hay stock disponible en inventario. Vaya a la pestaña 'Gestión de Stock' para reponer.")
            
    conn.close()

# --- INCIDENTES (MEJORADO: MAPA CALOR) ---
elif menu == "🚨 Incidentes":
    st.markdown("<div class='main-header'>Gestión de Accidentes</div>", unsafe_allow_html=True)
    conn = get_conn()
    
    with st.form("inc"):
        st.subheader("Reporte Inmediato")
        fec = st.date_input("Fecha"); tipo = st.selectbox("Tipo", ["Accidente CTP", "Trayecto", "Incidente"])
        afectado = st.selectbox("Afectado", pd.read_sql("SELECT rut, nombre FROM personal", conn)['rut'].astype(str) + " | " + pd.read_sql("SELECT nombre FROM personal", conn)['nombre'])
        parte = st.selectbox("Parte del Cuerpo Afectada", ["MANO DERECHA", "MANO IZQUIERDA", "OJOS", "ESPALDA", "PIERNA", "CABEZA"])
        desc = st.text_area("Relato")
        if st.form_submit_button("Guardar Reporte"):
            conn.execute("INSERT INTO incidentes (fecha, tipo, descripcion, rut_afectado, nombre_afectado, parte_cuerpo, estado) VALUES (?,?,?,?,?,?,?)",
                        (fec, tipo, desc, afectado.split(" | ")[0], afectado.split(" | ")[1], parte, "ABIERTO"))
            conn.commit(); st.success("Registrado")
    
    st.divider()
    st.subheader("Generación DIAT")
    incs = pd.read_sql("SELECT * FROM incidentes ORDER BY id DESC", conn)
    if not incs.empty:
        sel_inc = st.selectbox("Seleccione Incidente:", incs['id'].astype(str) + " - " + incs['nombre_afectado'])
        if st.button("📄 Generar PDF DIAT"):
            i_data = incs[incs['id']==int(sel_inc.split(" - ")[0])].iloc[0]
            pdf = DocumentosLegalesPDF("DENUNCIA INDIVIDUAL", "DIAT").generar_diat({
                'nombre': i_data['nombre_afectado'], 'rut': i_data['rut_afectado'], 
                'fecha': i_data['fecha'], 'tipo': i_data['tipo'], 
                'area': 'FAENA', 'severidad': 'GRAVE', 'descripcion': i_data['descripcion']
            })
            st.download_button("Descargar DIAT", pdf, "DIAT.pdf", "application/pdf")
    conn.close()

# --- MÓDULOS MANTENIDOS (ESTABLES) ---
elif menu == "👥 Gestión Personas":
    st.markdown("<div class='main-header'>Gestión de Personas (RH)</div>", unsafe_allow_html=True)
    tab_list, tab_carga, tab_new, tab_dig = st.tabs(["📋 Nómina", "📂 Carga Masiva", "➕ Nuevo", "🗂️ Carpeta"])
    conn = get_conn()
    with tab_list:
        df_p = pd.read_sql("SELECT rut, nombre, cargo, centro_costo, estado FROM personal", conn)
        edited_df = st.data_editor(df_p, num_rows="dynamic", key="editor_personal", use_container_width=True)
        if st.button("💾 Guardar Cambios"):
            c = conn.cursor()
            for i, r in edited_df.iterrows(): c.execute("UPDATE personal SET nombre=?, cargo=?, centro_costo=?, estado=? WHERE rut=?", (r['nombre'], r['cargo'], r['centro_costo'], r['estado'], r['rut']))
            conn.commit(); st.success("Actualizado.")
    with tab_carga:
        up = st.file_uploader("Excel/CSV", type=['csv','xlsx'])
        if up:
            try:
                df = pd.read_csv(up) if up.name.endswith('.csv') else pd.read_excel(up)
                if st.button("Procesar"):
                    c = conn.cursor()
                    for i, r in df.iterrows():
                        raw_fec = r.get('FECHA DE CONTRATO'); fec = date.today()
                        try: val_dt = pd.to_datetime(raw_fec, errors='coerce'); fec = val_dt.date() if pd.notnull(val_dt) else date.today()
                        except: pass
                        c.execute("INSERT OR REPLACE INTO personal (rut, nombre, cargo, centro_costo, fecha_contrato, estado) VALUES (?,?,?,?,?,?)", (str(r.get('RUT','')), str(r.get('NOMBRE','')), str(r.get('CARGO','')), "FAENA", fec, "ACTIVO"))
                    conn.commit(); st.success("Carga OK")
            except Exception as e: st.error(f"Error: {e}")
    with tab_new:
        with st.form("newp"):
            r = st.text_input("RUT"); n = st.text_input("Nombre"); c = st.selectbox("Cargo", LISTA_CARGOS)
            if st.form_submit_button("Guardar"): conn.execute("INSERT INTO personal VALUES (?,?,?,?,?,?,?)", (r, n, c, "FAENA", date.today(), "ACTIVO", None)); conn.commit(); st.success("OK")
    with tab_dig:
        df_all = pd.read_sql("SELECT rut, nombre FROM personal", conn)
        if not df_all.empty:
            sel = st.selectbox("Trabajador:", df_all['rut'] + " - " + df_all['nombre'])
            if QR_AVAILABLE: st.button("🪪 Credencial")
    conn.close()

elif menu == "🛡️ Matriz IPER":
    st.title("Matriz IPER"); conn = get_conn(); st.data_editor(pd.read_sql("SELECT * FROM matriz_iper", conn), key="iper"); conn.close()

elif menu == "⚖️ Documental":
    st.markdown("<div class='main-header'>Gestor Documental</div>", unsafe_allow_html=True)
    tab_odi, tab_riohs = st.tabs(["IRL (DS44)", "RIOHS"])
    conn = get_conn()
    df = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
    with tab_odi:
        sel = st.selectbox("Trabajador:", df['rut'] + " - " + df['nombre'])
        if st.button("Generar IRL"):
            rut = sel.split(" - ")[0]; cargo = df[df['rut']==rut]['cargo'].values[0]
            riesgos = pd.read_sql("SELECT peligro, riesgo, consecuencia, medida_control, metodo_correcto FROM matriz_iper WHERE cargo_asociado=?", conn, params=(cargo,))
            if riesgos.empty: riesgos = pd.read_sql("SELECT peligro, riesgo, consecuencia, medida_control, metodo_correcto FROM matriz_iper LIMIT 3", conn)
            pdf = DocumentosLegalesPDF("INFORMACIÓN RIESGOS LABORALES", "RG-GD-04").generar_irl({'nombre': sel.split(" - ")[1], 'rut': rut, 'cargo': cargo}, riesgos.values.tolist())
            st.download_button("Descargar PDF", pdf, f"IRL_{rut}.pdf", "application/pdf")
    with tab_riohs:
        sel_r = st.selectbox("Trabajador RIOHS:", df['rut'] + " | " + df['nombre'])
        canvas = st_canvas(stroke_width=2, height=150, key="riohs")
        if st.button("Registrar"):
            if canvas.image_data is not None:
                img = PILImage.fromarray(canvas.image_data.astype('uint8'), 'RGBA'); b = io.BytesIO(); img.save(b, format='PNG'); ib64 = base64.b64encode(b.getvalue()).decode()
                conn.execute("INSERT INTO registro_riohs (fecha_entrega, rut_trabajador, nombre_trabajador, tipo_entrega, firma_b64) VALUES (?,?,?,?,?)", (date.today(), sel_r.split(" | ")[0], sel_r.split(" | ")[1], "Físico", ib64))
                conn.commit(); st.success("OK"); pdf = DocumentosLegalesPDF("RECEPCIÓN RIOHS", "RG-GD-03").generar_riohs({'nombre': sel_r.split(" | ")[1], 'rut': sel_r.split(" | ")[0], 'tipo': 'Físico', 'firma_b64': ib64})
                st.download_button("Descargar", pdf, "RIOHS.pdf")
    conn.close()

elif menu == "🎓 Capacitaciones":
    st.title("Capacitaciones"); conn = get_conn(); 
    with st.form("c"): 
        t = st.text_input("Tema"); a = st.multiselect("Asistentes", pd.read_sql("SELECT rut, nombre FROM personal", conn)['rut'].astype(str) + " - " + pd.read_sql("SELECT nombre FROM personal", conn)['nombre'])
        if st.form_submit_button("Guardar"):
            c = conn.cursor(); c.execute("INSERT INTO capacitaciones (fecha, tema, estado) VALUES (?,?,?)", (date.today(), t, "OK")); cid = c.lastrowid
            for x in a: c.execute("INSERT INTO asistencia_capacitacion (capacitacion_id, trabajador_rut, nombre_trabajador, estado) VALUES (?,?,?,?)", (cid, x.split(" - ")[0], x.split(" - ")[1], "OK"))
            conn.commit(); st.success("Guardado")
    conn.close()

elif menu == "📅 Plan Anual":
    st.title("Plan SST"); conn = get_conn(); st.dataframe(pd.read_sql("SELECT * FROM programa_anual", conn)); conn.close()

elif menu == "🧯 Extintores":
    st.title("Extintores"); conn = get_conn(); st.dataframe(pd.read_sql("SELECT * FROM extintores", conn)); conn.close()
