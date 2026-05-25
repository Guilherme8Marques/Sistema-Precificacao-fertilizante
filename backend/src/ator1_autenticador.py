"""ATOR 1 — AUTENTICADOR
Extrai o Session ID do Salesforce.

Estratégia (3 tentativas):
1. Verifica perfil salvo do Playwright (sessão anterior) → INSTANTÂNEO
2. Tenta ler cookies do Chrome no disco (funciona se Chrome FECHADO)
3. Abre janela para login manual (salva sessão para próximas vezes)

Na PRÁTICA para o usuário:
- 1ª vez: abre janela, faz login UMA VEZ, sessão fica salva
- Próximas vezes: conecta em ~2 segundos sem abrir nenhuma janela
- Sessão expirou: abre janela de novo automaticamente
"""

import asyncio
import json
import os
import base64
import sqlite3
import subprocess
import tempfile
import webbrowser
from pathlib import Path
from typing import Optional

from backend.config.settings import settings
from backend.utils.api_client import SalesforceAuth
from backend.utils.logger import log


ACTOR_NAME = "AUTENTICADOR"


class Autenticador:
    """Extrai Session ID do Salesforce."""

    def __init__(self, salesforce_url: Optional[str] = None):
        self.salesforce_url = salesforce_url or settings.SF_BASE_URL
        self.profile_dir = str(settings.DATA_DIR / "chrome_profile")

    async def autenticar(self) -> SalesforceAuth:
        """Autentica no Salesforce. Tenta reusar sessão salva primeiro.

        Fluxo:
        1. Verifica sessão salva (perfil Playwright) → sem abrir janela
        2. Tenta ler cookie do Chrome (se fechado) → sem abrir janela
        3. Abre janela para login manual → salva sessão
        """
        await log("INFO", ACTOR_NAME, "Iniciando autenticacao...")

        # ── Tentativa 1: Sessão salva no perfil dedicado ──
        await log("INFO", ACTOR_NAME, "Verificando sessao salva...")
        auth = await self._tentar_sessao_salva()
        if auth:
            return auth

        # ── Tentativa 2: Ler cookie do Chrome no disco ────
        await log("INFO", ACTOR_NAME, "Verificando cookies do Chrome...")
        session_id = self._ler_cookie_chrome()
        if session_id:
            auth = SalesforceAuth(session_id=session_id, instance_url=self.salesforce_url)
            if await self._validar_sessao(auth):
                await log("SUCCESS", ACTOR_NAME,
                          "Sessao do Chrome reutilizada com sucesso!")
                return auth
            else:
                await log("WARNING", ACTOR_NAME,
                          "Cookie do Chrome expirado.")

        # ── Tentativa 3: Abrir janela para login ──────────
        await log("INFO", ACTOR_NAME,
                  "Abrindo janela para login no Salesforce...")
        await log("INFO", ACTOR_NAME,
                  "Faca login na janela que abrir. Ela fechara automaticamente.")
        await log("INFO", ACTOR_NAME,
                  ">> Apos o primeiro login, as proximas conexoes serao instantaneas. <<")

        return await self._login_via_playwright()

    # ── Tentativa 1: Sessão salva ──────────────────────────
    async def _tentar_sessao_salva(self) -> Optional[SalesforceAuth]:
        """Tenta reusar sessão do perfil Playwright salvo (sem abrir janela)."""
        profile_path = Path(self.profile_dir)
        if not profile_path.exists():
            return None

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                # Abre headless (invisível) só para checar cookie
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=self.profile_dir,
                    channel="chrome",
                    headless=True,
                    args=["--no-first-run", "--disable-blink-features=AutomationControlled"],
                )

                try:
                    page = context.pages[0] if context.pages else await context.new_page()
                    await page.goto(self.salesforce_url, wait_until="domcontentloaded",
                                    timeout=15_000)

                    sid = await self._check_sid_playwright(context)
                    if sid:
                        instance_url = self._extract_instance_url(page.url)
                        auth = SalesforceAuth(session_id=sid, instance_url=instance_url)

                        if await self._validar_sessao(auth):
                            await log("SUCCESS", ACTOR_NAME,
                                      f"Sessao salva reutilizada! Conectado em {instance_url}")
                            return auth
                        else:
                            await log("WARNING", ACTOR_NAME,
                                      "Sessao salva expirada. Novo login necessario.")

                finally:
                    await context.close()

        except Exception as e:
            await log("WARNING", ACTOR_NAME, f"Erro ao verificar sessao salva: {e}")

        return None

    # ── Tentativa 2: Cookie do Chrome ──────────────────────
    def _ler_cookie_chrome(self) -> Optional[str]:
        """Tenta ler cookie 'sid' do Chrome (funciona se Chrome estiver fechado)."""
        try:
            chrome_data = Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data"
            if not chrome_data.exists():
                return None

            key = self._get_chrome_encryption_key(chrome_data)
            if not key:
                return None

            cookie_db = chrome_data / "Default" / "Network" / "Cookies"
            if not cookie_db.exists():
                return None

            # Tenta copiar (falha se Chrome aberto — esperado)
            temp_path = Path(tempfile.gettempdir()) / "chrome_cookies_copy.db"
            try:
                import shutil
                shutil.copy2(cookie_db, temp_path)
            except PermissionError:
                # Chrome aberto — não conseguimos ler
                return None

            try:
                conn = sqlite3.connect(str(temp_path))
                cur = conn.cursor()
                cur.execute(
                    "SELECT encrypted_value, host_key FROM cookies "
                    "WHERE name = 'sid' "
                    "AND (host_key LIKE '%.salesforce.com' OR host_key LIKE '%.force.com') "
                    "ORDER BY last_access_utc DESC LIMIT 1"
                )
                row = cur.fetchone()
                conn.close()

                if not row:
                    return None

                encrypted_value, _ = row
                return self._decrypt_cookie_value(encrypted_value, key)

            finally:
                temp_path.unlink(missing_ok=True)

        except Exception:
            return None

    def _get_chrome_encryption_key(self, chrome_data: Path) -> Optional[bytes]:
        """Extrai chave de encriptacao do Chrome via Windows DPAPI."""
        try:
            import ctypes
            import ctypes.wintypes

            with open(chrome_data / "Local State", "r", encoding="utf-8") as f:
                local_state = json.load(f)

            encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])[5:]

            class DATA_BLOB(ctypes.Structure):
                _fields_ = [
                    ("cbData", ctypes.wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char)),
                ]

            blob_in = DATA_BLOB(
                len(encrypted_key),
                ctypes.create_string_buffer(encrypted_key, len(encrypted_key)),
            )
            blob_out = DATA_BLOB()

            ok = ctypes.windll.crypt32.CryptUnprotectData(
                ctypes.byref(blob_in), None, None, None, None, 0,
                ctypes.byref(blob_out),
            )

            if not ok:
                return None

            key = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
            return key

        except Exception:
            return None

    def _decrypt_cookie_value(self, encrypted_value: bytes,
                                key: bytes) -> Optional[str]:
        """Decripta valor do cookie usando AES-256-GCM."""
        try:
            if not encrypted_value or len(encrypted_value) < 15:
                return None

            if encrypted_value[:3] not in (b"v10", b"v20"):
                try:
                    return encrypted_value.decode("utf-8")
                except Exception:
                    return None

            nonce = encrypted_value[3:15]
            ciphertext = encrypted_value[15:]

            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            aes = AESGCM(key)
            return aes.decrypt(nonce, ciphertext, None).decode("utf-8")

        except Exception:
            return None

    # ── Tentativa 3: Login via Playwright ──────────────────
    async def _login_via_playwright(self) -> SalesforceAuth:
        """Abre Chrome para login manual. Salva sessao para proximas vezes.

        Fluxo:
        1. Abre janela Chrome com perfil dedicado
        2. Navega ao Salesforce
        3. Monitora cookies a cada 3s NA JANELA ABERTA
        4. Quando encontra sid valido (pos-2FA) → fecha janela automaticamente
        5. Usa a URL configurada (settings) para validacao, nao a URL da pagina
        """
        from playwright.async_api import async_playwright

        await log("INFO", ACTOR_NAME,
                  ">> Faca login + 2FA na janela que abrir. <<")
        await log("INFO", ACTOR_NAME,
                  ">> A janela fechara AUTOMATICAMENTE apos o login. <<")

        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=self.profile_dir,
                channel="chrome",
                headless=False,
                args=[
                    "--no-first-run",
                    "--disable-blink-features=AutomationControlled",
                    "--window-size=900,700",
                ],
            )

            try:
                page = context.pages[0] if context.pages else await context.new_page()
                await page.goto(self.salesforce_url, wait_until="domcontentloaded",
                                timeout=30_000)

                # Se ja logado neste perfil, extrai e retorna direto
                sid = await self._check_sid_playwright(context)
                if sid:
                    auth = SalesforceAuth(
                        session_id=sid, instance_url=self.salesforce_url
                    )
                    if await self._validar_sessao(auth):
                        await log("SUCCESS", ACTOR_NAME,
                                  f"Sessao salva ativa! Conectado em {self.salesforce_url}")
                        return auth

                # Aguarda login + 2FA monitorando cookies na janela aberta
                auth = await self._aguardar_login_2fa(context, timeout_seconds=120)

                if not auth:
                    raise AuthenticationError(
                        "Timeout: login/2FA nao completado em 2 minutos."
                    )

                return auth

            finally:
                try:
                    await context.close()
                except Exception:
                    pass
                await log("INFO", ACTOR_NAME, "Janela fechada.")

    async def _aguardar_login_2fa(self, context,
                                    timeout_seconds: int = 120) -> Optional[SalesforceAuth]:
        """Monitora cookies na janela ABERTA ate encontrar um sid VALIDO.

        Diferenca critica das versoes anteriores:
        - Usa self.salesforce_url (URL configurada) para validacao,
          NAO page.url (que muda durante login/2FA e causava falha)
        - Valida via API (nao por URL da pagina ou presenca de cookie)
        - A janela fica aberta o tempo todo — so fecha quando valido
        """
        elapsed = 0
        interval = 3
        cookie_visto = False

        while elapsed < timeout_seconds:
            await asyncio.sleep(interval)
            elapsed += interval

            # Se o usuario fechou a janela, para de esperar
            try:
                if len(context.pages) == 0:
                    await log("WARNING", ACTOR_NAME,
                              "Janela fechada antes da validacao.")
                    return None
            except Exception:
                await log("WARNING", ACTOR_NAME,
                          "Chrome desconectado.")
                return None

            # Verifica cookie
            sid = await self._check_sid_playwright(context)

            if sid and not cookie_visto:
                cookie_visto = True
                await log("INFO", ACTOR_NAME,
                          "Cookie detectado! Aguardando 2FA ser concluido...")

            if sid:
                # Valida usando a URL CONFIGURADA (nao page.url!)
                auth = SalesforceAuth(
                    session_id=sid, instance_url=self.salesforce_url
                )
                if await self._validar_sessao(auth):
                    await log("SUCCESS", ACTOR_NAME,
                              "Login + 2FA concluidos! Sessao validada.")
                    return auth

            # Feedback
            if elapsed % 15 == 0:
                if cookie_visto:
                    await log("INFO", ACTOR_NAME,
                              f"Aguardando conclusao do 2FA... ({elapsed}s)")
                else:
                    await log("INFO", ACTOR_NAME,
                              f"Aguardando login... ({elapsed}s)")

        await log("ERROR", ACTOR_NAME,
                  f"Timeout de {timeout_seconds}s.")
        return None

    # ── Helpers ────────────────────────────────────────────
    async def _validar_sessao(self, auth: SalesforceAuth) -> bool:
        """Testa se o session_id ainda e valido fazendo uma chamada simples."""
        try:
            from backend.utils.api_client import SalesforceAPIClient
            client = SalesforceAPIClient(auth)
            return client.test_connection()
        except Exception:
            return False

    async def _check_sid_playwright(self, context) -> Optional[str]:
        """Verifica cookie 'sid' no contexto Playwright."""
        try:
            cookies = await context.cookies()
            for cookie in cookies:
                if cookie.get("name") == "sid":
                    domain = cookie.get("domain", "")
                    if "salesforce" in domain or "force" in domain:
                        return cookie["value"]
        except Exception:
            pass
        return None

    def _extract_instance_url(self, url: str) -> str:
        """Extrai instance URL da URL do navegador."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.hostname}"


class AuthenticationError(Exception):
    """Falha na autenticacao com o Salesforce."""
    pass
