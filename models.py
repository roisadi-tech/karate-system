from database import db


class Aluno(db.Model):
    
    __tablename__ = 'alunos'

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(200), nullable=False)
    nascimento = db.Column(db.String(30))
    sexo = db.Column(db.String(30))
    responsavel = db.Column(db.String(200))
    whatsapp = db.Column(db.String(30))
    faixa = db.Column(db.String(50))
    mensalidade = db.Column(db.Float)
    foto = db.Column(db.String(300))

    # Campos antigos, podem ficar por enquanto
    turma = db.Column(db.String(100))
    professor = db.Column(db.String(100))

    # Novo vínculo correto com turma
    turma_id = db.Column(db.Integer, db.ForeignKey('turmas.id'))

    turma_relacao = db.relationship(
        'Turma',
        backref='alunos'
    )


class Presenca(db.Model):

    __tablename__ = 'presencas'

    id = db.Column(db.Integer, primary_key=True)

    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'))
    data = db.Column(db.String(30))
    status = db.Column(db.String(30))

    aluno = db.relationship(
        'Aluno',
        backref='presencas'
    )


class Mensalidade(db.Model):

    __tablename__ = 'mensalidades'

    id = db.Column(db.Integer, primary_key=True)

    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'))
    valor = db.Column(db.Float)
    vencimento = db.Column(db.String(30))
    status = db.Column(db.String(30))

    aluno = db.relationship(
        'Aluno',
        backref='mensalidades'
    )


class Exame(db.Model):

    __tablename__ = 'exames'

    id = db.Column(db.Integer, primary_key=True)

    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'))
    faixa_atual = db.Column(db.String(50))
    nova_faixa = db.Column(db.String(50))
    data_exame = db.Column(db.String(30))
    resultado = db.Column(db.String(30))

    aluno = db.relationship(
        'Aluno',
        backref='exames'
    )


class Usuario(db.Model):

    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)

    usuario = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(300), nullable=False)
    tipo = db.Column(db.String(30), default='professor')

    professor_id = db.Column(
        db.Integer,
        db.ForeignKey('professores.id')
    )

    professor = db.relationship(
        'Professor',
        backref='usuarios'
    )


class Professor(db.Model):

    __tablename__ = 'professores'

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(150), nullable=False)
    telefone = db.Column(db.String(30))
    observacao = db.Column(db.String(300))


class Turma(db.Model):

    __tablename__ = 'turmas'

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(150), nullable=False)
    dias = db.Column(db.String(150))
    horario = db.Column(db.String(100))
    observacao = db.Column(db.String(300))

    professor_id = db.Column(
        db.Integer,
        db.ForeignKey('professores.id')
    )

    professor = db.relationship(
        'Professor',
        backref='turmas'
    )