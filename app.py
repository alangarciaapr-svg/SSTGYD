# --- 2. GESTIÓN NÓMINA (TUS TRABAJADORES REALES) ---
elif menu == "👥 Nómina (Base Excel)":
    st.title("Base de Datos Maestra de Personal")
    st.markdown("Datos cargados desde 'listado de trabajadores.xlsx'.")
    
    conn = sqlite3.connect('sgsst_master.db')
    
    # Subir Excel Nuevo (Lógica corregida para tu archivo específico)
    uploaded_file = st.file_uploader("📂 Actualizar Nómina (Subir Excel Completo)", type=['xlsx', 'csv'])
    if uploaded_file:
        try:
            # Detectar formato y leer
            # Tu archivo tiene los encabezados en la fila 3 (indice 2), por eso header=2
            if uploaded_file.name.endswith('.csv'):
                df_new = pd.read_csv(uploaded_file, header=2)
            else:
                df_new = pd.read_excel(uploaded_file, header=2)
            
            # Normalizar nombres de columnas (quitar espacios y poner mayúsculas)
            df_new.columns = df_new.columns.str.strip().str.upper()
            
            # Verificar si existen las columnas clave de TU archivo
            columnas_necesarias = ['RUT', 'NOMBRE', 'CARGO', 'LUGAR DE TRABAJO']
            if all(col in df_new.columns for col in columnas_necesarias):
                c = conn.cursor()
                count = 0
                for index, row in df_new.iterrows():
                    # Extraer datos limpiando posibles nulos
                    rut = str(row['RUT']).strip()
                    nombre = str(row['NOMBRE']).strip()
                    cargo = str(row['CARGO']).strip()
                    lugar = str(row.get('LUGAR DE TRABAJO', 'FAENA')).strip()
                    
                    # Intentar obtener fecha contrato, si falla poner hoy
                    try:
                        f_contrato = pd.to_datetime(row['F. CONTRATO']).date()
                    except:
                        f_contrato = date.today()

                    # Validar que el RUT tenga largo suficiente para ser real
                    if len(rut) > 5 and nombre != "nan":
                        # Usamos REPLACE para actualizar si el trabajador ya existe
                        c.execute("""INSERT OR REPLACE INTO personal 
                                     (rut, nombre, cargo, centro_costo, fecha_contrato, estado) 
                                     VALUES (?,?,?,?,?,?)""",
                                  (rut, nombre, cargo, lugar, f_contrato, "ACTIVO"))
                        count += 1
                
                conn.commit()
                st.success(f"✅ Éxito: Se han procesado y actualizado {count} trabajadores correctamente.")
                st.rerun() # Recargar para ver los cambios en la tabla
            else:
                st.error(f"El archivo no tiene el formato correcto. Columnas detectadas: {list(df_new.columns)}")
                st.info("Asegúrese que el Excel tenga las columnas: NOMBRE, RUT, CARGO, LUGAR DE TRABAJO")

        except Exception as e:
            st.error(f"Error técnico al leer archivo: {e}")

    # Mostrar Tabla Actualizada
    df = pd.read_sql("SELECT * FROM personal", conn)
    st.dataframe(df, use_container_width=True)
    conn.close()
