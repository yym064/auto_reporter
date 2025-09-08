import argparse
import glob
import os
import sys
from typing import Dict, List, Optional

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich import box
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt, FloatPrompt, Confirm

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
    parser.add_argument("--model", default="openai/gpt-oss-20b", help="LM Studio 모델명")
    parser.add_argument("--lmstudio-url", default=os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1"), help="LM Studio base URL")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-chars", type=int, default=4000, help="청크 최대 문자수")
    parser.add_argument("--clusters", type=int, default=3, help="클러스터 수")
    parser.add_argument("--max-tokens", type=int, default=512, help="LLM 최대 출력 토큰")
    parser.add_argument(
        "--chunk-summary-words",
        default="120-160",
        help="청크 요약 단어 수(예: '120-160' 또는 '150')",
    )
    parser.add_argument("--instruction-file", default=None, help="사전 지시 사항 파일 경로 (기본: ./instruction.md 존재 시 자동 사용)")
    parser.add_argument("--interactive", action="store_true", help="실행 전 대화형으로 옵션 수정")

    args = parser.parse_args(argv)

    console = Console()
    input_dir = args.input_dir
    artifacts_dir = args.artifacts_dir
    report_dir = args.report_dir

    # Interactive configuration (optional)
    if args.interactive:
        if sys.stdin.isatty():
            console.print("[cyan]대화형 설정 모드: 옵션을 수정하려면 입력하세요. (Enter로 기본값 유지)[/cyan]")
            try:
                input_dir = Prompt.ask("입력 폴더", default=input_dir)
                artifacts_dir = Prompt.ask("아티팩트 폴더", default=artifacts_dir)
                report_dir = Prompt.ask("리포트 폴더", default=report_dir)
                args.model = Prompt.ask("LM Studio 모델", default=args.model)
                args.lmstudio_url = Prompt.ask("LM Studio URL", default=args.lmstudio_url)
                args.temperature = FloatPrompt.ask("Temperature", default=args.temperature)
                args.max_chars = IntPrompt.ask("청크 최대 문자수", default=args.max_chars)
                args.max_tokens = IntPrompt.ask("LLM 최대 출력 토큰", default=args.max_tokens)
                args.clusters = IntPrompt.ask("클러스터 수", default=args.clusters)
                args.chunk_summary_words = Prompt.ask(
                    "청크 요약 단어 수 (예: 120-160 또는 150)",
                    default=str(args.chunk_summary_words),
                )
            except Exception:
                console.print("[red]대화형 입력 처리 중 오류가 발생했습니다. 기본값으로 진행합니다.[/red]\n")
        else:
            console.print("[yellow]표준 입력이 TTY가 아닙니다. 대화형 모드를 건너뜁니다.[/yellow]")

    os.makedirs(artifacts_dir, exist_ok=True)
    os.makedirs(report_dir, exist_ok=True)

    cache = JsonlCache(os.path.join(artifacts_dir, "cache"))

    # Load optional instruction.md and pass as pre system message
    pre_messages: List[Dict[str, str]] = []
    instr_path: Optional[str] = None
    if args.instruction_file:
        instr_path = args.instruction_file
    else:
        default_path = os.path.join(os.getcwd(), "instruction.md")
        if os.path.isfile(default_path):
            instr_path = default_path
    if instr_path and os.path.isfile(instr_path):
        try:
            with open(instr_path, "r", encoding="utf-8") as f:
                instr_text = f.read().strip()
            if instr_text:
                pre_messages.append({"role": "system", "content": instr_text})
                console.print(f"[green]instruction.md 적용:[/green] {instr_path}")
        except Exception as e:
            console.print(f"[yellow]instruction.md 읽기 실패:[/yellow] {e}\n")

    client = LMStudioClient(model=args.model, base_url=args.lmstudio_url, cache=cache, pre_messages=pre_messages)

    pdfs = find_pdfs(input_dir)
    if not pdfs:
        console.print(f"[red]PDF를 찾지 못했습니다: {input_dir}[/red]")
        return 1

    results: List[Dict] = []

    # TODO-style dashboard state
    def _icon(status: str) -> str:
        return {
            "pending": "[dim]□[/dim]",
            "in_progress": "[yellow]◐[/yellow]",
            "done": "[green]■[/green]",
            "failed": "[red]×[/red]",
        }.get(status, status)

    tasks: Dict[str, Dict] = {}
    for pdf_path in pdfs:
        pid = os.path.splitext(os.path.basename(pdf_path))[0]
        tasks[pid] = {
            "paper_path": pdf_path,
            "title": pid,
            "extract": "pending",
            "summarize": "pending",
            "combine": "pending",
            "chunks_total": 0,
            "chunks_done": 0,
        }

    report_status = "pending"

    def render_dashboard() -> Panel:
        table = Table(box=box.SIMPLE_HEAVY, show_lines=False)
        table.add_column("Paper", overflow="fold")
        table.add_column("Extract", justify="center", width=10)
        table.add_column("Summarize", justify="center", width=12)
        table.add_column("Combine", justify="center", width=10)
        table.add_column("Chunks", justify="right", width=10)
        for pid, st in tasks.items():
            name = st.get("title") or pid
            chunks = st.get("chunks_done", 0)
            total = st.get("chunks_total", 0)
            table.add_row(
                name,
                _icon(st["extract"]),
                _icon(st["summarize"]),
                _icon(st["combine"]),
                f"{chunks}/{total}" if total else "-",
            )
        footer = f"Report: {_icon(report_status)}  |  총 {len(pdfs)}개 PDF"
        return Panel(table, title="처리 현황 (TODO)", subtitle=footer, padding=(1,1))

    with Live(render_dashboard(), console=console, refresh_per_second=6) as live:
        # Process each paper
        for pdf_path in pdfs:
            pid = os.path.splitext(os.path.basename(pdf_path))[0]
            # Update title from metadata after extraction
            tasks[pid]["extract"] = "in_progress"
            live.update(render_dashboard())

            try:
                info = extract_pdf(pdf_path, artifacts_dir)
                title = info["metadata"].get("title") or info["paper_id"]
                tasks[pid]["title"] = title
                tasks[pid]["extract"] = "done"
                live.update(render_dashboard())
            except Exception as e:
                tasks[pid]["extract"] = "failed"
                live.update(render_dashboard())
                console.print(f"[red]추출 실패[/red] {pdf_path}: {e}")
                continue

            def on_progress(event: str, data: Dict):
                st = tasks[pid]
                if event == "chunking_done":
                    st["summarize"] = "in_progress"
                    st["chunks_total"] = int(data.get("chunks") or 0)
                    st["chunks_done"] = 0
                elif event == "chunk_summarized":
                    st["chunks_done"] = min(st.get("chunks_done", 0) + 1, st.get("chunks_total", 0))
                elif event == "combining":
                    st["combine"] = "in_progress"
                elif event == "paper_done":
                    st["summarize"] = "done"
                    st["combine"] = "done"
                live.update(render_dashboard())

            try:
                summary = summarize_single_paper(
                    client,
                    paper_text=info["text"],
                    paper_meta=info["metadata"],
                    max_chunk_chars=args.max_chars,
                    temperature=args.temperature,
                    max_output_tokens=args.max_tokens,
                    on_progress=on_progress,
                    chunk_summary_words=args.chunk_summary_words,
                )
                # If no callbacks fired (e.g., empty text), mark as done appropriately
                if tasks[pid]["summarize"] == "pending":
                    tasks[pid]["summarize"] = "done"
                if tasks[pid]["combine"] == "pending":
                    tasks[pid]["combine"] = "done"
            except Exception as e:
                console.print(f"[red]요약 실패[/red] {pdf_path}: {e}")
                tasks[pid]["summarize"] = "failed"
                if tasks[pid]["combine"] == "in_progress":
                    tasks[pid]["combine"] = "failed"
                summary = "요약 생성 실패 (LM Studio 서버 동작 여부 확인 필요)"
            finally:
                live.update(render_dashboard())

            results.append(
                {
                    "paper_id": info["paper_id"],
                    "metadata": info["metadata"],
                    "text_path": info["text_path"],
                    "figures_paths": info["figures_paths"],
                    "summary": summary,
                }
            )

        # Synthesis & Report
        report_status = "in_progress"
        live.update(render_dashboard())
        try:
            corpus_summary = synthesize_corpus_summary(
                client, results, temperature=args.temperature, max_output_tokens=args.max_tokens
            )
        except Exception as e:
            console.print(f"[red]종합 요약 실패:[/red] {e}")
            corpus_summary = "종합 요약 생성 실패 (LM Studio 서버 동작 여부 확인 필요)"

        try:
            out_path = generate_report(report_dir, corpus_summary, results)
            console.print(f"[bold green]보고서 생성 완료:[/bold green] {out_path}")
        except Exception as e:
            console.print(f"[red]리포트 생성 실패:[/red] {e}")
        finally:
            report_status = "done"
            live.update(render_dashboard())

    console.print("완료.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
