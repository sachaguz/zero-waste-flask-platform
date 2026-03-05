import os
import time
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, abort, send_file
)
from flask_login import (
    LoginManager, login_user, login_required,
    logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import or_

# MODELOS
from models import (
    db, User, BlogPost, Curso, Categoria, Examen, PreguntaExamen,
    CapituloLectura, IntentosExamen, Certificado, PostTrash, InscripcionCurso
)

# ReportLab / PDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

# ----------------------------------------------------------------------
# Flask App
# ----------------------------------------------------------------------
app = Flask(__name__)

# Configuración
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ZeroWaste.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'clave_super_secreta'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Dónde guardar los certificados PDF
app.config['CERT_DIR'] = os.path.join('static', 'certificados')
os.makedirs(app.config['CERT_DIR'], exist_ok=True)

# Inicializar extensiones
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Crear la base si no existe
with app.app_context():
    db.create_all()


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------
def slugify(texto: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in (texto or "")).strip("-").lower()


def ensure_dirs():
    """Crea carpetas de subida si no existen."""
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join('static', 'uploads', 'imagenes'), exist_ok=True)
    os.makedirs(os.path.join('static', 'uploads', 'pdfs'), exist_ok=True)


def is_trashed(post_id: int) -> bool:
    return PostTrash.query.filter_by(post_id=post_id).first() is not None


def generate_certificate_pdf(user, curso, calificacion, salida_absoluta):
    """
    Certificado elegante en A4 horizontal con borde, watermark y QR.
    """
    c = canvas.Canvas(salida_absoluta, pagesize=landscape(A4))
    w, h = landscape(A4)   # horizontal
    margin = 1.6 * cm

    # Paleta de colores
    COL_TEXT = colors.HexColor("#0f172a")
    COL_MUTED = colors.HexColor("#475569")
    COL_ACCENT = colors.HexColor("#10b981")   # verde
    COL_ACCENT2 = colors.HexColor("#0ea5e9")  # azul
    COL_LINE = colors.HexColor("#e2e8f0")

    # Fondo
    c.setFillColor(colors.white)
    c.rect(0, 0, w, h, fill=1, stroke=0)

    # Watermark
    c.saveState()
    c.setFont("Helvetica-Bold", 80)
    c.setFillColor(colors.Color(0, 0, 0, alpha=0.05))
    c.translate(w * 0.5, h * 0.48)
    c.rotate(18)
    c.drawCentredString(0, 0, "ZERO WASTE")
    c.restoreState()

    # Bordes
    c.saveState()
    c.setLineWidth(2.4)
    c.setStrokeColor(COL_ACCENT2)
    c.roundRect(margin, margin, w - 2 * margin, h - 2 * margin, 16, stroke=1, fill=0)
    inset = margin + 0.5 * cm
    c.setLineWidth(0.8)
    c.setStrokeColor(COL_ACCENT)
    c.roundRect(inset, inset, w - 2 * inset, h - 2 * inset, 12, stroke=1, fill=0)
    c.restoreState()

    # Logo
    logo_path = os.path.join('static', 'img', 'logost.png')
    if os.path.exists(logo_path):
        try:
            img = ImageReader(logo_path)
            c.drawImage(img, margin + 1.2 * cm, h - margin - 2.5 * cm,
                        width=2.4 * cm, height=2.4 * cm, mask='auto')
        except Exception:
            pass

    # Encabezado
    title_y = h - margin - 3.2 * cm
    c.setFillColor(COL_TEXT)
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(w / 2, title_y, "CERTIFICADO DE FINALIZACIÓN")

    c.setFont("Helvetica", 13)
    c.setFillColor(COL_MUTED)
    c.drawCentredString(w / 2, title_y - 1.1 * cm, "Zero Waste — Formación en Sostenibilidad")

    # Nombre
    name_y = title_y - 3.2 * cm
    c.setFont("Helvetica-Bold", 34)
    c.setFillColor(COL_TEXT)
    c.drawCentredString(w / 2, name_y, user.nombre_completo)

    # Texto
    c.setFont("Helvetica", 13)
    c.setFillColor(COL_MUTED)
    c.drawCentredString(w / 2, name_y - 1.3 * cm, "ha completado y aprobado satisfactoriamente el curso:")

    # Curso
    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(COL_TEXT)
    c.drawCentredString(w / 2, name_y - 3.3 * cm, (curso.titulo or "")[:80])

    # Calificación y fecha
    fecha_str = datetime.utcnow().strftime("%d/%m/%Y")
    c.setFont("Helvetica", 12)
    c.setFillColor(COL_MUTED)
    c.drawCentredString(
        w / 2, name_y - 4.5 * cm,
        f"Calificación: {calificacion:.1f}/10   ·   Fecha: {fecha_str}"
    )

    # Firma
    line_y = margin + 3.2 * cm
    c.setStrokeColor(COL_LINE)
    c.line(w * 0.3, line_y, w * 0.7, line_y)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(COL_TEXT)
    c.drawCentredString(w * 0.5, line_y - 0.7 * cm, "Dirección Académica - Zero Waste")

    # QR (usando Drawing + renderPDF)
    qr_value = f"ZW|U{user.id}|C{curso.id}|{fecha_str}|{calificacion:.1f}"
    qrobj = qr.QrCodeWidget(qr_value)
    bounds = qrobj.getBounds()
    dW = bounds[2] - bounds[0]
    dH = bounds[3] - bounds[1]

    qr_w = 3.2 * cm
    qr_h = 3.2 * cm

    d = Drawing(qr_w, qr_h, transform=[qr_w / dW, 0, 0, qr_h / dH, 0, 0])
    d.add(qrobj)

    qr_x = w - margin - qr_w - 1.2 * cm
    qr_y = line_y - 1.2 * cm

    renderPDF.draw(d, c, qr_x, qr_y)

    # ID
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.grey)
    c.drawRightString(w - margin, margin + 0.7 * cm, f"ID: U{user.id}-C{curso.id}")

    c.showPage()
    c.save()


