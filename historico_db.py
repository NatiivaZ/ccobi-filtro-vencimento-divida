# -*- coding: utf-8 -*-
"""Camada de histórico do app.

Guarda os dados principais no SQLite e os arquivos exportados em pasta.
"""

import json
import sqlite3
import uuid
from io import StringIO
from pathlib import Path
from datetime import datetime

import pandas as pd

# Tudo fica ao lado do app para facilitar backup e uso local.
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "historico_comparacoes.db"
PASTA_EXPORTACOES = BASE_DIR / "historico_exportacoes"


def _conectar():
    return sqlite3.connect(str(DB_PATH))


def _serializar_json(payload):
    """Serializa o conteúdo do histórico sem perder acentuação."""
    return json.dumps(payload, ensure_ascii=False)


def _listar_arquivos_exportados(pasta):
    """Lista os arquivos de uma execução sempre na mesma ordem."""
    if pasta and pasta.is_dir():
        return sorted(pasta.iterdir())
    return []


def _remover_pasta_exportacao(pasta):
    """Tenta apagar a pasta da execução sem travar a limpeza se algo falhar."""
    if not (pasta and isinstance(pasta, Path) and pasta.is_dir()):
        return
    import shutil

    try:
        shutil.rmtree(pasta)
    except Exception:
        pass


def init_db():
    """Cria a tabela de comparações se não existir."""
    conn = _conectar()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS comparacoes (
                id TEXT PRIMARY KEY,
                data_hora TEXT NOT NULL,
                nome_base_antiga TEXT NOT NULL,
                nome_base_nova TEXT NOT NULL,
                config_json TEXT,
                total_antiga INTEGER NOT NULL,
                total_nova INTEGER NOT NULL,
                total_sairam INTEGER NOT NULL,
                total_entraram INTEGER NOT NULL,
                anos_json TEXT,
                comparacao_df_json TEXT NOT NULL,
                pasta_export TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()


def save_run(
    resultado,
    nome_base_antiga,
    nome_base_nova,
    config,
    excel_comparacao_bytes,
    excel_por_ano_dict,
):
    """Salva a execução atual no banco e grava os arquivos exportados."""
    init_db()
    run_id = uuid.uuid4().hex
    data_hora = datetime.now().isoformat(sep=" ", timespec="seconds")

    comparacao_df = resultado["comparacao_df"]
    total_antiga = int(len(resultado["df_antiga_com_ano"]))
    total_nova = int(len(resultado["df_nova_com_ano"]))
    total_sairam = int(comparacao_df["Sairam"].sum())
    total_entraram = int(comparacao_df["Entraram"].sum())
    anos_todos = resultado["anos_todos"]

    config_json = _serializar_json(config)
    anos_json = _serializar_json(anos_todos)
    comparacao_df_json = comparacao_df.to_json(orient="records", date_format="iso")

    pasta_run = PASTA_EXPORTACOES / run_id
    pasta_run.mkdir(parents=True, exist_ok=True)

    # A comparação principal sempre vai com um nome fixo para ficar fácil de achar.
    (pasta_run / "Comparacao.xlsx").write_bytes(excel_comparacao_bytes)

    # Os arquivos por ano ficam separados porque o app também mostra isso assim.
    for ano, bytes_ano in (excel_por_ano_dict or {}).items():
        (pasta_run / f"Autos_vencimento_{ano}.xlsx").write_bytes(bytes_ano)

    pasta_export_str = str(pasta_run)

    conn = _conectar()
    try:
        conn.execute(
            """
            INSERT INTO comparacoes (
                id, data_hora, nome_base_antiga, nome_base_nova, config_json,
                total_antiga, total_nova, total_sairam, total_entraram,
                anos_json, comparacao_df_json, pasta_export
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                data_hora,
                nome_base_antiga,
                nome_base_nova,
                config_json,
                total_antiga,
                total_nova,
                total_sairam,
                total_entraram,
                anos_json,
                comparacao_df_json,
                pasta_export_str,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return run_id


def list_runs():
    """Lista as execuções salvas, da mais recente para a mais antiga."""
    init_db()
    conn = _conectar()
    try:
        cur = conn.execute(
            """
            SELECT id, data_hora, nome_base_antiga, nome_base_nova,
                   total_antiga, total_nova, total_sairam, total_entraram
            FROM comparacoes
            ORDER BY data_hora DESC
            """
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "data_hora": r[1],
                "nome_base_antiga": r[2],
                "nome_base_nova": r[3],
                "total_antiga": r[4],
                "total_nova": r[5],
                "total_sairam": r[6],
                "total_entraram": r[7],
            }
            for r in rows
        ]
    finally:
        conn.close()


def get_run(run_id):
    """Recupera uma execução completa pelo id para reabrir no histórico."""
    conn = _conectar()
    try:
        cur = conn.execute(
            """
            SELECT data_hora, nome_base_antiga, nome_base_nova, config_json,
                   total_antiga, total_nova, total_sairam, total_entraram,
                   anos_json, comparacao_df_json, pasta_export
            FROM comparacoes WHERE id = ?
            """,
            (run_id,),
        )
        row = cur.fetchone()
        if not row:
            return None

        anos = json.loads(row[8])
        comparacao_df = pd.read_json(StringIO(row[9]), orient="records")
        if "Ano" in comparacao_df.columns:
            comparacao_df["Ano"] = comparacao_df["Ano"].astype(int)

        pasta = Path(row[10]) if row[10] else None
        arquivos = _listar_arquivos_exportados(pasta)

        return {
            "id": run_id,
            "data_hora": row[0],
            "nome_base_antiga": row[1],
            "nome_base_nova": row[2],
            "config": json.loads(row[3]) if row[3] else {},
            "total_antiga": row[4],
            "total_nova": row[5],
            "total_sairam": row[6],
            "total_entraram": row[7],
            "anos_todos": anos,
            "comparacao_df": comparacao_df,
            "pasta_export": pasta,
            "arquivos": arquivos,
        }
    finally:
        conn.close()


def excluir_run(run_id):
    """Exclui a execução e, se der, limpa a pasta que foi criada para ela."""
    run = get_run(run_id)
    if not run:
        return False
    conn = _conectar()
    try:
        conn.execute("DELETE FROM comparacoes WHERE id = ?", (run_id,))
        conn.commit()
    finally:
        conn.close()
    _remover_pasta_exportacao(run.get("pasta_export"))
    return True
