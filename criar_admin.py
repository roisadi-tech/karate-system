from app import app
from database import db
from models import Usuario

from werkzeug.security import generate_password_hash

with app.app_context():

    usuario_existe = Usuario.query.filter_by(
        usuario='admin'
    ).first()

    if not usuario_existe:

        novo_usuario = Usuario(

            usuario='admin',

            senha=generate_password_hash('1234'),

            tipo='admin'
        )

        db.session.add(novo_usuario)

        db.session.commit()

        print('Admin criado com sucesso!')

    else:

        print('Admin já existe.')