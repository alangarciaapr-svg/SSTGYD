# --- 8. GESTIÓN DE USUARIOS (V146 - ADMIN PRO) ---
elif menu == "🔐 Gestión Usuarios":
    st.markdown("<div class='main-header'>Administración de Usuarios y Accesos</div>", unsafe_allow_html=True)
    
    conn = get_conn()
    
    # KPIs de Usuarios
    try:
        total_u = pd.read_sql("SELECT count(*) FROM usuarios", conn).iloc[0,0]
        admins = pd.read_sql("SELECT count(*) FROM usuarios WHERE rol='ADMINISTRADOR'", conn).iloc[0,0]
    except: total_u=0; admins=0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Usuarios Totales", total_u)
    c2.metric("Administradores", admins)
    c3.metric("Seguridad", "Activa", delta_color="normal")
    st.divider()

    tab_list, tab_edit, tab_create = st.tabs(["👥 Directorio", "🛠️ Editar / Eliminar", "➕ Nuevo Usuario"])
    
    # 1. LISTADO (Solo lectura elegante)
    with tab_list:
        st.subheader("Directorio de Accesos")
        users_df = pd.read_sql("SELECT username as 'Usuario', rol as 'Rol Asignado' FROM usuarios", conn)
        st.dataframe(users_df, use_container_width=True, hide_index=True)
        
    # 2. EDICIÓN Y GESTIÓN
    with tab_edit:
        st.subheader("Gestión de Cuentas Existentes")
        
        # Seleccionar usuario
        all_users = pd.read_sql("SELECT username FROM usuarios", conn)['username'].tolist()
        user_to_edit = st.selectbox("Seleccione Usuario a gestionar:", all_users)
        
        if user_to_edit:
            st.info(f"Editando a: **{user_to_edit}**")
            
            col_a, col_b = st.columns(2)
            
            # A) CAMBIAR ROL
            with col_a:
                with st.form("edit_role"):
                    st.markdown("##### Cambiar Rol")
                    new_role = st.selectbox("Nuevo Rol", ["ADMINISTRADOR", "VISOR", "PREVENCIONISTA", "GERENCIA"])
                    if st.form_submit_button("Actualizar Rol"):
                        if user_to_edit == "admin" and new_role != "ADMINISTRADOR":
                            st.error("🚫 No puedes quitarle el rol de admin al superusuario principal.")
                        else:
                            conn.execute("UPDATE usuarios SET rol=? WHERE username=?", (new_role, user_to_edit))
                            conn.commit()
                            registrar_auditoria(st.session_state['user'], "UPDATE_USER", f"Cambio rol de {user_to_edit} a {new_role}")
                            st.success("Rol actualizado.")
                            time.sleep(1)
                            st.rerun()

            # B) RESETEAR CLAVE
            with col_b:
                with st.form("reset_pass"):
                    st.markdown("##### Resetear Contraseña")
                    new_p1 = st.text_input("Nueva Contraseña", type="password")
                    new_p2 = st.text_input("Confirmar Contraseña", type="password")
                    if st.form_submit_button("Cambiar Clave"):
                        if new_p1 and new_p1 == new_p2:
                            hashed = hashlib.sha256(new_p1.encode()).hexdigest()
                            conn.execute("UPDATE usuarios SET password=? WHERE username=?", (hashed, user_to_edit))
                            conn.commit()
                            registrar_auditoria(st.session_state['user'], "RESET_PASS", f"Cambio clave de {user_to_edit}")
                            st.success("Contraseña actualizada exitosamente.")
                        else:
                            st.error("Las contraseñas no coinciden o están vacías.")

            st.divider()
            
            # C) ELIMINAR USUARIO (ZONA DE PELIGRO)
            with st.expander("🗑️ Zona de Peligro - Eliminar Usuario"):
                st.warning(f"¿Estás seguro de eliminar a {user_to_edit}? Esta acción no se puede deshacer.")
                if st.button("SÍ, ELIMINAR CUENTA DEFINITIVAMENTE", type="primary"):
                    if user_to_edit == st.session_state['user']:
                        st.error("🚫 No puedes eliminar tu propia cuenta mientras estás logueado.")
                    elif user_to_edit == "admin":
                        st.error("🚫 El usuario 'admin' base no puede ser eliminado.")
                    else:
                        conn.execute("DELETE FROM usuarios WHERE username=?", (user_to_edit,))
                        conn.commit()
                        registrar_auditoria(st.session_state['user'], "DELETE_USER", f"Eliminó al usuario {user_to_edit}")
                        st.success(f"Usuario {user_to_edit} eliminado.")
                        time.sleep(1)
                        st.rerun()

    # 3. CREAR NUEVO
    with tab_create:
        st.subheader("Registrar Nuevo Acceso")
        with st.form("create_user_pro"):
            c1, c2 = st.columns(2)
            new_u = c1.text_input("Nombre de Usuario (Único)")
            new_r = c2.selectbox("Rol de Acceso", ["ADMINISTRADOR", "PREVENCIONISTA", "VISOR", "GERENCIA"])
            
            c3, c4 = st.columns(2)
            pass1 = c3.text_input("Contraseña", type="password")
            pass2 = c4.text_input("Repetir Contraseña", type="password")
            
            if st.form_submit_button("Crear Usuario"):
                if new_u and pass1 and pass2:
                    if pass1 != pass2:
                        st.error("❌ Las contraseñas no coinciden.")
                    else:
                        try:
                            # Verificar si existe
                            exists = pd.read_sql("SELECT username FROM usuarios WHERE username=?", conn, params=(new_u,))
                            if not exists.empty:
                                st.error("❌ El usuario ya existe.")
                            else:
                                h_pw = hashlib.sha256(pass1.encode()).hexdigest()
                                conn.execute("INSERT INTO usuarios (username, password, rol) VALUES (?,?,?)", (new_u, h_pw, new_r))
                                conn.commit()
                                registrar_auditoria(st.session_state['user'], "CREATE_USER", f"Creó usuario {new_u}")
                                st.success(f"✅ Usuario {new_u} creado correctamente.")
                                time.sleep(1)
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error técnico: {e}")
                else:
                    st.warning("⚠️ Complete todos los campos obligatorios.")
    
    conn.close()
