"""Geometría auxiliar. Coordenadas CTM12 (~4.9e6 / 2.0e6 m): todo en float64 y relativo a un origen local."""
import math


def punto_en_poligono(pt, anillos):
    x, y = pt[0], pt[1]
    dentro = False
    for pts in anillos:
        for (x0, y0, *_), (x1, y1, *_) in zip(pts, list(pts[1:]) + list(pts[:1])):
            if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
                dentro = not dentro
    return dentro


def anillos(shape):
    """Anillos de un shape de pyshp."""
    parts = list(shape.parts) + [len(shape.points)]
    return [shape.points[parts[i]:parts[i + 1]] for i in range(len(parts) - 1)]


def _centroide_anillo(pts):
    ox, oy = pts[0][0], pts[0][1]
    q = [(p[0] - ox, p[1] - oy) for p in pts]
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(q, q[1:] + q[:1]):
        c = x0 * y1 - x1 * y0
        a += c; cx += (x0 + x1) * c; cy += (y0 + y1) * c
    if abs(a) < 1e-12:
        return None, 0.0
    return (cx / (3 * a) + ox, cy / (3 * a) + oy), a / 2


def centroide(rings):
    """Centroide ponderado de los anillos; si cae fuera (polígono cóncavo / multiparte), un punto interior garantizado."""
    cs = [_centroide_anillo([tuple(p[:2]) for p in r]) for r in rings]
    cs_ok = [(c, a) for c, a in cs if c]
    if not cs_ok:
        return None
    tot = sum(abs(a) for _, a in cs_ok)
    cen = (sum(c[0] * abs(a) for c, a in cs_ok) / tot, sum(c[1] * abs(a) for c, a in cs_ok) / tot)
    if punto_en_poligono(cen, rings):
        return cen
    try:
        from shapely.geometry import Polygon
        mayor = max(rings, key=lambda r: abs(_centroide_anillo([tuple(p[:2]) for p in r])[1]))
        p = Polygon([tuple(q[:2]) for q in mayor]).buffer(0).representative_point()
        return (p.x, p.y)
    except Exception:
        return max(cs_ok, key=lambda x: abs(x[1]))[0]


def ancho_largo(g):
    """ANCHO / LARGO (cm) de un polígono shapely.

    Rectángulo mínimo rotado si el polígono lo llena (≥ 75 %); si no (franjas dobladas o en L),
    franja equivalente con la misma área y perímetro: A = a·l, P = 2(a + l) → a = (P/2 − √(P²/4 − 4A)) / 2."""
    mr = g.minimum_rotated_rectangle
    c = list(mr.exterior.coords)
    sd = sorted(math.dist(c[i], c[i + 1]) for i in range(4))
    if mr.area and g.area / mr.area >= 0.75:
        return sd[0] * 100, sd[2] * 100, "rectángulo"
    A, h = g.area, g.length / 2
    d = h * h - 4 * A
    a = (h - math.sqrt(d)) / 2 if d > 0 else math.sqrt(A)
    return a * 100, (A / a) * 100, "franja"


def medidas_no_corresponden(campos, medidas, tol_cm=60, tol_rel=0.35):
    """True si ANCHO_CM/LARGO_CM declarados difieren de la geometría más de max(tol_cm, tol_rel·valor)."""
    dims = sorted(campos)
    a, l = medidas
    return abs(dims[0] - a) > max(tol_cm, tol_rel * a) or abs(dims[1] - l) > max(tol_cm, tol_rel * l)