def get_or_create_certificate(user, curso, calificacion):
    """
    - Reutiliza el certificado si ya existe y el archivo está en disco.
    - Si no, genera uno nuevo (horizontal) y guarda la fila en DB.
    Retorna: (instancia_certificado, ruta_absoluta)
    """
    cert = (Certificado.query
            .filter_by(usuario_id=user.id, curso_id=curso.id)
            .order_by(Certificado.id.desc())
            .first())

    cert_dir = app.config['CERT_DIR']

    if cert:
        abs_path = os.path.join(cert_dir, cert.archivo)
        if os.path.exists(abs_path):
            return cert, abs_path

    ts = int(time.time())
    filename = f"certificado_u{user.id}_c{curso.id}_{ts}.pdf"
    abs_path = os.path.join(cert_dir, filename)

    generate_certificate_pdf(user, curso, calificacion, abs_path)

    cert = Certificado(usuario_id=user.id, curso_id=curso.id, archivo=filename)
    db.session.add(cert)
    db.session.commit()

    return cert, abs_path


# ----------------------------------------------------------------------
# Config Examen
# ----------------------------------------------------------------------
MAX_INTENTOS_EXAMEN = 2
MIN_APROBATORIA = 8.0


# ----------------------------------------------------------------------
# Blog (con soft delete mediante PostTrash)
# ----------------------------------------------------------------------
@app.route('/blog')
def blog():
    # Excluye posts en papelera
    posts = (db.session.query(BlogPost)
             .outerjoin(PostTrash, PostTrash.post_id == BlogPost.id)
             .filter(PostTrash.post_id == None)
             .order_by(BlogPost.fecha.desc())
             .all())
    return render_template('blog.html', posts=posts)


from sqlalchemy import func

@app.route('/post/<int:post_id>')
def ver_post(post_id):
    post = BlogPost.query.get_or_404(post_id)

    # Si está en papelera, restringir a admin/autor
    trashed = PostTrash.query.filter_by(post_id=post.id).first()
    if trashed and not (current_user.is_authenticated and
                        (current_user.es_admin or current_user.id == post.autor_id)):
        abort(404)

    # SUMAR SIEMPRE (sin usar session)
    try:
        (db.session.query(BlogPost)
         .filter(BlogPost.id == post_id)
         .update({BlogPost.vistas: func.coalesce(BlogPost.vistas, 0) + 1},
                 synchronize_session=False))
        db.session.commit()
        # Relee el post para mostrar el valor actualizado
        post = BlogPost.query.get(post_id)
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"[VISTAS][ERROR] post={post_id} -> {e}")

    return render_template('blog-detail.html', post=post)


