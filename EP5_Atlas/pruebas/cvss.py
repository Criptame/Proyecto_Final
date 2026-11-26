"""Cálculo del puntaje base CVSS v3.1 (especificación FIRST, sección 7.1)."""
import math

_W = {
    "AV": {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2},
    "AC": {"L": 0.77, "H": 0.44},
    "UI": {"N": 0.85, "R": 0.62},
    "C": {"H": 0.56, "L": 0.22, "N": 0.0},
    "I": {"H": 0.56, "L": 0.22, "N": 0.0},
    "A": {"H": 0.56, "L": 0.22, "N": 0.0},
}
_PR = {"U": {"N": 0.85, "L": 0.62, "H": 0.27}, "C": {"N": 0.85, "L": 0.68, "H": 0.5}}


def _roundup(x):
    i = int(round(x * 100000))
    return i / 100000.0 if i % 10000 == 0 else (math.floor(i / 10000) + 1) / 10.0


def puntaje(vector: str) -> float:
    m = dict(p.split(":") for p in vector.split("/"))
    s = m["S"]
    iss = 1 - (1 - _W["C"][m["C"]]) * (1 - _W["I"][m["I"]]) * (1 - _W["A"][m["A"]])
    impacto = 6.42 * iss if s == "U" else 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15
    explot = 8.22 * _W["AV"][m["AV"]] * _W["AC"][m["AC"]] * _PR[s][m["PR"]] * _W["UI"][m["UI"]]
    if impacto <= 0:
        return 0.0
    if s == "U":
        return _roundup(min(impacto + explot, 10))
    return _roundup(min(1.08 * (impacto + explot), 10))


def severidad(score: float) -> str:
    if score == 0:
        return "Ninguna"
    if score < 4:
        return "Baja"
    if score < 7:
        return "Media"
    if score < 9:
        return "Alta"
    return "Crítica"


if __name__ == "__main__":
    # Verificación contra ejemplos publicados por FIRST
    assert puntaje("AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") == 9.8
    assert puntaje("AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H") == 10.0
    assert puntaje("AV:N/AC:L/PR:L/UI:R/S:C/C:L/I:L/A:N") == 5.4
    assert puntaje("AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N") == 5.3
    print("CVSS OK")
