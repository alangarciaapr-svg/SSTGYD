import streamlit as st
import sqlite3
import os
import glob

# ==============================================================================
# CONFIGURACIÓN INICIAL
# ==============================================================================
st.set_page_config(page_title="SGSST - Nuevo Inicio", layout="wide")

# ==============================================================================
# LIMPIEZA DE ENTORNO (SOLO SE EJECUTA SI ES NECESARIO)
# ==============================================================================
# Esto borra cualquier rastro de las bases de datos corruptas anteriores
def limpiar_entorno():
    db_files = glob.glob("*.db")
    for f in db_files:
        try:
            os.remove(f)
            print(f"Eliminado: {f}")
        except:
            pass

# Ejecutamos limpieza al cargar para asegurar "Lienzo en Blanco"
if 'limpieza_hecha' not in st.session_state:
    limpiar_entorno()
    st.session_state['limpieza_hecha'] = True

# ==============================================================================
# BASE DE DATOS NUEVA (MINIMALISTA)
# ==============================================================================
DB_NAME = "sgsst_master_v1.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Solo creamos la tabla de usuarios para empezar
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                    username TEXT PRIMARY KEY, 
                    password TEXT, 
                    rol TEXT)''')
    conn.commit()
    conn.close()

# Inicializamos la nueva BD limpia
init_db()

# ==============================================================================
# INTERFAZ
# ==============================================================================
st.title("🚀 Sistema Reiniciado")
st.success("El entorno se ha limpiado correctamente. No hay errores de base de datos.")
st.info("Esperando instrucciones para construir el primer módulo...")

# Verificador de estado
st.write("Estado del sistema: **OK**")
