import os

import requests
import pandas as pd
from dotenv import load_dotenv
import psycopg2

# Lê cada linha do meu .env
load_dotenv()
conexao = psycopg2.connect(os.getenv("DATABASE_URL"))
cursor = conexao.cursor()

DATABASE_URL = os.getenv("DATABASE_URL")

# Criando a Variavel da url da api
URL = "https://brasilapi.com.br/api/feriados/v1/2026"

# Salvando os dados da api utilizando get
resposta = requests.get(URL)

# Validando se a resposta é 200 da api
resposta.raise_for_status()
print("Sucesso na Chamada da API!!")

# Convertendo a variavel resposta para json e salvando na variavel feriado
feriado = resposta.json()
print("Dados convertidos para JSON")

df = pd.DataFrame(feriado)
print("Dados convertidos para DataFrame")

df["date"] = pd.to_datetime(df["date"])
print("Date convetida para datatime")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS feriados (
        date DATE PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        weekday TEXT NOT NULL
    );
""")

df_banco = df[["date", "name", "type", "weekday"]].copy()
df_banco["date"] =  df_banco["date"].dt.date

for linha in df_banco.itertuples(index=False):
    cursor.execute("""
        INSERT INTO feriados (date, name, type, weekday)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (date) DO UPDATE
        SET name = EXCLUDED.name,
            type = EXCLUDED.type,
            weekday = EXCLUDED.weekday;
    """, (linha.date, linha.name, linha.type, linha.weekday))

print("Dados Salvo no Banco")
conexao.commit()
cursor.close()
conexao.close()