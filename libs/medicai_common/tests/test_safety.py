from medicai_common.safety import red_flag

ALARMA = ["mi mamá no respira bien ayuda", "se cayó y no despierta", "tengo un dolor fuerte en el pecho que baja al brazo",
          "me duele el pecho y el brazo izquierdo", "no puedo respirar", "se le durmió la mitad de la cara",
          "mi hijo está convulsionando", "131", "creo que se intoxicó con pastillas"]
SIN_ALARMA = ["tengo tos seca, fiebre alta, dificultad para respirar", "dolor en el pecho al esfuerzo, palpitaciones, mareos",
              "quiero pedir hora", "me duele la cabeza", "recuérdame el losartán", "no puedo ir a mi hora",
              "tengo 131 pastillas", "dolor de garganta fuerte"]


def test_detecta_alarmas():
    assert all(red_flag(t) == "urgencia" for t in ALARMA), [t for t in ALARMA if red_flag(t) != "urgencia"]


def test_no_secuestra_consultas_comunes():
    assert not [t for t in SIN_ALARMA if red_flag(t)]


def test_salud_mental():
    assert red_flag("ya no quiero vivir") == "salud_mental"
    assert red_flag("he pensado en suicidarme") == "salud_mental"
