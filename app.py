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

from io import BytesIO

import qrcode

from PIL import (
    Image,
    ImageDraw,
    ImageFont,
    ImageOps
)

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill

from uuid import uuid4

from datetime import datetime, date

from functools import wraps

from werkzeug.utils import secure_filename

from werkzeug.security import (
    check_password_hash,
    generate_password_hash
)

from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

from reportlab.pdfgen import canvas


# =====================================
# GERAR QR CODE DO ALUNO
# =====================================

def gerar_qrcode_aluno(aluno):

    qr_texto = (
        f'AAKC KARATÊ\n'
        f'Aluno: {aluno.nome}\n'
        f'ID: {aluno.id}\n'
        f'Faixa: {aluno.faixa}\n'
        f'WhatsApp: {aluno.whatsapp}\n'
        f'Responsável: {aluno.responsavel}'
    )

    qr = qrcode.QRCode(
        version=1,
        box_size=8,
        border=2
    )

    qr.add_data(qr_texto)
    qr.make(fit=True)

    qr_img = qr.make_image(
        fill_color='black',
        back_color='white'
    ).convert('RGB')

    buffer = BytesIO()

    qr_img.save(
        buffer,
        format='PNG'
    )

    buffer.seek(0)

    return buffer


# =====================================
# DESENHAR TEXTO CENTRALIZADO
# =====================================

def desenhar_texto_centralizado(
    draw,
    texto,
    fonte,
    cor,
    x_centro,
    y
):

    bbox = draw.textbbox(
        (0, 0),
        texto,
        font=fonte
    )

    largura_texto = bbox[2] - bbox[0]

    x = x_centro - (largura_texto / 2)

    draw.text(
        (x, y),
        texto,
        font=fonte,
        fill=cor
    )
    

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
# GERAR NOME FOTO
# =====================================

def gerar_nome_foto(nome_original):

    nome_seguro = secure_filename(nome_original)

    nome_base, extensao = os.path.splitext(nome_seguro)

    codigo_unico = uuid4().hex[:12]

    return f'{nome_base}_{codigo_unico}{extensao}'


# =====================================
# FORMATAR NOME
# =====================================

def formatar_nome(nome):

    nome = str(nome).strip()

    nome = ' '.join(
        nome.split()
    )

    return nome.title()


# =====================================
# LIMPAR WHATSAPP
# =====================================

def limpar_whatsapp(numero):

    numero = ''.join(
        filter(str.isdigit, str(numero))
    )

    if numero.startswith('55') and len(numero) == 13:

        numero = numero[2:]

    return numero


# =====================================
# VALIDAR WHATSAPP
# =====================================

def validar_whatsapp(numero):

    numero = limpar_whatsapp(numero)

    if numero == '':

        return True

    if len(numero) == 10 or len(numero) == 11:

        return True

    return False


# =====================================
# VALIDAR NASCIMENTO
# =====================================

def validar_nascimento(data_nascimento):

    if not data_nascimento:

        return True

    try:

        nascimento = datetime.strptime(
            data_nascimento,
            '%Y-%m-%d'
        ).date()

        hoje = date.today()

        if nascimento > hoje:

            return False

        return True

    except Exception:

        return False


# =====================================
# VALIDAR FAIXA
# =====================================

def validar_faixa(faixa):

    faixas_permitidas = [
        'Branca',
        'Cinza',
        'Amarela',
        'Laranja',
        'Verde',
        'Azul',
        'Roxa',
        'Marrom',
        'Preta'
    ]

    if faixa in faixas_permitidas:

        return True

    return False


# =====================================
# VALIDAR SEXO
# =====================================

def validar_sexo(sexo):

    sexos_permitidos = [
        'Masculino',
        'Feminino'
    ]

    if sexo in sexos_permitidos:

        return True

    return False


# =====================================
# VALIDAR STATUS MENSALIDADE
# =====================================

def validar_status_mensalidade(status):

    status_permitidos = [
        'PAGO',
        'PENDENTE'
    ]

    if status in status_permitidos:

        return True

    return False


# =====================================
# VALIDAR STATUS PRESENÇA
# =====================================

def validar_status_presenca(status):

    status_permitidos = [
        'PRESENTE',
        'FALTA'
    ]

    if status in status_permitidos:

        return True

    return False


# =====================================
# VALIDAR RESULTADO EXAME
# =====================================

def validar_resultado_exame(resultado):

    resultados_permitidos = [
        'APROVADO',
        'REPROVADO'
    ]

    if resultado in resultados_permitidos:

        return True

    return False


# =====================================
# VALIDAR DATA EXAME
# =====================================

def validar_data_exame(data_exame):

    if not data_exame:

        return False

    try:

        data_convertida = datetime.strptime(
            data_exame,
            '%Y-%m-%d'
        ).date()

        hoje = date.today()

        if data_convertida > hoje:

            return False

        return True

    except Exception:

        return False


# =====================================
# VALIDAR DATA VENCIMENTO
# =====================================

def validar_data_vencimento(data_vencimento):

    if not data_vencimento:

        return False

    try:

        datetime.strptime(
            data_vencimento,
            '%Y-%m-%d'
        ).date()

        return True

    except Exception:

        return False


# =====================================
# BUSCAR ALUNO VÁLIDO
# =====================================

