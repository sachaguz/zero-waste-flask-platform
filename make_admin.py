from app import app
from models import db, User

with app.app_context():
    # Cambia el correo por el del usuario que quieres hacer admin
    user = User.query.filter_by(email='sachaguz05@gmail.com').first()

    if user:
        user.es_admin = True
        db.session.commit()
        print(f"✅ Usuario {user.nombre} ahora es administrador.")
    else:
        print("❌ Usuario no encontrado.")
