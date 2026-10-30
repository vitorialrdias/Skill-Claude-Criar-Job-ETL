"""Refresh de datasets do Power BI via service principal.

credenciais['powerbi'] = {"tenant_id": "...", "client_id": "...", "client_secret": "..."}
"""
import logging
import requests

logger = logging.getLogger(__name__)


class PowerbiRequest:
    @staticmethod
    def _token(cfg: dict) -> str:
        r = requests.post(
            f"https://login.microsoftonline.com/{cfg['tenant_id']}/oauth2/v2.0/token",
            data={"grant_type": "client_credentials", "client_id": cfg["client_id"],
                  "client_secret": cfg["client_secret"],
                  "scope": "https://analysis.windows.net/powerbi/api/.default"},
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["access_token"]

    @staticmethod
    def update_dataset(credenciais: dict, workspace_id: str, datasets: list) -> dict:
        resultado = {}
        cfg = credenciais.get("powerbi")
        if not cfg:
            logger.warning("Seção 'powerbi' ausente nas credenciais — refresh ignorado.")
            return resultado
        headers = {"Authorization": f"Bearer {PowerbiRequest._token(cfg)}"}
        for d in datasets:
            url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{d['id']}/refreshes"
            r = requests.post(url, headers=headers, json={"notifyOption": "NoNotification"}, timeout=60)
            ok = r.status_code in (200, 202)
            resultado[d["nome"]] = ok
            (logger.info if ok else logger.error)(f"Refresh '{d['nome']}': HTTP {r.status_code}")
        return resultado
