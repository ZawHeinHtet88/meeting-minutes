"""Safe, deterministic standalone HTML meeting report generation."""

from __future__ import annotations

import html
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from transcriber import format_timestamp


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _paragraph(value: str) -> str:
    return _escape(value).replace("\n", "<br>\n")


def _empty(message: str) -> str:
    return f'<p class="empty">{_escape(message)}</p>'


def _list(items: list[str], css_class: str = "clean-list") -> str:
    if not items:
        return _empty("None recorded")
    return f'<ul class="{css_class}">' + "".join(
        f"<li>{_paragraph(item)}</li>" for item in items
    ) + "</ul>"


def _discussion_cards(items: list[dict[str, str]]) -> str:
    if not items:
        return _empty("No discussion points were identified")
    return "".join(
        '<article class="discussion-card">'
        f'<h3>{_escape(item["topic"])}</h3>'
        + (
            f'<span class="source-time">{_escape(item["timestamp"])}</span>'
            if item.get("timestamp")
            else ""
        )
        + f'<p>{_paragraph(item["details"])}</p>'
        + "</article>"
        for item in items
    )


def _decision_list(items: list[dict[str, Any]]) -> str:
    if not items:
        return _empty("None recorded")
    return '<ul class="decision-list">' + "".join(
        "<li>"
        f'{_paragraph(item["decision"])}'
        + (
            f' <span class="source-time">{_escape(item["timestamp"])}</span>'
            if item.get("timestamp")
            else ""
        )
        + "</li>"
        for item in items
    ) + "</ul>"