@app.route('/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_post():
    if not current_user.es_admin:
        flash('Solo los administradores pueden crear publicaciones.', 'danger')
        return redirect(url_for('blog'))

    if request.method == 'POST':
        ensure_dirs()
        titulo = request.form['titulo']
        subtitulo = request.form['subtitulo']
        contenido = request.form['contenido']
        imagen = request.files.get('imagen')
        filename = None

        if imagen and imagen.filename:
            filename = secure_filename(imagen.filename)
            imagen.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        nuevo = BlogPost(
            titulo=titulo,
            subtitulo=subtitulo,
            contenido=contenido,
            imagen=filename,
            autor_id=current_user.id
        )
        db.session.add(nuevo)
        db.session.commit()
        flash('Post creado exitosamente.', 'success')
        return redirect(url_for('blog'))

    posts = (db.session.query(BlogPost)
             .outerjoin(PostTrash, PostTrash.post_id == BlogPost.id)
             .filter(PostTrash.post_id == None)
             .order_by(BlogPost.fecha.desc())
             .limit(2).all())
    return render_template('add-new-post.html', posts=posts)


@app.route('/posts/<int:post_id>/delete', methods=['POST'], endpoint='eliminar_post')
@login_required
def eliminar_post(post_id):
    post = BlogPost.query.get_or_404(post_id)

    # Autorización: admin o autor
    if not (current_user.es_admin or current_user.id == post.autor_id):
        abort(403)

    # ¿Ya estaba en papelera?
    if PostTrash.query.filter_by(post_id=post.id).first():
        flash("El post ya está en la papelera.", "info")
        return redirect(url_for('blog'))

    trash = PostTrash(post_id=post.id, deleted_by=current_user.id, deleted_at=datetime.utcnow())
    db.session.add(trash)
    db.session.commit()

    flash("Post enviado a la papelera (soft delete).", "success")
    return redirect(url_for('blog'))


@app.route('/papelera')
@login_required
def papelera():
    # Solo admin; si quieres permitir autores, cámbialo abajo en restaurar/destruir
    if not current_user.es_admin:
        abort(403)

    rows = (
        db.session.query(BlogPost, PostTrash)
        .join(PostTrash, PostTrash.post_id == BlogPost.id)
        .order_by(PostTrash.deleted_at.desc())
        .all()
    )
    return render_template('papelera.html', rows=rows)


from sqlalchemy import text

from sqlalchemy import text

@app.route('/posts/<int:post_id>/restore', methods=['POST'], endpoint='restaurar_post')
@login_required
def restaurar_post(post_id):
    # Permisos: admin o autor del post
    post = BlogPost.query.get_or_404(post_id)
    if not (current_user.es_admin or current_user.id == post.autor_id):
        abort(403)

    try:
        res = db.session.execute(
            text("DELETE FROM post_trash WHERE post_id = :pid"),
            {"pid": post_id}
        )
        db.session.commit()
        app.logger.info(f"[RESTORE_FORCE] post_id={post_id} rows_deleted={res.rowcount}")
        flash("Post restaurado.", "success")
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"[RESTORE_FORCE][ERROR] post_id={post_id}: {e}")
        flash("Error al restaurar.", "danger")

    # Vuelve a la papelera (o al detalle si prefieres)
    return redirect(url_for('papelera'))



from sqlalchemy import text

from sqlalchemy import text