def buscar_aluno_valido(aluno_id):

    try:

        aluno_id = int(aluno_id)

    except Exception:

        return None

    aluno = Aluno.query.get(aluno_id)

    return aluno


# =====================================
# VALIDAR DATA PRESENÇA
# =====================================

def validar_data_presenca(data_presenca):

    if not data_presenca:

        return False

    try:

        data_convertida = datetime.strptime(
            data_presenca,
            '%Y-%m-%d'
        ).date()

        hoje = date.today()

        if data_convertida > hoje:

            return False

        return True

    except Exception:

        return False
    

# =====================================
# VALIDAR TIPO DE USUÁRIO
# =====================================

def validar_tipo_usuario(tipo):

    tipos_permitidos = [
        'admin',
        'professor'
    ]

    if tipo in tipos_permitidos:

        return True

    return False


# =====================================
# VALIDAR SENHA
# =====================================

def validar_senha(senha):

    senha = str(senha).strip()

    if len(senha) < 4:

        return False

    return True


# =====================================
# CALCULAR IDADE
# =====================================

def calcular_idade(data_nascimento):

    if not data_nascimento:

        return None

    try:

        nascimento = datetime.strptime(
            str(data_nascimento),
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

        return idade

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

    faturamento = float(faturamento)

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

    hoje = date.today()

    aniversariantes_mes = 0
    aniversariantes_hoje = 0

    for aluno in alunos:

        if not aluno.nascimento:

            continue

        try:

            nascimento = datetime.strptime(
                aluno.nascimento,
                '%Y-%m-%d'
            ).date()

            if nascimento.month == hoje.month:

                aniversariantes_mes += 1

                if nascimento.day == hoje.day:

                    aniversariantes_hoje += 1

        except Exception:

            continue

    return render_template(
        'index.html',
        total_alunos=total_alunos,
        faturamento=faturamento,
        inadimplentes=inadimplentes,
        aptos=aptos,
        ultimos_alunos=ultimos_alunos,
        pendencias=pendencias,
        aniversariantes_mes=aniversariantes_mes,
        aniversariantes_hoje=aniversariantes_hoje
    )


# =====================================
# LOGIN
# =====================================

@app.route('/login', methods=['GET', 'POST'])
def login():

    if 'usuario' in session:

        return redirect('/')

    if request.method == 'POST':

        usuario_form = request.form['usuario'].strip()
        senha_form = request.form['senha'].strip()

        if usuario_form == '' or senha_form == '':

            flash(
                'Informe usuário e senha.',
                'warning'
            )

            return redirect('/login')

        usuario = Usuario.query.filter_by(
            usuario=usuario_form
        ).first()

        if usuario and check_password_hash(
            usuario.senha,
            senha_form
        ):

            session['usuario_id'] = usuario.id
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

    return render_template(
        'login.html'
    )


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

        busca = busca.strip()

        lista_alunos = Aluno.query.filter(
            Aluno.nome.ilike(f'%{busca}%')
        ).order_by(
            Aluno.nome.asc()
        ).all()

    else:

        lista_alunos = Aluno.query.order_by(
            Aluno.nome.asc()
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

        nome = formatar_nome(
            request.form['nome']
        )

        nascimento = request.form['nascimento']

        if not validar_nascimento(nascimento):

            flash(
                'Informe uma data de nascimento válida. A data não pode ser futura.',
                'warning'
            )

            return redirect(request.url)

        aluno_existente = Aluno.query.filter(
            Aluno.nome == nome,
            Aluno.nascimento == nascimento
        ).first()

        if aluno_existente:

            flash(
                'Já existe um aluno cadastrado com este nome e esta data de nascimento.',
                'warning'
            )

            return redirect(request.url)

        sexo = request.form['sexo']

        if not validar_sexo(sexo):

            flash(
                'Selecione um sexo válido para o aluno.',
                'warning'
            )

            return redirect(request.url)

        responsavel = formatar_nome(
            request.form['responsavel']
        )

        whatsapp = limpar_whatsapp(
            request.form['whatsapp']
        )

        if not validar_whatsapp(whatsapp):

            flash(
                'Informe um WhatsApp válido com DDD. Exemplo: 88999998888.',
                'warning'
            )

            return redirect(request.url)

        faixa = request.form['faixa']

        if not validar_faixa(faixa):

            flash(
                'Selecione uma faixa válida para o aluno.',
                'warning'
            )

            return redirect(request.url)

        mensalidade_convertida = converter_mensalidade(
            request.form['mensalidade']
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
                    'Formato de imagem inválido. Use PNG, JPG, JPEG ou WEBP.',
                    'danger'
                )

                return redirect(request.url)

            nome_arquivo = gerar_nome_foto(
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

        nome_form = formatar_nome(
            request.form['nome']
        )

        nascimento_form = request.form['nascimento']

        if not validar_nascimento(nascimento_form):

            flash(
                'Informe uma data de nascimento válida. A data não pode ser futura.',
                'warning'
            )

            return redirect(request.url)

        aluno_existente = Aluno.query.filter(
            Aluno.nome == nome_form,
            Aluno.nascimento == nascimento_form,
            Aluno.id != id
        ).first()

        if aluno_existente:

            flash(
                'Já existe outro aluno cadastrado com este nome e esta data de nascimento.',
                'warning'
            )

            return redirect(request.url)

        sexo_form = request.form['sexo']

        if not validar_sexo(sexo_form):

            flash(
                'Selecione um sexo válido para o aluno.',
                'warning'
            )

            return redirect(request.url)

        faixa_form = request.form['faixa']

        if not validar_faixa(faixa_form):

            flash(
                'Selecione uma faixa válida para o aluno.',
                'warning'
            )

            return redirect(request.url)

        whatsapp_form = limpar_whatsapp(
            request.form['whatsapp']
        )

        if not validar_whatsapp(whatsapp_form):

            flash(
                'Informe um WhatsApp válido com DDD. Exemplo: 88999998888.',
                'warning'
            )

            return redirect(request.url)

        mensalidade_convertida = converter_mensalidade(
            request.form['mensalidade']
        )

        if mensalidade_convertida is None:

            flash(
                'Informe uma mensalidade válida. Use valores como 80, 80.00 ou 80,00.',
                'warning'
            )

            return redirect(request.url)

        aluno.nome = nome_form
        aluno.nascimento = nascimento_form
        aluno.sexo = sexo_form
        aluno.responsavel = formatar_nome(
            request.form['responsavel']
        )
        aluno.whatsapp = whatsapp_form
        aluno.faixa = faixa_form
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
                    'Formato de imagem inválido. Use PNG, JPG, JPEG ou WEBP.',
                    'danger'
                )

                return redirect(request.url)

            nome_arquivo = gerar_nome_foto(
                foto.filename
            )

            if not os.path.exists('static/uploads'):

                os.makedirs('static/uploads')

            caminho = os.path.join(
                'static/uploads',
                nome_arquivo
            )

            foto.save(caminho)

            if aluno.foto:

                caminho_foto_antiga = os.path.join(
                    'static/uploads',
                    aluno.foto
                )

                if os.path.exists(caminho_foto_antiga):

                    os.remove(caminho_foto_antiga)

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
# CARTEIRINHA DO ALUNO PDF
# =====================================

@app.route('/carteirinha/<int:id>')
@login_obrigatorio
def carteirinha_aluno(id):

    aluno = Aluno.query.get_or_404(id)

    idade = calcular_idade(
        aluno.nascimento
    )

    base_path = 'static/modelos/carteirinha_base.png'

    if not os.path.exists(base_path):

        flash(
            'Modelo da carteirinha não encontrado em static/modelos/carteirinha_base.png',
            'danger'
        )

        return redirect(f'/aluno/{id}')

    if not os.path.exists('carteirinhas'):

        os.makedirs('carteirinhas')

    nome_arquivo = f'carteirinhas/carteirinha_{aluno.id}.pdf'

    largura_pdf = 297 * mm
    altura_pdf = 210 * mm

    c = canvas.Canvas(
        nome_arquivo,
        pagesize=(largura_pdf, altura_pdf)
    )

    cor_vermelha = colors.HexColor('#e30613')
    cor_branca = colors.white
    cor_preta = colors.black

    # =====================================
    # FUNDO COM O MOCKUP
    # =====================================

    c.drawImage(
        base_path,
        0,
        0,
        width=largura_pdf,
        height=altura_pdf,
        preserveAspectRatio=True,
        mask='auto'
    )

    # =====================================
    # ESCALA DE CONVERSÃO
    # imagem original: 1448 x 1086 px
    # PDF: 297 x 210 mm
    # =====================================

    escala_x = largura_pdf / 1448
    escala_y = altura_pdf / 1086

    def px_x(valor):

        return valor * escala_x

    def px_y(valor):

        return altura_pdf - (valor * escala_y)

    def escrever(texto, x, y, tamanho=10, cor=cor_branca, negrito=False):

        c.setFillColor(cor)

        if negrito:

            c.setFont(
                'Helvetica-Bold',
                tamanho
            )

        else:

            c.setFont(
                'Helvetica',
                tamanho
            )

        c.drawString(
            px_x(x),
            px_y(y),
            str(texto)
        )

    def limitar_texto(texto, limite):

        texto = str(texto or '')

        if len(texto) > limite:

            return texto[:limite] + '...'

        return texto

    # =====================================
    # DADOS DA FRENTE
    # =====================================

    nome_aluno = limitar_texto(
        aluno.nome or 'Não informado',
        26
    )

    faixa = limitar_texto(
        aluno.faixa or 'Não informado',
        22
    )

    responsavel = limitar_texto(
        aluno.responsavel or 'Não informado',
        24
    )

    nascimento = formatar_data(
        aluno.nascimento
    )

    whatsapp = formatar_whatsapp(
        aluno.whatsapp
    )

    matricula = f'AAKC-{aluno.id:06d}'

    validade = '31/12/' + str(date.today().year)

    # Nome
    escrever(
        nome_aluno,
        198,
        404,
        tamanho=10.5,
        cor=cor_branca
    )

    # Faixa
    escrever(
        faixa,
        198,
        499,
        tamanho=10.5,
        cor=cor_branca
    )

    # Responsável
    escrever(
        responsavel,
        198,
        594,
        tamanho=10.5,
        cor=cor_branca
    )

    # Nascimento
    escrever(
        nascimento,
        198,
        688,
        tamanho=10.5,
        cor=cor_branca
    )

    # WhatsApp
    escrever(
        whatsapp,
        198,
        783,
        tamanho=10.5,
        cor=cor_branca
    )

    # Matrícula
    escrever(
        matricula,
        198,
        877,
        tamanho=10.5,
        cor=cor_branca
    )

    # Validade
    escrever(
        validade,
        198,
        970,
        tamanho=10.5,
        cor=cor_branca
    )

    # =====================================
    # FOTO DO ALUNO
    # =====================================

    if aluno.foto:

        caminho_foto = os.path.join(
            'static',
            'uploads',
            aluno.foto
        )

        if os.path.exists(caminho_foto):

            try:

                c.drawImage(
                    caminho_foto,
                    px_x(440),
                    px_y(830),
                    width=px_x(220),
                    height=px_y(554) - px_y(830),
                    preserveAspectRatio=True,
                    mask='auto'
                )

            except Exception:

                pass

    # =====================================
    # QR CODE NO VERSO
    # =====================================

    qr_buffer = gerar_qrcode_aluno(
        aluno
    )

    qr_reader = ImageReader(
        qr_buffer
    )

    c.drawImage(
        qr_reader,
        px_x(1132),
        px_y(505),
        width=px_x(165),
        height=px_x(165)
    )

    # =====================================
    # CONTATO / VALIDAÇÃO NO VERSO
    # =====================================

    escrever(
        f'Aluno: {limitar_texto(aluno.nome, 28)}',
        795,
        930,
        tamanho=7,
        cor=cor_branca
    )

    escrever(
        f'ID: {aluno.id}',
        795,
        960,
        tamanho=7,
        cor=cor_branca
    )

    escrever(
        f'Faixa: {aluno.faixa or "Não informado"}',
        795,
        990,
        tamanho=7,
        cor=cor_branca
    )

    c.save()

    return send_file(
        nome_arquivo,
        as_attachment=True
    )


# =====================================
# ANIVERSARIANTES
# =====================================

@app.route('/aniversariantes')
@login_obrigatorio
def aniversariantes():

    hoje = date.today()

    alunos = Aluno.query.order_by(
        Aluno.nome.asc()
    ).all()

    aniversariantes_mes = []
    aniversariantes_hoje = []

    for aluno in alunos:

        if not aluno.nascimento:

            continue

        try:

            nascimento = datetime.strptime(
                aluno.nascimento,
                '%Y-%m-%d'
            ).date()

            idade_atual = calcular_idade(
                aluno.nascimento
            )

            idade_nova = hoje.year - nascimento.year

            if nascimento.month == hoje.month:

                dados_aluno = {

                    'id': aluno.id,
                    'nome': aluno.nome,
                    'nascimento': aluno.nascimento,
                    'dia': nascimento.day,
                    'idade_atual': idade_atual,
                    'idade_nova': idade_nova,
                    'whatsapp': aluno.whatsapp,
                    'faixa': aluno.faixa
                }

                aniversariantes_mes.append(
                    dados_aluno
                )

                if nascimento.day == hoje.day:

                    aniversariantes_hoje.append(
                        dados_aluno
                    )

        except Exception:

            continue

    aniversariantes_mes = sorted(
        aniversariantes_mes,
        key=lambda aluno: aluno['dia']
    )

    total_mes = len(
        aniversariantes_mes
    )

    total_hoje = len(
        aniversariantes_hoje
    )

    return render_template(
        'aniversariantes.html',
        aniversariantes_mes=aniversariantes_mes,
        aniversariantes_hoje=aniversariantes_hoje,
        total_mes=total_mes,
        total_hoje=total_hoje,
        hoje=hoje
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

        aluno = buscar_aluno_valido(
            request.form['aluno_id']
        )

        if not aluno:

            flash(
                'Aluno inválido. Selecione um aluno cadastrado.',
                'warning'
            )

            return redirect('/presencas')

        data_form = request.form['data']

        if not validar_data_presenca(data_form):

            flash(
                'Informe uma data de presença válida. A data não pode ser futura.',
                'warning'
            )

            return redirect('/presencas')

        status_form = request.form['status']

        if not validar_status_presenca(status_form):

            flash(
                'Status de presença inválido.',
                'warning'
            )

            return redirect('/presencas')

        presenca_existente = Presenca.query.filter_by(
            aluno_id=aluno.id,
            data=data_form
        ).first()

        if presenca_existente:

            flash(
                'Este aluno já possui presença registrada nesta data.',
                'warning'
            )

            return redirect('/presencas')

        nova_presenca = Presenca(

            aluno_id=aluno.id,
            data=data_form,
            status=status_form
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

        aluno = buscar_aluno_valido(
            request.form['aluno_id']
        )

        if not aluno:

            flash(
                'Aluno inválido. Selecione um aluno cadastrado.',
                'warning'
            )

            return redirect(request.url)

        data_form = request.form['data']

        if not validar_data_presenca(data_form):

            flash(
                'Informe uma data de presença válida. A data não pode ser futura.',
                'warning'
            )

            return redirect(request.url)

        status_form = request.form['status']

        if not validar_status_presenca(status_form):

            flash(
                'Status de presença inválido.',
                'warning'
            )

            return redirect(request.url)

        presenca_existente = Presenca.query.filter(
            Presenca.aluno_id == aluno.id,
            Presenca.data == data_form,
            Presenca.id != id
        ).first()

        if presenca_existente:

            flash(
                'Já existe outro registro de presença para este aluno nesta data.',
                'warning'
            )

            return redirect(f'/editar_presenca/{id}')

        presenca.aluno_id = aluno.id
        presenca.data = data_form
        presenca.status = status_form

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

    hoje = date.today()

    mes = request.args.get('mes')
    ano = request.args.get('ano')

    if not mes:

        mes = str(hoje.month).zfill(2)

    if not ano:

        ano = str(hoje.year)

    filtro = request.args.get(
        'filtro',
        'todas'
    )

    prefixo_data = f'{ano}-{mes}'

    if request.method == 'POST':

        aluno = buscar_aluno_valido(
            request.form['aluno_id']
        )

        if not aluno:

            flash(
                'Aluno inválido. Selecione um aluno cadastrado.',
                'warning'
            )

            return redirect(
                f'/mensalidades?mes={mes}&ano={ano}&filtro={filtro}'
            )

        valor_form = converter_mensalidade(
            request.form['valor']
        )

        if valor_form is None:

            flash(
                'Informe um valor de mensalidade válido. Use valores como 80, 80.00 ou 80,00.',
                'warning'
            )

            return redirect(
                f'/mensalidades?mes={mes}&ano={ano}&filtro={filtro}'
            )

        vencimento_form = request.form['vencimento']

        if not validar_data_vencimento(vencimento_form):

            flash(
                'Informe uma data de vencimento válida.',
                'warning'
            )

            return redirect(
                f'/mensalidades?mes={mes}&ano={ano}&filtro={filtro}'
            )

        status_form = request.form['status']

        if not validar_status_mensalidade(status_form):

            flash(
                'Status de mensalidade inválido.',
                'warning'
            )

            return redirect(
                f'/mensalidades?mes={mes}&ano={ano}&filtro={filtro}'
            )

        mensalidade_existente = Mensalidade.query.filter_by(
            aluno_id=aluno.id,
            vencimento=vencimento_form
        ).first()

        if mensalidade_existente:

            flash(
                'Este aluno já possui mensalidade cadastrada para este vencimento.',
                'warning'
            )

            return redirect(
                f'/mensalidades?mes={mes}&ano={ano}&filtro={filtro}'
            )

        nova_mensalidade = Mensalidade(

            aluno_id=aluno.id,
            valor=valor_form,
            vencimento=vencimento_form,
            status=status_form
        )

        db.session.add(nova_mensalidade)

        db.session.commit()

        flash(
            'Mensalidade cadastrada com sucesso.',
            'success'
        )

        mes_novo = vencimento_form[5:7]
        ano_novo = vencimento_form[0:4]

        return redirect(
            f'/mensalidades?mes={mes_novo}&ano={ano_novo}&filtro=todas'
        )

    alunos = Aluno.query.order_by(
        Aluno.nome.asc()
    ).all()

    hoje_str = hoje.strftime('%Y-%m-%d')

    query = Mensalidade.query.filter(
        Mensalidade.vencimento.like(f'{prefixo_data}%')
    )

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
        Mensalidade.vencimento.asc()
    ).all()

    todas_do_mes = Mensalidade.query.filter(
        Mensalidade.vencimento.like(f'{prefixo_data}%')
    ).all()

    total_registros = len(
        todas_do_mes
    )

    total_pagos = 0
    total_pendentes = 0

    recebido = 0
    pendente = 0

    for mensalidade in todas_do_mes:

        valor = mensalidade.valor or 0

        if mensalidade.status == 'PAGO':

            total_pagos += 1

            recebido += float(
                valor
            )

        elif mensalidade.status == 'PENDENTE':

            total_pendentes += 1

            pendente += float(
                valor
            )

    total_geral = recebido + pendente

    percentual_recebido = 0
    percentual_pendente = 0

    if total_geral > 0:

        percentual_recebido = round(
            (recebido / total_geral) * 100,
            1
        )

        percentual_pendente = round(
            (pendente / total_geral) * 100,
            1
        )

    meses = [
        ('01', 'Janeiro'),
        ('02', 'Fevereiro'),
        ('03', 'Março'),
        ('04', 'Abril'),
        ('05', 'Maio'),
        ('06', 'Junho'),
        ('07', 'Julho'),
        ('08', 'Agosto'),
        ('09', 'Setembro'),
        ('10', 'Outubro'),
        ('11', 'Novembro'),
        ('12', 'Dezembro')
    ]

    anos = []

    ano_atual = hoje.year

    for item in range(ano_atual - 3, ano_atual + 2):

        anos.append(
            str(item)
        )

    nome_mes = ''

    for numero_mes, nome in meses:

        if numero_mes == mes:

            nome_mes = nome

    vencimento_padrao = f'{ano}-{mes}-10'

    return render_template(
        'mensalidades.html',
        alunos=alunos,
        mensalidades=lista,
        hoje=hoje,
        filtro=filtro,
        total_registros=total_registros,
        total_pagos=total_pagos,
        total_pendentes=total_pendentes,
        recebido=recebido,
        pendente=pendente,
        total_geral=total_geral,
        percentual_recebido=percentual_recebido,
        percentual_pendente=percentual_pendente,
        mes=mes,
        ano=ano,
        meses=meses,
        anos=anos,
        nome_mes=nome_mes,
        vencimento_padrao=vencimento_padrao
    )


# =====================================
# EXPORTAR MENSALIDADES EXCEL
# =====================================

@app.route('/exportar_mensalidades_excel')
@login_obrigatorio
def exportar_mensalidades_excel():

    hoje = date.today()

    mes = request.args.get('mes')
    ano = request.args.get('ano')
    filtro = request.args.get('filtro', 'todas')

    if not mes:

        mes = str(hoje.month).zfill(2)

    if not ano:

        ano = str(hoje.year)

    prefixo_data = f'{ano}-{mes}'

    hoje_str = hoje.strftime('%Y-%m-%d')

    query = Mensalidade.query.filter(
        Mensalidade.vencimento.like(f'{prefixo_data}%')
    )

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

    mensalidades = query.order_by(
        Mensalidade.vencimento.asc()
    ).all()

    meses = {
        '01': 'Janeiro',
        '02': 'Fevereiro',
        '03': 'Março',
        '04': 'Abril',
        '05': 'Maio',
        '06': 'Junho',
        '07': 'Julho',
        '08': 'Agosto',
        '09': 'Setembro',
        '10': 'Outubro',
        '11': 'Novembro',
        '12': 'Dezembro'
    }

    nome_mes = meses.get(
        mes,
        mes
    )

    wb = Workbook()

    ws = wb.active

    ws.title = 'Mensalidades'

    ws.merge_cells('A1:E1')

    ws['A1'] = f'Mensalidades - {nome_mes} / {ano}'

    ws['A1'].font = Font(
        bold=True,
        size=16,
        color='FFFFFF'
    )

    ws['A1'].alignment = Alignment(
        horizontal='center'
    )

    ws['A1'].fill = PatternFill(
        start_color='0F172A',
        end_color='0F172A',
        fill_type='solid'
    )

    cabecalhos = [
        'Aluno',
        'Valor',
        'Vencimento',
        'Status',
        'WhatsApp'
    ]

    ws.append([])

    ws.append(cabecalhos)

    for celula in ws[3]:

        celula.font = Font(
            bold=True,
            color='FFFFFF'
        )

        celula.fill = PatternFill(
            start_color='DC3545',
            end_color='DC3545',
            fill_type='solid'
        )

        celula.alignment = Alignment(
            horizontal='center'
        )

    total = 0
    recebido = 0
    pendente = 0

    for mensalidade in mensalidades:

        valor = mensalidade.valor or 0

        total += float(valor)

        if mensalidade.status == 'PAGO':

            recebido += float(valor)

        elif mensalidade.status == 'PENDENTE':

            pendente += float(valor)

        nome_aluno = 'Sem aluno'

        whatsapp = ''

        if mensalidade.aluno:

            nome_aluno = mensalidade.aluno.nome
            whatsapp = mensalidade.aluno.whatsapp or ''

        ws.append([
            nome_aluno,
            float(valor),
            formatar_data(mensalidade.vencimento),
            mensalidade.status,
            whatsapp
        ])

    linha_resumo = ws.max_row + 2

    ws[f'A{linha_resumo}'] = 'Resumo'
    ws[f'A{linha_resumo}'].font = Font(
        bold=True,
        size=13
    )

    ws[f'A{linha_resumo + 1}'] = 'Total'
    ws[f'B{linha_resumo + 1}'] = total

    ws[f'A{linha_resumo + 2}'] = 'Recebido'
    ws[f'B{linha_resumo + 2}'] = recebido

    ws[f'A{linha_resumo + 3}'] = 'Pendente'
    ws[f'B{linha_resumo + 3}'] = pendente

    for linha in range(4, ws.max_row + 1):

        ws[f'B{linha}'].number_format = 'R$ #,##0.00'

    ws.column_dimensions['A'].width = 35
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 18
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 18

    for row in ws.iter_rows():

        for cell in row:

            cell.alignment = Alignment(
                vertical='center'
            )

    arquivo = BytesIO()

    wb.save(arquivo)

    arquivo.seek(0)

    nome_arquivo = f'mensalidades_{ano}_{mes}_{filtro}.xlsx'

    return send_file(
        arquivo,
        as_attachment=True,
        download_name=nome_arquivo,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


# =====================================
# GERAR MENSALIDADES AUTOMÁTICAS
# =====================================

@app.route('/gerar_mensalidades', methods=['POST'])
@login_obrigatorio
@admin_obrigatorio
def gerar_mensalidades():

    vencimento = request.form['vencimento']

    if not validar_data_vencimento(vencimento):

        flash(
            'Informe uma data de vencimento válida.',
            'warning'
        )

        return redirect('/mensalidades')

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

        valor_aluno = converter_mensalidade(
            aluno.mensalidade
        )

        if valor_aluno is None:

            valor_aluno = 0

        nova_mensalidade = Mensalidade(

            aluno_id=aluno.id,
            valor=valor_aluno,
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

    mes = vencimento[5:7]
    ano = vencimento[0:4]

    return redirect(
        f'/mensalidades?mes={mes}&ano={ano}&filtro=todas'
    )


# =====================================
# EDITAR MENSALIDADE
# =====================================

@app.route('/editar_mensalidade/<int:id>', methods=['GET', 'POST'])
@login_obrigatorio
def editar_mensalidade(id):

    mes = request.args.get('mes')
    ano = request.args.get('ano')
    filtro = request.args.get('filtro', 'todas')

    if mes and ano:

        retorno = f'/mensalidades?mes={mes}&ano={ano}&filtro={filtro}'

    else:

        retorno = '/mensalidades'

    mensalidade = Mensalidade.query.get_or_404(id)

    if mensalidade.status == 'PAGO':

        flash(
            'Mensalidade já paga não pode ser editada para preservar o histórico financeiro.',
            'warning'
        )

        return redirect(retorno)

    if request.method == 'POST':

        aluno = buscar_aluno_valido(
            request.form['aluno_id']
        )

        if not aluno:

            flash(
                'Aluno inválido. Selecione um aluno cadastrado.',
                'warning'
            )

            return redirect(request.url)

        valor_form = converter_mensalidade(
            request.form['valor']
        )

        if valor_form is None:

            flash(
                'Informe um valor de mensalidade válido. Use valores como 80, 80.00 ou 80,00.',
                'warning'
            )

            return redirect(request.url)

        vencimento_form = request.form['vencimento']

        if not validar_data_vencimento(vencimento_form):

            flash(
                'Informe uma data de vencimento válida.',
                'warning'
            )

            return redirect(request.url)

        status_form = request.form['status']

        if not validar_status_mensalidade(status_form):

            flash(
                'Status de mensalidade inválido.',
                'warning'
            )

            return redirect(request.url)

        mensalidade_existente = Mensalidade.query.filter(
            Mensalidade.aluno_id == aluno.id,
            Mensalidade.vencimento == vencimento_form,
            Mensalidade.id != id
        ).first()

        if mensalidade_existente:

            flash(
                'Já existe outra mensalidade para este aluno com este vencimento.',
                'warning'
            )

            return redirect(request.url)

        mensalidade.aluno_id = aluno.id
        mensalidade.valor = valor_form
        mensalidade.vencimento = vencimento_form
        mensalidade.status = status_form

        db.session.commit()

        flash(
            'Mensalidade atualizada com sucesso.',
            'success'
        )

        mes_novo = vencimento_form[5:7]
        ano_novo = vencimento_form[0:4]

        return redirect(
            f'/mensalidades?mes={mes_novo}&ano={ano_novo}&filtro=todas'
        )

    alunos = Aluno.query.order_by(
        Aluno.nome.asc()
    ).all()

    return render_template(
        'editar_mensalidade.html',
        mensalidade=mensalidade,
        alunos=alunos,
        mes=mes,
        ano=ano,
        filtro=filtro
    )


# =====================================
# EXCLUIR MENSALIDADE
# =====================================

@app.route('/excluir_mensalidade/<int:id>')
@login_obrigatorio
@admin_obrigatorio
def excluir_mensalidade(id):

    mes = request.args.get('mes')
    ano = request.args.get('ano')
    filtro = request.args.get('filtro', 'todas')

    if mes and ano:

        retorno = f'/mensalidades?mes={mes}&ano={ano}&filtro={filtro}'

    else:

        retorno = '/mensalidades'

    mensalidade = Mensalidade.query.get_or_404(id)

    if mensalidade.status == 'PAGO':

        flash(
            'Não é possível excluir uma mensalidade já paga. Para manter o histórico financeiro, edite o registro se necessário.',
            'warning'
        )

        return redirect(retorno)

    db.session.delete(mensalidade)

    db.session.commit()

    flash(
        'Mensalidade excluída com sucesso.',
        'success'
    )

    return redirect(retorno)


# =====================================
# MARCAR MENSALIDADE COMO PAGA
# =====================================

@app.route('/pagar_mensalidade/<int:id>')
@login_obrigatorio
def pagar_mensalidade(id):

    mes = request.args.get('mes')
    ano = request.args.get('ano')
    filtro = request.args.get('filtro', 'todas')

    if mes and ano:

        retorno = f'/mensalidades?mes={mes}&ano={ano}&filtro={filtro}'

    else:

        retorno = '/mensalidades'

    mensalidade = Mensalidade.query.get_or_404(id)

    if mensalidade.status == 'PAGO':

        flash(
            'Esta mensalidade já está marcada como paga.',
            'warning'
        )

        return redirect(retorno)

    if mensalidade.status != 'PENDENTE':

        flash(
            'Esta mensalidade possui um status inválido e não pode ser marcada como paga.',
            'warning'
        )

        return redirect(retorno)

    mensalidade.status = 'PAGO'

    db.session.commit()

    flash(
        'Mensalidade marcada como paga.',
        'success'
    )

    return redirect(retorno)


# =====================================
# EXAMES
# =====================================

@app.route('/exames', methods=['GET', 'POST'])
@login_obrigatorio
def exames():

    if request.method == 'POST':

        aluno = buscar_aluno_valido(
            request.form['aluno_id']
        )

        if not aluno:

            flash(
                'Aluno inválido. Selecione um aluno cadastrado.',
                'warning'
            )

            return redirect('/exames')

        faixa_atual_form = request.form['faixa_atual']

        if not validar_faixa(faixa_atual_form):

            flash(
                'Faixa atual inválida.',
                'warning'
            )

            return redirect('/exames')

        nova_faixa_form = request.form['nova_faixa']

        if not validar_faixa(nova_faixa_form):

            flash(
                'Nova faixa inválida.',
                'warning'
            )

            return redirect('/exames')

        data_exame_form = request.form['data_exame']

        if not validar_data_exame(data_exame_form):

            flash(
                'Informe uma data de exame válida. A data não pode ser futura.',
                'warning'
            )

            return redirect('/exames')

        resultado_form = request.form['resultado']

        if not validar_resultado_exame(resultado_form):

            flash(
                'Resultado de exame inválido.',
                'warning'
            )

            return redirect('/exames')

        novo_exame = Exame(

            aluno_id=aluno.id,
            faixa_atual=faixa_atual_form,
            nova_faixa=nova_faixa_form,
            data_exame=data_exame_form,
            resultado=resultado_form
        )

        db.session.add(novo_exame)

        if resultado_form == 'APROVADO':

            aluno.faixa = nova_faixa_form

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

    dados = Mensalidade.query.join(
        Aluno
    ).filter(
        Mensalidade.status == 'PENDENTE'
    ).order_by(
        Mensalidade.vencimento.asc()
    ).all()

    total_pendente = db.session.query(
        db.func.sum(Mensalidade.valor)
    ).join(
        Aluno
    ).filter(
        Mensalidade.status == 'PENDENTE'
    ).scalar()

    if total_pendente is None:

        total_pendente = 0

    vencidas = Mensalidade.query.join(
        Aluno
    ).filter(
        Mensalidade.status == 'PENDENTE',
        Mensalidade.vencimento < hoje_str
    ).count()

    vence_hoje = Mensalidade.query.join(
        Aluno
    ).filter(
        Mensalidade.status == 'PENDENTE',
        Mensalidade.vencimento == hoje_str
    ).count()

    pendentes_futuras = Mensalidade.query.join(
        Aluno
    ).filter(
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

    if mensalidade.status != 'PAGO':

        flash(
            'Só é possível gerar recibo de mensalidades pagas.',
            'warning'
        )

        return redirect('/mensalidades')

    if not mensalidade.aluno:

        flash(
            'Não foi possível gerar o recibo, pois esta mensalidade não possui aluno vinculado.',
            'danger'
        )

        return redirect('/mensalidades')

    if mensalidade.valor is None:

        flash(
            'Não foi possível gerar o recibo, pois esta mensalidade não possui valor informado.',
            'danger'
        )

        return redirect('/mensalidades')

    if not os.path.exists('recibos'):

        os.makedirs('recibos')

    nome_arquivo = f'recibos/recibo_{id}.pdf'

    valor_formatado = f'{float(mensalidade.valor):.2f}'.replace('.', ',')

    vencimento_formatado = formatar_data(
        mensalidade.vencimento
    )

    data_emissao = datetime.now().strftime('%d/%m/%Y')
    data_hora_emissao = datetime.now().strftime('%d/%m/%Y %H:%M')

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
        f"Data: {data_emissao}"
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
        f"Vencimento: {vencimento_formatado}"
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
        f"Emitido em: {data_hora_emissao}"
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

    recebido = float(recebido)

    pendente = db.session.query(
        db.func.sum(Mensalidade.valor)
    ).filter(
        Mensalidade.status == 'PENDENTE'
    ).scalar()

    if pendente is None:

        pendente = 0

    pendente = float(pendente)

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
    ).filter(
        Aluno.faixa != None
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

        usuario_form = request.form['usuario'].strip()
        senha_form = request.form['senha'].strip()
        tipo_form = request.form['tipo']

        if usuario_form == '':

            flash(
                'Informe um nome de usuário.',
                'warning'
            )

            return redirect('/cadastrar_usuario')

        if not validar_senha(senha_form):

            flash(
                'A senha deve ter pelo menos 4 caracteres.',
                'warning'
            )

            return redirect('/cadastrar_usuario')

        if not validar_tipo_usuario(tipo_form):

            flash(
                'Tipo de usuário inválido.',
                'warning'
            )

            return redirect('/cadastrar_usuario')

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

        usuario_form = request.form['usuario'].strip()
        tipo_form = request.form['tipo']
        senha_form = request.form['senha'].strip()

        if usuario_form == '':

            flash(
                'Informe um nome de usuário.',
                'warning'
            )

            return redirect(f'/editar_usuario/{id}')

        if not validar_tipo_usuario(tipo_form):

            flash(
                'Tipo de usuário inválido.',
                'warning'
            )

            return redirect(f'/editar_usuario/{id}')

        if senha_form != '' and not validar_senha(senha_form):

            flash(
                'A nova senha deve ter pelo menos 4 caracteres.',
                'warning'
            )

            return redirect(f'/editar_usuario/{id}')

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

        if usuario.tipo == 'admin' and tipo_form != 'admin':

            total_admins = Usuario.query.filter_by(
                tipo='admin'
            ).count()

            if total_admins <= 1:

                flash(
                    'O sistema precisa ter pelo menos um administrador.',
                    'danger'
                )

                return redirect(f'/editar_usuario/{id}')

        if usuario.usuario == session['usuario'] and usuario.tipo == 'admin' and tipo_form != 'admin':

            flash(
                'Você não pode remover seu próprio acesso de administrador.',
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
# INICIAR SERVIDOR LOCAL
# =====================================

if __name__ == '__main__':

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False
    )