from __future__ import annotations

from fastapi import Depends

from medicai_common.contracts import DialogRequest, DialogResponse
from medicai_common.service import create_service, require_internal, setup_logging

from . import dialog, reglas

SERVICE = "orientacion"
log = setup_logging(SERVICE)
app = create_service(SERVICE, "Orientación inicial de síntomas basada en reglas clínicas auditables: "
                              "sugiere el nivel de atención (urgencia, prioritario, CESFAM, autocuidado).")


@app.post("/dialog", response_model=DialogResponse, dependencies=[Depends(require_internal)], tags=["chat"])
def post_dialog(req: DialogRequest) -> DialogResponse:
    return dialog.handle(req)


@app.get("/rules", tags=["dashboard"])
def rules():
    """Transparencia: expone categorías y síntomas reconocidos para revisión clínica."""
    return {
        "categorias": [{"id": k, "nombre": v} for k, v in dialog.CATEGORIAS],
        "sintomas": reglas.SINTOMAS_CONOCIDOS,
        "niveles": {k: v[1] for k, v in dialog.NIVELES.items()},
    }
