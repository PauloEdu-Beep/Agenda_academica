import mysql.connector
from mysql.connector import errorcode

# Copie exatamente a mesma configuração do seu arquivo db_config.py
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'SPQR#Invictus476',
    'database': 'Agendas_Universitaria'
}

print("Tentando conectar ao MySQL...")

try:
    # Tenta estabelecer a conexão
    conn = mysql.connector.connect(**db_config)
    print("Conexão bem-sucedida!")
    
    # Faz uma consulta simples para garantir
    cursor = conn.cursor()
    cursor.execute("SELECT VERSION();")
    db_version = cursor.fetchone()
    print(f"Versão do Banco de Dados: {db_version[0]}")
    
    cursor.close()
    conn.close()
    print("Conexão fechada com sucesso.")

except mysql.connector.Error as err:
    # Se a conexão falhar, o erro será capturado aqui
    print("\n--- OCORREU UM ERRO DE CONEXÃO ---")
    if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
        print("ERRO: Usuário ou senha inválidos.")
    elif err.errno == errorcode.ER_BAD_DB_ERROR:
        print(f"ERRO: O banco de dados '{db_config['database']}' não existe.")
    else:
        print(f"ERRO INESPERADO: {err}")
    print("------------------------------------")

except Exception as e:
    print(f"\n--- UM ERRO NÃO RELACIONADO AO MYSQL OCORREU ---")
    print(f"Tipo de Erro: {type(e).__name__}")
    print(f"Mensagem: {e}")
    print("------------------------------------------------")