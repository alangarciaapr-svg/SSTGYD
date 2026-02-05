"""
SGSST ERP - Archivo de Configuración
Versión: v193 (Mejorado y Refactorizado)
"""
import streamlit as st
import os

# ==============================================================================
# CONFIGURACIÓN DE BASE DE DATOS
# ==============================================================================
DB_NAME = 'sgsst_v193_optimized.db'

# ==============================================================================
# CONFIGURACIÓN VISUAL
# ==============================================================================
COLOR_PRIMARY = "#8B0000"
COLOR_SECONDARY = "#2C3E50"
COLOR_SUCCESS = "#28a745"
COLOR_WARNING = "#ffc107"
COLOR_DANGER = "#dc3545"

# ==============================================================================
# CONFIGURACIÓN DE EMAIL (SEGURA)
# ==============================================================================
def get_email_config():
    """
    Obtiene configuración de email de forma segura.
    Prioridad: st.secrets > variables de entorno > modo demo
    """
    try:
        # Intentar obtener de Streamlit secrets
        EMAIL_EMISOR = st.secrets.get("email", {}).get("user", "")
        EMAIL_PASSWORD = st.secrets.get("email", {}).get("password", "")
        SMTP_SERVER = st.secrets.get("email", {}).get("smtp_server", "smtp.gmail.com")
        SMTP_PORT = st.secrets.get("email", {}).get("smtp_port", 587)
    except:
        # Fallback a variables de entorno
        EMAIL_EMISOR = os.getenv("SMTP_EMAIL", "")
        EMAIL_PASSWORD = os.getenv("SMTP_PASSWORD", "")
        SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    
    # Si no hay configuración, modo demo
    if not EMAIL_EMISOR or not EMAIL_PASSWORD:
        return {
            'enabled': False,
            'demo_mode': True,
            'server': SMTP_SERVER,
            'port': SMTP_PORT,
            'user': 'demo@empresa.com',
            'password': ''
        }
    
    return {
        'enabled': True,
        'demo_mode': False,
        'server': SMTP_SERVER,
        'port': SMTP_PORT,
        'user': EMAIL_EMISOR,
        'password': EMAIL_PASSWORD
    }

# ==============================================================================
# LISTA DE CARGOS
# ==============================================================================
LISTA_CARGOS = [
    "GERENTE GENERAL", 
    "GERENTE DE FINANZAS", 
    "PREVENCIONISTA DE RIESGOS", 
    "JEFE DE PATIO", 
    "OPERADOR DE ASERRADERO", 
    "AYUDANTE DE ASERRADERO", 
    "OPERADOR DE MAQUINARIA", 
    "MOTOSIERRISTA", 
    "ESTROBERO", 
    "AYUDANTE MECANICO", 
    "MECANICO LIDER", 
    "CALIBRADOR", 
    "PAÑOLERO", 
    "ADMINISTRATIVO"
]

# ==============================================================================
# DICCIONARIO DE RIESGOS ISP V3
# ==============================================================================
ISP_RISK_CODES = {
    "Seguridad": [
        "Caídas al mismo nivel (A1)", "Caídas a distinto nivel (A2)", "Caídas de altura (A3)", "Caídas al agua (A4)",
        "Atrapamiento (B1)", "Golpeado por/contra (B2)", "Cortes/Punzonantes (B3)", "Choque contra objetos (B4)",
        "Contacto con personas (C1)", "Contacto con animales/insectos (C2)",
        "Contacto con objetos calientes (E1)", "Contacto con objetos fríos (E2)",
        "Contacto eléctrico Baja Tensión (F1/F3)", "Contacto eléctrico Alta Tensión (F2/F4)",
        "Contacto sustancias cáusticas (G1)", "Otras sustancias químicas (G2)",
        "Proyección de partículas (H2)", "Atropellos (I1)", "Choque/Colisión Vehicular (I2)"
    ],
    "Higiene Ocupacional": [
        "Aerosoles Sólidos (Sílice/Polvos) (O1)", "Aerosoles Líquidos (Nieblas) (O2)", "Gases y Vapores (O3)",
        "Ruido (PREXOR) (P1)", "Vibraciones Cuerpo Entero (P2)", "Vibraciones Mano-Brazo (P3)",
        "Radiaciones Ionizantes (P4)", "Radiaciones No Ionizantes (UV/Solar) (P5)", 
        "Calor (P6)", "Frío (P7)", "Altas Presiones (P8)", "Bajas Presiones (Hipobaria) (P9)",
        "Agentes Biológicos (Fluidos) (Q1)", "Agentes Biológicos (Virus/Bacterias) (Q2)"
    ],
    "Músculo Esqueléticos": [
        "Manejo Manual de Cargas (R1)", "Manejo de Pacientes (R2)", "Trabajo Repetitivo (S1)", 
        "Postura de Pie (T1)", "Postura Sentado (T2)", "En Cuclillas (T3)", "Arrodillado (T4)",
        "Tronco Inclinado/Torsión (T5)", "Cabeza/Cuello Flexión (T6)", "Fuera del Alcance (T7)", "Posturas Estáticas (T8)"
    ],
    "Psicosociales (ISTAS21)": [
        "Carga de Trabajo (D1)", "Exigencias Emocionales (D2)", "Desarrollo Profesional (D3)",
        "Reconocimiento y Claridad (D4)", "Conflicto de Rol (D5)", "Calidad de Liderazgo (D6)",
        "Compañerismo (D7)", "Inseguridad (D8)", "Doble Presencia (D9)", 
        "Confianza y Justicia (D10)", "Vulnerabilidad (D11)", "Violencia y Acoso (D12)"
    ],
    "Desastres y Emergencias": [
        "Incendios (J)", "Explosiones (H1)", 
        "Ambientes Deficiencia Oxígeno (K1)", "Gases Tóxicos Emergencia (K2)",
        "Sismos / Terremotos (Natural)", "Inundaciones / Aluviones (Natural)"
    ]
}

# ==============================================================================
# CONFIGURACIÓN DE PAGINACIÓN
# ==============================================================================
ITEMS_PER_PAGE = 50

# ==============================================================================
# CONFIGURACIÓN DE CACHE
# ==============================================================================
CACHE_TTL = 300  # 5 minutos

# ==============================================================================
# LOGOS Y RECURSOS
# ==============================================================================
LOGO_URL = "https://www.maderasgyd.cl/wp-content/uploads/2024/02/logo-maderas-gd-1.png"
LOGIN_BG_IMAGE = "https://i.imgur.com/aHPH6U6.jpeg"
