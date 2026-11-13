import os
from openpyxl import Workbook, load_workbook
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

USUARIOS_FILE    = os.path.join(DATA_DIR, 'usuarios.xlsx')
INVENTARIO_FILE  = os.path.join(DATA_DIR, 'inventario.xlsx')
SOLICITUDES_FILE = os.path.join(DATA_DIR, 'solicitudes.xlsx')
MOVIMIENTOS_FILE = os.path.join(DATA_DIR, 'movimientos.xlsx')  

# ---------- Utilidad para crear archivos con encabezado ----------
def _ensure_file(path, headers):
    if not os.path.exists(path):
        wb = Workbook()
        ws = wb.active
        ws.append(headers)
        wb.save(path)

def init_data():
    _ensure_file(USUARIOS_FILE,    ['id', 'username', 'password_hash', 'rol'])
    _ensure_file(INVENTARIO_FILE,
                 ['id', 'nombre', 'codigo', 'categoria',
                  'cantidad', 'stock_minimo', 'ubicacion'])      # NUEVAS COLUMNAS
    _ensure_file(SOLICITUDES_FILE, ['id', 'tecnico', 'pieza_codigo', 'cantidad',
                                    'estado', 'fecha', 'observacion'])
    _ensure_file(MOVIMIENTOS_FILE, ['id', 'fecha', 'tipo', 'codigo',
                                    'cantidad', 'usuario', 'motivo'])  # NUEVO

# ---------- USUARIOS ----------
def get_usuarios():
    wb = load_workbook(USUARIOS_FILE)
    ws = wb.active
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    return [dict(id=r[0], username=r[1], password_hash=r[2], rol=r[3]) for r in rows if r[0] is not None]

def get_usuario(username):
    for u in get_usuarios():
        if u['username'] == username:
            return u
    return None

def add_usuario(username, password, rol):
    wb = load_workbook(USUARIOS_FILE)
    ws = wb.active
    next_id = 1
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] is not None:
            next_id = max(next_id, row[0] + 1)
    ws.append([next_id, username, generate_password_hash(password), rol])
    wb.save(USUARIOS_FILE)

def delete_usuario(user_id):
    wb = load_workbook(USUARIOS_FILE)
    ws = wb.active
    for i, row in enumerate(ws.iter_rows(min_row=2), start=2):
        if row[0].value == user_id:
            ws.delete_rows(i)
            break
    wb.save(USUARIOS_FILE)

def verify_usuario(username, password):
    u = get_usuario(username)
    if u and check_password_hash(u['password_hash'], password):
        return u
    return None

# ---------- INVENTARIO ----------
def get_piezas():
    wb = load_workbook(INVENTARIO_FILE)
    ws = wb.active
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    return [dict(id=r[0], nombre=r[1], codigo=r[2], categoria=r[3],
                 cantidad=r[4], stock_minimo=r[5], ubicacion=r[6])
            for r in rows if r[0] is not None]

def get_pieza(pieza_id):
    return next((p for p in get_piezas() if p['id'] == pieza_id), None)

def get_pieza_por_codigo(codigo):
    return next((p for p in get_piezas() if p['codigo'] == codigo), None)

def buscar_piezas(texto):
    """Busca por nombre, código, categoría o ubicación (case-insensitive)."""
    t = (texto or '').lower().strip()
    if not t:
        return get_piezas()
    return [p for p in get_piezas()
            if t in str(p['nombre']).lower()
            or t in str(p['codigo']).lower()
            or t in str(p['categoria']).lower()
            or t in str(p['ubicacion']).lower()]

def add_pieza(nombre, codigo, categoria, cantidad, stock_minimo, ubicacion):
    wb = load_workbook(INVENTARIO_FILE)
    ws = wb.active
    next_id = 1
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] is not None:
            next_id = max(next_id, row[0] + 1)
    ws.append([next_id, nombre, codigo, categoria,
               int(cantidad), int(stock_minimo), ubicacion])
    wb.save(INVENTARIO_FILE)
    # Movimiento de entrada inicial
    registrar_movimiento('ENTRADA', codigo, int(cantidad), 'sistema',
                         f'Carga inicial: {nombre}')

def update_pieza(pieza_id, nombre, codigo, categoria,
                 cantidad, stock_minimo, ubicacion):
    wb = load_workbook(INVENTARIO_FILE)
    ws = wb.active
    for row in ws.iter_rows(min_row=2):
        if row[0].value == pieza_id:
            row[1].value = nombre
            row[2].value = codigo
            row[3].value = categoria
            row[4].value = int(cantidad)
            row[5].value = int(stock_minimo)
            row[6].value = ubicacion
            break
    wb.save(INVENTARIO_FILE)

