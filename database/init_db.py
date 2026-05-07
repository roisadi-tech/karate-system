import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

db_path = os.path.join(BASE_DIR, 'database.db')

conn = sqlite3.connect(db_path)

cursor = conn.cursor()

# =========================
# TABELA ALUNOS
# =========================

cursor.execute('''
CREATE TABLE IF NOT EXISTS alunos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    nascimento TEXT,
    responsavel TEXT,
    whatsapp TEXT,
    faixa TEXT,
    mensalidade REAL,
    status TEXT DEFAULT 'ATIVO',
    foto TEXT
)
''')

# =========================
# TABELA PRESENCAS
# =========================

cursor.execute('''
CREATE TABLE IF NOT EXISTS presencas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aluno_id INTEGER,
    data TEXT,
    status TEXT
)
''')

# =========================
# TABELA MENSALIDADES
# =========================

cursor.execute('''
CREATE TABLE IF NOT EXISTS mensalidades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aluno_id INTEGER,
    valor REAL,
    vencimento TEXT,
    status TEXT
)
''')

# =========================
# TABELA EXAMES
# =========================

cursor.execute('''
CREATE TABLE IF NOT EXISTS exames (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aluno_id INTEGER,
    faixa_atual TEXT,
    nova_faixa TEXT,
    data_exame TEXT,
    resultado TEXT
)
''')

conn.commit()
conn.close()

print('Banco criado com sucesso!')