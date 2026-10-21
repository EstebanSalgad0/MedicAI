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
CENTRO_NOMBRE = {k: n for k, n, _ in CENTROS}
