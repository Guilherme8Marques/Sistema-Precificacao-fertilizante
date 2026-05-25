"""Servidor FastAPI — Central de Comando para Precificação de Fertilizantes.

Endpoints REST + WebSocket para monitoramento em tempo real.
"""

import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import pandas as pd
import io

from backend.config.settings import settings
from backend.utils.logger import get_broadcaster, log
from backend.utils.safety import SafetyGuard
from backend.utils.api_client import SalesforceAuth, AuthExpiredError
from backend.src.ator1_autenticador import Autenticador, AuthenticationError
from backend.src.ator2_extrator import Extrator
from backend.src.ator3_cerebro import Cerebro
from backend.src.ator4_executor import Executor


# ── Estado global ──────────────────────────────────────
class AppState:
    auth: Optional[SalesforceAuth] = None
    task_running: bool = False
    task_result: Optional[dict] = None


state = AppState()


# ── Lifespan ───────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await log("INFO", "SERVER", f"Central de Precificação iniciada em http://localhost:{settings.PORT}")
    yield
    await log("INFO", "SERVER", "Servidor encerrado.")


# ── App ────────────────────────────────────────────────
app = FastAPI(
    title="Central de Precificação — Fertilizantes",
    version="2.0.0",
    lifespan=lifespan,
)

# Serve frontend estático
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ── Models ─────────────────────────────────────────────
class SearchRequest(BaseModel):
    codigos: list[str]


class MotorSelecionado(BaseModel):
    id: str
    name: str
    filiais: list[str] = []
    campanhas: list[str] = []
    uf: str


class PricingPreviewRequest(BaseModel):
    motores: list[MotorSelecionado]
    incluir_novos: bool = False


class PricingExecuteRequest(BaseModel):
    motores: list[MotorSelecionado]
    incluir_novos: bool = False


# ── Frontend ───────────────────────────────────────────
@app.get("/")
async def serve_frontend():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


# ── API: Autenticação ──────────────────────────────────
@app.post("/api/auth")
async def autenticar():
    """Ator 1: Extrai Session ID do Chrome."""
    if state.task_running:
        return JSONResponse({"error": "Operação em andamento."}, status_code=409)

    try:
        auth_actor = Autenticador()
        state.auth = await auth_actor.autenticar()
        return {"status": "authenticated", "instance_url": state.auth.instance_url}
    except AuthenticationError as e:
        return JSONResponse({"error": str(e)}, status_code=401)
    except Exception as e:
        return JSONResponse({"error": f"Erro na autenticação: {str(e)}"}, status_code=500)


# ── API: Upload de Planilha ────────────────────────────
@app.post("/api/upload")
async def upload_planilha(file: UploadFile = File(...)):
    """Recebe a planilha de precificação e extrai os códigos."""
    if not file.filename.endswith('.xlsx'):
        return JSONResponse({"error": "Apenas arquivos .xlsx são permitidos."}, status_code=400)

    try:
        contents = await file.read()

        # Salva o arquivo para uso futuro (preview e execute)
        temp_path = settings.PLANILHAS_DIR / "temp_upload.xlsx"
        settings.PLANILHAS_DIR.mkdir(parents=True, exist_ok=True)
        with open(temp_path, "wb") as f:
            f.write(contents)

        # Lemos o arquivo para extrair códigos
        df = pd.read_excel(contents, header=None, engine='openpyxl')

        # Procura a coluna "CÓDIGO" varrendo as primeiras 6 linhas
        col_codigo = -1
        header_row_idx = -1
        search_terms = ["CÓDIGO", "CODIGO", "ITEM"]

        for row_idx in range(min(6, len(df))):
            row_vals = df.iloc[row_idx].astype(str).tolist()
            for col_idx, val in enumerate(row_vals):
                val_upper = val.upper().strip()
                if any(term in val_upper for term in search_terms):
                    col_codigo = col_idx
                    header_row_idx = row_idx
                    break
            if col_codigo != -1:
                break

        if col_codigo == -1:
            col_codigo = 0
            header_row_idx = 3

        data_start = header_row_idx + 1
        df_dados = df.iloc[data_start:]

        codigos_encontrados = []
        if col_codigo < len(df.columns):
            for val in df_dados.iloc[:, col_codigo]:
                val_str = str(val).replace('.0', '').strip()
                if val_str and val_str.lower() != "nan" and val_str.lower() != "none":
                    try:
                        int(float(val_str))
                        if val_str not in codigos_encontrados:
                            codigos_encontrados.append(val_str)
                    except (ValueError, TypeError):
                        pass

        return {
            "filename": file.filename,
            "codigos": codigos_encontrados,
            "produtos_count": len(codigos_encontrados)
        }
    except Exception as e:
        return JSONResponse({"error": f"Erro ao ler a planilha: {str(e)}"}, status_code=500)


