from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import pandas as pd

app = Flask(__name__)
app.secret_key = 'clave_secreta_segura'

# Configuración de la base de datos SQLite
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'rrhh.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

### MODELOS ###
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Empleado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    cargo = db.Column(db.String(100), nullable=False)
    fecha_ingreso = db.Column(db.Date, nullable=False)
    estado = db.Column(db.String(50), default='Activo')

class Candidato(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    puesto = db.Column(db.String(100), nullable=False)
    estado = db.Column(db.String(50), default='Postulado')

### AUTENTICACIÓN ###
@app.before_request
def inicializar():
    db.create_all()
    if not Usuario.query.filter_by(usuario='adm').first():
        admin = Usuario(usuario='adm', email='admin@correo.com',
                        password=generate_password_hash('admin123'))
        db.session.add(admin)
        db.session.commit()

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        password = request.form['password']
        user = Usuario.query.filter_by(usuario=usuario).first()
        if user and check_password_hash(user.password, password):
            session['usuario'] = user.usuario
            flash('Inicio de sesión exitoso')
            return redirect(url_for('index'))
        flash('Usuario o contraseña incorrectos')
    return render_template('login.html')

@app.route('/registrar', methods=['GET', 'POST'])
def registrar():
    if request.method == 'POST':
        usuario = request.form['usuario']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        if Usuario.query.filter_by(usuario=usuario).first():
            flash('Usuario ya existe')
            return redirect(url_for('registrar'))
        nuevo = Usuario(usuario=usuario, email=email, password=password)
        db.session.add(nuevo)
        db.session.commit()
        flash('Usuario registrado correctamente')
        return redirect(url_for('login'))
    return render_template('registrar.html')

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    flash('Sesión cerrada')
    return redirect(url_for('login'))

### DASHBOARD ###
@app.route('/index')
def index():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    total_empleados = Empleado.query.count()
    total_candidatos = Candidato.query.count()
    return render_template('index.html', empleados=total_empleados, candidatos=total_candidatos)

### EMPLEADOS ###
@app.route('/empleados')
def empleados():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    busqueda = request.args.get('buscar')
    page = request.args.get('page', 1, type=int)
    query = Empleado.query
    if busqueda:
        query = query.filter(Empleado.nombre.ilike(f'%{busqueda}%') | Empleado.apellido.ilike(f'%{busqueda}%') | Empleado.cargo.ilike(f'%{busqueda}%'))
    empleados = query.paginate(page=page, per_page=5)
    if page > empleados.pages:
        flash('Página no válida')
        return redirect(url_for('empleados'))
    return render_template('empleados.html', empleados=empleados, buscar=busqueda)

@app.route('/empleado/nuevo', methods=['GET', 'POST'])
def nuevo_empleado():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        if not request.form['nombre'] or not request.form['apellido']:
            flash('Todos los campos son obligatorios')
            return redirect(url_for('nuevo_empleado'))
        emp = Empleado(
            nombre=request.form['nombre'],
            apellido=request.form['apellido'],
            cargo=request.form['cargo'],
            fecha_ingreso=datetime.strptime(request.form['fecha_ingreso'], '%Y-%m-%d'),
            estado=request.form['estado']
        )
        db.session.add(emp)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f'Error al guardar en la base de datos: {e}')
        flash('Empleado agregado')
        return redirect(url_for('empleados'))
    return render_template('nuevo_empleado.html')

@app.route('/empleado/editar/<int:id>', methods=['GET', 'POST'])
def editar_empleado(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))
    emp = Empleado.query.get_or_404(id)
    if request.method == 'POST':
        emp.nombre = request.form['nombre']
        emp.apellido = request.form['apellido']
        emp.cargo = request.form['cargo']
        emp.fecha_ingreso = datetime.strptime(request.form['fecha_ingreso'], '%Y-%m-%d')
        emp.estado = request.form['estado']
        db.session.commit()
        flash('Empleado actualizado')
        return redirect(url_for('empleados'))
    return render_template('editar_empleado.html', empleado=emp)

@app.route('/empleado/eliminar/<int:id>', methods=['POST'])
def eliminar_empleado(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))
    emp = Empleado.query.get_or_404(id)
    db.session.delete(emp)
    db.session.commit()
    flash('Empleado eliminado correctamente')
    return redirect(url_for('empleados'))

@app.route('/empleados/exportar')
def exportar_empleados():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    empleados = Empleado.query.all()
    data = [{
        'Nombre': e.nombre,
        'Apellido': e.apellido,
        'Cargo': e.cargo,
        'Fecha Ingreso': e.fecha_ingreso.strftime('%Y-%m-%d'),
        'Estado': e.estado
    } for e in empleados]
    df = pd.DataFrame(data)
    export_path = os.path.join(basedir, 'empleados_exportados.xlsx')
    try:
        df.to_excel(export_path, index=False)
    except Exception as e:
        flash(f'Error al exportar empleados: {e}')
        return redirect(url_for('empleados'))
    
    # Enviar el archivo como descarga
    return send_file(export_path, as_attachment=True, download_name='empleados_exportados.xlsx')

### CANDIDATOS ###
@app.route('/candidatos')
def candidatos():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    busqueda = request.args.get('buscar')
    page = request.args.get('page', 1, type=int)
    query = Candidato.query
    if busqueda:
        query = query.filter(Candidato.nombre.ilike(f'%{busqueda}%') | Candidato.puesto.ilike(f'%{busqueda}%'))
    candidatos = query.paginate(page=page, per_page=5)
    return render_template('candidatos.html', candidatos=candidatos, buscar=busqueda)

@app.route('/candidato/nuevo', methods=['GET', 'POST'])
def nuevo_candidato():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        c = Candidato(
            nombre=request.form['nombre'],
            puesto=request.form['puesto'],
            estado=request.form['estado']
        )
        db.session.add(c)
        db.session.commit()
        flash('Candidato agregado')
        return redirect(url_for('candidatos'))
    return render_template('nuevo_candidato.html')

@app.route('/candidato/editar/<int:id>', methods=['GET', 'POST'])
def editar_candidato(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))
    c = Candidato.query.get_or_404(id)
    if request.method == 'POST':
        c.nombre = request.form['nombre']
        c.puesto = request.form['puesto']
        c.estado = request.form['estado']
        db.session.commit()
        flash('Candidato actualizado')
        return redirect(url_for('candidatos'))
    return render_template('editar_candidato.html', candidato=c)

@app.route('/candidato/eliminar/<int:id>', methods=['POST'])
def eliminar_candidato(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))
    c = Candidato.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    flash('Candidato eliminado')
    return redirect(url_for('candidatos'))

if __name__ == '__main__':
    app.run(debug=True)
