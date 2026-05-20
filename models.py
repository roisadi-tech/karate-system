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
        db.String(20)
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
        db.String(20)
    )

    status = db.Column(
        db.String(20)
    )

    aluno = db.relationship(
        'Aluno',
        backref='mensalidades'
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
        db.String(20)
    )

    status = db.Column(
        db.String(20)
    )

    aluno = db.relationship(
        'Aluno',
        backref='presencas'
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
        db.String(20)
    )

    resultado = db.Column(
        db.String(20)
    )

    aluno = db.relationship(
        'Aluno',
        backref='exames'
    )