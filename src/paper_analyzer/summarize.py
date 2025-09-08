from typing import Callable, Dict, List, Optional

from .lmstudio import LMStudioClient
from .text_utils import chunk_text


def summarize_single_paper(
    client: LMStudioClient,
    paper_text: str,
    paper_meta: Dict,
    max_chunk_chars: int = 4000,
    temperature: float = 0.2,
    max_output_tokens: Optional[int] = None,
    on_progress: Optional[Callable[[str, Dict], None]] = None,
    chunk_summary_words: Optional[str] = "120-160",
) -> str:
    """Map-reduce style summarization for a single paper."""
    title = paper_meta.get("title") or paper_meta.get("paper_id")
    chunks = chunk_text(paper_text, max_chars=max_chunk_chars)
    if not chunks:
        return ""

    if on_progress:
        try:
            on_progress("chunking_done", {"chunks": len(chunks), "title": title})
        except Exception:
            pass

    chunk_summaries: List[str] = []
    # Build word constraint text for chunk summaries
    word_clause = None
    if chunk_summary_words:
        txt = str(chunk_summary_words).strip()
        # normalize spaces
        txt = txt.replace(" ", "")
        if txt.isdigit():
            word_clause = f"{int(txt)} words."
        elif "-" in txt:
            parts = txt.split("-", 1)
            try:
                lo = int(parts[0])
                hi = int(parts[1])
                if lo > 0 and hi >= lo:
                    word_clause = f"{lo}-{hi} words."
            except ValueError:
                word_clause = None
        # Fallback: use as-is if it ends with 'words' or 'word'
        if not word_clause:
            cleaned = chunk_summary_words.strip()
            if cleaned:
                word_clause = cleaned if cleaned.lower().endswith("word") or cleaned.lower().endswith("words") else f"{cleaned} words."

    for i, ch in enumerate(chunks):
        prompt = (
            f"You are analyzing a research paper titled: {title}.\n"
            "Summarize the following excerpt focusing on: problem, method, data, key results, and limitations.\n"
            f"Use concise academic tone. {word_clause or '120-160 words.'}\n\n"
            f"Excerpt {i+1}/{len(chunks)}:\n" + ch
        )
        content = client.chat_complete([
            {"role": "system", "content": "You are a helpful research assistant."},
            {"role": "user", "content": prompt},
        ], temperature=temperature, max_tokens=max_output_tokens)
        chunk_summaries.append(content)

        if on_progress:
            try:
                on_progress("chunk_summarized", {"i": i + 1, "total": len(chunks), "title": title})
            except Exception:
                pass

    combined_prompt = (
        "Combine the following excerpt summaries into a cohesive summary of the paper.\n"
        "Structure the output with labeled sections: Problem, Method, Data, Results, Limitations.\n"
        "Keep it 250-350 words, objective, and specific.\n\n"
        f"Title: {title}\n\n"
        "Excerpt summaries:\n" + "\n\n".join(f"- {s}" for s in chunk_summaries)
    )

    if on_progress:
        try:
            on_progress("combining", {"title": title})
        except Exception:
            pass

    combined = client.chat_complete([
        {"role": "system", "content": "You are a helpful research assistant."},
        {"role": "user", "content": combined_prompt},
    ], temperature=temperature, max_tokens=max_output_tokens)
    final = combined.strip()
    if on_progress:
        try:
            on_progress("paper_done", {"title": title})
        except Exception:
            pass
    return final


def synthesize_corpus_summary(
    client: LMStudioClient,
    paper_summaries: List[Dict],
    temperature: float = 0.2,
    max_output_tokens: Optional[int] = None,
) -> str:
    """Create an overall synthesis across all papers."""
    bullets = []
    for p in paper_summaries:
        bullets.append(f"Title: {p['metadata'].get('title')}\nSummary: {p['summary']}")

    prompt = (
        "You are reviewing multiple research papers. Create a comprehensive synthesis including:\n"
        "- Field context and overarching themes\n"
        "- Key methods and trends\n"
        "- Consensus findings and points of disagreement\n"
        "- Notable gaps and future directions\n"
        "Write 350-500 words in clear, structured prose.\n\n"
        "Inputs:\n" + "\n\n".join(bullets)
    )
    resp = client.chat_complete([
        {"role": "system", "content": "You are an expert research synthesizer."},
        {"role": "user", "content": prompt},
    ], temperature=temperature, max_tokens=max_output_tokens)
    return resp.strip()
