from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

# ------------------------
# Tabla de usuarios
# ------------------------


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Alias o nombre corto que ya usabas en certificados/perfil
    nombre = db.Column(db.String(100), nullable=False)

    # NUEVOS CAMPOS
    nombre_completo = db.Column(db.String(150), nullable=True, index=True)
    estado = db.Column(db.String(100), nullable=True, index=True)

    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password = db.Column(db.String(200), nullable=False)
    es_admin = db.Column(db.Boolean, default=False)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    imagen = db.Column(db.String(100), default='default.png')

    # Relaciones existentes
    posts = db.relationship('BlogPost', backref='autor_usuario', lazy=True)
    inscripciones = db.relationship('InscripcionCurso', backref='usuario', lazy=True)

    # Quién envía posts a la papelera (soft delete)
    deleted_posts = db.relationship(
        'PostTrash',
        back_populates='deleter',
        foreign_keys='PostTrash.deleted_by',
        lazy=True
    )

    # (Opcional) Nombre a mostrar; prioriza nombre_completo si existe
    @property
    def display_name(self):
        return self.nombre_completo or self.nombre


# ------------------------
# Tabla de posts de blog
# ------------------------
class BlogPost(db.Model):
    # Nota: sin __tablename__, será 'blog_post'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    subtitulo = db.Column(db.String(300))
    contenido = db.Column(db.Text, nullable=False)
    imagen = db.Column(db.String(300))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    vistas = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    autor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    

    # Relación 1-1 con PostTrash (nuevo enfoque usado por app.py)
    trash = db.relationship(
        'PostTrash',
        uselist=False,
        back_populates='post',
        cascade='all, delete-orphan',
        single_parent=True,
        lazy=True
    )

    # Helpers opcionales para usar PostTrash
    def soft_delete(self, deleted_by=None, when=None):
        """Envia el post a papelera mediante PostTrash."""
        if not self.trash:
            self.trash = PostTrash(
                post=self,
                deleted_by=deleted_by,
                deleted_at=when or datetime.utcnow()
            )

    def restore(self):
        """Restaura el post desde papelera."""
        if self.trash:
            db.session.delete(self.trash)

# ------------------------
# Tabla PostTrash (papelera de posts)
# ------------------------
class PostTrash(db.Model):
    __tablename__ = 'post_trash'
    id = db.Column(db.Integer, primary_key=True)

    # FK al post (único: un post solo puede estar una vez en papelera)
    post_id = db.Column(db.Integer, db.ForeignKey('blog_post.id'), nullable=False, unique=True, index=True)

    # Quién lo envió a papelera (usuario)
    deleted_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)

    # Cuándo se envió a papelera
    deleted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Opcional: razón
    reason = db.Column(db.String(255), nullable=True)

    # Relaciones
    post = db.relationship('BlogPost', back_populates='trash', lazy=True)
    deleter = db.relationship('User', back_populates='deleted_posts', lazy=True)

# ------------------------
# Tabla de categorías normalizadas
# ------------------------
class Categoria(db.Model):
    __tablename__ = 'categorias'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)

    cursos = db.relationship('Curso', backref='categoria_obj', lazy=True)

# ------------------------
# Tabla de cursos
# ------------------------
class Curso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    imagen = db.Column(db.String(200), nullable=False)  # Ruta de la imagen
    precio = db.Column(db.Float, nullable=False)
    duracion_horas = db.Column(db.Integer, nullable=False)
    fecha_inicio = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    fecha_fin = db.Column(db.DateTime, nullable=True)
    # Normalización: FK hacia Categoria
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias.id'), nullable=False)
    creador_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    creador = db.relationship('User', backref='cursos_creados')
    

    @property
    def num_lecturas(self):
        return len(self.capitulos)

class IntentosExamen(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    examen_id = db.Column(db.Integer, db.ForeignKey('examen.id'), nullable=False)
    intento_numero = db.Column(db.Integer, nullable=False)
    calificacion = db.Column(db.Float)
    aprobado = db.Column(db.Boolean, default=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

    usuario = db.relationship('User', backref='intentos_examen')
    examen = db.relationship('Examen', backref='intentos')

# ------------------------
# Inscripción de usuarios a cursos
# ------------------------
class InscripcionCurso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    curso_id = db.Column(db.Integer, db.ForeignKey('curso.id'), nullable=False)
    fecha_inscripcion = db.Column(db.DateTime, default=datetime.utcnow)

# ------------------------
# Lecturas de los cursos
# ------------------------
class CapituloLectura(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    archivo_pdf = db.Column(db.String(200), nullable=False)  # Ruta al PDF
    curso_id = db.Column(db.Integer, db.ForeignKey('curso.id'), nullable=False)

    curso = db.relationship('Curso', backref='capitulos', lazy=True)

class Examen(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    instrucciones = db.Column(db.Text)
    curso_id = db.Column(db.Integer, db.ForeignKey('curso.id'), nullable=False)

    curso = db.relationship('Curso', backref='examen', uselist=False)

class PreguntaExamen(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    examen_id = db.Column(db.Integer, db.ForeignKey('examen.id'), nullable=False)

    enunciado = db.Column(db.Text, nullable=False)
    opcion_a = db.Column(db.String(200), nullable=False)
    opcion_b = db.Column(db.String(200), nullable=False)
    opcion_c = db.Column(db.String(200), nullable=False)
    opcion_d = db.Column(db.String(200), nullable=False)
    respuesta_correcta = db.Column(db.String(1), nullable=False)  # 'A', 'B', 'C', 'D'

    examen = db.relationship('Examen', backref='preguntas')


class Certificado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    curso_id = db.Column(db.Integer, db.ForeignKey('curso.id'), nullable=False)
    archivo = db.Column(db.String(200), nullable=False)  # Ruta al PDF generado
    fecha_emision = db.Column(db.DateTime, default=datetime.utcnow)

    usuario = db.relationship('User', backref='certificados')
    curso = db.relationship('Curso', backref='certificados')
