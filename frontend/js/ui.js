/**
 * UI Manager v3 — Layout Unificado (Motor + Dashboard em uma página)
 */
const UI = {
    // ── Elementos ──────────────────────────────────
    els: {
        authBadge: () => document.getElementById('auth-badge'),
        btnAuth: () => document.getElementById('btn-auth'),
        // Wizard Navegação (3 Passos)
        stepInd1: () => document.getElementById('step-ind-1'),
        stepInd2: () => document.getElementById('step-ind-2'),
        stepInd3: () => document.getElementById('step-ind-3'),
        stepConn1: () => document.getElementById('step-conn-1'),
        stepConn2: () => document.getElementById('step-conn-2'),
        paneStep0: () => document.getElementById('pane-step-0'),
        paneStep1: () => document.getElementById('pane-step-1'),
        paneStep2: () => document.getElementById('pane-step-2'),
        paneStep3: () => document.getElementById('pane-step-3'),
        btnGotoStep2: () => document.getElementById('btn-goto-step-2'),
        btnSelectMethodConvencionais: () => document.getElementById('btn-select-method-convencionais'),
        btnPrevToStep0: () => document.getElementById('btn-prev-to-step-0'),
        btnPrevToStep1FromStep2: () => document.getElementById('btn-prev-to-step-1-from-step-2'),
        btnPrevToStep2: () => document.getElementById('btn-prev-to-step-2'),
        campaignCardsGrid: () => document.getElementById('campaign-cards-grid'),
        filterCampaignStatus: () => document.getElementById('filter-campaign-status'),
        filterCampaignSearch: () => document.getElementById('filter-campaign-search'),
        
        // Passo 1: Upload
        fileUpload: () => document.getElementById('file-upload'),
        uploadArea: () => document.getElementById('upload-area'),
        uploadStatus: () => document.getElementById('upload-status'),
        codesInput: () => document.getElementById('codes-input'),
        codesCounter: () => document.getElementById('codes-counter'),
        
        // Passo 3: Configurar & Precificar (Busca e Dropdowns)
        campaignSearchInput: () => document.getElementById('campaign-search-input'),
        campaignDropdownList: () => document.getElementById('campaign-dropdown-list'),
        filialSearchInput: () => document.getElementById('filial-search-input'),
        filialDropdownList: () => document.getElementById('filial-dropdown-list'),
        filterOnlyActive: () => document.getElementById('filter-only-active'),
        headerFilialDropdown: () => document.getElementById('header-filial-dropdown'),
        headerFilialSearchInput: () => document.getElementById('header-filial-search-input'),
        headerFilialDropdownList: () => document.getElementById('header-filial-dropdown-list'),
        motorList: () => document.getElementById('motor-list'),
        motorSearchInput: () => document.getElementById('motor-search-input'),
        motorCounter: () => document.getElementById('motor-counter'),
        btnSelectAllMotors: () => document.getElementById('btn-select-all-motors'),
        btnDeselectAllMotors: () => document.getElementById('btn-deselect-all-motors'),
        
        // New items
        newItemsAlert: () => document.getElementById('new-items-alert'),
        newItemsCodes: () => document.getElementById('new-items-codes'),
        includeNewItems: () => document.getElementById('include-new-items'),
        
        // Dashboard actions (Passo 3)
        btnCalcDesconto: () => document.getElementById('btn-calc-desconto'),
        btnExecutePricing: () => document.getElementById('btn-execute-pricing'),
        actionInfo: () => document.getElementById('action-info'),
        
        // Dashboard
        previewFilters: () => document.getElementById('preview-filters'),
        filterFilial: () => document.getElementById('filter-filial'),
        filterMotor: () => document.getElementById('filter-motor'),
        filterCodigo: () => document.getElementById('filter-codigo'),
        previewSummary: () => document.getElementById('preview-summary'),
        previewCount: () => document.getElementById('preview-count'),
        previewTable: () => document.getElementById('preview-table'),
        previewTableBody: () => document.getElementById('preview-table-body'),
        mappingSummaryContainer: () => document.getElementById('mapping-summary-container'),
        mappingTableBody: () => document.getElementById('mapping-table-body'),
        previewTableContainer: () => document.getElementById('preview-table-container'),
        dashboardEmptyState: () => document.getElementById('dashboard-empty-state'),
        
        // Stats
        statTotal: () => document.getElementById('stat-total'),
        statDeletados: () => document.getElementById('stat-deletados'),
        statInseridos: () => document.getElementById('stat-inseridos'),
        statNovos: () => document.getElementById('stat-novos'),
        
        // Logs
        logContainer: () => document.getElementById('log-container'),
        progressSection: () => document.getElementById('progress-section'),
        progressFill: () => document.getElementById('progress-fill'),
        progressValue: () => document.getElementById('progress-value'),
        progressLabel: () => document.getElementById('progress-label'),
    },

    // ── Wizard Passo de Controle (4 Estados) ────────
    currentStep: 0,

    setStep(step) {
        this.currentStep = step;

        // Resetar classes das abas de progresso
        if (this.els.stepInd1()) this.els.stepInd1().className = 'wizard-step';
        if (this.els.stepInd2()) this.els.stepInd2().className = 'wizard-step';
        if (this.els.stepInd3()) this.els.stepInd3().className = 'wizard-step';
        if (this.els.stepConn1()) this.els.stepConn1().className = 'wizard-connector';
        if (this.els.stepConn2()) this.els.stepConn2().className = 'wizard-connector';

        // Ocultar todos os painéis do Wizard
        if (this.els.paneStep0()) this.els.paneStep0().style.display = 'none';
        if (this.els.paneStep1()) this.els.paneStep1().style.display = 'none';
        if (this.els.paneStep2()) this.els.paneStep2().style.display = 'none';
        if (this.els.paneStep3()) this.els.paneStep3().style.display = 'none';

        // Elementos globais que ficam ocultos na home (Passo 0)
        const statsRow = document.getElementById('stats-row');
        const stepsContainer = document.getElementById('wizard-steps-container');
        const logPanel = document.querySelector('.log-panel');

        if (step === 0) {
            if (statsRow) statsRow.style.display = 'none';
            if (stepsContainer) stepsContainer.style.display = 'none';
            if (logPanel) logPanel.style.display = 'none';
            if (this.els.paneStep0()) this.els.paneStep0().style.display = 'block';
        } else {
            if (statsRow) statsRow.style.display = 'grid';
            if (stepsContainer) stepsContainer.style.display = 'flex';
            if (logPanel) logPanel.style.display = 'block';

            if (step === 1) {
                if (this.els.stepInd1()) this.els.stepInd1().className = 'wizard-step active';
                if (this.els.paneStep1()) this.els.paneStep1().style.display = 'block';
            } else if (step === 2) {
                if (this.els.stepInd1()) this.els.stepInd1().className = 'wizard-step completed';
                if (this.els.stepConn1()) this.els.stepConn1().className = 'wizard-connector completed';
                if (this.els.stepInd2()) this.els.stepInd2().className = 'wizard-step active';
                if (this.els.paneStep2()) this.els.paneStep2().style.display = 'block';
                if (this.els.paneStep2()) this.els.paneStep2().scrollIntoView({ behavior: 'smooth' });
            } else if (step === 3) {
                if (this.els.stepInd1()) this.els.stepInd1().className = 'wizard-step completed';
                if (this.els.stepConn1()) this.els.stepConn1().className = 'wizard-connector completed';
                if (this.els.stepInd2()) this.els.stepInd2().className = 'wizard-step completed';
                if (this.els.stepConn2()) this.els.stepConn2().className = 'wizard-connector completed';
                if (this.els.stepInd3()) this.els.stepInd3().className = 'wizard-step active';
                if (this.els.paneStep3()) this.els.paneStep3().style.display = 'block';
                if (this.els.paneStep3()) this.els.paneStep3().scrollIntoView({ behavior: 'smooth' });
            }
        }
    },

    // ── Auth Badge ─────────────────────────────────
    setAuthStatus(connected) {
        const badge = this.els.authBadge();
        if (connected) {
            badge.className = 'badge badge-connected';
            badge.textContent = '● Conectado';
            this.els.btnAuth().textContent = '🔐 Reconectar';
            this.updateCodesCounter(); // Re-avalia o botão avançar
        } else {
            badge.className = 'badge badge-disconnected';
            badge.textContent = '● Desconectado';
        }
    },

    // ── Upload ─────────────────────────────────────
    setUploadStatus(text, isError = false) {
        const el = this.els.uploadStatus();
        el.textContent = text;
        el.style.color = isError ? 'var(--accent-red)' : 'var(--accent-green)';
    },

    // ── Codes ──────────────────────────────────────
    getCodes() {
        const text = this.els.codesInput().value.trim();
        if (!text) return [];
        return text.split(/[\n,;\s]+/).map(c => c.trim()).filter(c => c.length > 0);
    },

    updateCodesCounter() {
        const count = this.getCodes().length;
        this.els.codesCounter().textContent = `${count} código${count !== 1 ? 's' : ''} extraído${count !== 1 ? 's' : ''}`;
        
        const isAuth = document.getElementById('auth-badge').classList.contains('badge-connected');
        const canAdvance = count > 0 && isAuth;
        this.els.btnGotoStep2().disabled = !canAdvance;
    },

    // ── Motor List ─────────────────────────────────
    _motorData: [],

    renderMotors(motores) {
        this._motorData = motores;
        const list = this.els.motorList();

        if (!motores || !motores.length) {
            list.innerHTML = '<div class="empty-state" style="padding:16px;"><span class="icon">⚙️</span><span>Nenhum motor cadastrado no Salesforce</span></div>';
            this.els.motorCounter().textContent = '0 motores';
            this.els.btnSelectAllMotors().disabled = true;
            this.els.btnDeselectAllMotors().disabled = true;
            return;
        }

        // Renderiza lista física dos motores com design elegante e badges proeminentes
        list.innerHTML = motores.map((motor) => {
            const ufBadgeClass = motor.uf === 'SP' ? 'badge-sp' : 'badge-mg';
            const statusBadgeClass = motor.active ? 'badge-mg' : 'badge-sp';
            const statusText = motor.active ? 'Ativo' : 'Inativo';
            const filiaisText = motor.filiais.join(', ') || 'Sem Filial';
            const campanhasText = motor.campanhas.join(', ') || 'Sem Campanha';
            const isSelected = motor.active ? 'selected' : '';

            return `
                <div class="motor-item ${isSelected}"
                     data-motor-id="${motor.id}"
                     data-motor-name="${this._escapeHtml(motor.name)}"
                     data-filiais="${this._escapeHtml(filiaisText)}"
                     data-campanhas="${this._escapeHtml(campanhasText)}"
                     data-active="${motor.active}"
                     data-uf="${motor.uf}">
                    <div class="motor-checkbox"><span class="motor-checkbox-check">✓</span></div>
                    <div style="flex:1; display:flex; flex-direction:column; gap:4px; font-size:12px; margin-left:8px; overflow:hidden;">
                        <div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">
                            <span class="motor-name-text" style="font-weight:600; color:var(--text-primary); text-overflow:ellipsis; overflow:hidden; white-space:nowrap; max-width:280px;">${this._escapeHtml(motor.name)}</span>
                            <div style="display:flex; gap:4px; align-items:center;">
                                <span class="motor-uf-badge ${statusBadgeClass}">${statusText}</span>
                                <span class="motor-uf-badge ${ufBadgeClass}">${motor.uf}</span>
                            </div>
                        </div>
                        <div style="display:flex; flex-wrap:wrap; gap:8px; font-size:11px;">
                            <span style="color:var(--text-secondary); background:rgba(255,255,255,0.02); padding:2px 6px; border-radius:4px; display:inline-flex; align-items:center; gap:4px;">
                                🎯 <strong>Campanha:</strong> <span style="color:var(--accent-purple); font-weight:600;">${this._escapeHtml(campanhasText)}</span>
                            </span>
                            <span style="color:var(--text-secondary); background:rgba(255,255,255,0.02); padding:2px 6px; border-radius:4px; display:inline-flex; align-items:center; gap:4px;">
                                🏢 <strong>Filial:</strong> <span style="color:var(--accent-cyan); font-weight:600;">${this._escapeHtml(filiaisText)}</span>
                            </span>
                        </div>
                    </div>
                    <span style="background:rgba(99, 102, 241, 0.1); border:1px solid rgba(99,102,241,0.2); padding:4px 10px; border-radius:12px; font-size:10px; color:var(--accent-blue); font-weight:bold; margin-left:8px; white-space:nowrap; display:inline-flex; align-items:center; gap:4px;">
                        📦 ${motor.total_produtos_existentes} itens lidos
                    </span>
                </div>
            `;
        }).join('');

        this.els.btnSelectAllMotors().disabled = false;
        this.els.btnDeselectAllMotors().disabled = false;

        list.querySelectorAll('.motor-item').forEach(item => {
            item.addEventListener('click', () => {
                item.classList.toggle('selected');
                this.updateMotorCounter();
            });
        });

        // Constrói e inicializa os dropdowns customizados de Campanha e Filial
        this.initSearchableDropdowns();

        // Executa a primeira filtragem inteligente com base nos campos de busca
        this.applySmartMotorFilters();
    },

    // ── Grid de Campanhas Dinâmicas (Passo 2) ────────
    _campaigns: [],
    _motores: [],

    renderCampaignCards(campanhas, motores) {
        this._campaigns = campanhas || [];
        this._motores = motores || [];
        this.applyCampaignFilters();
    },

    applyCampaignFilters() {
        const grid = this.els.campaignCardsGrid();
        if (!grid) return;
        grid.innerHTML = '';

        if (!this._campaigns || !this._campaigns.length) {
            grid.innerHTML = '<div style="grid-column:1/-1; padding:20px; text-align:center; color:var(--text-secondary);">Nenhuma campanha ativa encontrada para os produtos analisados.</div>';
            return;
        }

        const statusFilter = this.els.filterCampaignStatus().value; // 'ativos' | 'todos' | 'inativos'
        const searchQuery = (this.els.filterCampaignSearch().value || '').toLowerCase().trim();

        let filteredCampanhas = this._campaigns;

        // 1. Filtrar por pesquisa digitada
        if (searchQuery) {
            filteredCampanhas = filteredCampanhas.filter(c => c.toLowerCase().includes(searchQuery));
        }

        // 2. Filtrar por motores ativos/inativos/todos
        filteredCampanhas = filteredCampanhas.filter(campName => {
            const activeCount = this._motores.filter(m => m.active && (m.campanhas || []).includes(campName)).length;
            
            if (statusFilter === 'ativos') {
                return activeCount > 0;
            } else if (statusFilter === 'inativos') {
                return activeCount === 0;
            }
            return true; // 'todos'
        });

        if (!filteredCampanhas.length) {
            grid.innerHTML = '<div style="grid-column:1/-1; padding:30px; text-align:center; color:var(--text-secondary); font-weight:600;"><span style="font-size: 20px; display:block; margin-bottom:8px;">🔍</span> Nenhum resultado corresponde aos filtros selecionados.</div>';
            return;
        }

        filteredCampanhas.forEach(campName => {
            const totalMotors = this._motores.filter(m => (m.campanhas || []).includes(campName)).length;
            const activeCount = this._motores.filter(m => m.active && (m.campanhas || []).includes(campName)).length;

            const card = document.createElement('div');
            card.className = 'campaign-card';
            card.dataset.campaignName = campName;

            card.innerHTML = `
                <div class="campaign-card-icon">🎯</div>
                <div class="campaign-card-content">
                    <h4 class="campaign-card-title">${this._escapeHtml(campName)}</h4>
                    <p class="campaign-card-subtitle">
                        ${totalMotors} motor${totalMotors !== 1 ? 'es' : ''} (${activeCount} ativo${activeCount !== 1 ? 's' : ''})
                    </p>
                </div>
                <div class="campaign-card-arrow">➡️</div>
            `;

            grid.appendChild(card);
        });
    },

    // ── Dropdowns Pesquisáveis Customizados ──────────
    initSearchableDropdowns() {
        const campaignInput = this.els.campaignSearchInput();
        const campaignList = this.els.campaignDropdownList();
        const filialInput = this.els.filialSearchInput();
        const filialList = this.els.filialDropdownList();

        // Extrai campanhas e filiais únicas
        const campaignsMap = {};
        const filiaisMap = {};

        this._motorData.forEach(m => {
            const onlyActive = this.els.filterOnlyActive().checked;
            if (onlyActive && !m.active) return;

            (m.campanhas || []).forEach(c => {
                if (c) campaignsMap[c] = (campaignsMap[c] || 0) + 1;
            });
            (m.filiais || []).forEach(f => {
                if (f) filiaisMap[f] = (filiaisMap[f] || 0) + 1;
            });
        });

        const uniqueCampaigns = Object.keys(campaignsMap).sort();
        const uniqueFiliais = Object.keys(filiaisMap).sort();

        // Renderiza itens da Campanha
        campaignList.innerHTML = uniqueCampaigns.map(c => `
            <div class="dropdown-item" data-value="${this._escapeHtml(c)}">
                <span>🎯 ${this._escapeHtml(c)}</span>
                <span class="count-badge">${campaignsMap[c]} motor(es)</span>
            </div>
        `).join('') || '<div style="padding:10px; color:var(--text-muted); font-size:12px; text-align:center;">Nenhuma campanha encontrada</div>';

        // Renderiza itens da Filial
        filialList.innerHTML = uniqueFiliais.map(f => `
            <div class="dropdown-item" data-value="${this._escapeHtml(f)}">
                <span>🏢 ${this._escapeHtml(f)}</span>
                <span class="count-badge">${filiaisMap[f]} motor(es)</span>
            </div>
        `).join('') || '<div style="padding:10px; color:var(--text-muted); font-size:12px; text-align:center;">Nenhuma filial encontrada</div>';

        // Eventos do input de Campanha
        campaignInput.addEventListener('focus', () => {
            campaignList.style.display = 'block';
            this.filterDropdownItems(campaignInput, campaignList);
        });
        campaignInput.addEventListener('input', () => {
            campaignList.style.display = 'block';
            this.filterDropdownItems(campaignInput, campaignList);
            this.applySmartMotorFilters();
        });
        campaignList.querySelectorAll('.dropdown-item').forEach(item => {
            item.addEventListener('click', (e) => {
                campaignInput.value = item.dataset.value;
                campaignList.style.display = 'none';
                this.applySmartMotorFilters();
                e.stopPropagation();
            });
        });

        // Eventos do input de Filial
        filialInput.addEventListener('focus', () => {
            filialList.style.display = 'block';
            this.filterDropdownItems(filialInput, filialList);
        });
        filialInput.addEventListener('input', () => {
            filialList.style.display = 'block';
            this.filterDropdownItems(filialInput, filialList);
            this.applySmartMotorFilters();
        });
        filialList.querySelectorAll('.dropdown-item').forEach(item => {
            item.addEventListener('click', (e) => {
                filialInput.value = item.dataset.value;
                filialList.style.display = 'none';
                this.applySmartMotorFilters();
                e.stopPropagation();
            });
        });

        // Fecha dropdowns ao clicar fora
        document.addEventListener('click', (e) => {
            if (!e.target.closest('#campaign-dropdown')) {
                campaignList.style.display = 'none';
            }
            if (!e.target.closest('#filial-dropdown')) {
                filialList.style.display = 'none';
            }
            const headerFilialDropdownList = document.getElementById('header-filial-dropdown-list');
            if (headerFilialDropdownList && !e.target.closest('#header-filial-dropdown')) {
                headerFilialDropdownList.style.display = 'none';
            }
        });
    },

    filterDropdownItems(input, list) {
        const query = (input.value || '').toLowerCase().trim();
        const items = list.querySelectorAll('.dropdown-item');
        items.forEach(item => {
            const val = (item.dataset.value || '').toLowerCase();
            if (!query || val.includes(query)) {
                item.style.display = 'flex';
            } else {
                item.style.display = 'none';
            }
        });
    },

    applySmartMotorFilters() {
        const campSearch = (this.els.campaignSearchInput().value || '').toLowerCase().trim();
        const filialSearch = (this.els.filialSearchInput().value || '').toLowerCase().trim();
        const motorSearch = (this.els.motorSearchInput().value || '').toLowerCase().trim();
        const onlyActive = this.els.filterOnlyActive().checked;

        const items = this.els.motorList().querySelectorAll('.motor-item');

        items.forEach(item => {
            const name = (item.dataset.motorName || '').toLowerCase();
            const filiais = (item.dataset.filiais || '').toLowerCase();
            const camps = (item.dataset.campanhas || '').toLowerCase();
            const active = item.dataset.active === 'true';

            // Critérios de combinação
            const matchActive = !onlyActive || active;
            
            // Suporta correspondência parcial ou completa
            const matchCamp = !campSearch || camps.includes(campSearch) || name.includes(campSearch);
            const matchFilial = !filialSearch || filiais.includes(filialSearch) || name.includes(filialSearch);
            const matchMotor = !motorSearch || name.includes(motorSearch);

            const isMatch = matchActive && matchCamp && matchFilial && matchMotor;

            // Exibe ou oculta fisicamente na lista
            item.style.display = isMatch ? '' : 'none';
        });

        this.updateMotorCounter();
    },

    getSelectedMotors() {
        const ids = Array.from(
            this.els.motorList().querySelectorAll('.motor-item.selected')
        ).map(el => el.dataset.motorId);
        return this._motorData.filter(m => ids.includes(m.id));
    },

    selectAllMotors() {
        this.els.motorList().querySelectorAll('.motor-item').forEach(el => {
            if (el.style.display !== 'none') el.classList.add('selected');
        });
        this.updateMotorCounter();
    },

    deselectAllMotors() {
        this.els.motorList().querySelectorAll('.motor-item').forEach(el => {
            if (el.style.display !== 'none') el.classList.remove('selected');
        });
        this.updateMotorCounter();
    },

    updateMotorCounter() {
        const selected = this.getSelectedMotors();
        const count = selected.length;
        this.els.motorCounter().textContent = `${count} motor${count !== 1 ? 'es' : ''} selecionado${count !== 1 ? 's' : ''}`;

        const hasMotors = count > 0;
        this.els.btnCalcDesconto().disabled = !hasMotors;

        if (hasMotors) {
            const totalItens = selected.reduce((s, m) => s + (m.total_produtos_existentes || 0), 0);
            this.els.actionInfo().textContent = `${count} motor${count !== 1 ? 'es' : ''} selecionado${count !== 1 ? 's' : ''} — total de ${totalItens} produtos para precificar`;
        } else {
            this.els.actionInfo().textContent = 'Selecione motores acima para precificar.';
        }
    },

    // ── New Items Alert ────────────────────────────
    showNewItemsAlert(itensNovos) {
        const alert = this.els.newItemsAlert();
        if (!itensNovos || !itensNovos.length) { alert.style.display = 'none'; return; }
        alert.style.display = 'block';
        this.els.newItemsCodes().textContent = itensNovos.join(', ');
        this.els.statNovos().textContent = itensNovos.length;
    },

    getIncludeNewItems() {
        return this.els.includeNewItems().checked;
    },

    // ── Dashboard ─────────────────────────────────
    renderDashboard(data) {
        // Esconde filtros antigos de input de texto
        if (this.els.previewFilters()) this.els.previewFilters().style.display = 'none';

        // Esconde empty state
        const emptyEl = this.els.dashboardEmptyState();
        if (emptyEl) emptyEl.style.display = 'none';

        // Mapeamento de Filiais
        const mappingContainer = this.els.mappingSummaryContainer();
        const mappingTbody = this.els.mappingTableBody();
        if (mappingContainer && mappingTbody) {
            if (data.mapeamento_filiais && data.mapeamento_filiais.length > 0) {
                mappingContainer.style.display = 'block';
                mappingTbody.innerHTML = '';
                data.mapeamento_filiais.forEach(item => {
                    const tr = document.createElement('tr');
                    const statusText = item.status === 'ok' ? '✅ Mapeado' : '⚠️ Falhou';
                    const statusColor = item.status === 'ok' ? 'var(--accent-green)' : 'var(--accent-red)';
                    const custoFmt = item.custo_exemplo !== null && item.custo_exemplo !== undefined
                        ? `R$ ${item.custo_exemplo.toLocaleString('pt-BR', {minimumFractionDigits:2})}`
                        : '—';
                    tr.innerHTML = `
                        <td style="padding: 8px 10px; border-bottom: 1px solid rgba(255,255,255,0.05); font-weight:600;">${this._escapeHtml(item.motor_name)}</td>
                        <td style="padding: 8px 10px; border-bottom: 1px solid rgba(255,255,255,0.05); color: var(--text-secondary);">${this._escapeHtml(item.filial_salesforce)}</td>
                        <td style="padding: 8px 10px; border-bottom: 1px solid rgba(255,255,255,0.05); font-weight:600; color: var(--accent-blue);">${this._escapeHtml(item.filial_planilha)}</td>
                        <td style="padding: 8px 10px; border-bottom: 1px solid rgba(255,255,255,0.05); text-align:right; font-family:'JetBrains Mono',monospace;">${custoFmt}</td>
                        <td style="padding: 8px 10px; border-bottom: 1px solid rgba(255,255,255,0.05); text-align:center; color:${statusColor}; font-weight:bold;">${statusText}</td>
                    `;
                    mappingTbody.appendChild(tr);
                });
            } else {
                mappingContainer.style.display = 'none';
            }
        }

        // Resumo
        const summaryEl = this.els.previewSummary();
        summaryEl.style.display = 'flex';
        summaryEl.innerHTML =
            `<span>🗑️ <strong>${data.registros_deletar.toLocaleString('pt-BR')}</strong> para deletar</span>` +
            `<span>📥 <strong>${data.registros_inserir.toLocaleString('pt-BR')}</strong> para inserir</span>` +
            `<span>⚙️ <strong>${data.motores_count}</strong> motores</span>` +
            (data.itens_novos && data.itens_novos.length
                ? `<span>⚠️ <strong>${data.itens_novos.length}</strong> itens novos</span>` : '');

        // Habilita botão Executar agora que há dados calculados
        this.els.btnExecutePricing().disabled = false;

        // Tabela
        const tableEl = this.els.previewTable();
        tableEl.style.display = 'table';

        const tbody = this.els.previewTableBody();
        tbody.innerHTML = '';

        if (data.detalhes && data.detalhes.length > 0) {
            data.detalhes.forEach(item => {
                const tr = document.createElement('tr');
                const descontoColor = item.desconto >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';
                const ufClass = item.uf === 'SP' ? 'badge-sp' : 'badge-mg';
                const descontoFmt = (item.desconto * 100).toFixed(8) + '%';

                tr.innerHTML = `
                    <td><strong>${item.codigo}</strong></td>
                    <td style="color:var(--text-primary); font-weight:600;">${this._escapeHtml(item.filial)}</td>
                    <td style="color:var(--text-muted); font-size:11px;">${this._escapeHtml(item.motor_name)}</td>
                    <td>${this._escapeHtml(item.campanha)}</td>
                    <td><span class="motor-uf-badge ${ufClass}">${item.uf}</span></td>
                    <td>R$ ${item.custo.toLocaleString('pt-BR', {minimumFractionDigits:2})}</td>
                    <td>${(item.margem * 100).toFixed(2)}%</td>
                    <td style="color:var(--accent-blue);">R$ ${item.preco_partida.toLocaleString('pt-BR', {minimumFractionDigits:2})}</td>
                    <td>R$ ${item.preco_erp.toLocaleString('pt-BR', {minimumFractionDigits:2})}</td>
                    <td style="color:${descontoColor}; font-weight:bold; font-family:'JetBrains Mono',monospace; font-size:11px;">${descontoFmt}</td>
                `;
                tbody.appendChild(tr);
            });
            this.els.previewCount().textContent = `${data.detalhes.length} registros`;
        } else {
            tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--text-muted);">Nenhum registro calculado</td></tr>';
            this.els.previewCount().textContent = '';
        }

        // Popula filtro de filial no cabeçalho do Dashboard (Searchable Dropdown)
        const dropdownContainer = this.els.headerFilialDropdown();
        const searchInput = this.els.headerFilialSearchInput();
        const dropdownList = this.els.headerFilialDropdownList();

        if (dropdownContainer && searchInput && dropdownList) {
            dropdownContainer.style.display = 'block';
            
            // Extrai filiais únicas das linhas da tabela
            const filiaisSet = new Set();
            if (data.detalhes && data.detalhes.length > 0) {
                data.detalhes.forEach(item => {
                    if (item.filial) filiaisSet.add(item.filial);
                });
            }
            
            const sortedFiliais = Array.from(filiaisSet).sort();
            
            // Cria os itens do dropdown
            let html = `<div class="dropdown-item" data-value="" style="padding: 8px 12px; cursor: pointer; transition: background 0.2s; font-size: 11px; font-weight: 600; display: flex; align-items: center; gap: 8px; color: var(--text-primary); border-bottom: 1px solid var(--border);" onmouseenter="this.style.background='var(--bg-hover)'" onmouseleave="this.style.background='transparent'">🏢 Todas as Filiais</div>`;
            
            sortedFiliais.forEach(f => {
                html += `<div class="dropdown-item" data-value="${this._escapeHtml(f)}" style="padding: 8px 12px; cursor: pointer; transition: background 0.2s; font-size: 11px; display: flex; align-items: center; gap: 8px; color: var(--text-primary); border-bottom: 1px solid rgba(255,255,255,0.05);" onmouseenter="this.style.background='var(--bg-hover)'" onmouseleave="this.style.background='transparent'">🏢 ${this._escapeHtml(f)}</div>`;
            });
            
            dropdownList.innerHTML = html;
            searchInput.value = ''; // Limpa a busca anterior
            
            // Configura os eventos do input
            searchInput.onfocus = () => {
                dropdownList.style.display = 'block';
            };
            
            searchInput.oninput = () => {
                const query = (searchInput.value || '').toLowerCase().trim();
                dropdownList.querySelectorAll('.dropdown-item').forEach(item => {
                    const val = (item.dataset.value || '').toLowerCase();
                    const text = (item.textContent || '').toLowerCase();
                    if (!query || val.includes(query) || text.includes(query)) {
                        item.style.display = 'flex';
                    } else {
                        item.style.display = 'none';
                    }
                });
            };
            
            // Configura os eventos de clique nos itens
            dropdownList.onclick = (e) => {
                const item = e.target.closest('.dropdown-item');
                if (!item) return;
                
                const val = item.dataset.value;
                searchInput.value = val ? item.textContent.replace('🏢 ', '') : '';
                dropdownList.style.display = 'none';
                this._applyDashboardHeaderFilters(val);
            };
        }
    },

    _applyDashboardHeaderFilters(selectedFilialVal = null) {
        let selectedFilial = selectedFilialVal;
        if (selectedFilial === null) {
            selectedFilial = (this.els.headerFilialSearchInput().value || '').toLowerCase().trim();
        } else {
            selectedFilial = selectedFilial.toLowerCase().trim();
        }

        let visible = 0;
        this.els.previewTableBody().querySelectorAll('tr').forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length < 2) return;
            const filialText = (cells[1].textContent || '').toLowerCase().trim();
            const match = !selectedFilial || filialText === selectedFilial;

            row.style.display = match ? '' : 'none';
            if (match) visible++;
        });
        this.els.previewCount().textContent = `${visible} registros visíveis`;
    },

    _bindDashboardFilters() {
        const fn = () => this._applyDashboardFilters();
        // Remove listeners antigos antes de rebind
        ['filter-filial','filter-motor','filter-codigo'].forEach(id => {
            const el = document.getElementById(id);
            const newEl = el.cloneNode(true);
            el.parentNode.replaceChild(newEl, el);
            newEl.addEventListener('input', fn);
        });
    },

    _applyDashboardFilters() {
        const filial = (this.els.filterFilial().value || '').toLowerCase();
        const motor = (this.els.filterMotor().value || '').toLowerCase();
        const codigo = (this.els.filterCodigo().value || '').toLowerCase();

        let visible = 0;
        this.els.previewTableBody().querySelectorAll('tr').forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length < 3) return;
            const match =
                (cells[0].textContent || '').toLowerCase().includes(codigo) &&
                (cells[1].textContent || '').toLowerCase().includes(filial) &&
                (cells[2].textContent || '').toLowerCase().includes(motor);
            row.style.display = match ? '' : 'none';
            if (match) visible++;
        });
        this.els.previewCount().textContent = `${visible} registros visíveis`;
    },

    // ── Stats ──────────────────────────────────────
    setStats(total, deletados, inseridos, novos) {
        if (total != null) this.els.statTotal().textContent = total.toLocaleString('pt-BR');
        if (deletados != null) this.els.statDeletados().textContent = deletados.toLocaleString('pt-BR');
        if (inseridos != null) this.els.statInseridos().textContent = inseridos.toLocaleString('pt-BR');
        if (novos != null) this.els.statNovos().textContent = novos.toLocaleString('pt-BR');
    },

    // ── Logs ───────────────────────────────────────
    _logStarted: false,

    addLogEntry(entry) {
        const container = this.els.logContainer();
        if (!this._logStarted) { container.innerHTML = ''; this._logStarted = true; }

        const levelClass = { 'SUCCESS':'success','ERROR':'error','WARNING':'warning','PROGRESS':'progress' }[entry.level] || '';
        const icon = { 'INFO':'ℹ️','SUCCESS':'✅','ERROR':'❌','WARNING':'⚠️','PROGRESS':'📊' }[entry.level] || '📋';

        const div = document.createElement('div');
        div.className = 'log-entry';
        div.innerHTML = `
            <span class="log-time">${entry.timestamp}</span>
            ${icon}
            <span class="log-actor">[${this._escapeHtml(entry.actor)}]</span>
            <span class="log-msg ${levelClass}">${this._escapeHtml(entry.message)}</span>
        `;
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;

        if (entry.progress !== undefined) this.setProgress(entry.progress, entry.batch_current, entry.batch_total);
    },

    clearLogs() {
        this.els.logContainer().innerHTML = '<div class="log-empty">Aguardando operação...</div>';
        this._logStarted = false;
    },

    // ── Progress ───────────────────────────────────
    showProgress() { this.els.progressSection().style.display = 'block'; },
    hideProgress() { this.els.progressSection().style.display = 'none'; },

    setProgress(percent, current, total) {
        this.showProgress();
        this.els.progressFill().style.width = `${percent}%`;
        this.els.progressValue().textContent = `${Math.round(percent)}%`;
        if (current && total) this.els.progressLabel().textContent = `Batch ${current}/${total}`;
    },

    // ── Loading state ──────────────────────────────
    setLoading(button, loading, text = '') {
        if (loading) {
            button.disabled = true;
            button._originalText = button.textContent;
            button.innerHTML = `<div class="spinner"></div> ${text || 'Aguarde...'}`;
        } else {
            button.disabled = false;
            button.textContent = button._originalText || button.textContent;
        }
    },

    // ── Helpers ────────────────────────────────────
    _escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },
};