@app.route('/posts/<int:post_id>/restore_force', methods=['POST'])
@login_required
def restaurar_post_force(post_id):
    if not current_user.es_admin:
        abort(403)
    try:
        res = db.session.execute(
            text("DELETE FROM post_trash WHERE post_id = :pid"),
            {"pid": post_id}
        )
        db.session.commit()
        # res.rowcount suele dar cuántas filas se afectaron
        app.logger.info(f"[RESTORE_FORCE] post_id={post_id} rows_deleted={res.rowcount}")
        flash(f"Restaurado (forzado). Filas borradas: {res.rowcount}", "success")
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"[RESTORE_FORCE][ERROR] post_id={post_id}: {e}")
        flash("Error al restaurar (forzado). Revisa logs.", "danger")
    return redirect(url_for('papelera'))


@app.route('/posts/<int:post_id>/destroy', methods=['POST'], endpoint='destruir_post')
@login_required
def destruir_post(post_id):
    # Solo admin (o ajusta si quieres permitir autor)
    if not current_user.es_admin:
        abort(403)

    post = BlogPost.query.get_or_404(post_id)

    try:
        db.session.delete(post)  # esto también eliminará PostTrash por cascade
        db.session.commit()
        flash("Post eliminado definitivamente.", "warning")
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"[PAPELERA][DESTROY][ERROR] post={post_id}: {e}")
        flash("No se pudo eliminar definitivamente el post.", "danger")

    return redirect(url_for('papelera'))


# Búsqueda (excluye papelera)
@app.route('/buscar')
def buscar():
    consulta = request.args.get('q', '').strip()
    if not consulta:
        flash('Ingresa un término de búsqueda.', 'warning')
        return redirect(url_for('blog'))

    resultados = (db.session.query(BlogPost)
                  .outerjoin(PostTrash, PostTrash.post_id == BlogPost.id)
                  .filter(PostTrash.post_id == None)
                  .filter(or_(
                      BlogPost.titulo.ilike(f'%{consulta}%'),
                      BlogPost.subtitulo.ilike(f'%{consulta}%'),
                      BlogPost.contenido.ilike(f'%{consulta}%')
                  ))
                  .order_by(BlogPost.fecha.desc())
                  .all())

    return render_template('resultados_busqueda.html', posts=resultados, consulta=consulta)


# ----------------------------------------------------------------------
# Autenticación
# ----------------------------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Sesión iniciada correctamente.', 'success')
            return redirect(url_for('blog'))
        else:
            flash('Correo o contraseña incorrectos.', 'danger')

    return render_template('sign-in-2.html')


