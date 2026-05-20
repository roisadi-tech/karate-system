from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    send_file
)

from flask_sqlalchemy import SQLAlchemy

import sqlite3
import os
import shutil

from datetime import datetime

from functools import wraps

from werkzeug.utils import secure_filename

from reportlab.pdfgen import canvas

app = Flask(__name__)

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

db = SQLAlchemy(app)
from models import *

app.secret_key = 'karate_secret'
from functools import wraps

def login_obrigatorio(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if 'usuario' not in session:

            return redirect('/login')

        return f(*args, **kwargs)

    return decorated_function


@app.route('/')

@login_obrigatorio
def index():

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # TOTAL DE ALUNOS
    cursor.execute('''
    SELECT COUNT(*)
    FROM alunos
    ''')

    total_alunos = cursor.fetchone()[0]

    # FATURAMENTO PAGO
    cursor.execute('''
    SELECT SUM(valor)
    FROM mensalidades
    WHERE status='PAGO'
    ''')

    resultado = cursor.fetchone()[0]

    if resultado:
        faturamento = resultado
    else:
        faturamento = 0

    # INADIMPLENTES
    cursor.execute('''
    SELECT COUNT(*)
    FROM mensalidades
    WHERE status='PENDENTE'
    ''')

    inadimplentes = cursor.fetchone()[0]

    # APTOS EXAME
    cursor.execute('SELECT id FROM alunos')

    alunos = cursor.fetchall()

    aptos = 0

    for aluno in alunos:

        aluno_id = aluno[0]

        cursor.execute('''
        SELECT COUNT(*)
        FROM presencas
        WHERE aluno_id=?
        ''', (aluno_id,))

        total = cursor.fetchone()[0]

        cursor.execute('''
        SELECT COUNT(*)
        FROM presencas
        WHERE aluno_id=?
        AND status='PRESENTE'
        ''', (aluno_id,))

        presentes = cursor.fetchone()[0]

        if total > 0:

            percentual = (
                presentes / total
            ) * 100

            if percentual >= 75:
                aptos += 1

    conn.close()

    return render_template(
        'index.html',
        total_alunos=total_alunos,
        faturamento=faturamento,
        inadimplentes=inadimplentes,
        aptos=aptos
    )


@app.route('/alunos', methods=['GET', 'POST'])
@login_obrigatorio
def alunos():

    # CADASTRAR ALUNO
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

        return redirect('/alunos')

    # BUSCA
    busca = request.args.get('busca')

    if busca:

        lista_alunos = Aluno.query.filter(
            Aluno.nome.ilike(f'%{busca}%')
        ).order_by(Aluno.id.desc()).all()

    else:

        lista_alunos = Aluno.query.order_by(
            Aluno.id.desc()
        ).all()

    return render_template(
        'alunos.html',
        alunos=lista_alunos
    )


@app.route('/cadastrar_aluno', methods=['GET', 'POST'])

@login_obrigatorio
def cadastrar_aluno():

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

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

            caminho = os.path.join(
                'static/uploads',
                nome_arquivo
            )

            foto.save(caminho)

        cursor.execute('''
        INSERT INTO alunos
        (
            nome,
            nascimento,
            responsavel,
            whatsapp,
            faixa,
            mensalidade,
            foto
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            nome,
            nascimento,
            responsavel,
            whatsapp,
            faixa,
            mensalidade,
            nome_arquivo
        ))

        conn.commit()
        conn.close()

        return redirect('/alunos')

    conn.close()

    return render_template(
        'cadastrar_aluno.html'
    )


# =========================
# EDITAR ALUNO
# =========================

@app.route('/editar_aluno/<int:id>', methods=['GET', 'POST'])

@login_obrigatorio
def editar_aluno(id):

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if request.method == 'POST':

        nome = request.form['nome']
        faixa = request.form['faixa']
        whatsapp = request.form['whatsapp']
        mensalidade = request.form['mensalidade']

        cursor.execute('''
        UPDATE alunos
        SET nome=?, faixa=?, whatsapp=?, mensalidade=?
        WHERE id=?
        ''', (
            nome,
            faixa,
            whatsapp,
            mensalidade,
            id
        ))

        conn.commit()
        conn.close()

        return redirect('/alunos')

    cursor.execute(
        'SELECT * FROM alunos WHERE id=?',
        (id,)
    )

    aluno = cursor.fetchone()

    conn.close()

    return render_template(
        'editar_aluno.html',
        aluno=aluno
    )


# =========================
# EXCLUIR ALUNO
# =========================

@app.route('/excluir_aluno/<int:id>')

@login_obrigatorio
def excluir_aluno(id):

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute(
        'DELETE FROM alunos WHERE id=?',
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect('/alunos')



@app.route('/presencas', methods=['GET', 'POST'])

@login_obrigatorio
def presencas():

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if request.method == 'POST':

        aluno_id = request.form['aluno_id']
        data = request.form['data']
        status = request.form['status']

        cursor.execute('''
        INSERT INTO presencas
        (aluno_id, data, status)
        VALUES (?, ?, ?)
        ''', (
            aluno_id,
            data,
            status
        ))

        conn.commit()

    cursor.execute('SELECT * FROM alunos')

    alunos = cursor.fetchall()

    cursor.execute('''
    SELECT
        presencas.id,
        alunos.nome,
        presencas.data,
        presencas.status

    FROM presencas

    INNER JOIN alunos
    ON alunos.id = presencas.aluno_id

    ORDER BY presencas.data DESC
    ''')

    lista_presencas = cursor.fetchall()

    conn.close()

    return render_template(
        'presencas.html',
        alunos=alunos,
        presencas=lista_presencas
    )


@app.route('/frequencia')

@login_obrigatorio
def frequencia():

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('SELECT id, nome FROM alunos')

    alunos = cursor.fetchall()

    relatorio = []

    for aluno in alunos:

        aluno_id = aluno[0]
        nome = aluno[1]

        # TOTAL DE AULAS
        cursor.execute('''
        SELECT COUNT(*)
        FROM presencas
        WHERE aluno_id=?
        ''', (aluno_id,))

        total = cursor.fetchone()[0]

        # PRESENÇAS
        cursor.execute('''
        SELECT COUNT(*)
        FROM presencas
        WHERE aluno_id=?
        AND status='PRESENTE'
        ''', (aluno_id,))

        presentes = cursor.fetchone()[0]

        # CÁLCULO %
        if total > 0:
            percentual = round(
                (presentes / total) * 100,
                1
            )
        else:
            percentual = 0

        relatorio.append({
            'nome': nome,
            'total': total,
            'presentes': presentes,
            'percentual': percentual
        })

    conn.close()

    return render_template(
        'frequencia.html',
        relatorio=relatorio
    )

@app.route('/mensalidades', methods=['GET', 'POST'])

@login_obrigatorio
def mensalidades():

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if request.method == 'POST':

        aluno_id = request.form['aluno_id']
        valor = request.form['valor']
        vencimento = request.form['vencimento']
        status = request.form['status']

        cursor.execute('''
        INSERT INTO mensalidades
        (aluno_id, valor, vencimento, status)
        VALUES (?, ?, ?, ?)
        ''', (
            aluno_id,
            valor,
            vencimento,
            status
        ))

        conn.commit()

    cursor.execute('SELECT * FROM alunos')

    alunos = cursor.fetchall()

    cursor.execute('''
    SELECT
        mensalidades.id,
        alunos.nome,
        mensalidades.valor,
        mensalidades.vencimento,
        mensalidades.status,
        alunos.whatsapp

    FROM mensalidades

    INNER JOIN alunos
    ON alunos.id = mensalidades.aluno_id

    ORDER BY mensalidades.vencimento DESC
    ''')

    lista = cursor.fetchall()

    conn.close()

    return render_template(
        'mensalidades.html',
        alunos=alunos,
        mensalidades=lista
    )

@app.route('/exames', methods=['GET', 'POST'])

@login_obrigatorio
def exames():

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if request.method == 'POST':

        aluno_id = request.form['aluno_id']
        faixa_atual = request.form['faixa_atual']
        nova_faixa = request.form['nova_faixa']
        data_exame = request.form['data_exame']
        resultado = request.form['resultado']

        cursor.execute('''
        INSERT INTO exames
        (
            aluno_id,
            faixa_atual,
            nova_faixa,
            data_exame,
            resultado
        )
        VALUES (?, ?, ?, ?, ?)
        ''', (
            aluno_id,
            faixa_atual,
            nova_faixa,
            data_exame,
            resultado
        ))

        # SE APROVADO -> ALTERA FAIXA DO ALUNO
        if resultado == 'APROVADO':

            cursor.execute('''
            UPDATE alunos
            SET faixa=?
            WHERE id=?
            ''', (
                nova_faixa,
                aluno_id
            ))

        conn.commit()

    cursor.execute('SELECT * FROM alunos')

    alunos = cursor.fetchall()

    cursor.execute('''
    SELECT
        exames.id,
        alunos.nome,
        exames.faixa_atual,
        exames.nova_faixa,
        exames.data_exame,
        exames.resultado

    FROM exames

    INNER JOIN alunos
    ON alunos.id = exames.aluno_id

    ORDER BY exames.data_exame DESC
    ''')

    lista = cursor.fetchall()

    conn.close()

    return render_template(
        'exames.html',
        alunos=alunos,
        exames=lista
    )

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        usuario = request.form['usuario']
        senha = request.form['senha']

        # LOGIN SIMPLES
        if usuario == 'admin' and senha == '1234':

            session['usuario'] = usuario

            return redirect('/')

    return render_template('login.html')

@app.route('/logout')
def logout():

    session.pop('usuario', None)

    return redirect('/login')

@app.route('/recibo/<int:id>')
@login_obrigatorio
def recibo(id):

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''
    SELECT
        mensalidades.id,
        alunos.nome,
        mensalidades.valor,
        mensalidades.vencimento,
        mensalidades.status

    FROM mensalidades

    INNER JOIN alunos
    ON alunos.id = mensalidades.aluno_id

    WHERE mensalidades.id=?
    ''', (id,))

    mensalidade = cursor.fetchone()

    conn.close()

    nome_arquivo = f'recibo_{id}.pdf'

    c = canvas.Canvas(nome_arquivo)

    c.setFont("Helvetica-Bold", 20)
    c.drawString(180, 800, "RECIBO")

    c.setFont("Helvetica", 12)

    c.drawString(
        100,
        730,
        f'Aluno: {mensalidade[1]}'
    )

    c.drawString(
        100,
        700,
        f'Valor: R$ {mensalidade[2]}'
    )

    c.drawString(
        100,
        670,
        f'Vencimento: {mensalidade[3]}'
    )

    c.drawString(
        100,
        640,
        f'Status: {mensalidade[4]}'
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

@app.route('/backup')
@login_obrigatorio
def backup():

    data = datetime.now().strftime(
        '%Y-%m-%d_%H-%M-%S'
    )

    nome_backup = f'backup_{data}.db'

    origem = 'database.db'

    destino = os.path.join(
        'backups',
        nome_backup
    )

    # CRIA PASTA BACKUPS
    if not os.path.exists('backups'):

        os.makedirs('backups')

    shutil.copy(
        origem,
        destino
    )

    return send_file(
        destino,
        as_attachment=True
    )

@app.route('/relatorios')

@login_obrigatorio
def relatorios():

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # TOTAL ALUNOS
    cursor.execute('''
    SELECT COUNT(*)
    FROM alunos
    ''')

    total_alunos = cursor.fetchone()[0]

    # TOTAL RECEBIDO
    cursor.execute('''
    SELECT SUM(valor)
    FROM mensalidades
    WHERE status='PAGO'
    ''')

    recebido = cursor.fetchone()[0]

    if recebido is None:
        recebido = 0

    # TOTAL PENDENTE
    cursor.execute('''
    SELECT SUM(valor)
    FROM mensalidades
    WHERE status='PENDENTE'
    ''')

    pendente = cursor.fetchone()[0]

    if pendente is None:
        pendente = 0

    # ALUNOS POR FAIXA
    cursor.execute('''
    SELECT faixa, COUNT(*)
    FROM alunos
    GROUP BY faixa
    ''')

    faixas = cursor.fetchall()

    conn.close()

    return render_template(
        'relatorios.html',
        total_alunos=total_alunos,
        recebido=recebido,
        pendente=pendente,
        faixas=faixas
    )

@app.route('/cobrar')

@login_obrigatorio
def cobrar():

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''
    SELECT
        alunos.nome,
        alunos.whatsapp,
        mensalidades.valor,
        mensalidades.vencimento

    FROM mensalidades

    INNER JOIN alunos
    ON alunos.id = mensalidades.aluno_id

    WHERE mensalidades.status='PENDENTE'
    ''')

    dados = cursor.fetchall()

    conn.close()

    return render_template(
        'cobrar.html',
        dados=dados
    )

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)