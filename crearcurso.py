from app import app, db
from models import User, Categoria, Curso  # Asegúrate de importar correctamente

with app.app_context():
    # Buscar un usuario existente que será el autor del curso
    autor = User.query.filter_by(email='admin@zerowaste.com').first()
    if not autor:
        print("❌ No se encontró el usuario. Crea el usuario primero.")
        exit()

    # Buscar o crear la categoría (ej. 'Educación')
    categoria = Categoria.query.filter_by(nombre='Educación').first()
    if not categoria:
        categoria = Categoria(nombre='Educación')
        db.session.add(categoria)
        db.session.commit()

    # Crear un curso de ejemplo
    nuevo_curso = Curso(
        titulo='Colombia',
        descripcion='Cordero',
        imagen='album1.png',  # Asegúrate que exista esta imagen en static/images/
        precio=199.99,
        
        duracion_horas=6,
        categoria_id=categoria.id,
        creador_id=autor.id
    )

    # Agregar y guardar en la base de datos
    db.session.add(nuevo_curso)
    db.session.commit()
    print("✅ Curso agregado correctamente.")
