"""ATOR 3 — CÉREBRO
Usa Pandas para cruzar, limpar e filtrar dados.
Substitui toda a lógica de Excel (PROCV, filtros manuais).

Fluxo real do processo manual:
1. Usuário tem uma lista de códigos de produtos (Código CXP = ProductCode__c)
2. Sistema consulta SF → todos os ProductsModifierEngine__c ativos
3. PROCV: cruza códigos do usuário com dados do SF
4. Remove N/D (produtos sem match)
5. Filtra por motores/campanhas selecionados
6. Extrai IDs dos registros que serão deletados
"""

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from backend.config.settings import settings
from backend.utils.logger import log


ACTOR_NAME = "CÉREBRO"


@dataclass
class ResultadoProcessamento:
    """Resultado do processamento do Cérebro."""
    ids_para_deletar: list[str]
    total_bruto: int
    total_codigos_input: int
    total_apos_merge: int
    total_apos_filtro: int
    df_backup: pd.DataFrame
    motores_encontrados: list[str] = field(default_factory=list)


class Cerebro:
    """Processa dados extraídos do Salesforce e produz lista de IDs para deleção."""

    async def processar(self, dados_brutos: list[dict],
                         codigos_alvo: list[str],
                         motores_selecionados: list[str]) -> ResultadoProcessamento:
        """Pipeline completo de transformação.

        Args:
            dados_brutos: Registros vindos do Ator 2 (todos os ProductsModifierEngine__c ativos).
            codigos_alvo: Lista de ProductCode__c fornecidos pelo usuário (Código CXP).
            motores_selecionados: Nomes dos motores selecionados na UI.

        Returns:
            ResultadoProcessamento com IDs prontos para deleção.
        """
        total_bruto = len(dados_brutos)
        total_codigos = len(codigos_alvo)
        await log("INFO", ACTOR_NAME,
                  f"Iniciando processamento: {total_bruto} registros SF × {total_codigos} códigos alvo")

        # ── 1. Converter para DataFrame ────────────────
        df = pd.DataFrame(dados_brutos)
        await log("INFO", ACTOR_NAME,
                  f"DataFrame criado: {df.shape[0]} linhas x {df.shape[1]} colunas")

        # ── 2. Garantir tipo string no ProductCode__c ──
        df["ProductCode__c"] = df["ProductCode__c"].astype(str).str.strip()
        codigos_limpos = [str(c).strip() for c in codigos_alvo if str(c).strip()]

        await log("INFO", ACTOR_NAME,
                  f"Códigos alvo (amostra): {codigos_limpos[:5]}...")

        # ── 3. PROCV: cruzar códigos do usuário com SF ─
        #    Equivalente a: "Em quais motores esses produtos estão inseridos?"
        df_merged = df[df["ProductCode__c"].isin(codigos_limpos)].copy()
        total_apos_merge = len(df_merged)

        await log("INFO", ACTOR_NAME,
                  f"Após cruzamento (PROCV): {total_apos_merge} registros encontrados "
                  f"(de {total_bruto} totais)")

        if total_apos_merge == 0:
            await log("WARNING", ACTOR_NAME,
                      "Nenhum código alvo encontrado no Salesforce. Verifique os códigos.")
            return ResultadoProcessamento(
                ids_para_deletar=[],
                total_bruto=total_bruto,
                total_codigos_input=total_codigos,
                total_apos_merge=0,
                total_apos_filtro=0,
                df_backup=pd.DataFrame(),
                motores_encontrados=motores_selecionados,
            )

        # ── 4. Remover N/D (nulos) ─────────────────────
        df_merged = df_merged.dropna(subset=["Id", "ProductCode__c"])
        await log("INFO", ACTOR_NAME,
                  f"Após remover nulos: {len(df_merged)} registros")

        # ── 5. Filtrar por motores selecionados ────────
        df_filtrado = await self._filtrar_motores(df_merged, motores_selecionados)
        total_apos_filtro = len(df_filtrado)

        # ── 6. Extrair IDs limpos ──────────────────────
        ids = df_filtrado["Id"].dropna().unique().tolist()

        await log("SUCCESS", ACTOR_NAME,
                  f"Processamento concluído: {len(ids)} IDs prontos para deleção.",
                  total_bruto=total_bruto,
                  total_codigos=total_codigos,
                  total_apos_merge=total_apos_merge,
                  total_apos_filtro=total_apos_filtro)

        return ResultadoProcessamento(
            ids_para_deletar=ids,
            total_bruto=total_bruto,
            total_codigos_input=total_codigos,
            total_apos_merge=total_apos_merge,
            total_apos_filtro=total_apos_filtro,
            df_backup=df_filtrado,
            motores_encontrados=motores_selecionados,
        )

    async def _filtrar_motores(self, df: pd.DataFrame,
                                 motores: list[str]) -> pd.DataFrame:
        """Filtra DataFrame pelos motores selecionados na UI."""
        if not motores:
            await log("WARNING", ACTOR_NAME, "Nenhum motor selecionado. Retornando todos.")
            return df

        col = "ModifierEngine__r.Name"
        if col not in df.columns:
            await log("ERROR", ACTOR_NAME,
                      f"Coluna '{col}' não encontrada. Colunas: {list(df.columns)}")
            return df

        # Filtro exato pelos motores selecionados
        mask = df[col].isin(motores)
        df_filtrado = df[mask].copy()

        await log("INFO", ACTOR_NAME,
                  f"Filtro de motores: {len(df_filtrado)} registros "
                  f"em {len(motores)} motor(es)")

        # Log detalhado por motor
        for motor in motores:
            count = len(df_filtrado[df_filtrado[col] == motor])
            await log("INFO", ACTOR_NAME, f"  → {motor}: {count} registros")

        return df_filtrado
