# -*- coding: utf-8 -*-
"""
Histórico de comparações: SQLite (metadados + tabela) + pasta com Excel exportados.
"""

import json
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime

import pandas as pd

# Caminhos na mesma pasta do app
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "historico_comparacoes.db"
PASTA_EXPORTACOES = BASE_DIR / "historico_exportacoes"


def _conectar():
    return sqlite3.connect(str(DB_PATH))


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
    """
    Salva uma comparação no SQLite e grava os Excel na pasta historico_exportacoes/<id>/.
    Retorna o id da run.
    """
    init_db()
    run_id = uuid.uuid4().hex
    data_hora = datetime.now().isoformat(sep=" ", timespec="seconds")

    comparacao_df = resultado["comparacao_df"]
    total_antiga = int(len(resultado["df_antiga_com_ano"]))
    total_nova = int(len(resultado["df_nova_com_ano"]))
    total_sairam = int(comparacao_df["Sairam"].sum())
    total_entraram = int(comparacao_df["Entraram"].sum())
    anos_todos = resultado["anos_todos"]

    config_json = json.dumps(config, ensure_ascii=False)
    anos_json = json.dumps(anos_todos)
    comparacao_df_json = comparacao_df.to_json(orient="records", date_format="iso")

    pasta_run = PASTA_EXPORTACOES / run_id
    pasta_run.mkdir(parents=True, exist_ok=True)

    # Salvar Excel da tabela de comparação
    (pasta_run / "Comparacao.xlsx").write_bytes(excel_comparacao_bytes)

    # Salvar Excel por ano
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
    """Lista todas as comparações (mais recente primeiro). Retorna lista de dicts."""
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
    """
    Retorna um dict com: comparacao_df, data_hora, nome_base_antiga, nome_base_nova,
    config, total_antiga, total_nova, total_sairam, total_entraram, anos_todos, pasta_export, arquivos.
    """
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
        comparacao_df = pd.read_json(row[9], orient="records")
        if "Ano" in comparacao_df.columns:
            comparacao_df["Ano"] = comparacao_df["Ano"].astype(int)

        pasta = Path(row[10]) if row[10] else None
        arquivos = list(pasta.iterdir()) if pasta and pasta.is_dir() else []

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
    """Remove a run do SQLite e apaga a pasta de exportações (se existir)."""
    run = get_run(run_id)
    if not run:
        return False
    conn = _conectar()
    try:
        conn.execute("DELETE FROM comparacoes WHERE id = ?", (run_id,))
        conn.commit()
    finally:
        conn.close()
    pasta = run.get("pasta_export")
    if pasta and isinstance(pasta, Path) and pasta.is_dir():
        import shutil
        try:
            shutil.rmtree(pasta)
        except Exception:
            pass
    return True
