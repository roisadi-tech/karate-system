from app import app
from database import db

from models import Usuario

from werkzeug.security import generate_password_hash


with app.app_context():

    existe = Usuario.query.filter_by(
        usuario='admin'
    ).first()

    if existe:

        print('Usuário admin já existe.')

    else:

        novo = Usuario(

            usuario='admin',

            senha=generate_password_hash('1234'),

            tipo='admin'
        )

        db.session.add(novo)

        db.session.commit()

        print('Admin criado com sucesso.')