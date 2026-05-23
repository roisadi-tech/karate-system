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

from datetime import datetime, date

from functools import wraps

from werkzeug.utils import secure_filename

from werkzeug.security import (
    check_password_hash,
    generate_password_hash
)

from reportlab.pdfgen import canvas


# =====================================
# APP
# =====================================

app = Flask(__name__)

@app.context_processor
def inject_data():

    return {

        'current_date': datetime.now().strftime('%d/%m/%Y')

    }

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

            flash(
                'Acesso permitido apenas para administradores.',
                'danger'
            )

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

    ultimos_alunos = Aluno.query.order_by(
        Aluno.id.desc()
    ).limit(5).all()

    pendencias = Mensalidade.query.filter_by(
        status='PENDENTE'
    ).order_by(
        Mensalidade.vencimento.asc()
    ).limit(5).all()

    return render_template(
        'index.html',
        total_alunos=total_alunos,
        faturamento=faturamento,
        inadimplentes=inadimplentes,
        aptos=aptos,
        ultimos_alunos=ultimos_alunos,
        pendencias=pendencias
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

            flash(
                'Login realizado com sucesso.',
                'success'
            )

            return redirect('/')

        flash(
            'Usuário ou senha inválidos.',
            'danger'
        )

    return render_template('login.html')


# =====================================
# LOGOUT
# =====================================

@app.route('/logout')
def logout():

    session.clear()

    flash(
        'Logout realizado com sucesso.',
        'info'
    )

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

        foto = request.files.get('foto')

        nome_arquivo = ''

        if foto and foto.filename != '':

            extensoes_permitidas = [
                '.png',
                '.jpg',
                '.jpeg',
                '.webp'
            ]

            extensao = os.path.splitext(
                foto.filename
            )[1].lower()

            if extensao not in extensoes_permitidas:

                flash(
                    'Formato de imagem inválido.',
                    'danger'
                )

                return redirect(request.url)

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

        flash(
            'Aluno cadastrado com sucesso.',
            'success'
        )

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

        foto = request.files.get('foto')

        if foto and foto.filename != '':

            extensoes_permitidas = [
                '.png',
                '.jpg',
                '.jpeg',
                '.webp'
            ]

            extensao = os.path.splitext(
                foto.filename
            )[1].lower()

            if extensao not in extensoes_permitidas:

                flash(
                    'Formato de imagem inválido.',
                    'danger'
                )

                return redirect(request.url)

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

        flash(
            'Aluno atualizado com sucesso.',
            'success'
        )

        return redirect('/alunos')

    return render_template(
        'editar_aluno.html',
        aluno=aluno
    )


# =====================================
# PERFIL DO ALUNO
# =====================================

@app.route('/aluno/<int:id>')
@app.route('/perfil_aluno/<int:id>')
@login_obrigatorio
def perfil_aluno(id):

    aluno = Aluno.query.get_or_404(id)

    presencas = Presenca.query.filter_by(
        aluno_id=id
    ).order_by(
        Presenca.data.desc()
    ).all()

    mensalidades = Mensalidade.query.filter_by(
        aluno_id=id
    ).order_by(
        Mensalidade.vencimento.desc()
    ).all()

    exames = Exame.query.filter_by(
        aluno_id=id
    ).order_by(
        Exame.data_exame.desc()
    ).all()

    total = Presenca.query.filter_by(
        aluno_id=id
    ).count()

    presentes = Presenca.query.filter_by(
        aluno_id=id,
        status='PRESENTE'
    ).count()

    percentual = 0

    if total > 0:

        percentual = round(
            (presentes / total) * 100,
            1
        )

    idade = None

    data_nascimento = aluno.nascimento

    if data_nascimento:

        try:

            nascimento = datetime.strptime(
                data_nascimento,
                '%Y-%m-%d'
            ).date()

            hoje = date.today()

            idade = hoje.year - nascimento.year

            if (
                hoje.month,
                hoje.day
            ) < (
                nascimento.month,
                nascimento.day
            ):

                idade -= 1

        except Exception:

            idade = None

    return render_template(
        'perfil_aluno.html',
        aluno=aluno,
        presencas=presencas,
        mensalidades=mensalidades,
        exames=exames,
        percentual=percentual,
        idade=idade
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

    flash(
        'Aluno excluído com sucesso.',
        'success'
    )

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

        flash(
            'Presença registrada com sucesso.',
            'success'
        )

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

        flash(
            'Mensalidade cadastrada com sucesso.',
            'success'
        )

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
    mensalidades=lista,
    hoje=date.today()
    )


# =====================================
# MARCAR MENSALIDADE COMO PAGA
# =====================================

@app.route('/pagar_mensalidade/<int:id>')
@login_obrigatorio
def pagar_mensalidade(id):

    mensalidade = Mensalidade.query.get_or_404(id)

    mensalidade.status = 'PAGO'

    db.session.commit()

    flash(
        'Mensalidade marcada como paga.',
        'success'
    )

    return redirect('/mensalidades')


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

        flash(
            'Exame registrado com sucesso.',
            'success'
        )

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

    c.drawString(
        100,
        540,
        f'Gerado em: {datetime.now().strftime("%d/%m/%Y %H:%M")}'
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

    flash(
        'Backup realizado com sucesso.',
        'success'
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
# USUÁRIOS
# =====================================

@app.route('/usuarios')
@login_obrigatorio
@admin_obrigatorio
def usuarios():

    lista_usuarios = Usuario.query.order_by(
        Usuario.id.desc()
    ).all()

    return render_template(
        'usuarios.html',
        usuarios=lista_usuarios
    )


# =====================================
# CADASTRAR USUÁRIO
# =====================================

@app.route('/cadastrar_usuario', methods=['GET', 'POST'])
@login_obrigatorio
@admin_obrigatorio
def cadastrar_usuario():

    if request.method == 'POST':

        usuario_form = request.form['usuario']
        senha_form = request.form['senha']
        tipo_form = request.form['tipo']

        # VERIFICA DUPLICADO

        existe = Usuario.query.filter_by(
            usuario=usuario_form
        ).first()

        if existe:

            flash('Este usuário já existe.')

            return redirect('/cadastrar_usuario')

        # CRIPTOGRAFA SENHA

        senha_hash = generate_password_hash(
            senha_form
        )

        novo_usuario = Usuario(

            usuario=usuario_form,
            senha=senha_hash,
            tipo=tipo_form
        )

        db.session.add(novo_usuario)

        db.session.commit()

        flash('Usuário cadastrado com sucesso.')

        return redirect('/usuarios')

    return render_template(
        'cadastrar_usuario.html'
    )


# =====================================
# EDITAR USUÁRIO
# =====================================

@app.route('/editar_usuario/<int:id>', methods=['GET', 'POST'])
@login_obrigatorio
@admin_obrigatorio
def editar_usuario(id):

    usuario = Usuario.query.get_or_404(id)

    if request.method == 'POST':

        usuario_form = request.form['usuario']
        tipo_form = request.form['tipo']
        senha_form = request.form['senha']

        # VERIFICA SE JÁ EXISTE OUTRO USUÁRIO

        existe = Usuario.query.filter(
            Usuario.usuario == usuario_form,
            Usuario.id != id
        ).first()

        if existe:

            flash('Já existe outro usuário com este nome.')

            return redirect(f'/editar_usuario/{id}')

        # ATUALIZA DADOS

        usuario.usuario = usuario_form
        usuario.tipo = tipo_form

        # ALTERA SENHA SOMENTE SE PREENCHER

        if senha_form != '':

            usuario.senha = generate_password_hash(
                senha_form
            )

        db.session.commit()

        flash('Usuário atualizado com sucesso.')

        return redirect('/usuarios')

    return render_template(
        'editar_usuario.html',
        usuario=usuario
    )


# =====================================
# EXCLUIR USUÁRIO
# =====================================

@app.route('/excluir_usuario/<int:id>')
@login_obrigatorio
@admin_obrigatorio
def excluir_usuario(id):

    usuario = Usuario.query.get_or_404(id)

    # NÃO PODE EXCLUIR A SI MESMO

    if usuario.usuario == session['usuario']:

        flash('Você não pode excluir sua própria conta.')

        return redirect('/usuarios')

    # VERIFICA QUANTOS ADMINS EXISTEM

    if usuario.tipo == 'admin':

        total_admins = Usuario.query.filter_by(
            tipo='admin'
        ).count()

        if total_admins <= 1:

            flash('O sistema precisa ter pelo menos um administrador.')

            return redirect('/usuarios')

    db.session.delete(usuario)

    db.session.commit()

    flash('Usuário excluído com sucesso.')

    return redirect('/usuarios')


# =====================================
# CRIAR TABELAS
# =====================================

with app.app_context():

    db.create_all()


# =====================================
# INICIAR SERVIDOR
# =====================================

if __name__ == '__main__':

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )