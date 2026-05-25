"""ATOR 2 — EXTRATOR
Usa a Salesforce REST API para executar queries SOQL e retornar dados brutos.
Substitui completamente a aba 'Data Export' do Inspector.
"""

from typing import Optional

from backend.config.soql_queries import SOQLQueries
from backend.utils.api_client import SalesforceAPIClient, SalesforceAuth
from backend.utils.logger import log


ACTOR_NAME = "EXTRATOR"


class Extrator:
    """Executa queries SOQL via API REST e retorna dados brutos."""

    def __init__(self, auth: SalesforceAuth):
        self.client = SalesforceAPIClient(auth)

    async def extrair_produtos_motor(self, codigos: Optional[list[str]] = None) -> list[dict]:
        """Extrai produtos de motores ativos, filtrando por códigos se fornecido.

        Args:
            codigos: Lista de ProductCode__c para filtrar. Se None, não filtra.

        Returns:
            Lista de dicts com os registros do Salesforce.
        """
        await log("INFO", ACTOR_NAME, "Validando conexão com Salesforce...")

        if not self.client.test_connection():
            raise ConnectionError("Session ID inválido. Re-autentique.")

        await log("SUCCESS", ACTOR_NAME, "Conexão validada.")

        # Constrói a query SOQL
        soql = SOQLQueries.PRODUTOS_MOTOR_BASE

        if codigos:
            codigos_limpos = [str(c).strip() for c in codigos if str(c).strip()]
            if codigos_limpos:
                # Formata a lista para a cláusula IN do SOQL ('111', '222')
                in_clause = ", ".join(f"'{c}'" for c in codigos_limpos)
                soql += f" AND ProductCode__c IN ({in_clause})"

        await log("INFO", ACTOR_NAME, "Executando SOQL: ProductsModifierEngine__c...")

        dados = self.client.query(soql)

        await log("SUCCESS", ACTOR_NAME,
                  f"{len(dados)} registros extraídos do Salesforce.",
                  total=len(dados))

        # Log de motores únicos encontrados
        motores = set()
        for registro in dados:
            nome = registro.get("ModifierEngine__r.Name", "")
            if nome:
                motores.add(nome)

        await log("INFO", ACTOR_NAME,
                  f"{len(motores)} motores ativos encontrados.",
                  motores=sorted(list(motores)))

        return dados

    async def listar_motores_ativos(self) -> list[str]:
        """Retorna lista de nomes únicos de motores ativos (para o dropdown da UI)."""
        await log("INFO", ACTOR_NAME, "Buscando lista de motores ativos...")

        dados = self.client.query(SOQLQueries.PRODUTOS_MOTOR_BASE)

        motores = sorted(set(
            r.get("ModifierEngine__r.Name", "")
            for r in dados
            if r.get("ModifierEngine__r.Name")
        ))

        await log("SUCCESS", ACTOR_NAME,
                  f"{len(motores)} motores encontrados.",
                  motores=motores)

        return motores

    async def listar_motores_completos(self) -> list[dict]:
        """Busca todos os motores (ativos e inativos), suas filiais e campanhas associadas."""
        await log("INFO", ACTOR_NAME, "Buscando todos os motores com filiais e campanhas...")

        # 1. Query direta ao objeto principal de motores para garantir nomes reais e status ativo
        soql_motores = "SELECT Id, Name, IsActive__c FROM ModifierEngine__c"
        dados_motores = self.client.query(soql_motores)

        # 2. Query de Filiais (BranchModifierEngine__c)
        soql_filiais = """
            SELECT ModifierEngine__c, Branch__r.Name
            FROM BranchModifierEngine__c
        """
        dados_filiais = self.client.query(soql_filiais)

        # 3. Query de Campanhas (CampaignModifierEngine__c)
        soql_campanhas = """
            SELECT ModifierEngine__c, Campaign__r.Name
            FROM CampaignModifierEngine__c
        """
        dados_campanhas = self.client.query(soql_campanhas)

        # Agrupa filiais por motor
        filiais_por_motor = {}  # {motor_id: list of branch names}
        for r in dados_filiais:
            mid = r.get("ModifierEngine__c")
            fname = r.get("Branch__r.Name", "")
            if mid and fname:
                if mid not in filiais_por_motor:
                    filiais_por_motor[mid] = []
                if fname not in filiais_por_motor[mid]:
                    filiais_por_motor[mid].append(fname)

        # Agrupa campanhas por motor
        campanhas_por_motor = {}  # {motor_id: list of campaign names}
        for r in dados_campanhas:
            mid = r.get("ModifierEngine__c")
            cname = r.get("Campaign__r.Name", "")
            if mid and cname:
                if mid not in campanhas_por_motor:
                    campanhas_por_motor[mid] = []
                if cname not in campanhas_por_motor[mid]:
                    campanhas_por_motor[mid].append(cname)

        motores_list = []
        for m in dados_motores:
            mid = m.get("Id")
            name = m.get("Name", mid)
            is_active = m.get("IsActive__c", True)
            
            filiais = filiais_por_motor.get(mid, [])
            campanhas = campanhas_por_motor.get(mid, [])

            # UF principal do motor com base nas filiais ou nome
            from backend.src.ator5_precificador import _uf_para_filial
            uf = _uf_para_filial(filiais[0]) if filiais else _uf_para_filial(name)

            motores_list.append({
                "id": mid,
                "name": name,
                "filiais": filiais,
                "campanhas": campanhas,
                "uf": uf,
                "active": is_active
            })

        # Ordena por nome do motor para exibição consistente
        motores_ordenados = sorted(motores_list, key=lambda x: x["name"])

        await log("SUCCESS", ACTOR_NAME,
                  f"{len(motores_ordenados)} motores mapeados com filiais e campanhas.",
                  total=len(motores_ordenados))

        return motores_ordenados



    async def buscar_campanhas_por_motores(self, motor_ids: list[str]) -> list[dict]:
        """Busca campanhas vinculadas aos motores via CampaignModifierEngine__c.

        Args:
            motor_ids: Lista de ModifierEngine__c IDs.

        Returns:
            Lista de dicts com {campaign_id, campaign_name, motor_id, motor_name}.
        """
        if not motor_ids:
            return []

        await log("INFO", ACTOR_NAME, f"Buscando campanhas para {len(motor_ids)} motores...")

        # Divide em lotes de 150 para não estourar limite SOQL
        resultados = []
        lotes = [motor_ids[i:i + 150] for i in range(0, len(motor_ids), 150)]

        for lote in lotes:
            in_clause = ", ".join(f"'{mid}'" for mid in lote)
            soql = f"""
                SELECT Id, ModifierEngine__c, ModifierEngine__r.Name,
                       ModifierEngine__r.IsActive__c,
                       Campaign__r.Name, Campaign__c
                FROM CampaignModifierEngine__c
                WHERE ModifierEngine__c IN ({in_clause})
            """
            dados = self.client.query(soql)
            resultados.extend(dados)

        # Agrupa por campanha
        campanhas = set()
        for r in resultados:
            camp_name = r.get("Campaign__r.Name", "")
            if camp_name:
                campanhas.add(camp_name)

        await log("SUCCESS", ACTOR_NAME,
                  f"{len(campanhas)} campanhas encontradas para {len(motor_ids)} motores.")

        return resultados
