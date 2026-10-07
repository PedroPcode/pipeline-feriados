"""
Pipeline de Feriados do Brasil

Extract:   busca os feriados nacionais na BrasilAPI
Transform: converte para DataFrame e ajusta os tipos
Load:      grava no Postgres (Supabase) usando upsert,
           então pode rodar várias vezes sem duplicar dados
"""

import os

import pandas as pd
import psycopg2
import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------
# CONFIGURAÇÃO
# ---------------------------------------------------------------

# Lê o arquivo .env e deixa as variáveis disponíveis para o programa
load_dotenv()

# A connection string vem do .env, nunca fica escrita no código
DATABASE_URL = os.getenv("DATABASE_URL")

# Endereço da API e nome da tabela em constantes (MAIÚSCULAS).
# Assim, se precisar mudar, muda em um lugar só e evita erro de digitação.
API_URL = "https://brasilapi.com.br/api/feriados/v1/2026"
TABELA = "feriados"

# ---------------------------------------------------------------
# EXTRACT: buscar os dados da API
# ---------------------------------------------------------------

# GET porque só queremos ler dados
resposta = requests.get(API_URL)

# Se a API devolver erro (404, 500...), o script para aqui com uma mensagem clara
resposta.raise_for_status()
print("Sucesso na chamada da API!")

# Converte o corpo da resposta (JSON) em uma lista de dicionários do Python
feriados_api = resposta.json()
print(f"Dados convertidos para JSON: {len(feriados_api)} feriados")

# ---------------------------------------------------------------
# TRANSFORM: tratar os dados
# ---------------------------------------------------------------

# Lista de dicionários -> DataFrame (tabela do pandas)
df = pd.DataFrame(feriados_api)
print("Dados convertidos para DataFrame")

# A API entrega a data como texto ("2026-01-01"); aqui vira data de verdade
df["date"] = pd.to_datetime(df["date"])
print("Coluna date convertida para datetime")

# Seleciona só as colunas que vão para o banco.
# .copy() cria uma cópia independente, para não alterar o df original.
df_banco = df[["date", "name", "type", "weekday"]].copy()

# Tira o horário (tudo é meia-noite) para combinar com o tipo DATE do Postgres
df_banco["date"] = df_banco["date"].dt.date

# ---------------------------------------------------------------
# LOAD: gravar no Postgres
# ---------------------------------------------------------------

# A conexão só é aberta aqui, perto de onde é usada.
# Assim, se a API falhar lá em cima, nenhuma conexão fica aberta à toa.
conexao = psycopg2.connect(DATABASE_URL)
cursor = conexao.cursor()

try:
    # Cria a tabela apenas se ainda não existir (evita erro na 2ª execução)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABELA} (
            date    DATE PRIMARY KEY,
            name    TEXT NOT NULL,
            type    TEXT NOT NULL,
            weekday TEXT NOT NULL
        );
    """)

    # Insere linha por linha.
    # Os %s são espaços reservados: os valores vão na tupla, e não colados no
    # texto do SQL. Isso protege contra SQL injection.
    for linha in df_banco.itertuples(index=False):
        cursor.execute(f"""
            INSERT INTO {TABELA} (date, name, type, weekday)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (date) DO UPDATE
            SET name    = EXCLUDED.name,
                type    = EXCLUDED.type,
                weekday = EXCLUDED.weekday;
        """, (linha.date, linha.name, linha.type, linha.weekday))
        # ON CONFLICT: se a data já existe, atualiza em vez de dar erro (upsert).
        # EXCLUDED representa a linha nova que tentamos inserir.

    # Só aqui as mudanças viram definitivas no banco
    conexao.commit()
    print(f"Dados salvos no banco: {len(df_banco)} linhas")

except Exception:
    # Se algo falhar no meio, desfaz tudo que ainda não foi confirmado,
    # para não deixar a tabela pela metade
    conexao.rollback()
    print("Erro ao gravar no banco. Alterações desfeitas.")
    raise  # relança o erro para você ver a mensagem completa

finally:
    # Roda sempre, deu certo ou deu erro: fecha o que foi aberto
    cursor.close()
    conexao.close()
