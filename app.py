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
# FORMATAR WHATSAPP
# =====================================

def formatar_whatsapp(numero):

    numero = ''.join(
        filter(str.isdigit, str(numero))
    )

    if len(numero) == 11:

        return f'({numero[:2]}) {numero[2:7]}-{numero[7:]}'

    return numero


# =====================================
# FORMATAR MOEDA
# =====================================

def formatar_moeda(valor):

    try:

        valor = float(valor)

        return f'R$ {valor:.2f}'.replace('.', ',')

    except Exception:

        return 'R$ 0,00'


# =====================================
# FORMATAR DATA
# =====================================

def formatar_data(data):

    if not data:

        return 'Não informado'

    try:

        data_convertida = datetime.strptime(
            str(data),
            '%Y-%m-%d'
        )

        return data_convertida.strftime('%d/%m/%Y')

    except Exception:

        return data


# =====================================
# CONVERTER MENSALIDADE
# =====================================

def converter_mensalidade(valor):

    try:

        valor = str(valor).strip()

        if valor == '':

            return 0

        valor = valor.replace(',', '.')

        valor_convertido = float(valor)

        if valor_convertido < 0:

            return None

        return valor_convertido

    except Exception:

        return None


# =====================================
# APP
# =====================================

app = Flask(__name__)

app.secret_key = os.getenv(
    'SECRET_KEY',
    'karate_secret'
)


@app.context_processor
def inject_data():

    return {

        'current_date': datetime.now().strftime('%d/%m/%Y'),
        'formatar_whatsapp': formatar_whatsapp,
        'formatar_moeda': formatar_moeda,
        'formatar_data': formatar_data

    }


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
        sexo = request.form['sexo']
        responsavel = request.form['responsavel']
        whatsapp = request.form['whatsapp']
        faixa = request.form['faixa']
        mensalidade = request.form['mensalidade']

        mensalidade_convertida = converter_mensalidade(
            mensalidade
        )

        if mensalidade_convertida is None:

            flash(
                'Informe uma mensalidade válida. Use valores como 80, 80.00 ou 80,00.',
                'warning'
            )

            return redirect(request.url)

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
            nascimento=nascimento,
            sexo=sexo,
            responsavel=responsavel,
            whatsapp=whatsapp,
            faixa=faixa,
            mensalidade=mensalidade_convertida,
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

        mensalidade_convertida = converter_mensalidade(
            request.form['mensalidade']
        )

        if mensalidade_convertida is None:

            flash(
                'Informe uma mensalidade válida. Use valores como 80, 80.00 ou 80,00.',
                'warning'
            )

            return redirect(request.url)

        aluno.nome = request.form['nome']
        aluno.nascimento = request.form['nascimento']
        aluno.sexo = request.form['sexo']
        aluno.responsavel = request.form['responsavel']
        aluno.whatsapp = request.form['whatsapp']
        aluno.faixa = request.form['faixa']
        aluno.mensalidade = mensalidade_convertida

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

            if not os.path.exists('static/uploads'):

                os.makedirs('static/uploads')

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

    pendentes = Mensalidade.query.filter_by(
        aluno_id=id,
        status='PENDENTE'
    ).count()

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
        idade=idade,
        pendentes=pendentes
    )


# =====================================
# EXCLUIR ALUNO
# =====================================

