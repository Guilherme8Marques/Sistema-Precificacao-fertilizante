"""Ator 5: Precificador — Lê a planilha, calcula preços e prepara payload para inserção.

Regras de negócio implementadas:
- A planilha fornece APENAS: CÓDIGO (col B), CUSTO (col H/I) e MARGEM (col AS).
- O Preço de Partida é calculado: (Custo / (1 - Margem)) * 1.0069 / 0.99075
- O desconto é calculado usando o catálogo de preço CORRETO por estado (MG ou SP).
- O payload de inserção segue o mapeamento exato exigido pelo Salesforce Inspector:
  * Product__r:Product2:ExternalID__c = SKU (código CXP)
  * ModifierEngine__c = ID do motor selecionado
  * Discount__c = desconto calculado (0.0 a 1.0)
  * DateHourInitial__c = 7:00 AM do dia anterior (auto-injetado)
  * DateHourEnd__c = vazio (null)
"""

import datetime
import re
import unicodedata
import pandas as pd
from typing import List, Dict, Any, Optional
from backend.config.settings import settings
from backend.utils.logger import log
from backend.utils.api_client import SalesforceAuth


# ── Mapeamento de Filiais por Estado ────────────────────────────────────────
# Chave: substring do nome da filial (case-insensitive)
# Valor: "SP" ou "MG"
# Este mapeamento é usado para escolher o catálogo correto de preços no PricebookEntry.
FILIAIS_ESTADO: Dict[str, str] = {
    # São Paulo
    "caconde":           "SP",
    "altinopolis":       "SP",
    "altinópolis":       "SP",
    "espirito santo":    "SP",
    "espírito santo":    "SP",
    "são josé do rio pardo": "SP",
    "sao jose do rio pardo": "SP",
    "cachoeira":         "SP",
    "franca":            "SP",
    "serra negra":       "SP",
    # Minas Gerais (todos os demais são MG)
    "alfenas":           "MG",
    "alpinopolis":       "MG",
    "alpinópolis":       "MG",
    "andradas":          "MG",
    "boa esperanca":     "MG",
    "boa esperança":     "MG",
    "botelhos":          "MG",
    "cabo verde":        "MG",
    "campestre":         "MG",
    "campos gerais":     "MG",
    "carmo do rio":      "MG",
    "conceicao":         "MG",
    "conceição":         "MG",
    "guaranesia":        "MG",
    "guaranésia":        "MG",
    "guaxupe":           "MG",
    "guaxupé":           "MG",
    "ibiraci":           "MG",
    "itamogi":           "MG",
    "lambari":           "MG",
    "machado":           "MG",
    "monte belo":        "MG",
    "monte carmelo":     "MG",
    "monte santo":       "MG",
    "muzambinho":        "MG",
    "nepomuceno":        "MG",
    "nova resende":      "MG",
    "piumhi":            "MG",
    "piumhí":            "MG",
    "rio paranaiba":     "MG",
    "rio paranaíba":     "MG",
    "santo antonio":     "MG",
    "santo antônio":     "MG",
    "sao pedro":         "MG",
    "são pedro":         "MG",
    "sao sebastiao":     "MG",
    "são sebastião":     "MG",
    "serra do salitre":  "MG",
    "patrocinio":        "MG",
    "patrocínio":        "MG",
    "coromandel":        "MG",
    "araguari":          "MG",
    "campos altos":      "MG",
}


def _uf_para_filial(nome_filial: str) -> str:
    """Determina a UF (MG ou SP) de uma filial pelo nome.
    Padrão: MG se não encontrar correspondência.
    """
    nome_lower = nome_filial.lower()
    for chave, uf in FILIAIS_ESTADO.items():
        if chave in nome_lower:
            return uf
    return "MG"  # fallback: maioria das filiais é MG


