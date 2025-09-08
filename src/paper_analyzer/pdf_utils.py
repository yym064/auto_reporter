import os
import json
import re
from typing import Dict, List, Tuple

import fitz  # PyMuPDF


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "paper"


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def extract_pdf(
    pdf_path: str,
    artifacts_dir: str,
) -> Dict:
    """
    Extract text, figures, and metadata from a PDF.

    Returns dict with keys: paper_id, text_path, figures_paths, metadata_path, metadata
    """
    filename = os.path.splitext(os.path.basename(pdf_path))[0]
    paper_id = slugify(filename)

    figures_dir = os.path.join(artifacts_dir, "figures", paper_id)
    text_dir = os.path.join(artifacts_dir, "clean_text")
    meta_dir = os.path.join(artifacts_dir, "metadata")

    ensure_dir(figures_dir)
    ensure_dir(text_dir)
    ensure_dir(meta_dir)

    text_path = os.path.join(text_dir, f"{paper_id}.txt")
    metadata_path = os.path.join(meta_dir, f"{paper_id}.json")

    doc = fitz.open(pdf_path)

    # Text extraction
    texts: List[str] = []
    for page in doc:
        try:
            texts.append(page.get_text("text"))
        except Exception:
            # fallback to simple text
            texts.append(page.get_text())
    full_text = "\n".join(texts)

    with open(text_path, "w", encoding="utf-8") as f:
        f.write(full_text)

    # Metadata extraction
    meta = doc.metadata or {}
    meta_obj = {
        "paper_id": paper_id,
        "source_pdf": os.path.relpath(pdf_path),
        "title": meta.get("title") or filename,
        "author": meta.get("author"),
        "creationDate": meta.get("creationDate"),
        "modDate": meta.get("modDate"),
        "keywords": meta.get("keywords"),
        "producer": meta.get("producer"),
        "encryption": doc.is_encrypted,
        "page_count": len(doc),
    }
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(meta_obj, f, ensure_ascii=False, indent=2)

    # Image extraction
    fig_paths: List[str] = []
    img_index = 0
    for page_index in range(len(doc)):
        page = doc[page_index]
        try:
            images = page.get_images(full=True)
        except Exception:
            images = []
        for img in images:
            xref = img[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                # If CMYK convert to RGB
                if pix.n >= 5:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                img_path = os.path.join(figures_dir, f"img_{img_index:03d}.png")
                pix.save(img_path)
                fig_paths.append(img_path)
                img_index += 1
            except Exception:
                # skip problematic images
                continue

    doc.close()

    return {
        "paper_id": paper_id,
        "text_path": text_path,
        "figures_paths": fig_paths,
        "metadata_path": metadata_path,
        "metadata": meta_obj,
        "text": full_text,
    }