# ── API: Analisar Produtos (Descoberta de Campanhas) ───
@app.post("/api/analyze")
async def analyze(req: SearchRequest):
    """Retorna todos os motores e campanhas para os códigos da planilha de forma otimizada."""
    if not state.auth:
        return JSONResponse({"error": "Não autenticado."}, status_code=401)

    if not req.codigos:
        return JSONResponse({"error": "Informe os códigos dos produtos."}, status_code=400)

    try:
        extrator = Extrator(state.auth)
        codigos_limpos = [str(c).strip() for c in req.codigos if str(c).strip()]

        # 1. Busca todos os motores mapeados com filiais e campanhas
        await log("INFO", "ANÁLISE", "Buscando motores e campanhas no Salesforce...")
        motores = await extrator.listar_motores_completos()

        # 2. Define o total de produtos existentes como zero nesta fase rápida
        for m in motores:
            m["total_produtos_existentes"] = len(codigos_limpos)

        # 3. Extrai todas as campanhas únicas para os dropdowns de filtros na UI
        campanhas_set = set()
        for m in motores:
            for c in m["campanhas"]:
                if c:
                    campanhas_set.add(c)
        campanhas_list = sorted(list(campanhas_set))

        await log("SUCCESS", "ANÁLISE",
                  f"Análise concluída: {len(motores)} motores mapeados com campanhas e filiais, "
                  f"{len(campanhas_list)} campanhas encontradas.")

        return {
            "motores": motores,
            "campanhas": campanhas_list,
            "itens_novos": [],
            "total_registros_existentes": 0,
        }
    except AuthExpiredError:
        state.auth = None
        return JSONResponse({"error": "Sessão expirada. Re-autentique."}, status_code=401)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── API: Preview Unificado (Delete + Insert) ───────────
@app.post("/api/pricing/preview")
async def pricing_preview(req: PricingPreviewRequest):
    """Preview unificado: mostra o que será deletado + o que será inserido, por filial."""
    if not state.auth:
        return JSONResponse({"error": "Não autenticado."}, status_code=401)

    if not req.motores:
        return JSONResponse({"error": "Nenhum motor selecionado."}, status_code=400)

    try:
        extrator = Extrator(state.auth)
        codigos_upload = _extrair_codigos_upload()

        # Transforma os motores do request em dict simples
        motores_list = [m.model_dump() for m in req.motores]
        motor_names = [m["name"] for m in motores_list]

        # Busca registros de produtos existentes no Salesforce para calcular quantidade de deletes
        registros_sf = await extrator.extrair_produtos_motor(codigos_upload)
        registros_deletar = sum(
            1 for r in registros_sf
            if r.get("ModifierEngine__r.Name", "") in motor_names
        )

        # Mapeamento de campanhas por motor para repassar ao precificador
        campanhas_por_motor = {}
        for m in motores_list:
            campanhas_por_motor[m["id"]] = ", ".join(m["campanhas"]) if m["campanhas"] else "Sem Campanha"

        # Calcula preços (preview unificado)
        from backend.src.ator5_precificador import Precificador
        precificador = Precificador(state.auth)
        resultado = await precificador.preview_unificado(motores_list, campanhas_por_motor)
        mapeamento = precificador.mapear_filiais(motores_list)

        # Identifica itens novos
        codigos_encontrados = set(str(r.get("ProductCode__c", "")) for r in registros_sf)
        itens_novos = [c for c in codigos_upload if c not in codigos_encontrados]

        return {
            "registros_deletar": registros_deletar,
            "registros_inserir": resultado["insercoes_projetadas"],
            "motores_count": len(motores_list),
            "produtos_lidos": resultado["produtos_lidos"],
            "itens_novos": itens_novos,
            "detalhes": resultado["detalhes"],
            "mapeamento_filiais": mapeamento,
        }
    except FileNotFoundError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── API: Executar Precificação (Delete → Insert) ──────
