import argparse
import glob
import os
import sys
from typing import Dict, List, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from .pdf_utils import extract_pdf
from .cache import JsonlCache
from .lmstudio import LMStudioClient
from .summarize import summarize_single_paper, synthesize_corpus_summary
from .report import generate_report


def find_pdfs(input_dir: str) -> List[str]:
    patterns = ["*.pdf", "*.PDF"]
    paths: List[str] = []
    for pat in patterns:
        paths.extend(glob.glob(os.path.join(input_dir, pat)))
    return sorted(list(set(paths)))


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(description="논문 폴더를 분석하여 종합 보고서를 생성")
    parser.add_argument("--input-dir", required=True, help="PDF 폴더 경로")
    parser.add_argument("--artifacts-dir", default="artifacts", help="아티팩트 출력 폴더")
    parser.add_argument("--report-dir", default="report", help="보고서 출력 폴더")
    parser.add_argument("--model", default="TheBloke/Mistral-7B-Instruct-v0.2-GGUF", help="LM Studio 모델명")
    parser.add_argument("--lmstudio-url", default=os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1"), help="LM Studio base URL")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-chars", type=int, default=4000, help="청크 최대 문자수")
    parser.add_argument("--clusters", type=int, default=3, help="클러스터 수")
    parser.add_argument("--max-tokens", type=int, default=512, help="LLM 최대 출력 토큰")

    args = parser.parse_args(argv)

    console = Console()
    input_dir = args.input_dir
    artifacts_dir = args.artifacts_dir
    report_dir = args.report_dir

    os.makedirs(artifacts_dir, exist_ok=True)
    os.makedirs(report_dir, exist_ok=True)

    cache = JsonlCache(os.path.join(artifacts_dir, "cache"))
    client = LMStudioClient(model=args.model, base_url=args.lmstudio_url, cache=cache)

    pdfs = find_pdfs(input_dir)
    if not pdfs:
        console.print(f"[red]PDF를 찾지 못했습니다: {input_dir}[/red]")
        return 1

    results: List[Dict] = []

    overall_task_desc = f"총 {len(pdfs)}개 PDF 처리"
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_overall = progress.add_task(overall_task_desc, total=len(pdfs))

        for pdf_path in pdfs:
            progress.log(f"[green]추출 중:[/green] {pdf_path}")
            try:
                info = extract_pdf(pdf_path, artifacts_dir)
            except Exception as e:
                console.print(f"[red]추출 실패[/red] {pdf_path}: {e}")
                progress.advance(task_overall)
                continue

            title = info["metadata"].get("title") or info["paper_id"]
            sub_desc = f"요약 준비: {title}"
            task_sub: Optional[int] = progress.add_task(sub_desc, total=0)

            def on_progress(event: str, data: Dict):
                nonlocal task_sub
                try:
                    if event == "chunking_done":
                        total = int(data.get("chunks") or 0)
                        progress.update(task_sub, total=total, completed=0, description=f"요약 중: {title}")
                        if total == 0:
                            progress.update(task_sub, description=f"요약 건너뜀: {title}")
                    elif event == "chunk_summarized":
                        progress.advance(task_sub, 1)
                    elif event == "combining":
                        progress.update(task_sub, description=f"결과 통합 중: {title}")
                    elif event == "paper_done":
                        progress.update(task_sub, description=f"완료: {title}")
                except Exception:
                    pass

            try:
                summary = summarize_single_paper(
                    client,
                    paper_text=info["text"],
                    paper_meta=info["metadata"],
                    max_chunk_chars=args.max_chars,
                    temperature=args.temperature,
                    max_output_tokens=args.max_tokens,
                    on_progress=on_progress,
                )
            except Exception as e:
                console.print(f"[red]요약 실패[/red] {pdf_path}: {e}")
                summary = "요약 생성 실패 (LM Studio 서버 동작 여부 확인 필요)"

            results.append(
                {
                    "paper_id": info["paper_id"],
                    "metadata": info["metadata"],
                    "text_path": info["text_path"],
                    "figures_paths": info["figures_paths"],
                    "summary": summary,
                }
            )

            try:
                if task_sub is not None:
                    progress.remove_task(task_sub)
            except Exception:
                pass

            progress.advance(task_overall)

        # Synthesis
        progress.log("[cyan]전체 종합 요약 생성 중...[/cyan]")
        try:
            corpus_summary = synthesize_corpus_summary(
                client, results, temperature=args.temperature, max_output_tokens=args.max_tokens
            )
        except Exception as e:
            console.print(f"[red]종합 요약 실패:[/red] {e}")
            corpus_summary = "종합 요약 생성 실패 (LM Studio 서버 동작 여부 확인 필요)"

        # Report
        progress.log("[cyan]리포트 생성 중...[/cyan]")
        try:
            out_path = generate_report(report_dir, corpus_summary, results)
            progress.log(f"[bold green]보고서 생성 완료:[/bold green] {out_path}")
        except Exception as e:
            console.print(f"[red]리포트 생성 실패:[/red] {e}")

    console.print("완료.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
