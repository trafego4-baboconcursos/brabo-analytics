"""Cliente da API do Unnichat: só leitura, com ritmo controlado e novas tentativas."""
from __future__ import annotations

import logging
import threading
import time

import requests

API_BASE = "https://unnichat.com.br/api"
log = logging.getLogger("coletor.unnichat")


class Ritmo:
    """No máximo N requisições por segundo, somando todas as threads.
    A doc cita limites de 6/s e 25/s conforme a rota; o padrão (5/s) fica
    abaixo do menor."""

    def __init__(self, por_segundo: float):
        self._intervalo = 1.0 / por_segundo
        self._lock = threading.Lock()
        self._proxima = 0.0

    def esperar(self) -> None:
        with self._lock:
            agora = time.monotonic()
            espera = self._proxima - agora
            self._proxima = max(agora, self._proxima) + self._intervalo
        if espera > 0:
            time.sleep(espera)


class Unnichat:
    def __init__(self, tokens: dict[str, str], ritmo: Ritmo, tentativas: int = 4):
        self._tokens = tokens
        self._ritmo = ritmo
        self._tentativas = tentativas
        self._sessao = requests.Session()

    def _get(self, conexao: str, caminho: str, params: dict | None = None) -> dict:
        token = self._tokens[conexao]
        for tentativa in range(1, self._tentativas + 1):
            self._ritmo.esperar()
            resp = self._sessao.get(
                f"{API_BASE}{caminho}", params=params, timeout=30,
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                pausa = 2 ** tentativa
                log.warning("%s %s → %s, nova tentativa em %ss", conexao, caminho, resp.status_code, pausa)
                time.sleep(pausa)
                continue
            resp.raise_for_status()
            return resp.json()
        resp.raise_for_status()
        return resp.json()

    def mensagens(self, conexao: str, contact_id: str) -> list[dict]:
        return self._get(conexao, f"/contact/{contact_id}/messages").get("data") or []

    def responsavel(self, conexao: str, contact_id: str) -> dict:
        """{} quando o contato foi apagado no Unnichat (400 "Contact not exists").
        Eles apagam contatos para liberar espaço; isso não pode travar a fila."""
        try:
            return self._get(conexao, f"/contact/{contact_id}/assign")
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 400:
                return {}
            raise

    def contato(self, conexao: str, contact_id: str) -> dict:
        return self._get(conexao, f"/contact/{contact_id}").get("data") or {}

    def atendentes(self, conexao: str) -> list[dict]:
        todos, pagina = [], 1
        while True:
            resp = self._get(conexao, "/attendants", {"page": pagina, "perPage": 100})
            todos.extend(resp.get("data") or [])
            if not (resp.get("metadata") or {}).get("hasNext"):
                return todos
            pagina += 1
