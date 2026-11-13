# ============================================================
# INVENTARIO INDUSTRIAL - Aplicación principal
# ============================================================
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import (
    LoginManager, UserMixin, login_user, login_required,
    logout_user, current_user
)
from functools import wraps
from datetime import datetime

import data_manager as dm


# ------------------------------------------------------------
# Configuración
# ------------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = 'clave_secreta_cambiar_en_produccion'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

dm.init_data()  # Crea los archivos Excel si no existen


# ------------------------------------------------------------
# Clase User para Flask-Login
# ------------------------------------------------------------
class User(UserMixin):
    def __init__(self, data):
        self.id = str(data['id'])
        self.username = data['username']
        self.rol = data['rol']


@login_manager.user_loader
def load_user(user_id):
    for u in dm.get_usuarios():
        if str(u['id']) == user_id:
            return User(u)
    return None


# ------------------------------------------------------------
# Decorador de roles
# ------------------------------------------------------------
def rol_requerido(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated or current_user.rol not in roles:
                flash('No tienes permiso para acceder a esta sección.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ============================================================
# AUTENTICACIÓN
# ============================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        user_data = dm.verify_usuario(request.form['username'],
                                      request.form['password'])
        if user_data:
            login_user(User(user_data))
            return redirect(url_for('dashboard'))
        flash('Usuario o contraseña incorrectos', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ============================================================
# DASHBOARD (todos los roles)
# ============================================================
@app.route('/')
@login_required
def dashboard():
    q = request.args.get('q', '')
    piezas = dm.buscar_piezas(q) if q else dm.get_piezas()
    alertas = dm.piezas_bajo_stock()
    return render_template('dashboard.html',
                           piezas=piezas, q=q, alertas=alertas)


# ============================================================
# ADMINISTRADOR - Gestión de usuarios
# ============================================================
@app.route('/admin/usuarios')
@login_required
@rol_requerido('Administrador')
def admin_usuarios():
    return render_template('admin_usuarios.html', usuarios=dm.get_usuarios())


@app.route('/admin/usuarios/agregar', methods=['POST'])
@login_required
@rol_requerido('Administrador')
def admin_agregar_usuario():
    username = request.form['username'].strip()
    password = request.form['password']
    rol = request.form['rol']

    if not username or not password:
        flash('Usuario y contraseña son obligatorios', 'danger')
    elif rol not in ('Administrador', 'Gerente', 'Técnico'):
        flash('Rol inválido', 'danger')
    elif dm.get_usuario(username):
        flash('Ese usuario ya existe', 'danger')
    else:
        dm.add_usuario(username, password, rol)
        flash(f'Usuario "{username}" creado con rol {rol}', 'success')
    return redirect(url_for('admin_usuarios'))


@app.route('/admin/usuarios/eliminar/<int:uid>')
@login_required
@rol_requerido('Administrador')
def admin_eliminar_usuario(uid):
    if str(uid) == str(current_user.id):
        flash('No puedes eliminar tu propio usuario', 'warning')
        return redirect(url_for('admin_usuarios'))
    dm.delete_usuario(uid)
    flash('Usuario eliminado', 'success')
    return redirect(url_for('admin_usuarios'))


# ============================================================
# ADMINISTRADOR - Gestión de piezas
# ============================================================
@app.route('/admin/piezas')
@login_required
@rol_requerido('Administrador')
def admin_piezas():
    return render_template('admin_piezas.html', piezas=dm.get_piezas())


@app.route('/admin/piezas/agregar', methods=['POST'])
@login_required
@rol_requerido('Administrador')
def admin_agregar_pieza():
    codigo = request.form['codigo'].strip()
    if dm.get_pieza_por_codigo(codigo):
        flash('Ya existe una pieza con ese código', 'danger')
        return redirect(url_for('admin_piezas'))
    dm.add_pieza(
        request.form['nombre'].strip(),
        codigo,
        request.form['categoria'].strip(),
        request.form['cantidad'],
        request.form['stock_minimo'],
        request.form['ubicacion'].strip(),
    )
    flash('Pieza registrada', 'success')
    return redirect(url_for('admin_piezas'))


@app.route('/admin/piezas/editar/<int:pid>', methods=['GET', 'POST'])
@login_required
@rol_requerido('Administrador')
def admin_editar_pieza(pid):
    pieza = dm.get_pieza(pid)
    if not pieza:
        flash('Pieza no encontrada', 'danger')
        return redirect(url_for('admin_piezas'))

    if request.method == 'POST':
        dm.update_pieza(
            pid,
            request.form['nombre'].strip(),
            request.form['codigo'].strip(),
            request.form['categoria'].strip(),
            request.form['cantidad'],
            request.form['stock_minimo'],
            request.form['ubicacion'].strip(),
        )
        flash('Pieza actualizada', 'success')
        return redirect(url_for('admin_piezas'))

    return render_template('admin_piezas.html',
                           piezas=dm.get_piezas(),
                           pieza_editar=pieza)


@app.route('/admin/piezas/eliminar/<int:pid>')
@login_required
@rol_requerido('Administrador')
def admin_eliminar_pieza(pid):
    dm.delete_pieza(pid)
    flash('Pieza eliminada', 'success')
    return redirect(url_for('admin_piezas'))


@app.route('/admin/piezas/<int:pid>/entrada', methods=['POST'])
@login_required
@rol_requerido('Administrador')
def admin_entrada_stock(pid):
    pieza = dm.get_pieza(pid)
    if not pieza:
        flash('Pieza no encontrada', 'danger')
        return redirect(url_for('admin_piezas'))

    try:
        cantidad = int(request.form['cantidad'])
        if cantidad <= 0:
            raise ValueError
    except (ValueError, KeyError):
        flash('Cantidad inválida (debe ser un entero mayor a 0)', 'danger')
        return redirect(url_for('admin_piezas'))

    motivo = request.form.get('motivo', '').strip() or 'Compra / reabastecimiento'
    dm.ajustar_stock(pieza['codigo'], cantidad, current_user.username, motivo)
    flash(f'Entrada registrada: +{cantidad} a {pieza["codigo"]}', 'success')
    return redirect(url_for('admin_piezas'))


# ============================================================
# GERENTE - Solicitudes y reportes
# ============================================================
@app.route('/gerente/solicitudes')
@login_required
@rol_requerido('Gerente')
def gerente_solicitudes():
    return render_template('gerente_solicitudes.html',
                           solicitudes=dm.get_solicitudes())


@app.route('/gerente/solicitudes/<int:sid>/<accion>', methods=['POST'])
@login_required
@rol_requerido('Gerente')
def gerente_resolver(sid, accion):
    obs = request.form.get('observacion', '').strip()

    if accion == 'aprobar':
        dm.update_estado_solicitud(sid, 'Aprobada', obs,
                                   usuario=current_user.username)
        flash('Solicitud aprobada y stock actualizado', 'success')
    elif accion == 'rechazar':
        dm.update_estado_solicitud(sid, 'Rechazada', obs,
                                   usuario=current_user.username)
        flash('Solicitud rechazada', 'warning')
    else:
        flash('Acción no reconocida', 'danger')

    return redirect(url_for('gerente_solicitudes'))


@app.route('/gerente/reportes')
@login_required
@rol_requerido('Gerente')
def gerente_reportes():
    piezas = dm.get_piezas()
    solicitudes = dm.get_solicitudes()
    movs = dm.get_movimientos()
    total_stock = sum(p['cantidad'] for p in piezas)
    por_estado = {
        'Pendiente': sum(1 for s in solicitudes if s['estado'] == 'Pendiente'),
        'Aprobada':  sum(1 for s in solicitudes if s['estado'] == 'Aprobada'),
        'Rechazada': sum(1 for s in solicitudes if s['estado'] == 'Rechazada'),
    }
    return render_template('gerente_reportes.html',
                           piezas=piezas,
                           total_stock=total_stock,
                           por_estado=por_estado,
                           alertas=dm.piezas_bajo_stock(),
                           total_movs=len(movs))


# ============================================================
# TÉCNICO - Solicitudes
# ============================================================
@app.route('/tecnico/solicitar', methods=['GET', 'POST'])
@login_required
@rol_requerido('Técnico')
def tecnico_solicitar():
    if request.method == 'POST':
        codigo = request.form['codigo'].strip()
        try:
            cantidad = int(request.form['cantidad'])
            if cantidad <= 0:
                raise ValueError
        except (ValueError, KeyError):
            flash('Cantidad inválida (debe ser un entero mayor a 0)', 'danger')
            return redirect(url_for('tecnico_solicitar'))

        pieza = dm.get_pieza_por_codigo(codigo)
        if not pieza:
            flash('La pieza no existe en el inventario', 'danger')
        elif pieza['cantidad'] < cantidad:
            flash(f'Stock insuficiente (disponible: {pieza["cantidad"]})', 'danger')
        else:
            fecha = datetime.now().strftime('%Y-%m-%d %H:%M')
            dm.add_solicitud(current_user.username, codigo, cantidad, fecha)
            flash('Solicitud registrada correctamente', 'success')
        return redirect(url_for('tecnico_solicitar'))

    return render_template('tecnico_solicitudes.html',
                           piezas=dm.get_piezas(),
                           solicitudes=[s for s in dm.get_solicitudes()
                                        if s['tecnico'] == current_user.username])


# ============================================================
# MOVIMIENTOS Y ALERTAS (Admin y Gerente; Técnico solo alertas)
# ============================================================
@app.route('/movimientos')
@login_required
@rol_requerido('Administrador', 'Gerente')
def movimientos():
    filtro = request.args.get('codigo', '').strip()
    movs = dm.get_movimientos(filtro_codigo=filtro or None)
    return render_template('movimientos.html',
                           movimientos=movs, filtro=filtro)


@app.route('/alertas')
@login_required
@rol_requerido('Administrador', 'Gerente', 'Técnico')
def alertas():
    return render_template('alertas.html', alertas=dm.piezas_bajo_stock())


# ============================================================
# Punto de entrada
# ============================================================
if __name__ == '__main__':
    app.run(debug=True)