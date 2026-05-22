from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    send_file,
    flash
)

from database import db

from models import (
    Aluno,
    Mensalidade,
    Presenca,
    Exame,
    Usuario
)

import os
import shutil

from datetime import datetime

from functools import wraps

from werkzeug.utils import secure_filename

from werkzeug.security import (
    check_password_hash
)

from reportlab.pdfgen import canvas


# =====================================
# APP
# =====================================

app = Flask(__name__)

app.secret_key = 'karate_secret'


# =====================================
# DATABASE
# =====================================

database_url = os.getenv('DATABASE_URL')

if database_url:

    database_url = database_url.replace(
        "postgres://",
        "postgresql://",
        1
    )

app.config['SQLALCHEMY_DATABASE_URI'] = (
    database_url or 'sqlite:///database.db'
)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)


# =====================================
# LOGIN OBRIGATÓRIO
# =====================================

def login_obrigatorio(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if 'usuario' not in session:

            return redirect('/login')

        return f(*args, **kwargs)

    return decorated_function


# =====================================
# ADMIN OBRIGATÓRIO
# =====================================

def admin_obrigatorio(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if session.get('tipo') != 'admin':

            flash('Acesso permitido apenas para administradores.')

            return redirect('/')

        return f(*args, **kwargs)

    return decorated_function


# =====================================
# DASHBOARD
# =====================================

@app.route('/')
@login_obrigatorio
def index():

    total_alunos = Aluno.query.count()

    faturamento = db.session.query(
        db.func.sum(Mensalidade.valor)
    ).filter(
        Mensalidade.status == 'PAGO'
    ).scalar()

    if faturamento is None:
        faturamento = 0

    inadimplentes = Mensalidade.query.filter_by(
        status='PENDENTE'
    ).count()

    alunos = Aluno.query.all()

    aptos = 0

    for aluno in alunos:

        total = Presenca.query.filter_by(
            aluno_id=aluno.id
        ).count()

        presentes = Presenca.query.filter_by(
            aluno_id=aluno.id,
            status='PRESENTE'
        ).count()

        if total > 0:

            percentual = (
                presentes / total
            ) * 100

            if percentual >= 75:

                aptos += 1

    return render_template(
        'index.html',
        total_alunos=total_alunos,
        faturamento=faturamento,
        inadimplentes=inadimplentes,
        aptos=aptos
    )


# =====================================
# LOGIN
# =====================================

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        usuario_form = request.form['usuario']
        senha_form = request.form['senha']

        usuario = Usuario.query.filter_by(
            usuario=usuario_form
        ).first()

        if usuario and check_password_hash(
            usuario.senha,
            senha_form
        ):

            session['usuario'] = usuario.usuario
            session['tipo'] = usuario.tipo

            return redirect('/')

        flash('Usuário ou senha inválidos.')

    return render_template('login.html')


# =====================================
# LOGOUT
# =====================================

@app.route('/logout')
def logout():

    session.clear()

    return redirect('/login')


# =====================================
# ALUNOS
# =====================================

@app.route('/alunos')
@login_obrigatorio
def alunos():

    busca = request.args.get('busca')

    if busca:

        lista_alunos = Aluno.query.filter(
            Aluno.nome.ilike(f'%{busca}%')
        ).order_by(
            Aluno.id.desc()
        ).all()

    else:

        lista_alunos = Aluno.query.order_by(
            Aluno.id.desc()
        ).all()

    return render_template(
        'alunos.html',
        alunos=lista_alunos
    )


# =====================================
# CADASTRAR ALUNO
# =====================================

@app.route('/cadastrar_aluno', methods=['GET', 'POST'])
@login_obrigatorio
def cadastrar_aluno():

    if request.method == 'POST':

        nome = request.form['nome']
        nascimento = request.form['nascimento']
        responsavel = request.form['responsavel']
        whatsapp = request.form['whatsapp']
        faixa = request.form['faixa']
        mensalidade = request.form['mensalidade']

        foto = request.files['foto']

        nome_arquivo = ''

        if foto and foto.filename != '':

            nome_arquivo = secure_filename(
                foto.filename
            )

            if not os.path.exists('static/uploads'):

                os.makedirs('static/uploads')

            caminho = os.path.join(
                'static/uploads',
                nome_arquivo
            )

            foto.save(caminho)

        novo_aluno = Aluno(

            nome=nome,
            idade=nascimento,
            sexo=responsavel,
            whatsapp=whatsapp,
            faixa=faixa,
            mensalidade=mensalidade,
            foto=nome_arquivo
        )

        db.session.add(novo_aluno)

        db.session.commit()

        flash('Aluno cadastrado com sucesso.')

        return redirect('/alunos')

    return render_template(
        'cadastrar_aluno.html'
    )


# =====================================
# EDITAR ALUNO
# =====================================

@app.route('/editar_aluno/<int:id>', methods=['GET', 'POST'])
@login_obrigatorio
def editar_aluno(id):

    aluno = Aluno.query.get_or_404(id)

    if request.method == 'POST':

        aluno.nome = request.form['nome']
        aluno.faixa = request.form['faixa']
        aluno.whatsapp = request.form['whatsapp']
        aluno.mensalidade = request.form['mensalidade']

        foto = request.files['foto']

        if foto and foto.filename != '':

            nome_arquivo = secure_filename(
                foto.filename
            )

            caminho = os.path.join(
                'static/uploads',
                nome_arquivo
            )

            foto.save(caminho)

            aluno.foto = nome_arquivo

        db.session.commit()

        flash('Aluno atualizado.')

        return redirect('/alunos')

    return render_template(
        'editar_aluno.html',
        aluno=aluno
    )


# =====================================
# EXCLUIR ALUNO
# =====================================

@app.route('/excluir_aluno/<int:id>')
@login_obrigatorio
@admin_obrigatorio
def excluir_aluno(id):

    aluno = Aluno.query.get_or_404(id)

    if aluno.foto:

        caminho = os.path.join(
            'static/uploads',
            aluno.foto
        )

        if os.path.exists(caminho):

            os.remove(caminho)

    db.session.delete(aluno)

    db.session.commit()

    flash('Aluno excluído.')

    return redirect('/alunos')


# =====================================
# PRESENÇAS
# =====================================

@app.route('/presencas', methods=['GET', 'POST'])
@login_obrigatorio
def presencas():

    if request.method == 'POST':

        nova_presenca = Presenca(

            aluno_id=request.form['aluno_id'],
            data=request.form['data'],
            status=request.form['status']
        )

        db.session.add(nova_presenca)

        db.session.commit()

        flash('Presença registrada.')

        return redirect('/presencas')

    alunos = Aluno.query.order_by(
        Aluno.nome.asc()
    ).all()

    lista_presencas = Presenca.query.order_by(
        Presenca.data.desc()
    ).all()

    return render_template(
        'presencas.html',
        alunos=alunos,
        presencas=lista_presencas
    )


# =====================================
# FREQUÊNCIA
# =====================================

@app.route('/frequencia')
@login_obrigatorio
def frequencia():

    alunos = Aluno.query.order_by(
        Aluno.nome.asc()
    ).all()

    relatorio = []

    for aluno in alunos:

        total = Presenca.query.filter_by(
            aluno_id=aluno.id
        ).count()

        presentes = Presenca.query.filter_by(
            aluno_id=aluno.id,
            status='PRESENTE'
        ).count()

        percentual = 0

        if total > 0:

            percentual = round(
                (presentes / total) * 100,
                1
            )

        relatorio.append({

            'nome': aluno.nome,
            'total': total,
            'presentes': presentes,
            'percentual': percentual
        })

    return render_template(
        'frequencia.html',
        relatorio=relatorio
    )


# =====================================
# MENSALIDADES
# =====================================

@app.route('/mensalidades', methods=['GET', 'POST'])
@login_obrigatorio
def mensalidades():

    if request.method == 'POST':

        nova_mensalidade = Mensalidade(

            aluno_id=request.form['aluno_id'],
            valor=request.form['valor'],
            vencimento=request.form['vencimento'],
            status=request.form['status']
        )

        db.session.add(nova_mensalidade)

        db.session.commit()

        flash('Mensalidade cadastrada.')

        return redirect('/mensalidades')

    alunos = Aluno.query.order_by(
        Aluno.nome.asc()
    ).all()

    lista = Mensalidade.query.order_by(
        Mensalidade.vencimento.desc()
    ).all()

    return render_template(
        'mensalidades.html',
        alunos=alunos,
        mensalidades=lista
    )


# =====================================
# EXAMES
# =====================================

@app.route('/exames', methods=['GET', 'POST'])
@login_obrigatorio
def exames():

    if request.method == 'POST':

        aluno_id = request.form['aluno_id']

        novo_exame = Exame(

            aluno_id=aluno_id,
            faixa_atual=request.form['faixa_atual'],
            nova_faixa=request.form['nova_faixa'],
            data_exame=request.form['data_exame'],
            resultado=request.form['resultado']
        )

        db.session.add(novo_exame)

        if request.form['resultado'] == 'APROVADO':

            aluno = Aluno.query.get(aluno_id)

            if aluno:

                aluno.faixa = request.form['nova_faixa']

        db.session.commit()

        flash('Exame registrado.')

        return redirect('/exames')

    alunos = Aluno.query.order_by(
        Aluno.nome.asc()
    ).all()

    lista = Exame.query.order_by(
        Exame.data_exame.desc()
    ).all()

    return render_template(
        'exames.html',
        alunos=alunos,
        exames=lista
    )


# =====================================
# COBRANÇAS
# =====================================

@app.route('/cobrar')
@login_obrigatorio
def cobrar():

    dados = Mensalidade.query.filter_by(
        status='PENDENTE'
    ).order_by(
        Mensalidade.vencimento.asc()
    ).all()

    return render_template(
        'cobrar.html',
        dados=dados
    )


# =====================================
# RECIBO PDF
# =====================================

@app.route('/recibo/<int:id>')
@login_obrigatorio
def recibo(id):

    mensalidade = Mensalidade.query.get_or_404(id)

    if not os.path.exists('recibos'):

        os.makedirs('recibos')

    nome_arquivo = f'recibos/recibo_{id}.pdf'

    c = canvas.Canvas(nome_arquivo)

    c.setFont("Helvetica-Bold", 22)

    c.drawString(200, 800, "RECIBO")

    c.setFont("Helvetica", 12)

    c.drawString(
        100,
        730,
        f'Aluno: {mensalidade.aluno.nome}'
    )

    c.drawString(
        100,
        700,
        f'Valor: R$ {mensalidade.valor}'
    )

    c.drawString(
        100,
        670,
        f'Vencimento: {mensalidade.vencimento}'
    )

    c.drawString(
        100,
        640,
        f'Status: {mensalidade.status}'
    )

    c.drawString(
        100,
        580,
        'Academia de Karatê'
    )

    c.save()

    return send_file(
        nome_arquivo,
        as_attachment=True
    )


# =====================================
# BACKUP
# =====================================

@app.route('/backup')
@login_obrigatorio
@admin_obrigatorio
def backup():

    data = datetime.now().strftime(
        '%Y-%m-%d_%H-%M-%S'
    )

    nome_backup = f'backup_{data}.db'

    origem = 'database.db'

    if not os.path.exists('backups'):

        os.makedirs('backups')

    destino = os.path.join(
        'backups',
        nome_backup
    )

    shutil.copy(
        origem,
        destino
    )

    return send_file(
        destino,
        as_attachment=True
    )


# =====================================
# RELATÓRIOS
# =====================================

@app.route('/relatorios')
@login_obrigatorio
def relatorios():

    total_alunos = Aluno.query.count()

    recebido = db.session.query(
        db.func.sum(Mensalidade.valor)
    ).filter(
        Mensalidade.status == 'PAGO'
    ).scalar()

    if recebido is None:
        recebido = 0

    pendente = db.session.query(
        db.func.sum(Mensalidade.valor)
    ).filter(
        Mensalidade.status == 'PENDENTE'
    ).scalar()

    if pendente is None:
        pendente = 0

    faixas = db.session.query(
        Aluno.faixa,
        db.func.count(Aluno.id)
    ).group_by(
        Aluno.faixa
    ).all()

    return render_template(
        'relatorios.html',
        total_alunos=total_alunos,
        recebido=recebido,
        pendente=pendente,
        faixas=faixas
    )


# =====================================
# INICIAR APP
# =====================================

with app.app_context():

    db.create_all()


if __name__ == '__main__':

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )