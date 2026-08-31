#!/usr/bin/env python3
"""Extract text from an image-only PDF with RapidOCR."""

import argparse
import os

import pypdfium2 as pdfium
from rapidocr import RapidOCR


def extract_pdf(path: str) -> str:
    scale = float(os.environ.get("OCR_RENDER_SCALE", "2.5"))
    minimum_score = float(os.environ.get("OCR_MIN_SCORE", "0.5"))
    engine = RapidOCR()
    document = pdfium.PdfDocument(path)
    pages = []

    try:
        for index in range(len(document)):
            page = document[index]
            try:
                image = page.render(scale=scale).to_pil()
                result = engine(image)
                lines = [
                    text.strip()
                    for text, score in zip(result.txts or (), result.scores or ())
                    if text.strip() and score >= minimum_score
                ]
                if lines:
                    pages.append(f"## Page {index + 1}\n\n" + "\n".join(lines))
            finally:
                page.close()
    finally:
        document.close()

    return "\n\n".join(pages).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf")
    args = parser.parse_args()
    print(extract_pdf(args.pdf))


if __name__ == "__main__":
    main()