@app.route('/excluir_aluno/<int:id>')
@login_obrigatorio
@admin_obrigatorio
def excluir_aluno(id):

    aluno = Aluno.query.get_or_404(id)

    total_presencas = Presenca.query.filter_by(
        aluno_id=aluno.id
    ).count()

    total_mensalidades = Mensalidade.query.filter_by(
        aluno_id=aluno.id
    ).count()

    total_exames = Exame.query.filter_by(
        aluno_id=aluno.id
    ).count()

    if total_presencas > 0 or total_mensalidades > 0 or total_exames > 0:

        flash(
            f'Não é possível excluir este aluno, pois ele possui histórico no sistema: '
            f'{total_presencas} presença(s), '
            f'{total_mensalidades} mensalidade(s) e '
            f'{total_exames} exame(s).',
            'warning'
        )

        return redirect('/alunos')

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

        presenca_existente = Presenca.query.filter_by(
            aluno_id=request.form['aluno_id'],
            data=request.form['data']
        ).first()

        if presenca_existente:

            flash(
                'Este aluno já possui presença registrada nesta data.',
                'warning'
            )

            return redirect('/presencas')

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

    filtro_aluno = request.args.get('aluno_id')
    filtro_data = request.args.get('data')
    filtro_status = request.args.get('status')

    query = Presenca.query

    if filtro_aluno:

        query = query.filter(
            Presenca.aluno_id == filtro_aluno
        )

    if filtro_data:

        query = query.filter(
            Presenca.data == filtro_data
        )

    if filtro_status:

        query = query.filter(
            Presenca.status == filtro_status
        )

    lista_presencas = query.order_by(
        Presenca.data.desc()
    ).all()

    total_registros = Presenca.query.count()

    total_presentes = Presenca.query.filter_by(
        status='PRESENTE'
    ).count()

    total_faltas = Presenca.query.filter_by(
        status='FALTA'
    ).count()

    return render_template(
        'presencas.html',
        alunos=alunos,
        presencas=lista_presencas,
        total_registros=total_registros,
        total_presentes=total_presentes,
        total_faltas=total_faltas,
        filtro_aluno=filtro_aluno,
        filtro_data=filtro_data,
        filtro_status=filtro_status
    )


# =====================================
# EXCLUIR PRESENÇA
# =====================================

@app.route('/excluir_presenca/<int:id>')
@login_obrigatorio
def excluir_presenca(id):

    presenca = Presenca.query.get_or_404(id)

    db.session.delete(presenca)

    db.session.commit()

    flash(
        'Registro de presença excluído com sucesso.',
        'success'
    )

    return redirect('/presencas')


# =====================================
# EDITAR PRESENÇA
# =====================================

