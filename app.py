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
    Usuario,
    Professor,
    Turma
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
# FONTE DA CARTEIRINHA
# =====================================

def carregar_fonte(tamanho, negrito=False):

    caminhos = []

    if negrito:

        caminhos = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf',
            'C:/Windows/Fonts/arialbd.ttf'
        ]

    else:

        caminhos = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf',
            'C:/Windows/Fonts/arial.ttf'
        ]

    for caminho in caminhos:

        if os.path.exists(caminho):

            return ImageFont.truetype(
                caminho,
                tamanho
            )

    return ImageFont.load_default()


# =====================================
# AJUSTAR FONTE PELO TAMANHO DO TEXTO
# =====================================

def ajustar_fonte(
    draw,
    texto,
    largura_max,
    tamanho_inicial=28,
    tamanho_min=12,
    negrito=False
):

    tamanho = tamanho_inicial

    while tamanho >= tamanho_min:

        fonte = carregar_fonte(
            tamanho,
            negrito=negrito
        )

        largura_texto = draw.textbbox(
            (0, 0),
            str(texto),
            font=fonte
        )[2]

        if largura_texto <= largura_max:

            return fonte

        tamanho -= 1

    return carregar_fonte(
        tamanho_min,
        negrito=negrito
    )


# =====================================
# CRIAR QR CODE
# =====================================

def criar_qr_code(conteudo, tamanho=220):

    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=2
    )

    qr.add_data(conteudo)
    qr.make(fit=True)

    img_qr = qr.make_image(
        fill_color='black',
        back_color='white'
    ).convert('RGB')

    img_qr = img_qr.resize(
        (tamanho, tamanho),
        Image.Resampling.LANCZOS
    )

    return img_qr


# =====================================
# PREPARAR FOTO DO ALUNO
# =====================================

def preparar_foto_aluno(caminho_foto, largura, altura):

    if caminho_foto and os.path.exists(caminho_foto):

        foto = Image.open(caminho_foto).convert('RGB')

    else:

        foto = Image.new(
            'RGB',
            (largura, altura),
            (60, 60, 60)
        )

        draw_foto = ImageDraw.Draw(foto)

        fonte = carregar_fonte(
            28,
            negrito=True
        )

        texto = 'SEM FOTO'

        bbox = draw_foto.textbbox(
            (0, 0),
            texto,
            font=fonte
        )

        texto_largura = bbox[2] - bbox[0]
        texto_altura = bbox[3] - bbox[1]

        draw_foto.text(
            (
                (largura - texto_largura) / 2,
                (altura - texto_altura) / 2
            ),
            texto,
            font=fonte,
            fill=(220, 220, 220)
        )

    foto = ImageOps.fit(
        foto,
        (largura, altura),
        Image.Resampling.LANCZOS
    )

    return foto


# =====================================
# DESENHAR CAMPO DE TEXTO SEM CAIXA
# =====================================

def desenhar_campo(
    draw,
    x,
    y,
    largura,
    altura,
    texto,
    fonte,
    cor_fundo=None,
    cor_texto=(255, 255, 255),
    cor_borda=None
):

    bbox = draw.textbbox(
        (0, 0),
        str(texto),
        font=fonte
    )

    texto_altura = bbox[3] - bbox[1]

    draw.text(
        (
            x,
            y + (altura - texto_altura) / 2 - 2
        ),
        str(texto),
        font=fonte,
        fill=cor_texto
    )


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
# VERIFICAR SE ALUNO ESTÁ APTO PARA EXAME
# =====================================

def verificar_aluno_apto_exame(aluno):

    total_presencas = Presenca.query.filter_by(
        aluno_id=aluno.id
    ).count()

    presencas_confirmadas = Presenca.query.filter_by(
        aluno_id=aluno.id,
        status='PRESENTE'
    ).count()

    percentual = 0

    if total_presencas > 0:

        percentual = round(
            (presencas_confirmadas / total_presencas) * 100,
            1
        )

    apto = False

    if total_presencas > 0 and percentual >= 75:

        apto = True

    return {
        'apto': apto,
        'percentual': percentual,
        'total_presencas': total_presencas,
        'presencas_confirmadas': presencas_confirmadas
    }


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

    faturamento = float(
        faturamento
    )

    inadimplentes = Mensalidade.query.filter_by(
        status='PENDENTE'
    ).count()

    alunos = Aluno.query.all()

    aptos = 0

    for aluno in alunos:

        resultado_apto = verificar_aluno_apto_exame(
            aluno
        )

        if resultado_apto['apto']:

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

    busca = request.args.get('busca', '').strip()
    turma_filtro = request.args.get('turma_id', '').strip()

    query = Aluno.query

    if busca:

        query = query.filter(
            Aluno.nome.ilike(f'%{busca}%')
        )

    if turma_filtro:

        query = query.filter(
            Aluno.turma_id == turma_filtro
        )

    lista_alunos = query.order_by(
        Aluno.nome.asc()
    ).all()

    lista_turmas = Turma.query.order_by(
        Turma.nome.asc()
    ).all()

    dados_aptidao = {}

    aptos_exame = 0

    for aluno in lista_alunos:

        resultado_apto = verificar_aluno_apto_exame(
            aluno
        )

        dados_aptidao[aluno.id] = resultado_apto

        if resultado_apto['apto']:

            aptos_exame += 1

    return render_template(
        'alunos.html',
        alunos=lista_alunos,
        dados_aptidao=dados_aptidao,
        aptos_exame=aptos_exame,
        lista_turmas=lista_turmas,
        busca=busca,
        turma_filtro=turma_filtro
    )