def _action_rows(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<tr><td colspan="4" class="empty table-empty">No action items recorded</td></tr>'
    rows: list[str] = []
    for number, item in enumerate(items, start=1):
        owner = item.get("responsible_person") or "Not specified"
        deadline = item.get("deadline") or "Not specified"
        rows.append(
            "<tr>"
            f'<td class="number">{number:02d}</td>'
            f'<td data-label="Action">{_paragraph(item["task"])}</td>'
            f'<td data-label="Owner">{_escape(owner)}</td>'
            f'<td data-label="Deadline">{_escape(deadline)}</td>'
            "</tr>"
        )
    return "".join(rows)


def _transcript_rows(segments: list[dict[str, Any]]) -> str:
    if not segments:
        return _empty("No speech was transcribed")
    return "".join(
        '<div class="transcript-row">'
        f'<time>{_escape(format_timestamp(float(segment["start"])))}</time>'
        f'<span class="speaker">{_escape(segment.get("speaker", "Unknown Speaker"))}</span>'
        f'<p>{_paragraph(str(segment["text"]))}</p>'
        "</div>"
        for segment in segments
    )


def generate_html(
    analysis: dict[str, Any],
    transcript: dict[str, Any],
    source_path: Path,
    model: str,
    variant: str,
) -> str:
    """Build one standalone document. Inputs must already be schema-validated."""
    title = _escape(analysis["meeting_title"])
    duration = format_timestamp(float(transcript.get("duration", 0.0) or 0.0))
    language = str(transcript.get("language", "unknown"))
    transcription_model = str(transcript.get("model", "unknown"))
    generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    discussions = _discussion_cards(analysis["discussion_points"])
    decisions = _decision_list(analysis["key_decisions"])
    follow_ups = _list(analysis["follow_up_points"])
    blockers = _list(analysis.get("blockers", []))
    questions = _list(analysis.get("open_questions", []))
    uncertainties = _list(analysis.get("uncertainties", []))
    actions = _action_rows(analysis["action_items"])
    transcript_rows = _transcript_rows(transcript.get("segments", []))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>{title} — Meeting Minutes</title>
  <style>
    :root {{
      --ink: #17202a; --muted: #65717e; --paper: #fbfaf7; --card: #fff;
      --line: #e7e1d8; --accent: #126b63; --accent-soft: #e4f2ef;
      --warm: #f2b84b; --shadow: 0 18px 50px rgba(29, 42, 50, .09);
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0; color: var(--ink); background: var(--paper);
      font-family: Inter, "Noto Sans Myanmar", "Myanmar Text", "Pyidaungsu",
        system-ui, -apple-system, "Segoe UI", sans-serif;
      font-size: 16px; line-height: 1.72;
    }}
    body::before {{
      content: ""; position: fixed; inset: 0 0 auto; height: 6px;
      background: linear-gradient(90deg, var(--accent), var(--warm)); z-index: 5;
    }}
    .page {{ max-width: 1120px; margin: 0 auto; padding: 72px 28px 90px; }}
    .hero {{
      position: relative; overflow: hidden; padding: clamp(34px, 7vw, 72px);
      border-radius: 28px; color: #fff; background: #143f3c; box-shadow: var(--shadow);
    }}
    .hero::after {{
      content: ""; position: absolute; width: 420px; height: 420px; right: -170px;
      top: -210px; border-radius: 50%; border: 70px solid rgba(242,184,75,.22);
    }}
    .eyebrow {{
      margin: 0 0 14px; color: #b8ddd8; font-size: .76rem; font-weight: 800;
      letter-spacing: .17em; text-transform: uppercase;
    }}
    h1 {{
      position: relative; z-index: 1; max-width: 800px; margin: 0;
      font-family: Georgia, "Noto Sans Myanmar", "Myanmar Text", serif;
      font-size: clamp(2.15rem, 6vw, 4.6rem); line-height: 1.08; letter-spacing: -.035em;
    }}
    .meta-grid {{
      position: relative; z-index: 1; display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; margin-top: 42px;
    }}
    .meta {{ padding: 14px 16px; border: 1px solid rgba(255,255,255,.15); border-radius: 14px; background: rgba(255,255,255,.07); }}
    .meta b {{ display: block; color: #a9cbc7; font-size: .68rem; letter-spacing: .11em; text-transform: uppercase; }}
    .meta span {{ display: block; overflow-wrap: anywhere; margin-top: 3px; font-size: .9rem; }}
    nav {{ display: flex; flex-wrap: wrap; gap: 9px; margin: 25px 0 48px; }}
    nav a {{ padding: 8px 13px; border: 1px solid var(--line); border-radius: 999px; color: var(--accent); background: #fff; font-size: .82rem; font-weight: 700; text-decoration: none; }}
    main {{ display: grid; gap: 28px; }}
    section {{ scroll-margin-top: 24px; padding: clamp(24px, 5vw, 46px); border: 1px solid var(--line); border-radius: 22px; background: var(--card); box-shadow: 0 8px 30px rgba(29,42,50,.045); }}
    .section-heading {{ display: flex; align-items: baseline; gap: 14px; margin-bottom: 23px; }}
    .section-heading span {{ color: var(--accent); font: 700 .75rem/1 Georgia, serif; }}
    h2 {{ margin: 0; font-family: Georgia, "Noto Sans Myanmar", "Myanmar Text", serif; font-size: clamp(1.45rem, 3vw, 2.1rem); letter-spacing: -.02em; }}
    h3 {{ margin: 0 0 7px; font-size: 1rem; }}
    p {{ margin: 0; }}
    .summary {{ font-size: clamp(1.05rem, 2vw, 1.25rem); color: #2f3c43; }}
    .discussion-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 15px; }}
    .discussion-card {{ padding: 20px; border-left: 3px solid var(--warm); border-radius: 5px 14px 14px 5px; background: #faf8f3; }}
    .discussion-card p, .clean-list {{ color: #47545c; }}
    .source-time {{ display: inline-block; margin: 0 0 7px; color: var(--accent); font: 700 .72rem/1.4 ui-monospace, SFMono-Regular, Consolas, monospace; }}
    .open-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 24px; }}
    .open-grid h3 {{ padding-bottom: 8px; border-bottom: 2px solid var(--accent-soft); }}
    .decision-list, .clean-list {{ margin: 0; padding: 0; list-style: none; }}
    .decision-list li, .clean-list li {{ position: relative; padding: 10px 0 10px 30px; border-bottom: 1px solid var(--line); }}
    .decision-list li:last-child, .clean-list li:last-child {{ border: 0; }}
    .decision-list li::before {{ content: "✓"; position: absolute; left: 0; color: var(--accent); font-weight: 900; }}
    .clean-list li::before {{ content: "→"; position: absolute; left: 0; color: var(--accent); font-weight: 900; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{ padding: 12px 14px; color: var(--muted); border-bottom: 2px solid var(--ink); font-size: .72rem; letter-spacing: .08em; text-align: left; text-transform: uppercase; }}
    td {{ padding: 17px 14px; border-bottom: 1px solid var(--line); vertical-align: top; }}
    tr:last-child td {{ border-bottom: 0; }}
    .number {{ width: 48px; color: var(--accent); font-family: Georgia, serif; font-weight: 700; }}
    .empty {{ color: var(--muted); font-style: italic; }}
    .table-empty {{ text-align: center; }}
    details summary {{ cursor: pointer; color: var(--accent); font-weight: 750; }}
    .transcript {{ margin-top: 25px; border-top: 1px solid var(--line); }}
    .transcript-row {{ display: grid; grid-template-columns: 92px 100px 1fr; gap: 20px; padding: 17px 0; border-bottom: 1px solid var(--line); }}
    .transcript-row time {{ color: var(--accent); font: 700 .78rem/1.75 ui-monospace, SFMono-Regular, Consolas, monospace; }}
    .speaker {{ align-self:start; padding:3px 8px; border-radius:999px; color:#315b57; background:var(--accent-soft); font-size:.72rem; font-weight:800; text-align:center; }}
    footer {{ padding: 32px 4px 0; color: var(--muted); font-size: .77rem; text-align: center; }}
    @media (max-width: 760px) {{
      .page {{ padding: 36px 15px 60px; }} .hero {{ border-radius: 20px; }}
      .meta-grid {{ grid-template-columns: repeat(2, 1fr); }}
      .discussion-grid {{ grid-template-columns: 1fr; }}
      .open-grid {{ grid-template-columns: 1fr; }}
      table, tbody, tr, td {{ display: block; }} thead {{ display: none; }}
      tr {{ padding: 12px 0; border-bottom: 1px solid var(--line); }}
      td {{ display: grid; grid-template-columns: 90px 1fr; padding: 7px 4px; border: 0; }}
      td::before {{ content: attr(data-label); color: var(--muted); font-size: .72rem; font-weight: 800; text-transform: uppercase; }}
      td.number {{ display: none; }} .table-empty {{ display: block; }}
      .transcript-row {{ grid-template-columns:1fr; gap:5px; }} .speaker {{ justify-self:start; }}
    }}
    @media print {{
      body {{ background: #fff; }} .page {{ max-width: none; padding: 0; }}
      .hero, section {{ box-shadow: none; break-inside: avoid; }} nav {{ display: none; }}
      details:not([open]) > *:not(summary) {{ display: block; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <header class="hero">
      <p class="eyebrow">Meeting minutes</p>
      <h1>{title}</h1>
      <div class="meta-grid">
        <div class="meta"><b>Source</b><span>{_escape(source_path.name)}</span></div>
        <div class="meta"><b>Duration</b><span>{_escape(duration)}</span></div>
        <div class="meta"><b>Language</b><span>{_escape(language)}</span></div>
        <div class="meta"><b>Transcription</b><span>{_escape(transcription_model)}</span></div>
        <div class="meta"><b>Meeting date</b><span>{_escape(analysis.get("meeting_date") or "Not stated")}</span></div>
        <div class="meta"><b>Generated</b><span>{_escape(generated)}</span></div>
      </div>
    </header>
    <nav aria-label="Report sections">
      <a href="#summary">Summary</a><a href="#discussion">Discussion</a>
      <a href="#decisions">Decisions</a><a href="#actions">Actions</a>
      <a href="#follow-up">Follow-up</a><a href="#open-items">Open items</a>
      <a href="#transcript">Transcript</a>
    </nav>
    <main>
      <section id="summary"><div class="section-heading"><span>01</span><h2>Executive summary</h2></div><p class="summary">{_paragraph(analysis["executive_summary"])}</p></section>
      <section id="discussion"><div class="section-heading"><span>02</span><h2>Discussion points</h2></div><div class="discussion-grid">{discussions}</div></section>
      <section id="decisions"><div class="section-heading"><span>03</span><h2>Key decisions</h2></div>{decisions}</section>
      <section id="actions"><div class="section-heading"><span>04</span><h2>Action items</h2></div><div class="table-wrap"><table><thead><tr><th>#</th><th>Action</th><th>Owner</th><th>Deadline</th></tr></thead><tbody>{actions}</tbody></table></div></section>
      <section id="follow-up"><div class="section-heading"><span>05</span><h2>Follow-up points</h2></div>{follow_ups}</section>
      <section id="open-items"><div class="section-heading"><span>06</span><h2>Open items &amp; uncertainties</h2></div><div class="open-grid"><div><h3>Blockers</h3>{blockers}</div><div><h3>Open questions</h3>{questions}</div><div><h3>Uncertainties</h3>{uncertainties}</div></div></section>
      <section id="transcript"><div class="section-heading"><span>07</span><h2>Full transcript</h2></div><details><summary>Show timestamped transcript</summary><div class="transcript">{transcript_rows}</div></details></section>
    </main>
    <footer>Generated from {_escape(source_path.name)} · Transcription: {_escape(transcription_model)} · Analysis: {_escape(model)} / {_escape(variant)}</footer>
  </div>
</body>
</html>
"""


def write_report(
    output_path: Path,
    analysis: dict[str, Any],
    transcript: dict[str, Any],
    source_path: Path,
    model: str,
    variant: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document = generate_html(analysis, transcript, source_path, model, variant)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(document, encoding="utf-8")
    os.replace(temporary, output_path)


def write_index(site_dir: Path) -> None:
    """Create a standalone landing page linking every report in one site folder."""
    site_dir.mkdir(parents=True, exist_ok=True)
    reports = sorted(
        (path for path in site_dir.glob("*.html") if path.name.lower() != "index.html"),
        key=lambda path: path.name.casefold(),
    )
    if reports:
        cards = "".join(
            '<a class="card" href="'
            + _escape(quote(path.name))
            + '"><span>Meeting minutes</span><strong>'
            + _escape(path.stem)
            + "</strong><small>Open report →</small></a>"
            for path in reports
        )
    else:
        cards = '<p class="empty">No meeting reports have been generated yet.</p>'
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Meeting Minutes</title>
  <style>
    :root {{ --ink:#17202a; --muted:#65717e; --paper:#fbfaf7; --card:#fff;
      --line:#e7e1d8; --accent:#126b63; --warm:#f2b84b; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:var(--paper);
      font-family:Inter,"Noto Sans Myanmar","Myanmar Text",system-ui,sans-serif; }}
    body::before {{ content:""; display:block; height:6px;
      background:linear-gradient(90deg,var(--accent),var(--warm)); }}
    main {{ width:min(1040px,calc(100% - 32px)); margin:0 auto; padding:72px 0 90px; }}
    .eyebrow {{ margin:0 0 12px; color:var(--accent); font-size:.75rem;
      font-weight:800; letter-spacing:.16em; text-transform:uppercase; }}
    h1 {{ margin:0; font:700 clamp(2.4rem,7vw,5rem)/1.05 Georgia,
      "Noto Sans Myanmar",serif; letter-spacing:-.04em; }}
    .intro {{ max-width:650px; margin:20px 0 45px; color:var(--muted);
      font-size:1.08rem; line-height:1.7; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:16px; }}
    .card {{ display:flex; min-height:190px; padding:24px; border:1px solid var(--line);
      border-radius:20px; color:inherit; background:var(--card); text-decoration:none;
      flex-direction:column; box-shadow:0 10px 35px rgba(29,42,50,.06);
      transition:transform .18s ease,box-shadow .18s ease; }}
    .card:hover {{ transform:translateY(-3px); box-shadow:0 16px 45px rgba(29,42,50,.11); }}
    .card span {{ color:var(--accent); font-size:.72rem; font-weight:800;
      letter-spacing:.12em; text-transform:uppercase; }}
    .card strong {{ margin:18px 0; font:700 1.25rem/1.45 Georgia,
      "Noto Sans Myanmar",serif; overflow-wrap:anywhere; }}
    .card small {{ margin-top:auto; color:var(--accent); font-weight:750; }}
    .empty {{ padding:28px; border:1px dashed var(--line); border-radius:18px;
      color:var(--muted); }}
  </style>
</head>
<body><main><p class="eyebrow">Archive</p><h1>Meeting Minutes</h1>
<p class="intro">Generated meeting reports. Select a recording to view its summary,
decisions, action items, and timestamped transcript.</p><div class="grid">{cards}</div>
</main></body></html>
"""
    temporary = site_dir / "index.html.tmp"
    temporary.write_text(document, encoding="utf-8")
    os.replace(temporary, site_dir / "index.html")
