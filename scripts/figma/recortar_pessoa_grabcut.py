"""Recorta uma pessoa de uma foto/arte (fundo transparente) com GrabCut do OpenCV.

Serve quando não há rembg: o usuário marca o retângulo do recorte, uma elipse
"certamente pessoa" (rosto) e, se houver, áreas "certamente fundo" (texto da arte
por cima da foto). Usado no V1 do perpétuo TJ-SP (Ivan do AD209, 04/11/26).

    python scripts/figma/recortar_pessoa_grabcut.py ENTRADA.jpg SAIDA.png \
        --corte 200,80,940,690 --rosto 565,360,70,90 \
        [--fundo 0,225,415,520 ...]

Coordenadas na imagem original. --rosto = cx,cy,raio_x,raio_y.
O torso abaixo do rosto entra como "provavelmente pessoa".
"""
import argparse

import cv2
import numpy as np
from PIL import Image


def _quad(s):
    return tuple(int(v) for v in s.split(","))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entrada")
    ap.add_argument("saida")
    ap.add_argument("--corte", type=_quad, required=True, help="x0,y0,x1,y1")
    ap.add_argument("--rosto", type=_quad, required=True, help="cx,cy,rx,ry")
    ap.add_argument("--fundo", type=_quad, action="append", default=[], help="x0,y0,x1,y1 certamente fundo")
    ap.add_argument("--aparar-base", type=int, default=0, help="px cortados da base (ex.: pontas de objeto na mão)")
    a = ap.parse_args()

    img = cv2.imdecode(np.fromfile(a.entrada, np.uint8), cv2.IMREAD_COLOR)
    x0, y0, x1, y1 = a.corte
    c = img[y0:y1, x0:x1].copy()
    h, w = c.shape[:2]
    cx, cy, rx, ry = a.rosto
    cx, cy = cx - x0, cy - y0

    mask = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
    cv2.ellipse(mask, (cx, cy - ry // 3), (int(rx * 1.7), int(ry * 1.8)), 0, 0, 360, cv2.GC_PR_FGD, -1)
    ombro = min(h - 1, cy + ry * 2)
    mask[ombro:, max(0, cx - rx * 4):min(w, cx + rx * 4)] = cv2.GC_PR_FGD
    cv2.ellipse(mask, (cx, cy), (rx, ry), 0, 0, 360, cv2.GC_FGD, -1)
    mask[:, :40] = cv2.GC_BGD
    mask[:, -30:] = cv2.GC_BGD
    mask[:30, :] = cv2.GC_BGD
    for fx0, fy0, fx1, fy1 in a.fundo:
        mask[max(0, fy0 - y0):max(0, fy1 - y0), max(0, fx0 - x0):max(0, fx1 - x0)] = cv2.GC_BGD

    bg, fg = np.zeros((1, 65)), np.zeros((1, 65))
    cv2.grabCut(c, mask, None, bg, fg, 8, cv2.GC_INIT_WITH_MASK)
    m = np.where((mask == 1) | (mask == 3), 255, 0).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    k = 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])
    m = np.where(lab == k, 255, 0).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    m = cv2.GaussianBlur(m, (5, 5), 0)

    rgba = cv2.cvtColor(c, cv2.COLOR_BGR2RGBA)
    rgba[:, :, 3] = m
    im = Image.fromarray(rgba)
    if a.aparar_base:
        im = im.crop((0, 0, im.width, im.height - a.aparar_base))
    im = im.crop(im.split()[3].getbbox())
    im.save(a.saida)
    print(a.saida, im.size)


if __name__ == "__main__":
    main()
