"""Wrapper HTTP para a Salesforce REST API — gerencia auth, paginação e retry."""

import time
import requests
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

from backend.config.settings import settings


@dataclass
class SalesforceAuth:
    """Credenciais extraídas do browser."""
    session_id: str
    instance_url: str
    api_version: str = settings.SF_API_VERSION

    @property
    def headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.session_id}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        }

    @property
    def base_api_url(self) -> str:
        return f"{self.instance_url}/services/data/{self.api_version}"


class SalesforceAPIClient:
    """Cliente HTTP para operações REST no Salesforce."""

    def __init__(self, auth: SalesforceAuth):
        self.auth = auth
        self.session = requests.Session()
        self.session.headers.update(self.auth.headers)

    # ── SOQL Query (com paginação automática) ──────────

    def query(self, soql: str) -> list[dict]:
        """Executa SOQL e retorna todos os registros (paginação automática)."""
        url = f"{self.auth.base_api_url}/query"
        params = {"q": soql}
        all_records = []

        response = self._request("GET", url, params=params)
        data = response.json()
        all_records.extend(self._clean_records(data.get("records", [])))

        # Paginação
        while not data.get("done", True):
            next_url = f"{self.auth.instance_url}{data['nextRecordsUrl']}"
            response = self._request("GET", next_url)
            data = response.json()
            all_records.extend(self._clean_records(data.get("records", [])))

        return all_records

    # ── Delete via Composite API (batches de 200) ──────

    def delete_composite(self, ids: list[str], all_or_none: bool = False) -> list[dict]:
        """Deleta registros via Composite SObjects (máx 200 por chamada)."""
        url = f"{self.auth.base_api_url}/composite/sobjects"
        results = []
        batch_size = settings.COMPOSITE_BATCH_SIZE

        for i in range(0, len(ids), batch_size):
            batch = ids[i:i + batch_size]
            ids_param = ",".join(batch)
            params = {
                "ids": ids_param,
                "allOrNone": str(all_or_none).lower(),
            }
            response = self._request("DELETE", url, params=params)
            batch_results = response.json()

            for result in batch_results:
                results.append({
                    "id": result.get("id"),
                    "success": result.get("success"),
                    "errors": result.get("errors", []),
                })

            # Intervalo para não estourar rate limit
            if i + batch_size < len(ids):
                time.sleep(0.5)

        return results

    # ── Insert via Composite API (batches de 200) ──────

    def insert_composite(self, object_name: str, records: list[dict]) -> list[dict]:
        """Insere registros via Composite SObjects (máx 200 por chamada).

        Args:
            object_name: Nome do objeto Salesforce (ex: ProductsModifierEngine__c).
            records: Lista de dicts com os campos a inserir.

        Returns:
            Lista de resultados no formato {"id": str, "success": bool, "errors": list}.
        """
        url = f"{self.auth.base_api_url}/composite/sobjects/{object_name}"
        results = []
        batch_size = settings.COMPOSITE_BATCH_SIZE

        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            payload = {"records": [{"attributes": {"type": object_name}, **r} for r in batch]}
            response = self._request("POST", url, json=payload)
            batch_results = response.json()

            for result in batch_results:
                results.append({
                    "id": result.get("id"),
                    "success": result.get("success"),
                    "errors": result.get("errors", []),
                })

            # Intervalo para não estourar rate limit
            if i + batch_size < len(records):
                time.sleep(0.5)

        return results

    # ── Bulk API 2.0 (para grandes volumes) ────────────

    def delete_bulk(self, object_name: str, ids: list[str]) -> dict:
        """Deleta registros via Bulk API 2.0 (para > 10K registros)."""
        base = f"{self.auth.base_api_url}/jobs/ingest"

        # 1. Criar job com terminação de linha explícita LF
        job_payload = {
            "object": object_name,
            "operation": "delete",
            "contentType": "CSV",
            "lineEnding": "LF",
        }
        job_response = self._request("POST", base, json=job_payload)
        job = job_response.json()
        job_id = job["id"]

        # 2. Upload CSV (apenas coluna Id)
        csv_data = "Id\n" + "\n".join(ids)
        upload_url = f"{base}/{job_id}/batches"
        self._request(
            "PUT", upload_url,
            data=csv_data.encode("utf-8"),
            headers_override={"Content-Type": "text/csv"},
        )

        # 3. Fechar job
        self._request("PATCH", f"{base}/{job_id}", json={"state": "UploadComplete"})

        # 4. Monitorar até conclusão
        return self._poll_job(f"{base}/{job_id}")

    # ── Insert via Bulk API 2.0 (para grandes volumes) ─

    def insert_bulk(self, object_name: str, csv_content: str) -> dict:
        """Insere registros via Bulk API 2.0 a partir de um CSV.

        O CSV deve ter cabeçalho na primeira linha. O campo de relacionamento
        deve usar a notação padrão do Salesforce: 'Product__r.ExternalID__c'.

        Args:
            object_name: Ex: ProductsModifierEngine__c.
            csv_content: String CSV com cabeçalho + linhas de dados.

        Returns:
            Dict com estado final do job Bulk.
        """
        base = f"{self.auth.base_api_url}/jobs/ingest"

        # 1. Criar job de insert com terminação de linha explícita CRLF
        job_payload = {
            "object": object_name,
            "operation": "insert",
            "contentType": "CSV",
            "lineEnding": "CRLF",
        }
        job_response = self._request("POST", base, json=job_payload)
        job = job_response.json()
        job_id = job["id"]

        # 2. Upload CSV
        upload_url = f"{base}/{job_id}/batches"
        self._request(
            "PUT", upload_url,
            data=csv_content.encode("utf-8"),
            headers_override={"Content-Type": "text/csv"},
        )

        # 3. Fechar job
        self._request("PATCH", f"{base}/{job_id}", json={"state": "UploadComplete"})

        # 4. Monitorar até conclusão
        return self._poll_job(f"{base}/{job_id}")

    # ── Validar conexão ────────────────────────────────

    def test_connection(self) -> bool:
        """Testa se o session_id é válido."""
        try:
            url = f"{self.auth.base_api_url}/limits"
            self._request("GET", url)
            return True
        except Exception:
            return False

    # ── Internos ───────────────────────────────────────

    def _request(self, method: str, url: str, headers_override: Optional[dict] = None,
                 **kwargs) -> requests.Response:
        """Executa request HTTP com retry."""
        headers = {**self.session.headers}
        if headers_override:
            headers.update(headers_override)

        for attempt in range(settings.MAX_RETRIES):
            try:
                resp = self.session.request(method, url, headers=headers,
                                            timeout=settings.REQUEST_TIMEOUT, **kwargs)
                if resp.status_code == 401:
                    raise AuthExpiredError("Session ID expirado. Re-autentique.")
                if resp.status_code >= 500:
                    if attempt < settings.MAX_RETRIES - 1:
                        time.sleep(2 ** attempt)
                        continue
                resp.raise_for_status()
                return resp
            except requests.exceptions.Timeout:
                if attempt < settings.MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise

        raise RuntimeError(f"Falha após {settings.MAX_RETRIES} tentativas: {url}")

    def _clean_records(self, records: list[dict]) -> list[dict]:
        """Remove metadados do Salesforce (attributes) dos registros."""
        cleaned = []
        for record in records:
            clean = {}
            for key, value in record.items():
                if key == "attributes":
                    continue
                if isinstance(value, dict) and "attributes" in value:
                    # Flatten relacionamentos (ex: ModifierEngine__r.Name)
                    for sub_key, sub_val in value.items():
                        if sub_key != "attributes":
                            clean[f"{key}.{sub_key}"] = sub_val
                else:
                    clean[key] = value
            cleaned.append(clean)
        return cleaned

    def _poll_job(self, job_url: str, interval: int = 3, max_wait: int = 600) -> dict:
        """Monitora job Bulk API até conclusão."""
        elapsed = 0
        while elapsed < max_wait:
            resp = self._request("GET", job_url)
            job = resp.json()
            state = job.get("state")
            if state in ("JobComplete", "Failed", "Aborted"):
                return job
            time.sleep(interval)
            elapsed += interval
        raise TimeoutError(f"Job Bulk API não concluiu em {max_wait}s")


class AuthExpiredError(Exception):
    """Session ID expirado — precisa re-autenticar."""
    pass