def _normalizar_nome(nome: str) -> str:
    """Normaliza nome de filial para cruzamento entre Salesforce e planilha.

    Remove prefixos como 'L09:', 'Loja', 'Unidade Avançada', acentos e converte para UPPER.
    Exemplos:
        'L09:Loja Alfenas'                        → 'ALFENAS'
        '311:Unidade Avançada Andradas'            → 'ANDRADAS'
        '301:Unidade Avançada Conceição Aparecida' → 'CONCEICAO APARECIDA'
        'CONCEIÇÃO APARECIDA'                      → 'CONCEICAO APARECIDA'
    """
    # Remove prefixo numérico (ex: '076:', 'L09:', '311:')
    nome = re.sub(r'^[A-Za-z]?\d+:', '', nome).strip()
    # Remove prefixos comuns do Salesforce
    nome = re.sub(r'^(Loja|Unidade\s+Avan[çc]ada)\s*', '', nome, flags=re.IGNORECASE).strip()
    # Remove acentos via NFKD
    nfkd = unicodedata.normalize('NFKD', nome)
    sem_acento = ''.join(c for c in nfkd if not unicodedata.combining(c))
    res = sem_acento.upper().strip()
    # Se contiver 'MATRIZ', mapeia para 'GUAXUPE' (sede da Cooxupé)
    if "MATRIZ" in res:
        return "GUAXUPE"
    return res


def _calcular_date_hour_initial() -> str:
    """Retorna 7:00 AM do dia anterior no formato ISO aceito pelo Salesforce.
    Exemplo: '2026-05-17T07:00:00.000Z'
    """
    ontem = datetime.date.today() - datetime.timedelta(days=1)
    dt = datetime.datetime.combine(ontem, datetime.time(7, 0))
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


