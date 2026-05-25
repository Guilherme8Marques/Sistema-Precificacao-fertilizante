"""ATOR 4 — EXECUTOR
Usa a Salesforce REST API para deletar registros em massa.
Substitui a aba 'Data Import' do Inspector (ação Delete).
"""

import time

from backend.config.settings import settings
from backend.utils.api_client import SalesforceAPIClient, SalesforceAuth
from backend.utils.safety import SafetyGuard
from backend.utils.logger import log
from backend.src.ator3_cerebro import ResultadoProcessamento


ACTOR_NAME = "EXECUTOR"


class Executor:
    """Deleta registros do Salesforce via API REST com segurança."""

    def __init__(self, auth: SalesforceAuth):
        self.client = SalesforceAPIClient(auth)
        self.safety = SafetyGuard()

    async def executar_delecao(self, resultado: ResultadoProcessamento,
                                objeto: str = "ProductsModifierEngine__c") -> dict:
        """Pipeline completo de deleção com backup e validação.

        Args:
            resultado: Output do Ator 3 (IDs + DataFrame de backup).
            objeto: Nome do objeto Salesforce.

        Returns:
            Relatório final da operação.
        """
        ids = resultado.ids_para_deletar
        total = len(ids)

        if total == 0:
            await log("WARNING", ACTOR_NAME, "Nenhum ID para deletar. Abortando.")
            return {"total_processados": 0, "deletados": 0, "falhos": 0}

        # ── 1. BACKUP ──────────────────────────────────
        motor_label = ", ".join(resultado.motores_encontrados[:3])
        caminho_backup = self.safety.backup_antes_delecao(
            ids, resultado.df_backup, motor_label
        )
        await log("SUCCESS", ACTOR_NAME,
                  f"Backup salvo: {caminho_backup}",
                  caminho=caminho_backup)

        # ── 2. VALIDAÇÃO ───────────────────────────────
        validacao = self.safety.validar_contagem(
            resultado.total_bruto, resultado.total_apos_filtro
        )
        await log("INFO", ACTOR_NAME,
                  f"Validação: {validacao['percent']} dos registros "
                  f"({validacao['total_filtrado']}/{validacao['total_bruto']})")

        # ── 3. DELEÇÃO ─────────────────────────────────
        await log("INFO", ACTOR_NAME,
                  f"Iniciando deleção de {total} registros...",
                  total=total)

        inicio = time.time()

        if total <= settings.BULK_THRESHOLD:
            resultados = await self._deletar_composite(ids, total)
        else:
            resultados = await self._deletar_bulk(objeto, ids, total)

        tempo = time.time() - inicio

        # ── 4. RELATÓRIO ───────────────────────────────
        relatorio = self.safety.gerar_relatorio(resultados, tempo, caminho_backup)

        level = "SUCCESS" if relatorio["falhos"] == 0 else "WARNING"
        await log(level, ACTOR_NAME,
                  f"Deleção concluída: {relatorio['deletados']} deletados, "
                  f"{relatorio['falhos']} falhos em {relatorio['tempo_execucao_s']}s",
                  **relatorio)

        return relatorio

    async def executar_insercao(self, payload: list[dict],
                                objeto: str = "ProductsModifierEngine__c") -> dict:
        """Insere registros no Salesforce com backup e relatório.

        Args:
            payload: Lista de dicts gerada pelo Precificador.
                     Cada registro contém: ModifierEngine__c, Product__r:Product2:ExternalID__c,
                     Discount__c, DateHourInitial__c, DateHourEnd__c.
            objeto: Nome do objeto Salesforce.

        Returns:
            Relatório final da operação.
        """
        total = len(payload)
        await log("INFO", ACTOR_NAME, f"Iniciando inserção de {total} registros...")

        if total == 0:
            await log("WARNING", ACTOR_NAME, "Nenhum registro para inserir. Abortando.")
            return {"total_processados": 0, "inseridos": 0, "falhos": 0}

        import time as _time

        inicio = _time.time()

        if total <= settings.BULK_THRESHOLD:
            resultados = await self._inserir_composite(payload, objeto, total)
        else:
            resultados = await self._inserir_bulk(payload, objeto, total)

        tempo = _time.time() - inicio

        inseridos = sum(1 for r in resultados if r.get("success"))
        falhos = total - inseridos

        relatorio = {
            "total_processados": total,
            "inseridos": inseridos,
            "falhos": falhos,
            "tempo_execucao_s": round(tempo, 2),
        }

        level = "SUCCESS" if falhos == 0 else "WARNING"
        await log(level, ACTOR_NAME,
                  f"Inserção concluída: {inseridos} inseridos, {falhos} falhos em {relatorio['tempo_execucao_s']}s",
                  **relatorio)

        return relatorio

    async def _inserir_composite(self, payload: list[dict],
                                  objeto: str, total: int) -> list[dict]:
        """Inserção via Composite API (batches de 200).

        A Composite API de insert usa o endpoint /sobjects/{objeto} em série.
        Para relacionamentos externos (Product__r:Product2:ExternalID__c) a notação
        com ponto-e-vírgula não é suportada via JSON; usamos Bulk API CSV para isso.
        Se o payload contiver External IDs de relacionamento, delega para Bulk.
        """
        # Verifica se há campos com notação de External ID (contêm "." ou ":")
        has_external_id = any(
            "." in key or ":" in key
            for rec in payload
            for key in rec.keys()
        )

        if has_external_id:
            await log("INFO", ACTOR_NAME,
                      "Payload contém External ID de relacionamento. Usando Bulk API CSV.")
            return await self._inserir_bulk(payload, objeto, total)

        batch_size = settings.COMPOSITE_BATCH_SIZE
        total_batches = (total + batch_size - 1) // batch_size

        await log("INFO", ACTOR_NAME,
                  f"Usando Composite API: {total_batches} batches de {batch_size}")

        all_results = []

        for i in range(0, total, batch_size):
            batch_num = (i // batch_size) + 1
            batch = payload[i:i + batch_size]

            await log("PROGRESS", ACTOR_NAME,
                      f"Inserindo batch {batch_num}/{total_batches} ({len(batch)} registros)...",
                      progress=round(batch_num / total_batches * 100, 1),
                      batch_current=batch_num,
                      batch_total=total_batches)

            batch_results = self.client.insert_composite(objeto, batch)
            all_results.extend(batch_results)

            success_count = sum(1 for r in batch_results if r.get("success"))
            fail_count = len(batch_results) - success_count

            if fail_count > 0:
                await log("WARNING", ACTOR_NAME,
                          f"Batch {batch_num}: {success_count} OK, {fail_count} falhas")

        return all_results

    async def _inserir_bulk(self, payload: list[dict],
                             objeto: str, total: int) -> list[dict]:
        """Inserção via Bulk API 2.0 usando CSV.

        O CSV usa a notação literal do Salesforce Inspector para External IDs,
        por exemplo: 'Product__r:Product2:ExternalID__c'
        """
        import io
        import csv

        await log("INFO", ACTOR_NAME,
                  f"Usando Bulk API 2.0 para {total} registros...")

        if not payload:
            return []

        # Monta CSV com todas as colunas do payload
        colunas = list(payload[0].keys())
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=colunas)
        writer.writeheader()
        for rec in payload:
            # Substitui None por string vazia (padrão CSV do Inspector)
            writer.writerow({k: ("" if v is None else v) for k, v in rec.items()})

        csv_content = output.getvalue()

        await log("PROGRESS", ACTOR_NAME,
                  f"CSV gerado: {total} linhas. Enviando para Bulk API...",
                  progress=30)

        job = self.client.insert_bulk(objeto, csv_content)

        state = job.get("state", "Unknown")
        records_processed = job.get("numberRecordsProcessed", 0)
        records_failed = job.get("numberRecordsFailed", 0)

        await log("INFO", ACTOR_NAME,
                  f"Job Bulk finalizado: state={state}, "
                  f"processados={records_processed}, falhas={records_failed}")

        # Monta resultados no mesmo formato do Composite
        results = []
        for rec in payload:
            results.append({
                "id": None,
                "success": state == "JobComplete",
                "errors": [] if state == "JobComplete" else [{"message": state}],
            })

        return results

    async def _deletar_composite(self, ids: list[str], total: int) -> list[dict]:
        """Deleção via Composite API (batches de 200)."""
        batch_size = settings.COMPOSITE_BATCH_SIZE
        total_batches = (total + batch_size - 1) // batch_size

        await log("INFO", ACTOR_NAME,
                  f"Usando Composite API: {total_batches} batches de {batch_size}")

        all_results = []

        for i in range(0, total, batch_size):
            batch_num = (i // batch_size) + 1
            batch = ids[i:i + batch_size]

            await log("PROGRESS", ACTOR_NAME,
                      f"Deletando batch {batch_num}/{total_batches} "
                      f"({len(batch)} registros)...",
                      progress=round(batch_num / total_batches * 100, 1),
                      batch_current=batch_num,
                      batch_total=total_batches)

            batch_results = self.client.delete_composite(batch)
            all_results.extend(batch_results)

            # Contagem parcial
            success_count = sum(1 for r in batch_results if r.get("success"))
            fail_count = len(batch_results) - success_count

            if fail_count > 0:
                await log("WARNING", ACTOR_NAME,
                          f"Batch {batch_num}: {success_count} OK, {fail_count} falhas")

        return all_results

    async def _deletar_bulk(self, objeto: str, ids: list[str],
                              total: int) -> list[dict]:
        """Deleção via Bulk API 2.0 (para grandes volumes)."""
        await log("INFO", ACTOR_NAME,
                  f"Usando Bulk API 2.0 para {total} registros...")

        job = self.client.delete_bulk(objeto, ids)

        state = job.get("state", "Unknown")
        records_processed = job.get("numberRecordsProcessed", 0)
        records_failed = job.get("numberRecordsFailed", 0)

        await log("INFO", ACTOR_NAME,
                  f"Job Bulk finalizado: state={state}, "
                  f"processados={records_processed}, falhas={records_failed}")

        # Monta resultados no mesmo formato do Composite
        results = []
        for id_ in ids:
            results.append({
                "id": id_,
                "success": state == "JobComplete",
                "errors": [] if state == "JobComplete" else [{"message": state}],
            })

        return results
