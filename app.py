import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
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
st.set_page_config(page_title="SGSST ERP PRO", layout="wide", page_icon="🏗️")

DB_NAME = 'sgsst_v103_rhmaster.db' # Actualización de DB
COLOR_PRIMARY = "#8B0000"
COLOR_SECONDARY = "#2C3E50"
MESES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']

# Estilos CSS
st.markdown("""
    <style>
    .main-header {font-size: 2.2rem; font-weight: 700; color: #2C3E50; border-bottom: 3px solid #8B0000; margin-bottom: 20px;}
    .alert-box {padding: 12px; border-radius: 6px; margin-bottom: 8px; font-weight: 600;}
    .alert-high {background-color: #ffebee; color: #b71c1c; border-left: 5px solid #d32f2f;}
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
    
    # Estructura Base
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT, rol TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS auditoria (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATETIME, usuario TEXT, accion TEXT, detalle TEXT)''')
    
    # RRHH y Matriz
    c.execute('''CREATE TABLE IF NOT EXISTS personal (rut TEXT PRIMARY KEY, nombre TEXT, cargo TEXT, centro_costo TEXT, fecha_contrato DATE, estado TEXT, vigencia_examen_medico DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS matriz_iper (id INTEGER PRIMARY KEY AUTOINCREMENT, cargo_asociado TEXT, proceso TEXT, peligro TEXT, riesgo TEXT, consecuencia TEXT, medida_control TEXT, metodo_correcto TEXT, criticidad TEXT)''')
    
    # Documentos y Operaciones
    c.execute('''CREATE TABLE IF NOT EXISTS capacitaciones (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tema TEXT, tipo_actividad TEXT, responsable_rut TEXT, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS asistencia_capacitacion (id INTEGER PRIMARY KEY AUTOINCREMENT, capacitacion_id INTEGER, trabajador_rut TEXT, nombre_trabajador TEXT, cargo_trabajador TEXT, estado TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS registro_epp (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrega DATE, rut_trabajador TEXT, nombre_trabajador TEXT, cargo TEXT, lista_productos TEXT, firma_b64 TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS registro_riohs (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrega DATE, rut_trabajador TEXT, nombre_trabajador TEXT, tipo_entrega TEXT, firma_b64 TEXT)''')
    
    # Módulos Extra
    c.execute('''CREATE TABLE IF NOT EXISTS cphs_actas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_reunion DATE, nro_acta INTEGER, tipo_reunion TEXT, acuerdos TEXT, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS incidentes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tipo TEXT, descripcion TEXT, area TEXT, severidad TEXT, estado TEXT)''')

    # Seed
    c.execute("SELECT count(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO usuarios VALUES (?,?,?)", ("admin", hashlib.sha256("1234".encode()).hexdigest(), "ADMINISTRADOR"))
        datos_matriz = [
            ("OPERADOR DE MAQUINARIA", "Cosecha", "Pendiente Abrupta", "Volcamiento", "Muerte", "Cabina ROPS/FOPS", "No operar >30%", "CRITICO"),
            ("MOTOSIERRISTA", "Tala", "Caída árbol", "Golpe", "Muerte", "Planificación caída", "Distancia seguridad", "CRITICO"),
            ("JEFE DE PATIO", "Logística", "Tránsito Maquinaria", "Atropello", "Muerte", "Chaleco Reflectante", "Contacto Visual", "ALTO")
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
    trabs = pd.read_sql("SELECT rut, nombre FROM personal WHERE estado='ACTIVO'", conn)
    for i, t in trabs.iterrows():
        count = pd.read_sql("SELECT count(*) FROM asistencia_capacitacion WHERE trabajador_rut=?", conn, params=(t['rut'],)).iloc[0,0]
        if count == 0: alertas.append(f"⚠️ Falta ODI/Inducción para: {t['nombre']}")
    conn.close()
    return alertas

# ==============================================================================
# 3. MOTOR DE DOCUMENTOS LEGALES (REPORTLAB PROFESIONAL)
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
                 Paragraph(f"CÓDIGO: {self.codigo}<br/>VERSIÓN: 01<br/>FECHA: {datetime.now().strftime('%d/%m/%Y')}", ParagraphStyle('C', alignment=TA_CENTER, fontSize=8))]]
        
        t = Table(data, colWidths=[100, 320, 100])
        t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
        self.elements.append(t)
        self.elements.append(Spacer(1, 20))

    def _signature_block(self, firma_b64, label="FIRMA TRABAJADOR"):
        if firma_b64:
            try:
                img_data = base64.b64decode(firma_b64)
                img = RLImage(io.BytesIO(img_data), width=140, height=50)
                self.elements.append(Spacer(1, 10))
                self.elements.append(img)
            except: self.elements.append(Paragraph("[Firma Digital Error]", self.styles['Normal']))
        self.elements.append(Paragraph(f"__________________________<br/>{label}", ParagraphStyle('C', alignment=TA_CENTER)))

    def generar_epp(self, data):
        self._header()
        info = [[f"NOMBRE: {data['nombre']}", f"RUT: {data['rut']}"], [f"CARGO: {data['cargo']}", f"FECHA: {data['fecha']}"]]
        t_info = Table(info, colWidths=[260, 260])
        t_info.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke)]))
        self.elements.append(t_info); self.elements.append(Spacer(1, 15))
        
        items = eval(data['lista'])
        t_data = [["CANT", "DESCRIPCIÓN EPP"]]
        for i in items: t_data.append([str(i.split('(')[1].replace(')','')), i.split('(')[0]])
        
        t_prod = Table(t_data, colWidths=[60, 460])
        t_prod.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 0.5, colors.black), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
        self.elements.append(t_prod); self.elements.append(Spacer(1, 25))
        
        self.elements.append(Paragraph("<b>DECLARACIÓN:</b> Declaro haber recibido los elementos de protección personal detallados, en buen estado y de forma gratuita, comprometiéndome a usarlos correctamente (Art. 53 DS 594).", ParagraphStyle('J', alignment=TA_JUSTIFY)))
        self.elements.append(Spacer(1, 40))
        self._signature_block(data['firma_b64'])
        self.doc.build(self.elements); self.buffer.seek(0)
        return self.buffer

    def generar_riohs(self, data):
        self._header()
        self.elements.append(Paragraph(f"<b>NOMBRE:</b> {data['nombre']} | <b>RUT:</b> {data['rut']}", self.styles['Normal']))
        self.elements.append(Spacer(1, 20))
        texto = """En cumplimiento a lo dispuesto en el Artículo 156 del Código del Trabajo, Ley 16.744 y Decreto Supremo N° 40, la empresa hace entrega de un ejemplar del <b>Reglamento Interno de Orden, Higiene y Seguridad (RIOHS)</b>.<br/><br/>
        El trabajador declara recibir el ejemplar, leerlo y cumplir sus disposiciones, así como participar activamente en los programas de prevención de riesgos."""
        self.elements.append(Paragraph(texto, ParagraphStyle('J', alignment=TA_JUSTIFY, leading=14)))
        self.elements.append(Spacer(1, 30))
        self.elements.append(Paragraph(f"<b>FORMATO DE ENTREGA:</b> {data['tipo']}", self.styles['Normal']))
        self.elements.append(Spacer(1, 50))
        self._signature_block(data['firma_b64'])
        self.doc.build(self.elements); self.buffer.seek(0)
        return self.buffer

    def generar_odi(self, data, riesgos):
        self._header()
        info = [["EMPRESA:", "MADERAS GÁLVEZ LTDA", "RUT:", "77.110.060-0"], ["TRABAJADOR:", data['nombre'], "RUT:", data['rut']], ["CARGO:", data['cargo'], "FECHA:", datetime.now().strftime("%d/%m/%Y")]]
        t = Table(info, colWidths=[70, 180, 50, 100])
        t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (1,-1), colors.whitesmoke)]))
        self.elements.append(t); self.elements.append(Spacer(1, 15))
        
        self.elements.append(Paragraph("<b>RIESGOS INHERENTES (ART 21 DS 40):</b>", self.styles['Heading3']))
        r_data = [["PELIGRO/RIESGO", "CONSECUENCIA", "MEDIDA CONTROL"]]
        for r in riesgos: r_data.append([Paragraph(f"<b>{r[0]}</b><br/>{r[1]}", ParagraphStyle('s', fontSize=8)), Paragraph(r[2], ParagraphStyle('s', fontSize=8)), Paragraph(r[3], ParagraphStyle('s', fontSize=8))])
        
        rt = Table(r_data, colWidths=[140, 120, 260], repeatRows=1)
        rt.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 0.5, colors.black), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
        self.elements.append(rt); self.elements.append(Spacer(1, 30))
        
        self.elements.append(Paragraph("Declaro haber sido informado acerca de los riesgos que entrañan mis labores, de las medidas preventivas y de los métodos de trabajo correctos.", ParagraphStyle('J', alignment=TA_JUSTIFY, fontSize=9)))
        self.elements.append(Spacer(1, 40))
        self._signature_block(None)
        self.doc.build(self.elements); self.buffer.seek(0)
        return self.buffer

    def generar_asistencia_capacitacion(self, data_cap, asistentes):
        self._header()
        c = [[f"ACTIVIDAD: {data_cap['tema']}", f"TIPO: {data_cap['tipo']}"], [f"RELATOR: {data_cap['resp']}", f"FECHA: {data_cap['fecha']}"]]
        tc = Table(c, colWidths=[260, 260])
        tc.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke)]))
        self.elements.append(tc); self.elements.append(Spacer(1, 15))
        
        self.elements.append(Paragraph("<b>LISTA DE ASISTENCIA</b>", self.styles['Heading3']))
        a_data = [["NOMBRE", "RUT", "CARGO", "FIRMA"]]
        for a in asistentes:
            a_data.append([a['nombre'], a['rut'], a['cargo'], "__________________"])
            
        ta = Table(a_data, colWidths=[180, 80, 120, 140], repeatRows=1)
        ta.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 0.5, colors.black), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ROWHEIGHT', (1,-1), 30)]))
        self.elements.append(ta)
        
        self.doc.build(self.elements); self.buffer.seek(0)
        return self.buffer

# ==============================================================================
# 4. FRONTEND (STREAMLIT)
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
    st.caption("ERP V103 - RH Master")
    menu = st.radio("MENÚ", ["📊 Dashboard", "👥 Gestión Personas", "🛡️ Matriz IPER", "🦺 Entrega EPP", "📘 Entrega RIOHS", "⚖️ Generador ODI/IRL", "🎓 Capacitaciones", "🤝 Comité Paritario", "🚨 Incidentes"])
    if st.button("Cerrar Sesión"): st.session_state['logged_in'] = False; st.rerun()

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.markdown("<div class='main-header'>Cuadro de Mando Integral</div>", unsafe_allow_html=True)
    alertas = get_alertas()
    if alertas:
        st.warning(f"⚠️ {len(alertas)} Pendientes")
        for a in alertas: st.markdown(f"<div class='alert-box alert-high'>{a}</div>", unsafe_allow_html=True)
    
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Accidentabilidad", "2.1%", "-0.2%")
    k2.metric("Siniestralidad", "12.5", "0%")
    k3.metric("Cumplimiento Legal", "95%", "+2%")
    k4.metric("Incidentes Mes", "0", "OK")
    
    g1, g2 = st.columns(2)
    with g1:
        st.markdown("### 📉 Tasa Siniestralidad")
        df_g = pd.DataFrame({'Mes': MESES[:6], 'Tasa': [3, 2.5, 2.1, 2.0, 2.2, 2.1]})
        st.plotly_chart(px.area(df_g, x='Mes', y='Tasa', color_discrete_sequence=[COLOR_PRIMARY]), use_container_width=True)
    with g2:
        st.subheader("📋 Auditoría Reciente")
        conn = get_conn()
        audit = pd.read_sql("SELECT usuario, accion, fecha FROM auditoria ORDER BY id DESC LIMIT 5", conn)
        st.dataframe(audit, use_container_width=True)
        conn.close()

# --- GESTIÓN PERSONAS (MEJORADO V103) ---
elif menu == "👥 Gestión Personas":
    st.markdown("<div class='main-header'>Gestión de Personas (RH)</div>", unsafe_allow_html=True)
    
    # NUEVA ESTRUCTURA DE TABS
    tab_list, tab_carga, tab_new, tab_dig = st.tabs(["📋 Nómina & Edición", "📂 Carga Masiva (Excel/CSV)", "➕ Nuevo Manual", "🗂️ Carpeta Digital"])
    
    conn = get_conn()
    
    with tab_list:
        st.info("💡 Edite los datos directamente en la tabla y presione 'Guardar Cambios'")
        df_p = pd.read_sql("SELECT rut, nombre, cargo, centro_costo, estado FROM personal", conn)
        
        # Editor interactivo (Modificaciones manuales rápidas)
        edited_df = st.data_editor(df_p, num_rows="dynamic", key="editor_personal", use_container_width=True)
        
        if st.button("💾 Guardar Cambios Nómina"):
            # Lógica de actualización (UPSERT simplificado borrando y reinsertando por simplicidad en demo)
            # En producción se recomienda UPDATE por RUT
            try:
                c = conn.cursor()
                for index, row in edited_df.iterrows():
                    c.execute("""
                        UPDATE personal SET nombre=?, cargo=?, centro_costo=?, estado=? 
                        WHERE rut=?
                    """, (row['nombre'], row['cargo'], row['centro_costo'], row['estado'], row['rut']))
                conn.commit()
                st.success("Nómina actualizada correctamente.")
                registrar_auditoria(st.session_state['user'], "PERSONAL", "Edición masiva nómina")
            except Exception as e:
                st.error(f"Error al guardar: {e}")

    with tab_carga:
        st.subheader("Importar Trabajadores desde Plantilla")
        st.markdown("Suba su archivo `.csv` o `.xlsx`. Columnas requeridas: **NOMBRE, RUT, CARGO, FECHA DE CONTRATO**")
        
        up_file = st.file_uploader("Cargar Archivo", type=['csv', 'xlsx'])
        
        if up_file:
            try:
                if up_file.name.endswith('.csv'):
                    df_upload = pd.read_csv(up_file)
                else:
                    df_upload = pd.read_excel(up_file)
                
                st.write("Vista Previa:", df_upload.head())
                
                if st.button("🚀 Procesar Carga Masiva"):
                    count = 0
                    c = conn.cursor()
                    for index, row in df_upload.iterrows():
                        # Mapeo de columnas según tu plantilla
                        rut_val = str(row.get('RUT', '')).strip()
                        nom_val = str(row.get('NOMBRE', '')).strip()
                        car_val = str(row.get('CARGO', '')).strip()
                        fec_val = pd.to_datetime(row.get('FECHA DE CONTRATO', date.today())).date()
                        
                        if rut_val and nom_val:
                            # INSERT OR IGNORE para no duplicar si ya existe
                            c.execute("""
                                INSERT OR REPLACE INTO personal 
                                (rut, nombre, cargo, centro_costo, fecha_contrato, estado) 
                                VALUES (?,?,?,?,?,?)
                            """, (rut_val, nom_val, car_val, "FAENA", fec_val, "ACTIVO"))
                            count += 1
                    
                    conn.commit()
                    st.success(f"Proceso completado. {count} trabajadores procesados.")
                    registrar_auditoria(st.session_state['user'], "CARGA_MASIVA", f"{count} registros importados")
            
            except Exception as e:
                st.error(f"Error al procesar archivo: {e}")

    with tab_new:
        with st.form("add_p_manual"):
            c1, c2 = st.columns(2)
            r = c1.text_input("RUT"); n = c2.text_input("Nombre")
            cg = c1.selectbox("Cargo", LISTA_CARGOS); cc = c2.selectbox("Centro Costo", ["FAENA", "ASERRADERO", "OFICINA"])
            if st.form_submit_button("Guardar Trabajador"):
                try:
                    conn.execute("INSERT INTO personal (rut, nombre, cargo, centro_costo, fecha_contrato, estado) VALUES (?,?,?,?,?,?)", (r, n, cg, cc, date.today(), "ACTIVO"))
                    conn.commit(); st.success("Guardado"); st.rerun()
                except: st.error("Error: RUT duplicado")

    with tab_dig:
        df_all = pd.read_sql("SELECT rut, nombre FROM personal", conn)
        if not df_all.empty:
            sel = st.selectbox("Seleccionar Trabajador:", df_all['rut'] + " - " + df_all['nombre'])
            if QR_AVAILABLE:
                if st.button("🪪 Credencial QR"): st.info("Módulo Credencial Activo")
    
    conn.close()

# --- EPP (PDF MEJORADO) ---
elif menu == "🦺 Entrega EPP":
    st.markdown("<div class='main-header'>Registro EPP (RG-GD-01)</div>", unsafe_allow_html=True)
    conn = get_conn()
    df = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
    sel = st.selectbox("Trabajador:", df['rut'] + " | " + df['nombre'])
    
    if 'epp_c' not in st.session_state: st.session_state.epp_c = []
    c1, c2 = st.columns(2)
    p = c1.selectbox("Producto", ["Casco", "Lentes", "Guantes", "Zapatos"]); q = c2.number_input("Cant", 1)
    if st.button("Agregar"): st.session_state.epp_c.append(f"{p} ({q})")
    
    st.table(st.session_state.epp_c)
    canvas = st_canvas(stroke_width=2, height=150, key="epp_s")
    
    if st.button("Guardar y Generar PDF"):
        if canvas.image_data is not None:
            rut = sel.split(" | ")[0]; nom = sel.split(" | ")[1]
            cargo = df[df['rut']==rut]['cargo'].values[0]
            img = PILImage.fromarray(canvas.image_data.astype('uint8'), 'RGBA'); b = io.BytesIO(); img.save(b, format='PNG'); img_str = base64.b64encode(b.getvalue()).decode()
            
            conn.execute("INSERT INTO registro_epp (fecha_entrega, rut_trabajador, nombre_trabajador, cargo, lista_productos, firma_b64) VALUES (?,?,?,?,?,?)",
                        (date.today(), rut, nom, cargo, str(st.session_state.epp_c), img_str))
            conn.commit()
            
            pdf_gen = DocumentosLegalesPDF("COMPROBANTE DE ENTREGA EPP", "RG-GD-01")
            pdf_bytes = pdf_gen.generar_epp({'nombre': nom, 'rut': rut, 'cargo': cargo, 'fecha': date.today(), 'lista': str(st.session_state.epp_c), 'firma_b64': img_str})
            st.download_button("📥 Descargar Comprobante", pdf_bytes, "EPP_Firmado.pdf", "application/pdf")
            st.session_state.epp_c = []
    conn.close()

# --- RIOHS (PDF MEJORADO) ---
elif menu == "📘 Entrega RIOHS":
    st.markdown("<div class='main-header'>Entrega RIOHS (RG-GD-03)</div>", unsafe_allow_html=True)
    conn = get_conn()
    df = pd.read_sql("SELECT rut, nombre FROM personal", conn)
    sel = st.selectbox("Trabajador:", df['rut'] + " | " + df['nombre'])
    tipo = st.selectbox("Formato", ["Físico", "Digital"])
    canvas = st_canvas(stroke_width=2, height=150, key="riohs_s")
    
    if st.button("Registrar y Generar PDF"):
        if canvas.image_data is not None:
            rut = sel.split(" | ")[0]; nom = sel.split(" | ")[1]
            img = PILImage.fromarray(canvas.image_data.astype('uint8'), 'RGBA'); b = io.BytesIO(); img.save(b, format='PNG'); img_str = base64.b64encode(b.getvalue()).decode()
            
            conn.execute("INSERT INTO registro_riohs (fecha_entrega, rut_trabajador, nombre_trabajador, tipo_entrega, firma_b64) VALUES (?,?,?,?,?)",
                        (date.today(), rut, nom, tipo, img_str))
            conn.commit()
            
            pdf_gen = DocumentosLegalesPDF("ACTA DE RECEPCIÓN RIOHS", "RG-GD-03")
            pdf_bytes = pdf_gen.generar_riohs({'nombre': nom, 'rut': rut, 'tipo': tipo, 'firma_b64': img_str})
            st.download_button("📥 Descargar Acta", pdf_bytes, "RIOHS_Firmado.pdf", "application/pdf")
    conn.close()

# --- ODI/IRL (PDF MEJORADO + SQL) ---
elif menu == "⚖️ Generador ODI/IRL":
    st.markdown("<div class='main-header'>Generador ODI (RG-GD-04)</div>", unsafe_allow_html=True)
    conn = get_conn()
    df = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
    sel = st.selectbox("Trabajador:", df['rut'] + " - " + df['nombre'])
    
    if st.button("Generar ODI"):
        rut = sel.split(" - ")[0]; cargo = df[df['rut']==rut]['cargo'].values[0]
        # Buscar riesgos SQL
        riesgos = pd.read_sql("SELECT peligro, riesgo, medida_control FROM matriz_iper WHERE cargo_asociado=?", conn, params=(cargo,))
        if riesgos.empty: riesgos = pd.read_sql("SELECT peligro, riesgo, medida_control FROM matriz_iper LIMIT 3", conn)
        
        pdf_gen = DocumentosLegalesPDF(f"OBLIGACIÓN DE INFORMAR (ODI)", "RG-GD-04")
        pdf_bytes = pdf_gen.generar_odi({'nombre': sel.split(" - ")[1], 'rut': rut, 'cargo': cargo}, riesgos.values.tolist())
        st.download_button("📥 Descargar ODI para Firma", pdf_bytes, f"ODI_{rut}.pdf", "application/pdf")
    conn.close()

# --- CAPACITACIONES (NUEVO PDF ASISTENCIA) ---
elif menu == "🎓 Capacitaciones":
    st.markdown("<div class='main-header'>Registro Capacitaciones (RG-GD-02)</div>", unsafe_allow_html=True)
    conn = get_conn()
    
    tab_new, tab_hist = st.tabs(["Nueva", "Historial & Descargas"])
    
    with tab_new:
        with st.form("cap"):
            tema = st.text_input("Tema")
            tipo = st.selectbox("Tipo", ["Inducción", "Charla 5 Min", "Específica"])
            resp = st.text_input("Relator", "Prevencionista")
            df = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
            asis = st.multiselect("Asistentes", df['rut'] + " | " + df['nombre'])
            
            if st.form_submit_button("Guardar Registro"):
                c = conn.cursor()
                c.execute("INSERT INTO capacitaciones (fecha, tema, tipo_actividad, responsable_rut, estado) VALUES (?,?,?,?,?)", (date.today(), tema, tipo, resp, "EJECUTADA"))
                cid = c.lastrowid
                for a in asis:
                    rut = a.split(" | ")[0]; nom = a.split(" | ")[1]
                    cargo = df[df['rut']==rut]['cargo'].values[0]
                    c.execute("INSERT INTO asistencia_capacitacion (capacitacion_id, trabajador_rut, nombre_trabajador, cargo_trabajador, estado) VALUES (?,?,?,?,?)", (cid, rut, nom, cargo, "ASISTIÓ"))
                conn.commit()
                st.success("Guardado.")
    
    with tab_hist:
        caps = pd.read_sql("SELECT * FROM capacitaciones ORDER BY id DESC", conn)
        if not caps.empty:
            st.dataframe(caps)
            sel_cap = st.selectbox("Seleccionar Capacitación para PDF:", caps['id'].astype(str) + " - " + caps['tema'])
            if st.button("📄 Descargar Lista Asistencia"):
                cid = int(sel_cap.split(" - ")[0])
                data_cap = pd.read_sql("SELECT * FROM capacitaciones WHERE id=?", conn, params=(cid,)).iloc[0]
                asis_list = pd.read_sql("SELECT nombre_trabajador as nombre, trabajador_rut as rut, cargo_trabajador as cargo FROM asistencia_capacitacion WHERE capacitacion_id=?", conn, params=(cid,)).to_dict('records')
                
                pdf_gen = DocumentosLegalesPDF("REGISTRO DE CAPACITACIÓN", "RG-GD-02")
                pdf_bytes = pdf_gen.generar_asistencia_capacitacion({'tema': data_cap['tema'], 'tipo': data_cap['tipo_actividad'], 'resp': data_cap['responsable_rut'], 'fecha': data_cap['fecha']}, asis_list)
                st.download_button("📥 Bajar PDF Asistencia", pdf_bytes, f"Asistencia_{cid}.pdf", "application/pdf")
    conn.close()

# --- OTROS MÓDULOS (COMPLEMENTARIOS) ---
elif menu == "🛡️ Matriz IPER":
    st.title("Matriz IPER"); conn = get_conn(); df = pd.read_sql("SELECT * FROM matriz_iper", conn); st.data_editor(df, key="iper"); conn.close()
elif menu == "🤝 Comité Paritario":
    st.title("CPHS"); st.info("Módulo de Actas (Ver V101)")
elif menu == "🚨 Incidentes":
    st.title("Incidentes"); st.info("Registro DIAT/DIEP (Ver V101)")
