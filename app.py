import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import io
import hashlib
import os
import base64
from PIL import Image as PILImage
import matplotlib
import matplotlib.pyplot as plt
import plotly.express as px
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from streamlit_drawable_canvas import st_canvas

# Configuración Matplotlib
matplotlib.use('Agg')

# ==============================================================================
# 1. CONFIGURACIÓN DEL SISTEMA
# ==============================================================================
st.set_page_config(page_title="SGSST DOCUMENT EXPERT", layout="wide", page_icon="🗂️")

DB_NAME = 'sgsst_v109_docs.db'
COLOR_PRIMARY = "#8B0000"
COLOR_SECONDARY = "#2C3E50"
MESES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']

# Estilos CSS
st.markdown("""
    <style>
    .main-header {font-size: 2.0rem; font-weight: 700; color: #2C3E50; border-bottom: 2px solid #8B0000; margin-bottom: 15px;}
    .alert-box {padding: 8px 12px; border-radius: 4px; margin-bottom: 6px; font-size: 0.85rem; font-weight: 500;}
    .alert-high {background-color: #ffebee; color: #b71c1c; border-left: 4px solid #d32f2f;}
    </style>
""", unsafe_allow_html=True)

LISTA_CARGOS = ["GERENTE GENERAL", "PREVENCIONISTA DE RIESGOS", "JEFE DE PATIO", "OPERADOR DE MAQUINARIA", "MOTOSIERRISTA", "ESTROBERO", "MECANICO"]