@app.route('/editar_presenca/<int:id>', methods=['GET', 'POST'])
@login_obrigatorio
def editar_presenca(id):

    presenca = Presenca.query.get_or_404(id)

    alunos = Aluno.query.order_by(
        Aluno.nome.asc()
    ).all()

    if request.method == 'POST':

        aluno_id_form = request.form['aluno_id']
        data_form = request.form['data']

        presenca_existente = Presenca.query.filter(
            Presenca.aluno_id == aluno_id_form,
            Presenca.data == data_form,
            Presenca.id != id
        ).first()

        if presenca_existente:

            flash(
                'Já existe outro registro de presença para este aluno nesta data.',
                'warning'
            )

            return redirect(f'/editar_presenca/{id}')

        presenca.aluno_id = aluno_id_form
        presenca.data = data_form
        presenca.status = request.form['status']

        db.session.commit()

        flash(
            'Presença atualizada com sucesso.',
            'success'
        )

        return redirect('/presencas')

    return render_template(
        'editar_presenca.html',
        presenca=presenca,
        alunos=alunos
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

            'id': aluno.id,
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

        mensalidade_existente = Mensalidade.query.filter_by(
            aluno_id=request.form['aluno_id'],
            vencimento=request.form['vencimento']
        ).first()

        if mensalidade_existente:

            flash(
                'Este aluno já possui mensalidade cadastrada para este vencimento.',
                'warning'
            )

            return redirect('/mensalidades')

        nova_mensalidade = Mensalidade(

            aluno_id=request.form['aluno_id'],
            valor=float(request.form['valor']),
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

    filtro = request.args.get(
        'filtro',
        'todas'
    )

    hoje = date.today()

    hoje_str = hoje.strftime('%Y-%m-%d')

    query = Mensalidade.query

    if filtro == 'pagas':

        query = query.filter(
            Mensalidade.status == 'PAGO'
        )

    elif filtro == 'pendentes':

        query = query.filter(
            Mensalidade.status == 'PENDENTE'
        )

    elif filtro == 'vencidas':

        query = query.filter(
            Mensalidade.status == 'PENDENTE',
            Mensalidade.vencimento < hoje_str
        )

    elif filtro == 'hoje':

        query = query.filter(
            Mensalidade.status == 'PENDENTE',
            Mensalidade.vencimento == hoje_str
        )

    lista = query.order_by(
        Mensalidade.vencimento.desc()
    ).all()

    total_registros = Mensalidade.query.count()

    total_pagos = Mensalidade.query.filter_by(
        status='PAGO'
    ).count()

    total_pendentes = Mensalidade.query.filter_by(
        status='PENDENTE'
    ).count()

    return render_template(
        'mensalidades.html',
        alunos=alunos,
        mensalidades=lista,
        hoje=hoje,
        filtro=filtro,
        total_registros=total_registros,
        total_pagos=total_pagos,
        total_pendentes=total_pendentes
    )


# =====================================
# GERAR MENSALIDADES AUTOMÁTICAS
# =====================================

@app.route('/gerar_mensalidades', methods=['POST'])
@login_obrigatorio
@admin_obrigatorio
def gerar_mensalidades():

    vencimento = request.form['vencimento']

    alunos = Aluno.query.order_by(
        Aluno.nome.asc()
    ).all()

    criadas = 0
    ignoradas = 0

    for aluno in alunos:

        mensalidade_existente = Mensalidade.query.filter_by(
            aluno_id=aluno.id,
            vencimento=vencimento
        ).first()

        if mensalidade_existente:

            ignoradas += 1

            continue

        nova_mensalidade = Mensalidade(

            aluno_id=aluno.id,
            valor=float(aluno.mensalidade or 0),
            vencimento=vencimento,
            status='PENDENTE'
        )

        db.session.add(nova_mensalidade)

        criadas += 1

    db.session.commit()

    flash(
        f'{criadas} mensalidades geradas. {ignoradas} já existiam para este vencimento.',
        'success'
    )

    return redirect('/mensalidades')


# =====================================
# EDITAR MENSALIDADE
# =====================================

@app.route('/editar_mensalidade/<int:id>', methods=['GET', 'POST'])
@login_obrigatorio
def editar_mensalidade(id):

    mensalidade = Mensalidade.query.get_or_404(id)

    if mensalidade.status == 'PAGO':

        flash(
            'Mensalidade já paga não pode ser editada para preservar o histórico financeiro.',
            'warning'
        )

        return redirect('/mensalidades')

    if request.method == 'POST':

        aluno_id_form = request.form['aluno_id']
        vencimento_form = request.form['vencimento']

        mensalidade_existente = Mensalidade.query.filter(
            Mensalidade.aluno_id == aluno_id_form,
            Mensalidade.vencimento == vencimento_form,
            Mensalidade.id != id
        ).first()

        if mensalidade_existente:

            flash(
                'Já existe outra mensalidade para este aluno com este vencimento.',
                'warning'
            )

            return redirect(f'/editar_mensalidade/{id}')

        mensalidade.aluno_id = aluno_id_form
        mensalidade.valor = float(request.form['valor'])
        mensalidade.vencimento = vencimento_form
        mensalidade.status = request.form['status']

        db.session.commit()

        flash(
            'Mensalidade atualizada com sucesso.',
            'success'
        )

        return redirect('/mensalidades')

    alunos = Aluno.query.order_by(
        Aluno.nome.asc()
    ).all()

    return render_template(
        'editar_mensalidade.html',
        mensalidade=mensalidade,
        alunos=alunos
    )


# =====================================
# EXCLUIR MENSALIDADE
# =====================================

@app.route('/excluir_mensalidade/<int:id>')
@login_obrigatorio
@admin_obrigatorio
def excluir_mensalidade(id):

    mensalidade = Mensalidade.query.get_or_404(id)

    if mensalidade.status == 'PAGO':

        flash(
            'Não é possível excluir uma mensalidade já paga. Para manter o histórico financeiro, edite o registro se necessário.',
            'warning'
        )

        return redirect('/mensalidades')

    db.session.delete(mensalidade)

    db.session.commit()

    flash(
        'Mensalidade excluída com sucesso.',
        'success'
    )

    return redirect('/mensalidades')


# =====================================
# MARCAR MENSALIDADE COMO PAGA
# =====================================

@app.route('/pagar_mensalidade/<int:id>')
@login_obrigatorio
def pagar_mensalidade(id):

    mensalidade = Mensalidade.query.get_or_404(id)

    if mensalidade.status == 'PAGO':

        flash(
            'Esta mensalidade já está marcada como paga.',
            'warning'
        )

        return redirect('/mensalidades')

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

    hoje = date.today()
    hoje_str = hoje.strftime('%Y-%m-%d')

    dados = Mensalidade.query.filter_by(
        status='PENDENTE'
    ).order_by(
        Mensalidade.vencimento.asc()
    ).all()

    total_pendente = db.session.query(
        db.func.sum(Mensalidade.valor)
    ).filter(
        Mensalidade.status == 'PENDENTE'
    ).scalar()

    if total_pendente is None:

        total_pendente = 0

    vencidas = Mensalidade.query.filter(
        Mensalidade.status == 'PENDENTE',
        Mensalidade.vencimento < hoje_str
    ).count()

    vence_hoje = Mensalidade.query.filter(
        Mensalidade.status == 'PENDENTE',
        Mensalidade.vencimento == hoje_str
    ).count()

    pendentes_futuras = Mensalidade.query.filter(
        Mensalidade.status == 'PENDENTE',
        Mensalidade.vencimento > hoje_str
    ).count()

    return render_template(
        'cobrar.html',
        dados=dados,
        hoje=hoje,
        hoje_str=hoje_str,
        total_pendente=total_pendente,
        vencidas=vencidas,
        vence_hoje=vence_hoje,
        pendentes_futuras=pendentes_futuras
    )


# =====================================
# RECIBO PDF
# =====================================

@app.route('/recibo/<int:id>')
@login_obrigatorio
def recibo(id):

    import textwrap

    mensalidade = Mensalidade.query.get_or_404(id)

    if not os.path.exists('recibos'):

        os.makedirs('recibos')

    nome_arquivo = f'recibos/recibo_{id}.pdf'

    valor_formatado = f'{mensalidade.valor:.2f}'.replace('.', ',')

    c = canvas.Canvas(nome_arquivo)

    largura, altura = 595, 842

    # BORDA PRINCIPAL

    c.setLineWidth(2)

    c.rect(
        40,
        40,
        largura - 80,
        altura - 80
    )

    # CABEÇALHO

    c.setFont("Helvetica-Bold", 20)

    c.drawCentredString(
        largura / 2,
        775,
        "RECIBO DE PAGAMENTO"
    )

    c.setFont("Helvetica-Bold", 15)

    c.drawCentredString(
        largura / 2,
        742,
        "Academia de Karatê"
    )

    c.setFont("Helvetica", 10)

    c.drawCentredString(
        largura / 2,
        724,
        "Sistema de Gestão da Academia"
    )

    # LINHA

    c.line(
        70,
        705,
        largura - 70,
        705
    )

    # DADOS DO RECIBO

    c.setFont("Helvetica-Bold", 11)

    c.drawString(
        70,
        675,
        f"Recibo Nº: {mensalidade.id}"
    )

    c.drawString(
        360,
        675,
        f"Data: {datetime.now().strftime('%d/%m/%Y')}"
    )

    # TEXTO PRINCIPAL COM QUEBRA AUTOMÁTICA

    texto = (
        f"Recebemos de {mensalidade.aluno.nome}, "
        f"a importância de R$ {valor_formatado}, "
        f"referente ao pagamento de mensalidade da academia."
    )

    linhas = textwrap.wrap(
        texto,
        width=82
    )

    y = 625

    c.setFont("Helvetica", 11)

    for linha in linhas:

        c.drawString(
            70,
            y,
            linha
        )

        y -= 18

    # CAIXA DOS DADOS

    c.setLineWidth(1)

    c.roundRect(
        70,
        390,
        largura - 140,
        155,
        10
    )

    c.setFont("Helvetica-Bold", 13)

    c.drawString(
        90,
        515,
        "Dados do Pagamento"
    )

    c.setFont("Helvetica", 11)

    c.drawString(
        95,
        485,
        f"Aluno: {mensalidade.aluno.nome}"
    )

    c.drawString(
        95,
        460,
        f"Valor: R$ {valor_formatado}"
    )

    c.drawString(
        95,
        435,
        f"Vencimento: {mensalidade.vencimento}"
    )

    c.drawString(
        95,
        410,
        f"Status: {mensalidade.status}"
    )

    # EMISSÃO

    c.setFont("Helvetica", 10)

    c.drawString(
        70,
        350,
        f"Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )

    # OBSERVAÇÃO

    c.setFont("Helvetica-Oblique", 10)

    c.drawString(
        70,
        320,
        "Este recibo foi gerado automaticamente pelo sistema Karate System."
    )

    # ASSINATURA

    c.line(
        170,
        230,
        425,
        230
    )

    c.setFont("Helvetica", 11)

    c.drawCentredString(
        largura / 2,
        210,
        "Assinatura do responsável"
    )

    # RODAPÉ

    c.setFont("Helvetica", 9)

    c.drawCentredString(
        largura / 2,
        70,
        "Karate System - Gestão de Alunos, Frequência e Mensalidades"
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

    if not os.path.exists(origem):

        flash(
            'Backup disponível apenas quando estiver usando SQLite local.',
            'warning'
        )

        return redirect('/')

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

    total_financeiro = recebido + pendente

    percentual_recebido = 0
    percentual_pendente = 0

    if total_financeiro > 0:

        percentual_recebido = round(
            (recebido / total_financeiro) * 100,
            1
        )

        percentual_pendente = round(
            (pendente / total_financeiro) * 100,
            1
        )

    total_mensalidades = Mensalidade.query.count()

    mensalidades_pagas = Mensalidade.query.filter_by(
        status='PAGO'
    ).count()

    mensalidades_pendentes = Mensalidade.query.filter_by(
        status='PENDENTE'
    ).count()

    faixas = db.session.query(
        Aluno.faixa,
        db.func.count(Aluno.id)
    ).group_by(
        Aluno.faixa
    ).order_by(
        db.func.count(Aluno.id).desc()
    ).all()

    return render_template(
        'relatorios.html',
        total_alunos=total_alunos,
        recebido=recebido,
        pendente=pendente,
        total_financeiro=total_financeiro,
        percentual_recebido=percentual_recebido,
        percentual_pendente=percentual_pendente,
        total_mensalidades=total_mensalidades,
        mensalidades_pagas=mensalidades_pagas,
        mensalidades_pendentes=mensalidades_pendentes,
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

    total_usuarios = Usuario.query.count()

    total_admins = Usuario.query.filter_by(
        tipo='admin'
    ).count()

    total_professores = Usuario.query.filter_by(
        tipo='professor'
    ).count()

    return render_template(
        'usuarios.html',
        usuarios=lista_usuarios,
        total_usuarios=total_usuarios,
        total_admins=total_admins,
        total_professores=total_professores
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

        existe = Usuario.query.filter_by(
            usuario=usuario_form
        ).first()

        if existe:

            flash(
                'Este usuário já existe.',
                'danger'
            )

            return redirect('/cadastrar_usuario')

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

        flash(
            'Usuário cadastrado com sucesso.',
            'success'
        )

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

        existe = Usuario.query.filter(
            Usuario.usuario == usuario_form,
            Usuario.id != id
        ).first()

        if existe:

            flash(
                'Já existe outro usuário com este nome.',
                'danger'
            )

            return redirect(f'/editar_usuario/{id}')

        usuario.usuario = usuario_form
        usuario.tipo = tipo_form

        if senha_form != '':

            usuario.senha = generate_password_hash(
                senha_form
            )

        db.session.commit()

        flash(
            'Usuário atualizado com sucesso.',
            'success'
        )

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

    if usuario.usuario == session['usuario']:

        flash(
            'Você não pode excluir sua própria conta.',
            'danger'
        )

        return redirect('/usuarios')

    if usuario.tipo == 'admin':

        total_admins = Usuario.query.filter_by(
            tipo='admin'
        ).count()

        if total_admins <= 1:

            flash(
                'O sistema precisa ter pelo menos um administrador.',
                'danger'
            )

            return redirect('/usuarios')

    db.session.delete(usuario)

    db.session.commit()

    flash(
        'Usuário excluído com sucesso.',
        'success'
    )

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