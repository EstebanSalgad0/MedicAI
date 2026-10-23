"""CESFAM piloto (datos de referencia compartidos).

Corresponden a los centros con mayor concentración de consultas según el
análisis REM de la formulación. La lista definitiva la fijan las entidades
asociadas en la Fase 1 (línea base); basta con editar este archivo.
"""

CENTROS: list[tuple[str, str, str]] = [
    ("las_americas", "CESFAM Las Américas", "Talca"),
    ("julio_contardo", "CESFAM Dr. Julio Contardo", "Talca"),
    ("curico_centro", "CESFAM Curicó Centro", "Curicó"),
    ("san_juan_de_dios", "CESFAM San Juan de Dios", "Linares"),
    ("armando_williams", "CESFAM Armando Williams", "Cauquenes"),
]
# Hospital de referencia (nivel secundario). No se mezcla con CENTROS para que los
# flujos de APS (agenda de CESFAM, guía de ruta) sigan ofreciendo solo CESFAM.
HOSPITAL: tuple[str, str, str] = ("hrt", "Hospital Regional de Talca", "Talca")
ESTABLECIMIENTOS = CENTROS + [HOSPITAL]
CENTRO_NOMBRE = {k: n for k, n, _ in ESTABLECIMIENTOS}