# ==============================================================================
# 2. CAPA DE DATOS (SQL)
# ==============================================================================
def get_conn():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    # Tablas Base y RRHH
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT, rol TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS auditoria (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATETIME, usuario TEXT, accion TEXT, detalle TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS personal (rut TEXT PRIMARY KEY, nombre TEXT, cargo TEXT, centro_costo TEXT, fecha_contrato DATE, estado TEXT, vigencia_examen_medico DATE)''')
    
    # Matriz y Operaciones
    c.execute('''CREATE TABLE IF NOT EXISTS matriz_iper (id INTEGER PRIMARY KEY AUTOINCREMENT, cargo_asociado TEXT, proceso TEXT, peligro TEXT, riesgo TEXT, consecuencia TEXT, medida_control TEXT, metodo_correcto TEXT, criticidad TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS capacitaciones (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tema TEXT, tipo_actividad TEXT, responsable_rut TEXT, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS asistencia_capacitacion (id INTEGER PRIMARY KEY AUTOINCREMENT, capacitacion_id INTEGER, trabajador_rut TEXT, nombre_trabajador TEXT, cargo_trabajador TEXT, estado TEXT)''')
    
    # Registro EPP Mejorado (Incluye Motivo)
    c.execute('''CREATE TABLE IF NOT EXISTS registro_epp (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrega DATE, rut_trabajador TEXT, nombre_trabajador TEXT, cargo TEXT, lista_productos TEXT, motivo_general TEXT, firma_b64 TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS registro_riohs (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrega DATE, rut_trabajador TEXT, nombre_trabajador TEXT, tipo_entrega TEXT, firma_b64 TEXT)''')
    
    # Inventario y Otros
    c.execute('''CREATE TABLE IF NOT EXISTS inventario_epp (id INTEGER PRIMARY KEY AUTOINCREMENT, producto TEXT, stock_actual INTEGER, stock_minimo INTEGER, ubicacion TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS cphs_actas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_reunion DATE, nro_acta INTEGER, tipo_reunion TEXT, acuerdos TEXT, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS incidentes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tipo TEXT, descripcion TEXT, area TEXT, severidad TEXT, rut_afectado TEXT, nombre_afectado TEXT, parte_cuerpo TEXT, estado TEXT)''')

    # Seed
    c.execute("SELECT count(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO usuarios VALUES (?,?,?)", ("admin", hashlib.sha256("1234".encode()).hexdigest(), "ADMINISTRADOR"))
        c.executemany("INSERT INTO inventario_epp (producto, stock_actual, stock_minimo, ubicacion) VALUES (?,?,?,?)", [
            ("Casco Seguridad", 50, 10, "Bodega 1"), ("Lentes Seguridad", 100, 20, "Bodega 1"),
            ("Guantes Cabritilla", 200, 30, "Bodega 2"), ("Zapatos Seguridad", 40, 5, "Bodega 1")
        ])
        datos_matriz = [
            ("OPERADOR DE MAQUINARIA", "Cosecha", "Pendiente Abrupta", "Volcamiento", "Muerte", "Cabina ROPS/FOPS", "No operar >30%", "CRITICO"),
            ("MOTOSIERRISTA", "Tala", "Caída árbol", "Golpe", "Muerte", "Planificación caída", "Distancia seguridad", "CRITICO")
        ]
        c.executemany("INSERT INTO matriz_iper (cargo_asociado, proceso, peligro, riesgo, consecuencia, medida_control, metodo_correcto, criticidad) VALUES (?,?,?,?,?,?,?,?)", datos_matriz)
        c.execute("INSERT INTO personal VALUES (?,?,?,?,?,?,?)", ("12.345.678-9", "JUAN PEREZ", "OPERADOR DE MAQUINARIA", "FAENA", date.today(), "ACTIVO", date(2026, 12, 31)))

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
    # Alerta Stock
    stock = pd.read_sql("SELECT producto, stock_actual, stock_minimo FROM inventario_epp", conn)
    for i, s in stock.iterrows():
        if s['stock_actual'] <= s['stock_minimo']: alertas.append(f"📦 <b>Stock Bajo:</b> {s['producto']} ({s['stock_actual']})")
    conn.close()
    return alertas

# ==============================================================================
# 3. MOTOR DE DOCUMENTOS LEGALES (ESTRUCTURA DE SISTEMA DE GESTIÓN)
# ==============================================================================
class DocumentosLegalesPDF:
    def __init__(self, titulo_doc, codigo_doc):
        self.buffer = io.BytesIO()
        self.doc = SimpleDocTemplate(self.buffer, pagesize=letter, topMargin=40, bottomMargin=40, leftMargin=40, rightMargin=40)
        self.elements = []
        self.styles = getSampleStyleSheet()
        self.titulo = titulo_doc
        self.codigo = codigo_doc
        self.logo_path = "logo_empresa.png"

    def _header(self):
        # Logo
        logo = Paragraph("<b>LOGO</b>", self.styles['Normal'])
        if os.path.exists(self.logo_path):
            try: logo = RLImage(self.logo_path, width=80, height=35)
            except: pass
            
        # Tabla Cabecera Estándar ISO/SGSST
        data = [
            [logo, 
             Paragraph(f"SISTEMA DE GESTIÓN SST<br/><b>{self.titulo}</b>", ParagraphStyle('T', alignment=TA_CENTER, fontSize=11, fontName='Helvetica-Bold')), 
             Paragraph(f"CÓDIGO: {self.codigo}<br/>VERSIÓN: 01<br/>FECHA: {datetime.now().strftime('%d/%m/%Y')}", ParagraphStyle('C', alignment=TA_CENTER, fontSize=7))]
        ]
        
        t = Table(data, colWidths=[90, 340, 90])
        t.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        self.elements.append(t)
        self.elements.append(Spacer(1, 20))

    def _signature_block(self, firma_b64, label="FIRMA TRABAJADOR"):
        # Bloque de firma con espacio para huella
        signature_image = Paragraph("", self.styles['Normal'])
        if firma_b64:
            try:
                img_data = base64.b64decode(firma_b64)
                signature_image = RLImage(io.BytesIO(img_data), width=120, height=50)
            except: pass
            
        # Tabla Firma + Huella
        data = [[signature_image, "HUELLA\nDACTILAR"], [label, ""]]
        t = Table(data, colWidths=[200, 60], rowHeights=[60, 20])
        t.setStyle(TableStyle([
            ('ALIGN', (0,0), (0,0), 'CENTER'),
            ('VALIGN', (0,0), (0,0), 'BOTTOM'),
            ('LINEABOVE', (0,1), (0,1), 1, colors.black),
            ('GRID', (1,0), (1,1), 0.5, colors.grey), # Cuadro para huella
            ('VALIGN', (1,0), (1,0), 'MIDDLE'),
            ('ALIGN', (1,0), (1,0), 'CENTER'),
            ('FONTSIZE', (1,0), (1,0), 6)
        ]))
        
        # Centrar la tabla de firma en la página
        main_table = Table([[t]], colWidths=[500])
        main_table.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
        
        self.elements.append(Spacer(1, 20))
        self.elements.append(main_table)

    def generar_epp(self, data):
        self._header()
        
        # 1. Antecedentes
        self.elements.append(Paragraph("I. ANTECEDENTES DEL TRABAJADOR", ParagraphStyle('H3', fontSize=10, fontName='Helvetica-Bold')))
        info = [
            [f"NOMBRE: {data['nombre']}", f"RUT: {data['rut']}"], 
            [f"CARGO: {data['cargo']}", f"FECHA ENTREGA: {data['fecha']}"]
        ]
        t_info = Table(info, colWidths=[260, 260])
        t_info.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke)]))
        self.elements.append(t_info); self.elements.append(Spacer(1, 15))
        
        # 2. Detalle EPP
        self.elements.append(Paragraph("II. DETALLE DE ELEMENTOS ENTREGADOS", ParagraphStyle('H3', fontSize=10, fontName='Helvetica-Bold')))
        items = eval(data['lista']) # Lista de dicts: [{'prod':..., 'cant':..., 'mot':...}]
        t_data = [["CANT", "ELEMENTO DE PROTECCIÓN", "MOTIVO CAMBIO"]]
        for i in items: 
            t_data.append([str(i['cant']), i['prod'], i['mot']])
        
        t_prod = Table(t_data, colWidths=[40, 280, 200])
        t_prod.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), 
            ('TEXTCOLOR', (0,0), (-1,0), colors.white), 
            ('GRID', (0,0), (-1,-1), 0.5, colors.black), 
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTSIZE', (0,0), (-1,-1), 9)
        ]))
        self.elements.append(t_prod); self.elements.append(Spacer(1, 25))
        
        # 3. Declaración Legal (DS 594)
        self.elements.append(Paragraph("III. DECLARACIÓN DE RECEPCIÓN Y COMPROMISO", ParagraphStyle('H3', fontSize=10, fontName='Helvetica-Bold')))
        legal_text = """Declaro haber recibido en forma gratuita los Elementos de Protección Personal (EPP) detallados en este documento, los cuales se encuentran en buen estado.
        <br/><br/>
        En conformidad al <b>Artículo 53 del D.S. N° 594</b>, me comprometo a utilizarlos permanentemente mientras me encuentre expuesto a riesgos, a cuidarlos y a solicitar su reposición cuando correspondan."""
        self.elements.append(Paragraph(legal_text, ParagraphStyle('J', alignment=TA_JUSTIFY, fontSize=9)))
        self.elements.append(Spacer(1, 30))
        
        self._signature_block(data['firma_b64'])
        self.doc.build(self.elements); self.buffer.seek(0)
        return self.buffer

    def generar_riohs(self, data):
        self._header()
        self.elements.append(Paragraph(f"<b>NOMBRE:</b> {data['nombre']} | <b>RUT:</b> {data['rut']}", self.styles['Normal']))
        self.elements.append(Spacer(1, 20))
        texto = """En cumplimiento a lo dispuesto en el <b>Artículo 156 del Código del Trabajo</b>, Ley 16.744 y Decreto Supremo N° 40, la empresa hace entrega de un ejemplar del:
        <br/><br/>
        <font size=14><b>REGLAMENTO INTERNO DE ORDEN, HIGIENE Y SEGURIDAD (RIOHS)</b></font>
        <br/><br/>
        El trabajador declara recibir el ejemplar, leerlo y cumplir sus disposiciones."""
        self.elements.append(Paragraph(texto, ParagraphStyle('J', alignment=TA_CENTER, leading=16)))
        self.elements.append(Spacer(1, 30))
        self.elements.append(Paragraph(f"<b>FORMATO DE ENTREGA:</b> {data['tipo']}", self.styles['Normal']))
        self.elements.append(Spacer(1, 50))
        self._signature_block(data['firma_b64'])
        self.doc.build(self.elements); self.buffer.seek(0)
        return self.buffer

    def generar_irl(self, data, riesgos):
        self._header()
        info = [["EMPRESA:", "MADERAS GÁLVEZ LTDA", "RUT:", "77.110.060-0"], ["TRABAJADOR:", data['nombre'], "RUT:", data['rut']], ["CARGO:", data['cargo'], "FECHA:", datetime.now().strftime("%d/%m/%Y")]]
        t = Table(info, colWidths=[70, 180, 50, 100])
        t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (1,-1), colors.whitesmoke)]))
        self.elements.append(t); self.elements.append(Spacer(1, 15))
        
        self.elements.append(Paragraph("<b>OBLIGACIÓN DE INFORMAR RIESGOS LABORALES (ART. 21 DS 40 / DS 44):</b>", self.styles['Heading3']))
        self.elements.append(Paragraph("Se informa sobre los peligros y riesgos inherentes a sus labores, así como las medidas preventivas y métodos correctos de trabajo.", self.styles['Normal']))
        self.elements.append(Spacer(1, 10))

        r_data = [["PELIGRO", "RIESGO / CONSECUENCIA", "MEDIDA DE CONTROL"]]
        for r in riesgos: 
            r_data.append([
                Paragraph(f"<b>{r[0]}</b>", ParagraphStyle('s', fontSize=8)), 
                Paragraph(f"R: {r[1]}<br/>C: {r[2]}", ParagraphStyle('s', fontSize=8)), 
                Paragraph(f"{r[3]}<br/><i>Método: {r[4]}</i>", ParagraphStyle('s', fontSize=8))
            ])
        
        rt = Table(r_data, colWidths=[100, 160, 260], repeatRows=1)
        rt.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 0.5, colors.black), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
        self.elements.append(rt); self.elements.append(Spacer(1, 30))
        
        self.elements.append(Paragraph("Declaro haber sido informado de los riesgos laborales.", ParagraphStyle('J', alignment=TA_JUSTIFY, fontSize=9)))
        self.elements.append(Spacer(1, 40))
        self._signature_block(None)
        self.doc.build(self.elements); self.buffer.seek(0)
        return self.buffer

    def generar_asistencia_capacitacion(self, data, asis):
        self._header()
        c = [[f"ACTIVIDAD: {data['tema']}", f"TIPO: {data['tipo']}"], [f"RELATOR: {data['resp']}", f"FECHA: {data['fecha']}"]]
        tc = Table(c, colWidths=[260, 260])
        tc.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke)]))
        self.elements.append(tc); self.elements.append(Spacer(1, 15))
        
        self.elements.append(Paragraph("<b>LISTA DE ASISTENCIA</b>", self.styles['Heading3']))
        a_data = [["NOMBRE", "RUT", "FIRMA"]]
        for a in asis: a_data.append([a['nombre'], a['rut'], "_______"])
        t = Table(a_data, colWidths=[200, 100, 150])
        t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 0.5, colors.black), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
        self.elements.append(Spacer(1,10)); self.elements.append(t); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

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
    st.caption("V109 - DOC MASTER")
    menu = st.radio("MENÚ", ["📊 Dashboard", "⚖️ Gestor Documental", "🦺 Entrega EPP", "🎓 Capacitaciones", "👥 Gestión Personas", "🛡️ Matriz IPER", "📅 Plan Anual", "🧯 Extintores"])
    if st.button("Cerrar Sesión"): st.session_state['logged_in'] = False; st.rerun()

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.markdown("<div class='main-header'>Cuadro de Mando Integral</div>", unsafe_allow_html=True)
    alertas = get_alertas()
    if alertas:
        for a in alertas: st.markdown(f"<div class='alert-box alert-high'>{a}</div>", unsafe_allow_html=True)
    else: st.markdown("<div class='alert-box alert-ok'>✅ Todo al día</div>", unsafe_allow_html=True)
    
    k1, k2, k3 = st.columns(3)
    k1.metric("Accidentabilidad", "2.1%", "-0.2%")
    k2.metric("Siniestralidad", "12.5", "0%")
    k3.metric("Stock Crítico", f"{len(alertas)} Items", "Logística")

# --- GESTOR DOCUMENTAL (NUEVO HUB CENTRAL) ---
elif menu == "⚖️ Gestor Documental":
    st.markdown("<div class='main-header'>Centro de Documentación Legal</div>", unsafe_allow_html=True)
    
    tab_irl, tab_riohs, tab_hist_epp = st.tabs(["📄 Generar IRL (ODI)", "📘 Entrega RIOHS", "📂 Historial EPP"])
    conn = get_conn()
    df_p = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
    
    with tab_irl:
        st.subheader("Obligación de Informar (DS40 / DS44)")
        sel = st.selectbox("Trabajador IRL:", df_p['rut'] + " - " + df_p['nombre'], key="sel_irl")
        if st.button("Generar IRL"):
            rut = sel.split(" - ")[0]; cargo = df_p[df_p['rut']==rut]['cargo'].values[0]
            riesgos = pd.read_sql("SELECT peligro, riesgo, consecuencia, medida_control, metodo_correcto FROM matriz_iper WHERE cargo_asociado=?", conn, params=(cargo,))
            if riesgos.empty: riesgos = pd.read_sql("SELECT peligro, riesgo, consecuencia, medida_control, metodo_correcto FROM matriz_iper LIMIT 3", conn)
            pdf = DocumentosLegalesPDF("INFORMACIÓN RIESGOS LABORALES", "RG-GD-04").generar_irl({'nombre': sel.split(" - ")[1], 'rut': rut, 'cargo': cargo}, riesgos.values.tolist())
            st.download_button("Descargar PDF", pdf, f"IRL_{rut}.pdf", "application/pdf")

    with tab_riohs:
        st.subheader("Reglamento Interno")
        sel_r = st.selectbox("Trabajador RIOHS:", df_p['rut'] + " | " + df_p['nombre'], key="sel_riohs")
        tipo = st.selectbox("Formato", ["Físico", "Digital"])
        canvas = st_canvas(stroke_width=2, height=150, key="riohs_sign")
        if st.button("Registrar Entrega RIOHS"):
            if canvas.image_data is not None:
                img = PILImage.fromarray(canvas.image_data.astype('uint8'), 'RGBA'); b = io.BytesIO(); img.save(b, format='PNG'); ib64 = base64.b64encode(b.getvalue()).decode()
                rut = sel_r.split(" | ")[0]
                conn.execute("INSERT INTO registro_riohs (fecha_entrega, rut_trabajador, nombre_trabajador, tipo_entrega, firma_b64) VALUES (?,?,?,?,?)", (date.today(), rut, sel_r.split(" | ")[1], tipo, ib64))
                conn.commit()
                pdf = DocumentosLegalesPDF("RECEPCIÓN RIOHS", "RG-GD-03").generar_riohs({'nombre': sel_r.split(" | ")[1], 'rut': rut, 'tipo': tipo, 'firma_b64': ib64})
                st.download_button("Descargar Acta", pdf, "RIOHS.pdf")
                st.success("Registrado")

    with tab_hist_epp:
        st.subheader("Historial de Entregas de EPP")
        hist = pd.read_sql("SELECT * FROM registro_epp ORDER BY fecha_entrega DESC", conn)
        st.dataframe(hist[['fecha_entrega', 'nombre_trabajador', 'lista_productos']], use_container_width=True)
    conn.close()

# --- ENTREGA EPP (MEJORADA CON MOTIVO) ---
elif menu == "🦺 Entrega EPP":
    st.markdown("<div class='main-header'>Registro y Entrega de EPP (RG-GD-01)</div>", unsafe_allow_html=True)
    conn = get_conn()
    
    c1, c2 = st.columns([2, 1])
    
    with c1:
        df_p = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
        sel = st.selectbox("Trabajador:", df_p['rut'] + " | " + df_p['nombre'])
        
        # Selección de items desde Inventario
        inv = pd.read_sql("SELECT producto, stock_actual FROM inventario_epp WHERE stock_actual > 0", conn)
        
        if 'cart' not in st.session_state: st.session_state.cart = []
        
        col_p, col_c, col_m = st.columns(3)
        prod = col_p.selectbox("Producto Disponible", inv['producto'])
        cant = col_c.number_input("Cantidad", 1, 5, 1)
        mot = col_m.selectbox("Motivo Entrega", ["Reposición por Deterioro", "Nuevo", "Pérdida", "Recambio Programado"])
        
        if st.button("Agregar al Listado"):
            st.session_state.cart.append({'prod': prod, 'cant': cant, 'mot': mot})
        
        if st.session_state.cart:
            st.table(st.session_state.cart)
            if st.button("Limpiar Lista"): st.session_state.cart = []
            
            st.write("Firma de Recepción:")
            canvas = st_canvas(stroke_width=2, height=150, key="epp_sign")
            
            if st.button("CONFIRMAR ENTREGA"):
                if canvas.image_data is not None:
                    # Guardar y Descontar
                    rut = sel.split(" | ")[0]; nom = sel.split(" | ")[1]
                    cargo = df_p[df_p['rut']==rut]['cargo'].values[0]
                    img = PILImage.fromarray(canvas.image_data.astype('uint8'), 'RGBA'); b = io.BytesIO(); img.save(b, format='PNG'); ib64 = base64.b64encode(b.getvalue()).decode()
                    
                    # Descuento stock
                    c = conn.cursor()
                    for i in st.session_state.cart:
                        c.execute("UPDATE inventario_epp SET stock_actual = stock_actual - ? WHERE producto=?", (i['cant'], i['prod']))
                    
                    # Registro
                    c.execute("INSERT INTO registro_epp (fecha_entrega, rut_trabajador, nombre_trabajador, cargo, lista_productos, firma_b64) VALUES (?,?,?,?,?,?)",
                             (date.today(), rut, nom, cargo, str(st.session_state.cart), ib64))
                    conn.commit()
                    
                    # Generar PDF
                    pdf = DocumentosLegalesPDF("COMPROBANTE DE ENTREGA EPP", "RG-GD-01").generar_epp({
                        'nombre': nom, 'rut': rut, 'cargo': cargo, 'fecha': date.today(), 
                        'lista': str(st.session_state.cart), 'firma_b64': ib64
                    })
                    st.download_button("📥 Descargar Comprobante PDF", pdf, f"EPP_{rut}.pdf", "application/pdf")
                    st.success("Entrega registrada y Stock actualizado.")
                    st.session_state.cart = []
    
    with c2:
        st.subheader("📦 Stock Actual")
        st.dataframe(pd.read_sql("SELECT producto, stock_actual FROM inventario_epp", conn), use_container_width=True)
    conn.close()

# --- MÓDULOS MANTENIDOS ---
elif menu == "👥 Gestión Personas":
    st.title("RRHH"); conn = get_conn(); st.dataframe(pd.read_sql("SELECT * FROM personal", conn)); conn.close()
elif menu == "🛡️ Matriz IPER":
    st.title("Matriz IPER"); conn = get_conn(); st.data_editor(pd.read_sql("SELECT * FROM matriz_iper", conn)); conn.close()
elif menu == "🎓 Capacitaciones":
    st.title("Capacitaciones"); conn = get_conn(); st.dataframe(pd.read_sql("SELECT * FROM capacitaciones", conn)); conn.close()
elif menu == "📅 Plan Anual":
    st.title("Plan SST"); conn = get_conn(); st.dataframe(pd.read_sql("SELECT * FROM programa_anual", conn)); conn.close()
elif menu == "🧯 Extintores":
    st.title("Extintores"); conn = get_conn(); st.dataframe(pd.read_sql("SELECT * FROM extintores", conn)); conn.close()