# =====================================
# CADASTRAR ALUNO
# =====================================

@app.route('/cadastrar_aluno', methods=['GET', 'POST'])
@login_obrigatorio
def cadastrar_aluno():

    turmas = Turma.query.order_by(
        Turma.nome.asc()
    ).all()

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

        turma_id = request.form.get(
            'turma_id',
            ''
        )

        turma = None

        if turma_id:

            turma = Turma.query.get(
                turma_id
            )

            if not turma:

                flash(
                    'Selecione uma turma válida.',
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
            foto=nome_arquivo,
            turma_id=turma.id if turma else None
        )

        db.session.add(novo_aluno)

        db.session.commit()

        flash(
            'Aluno cadastrado com sucesso.',
            'success'
        )

        return redirect('/alunos')

    return render_template(
        'cadastrar_aluno.html',
        turmas=turmas
    )


# =====================================
# EDITAR ALUNO
# =====================================

@app.route('/editar_aluno/<int:id>', methods=['GET', 'POST'])
@login_obrigatorio
def editar_aluno(id):

    aluno = Aluno.query.get_or_404(id)

    turmas = Turma.query.order_by(
        Turma.nome.asc()
    ).all()

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

        turma_id = request.form.get(
            'turma_id',
            ''
        )

        turma = None

        if turma_id:

            turma = Turma.query.get(
                turma_id
            )

            if not turma:

                flash(
                    'Selecione uma turma válida.',
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
        aluno.turma_id = turma.id if turma else None

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
        aluno=aluno,
        turmas=turmas
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
# GERAR ARTE DA CARTEIRINHA
# =====================================

def gerar_arte_carteirinha(aluno):

    base_path = os.path.join(
        app.root_path,
        'static',
        'modelos',
        'carteirinha_base.png'
    )

    if not os.path.exists(base_path):

        return None

    # ABRE MOCKUP BASE

    base = Image.open(base_path).convert('RGBA')

    largura, altura = base.size

    # CAMADA PARA DESENHO

    camada = Image.new(
        'RGBA',
        base.size,
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(camada)

    # CORES

    branco = (255, 255, 255)

    # =====================================
    # DADOS FORMATADOS
    # =====================================

    nome_aluno = aluno.nome or 'Não informado'
    faixa = aluno.faixa or 'Não informado'
    responsavel = aluno.responsavel or 'Não informado'

    nascimento = formatar_data(
        aluno.nascimento
    )

    whatsapp = formatar_whatsapp(
        aluno.whatsapp
    )

    matricula = f'AAKC-{aluno.id:06d}'

    validade = f'31/12/{date.today().year}'

    # =====================================
    # FONTES
    # =====================================

    fonte_nome = ajustar_fonte(
        draw,
        nome_aluno,
        int(largura * 0.18),
        tamanho_inicial=24,
        tamanho_min=14,
        negrito=True
    )

    fonte_valor = carregar_fonte(
        18,
        negrito=False
    )

    fonte_matricula = ajustar_fonte(
        draw,
        matricula,
        int(largura * 0.18),
        tamanho_inicial=20,
        tamanho_min=14,
        negrito=False
    )

    # =====================================
    # COORDENADAS DA FRENTE
    # =====================================

    campo_x = int(largura * 0.115)
    campo_largura = int(largura * 0.175)
    campo_altura = int(altura * 0.035)

    nome_y = int(altura * 0.350)
    faixa_y = int(altura * 0.438)
    responsavel_y = int(altura * 0.512)
    nascimento_y = int(altura * 0.605)
    whatsapp_y = int(altura * 0.690)
    matricula_y = int(altura * 0.768)
    validade_y = int(altura * 0.850)

    # FOTO DO ALUNO

    foto_x = int(largura * 0.315)
    foto_y = int(altura * 0.420)
    foto_largura = int(largura * 0.145)
    foto_altura = int(altura * 0.280)

    # QR CODE NO VERSO

    qr_x = int(largura * 0.795)
    qr_y = int(altura * 0.285)
    qr_tamanho = int(altura * 0.185)

    # =====================================
    # DESENHAR DADOS DA FRENTE
    # =====================================

    desenhar_campo(
        draw,
        campo_x,
        nome_y,
        campo_largura,
        campo_altura,
        nome_aluno,
        fonte_nome,
        cor_texto=branco
    )

    desenhar_campo(
        draw,
        campo_x,
        faixa_y,
        campo_largura,
        campo_altura,
        faixa,
        fonte_valor,
        cor_texto=branco
    )

    desenhar_campo(
        draw,
        campo_x,
        responsavel_y,
        campo_largura,
        campo_altura,
        responsavel,
        fonte_valor,
        cor_texto=branco
    )

    desenhar_campo(
        draw,
        campo_x,
        nascimento_y,
        campo_largura,
        campo_altura,
        nascimento,
        fonte_valor,
        cor_texto=branco
    )

    desenhar_campo(
        draw,
        campo_x,
        whatsapp_y,
        campo_largura,
        campo_altura,
        whatsapp,
        fonte_valor,
        cor_texto=branco
    )

    desenhar_campo(
        draw,
        campo_x,
        matricula_y,
        campo_largura,
        campo_altura,
        matricula,
        fonte_matricula,
        cor_texto=branco
    )

    desenhar_campo(
        draw,
        campo_x,
        validade_y,
        campo_largura,
        campo_altura,
        validade,
        fonte_valor,
        cor_texto=branco
    )

    # =====================================
    # FOTO DO ALUNO
    # =====================================

    caminho_foto = None

    if aluno.foto:

        caminho_foto = os.path.join(
            app.root_path,
            'static',
            'uploads',
            aluno.foto
        )

    if caminho_foto and os.path.exists(caminho_foto):

        foto = preparar_foto_aluno(
            caminho_foto,
            foto_largura,
            foto_altura
        )

        base.paste(
            foto,
            (foto_x, foto_y)
        )

    # =====================================
    # QR CODE
    # =====================================

    dados_qr = f'https://karate-system.onrender.com/validar-carteirinha/{aluno.id}'

    qr_img = criar_qr_code(
        dados_qr,
        tamanho=qr_tamanho
    )

    base.paste(
        qr_img,
        (qr_x, qr_y)
    )

    # =====================================
    # CONTATO DA ACADEMIA NO VERSO
    # =====================================

    fonte_contato = carregar_fonte(
        17,
        negrito=False
    )

    contato_x = int(largura * 0.555)
    endereco_y = int(altura * 0.750)
    whatsapp_y_academia = int(altura * 0.780)
    instagram_y = int(altura * 0.815)

    draw.text(
        (contato_x, endereco_y),
        'Av. Des. Armando de Souza Louzada',
        font=fonte_contato,
        fill=branco
    )

    draw.text(
        (contato_x, whatsapp_y_academia),
        'WhatsApp: (88) 98880-5107',
        font=fonte_contato,
        fill=branco
    )

    draw.text(
        (contato_x, instagram_y),
        'Instagram: @aakc_acarau_',
        font=fonte_contato,
        fill=branco
    )

    # =====================================
    # JUNTA A CAMADA COM A BASE
    # =====================================

    arte_final = Image.alpha_composite(
        base,
        camada
    ).convert('RGB')

    return arte_final


# =====================================
# CARTEIRINHA DO ALUNO EM PDF
# =====================================

@app.route('/carteirinha/<int:id>')
@login_obrigatorio
def carteirinha_aluno(id):

    aluno = Aluno.query.get_or_404(id)

    arte_final = gerar_arte_carteirinha(
        aluno
    )

    if arte_final is None:

        flash(
            'Modelo da carteirinha não encontrado em static/modelos/carteirinha_base.png',
            'danger'
        )

        return redirect(f'/aluno/{id}')

    # =====================================
    # GERAR PDF PARA IMPRESSÃO
    # =====================================

    img_buffer = BytesIO()

    arte_final.save(
        img_buffer,
        format='PNG'
    )

    img_buffer.seek(0)

    pdf_buffer = BytesIO()

    pagina = landscape(
        (210 * mm, 297 * mm)
    )

    c = canvas.Canvas(
        pdf_buffer,
        pagesize=pagina
    )

    pagina_largura, pagina_altura = pagina

    margem = 5 * mm

    area_largura = pagina_largura - (margem * 2)
    area_altura = pagina_altura - (margem * 2)

    proporcao_img = arte_final.width / arte_final.height
    proporcao_area = area_largura / area_altura

    if proporcao_img > proporcao_area:

        draw_w = area_largura
        draw_h = draw_w / proporcao_img

    else:

        draw_h = area_altura
        draw_w = draw_h * proporcao_img

    pos_x = (pagina_largura - draw_w) / 2
    pos_y = (pagina_altura - draw_h) / 2

    c.drawImage(
        ImageReader(img_buffer),
        pos_x,
        pos_y,
        width=draw_w,
        height=draw_h,
        mask='auto'
    )

    c.showPage()

    c.save()

    pdf_buffer.seek(0)

    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=False,
        download_name=f'carteirinha_{aluno.id}.pdf'
    )


# =====================================
# CARTEIRINHA DO ALUNO EM PNG
# =====================================

@app.route('/carteirinha_png/<int:id>')
@login_obrigatorio
def carteirinha_aluno_png(id):

    aluno = Aluno.query.get_or_404(id)

    arte_final = gerar_arte_carteirinha(
        aluno
    )

    if arte_final is None:

        flash(
            'Modelo da carteirinha não encontrado em static/modelos/carteirinha_base.png',
            'danger'
        )

        return redirect(f'/aluno/{id}')

    img_buffer = BytesIO()

    arte_final.save(
        img_buffer,
        format='PNG'
    )

    img_buffer.seek(0)

    return send_file(
        img_buffer,
        mimetype='image/png',
        as_attachment=True,
        download_name=f'carteirinha_{aluno.id}.png'
    )


# =====================================
# VALIDAR CARTEIRINHA E REGISTRAR PRESENÇA
# =====================================

@app.route('/validar_carteirinha/<int:id>')
@app.route('/validar-carteirinha/<int:id>')
def validar_carteirinha(id):

    aluno = Aluno.query.get_or_404(id)

    idade = calcular_idade(
        aluno.nascimento
    )

    matricula = f'AAKC-{aluno.id:06d}'

    validade = f'31/12/{date.today().year}'

    presenca_registrada = False
    presenca_ja_existia = False
    usuario_logado = False

    if 'usuario' in session:

        usuario_logado = True

        hoje = date.today().strftime('%Y-%m-%d')

        presenca = Presenca.query.filter_by(
            aluno_id=aluno.id,
            data=hoje
        ).first()

        if presenca:

            if presenca.status == 'PRESENTE':

                presenca_ja_existia = True

            else:

                presenca.status = 'PRESENTE'

                db.session.commit()

                presenca_registrada = True

        else:

            nova_presenca = Presenca(
                aluno_id=aluno.id,
                data=hoje,
                status='PRESENTE'
            )

            db.session.add(
                nova_presenca
            )

            db.session.commit()

            presenca_registrada = True

    return render_template(
        'validar_carteirinha.html',
        aluno=aluno,
        idade=idade,
        matricula=matricula,
        validade=validade,
        presenca_registrada=presenca_registrada,
        presenca_ja_existia=presenca_ja_existia,
        usuario_logado=usuario_logado
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

        turma_retorno = request.form.get(
            'turma_id',
            ''
        )

        if not aluno:

            flash(
                'Aluno inválido. Selecione um aluno cadastrado.',
                'warning'
            )

            if turma_retorno:
                return redirect(f'/presencas?turma_id={turma_retorno}')

            return redirect('/presencas')

        data_form = request.form['data']

        if not validar_data_presenca(data_form):

            flash(
                'Informe uma data de presença válida. A data não pode ser futura.',
                'warning'
            )

            if turma_retorno:
                return redirect(f'/presencas?turma_id={turma_retorno}')

            return redirect('/presencas')

        status_form = request.form['status']

        if not validar_status_presenca(status_form):

            flash(
                'Status de presença inválido.',
                'warning'
            )

            if turma_retorno:
                return redirect(f'/presencas?turma_id={turma_retorno}')

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

            if turma_retorno:
                return redirect(f'/presencas?turma_id={turma_retorno}')

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

        if turma_retorno:
            return redirect(f'/presencas?turma_id={turma_retorno}')

        return redirect('/presencas')

    filtro_aluno = request.args.get('aluno_id', '').strip()
    filtro_data = request.args.get('data', '').strip()
    filtro_status = request.args.get('status', '').strip()
    filtro_turma = request.args.get('turma_id', '').strip()

    turmas = Turma.query.order_by(
        Turma.nome.asc()
    ).all()

    query_alunos = Aluno.query

    if filtro_turma:

        query_alunos = query_alunos.filter(
            Aluno.turma_id == filtro_turma
        )

    alunos = query_alunos.order_by(
        Aluno.nome.asc()
    ).all()

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

    if filtro_turma:

        query = query.filter(
            Presenca.aluno.has(
                Aluno.turma_id == int(filtro_turma)
            )
        )

    lista_presencas = query.order_by(
        Presenca.data.desc()
    ).all()

    total_registros = query.count()

    total_presentes = query.filter(
        Presenca.status == 'PRESENTE'
    ).count()

    total_faltas = query.filter(
        Presenca.status == 'FALTA'
    ).count()

    turma_selecionada = None

    if filtro_turma:

        turma_selecionada = Turma.query.get(
            filtro_turma
        )

    return render_template(
        'presencas.html',
        alunos=alunos,
        turmas=turmas,
        presencas=lista_presencas,
        total_registros=total_registros,
        total_presentes=total_presentes,
        total_faltas=total_faltas,
        filtro_aluno=filtro_aluno,
        filtro_data=filtro_data,
        filtro_status=filtro_status,
        filtro_turma=filtro_turma,
        turma_selecionada=turma_selecionada
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
# CHAMADA DA TURMA
# =====================================

@app.route('/chamada_turma/<int:id>', methods=['GET', 'POST'])
@login_obrigatorio
def chamada_turma(id):

    turma = Turma.query.get_or_404(id)

    alunos = Aluno.query.filter_by(
        turma_id=turma.id
    ).order_by(
        Aluno.nome.asc()
    ).all()

    data_chamada = request.args.get(
        'data',
        date.today().strftime('%Y-%m-%d')
    )

    if request.method == 'POST':

        data_form = request.form.get(
            'data',
            ''
        )

        if not validar_data_presenca(data_form):

            flash(
                'Informe uma data válida para a chamada. A data não pode ser futura.',
                'warning'
            )

            return redirect(f'/chamada_turma/{turma.id}')

        for aluno in alunos:

            status = request.form.get(
                f'status_{aluno.id}',
                ''
            )

            if status not in ['PRESENTE', 'FALTA', '']:

                continue

            if status == '':

                continue

            presenca_existente = Presenca.query.filter_by(
                aluno_id=aluno.id,
                data=data_form
            ).first()

            if presenca_existente:

                presenca_existente.status = status

            else:

                nova_presenca = Presenca(
                    aluno_id=aluno.id,
                    data=data_form,
                    status=status
                )

                db.session.add(nova_presenca)

        db.session.commit()

        flash(
            f'Chamada da turma {turma.nome} salva com sucesso.',
            'success'
        )

        return redirect(f'/chamada_turma/{turma.id}?data={data_form}')

    presencas_do_dia = Presenca.query.filter(
        Presenca.data == data_chamada,
        Presenca.aluno.has(
            Aluno.turma_id == turma.id
        )
    ).all()

    status_por_aluno = {}

    for presenca in presencas_do_dia:

        status_por_aluno[presenca.aluno_id] = presenca.status

    return render_template(
        'chamada_turma.html',
        turma=turma,
        alunos=alunos,
        data_chamada=data_chamada,
        status_por_aluno=status_por_aluno
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
    data_hora_emissao = datetime.now().strftime('%d/%m/%Y às %H:%M')

    aluno = mensalidade.aluno

    recibo_numero = f'REC-{mensalidade.id:06d}'

    # =====================================
    # CONFIGURAÇÕES DO PDF
    # =====================================

    largura, altura = 595, 842

    c = canvas.Canvas(
        nome_arquivo,
        pagesize=(largura, altura)
    )

    vermelho = colors.HexColor('#DC3545')
    vermelho_escuro = colors.HexColor('#8B0000')
    preto = colors.HexColor('#111827')
    cinza = colors.HexColor('#6B7280')
    cinza_claro = colors.HexColor('#F3F4F6')
    verde = colors.HexColor('#198754')
    branco = colors.white

    margem_x = 45

    # =====================================
    # FUNÇÃO AUXILIAR PARA TEXTO
    # =====================================

    def escrever_texto_quebrado(texto, x, y, largura_linha, tamanho=11, espacamento=16):

        c.setFont(
            'Helvetica',
            tamanho
        )

        linhas = textwrap.wrap(
            texto,
            width=largura_linha
        )

        for linha in linhas:

            c.drawString(
                x,
                y,
                linha
            )

            y -= espacamento

        return y

    # =====================================
    # FUNDO
    # =====================================

    c.setFillColor(
        colors.white
    )

    c.rect(
        0,
        0,
        largura,
        altura,
        fill=True,
        stroke=False
    )

    # FAIXA SUPERIOR

    c.setFillColor(
        preto
    )

    c.rect(
        0,
        755,
        largura,
        87,
        fill=True,
        stroke=False
    )

    c.setFillColor(
        vermelho
    )

    c.rect(
        0,
        745,
        largura,
        10,
        fill=True,
        stroke=False
    )

    # =====================================
    # LOGO
    # =====================================

    caminhos_logo = [
        os.path.join(app.root_path, 'static', 'modelos', 'logo.png'),
        os.path.join(app.root_path, 'static', 'modelos', 'Logo.png'),
        os.path.join(app.root_path, 'static', 'Logo.png'),
        os.path.join(app.root_path, 'static', 'logo.png')
    ]

    logo_path = None

    for caminho in caminhos_logo:

        if os.path.exists(caminho):

            logo_path = caminho
            break

    if logo_path:

        try:

            c.drawImage(
                logo_path,
                55,
                765,
                width=60,
                height=60,
                preserveAspectRatio=True,
                mask='auto'
            )

        except Exception:

            logo_path = None

    if not logo_path:

        c.setFillColor(
            vermelho
        )

        c.circle(
            85,
            795,
            28,
            fill=True,
            stroke=False
        )

        c.setFillColor(
            branco
        )

        c.setFont(
            'Helvetica-Bold',
            16
        )

        c.drawCentredString(
            85,
            789,
            'AAKC'
        )

    # =====================================
    # CABEÇALHO
    # =====================================

    c.setFillColor(
        branco
    )

    c.setFont(
        'Helvetica-Bold',
        22
    )

    c.drawString(
        130,
        805,
        'AAKC KARATÊ'
    )

    c.setFont(
        'Helvetica',
        10
    )

    c.drawString(
        132,
        787,
        'Academia de Artes Marciais'
    )

    c.drawString(
        132,
        771,
        'Av. Des. Armando de Souza Louzada | WhatsApp: (88) 98880-5107'
    )

    c.setFont(
        'Helvetica-Bold',
        18
    )

    c.drawRightString(
        largura - 45,
        805,
        'RECIBO'
    )

    c.setFont(
        'Helvetica',
        10
    )

    c.drawRightString(
        largura - 45,
        786,
        recibo_numero
    )

    # =====================================
    # TÍTULO PRINCIPAL
    # =====================================

    c.setFillColor(
        preto
    )

    c.setFont(
        'Helvetica-Bold',
        22
    )

    c.drawCentredString(
        largura / 2,
        705,
        'RECIBO DE PAGAMENTO'
    )

    c.setFont(
        'Helvetica',
        11
    )

    c.setFillColor(
        cinza
    )

    c.drawCentredString(
        largura / 2,
        685,
        'Comprovante referente ao pagamento de mensalidade'
    )

    # =====================================
    # SELO PAGO
    # =====================================

    c.setFillColor(
        verde
    )

    c.roundRect(
        430,
        650,
        95,
        34,
        10,
        fill=True,
        stroke=False
    )

    c.setFillColor(
        branco
    )

    c.setFont(
        'Helvetica-Bold',
        14
    )

    c.drawCentredString(
        477,
        661,
        'PAGO'
    )

    # =====================================
    # DADOS DO RECIBO
    # =====================================

    c.setFillColor(
        cinza_claro
    )

    c.roundRect(
        margem_x,
        605,
        largura - 90,
        35,
        8,
        fill=True,
        stroke=False
    )

    c.setFillColor(
        preto
    )

    c.setFont(
        'Helvetica-Bold',
        10
    )

    c.drawString(
        65,
        618,
        f'Recibo Nº: {recibo_numero}'
    )

    c.drawString(
        260,
        618,
        f'Emissão: {data_emissao}'
    )

    c.drawString(
        405,
        618,
        f'Mensalidade ID: {mensalidade.id}'
    )

    # =====================================
    # TEXTO PRINCIPAL
    # =====================================

    texto_principal = (
        f'Recebemos de {aluno.nome}, a importância de R$ {valor_formatado}, '
        f'referente ao pagamento de mensalidade da AAKC Karatê.'
    )

    c.setFillColor(
        preto
    )

    y_texto = escrever_texto_quebrado(
        texto_principal,
        65,
        560,
        82,
        tamanho=11,
        espacamento=17
    )

    # =====================================
    # CAIXA DE DADOS DO PAGAMENTO
    # =====================================

    c.setStrokeColor(
        vermelho
    )

    c.setLineWidth(
        1.2
    )

    c.roundRect(
        55,
        340,
        largura - 110,
        180,
        12,
        fill=False,
        stroke=True
    )

    c.setFillColor(
        vermelho
    )

    c.roundRect(
        55,
        485,
        largura - 110,
        35,
        12,
        fill=True,
        stroke=False
    )

    c.setFillColor(
        branco
    )

    c.setFont(
        'Helvetica-Bold',
        13
    )

    c.drawString(
        75,
        497,
        'DADOS DO PAGAMENTO'
    )

    c.setFillColor(
        preto
    )

    c.setFont(
        'Helvetica-Bold',
        10
    )

    c.drawString(
        75,
        455,
        'Aluno:'
    )

    c.setFont(
        'Helvetica',
        10
    )

    c.drawString(
        165,
        455,
        aluno.nome
    )

    c.setFont(
        'Helvetica-Bold',
        10
    )

    c.drawString(
        75,
        430,
        'Valor pago:'
    )

    c.setFont(
        'Helvetica-Bold',
        12
    )

    c.setFillColor(
        verde
    )

    c.drawString(
        165,
        430,
        f'R$ {valor_formatado}'
    )

    c.setFillColor(
        preto
    )

    c.setFont(
        'Helvetica-Bold',
        10
    )

    c.drawString(
        75,
        405,
        'Referência:'
    )

    c.setFont(
        'Helvetica',
        10
    )

    c.drawString(
        165,
        405,
        'Mensalidade da academia'
    )

    c.setFont(
        'Helvetica-Bold',
        10
    )

    c.drawString(
        75,
        380,
        'Vencimento:'
    )

    c.setFont(
        'Helvetica',
        10
    )

    c.drawString(
        165,
        380,
        vencimento_formatado
    )

    c.setFont(
        'Helvetica-Bold',
        10
    )

    c.drawString(
        75,
        355,
        'Status:'
    )

    c.setFont(
        'Helvetica-Bold',
        10
    )

    c.setFillColor(
        verde
    )

    c.drawString(
        165,
        355,
        mensalidade.status
    )

    # =====================================
    # OBSERVAÇÕES
    # =====================================

    c.setFillColor(
        cinza
    )

    c.setFont(
        'Helvetica',
        9
    )

    c.drawString(
        55,
        300,
        f'Emitido automaticamente pelo sistema Karate System em {data_hora_emissao}.'
    )

    c.drawString(
        55,
        285,
        'Este documento comprova o pagamento da mensalidade informada acima.'
    )

    # =====================================
    # ASSINATURA
    # =====================================

    c.setStrokeColor(
        preto
    )

    c.setLineWidth(
        1
    )

    c.line(
        170,
        205,
        425,
        205
    )

    c.setFillColor(
        preto
    )

    c.setFont(
        'Helvetica',
        10
    )

    c.drawCentredString(
        largura / 2,
        187,
        'Assinatura do responsável pela academia'
    )

    c.setFont(
        'Helvetica-Bold',
        10
    )

    c.drawCentredString(
        largura / 2,
        170,
        'AAKC KARATÊ'
    )

    # =====================================
    # RODAPÉ
    # =====================================

    c.setFillColor(
        preto
    )

    c.rect(
        0,
        0,
        largura,
        42,
        fill=True,
        stroke=False
    )

    c.setFillColor(
        branco
    )

    c.setFont(
        'Helvetica',
        8
    )

    c.drawCentredString(
        largura / 2,
        25,
        'AAKC Karatê | Av. Des. Armando de Souza Louzada | WhatsApp: (88) 98880-5107 | Instagram: @aakc_acarau_'
    )

    c.drawCentredString(
        largura / 2,
        12,
        'Karate System - Gestão de Alunos, Frequência e Mensalidades'
    )

    c.save()

    return send_file(
        nome_arquivo,
        as_attachment=True,
        download_name=f'recibo_{mensalidade.id}.pdf',
        mimetype='application/pdf'
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
# PROFESSORES
# =====================================

@app.route('/professores')
@login_obrigatorio
@admin_obrigatorio
def professores():

    lista_professores = Professor.query.order_by(
        Professor.nome.asc()
    ).all()

    return render_template(
        'professores.html',
        professores=lista_professores
    )


# =====================================
# CADASTRAR PROFESSOR
# =====================================

@app.route('/cadastrar_professor', methods=['GET', 'POST'])
@login_obrigatorio
@admin_obrigatorio
def cadastrar_professor():

    if request.method == 'POST':

        nome = formatar_nome(
            request.form.get('nome', '')
        )

        telefone = limpar_whatsapp(
            request.form.get('telefone', '')
        )

        observacao = request.form.get(
            'observacao',
            ''
        ).strip()

        if not nome:

            flash(
                'Informe o nome do professor.',
                'warning'
            )

            return redirect(request.url)

        professor_existente = Professor.query.filter(
            Professor.nome == nome
        ).first()

        if professor_existente:

            flash(
                'Já existe um professor cadastrado com este nome.',
                'warning'
            )

            return redirect(request.url)

        if telefone and not validar_whatsapp(telefone):

            flash(
                'Informe um telefone válido com DDD. Exemplo: 88999998888.',
                'warning'
            )

            return redirect(request.url)

        novo_professor = Professor(
            nome=nome,
            telefone=telefone,
            observacao=observacao
        )

        db.session.add(novo_professor)
        db.session.commit()

        flash(
            'Professor cadastrado com sucesso.',
            'success'
        )

        return redirect('/professores')

    return render_template(
        'cadastrar_professor.html'
    )


# =====================================
# EDITAR PROFESSOR
# =====================================

@app.route('/editar_professor/<int:id>', methods=['GET', 'POST'])
@login_obrigatorio
@admin_obrigatorio
def editar_professor(id):

    professor = Professor.query.get_or_404(id)

    if request.method == 'POST':

        nome = formatar_nome(
            request.form.get('nome', '')
        )

        telefone = limpar_whatsapp(
            request.form.get('telefone', '')
        )

        observacao = request.form.get(
            'observacao',
            ''
        ).strip()

        if not nome:

            flash(
                'Informe o nome do professor.',
                'warning'
            )

            return redirect(request.url)

        professor_existente = Professor.query.filter(
            Professor.nome == nome,
            Professor.id != id
        ).first()

        if professor_existente:

            flash(
                'Já existe outro professor cadastrado com este nome.',
                'warning'
            )

            return redirect(request.url)

        if telefone and not validar_whatsapp(telefone):

            flash(
                'Informe um telefone válido com DDD. Exemplo: 88999998888.',
                'warning'
            )

            return redirect(request.url)

        professor.nome = nome
        professor.telefone = telefone
        professor.observacao = observacao

        db.session.commit()

        flash(
            'Professor atualizado com sucesso.',
            'success'
        )

        return redirect('/professores')

    return render_template(
        'editar_professor.html',
        professor=professor
    )


# =====================================
# EXCLUIR PROFESSOR
# =====================================

@app.route('/excluir_professor/<int:id>')
@login_obrigatorio
@admin_obrigatorio
def excluir_professor(id):

    professor = Professor.query.get_or_404(id)

    turmas_vinculadas = Turma.query.filter_by(
        professor_id=professor.id
    ).count()

    if turmas_vinculadas > 0:

        flash(
            'Não é possível excluir este professor, pois ele possui turmas vinculadas.',
            'danger'
        )

        return redirect('/professores')

    db.session.delete(professor)
    db.session.commit()

    flash(
        'Professor excluído com sucesso.',
        'success'
    )

    return redirect('/professores')


# =====================================
# TURMAS
# =====================================

@app.route('/turmas')
@login_obrigatorio
def turmas():

    lista_turmas = Turma.query.order_by(
        Turma.nome.asc()
    ).all()

    return render_template(
        'turmas.html',
        turmas=lista_turmas
    )


# =====================================
# CADASTRAR TURMA
# =====================================

@app.route('/cadastrar_turma', methods=['GET', 'POST'])
@login_obrigatorio
@admin_obrigatorio
def cadastrar_turma():

    professores = Professor.query.order_by(
        Professor.nome.asc()
    ).all()

    if request.method == 'POST':

        nome = request.form.get(
            'nome',
            ''
        ).strip()

        dias = request.form.get(
            'dias',
            ''
        ).strip()

        horario = request.form.get(
            'horario',
            ''
        ).strip()

        observacao = request.form.get(
            'observacao',
            ''
        ).strip()

        professor_id = request.form.get(
            'professor_id',
            ''
        )

        if not nome:

            flash(
                'Informe o nome da turma.',
                'warning'
            )

            return redirect(request.url)

        turma_existente = Turma.query.filter(
            Turma.nome == nome
        ).first()

        if turma_existente:

            flash(
                'Já existe uma turma cadastrada com este nome.',
                'warning'
            )

            return redirect(request.url)

        professor = None

        if professor_id:

            professor = Professor.query.get(
                professor_id
            )

            if not professor:

                flash(
                    'Selecione um professor válido.',
                    'warning'
                )

                return redirect(request.url)

        nova_turma = Turma(
            nome=nome,
            dias=dias,
            horario=horario,
            observacao=observacao,
            professor_id=professor.id if professor else None
        )

        db.session.add(nova_turma)
        db.session.commit()

        flash(
            'Turma cadastrada com sucesso.',
            'success'
        )

        return redirect('/turmas')

    return render_template(
        'cadastrar_turma.html',
        professores=professores
    )


# =====================================
# EDITAR TURMA
# =====================================

@app.route('/editar_turma/<int:id>', methods=['GET', 'POST'])
@login_obrigatorio
@admin_obrigatorio
def editar_turma(id):

    turma = Turma.query.get_or_404(id)

    professores = Professor.query.order_by(
        Professor.nome.asc()
    ).all()

    if request.method == 'POST':

        nome = request.form.get(
            'nome',
            ''
        ).strip()

        dias = request.form.get(
            'dias',
            ''
        ).strip()

        horario = request.form.get(
            'horario',
            ''
        ).strip()

        observacao = request.form.get(
            'observacao',
            ''
        ).strip()

        professor_id = request.form.get(
            'professor_id',
            ''
        )

        if not nome:

            flash(
                'Informe o nome da turma.',
                'warning'
            )

            return redirect(request.url)

        turma_existente = Turma.query.filter(
            Turma.nome == nome,
            Turma.id != id
        ).first()

        if turma_existente:

            flash(
                'Já existe outra turma cadastrada com este nome.',
                'warning'
            )

            return redirect(request.url)

        professor = None

        if professor_id:

            professor = Professor.query.get(
                professor_id
            )

            if not professor:

                flash(
                    'Selecione um professor válido.',
                    'warning'
                )

                return redirect(request.url)

        turma.nome = nome
        turma.dias = dias
        turma.horario = horario
        turma.observacao = observacao
        turma.professor_id = professor.id if professor else None

        db.session.commit()

        flash(
            'Turma atualizada com sucesso.',
            'success'
        )

        return redirect('/turmas')

    return render_template(
        'editar_turma.html',
        turma=turma,
        professores=professores
    )


# =====================================
# EXCLUIR TURMA
# =====================================

@app.route('/excluir_turma/<int:id>')
@login_obrigatorio
@admin_obrigatorio
def excluir_turma(id):

    turma = Turma.query.get_or_404(id)

    alunos_vinculados = Aluno.query.filter_by(
        turma_id=turma.id
    ).count()

    if alunos_vinculados > 0:

        flash(
            'Não é possível excluir esta turma, pois existem alunos vinculados a ela.',
            'danger'
        )

        return redirect('/turmas')

    db.session.delete(turma)
    db.session.commit()

    flash(
        'Turma excluída com sucesso.',
        'success'
    )

    return redirect('/turmas')


# =====================================
# PERFIL DA TURMA
# =====================================

@app.route('/turma/<int:id>')
@login_obrigatorio
def perfil_turma(id):

    turma = Turma.query.get_or_404(id)

    alunos = Aluno.query.filter_by(
        turma_id=turma.id
    ).order_by(
        Aluno.nome.asc()
    ).all()

    alunos_disponiveis = Aluno.query.filter(
        (Aluno.turma_id == None) | (Aluno.turma_id != turma.id)
    ).order_by(
        Aluno.nome.asc()
    ).all()

    return render_template(
        'perfil_turma.html',
        turma=turma,
        alunos=alunos,
        alunos_disponiveis=alunos_disponiveis
    )


# =====================================
# ADICIONAR ALUNO À TURMA
# =====================================

@app.route('/turma/<int:turma_id>/adicionar_aluno', methods=['POST'])
@login_obrigatorio
@admin_obrigatorio
def adicionar_aluno_turma(turma_id):

    turma = Turma.query.get_or_404(turma_id)

    aluno_id = request.form.get(
        'aluno_id',
        ''
    )

    if not aluno_id:

        flash(
            'Selecione um aluno para adicionar à turma.',
            'warning'
        )

        return redirect(f'/turma/{turma.id}')

    aluno = Aluno.query.get(
        aluno_id
    )

    if not aluno:

        flash(
            'Aluno não encontrado.',
            'danger'
        )

        return redirect(f'/turma/{turma.id}')

    aluno.turma_id = turma.id

    db.session.commit()

    flash(
        f'Aluno {aluno.nome} adicionado à turma {turma.nome}.',
        'success'
    )

    return redirect(f'/turma/{turma.id}')


# =====================================
# REMOVER ALUNO DA TURMA
# =====================================

@app.route('/turma/<int:turma_id>/remover_aluno/<int:aluno_id>')
@login_obrigatorio
@admin_obrigatorio
def remover_aluno_turma(turma_id, aluno_id):

    turma = Turma.query.get_or_404(turma_id)

    aluno = Aluno.query.get_or_404(aluno_id)

    if aluno.turma_id != turma.id:

        flash(
            'Este aluno não pertence a esta turma.',
            'warning'
        )

        return redirect(f'/turma/{turma.id}')

    aluno.turma_id = None

    db.session.commit()

    flash(
        f'Aluno {aluno.nome} removido da turma {turma.nome}.',
        'success'
    )

    return redirect(f'/turma/{turma.id}')


# =====================================
# ATUALIZAR BANCO - TURMAS E PROFESSORES
# =====================================

@app.route('/atualizar_banco_turmas')
@login_obrigatorio
@admin_obrigatorio
def atualizar_banco_turmas():

    try:

        db.create_all()

        with db.engine.connect() as conexao:

            try:

                conexao.execute(
                    db.text(
                        'ALTER TABLE alunos ADD COLUMN turma_id INTEGER'
                    )
                )

            except Exception:

                pass

            try:

                conexao.execute(
                    db.text(
                        'ALTER TABLE alunos ADD CONSTRAINT fk_alunos_turmas FOREIGN KEY (turma_id) REFERENCES turmas(id)'
                    )
                )

            except Exception:

                pass

            conexao.commit()

        flash(
            'Banco atualizado com tabelas de professores, turmas e vínculo com alunos.',
            'success'
        )

    except Exception as erro:

        flash(
            f'Erro ao atualizar banco: {erro}',
            'danger'
        )

    return redirect('/alunos')


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