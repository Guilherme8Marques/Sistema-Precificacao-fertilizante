/**
 * App v3 — Layout Unificado: Motor + Dashboard em uma página.
 *
 * FLUXO:
 * 1. Upload → extrai códigos
 * 2. Analisar → lista todos os motores ativos
 * 3. Seleciona motores → Calcular Desconto → Dashboard preenche abaixo
 * 4. Executar Precificação (habilitado após cálculo)
 */
const App = {
    authenticated: false,
    uploadFile: null,
    analysisData: null,

    init() {
        this.bindEvents();
        this.connectWebSocket();
        this.checkStatus();
        UI.setStep(0); // Inicia sempre no passo 0 (Tela Inicial)
    },

    bindEvents() {
        // Auth
        UI.els.btnAuth().addEventListener('click', () => this.authenticate());

        // Passo 0: Escolha do Método
        UI.els.btnSelectMethodConvencionais().addEventListener('click', () => UI.setStep(1));

        // Upload Drag/Drop
        this.bindUploadEvents();

        // Navegação Wizard: Passo 1 ➡️ Passo 2 (Campanhas)
        UI.els.btnGotoStep2().addEventListener('click', async () => {
            const success = await this.analyzeProducts();
            if (success) {
                UI.setStep(2);
            }
        });

        // Navegação Wizard: Passo 1 ⬅️ Passo 0 (Início)
        UI.els.btnPrevToStep0().addEventListener('click', () => {
            UI.setStep(0);
        });

        // Navegação Wizard: Passo 2 ⬅️ Passo 1
        UI.els.btnPrevToStep1FromStep2().addEventListener('click', () => {
            UI.setStep(1);
        });

        // Navegação Wizard: Passo 3 ⬅️ Passo 2
        UI.els.btnPrevToStep2().addEventListener('click', () => {
            UI.setStep(2);
        });

        // Clique no Card de Campanha (Passo 2)
        UI.els.campaignCardsGrid().addEventListener('click', e => {
            const card = e.target.closest('.campaign-card');
            if (!card) return;
            const campaignName = card.dataset.campaignName;
            this.selecionarCampanha(campaignName);
        });

        // Passo 2: Filtros Pílula de Campanhas
        UI.els.filterCampaignStatus().addEventListener('change', () => UI.applyCampaignFilters());
        UI.els.filterCampaignSearch().addEventListener('input', () => UI.applyCampaignFilters());

        // Passo 3: Filtros Livres por Digitação (input)
        UI.els.campaignSearchInput().addEventListener('input', () => UI.applySmartMotorFilters());
        UI.els.filialSearchInput().addEventListener('input', () => UI.applySmartMotorFilters());
        UI.els.motorSearchInput().addEventListener('input', () => UI.applySmartMotorFilters());
        UI.els.filterOnlyActive().addEventListener('change', () => {
            // Recria a lista de dropdowns com base no status do checkbox
            UI.initSearchableDropdowns();
            UI.applySmartMotorFilters();
        });

        // Passo 3: Seleção de Motores
        UI.els.btnSelectAllMotors().addEventListener('click', () => UI.selectAllMotors());
        UI.els.btnDeselectAllMotors().addEventListener('click', () => UI.deselectAllMotors());

        // Dashboard ações (Passo 3)
        UI.els.btnCalcDesconto().addEventListener('click', () => this.calcularDesconto());
        UI.els.btnExecutePricing().addEventListener('click', () => this.executePricing());
    },

    bindUploadEvents() {
        const area = UI.els.uploadArea();
        const input = UI.els.fileUpload();

        area.addEventListener('click', () => input.click());
        area.addEventListener('dragover', e => { e.preventDefault(); area.classList.add('dragover'); });
        area.addEventListener('dragleave', e => { e.preventDefault(); area.classList.remove('dragover'); });
        area.addEventListener('drop', e => {
            e.preventDefault();
            area.classList.remove('dragover');
            if (e.dataTransfer.files.length) this.handleFileUpload(e.dataTransfer.files[0]);
        });
        input.addEventListener('change', e => {
            if (e.target.files.length) this.handleFileUpload(e.target.files[0]);
        });
    },

    // ── Upload ─────────────────────────────────────
    async handleFileUpload(file) {
        if (!file.name.endsWith('.xlsx')) {
            UI.setUploadStatus('Erro: Apenas .xlsx são permitidos.', true);
            return;
        }

        this.uploadFile = file;
        UI.setUploadStatus(`Lendo: ${file.name}...`);

        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await fetch('/api/upload', { method: 'POST', body: formData });
            const data = await res.json();

            if (res.ok) {
                UI.setUploadStatus(`✅ ${file.name} — ${data.produtos_count} códigos`);
                if (data.codigos && data.codigos.length) {
                    UI.els.codesInput().value = data.codigos.join('\n');
                    UI.updateCodesCounter();
                }
                UI.addLogEntry({
                    timestamp: new Date().toLocaleTimeString('pt-BR'),
                    level: 'SUCCESS', actor: 'UPLOAD',
                    message: `Planilha processada: ${data.produtos_count} produtos.`
                });
                
                // Transição automática para o Passo 2: roda a busca Salesforce em segundo plano e avança
                setTimeout(async () => {
                    const success = await this.analyzeProducts();
                    if (success) {
                        UI.setStep(2);
                    }
                }, 500);
            } else {
                UI.setUploadStatus(`Erro: ${data.error}`, true);
            }
        } catch (e) {
            UI.setUploadStatus(`Erro de conexão: ${e.message}`, true);
        }
    },

    // ── WebSocket ──────────────────────────────────
    connectWebSocket() {
        wsManager.onMessage = (data) => {
            UI.addLogEntry(data);
            if (data.actor === 'PIPELINE' && data.level === 'SUCCESS') this.onPipelineComplete();
            if (data.actor === 'PIPELINE' && data.level === 'ERROR') this.onPipelineError();
            if (data.actor === 'EXECUTOR') {
                if (data.deletados !== undefined) UI.setStats(null, data.deletados, null, null);
                if (data.inseridos !== undefined) UI.setStats(null, null, data.inseridos, null);
            }
        };
        wsManager.connect();
    },

    // ── API: Auth ──────────────────────────────────
    async authenticate() {
        const btn = UI.els.btnAuth();
        UI.setLoading(btn, true, 'Conectando...');
        UI.clearLogs();

        try {
            const res = await fetch('/api/auth', { method: 'POST' });
            const data = await res.json();
            if (res.ok) {
                this.authenticated = true;
                UI.setAuthStatus(true);
            } else {
                alert(`Erro: ${data.error}`);
            }
        } catch (e) {
            alert(`Erro de conexão: ${e.message}`);
        } finally {
            UI.setLoading(btn, false);
        }
    },

    // ── API: Analisar ──────────────────────────────
    async analyzeProducts() {
        const codigos = UI.getCodes();
        if (!codigos.length) {
            alert('Faça o upload da planilha primeiro.');
            return false;
        }

        const btn = UI.els.btnGotoStep2();
        UI.setLoading(btn, true, 'Analisando e buscando motores...');

        try {
            const res = await fetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ codigos }),
            });
            const data = await res.json();

            if (res.ok) {
                this.analysisData = data;
                UI.renderMotors(data.motores);
                UI.renderCampaignCards(data.campanhas, data.motores);
                UI.setStats(data.total_registros_existentes, null, null, data.itens_novos.length);
                UI.showNewItemsAlert(data.itens_novos);

                UI.addLogEntry({
                    timestamp: new Date().toLocaleTimeString('pt-BR'),
                    level: 'SUCCESS', actor: 'ANÁLISE',
                    message: `${data.motores.length} motores carregados do Salesforce, ${data.itens_novos.length} itens novos.`
                });
                return true;
            } else {
                if (res.status === 401) {
                    this.authenticated = false;
                    UI.setAuthStatus(false);
                    alert('Sessão expirada. Reconecte ao Salesforce.');
                } else {
                    alert(`Erro: ${data.error}`);
                }
                return false;
            }
        } catch (e) {
            alert(`Erro: ${e.message}`);
            return false;
        } finally {
            UI.setLoading(btn, false);
        }
    },

    // ── API: Calcular Desconto (Preview) ───────────
    async calcularDesconto() {
        const motores = UI.getSelectedMotors();
        if (!motores.length) return alert('Selecione pelo menos um motor.');

        const btn = UI.els.btnCalcDesconto();
        UI.setLoading(btn, true, 'Calculando...');

        try {
            const payload = {
                motores: motores.map(m => ({
                    id: m.id, name: m.name,
                    filiais: m.filiais, campanhas: m.campanhas, uf: m.uf
                })),
                incluir_novos: UI.getIncludeNewItems(),
            };

            const res = await fetch('/api/pricing/preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await res.json();

            if (res.ok) {
                UI.renderDashboard(data);
                UI.addLogEntry({
                    timestamp: new Date().toLocaleTimeString('pt-BR'),
                    level: 'SUCCESS', actor: 'CÁLCULO',
                    message: `Desconto calculado: ${data.registros_inserir} registros, ${data.registros_deletar} para deletar.`
                });
            } else {
                alert(`Erro no cálculo: ${data.error}`);
            }
        } catch (e) {
            alert(`Erro: ${e.message}`);
        } finally {
            UI.setLoading(btn, false);
        }
    },

    // ── API: Executar Precificação ─────────────────
    async executePricing() {
        const motores = UI.getSelectedMotors();
        if (!motores.length) return alert('Selecione pelo menos um motor.');

        const motorNames = motores.map(m => m.name).join('\n  • ');
        const confirmed = confirm(
            `⚡ PRECIFICAÇÃO EM MASSA\n\n` +
            `Motores (${motores.length}):\n  • ${motorNames}\n\n` +
            `O sistema vai:\n1. DELETAR registros antigos\n2. INSERIR novos com descontos recalculados\n\nDeseja continuar?`
        );
        if (!confirmed) return;

        const btn = UI.els.btnExecutePricing();
        UI.setLoading(btn, true, 'Executando...');
        UI.showProgress();
        UI.setProgress(0);
        UI.setStats(null, 0, 0, null);

        try {
            const payload = {
                motores: motores.map(m => ({
                    id: m.id, name: m.name,
                    filiais: m.filiais, campanhas: m.campanhas, uf: m.uf
                })),
                incluir_novos: UI.getIncludeNewItems(),
            };

            const res = await fetch('/api/pricing/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await res.json();

            if (!res.ok) {
                alert(`Erro: ${data.error}`);
                UI.setLoading(btn, false);
                UI.hideProgress();
            }
        } catch (e) {
            alert(`Erro: ${e.message}`);
            UI.setLoading(btn, false);
            UI.hideProgress();
        }
    },

    // ── Pipeline callbacks ─────────────────────────
    async onPipelineComplete() {
        UI.setLoading(UI.els.btnExecutePricing(), false);
        UI.setProgress(100);

        const res = await fetch('/api/status');
        const data = await res.json();
        if (data.task_result) {
            UI.setStats(null, data.task_result.deletados || 0, data.task_result.inseridos || 0, null);
            UI.addLogEntry({
                timestamp: new Date().toLocaleTimeString('pt-BR'),
                level: 'SUCCESS', actor: 'RESULTADO',
                message: `Concluído! Deletados: ${data.task_result.deletados || 0}, Inseridos: ${data.task_result.inseridos || 0}.`
            });
        }
    },

    onPipelineError() {
        UI.setLoading(UI.els.btnExecutePricing(), false);
        UI.hideProgress();
    },

    // ── Status inicial ─────────────────────────────
    async checkStatus() {
        try {
            const res = await fetch('/api/status');
            const data = await res.json();
            if (data.authenticated) {
                this.authenticated = true;
                UI.setAuthStatus(true);
            }
        } catch (e) { /* servidor ainda iniciando */ }
    },

    // ── Selecionar Campanha (Passo 2 ➡️ Passo 3) ────
    selecionarCampanha(campaignName) {
        // Preenche o input de busca com a campanha selecionada
        UI.els.campaignSearchInput().value = campaignName;

        // Pré-seleciona os motores que pertencem a esta campanha
        const list = UI.els.motorList();
        list.querySelectorAll('.motor-item').forEach(item => {
            const motorCampanhas = (item.dataset.campanhas || '').split(',').map(s => s.trim());
            const motorActive = item.dataset.active === 'true';

            // Se o motor pertence à campanha e está ativo, marca como selecionado
            if (motorCampanhas.includes(campaignName) && motorActive) {
                item.classList.add('selected');
            } else {
                item.classList.remove('selected');
            }
        });

        // Recria a lista de dropdowns com base na campanha selecionada
        UI.initSearchableDropdowns();

        // Atualiza a contagem dos motores
        UI.updateMotorCounter();

        // Aplica o filtro nos dropdowns e na visualização
        UI.applySmartMotorFilters();

        // Avança para o Passo 3
        UI.setStep(3);
    },
};

document.addEventListener('DOMContentLoaded', () => App.init());
