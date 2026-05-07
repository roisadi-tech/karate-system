import sqlite3
import os

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

db_path = os.path.join(
    BASE_DIR,
    'database.db'
)

conn = sqlite3.connect(db_path)

cursor = conn.cursor()

try:

    cursor.execute('''
    ALTER TABLE alunos
    ADD COLUMN foto TEXT
    ''')

    print('Coluna FOTO criada com sucesso!')

except Exception as e:

    print('Erro ou coluna já existe:')
    print(e)

conn.commit()
conn.close()