class Precificador:
    def __init__(self, auth: SalesforceAuth):
        self.auth = auth
        self.temp_file = settings.PLANILHAS_DIR / "temp_upload.xlsx"

    # ────────────────────────────────────────────────────────────────────────
    # Preview Unificado — retorna TODOS os registros com filial + campanha
    # ────────────────────────────────────────────────────────────────────────
    async def preview_unificado(
        self,
        motores_selecionados: List[Dict[str, str]],
        campanhas_por_motor: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Calcula preços para TODOS os produtos × motores, com info de filial e campanha.

        Args:
            motores_selecionados: Lista de {"id": "a0B...", "name": "Motor Name"}.
            campanhas_por_motor: Dict {motor_id: "Campaign Name"} para enriquecer preview.

        Returns:
            Dict com detalhes completos por produto × motor.
        """
        await log("INFO", "ATOR 5", "Iniciando cálculo de Preços de Partida e Descontos...")

        if not self.temp_file.exists():
            raise FileNotFoundError("Planilha não encontrada. Faça o upload novamente.")

        produtos = self._extrair_produtos_planilha()
        if not produtos:
            raise ValueError("Nenhum produto válido (com Código, Custo e Margem) encontrado na planilha.")

        await log("INFO", "ATOR 5", f"{len(produtos)} produtos extraídos da planilha.")

        codigos = [p["codigo"] for p in produtos]
        await log("PROGRESS", "ATOR 5", "Buscando preços de catálogo (MG e SP) no Salesforce...", progress=30)
        precos_erp = await self._buscar_precos_erp(codigos)

        await log("PROGRESS", "ATOR 5", "Calculando descontos por produto e motor...", progress=60)

        produtos_com_desconto = self._calcular_descontos(
            produtos, precos_erp, motores_selecionados, campanhas_por_motor
        )
        total = len(produtos_com_desconto)

        await log(
            "SUCCESS", "ATOR 5",
            f"Cálculo concluído! {len(produtos)} produtos × {len(motores_selecionados)} motores "
            f"= {total} registros para inserir."
        )

        return {
            "produtos_lidos": len(produtos),
            "produtos_calculados": total,
            "motores_selecionados": len(motores_selecionados),
            "insercoes_projetadas": total,
            "detalhes": produtos_com_desconto,  # ALL records, not sample
        }

    # ────────────────────────────────────────────────────────────────────────
    # PASSO 2: Gera o payload completo de inserção (usado pelo Executor)
    # ────────────────────────────────────────────────────────────────────────
    async def gerar_payload_insercao(self, motores_selecionados: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Gera a lista de registros prontos para inserção no Salesforce.

        Cada registro contém:
          - ModifierEngine__c: ID do motor
          - Product__r:Product2:ExternalID__c: SKU (código CXP do produto)
          - Discount__c: desconto calculado (decimal, ex: 0.0991)
          - DateHourInitial__c: 7:00 AM do dia anterior (ISO)
          - DateHourEnd__c: null
        """
        await log("INFO", "ATOR 5", "Gerando payload de inserção...")

        if not self.temp_file.exists():
            raise FileNotFoundError("Planilha não encontrada. Faça o upload novamente.")

        produtos = self._extrair_produtos_planilha()
        if not produtos:
            raise ValueError("Nenhum produto válido encontrado na planilha.")

        codigos = [p["codigo"] for p in produtos]
        precos_erp = await self._buscar_precos_erp(codigos)

        registros = self._calcular_descontos(produtos, precos_erp, motores_selecionados)

        date_hour_initial = _calcular_date_hour_initial()

        payload = []
        for rec in registros:
            payload.append({
                "ModifierEngine__c": rec["motor_id"],
                "Product__r.ExternalID__c": rec["codigo"],
                "Discount__c": rec["desconto"],
                "DateHourInitial__c": date_hour_initial,
                "DateHourEnd__c": None,
            })

        await log("INFO", "ATOR 5",
                  f"Payload gerado: {len(payload)} registros. DateHourInitial={date_hour_initial}")
        return payload

    # ────────────────────────────────────────────────────────────────────────
    # Internos
    # ────────────────────────────────────────────────────────────────────────

    def _extrair_produtos_planilha(self) -> List[Dict[str, Any]]:
        """Lê a planilha Template e extrai Código, Custos por Filial e Margem.

        Estrutura esperada na planilha (referência das linhas do Excel):
          - Linha 2 do Excel (Row 1 no pandas): "CUSTO" na coluna H
          - Linha 3 do Excel (Row 2 no pandas): Nomes das filiais + "MARGEM" na última coluna útil
          - Linha 4 do Excel (Row 3 no pandas): "Código", "Descrição", "Unidade"
          - Linha 7 do Excel em diante (Row 6+ no pandas): Dados dos produtos

        A detecção das colunas é DINÂMICA — funciona independente da quantidade de filiais.
        """
        df = pd.read_excel(self.temp_file, engine="openpyxl", header=None)

        # 1. Detecta col_codigo buscando "Código" nos cabeçalhos (linhas 0-5)
        col_codigo = -1
        for row_idx in range(min(6, len(df))):
            headers = df.iloc[row_idx].astype(str).str.strip().str.upper().tolist()
            for i, val in enumerate(headers):
                if col_codigo == -1 and ("CÓDIGO" in val or "CODIGO" in val):
                    col_codigo = i
            if col_codigo != -1:
                break
        if col_codigo == -1:
            col_codigo = 0  # Fallback: Coluna A

        # 2. Detecta col_margem buscando "MARGEM" na Row 2 (linha dos nomes de filiais)
        col_margem = -1
        row2 = df.iloc[2].astype(str).str.strip().str.upper().tolist() if len(df) > 2 else []
        for i, val in enumerate(row2):
            if "MARGEM" in val:
                col_margem = i
                break
        if col_margem == -1:
            col_margem = df.shape[1] - 1  # Fallback: última coluna

        # 3. Detecta colunas de custo por filial DINAMICAMENTE na Row 2
        #    Todas as colunas entre a primeira filial e a coluna MARGEM
        filial_cols = {}  # {NOME_NORMALIZADO: col_index}
        for c in range(df.shape[1]):
            if c >= col_margem:
                break
            val = str(df.iloc[2, c]).strip()
            if val and val.upper() != 'NAN' and val.upper() != 'MARGEM':
                nome_norm = _normalizar_nome(val)
                if nome_norm:
                    filial_cols[nome_norm] = c

        # 4. Extrai produtos com custos por filial
        produtos = []
        for _, row in df.iterrows():
            codigo_raw = str(row.iloc[col_codigo]).strip()
            if codigo_raw.endswith(".0"):
                codigo_raw = codigo_raw[:-2]
            if not codigo_raw.isdigit():
                continue

            try:
                margem_val = row.iloc[col_margem]
                margem = float(margem_val) if pd.notna(margem_val) else 0.0
                if margem >= 1.0:
                    margem = 0.0

                # Extrai custo de cada filial
                custos_por_filial = {}
                for nome_norm, col_idx in filial_cols.items():
                    custo_val = row.iloc[col_idx]
                    if pd.notna(custo_val):
                        try:
                            custo = float(custo_val)
                            if custo > 0:
                                custos_por_filial[nome_norm] = custo
                        except (ValueError, TypeError):
                            pass

                if not custos_por_filial:
                    continue

                produtos.append({
                    "codigo": codigo_raw,
                    "margem": margem,
                    "custos_por_filial": custos_por_filial,
                })
            except (ValueError, TypeError):
                continue

        return produtos

    def _calcular_descontos(
        self,
        produtos: List[Dict[str, Any]],
        precos_erp: Dict[str, Dict[str, float]],
        motores_selecionados: List[Dict[str, Any]],
        campanhas_por_motor: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Cruza produtos × motores, usando custo ESPECÍFICO da filial do motor.

        Args:
            produtos: Lista de {"codigo", "margem", "custos_por_filial": {FILIAL_NORM: custo}}.
            precos_erp: {"SKU": {"MG": preço, "SP": preço}}.
            motores_selecionados: [{"id": "a0B...", "name": "Alfenas", "filiais": [...], "uf": "MG"}, ...].
            campanhas_por_motor: {motor_id: "Campaign Name"} (opcional).

        Returns:
            Lista de registros com desconto calculado.
        """
        if campanhas_por_motor is None:
            campanhas_por_motor = {}

        # Pré-calcula mapeamento motor→filial normalizada da planilha
        filiais_planilha = set()
        if produtos:
            filiais_planilha = set(produtos[0].get("custos_por_filial", {}).keys())

        resultado = []

        for motor in motores_selecionados:
            motor_id = motor.get("id", "")
            motor_name = motor.get("name", "")
            filiais = motor.get("filiais", [])
            filial_display = ", ".join(filiais) if filiais else "Sem Filial"

            uf = motor.get("uf", "")
            if not uf:
                uf = _uf_para_filial(filiais[0]) if filiais else _uf_para_filial(motor_name)

            campanha = campanhas_por_motor.get(motor_id, "Sem Campanha")

            # Encontra a filial normalizada correspondente na planilha
            filial_norm_match = None
            for f in filiais:
                f_norm = _normalizar_nome(f)
                if f_norm in filiais_planilha:
                    filial_norm_match = f_norm
                    break
            # Fallback: tenta pelo nome do motor
            if not filial_norm_match:
                m_norm = _normalizar_nome(motor_name)
                if m_norm in filiais_planilha:
                    filial_norm_match = m_norm

            for prod in produtos:
                codigo = prod["codigo"]
                margem = prod["margem"]
                custos = prod.get("custos_por_filial", {})

                # Busca custo específico da filial mapeada
                custo = custos.get(filial_norm_match) if filial_norm_match else None
                if not custo or custo <= 0:
                    continue  # sem custo para essa filial, pula

                # Preço de Partida com custo específico da filial
                preco_partida = (custo / (1 - margem)) * 1.0069 / 0.99075

                erp_por_uf = precos_erp.get(codigo, {})
                preco_cat = erp_por_uf.get(uf)

                if not preco_cat:
                    outro_uf = "SP" if uf == "MG" else "MG"
                    preco_cat = erp_por_uf.get(outro_uf)

                if not preco_cat or preco_cat <= 0:
                    continue

                preco_erp = preco_cat * 0.96
                if preco_erp <= 0:
                    continue

                desconto = 1 - (preco_partida / preco_erp)

                resultado.append({
                    "motor_id": motor_id,
                    "motor_name": motor_name,
                    "filial": filial_display,
                    "campanha": campanha,
                    "uf": uf,
                    "codigo": codigo,
                    "custo": custo,
                    "margem": margem,
                    "preco_partida": preco_partida,
                    "preco_erp": preco_erp,
                    "desconto": desconto,
                })

        return resultado

    def mapear_filiais(
        self, motores_selecionados: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Gera preview de mapeamento Motor↔Filial da planilha, com custo do 1º produto.

        Retorna lista de dicts para exibição na UI antes do cálculo.
        """
        produtos = self._extrair_produtos_planilha()
        filiais_planilha = set()
        primeiro_produto_custos = {}
        if produtos:
            primeiro_produto_custos = produtos[0].get("custos_por_filial", {})
            filiais_planilha = set(primeiro_produto_custos.keys())

        mapeamento = []
        for motor in motores_selecionados:
            motor_name = motor.get("name", "")
            filiais = motor.get("filiais", [])
            filial_sf = ", ".join(filiais) if filiais else motor_name

            filial_match = None
            custo_exemplo = None
            for f in filiais:
                f_norm = _normalizar_nome(f)
                if f_norm in filiais_planilha:
                    filial_match = f_norm
                    custo_exemplo = primeiro_produto_custos.get(f_norm)
                    break
            if not filial_match:
                m_norm = _normalizar_nome(motor_name)
                if m_norm in filiais_planilha:
                    filial_match = m_norm
                    custo_exemplo = primeiro_produto_custos.get(m_norm)

            mapeamento.append({
                "motor_id": motor.get("id", ""),
                "motor_name": motor_name,
                "filial_salesforce": filial_sf,
                "filial_planilha": filial_match or "—",
                "custo_exemplo": custo_exemplo,
                "status": "ok" if filial_match else "falhou",
            })

        return mapeamento

    async def _buscar_precos_erp(self, codigos: List[str]) -> Dict[str, Dict[str, float]]:
        """Busca UnitPrice no PricebookEntry para os catálogos MG e SP.

        Returns:
            {"SKU": {"MG": preco_mg, "SP": preco_sp}}
        """
        from backend.utils.api_client import SalesforceAPIClient

        client = SalesforceAPIClient(self.auth)
        if not codigos:
            return {}

        precos: Dict[str, Dict[str, float]] = {}
        lotes = [codigos[i: i + 150] for i in range(0, len(codigos), 150)]

        for lote in lotes:
            codigos_str = ",".join([f"'{c}'" for c in lote])
            query = f"""
                SELECT Product2.ProductCode, UnitPrice, Pricebook2.Name
                FROM PricebookEntry
                WHERE Product2.ProductCode IN ({codigos_str})
                  AND Pricebook2.Name IN ('CONTRIBUINTE|MG|MG', 'CONTRIBUINTE|SP|SP')
            """
            resp = client.query(query)

            for rec in resp:
                # api_client já faz o flatten → Product2.ProductCode, Pricebook2.Name
                cod = rec.get("Product2.ProductCode")
                price = rec.get("UnitPrice", 0.0)
                catalog_name = rec.get("Pricebook2.Name", "")

                if not cod or not price:
                    continue

                if cod not in precos:
                    precos[cod] = {}

                # Determina a UF pelo nome do catálogo
                if "MG|MG" in catalog_name:
                    precos[cod]["MG"] = price
                elif "SP|SP" in catalog_name:
                    precos[cod]["SP"] = price

        await log("INFO", "ATOR 5",
                  f"Preços ERP encontrados: {len(precos)} produtos "
                  f"(MG: {sum(1 for v in precos.values() if 'MG' in v)}, "
                  f"SP: {sum(1 for v in precos.values() if 'SP' in v)})")
        return precos