from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash
from flask import render_template, request, redirect, url_for, flash

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Datos del formulario
        nombre = (request.form.get('nombre') or '').strip()                 # alias / nombre corto
        nombre_completo = (request.form.get('nombre_completo') or '').strip()
        estado = (request.form.get('estado') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''

        # Validaciones
        if not nombre_completo:
            # Si quieres exigirlo obligatoriamente, puedes hacer flash + redirect.
            # Aquí lo tomamos como fallback del alias.
            nombre_completo = nombre

        if not nombre or not email or not password:
            flash('Nombre, correo y contraseña son obligatorios.', 'warning')
            # Devuelve el form con lo ya escrito
            return render_template(
                'signup.html',
                form_data={
                    'nombre': nombre,
                    'nombre_completo': nombre_completo,
                    'estado': estado,
                    'email': email
                }
            )

        if len(password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres.', 'warning')
            return render_template(
                'signup.html',
                form_data={
                    'nombre': nombre,
                    'nombre_completo': nombre_completo,
                    'estado': estado,
                    'email': email
                }
            )

        # Email duplicado (check temprano)
        if User.query.filter_by(email=email).first():
            flash('El correo ya está registrado.', 'danger')
            return render_template(
                'signup.html',
                form_data={
                    'nombre': nombre,
                    'nombre_completo': nombre_completo,
                    'estado': estado,
                    'email': email
                }
            )

        # Normalización opcional del país (capitalización sencilla)
        if estado:
            estado = estado.strip()
            # Si prefieres dejarlo tal cual viene del <select>, comenta la línea siguiente
            # estado = estado.title()

        try:
            hashed_pw = generate_password_hash(password)

            nuevo_usuario = User(
                # Mantén "nombre" como alias corto; si no te interesa alias,
                # puedes setear nombre=nombre_completo[:100]
                nombre=nombre[:100] if nombre else (nombre_completo[:100] if nombre_completo else ''),
                nombre_completo=nombre_completo[:150] if nombre_completo else None,
                estado=estado or None,
                email=email,
                password=hashed_pw,
                es_admin=False
            )

            db.session.add(nuevo_usuario)
            db.session.commit()

        except IntegrityError:
            db.session.rollback()
            flash('Ocurrió un conflicto con los datos (posible correo duplicado).', 'danger')
            return render_template(
                'signup.html',
                form_data={
                    'nombre': nombre,
                    'nombre_completo': nombre_completo,
                    'estado': estado,
                    'email': email
                }
            )
        except Exception as e:
            db.session.rollback()
            # En prod, loguea e en vez de exponerlo
            flash('Ocurrió un error al crear la cuenta. Intenta de nuevo.', 'danger')
            return render_template(
                'signup.html',
                form_data={
                    'nombre': nombre,
                    'nombre_completo': nombre_completo,
                    'estado': estado,
                    'email': email
                }
            )

        flash('Cuenta creada correctamente. Ahora puedes iniciar sesión.', 'success')
        return redirect(url_for('login'))

    # GET
    return render_template('signup.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('blog'))





# ----------------------------------------------------------------------
# Power BI (solo admin)
# ----------------------------------------------------------------------
@app.route('/powerbi')
@login_required
def powerbi_dashboard():
    if not current_user.es_admin:
        abort(403)
    return render_template("powerbi.html")


# ----------------------------------------------------------------------
# Cursos, detalle y contenidos
# ----------------------------------------------------------------------
@app.route('/cursos/categoria/<categoria_nombre>')
def cursos_por_categoria(categoria_nombre):
    categoria = Categoria.query.filter_by(nombre=categoria_nombre).first_or_404()
    cursos = Curso.query.filter_by(categoria_id=categoria.id).all()
    return render_template("courses.html", cursos=cursos, categoria_actual=categoria.nombre)


@app.route('/curso/<int:curso_id>')
def detalle_curso(curso_id):
    curso = Curso.query.get_or_404(curso_id)
    lecturas = curso.lecturas if hasattr(curso, 'lecturas') else []
    examen = Examen.query.filter_by(curso_id=curso.id).first()
    preguntas = examen.preguntas if examen else []

    # --- NUEVO: saber si ya está inscrito ---
    is_inscrito = False
    if current_user.is_authenticated:
        is_inscrito = InscripcionCurso.query.filter_by(
            usuario_id=current_user.id,
            curso_id=curso.id
        ).first() is not None

    return render_template(
        'course-detail.html',
        curso=curso,
        lecturas=lecturas,
        examen=examen,
        preguntas=preguntas,
        is_inscrito=is_inscrito    # << se usa en el botón
    )



@app.route('/buscar_cursos')
def buscar_cursos():
    query = request.args.get('q', '')
    if query:
        cursos = Curso.query.filter(
            or_(Curso.titulo.ilike(f"%{query}%"),
                Curso.descripcion.ilike(f"%{query}%"))
        ).all()
    else:
        cursos = Curso.query.all()

    return render_template('courses.html', cursos=cursos, categoria_actual=None, query=query)


@app.route('/nuevo_curso', methods=['GET', 'POST'])
@login_required
def nuevo_curso():
    if request.method == 'POST':
        ensure_dirs()
        titulo = request.form.get('titulo')
        descripcion = request.form.get('descripcion')
        precio = request.form.get('precio', type=float)
        duracion_horas = request.form.get('duracion_horas', type=int)
        categoria_id = request.form.get('categoria_id', type=int)

        if not categoria_id:
            flash('Por favor, selecciona una categoría válida.', 'warning')
            return redirect(url_for('nuevo_curso'))

        fecha_inicio_str = request.form.get('fecha_inicio')
        fecha_fin_str = request.form.get('fecha_fin')
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d') if fecha_inicio_str else datetime.utcnow()
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d') if fecha_fin_str else None

        # Imagen del curso
        imagen_file = request.files.get('imagen')
        if imagen_file and imagen_file.filename != '':
            filename = secure_filename(imagen_file.filename)
            imagen_path = os.path.join('static', 'uploads', 'imagenes', filename)
            imagen_file.save(imagen_path)
        else:
            filename = 'default.png'

        nuevo = Curso(
            titulo=titulo,
            descripcion=descripcion,
            imagen=filename,
            precio=precio,
            duracion_horas=duracion_horas,
            categoria_id=categoria_id,
            creador_id=current_user.id,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin
        )
        db.session.add(nuevo)
        db.session.commit()

        # Capítulos (PDFs)
        titulos_cap = request.form.getlist('capitulo_titulo[]')
        archivos_cap = request.files.getlist('capitulo_pdf[]')
        for titulo_cap, archivo_pdf in zip(titulos_cap, archivos_cap):
            if archivo_pdf and archivo_pdf.filename != '':
                nombre_pdf = secure_filename(archivo_pdf.filename)
                ruta_pdf = os.path.join('static', 'uploads', 'pdfs', nombre_pdf)
                archivo_pdf.save(ruta_pdf)
                capitulo = CapituloLectura(
                    titulo=titulo_cap,
                    archivo_pdf=nombre_pdf,
                    curso_id=nuevo.id
                )
                db.session.add(capitulo)

        # Examen (opcional)
        preguntas_form = request.form.to_dict(flat=False)
        enunciados = [v for k, v in preguntas_form.items() if "enunciado" in k]
        if enunciados:
            examen = Examen(instrucciones="Examen final del curso", curso_id=nuevo.id)
            db.session.add(examen)
            db.session.commit()

            preguntas_por_indice = {}
            for key, value_list in preguntas_form.items():
                if key.startswith("preguntas["):
                    partes = key.split('[')
                    idx = partes[1].split(']')[0]
                    campo = partes[2].split(']')[0]
                    if idx not in preguntas_por_indice:
                        preguntas_por_indice[idx] = {}
                    preguntas_por_indice[idx][campo] = value_list[0]

            required = ['enunciado', 'opcion_a', 'opcion_b', 'opcion_c', 'opcion_d', 'respuesta_correcta']
            for datos in preguntas_por_indice.values():
                if all(campo in datos for campo in required):
                    pregunta = PreguntaExamen(
                        examen_id=examen.id,
                        enunciado=datos['enunciado'],
                        opcion_a=datos['opcion_a'],
                        opcion_b=datos['opcion_b'],
                        opcion_c=datos['opcion_c'],
                        opcion_d=datos['opcion_d'],
                        respuesta_correcta=datos['respuesta_correcta']
                    )
                    db.session.add(pregunta)

        db.session.commit()
        flash('Curso creado exitosamente', 'success')
        return redirect(url_for('cursos'))

    categorias = Categoria.query.all()
    return render_template('add-new-course.html', categorias=categorias)

from sqlalchemy.exc import IntegrityError


@app.route('/curso_contenido/<int:curso_id>')
def curso_contenido(curso_id):
    curso = Curso.query.get_or_404(curso_id)
    capitulos = curso.capitulos if hasattr(curso, 'capitulos') else []
    examen = Examen.query.filter_by(curso_id=curso.id).first()

    # ---------- Alta automática de inscripción ----------
    is_inscrito = False
    if current_user.is_authenticated:
        ins = InscripcionCurso.query.filter_by(
            usuario_id=current_user.id,
            curso_id=curso.id
        ).first()

        if not ins:
            try:
                ins = InscripcionCurso(
                    usuario_id=current_user.id,
                    curso_id=curso.id
                )
                db.session.add(ins)
                db.session.commit()
                # (Opcional) flash la primera vez
                # flash('Te inscribiste al curso correctamente.', 'success')
            except IntegrityError:
                db.session.rollback()
                # Si hubiera constraint único, evita crash en condición de carrera
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error al inscribir en curso {curso.id}: {e}")
                # flash("No pudimos registrar tu inscripción. Intenta de nuevo.", "warning")

        # Si hay registro (nuevo o ya existente), marcamos inscrito
        is_inscrito = True

    # ---------- Lógica de examen / progreso ----------
    curso_aprobado = False
    intentos_restantes = None
    ultima_nota = None

    if current_user.is_authenticated and examen:
        intentos = (IntentosExamen.query
                    .filter_by(usuario_id=current_user.id, examen_id=examen.id)
                    .order_by(IntentosExamen.id.desc())
                    .all())
        curso_aprobado = any(i.aprobado for i in intentos)
        intentos_restantes = max(0, MAX_INTENTOS_EXAMEN - len(intentos))
        ultima_nota = intentos[0].calificacion if intentos else None

    return render_template(
        'ver_curso.html',
        curso=curso,
        capitulos=capitulos,
        examen=examen,
        curso_aprobado=curso_aprobado,
        intentos_restantes=intentos_restantes,
        ultima_nota=ultima_nota,
        is_inscrito=is_inscrito,   # << por si lo quieres usar en la plantilla
    )



# ----------------------------------------------------------------------
# Examen y certificado
# ----------------------------------------------------------------------
@app.route('/examen/<int:curso_id>', methods=['GET', 'POST'])
def examen(curso_id):
    curso = Curso.query.get_or_404(curso_id)
    examen = Examen.query.filter_by(curso_id=curso.id).first_or_404()

    preguntas = list(examen.preguntas)
    user_id = current_user.id if current_user.is_authenticated else 1

    intentos_previos = (IntentosExamen.query
                        .filter_by(usuario_id=user_id, examen_id=examen.id)
                        .order_by(IntentosExamen.intento_numero)
                        .all())
    intentos_restantes = MAX_INTENTOS_EXAMEN - len(intentos_previos)
    if intentos_restantes <= 0:
        flash("Ya usaste tus 2 intentos para este examen.", "warning")
        return redirect(url_for('curso_contenido', curso_id=curso.id))

    if request.method == 'POST':
        total = len(preguntas)
        correctas = 0
        for p in preguntas:
            elegido = (request.form.get(f"pregunta_{p.id}") or "").strip().upper()
            correcta = (p.respuesta_correcta or "").strip().upper()
            if elegido == correcta:
                correctas += 1

        calificacion = round((correctas / total) * 10, 2) if total else 0.0
        aprobado = calificacion >= MIN_APROBATORIA

        intento = IntentosExamen(
            usuario_id=user_id,
            examen_id=examen.id,
            intento_numero=len(intentos_previos) + 1,
            calificacion=calificacion,
            aprobado=aprobado
        )
        db.session.add(intento)
        db.session.commit()

        if aprobado and current_user.is_authenticated:
            try:
                get_or_create_certificate(current_user, curso, calificacion)
            except Exception as e:
                app.logger.error(f"Error generando certificado: {e}")

        flash(f'Resultado guardado: {calificacion}/10', 'success')
        return redirect(url_for('resultado_examen', curso_id=curso.id))

    return render_template('examen.html',
                           curso=curso,
                           preguntas=preguntas,
                           intentos_restantes=intentos_restantes)


@app.route('/resultado_examen/<int:curso_id>')
def resultado_examen(curso_id):
    curso = Curso.query.get_or_404(curso_id)
    user_id = current_user.id if current_user.is_authenticated else 1

    intento = (IntentosExamen.query
               .join(Examen, IntentosExamen.examen_id == Examen.id)
               .filter(Examen.curso_id == curso_id,
                       IntentosExamen.usuario_id == user_id)
               .order_by(IntentosExamen.id.desc())
               .first_or_404())
    return render_template('resultado_examen.html', curso=curso, intento=intento)

from flask import render_template

@app.route('/about', endpoint='about-us')
def home():
    return render_template('about-us.html')

@app.route('/terminos', endpoint='terminos')
def home():
    return render_template('privacy-n-policy.html')

@app.route('/', endpoint='home')
def home():
    return render_template('company-home.html')

from flask_login import login_required, current_user
from sqlalchemy import or_

from flask_login import login_required, current_user
from sqlalchemy import or_

from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError

@app.route("/profile", methods=["GET"])
@login_required
def profile():
    # --- Cursos en los que está inscrito el usuario (curso + fecha_inscripcion) ---
    filas = (
        db.session.query(Curso, InscripcionCurso.fecha_inscripcion)
        .join(InscripcionCurso, InscripcionCurso.curso_id == Curso.id)
        .filter(InscripcionCurso.usuario_id == current_user.id)
        .options(
            joinedload(Curso.categoria_obj),  # categoría
            joinedload(Curso.creador),        # autor
            joinedload(Curso.capitulos),      # lecturas
        )
        .order_by(InscripcionCurso.fecha_inscripcion.desc())
        .all()
    )

    # Armar mis_cursos con estado y última calificación
    mis_cursos = []
    for curso, fecha_inscripcion in filas:
        examen = Examen.query.filter_by(curso_id=curso.id).first()
        aprobado = False
        ultima_cal = None
        examen_id = None

        if examen:
            examen_id = examen.id
            intento = (
                IntentosExamen.query
                .filter_by(usuario_id=current_user.id, examen_id=examen.id)
                .order_by(IntentosExamen.id.desc())
                .first()
            )
            if intento:
                ultima_cal = intento.calificacion
                aprobado = bool(intento.aprobado)

        mis_cursos.append({
            "curso": curso,
            "fecha_inscripcion": fecha_inscripcion,
            "estado": "Finalizado" if aprobado else "En Proceso",
            "ultima_calificacion": ultima_cal,
            "examen_id": examen_id,
        })

    # --- Posts del usuario (excluye papelera con PostTrash) ---
    mis_posts = (
        db.session.query(BlogPost)
        .filter(BlogPost.autor_id == current_user.id)
        .outerjoin(PostTrash, PostTrash.post_id == BlogPost.id)
        .filter(PostTrash.post_id == None)   # no está en papelera
        .order_by(BlogPost.fecha.desc())
        .all()
    )

    # (Opcional) logs de depuración
    app.logger.info(f"[PROFILE] user={current_user.id} cursos={len(mis_cursos)} posts={len(mis_posts)}")

    return render_template(
        "profile.html",
        usuario=current_user,
        mis_posts=mis_posts,
        mis_cursos=mis_cursos,    # << ¡Ahora sí se envía al template!
    )



# Dos rutas que apuntan al mismo endpoint, para compatibilidad con tu front
@app.route('/descargar_certificado/<int:curso_id>')
@app.route('/curso/<int:curso_id>/certificado/descargar', endpoint='descargar_certificado')
@login_required
def descargar_certificado(curso_id):
    examen = Examen.query.filter_by(curso_id=curso_id).first_or_404()

    intento_aprobado = (IntentosExamen.query
                        .filter_by(usuario_id=current_user.id, examen_id=examen.id, aprobado=True)
                        .order_by(IntentosExamen.id.desc())
                        .first())
    if not intento_aprobado:
        flash("Aún no has aprobado este examen.", "warning")
        return redirect(url_for('curso_contenido', curso_id=curso_id))

    calificacion = intento_aprobado.calificacion or 0.0
    cert, abs_path = get_or_create_certificate(current_user, examen.curso, calificacion)

    try:
        nice_name = f"certificado-{slugify(examen.curso.titulo)}.pdf"
    except Exception:
        nice_name = f"certificado-curso-{curso_id}.pdf"

    resp = send_file(
        abs_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=nice_name,
        etag=False,
        last_modified=None,
        conditional=False
    )
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


# ----------------------------------------------------------------------
# Listado de cursos
# ----------------------------------------------------------------------
@app.route('/cursos')
def cursos():
    cursos = Curso.query.all()
    return render_template("courses.html", cursos=cursos, categoria_actual=None)

from flask import redirect, url_for




# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
if __name__ == '__main__':
    ensure_dirs()

    with app.app_context():
        # Admin por defecto (desarrollo)
        if not User.query.filter_by(email="admin@zerowaste.com").first():
            admin_user = User(
                nombre="Administrador",
                email="admin@zerowaste.com",
                password=generate_password_hash("admin123"),
                es_admin=True,
                nombre_completo="Administrador"
            )
            db.session.add(admin_user)
            db.session.commit()

        # Categorías por defecto
        if Categoria.query.count() == 0:
            for nombre in ['Educación', 'Innovación', 'Empresas', 'Tecnología']:
                db.session.add(Categoria(nombre=nombre))
            db.session.commit()

    app.run(debug=True)