@app.post("/api/pricing/execute")
async def pricing_execute(req: PricingExecuteRequest, background_tasks: BackgroundTasks):
    """Pipeline unificado: DELETE → INSERT em background."""
    if not state.auth:
        return JSONResponse({"error": "Não autenticado."}, status_code=401)

    if not req.motores:
        return JSONResponse({"error": "Nenhum motor selecionado."}, status_code=400)

    if state.task_running:
        return JSONResponse({"error": "Operação em andamento."}, status_code=409)

    state.task_running = True
    state.task_result = None
    get_broadcaster().clear()

    # Extrai motores e campanhas
    motores_list = [m.model_dump() for m in req.motores]
    campanhas_por_motor = {}
    for m in motores_list:
        campanhas_por_motor[m["id"]] = ", ".join(m["campanhas"]) if m["campanhas"] else "Sem Campanha"

    codigos = _extrair_codigos_upload()

    background_tasks.add_task(
        _pipeline_precificacao, motores_list, codigos, campanhas_por_motor, req.incluir_novos
    )

    return {"status": "started", "message": "Pipeline de precificação iniciado em background."}


# ── API: Status ────────────────────────────────────────
@app.get("/api/status")
async def status():
    """Retorna status da operação corrente."""
    return {
        "authenticated": state.auth is not None,
        "task_running": state.task_running,
        "task_result": state.task_result,
    }


# ── API: Backups ───────────────────────────────────────
@app.get("/api/backups")
async def listar_backups():
    """Lista backups disponíveis."""
    safety = SafetyGuard()
    return {"backups": safety.listar_backups()}


