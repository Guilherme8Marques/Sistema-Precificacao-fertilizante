"""Camada de segurança — backup, validação e confirmação antes de deleções."""

import csv
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from backend.config.settings import settings


class SafetyGuard:
    """Proteções obrigatórias antes de qualquer operação destrutiva."""

    def backup_antes_delecao(self, ids: list[str], df: pd.DataFrame,
                              motor_label: str) -> str:
        """Salva backup CSV com todos os dados dos registros que serão deletados.

        Returns:
            Caminho absoluto do arquivo de backup.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_label = motor_label.replace(" ", "_").replace("/", "-")[:50]
        filename = f"backup_{timestamp}_{safe_label}.csv"
        filepath = settings.BACKUPS_DIR / filename

        df.to_csv(filepath, index=False, encoding="utf-8-sig")

        # Salva também lista pura de IDs (para referência rápida)
        ids_file = settings.BACKUPS_DIR / f"ids_{timestamp}_{safe_label}.txt"
        ids_file.write_text("\n".join(ids), encoding="utf-8")

        return str(filepath)

    def validar_contagem(self, total_bruto: int, total_filtrado: int,
                          threshold: float = 0.1) -> dict:
        """Verifica se a contagem de IDs está dentro do esperado.

        Args:
            total_bruto: Registros retornados pelo Salesforce.
            total_filtrado: Registros após filtros do Cérebro.
            threshold: Percentual máximo aceitável (10% por padrão).

        Returns:
            Dict com status da validação.
        """
        if total_bruto == 0:
            return {
                "valid": False,
                "reason": "Nenhum registro retornado do Salesforce.",
                "ratio": 0,
            }

        ratio = total_filtrado / total_bruto

        return {
            "valid": True,
            "ratio": round(ratio, 4),
            "total_bruto": total_bruto,
            "total_filtrado": total_filtrado,
            "percent": f"{ratio * 100:.1f}%",
        }

    def gerar_relatorio(self, resultados: list[dict], tempo_execucao: float,
                         caminho_backup: str) -> dict:
        """Gera relatório final da operação de deleção."""
        total = len(resultados)
        sucessos = sum(1 for r in resultados if r.get("success"))
        falhos = total - sucessos

        erros = []
        for r in resultados:
            if not r.get("success"):
                erros.append({
                    "id": r.get("id"),
                    "errors": r.get("errors", []),
                })

        return {
            "total_processados": total,
            "deletados": sucessos,
            "falhos": falhos,
            "erros": erros,
            "tempo_execucao_s": round(tempo_execucao, 2),
            "caminho_backup": caminho_backup,
            "timestamp": datetime.now().isoformat(),
        }

    def listar_backups(self) -> list[dict]:
        """Lista todos os backups disponíveis."""
        backups = []
        for f in sorted(settings.BACKUPS_DIR.glob("backup_*.csv"), reverse=True):
            backups.append({
                "filename": f.name,
                "path": str(f),
                "size_kb": round(f.stat().st_size / 1024, 1),
                "created": datetime.fromtimestamp(f.stat().st_ctime).isoformat(),
            })
        return backups