def delete_pieza(pieza_id):
    wb = load_workbook(INVENTARIO_FILE)
    ws = wb.active
    for i, row in enumerate(ws.iter_rows(min_row=2), start=2):
        if row[0].value == pieza_id:
            ws.delete_rows(i)
            break
    wb.save(INVENTARIO_FILE)

def ajustar_stock(codigo, delta, usuario, motivo):
    """Suma (delta positivo) o resta (delta negativo) stock a una pieza."""
    wb = load_workbook(INVENTARIO_FILE)
    ws = wb.active
    for row in ws.iter_rows(min_row=2):
        if row[2].value == codigo:
            nuevo = max(0, int(row[4].value or 0) + delta)
            row[4].value = nuevo
            wb.save(INVENTARIO_FILE)
            registrar_movimiento('ENTRADA' if delta > 0 else 'SALIDA',
                                 codigo, abs(delta), usuario, motivo)
            return nuevo
    return None

# ---------- SOLICITUDES ----------
def get_solicitudes():
    wb = load_workbook(SOLICITUDES_FILE)
    ws = wb.active
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    return [dict(id=r[0], tecnico=r[1], pieza_codigo=r[2], cantidad=r[3],
                 estado=r[4], fecha=str(r[5]), observacion=r[6])
            for r in rows if r[0] is not None]

def add_solicitud(tecnico, pieza_codigo, cantidad, fecha):
    wb = load_workbook(SOLICITUDES_FILE)
    ws = wb.active
    next_id = 1
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] is not None:
            next_id = max(next_id, row[0] + 1)
    ws.append([next_id, tecnico, pieza_codigo, int(cantidad), 'Pendiente', fecha, ''])
    wb.save(SOLICITUDES_FILE)

def update_estado_solicitud(sol_id, estado, observacion='', usuario='gerente'):
    wb = load_workbook(SOLICITUDES_FILE)
    ws = wb.active
    for row in ws.iter_rows(min_row=2):
        if row[0].value == sol_id:
            row[4].value = estado
            row[6].value = observacion
            break
    wb.save(SOLICITUDES_FILE)
    if estado == 'Aprobada':
        sol = next((s for s in get_solicitudes() if s['id'] == sol_id), None)
        if sol:
            ajustar_stock(sol['pieza_codigo'], -sol['cantidad'],
                          usuario, f'Aprobación solicitud #{sol_id}')
import zipfile

def _ensure_file(path, headers):
    """Crea el archivo si no existe O si está corrupto."""
    valid = False
    if os.path.exists(path):
        try:
            # Un .xlsx válido es un ZIP con contenido
            with zipfile.ZipFile(path, 'r') as z:
                valid = z.testzip() is None
        except (zipfile.BadZipFile, OSError):
            valid = False
    if not valid:
        if os.path.exists(path):
            os.remove(path)  # borra el corrupto
        wb = Workbook()
        ws = wb.active
        ws.append(headers)
        wb.save(path)

def piezas_bajo_stock():
    """Devuelve piezas agotadas o con cantidad <= stock_minimo."""
    return [p for p in get_piezas()
            if p['cantidad'] == 0 or p['cantidad'] <= p['stock_minimo']]

# ---------- MOVIMIENTOS ----------
def registrar_movimiento(tipo, codigo, cantidad, usuario, motivo):
    wb = load_workbook(MOVIMIENTOS_FILE)
    ws = wb.active
    next_id = 1
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] is not None:
            next_id = max(next_id, row[0] + 1)
    fecha = datetime.now().strftime('%Y-%m-%d %H:%M')
    ws.append([next_id, fecha, tipo, codigo, int(cantidad), usuario, motivo])
    wb.save(MOVIMIENTOS_FILE)

def get_movimientos(filtro_codigo=None):
    wb = load_workbook(MOVIMIENTOS_FILE)
    ws = wb.active
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    resultado = [dict(id=r[0], fecha=r[1], tipo=r[2], codigo=r[3],
                      cantidad=r[4], usuario=r[5], motivo=r[6])
                 for r in rows if r[0] is not None]
    if filtro_codigo:
        resultado = [m for m in resultado if m['codigo'] == filtro_codigo]
    return resultado