# ── API: Download Template ─────────────────────────────
@app.get("/api/template/download")
async def download_template():
    """Retorna a planilha template real (Planilhas bases/Template.xlsx)."""
    try:
        template_path = settings.PLANILHAS_DIR / "Template.xlsx"
        if template_path.exists():
            return FileResponse(
                path=template_path,
                filename="Template_Precificacao.xlsx",
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        return JSONResponse({"error": "Template não encontrado."}, status_code=404)
    except Exception as e:
        return JSONResponse({"error": f"Erro: {str(e)}"}, status_code=500)


# ── WebSocket: Logs ────────────────────────────────────
@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """Stream de logs em tempo real para o frontend."""
    await websocket.accept()
    broadcaster = get_broadcaster()

    async def send_log(entry: dict):
        try:
            await websocket.send_json(entry)
        except Exception:
            pass

    broadcaster.register(send_log)

    # Envia histórico acumulado
    for entry in broadcaster.history:
        await websocket.send_json(entry)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        broadcaster.unregister(send_log)


# ── Helper: extrai códigos do upload ───────────────────
def _extrair_codigos_upload() -> list[str]:
    """Extrai códigos da planilha temp_upload.xlsx (mesma lógica do upload endpoint)."""
    temp_path = settings.PLANILHAS_DIR / "temp_upload.xlsx"
    if not temp_path.exists():
        raise FileNotFoundError("Planilha não encontrada. Faça o upload novamente.")

    df = pd.read_excel(temp_path, header=None, engine='openpyxl')

    col_codigo = -1
    header_row_idx = -1
    for row_idx in range(min(6, len(df))):
        row_vals = df.iloc[row_idx].astype(str).tolist()
        for col_idx, val in enumerate(row_vals):
            val_upper = val.upper().strip()
            if "CÓDIGO" in val_upper or "CODIGO" in val_upper or "ITEM" in val_upper:
                col_codigo = col_idx
                header_row_idx = row_idx
                break
        if col_codigo != -1:
            break

    if col_codigo == -1:
        col_codigo = 0
        header_row_idx = 3

    data_start = header_row_idx + 1
    codigos = []
    for val in df.iloc[data_start:, col_codigo]:
        val_str = str(val).replace('.0', '').strip()
        if val_str and val_str.lower() not in ("nan", "none"):
            try:
                int(float(val_str))
                if val_str not in codigos:
                    codigos.append(val_str)
            except (ValueError, TypeError):
                pass

    return codigos


# ── Pipeline Unificado (background) ───────────────────
async def _pipeline_precificacao(
    motores: list[dict],
    codigos: list[str],
    campanhas_por_motor: dict,
    incluir_novos: bool,
):
    """Pipeline: DELETE registros antigos → INSERT novos com descontos recalculados."""
    try:
        await log("INFO", "PIPELINE",
                  f"Iniciando precificação: {len(motores)} motor(es), {len(codigos)} códigos...")

        # ── FASE 1: DELEÇÃO ────────────────────────────
        await log("INFO", "PIPELINE", "═══ FASE 1: DELEÇÃO DE REGISTROS ANTIGOS ═══")

        extrator = Extrator(state.auth)
        dados = await extrator.extrair_produtos_motor(codigos)

        motor_names = [m["name"] for m in motores]
        cerebro = Cerebro()
        resultado = await cerebro.processar(dados, codigos, motor_names)

        relatorio_delete = {"deletados": 0, "falhos": 0, "total_processados": 0}

        if resultado.ids_para_deletar:
            executor = Executor(state.auth)
            relatorio_delete = await executor.executar_delecao(resultado)

            if relatorio_delete.get("falhos", 0) > 0:
                await log("WARNING", "PIPELINE",
                          f"{relatorio_delete['falhos']} registros não deletados "
                          f"(possivelmente itens novos ou protegidos). Continuando com inserção...")
        else:
            await log("INFO", "PIPELINE",
                      "Nenhum registro existente para deletar. Todos são itens novos.")

        # ── FASE 2: INSERÇÃO ───────────────────────────
        await log("INFO", "PIPELINE", "═══ FASE 2: INSERÇÃO DE NOVOS REGISTROS ═══")

        from backend.src.ator5_precificador import Precificador
        precificador = Precificador(state.auth)
        payload = await precificador.gerar_payload_insercao(motores)

        relatorio_insert = {"inseridos": 0, "falhos": 0, "total_processados": 0}

        if payload:
            executor = Executor(state.auth)
            relatorio_insert = await executor.executar_insercao(payload)
        else:
            await log("WARNING", "PIPELINE",
                      "Nenhum registro gerado para inserção. "
                      "Verifique se a planilha foi enviada e se há preços no Salesforce.")

        # ── RESULTADO FINAL ────────────────────────────
        state.task_result = {
            "deletados": relatorio_delete.get("deletados", 0),
            "delete_falhos": relatorio_delete.get("falhos", 0),
            "inseridos": relatorio_insert.get("inseridos", 0),
            "insert_falhos": relatorio_insert.get("falhos", 0),
        }

        await log("SUCCESS", "PIPELINE",
                  f"Pipeline concluído! "
                  f"Deletados: {state.task_result['deletados']}, "
                  f"Inseridos: {state.task_result['inseridos']}")

    except Exception as e:
        await log("ERROR", "PIPELINE", f"Erro no pipeline: {str(e)}")
        state.task_result = {"error": str(e)}
    finally:
        state.task_running = False


# ── Entrypoint ─────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.server:app",
        host=settings.HOST,
        port=settings.PORT,
    )
