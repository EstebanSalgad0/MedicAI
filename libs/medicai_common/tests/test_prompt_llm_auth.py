from unittest.mock import patch

import pytest
from fastapi import HTTPException

from medicai_common import auth, llm, prompts


def test_prompt_por_modulo_incluye_nucleo_y_solo_su_modulo():
    p1 = prompts.para_modulo(1, "Resume la ficha.")
    assert "APOYAS, NUNCA DECIDES" in p1 and "TRAZABILIDAD TOTAL" in p1 and "LÍMITES" in p1
    assert "FICHA POR DICTADO" in p1 and "TRIAJE DE URGENCIA" not in p1 and "# TAREA ACTUAL" in p1
    p2 = prompts.para_modulo(2)
    assert "131 (SAMU)" in p2 and "FICHA POR DICTADO" not in p2
    assert set(prompts.SECCIONES) >= {"ROL E IDENTIDAD", "MÓDULO 3", "ARQUITECTURA TÉCNICA", "LÍMITES"}


def test_llm_externo_bloqueado_por_defecto_y_nunca_con_datos_clinicos(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_API_KEY", "x")
    monkeypatch.delenv("LLM_ALLOW_EXTERNAL", raising=False)
    assert not llm.enabled()
    monkeypatch.setenv("LLM_ALLOW_EXTERNAL", "true")
    assert llm.enabled() and not llm.enabled(clinical=True)
    with patch.object(llm.httpx, "post", side_effect=AssertionError("no debe llamarse")):
        assert llm.complete("s", "datos clínicos", clinical=True) is None


def test_llm_local_permitido_con_datos_clinicos(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    assert llm.is_local() and llm.enabled(clinical=True)
    monkeypatch.setenv("LLM_PROVIDER", "none")
    assert not llm.enabled()


def test_token_de_funcionario_y_roles():
    tok, _ = auth.emitir(auth.Funcionario(sub="1-9", nombre="Dra. Ana", rol="medico", run="1-9",
                                          establecimientos=["hrt"], metodo="claveunica"))
    f = auth.funcionario(f"Bearer {tok}")
    assert f.clinico and f.establecimientos == ["hrt"] and auth.requiere_clinico(f) is f
    admin, _ = auth.emitir(auth.Funcionario(sub="admin", nombre="admin", rol="admin"))
    with pytest.raises(HTTPException) as e:
        auth.requiere_clinico(auth.funcionario(f"Bearer {admin}"))
    assert e.value.status_code == 403
    # un rol clínico con cuenta local (sin ClaveÚnica) tampoco accede a fichas
    local, _ = auth.emitir(auth.Funcionario(sub="x", nombre="x", rol="medico", metodo="local"))
    with pytest.raises(HTTPException):
        auth.requiere_clinico(auth.funcionario(f"Bearer {local}"))
    with pytest.raises(HTTPException) as e:
        auth.funcionario("Bearer basura")
    assert e.value.status_code == 401
