from database import db


class Aluno(db.Model):

    __tablename__ = 'alunos'

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    nome = db.Column(
        db.String(200),
        nullable=False
    )

    idade = db.Column(
        db.String(50)
    )

    sexo = db.Column(
        db.String(50)
    )

    whatsapp = db.Column(
        db.String(30)
    )

    faixa = db.Column(
        db.String(50)
    )

    mensalidade = db.Column(
        db.Float
    )

    foto = db.Column(
        db.String(300)
    )


class Presenca(db.Model):

    __tablename__ = 'presencas'

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    aluno_id = db.Column(
        db.Integer,
        db.ForeignKey('alunos.id')
    )

    data = db.Column(
        db.String(30)
    )

    status = db.Column(
        db.String(30)
    )

    aluno = db.relationship(
        'Aluno',
        backref='presencas'
    )


class Mensalidade(db.Model):

    __tablename__ = 'mensalidades'

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    aluno_id = db.Column(
        db.Integer,
        db.ForeignKey('alunos.id')
    )

    valor = db.Column(
        db.Float
    )

    vencimento = db.Column(
        db.String(30)
    )

    status = db.Column(
        db.String(30)
    )

    aluno = db.relationship(
        'Aluno',
        backref='mensalidades'
    )


class Exame(db.Model):

    __tablename__ = 'exames'

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    aluno_id = db.Column(
        db.Integer,
        db.ForeignKey('alunos.id')
    )

    faixa_atual = db.Column(
        db.String(50)
    )

    nova_faixa = db.Column(
        db.String(50)
    )

    data_exame = db.Column(
        db.String(30)
    )

    resultado = db.Column(
        db.String(30)
    )

    aluno = db.relationship(
        'Aluno',
        backref='exames'
    )


class Usuario(db.Model):

    __tablename__ = 'usuarios'

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    usuario = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    senha = db.Column(
        db.String(300),
        nullable=False
    )

    tipo = db.Column(
        db.String(30),
        default='professor'
    )