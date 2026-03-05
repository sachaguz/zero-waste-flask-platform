from app import app, db
from models import BlogPost

with app.app_context():
    post = BlogPost(
        titulo='Segundo post real',
        contenido='Este es un segundo post guardado en la base de datos.',
        autor='Saúl'
    )
    db.session.add(post)
    db.session.commit()
    print("Post insertado")
