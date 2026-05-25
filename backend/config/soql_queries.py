"""Queries SOQL parametrizadas — extraídas da aba 'Querys' do Excel."""


class SOQLQueries:
    """Repositório centralizado de queries SOQL do Salesforce."""

    # ── Query principal: Produtos do Motor do Modificador ──
    # Objeto alvo da deleção (Fase 1)
    PRODUTOS_MOTOR_BASE = """
        SELECT Id, ProductCode__c, Product__r.Name,
               Discount__c, Addition__c,
               ModifierEngine__c, ModifierEngine__r.Name,
               DateHourInitial__c, DateHourEnd__c
        FROM ProductsModifierEngine__c
        WHERE ModifierEngine__r.IsActive__c = true
    """.strip()


    # ── Queries de suporte (referência / futuro) ──────────

    FILIAIS_MOTOR = """
        SELECT Id, ModifierEngine__c, ModifierEngine__r.Name,
               Branch__c, Branch__r.BranchCode__c, Branch__r.Name
        FROM BranchModifierEngine__c
    """.strip()

    FILIAIS = """
        SELECT Id, BranchCode__c, Name, Active__c, RecordType.Name
        FROM Branch__c
    """.strip()

    MODIFICADORES_ERP = """
        SELECT Id, Name, Active__c
        FROM PriceModifier__c
    """.strip()

    CAMPANHAS_MOTOR = """
        SELECT Id, ModifierEngine__c, ModifierEngine__r.Name,
               ModifierEngine__r.IsActive__c,
               Campaign__r.Name, Campaign__c
        FROM CampaignModifierEngine__c
    """.strip()

    CAMPANHAS = """
        SELECT Id, Name, Active__c
        FROM Campaign
    """.strip()
