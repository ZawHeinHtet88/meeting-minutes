from pathlib import Path

from html_generator import generate_html, write_index


def test_html_escapes_all_untrusted_content():
    analysis = {
        "meeting_title": "<script>alert('title')</script>",
        "meeting_date": None,
        "executive_summary": "Summary & notes",
        "discussion_points": [
            {"topic": "<b>Topic</b>", "details": "safe < text", "timestamp": None}
        ],
        "key_decisions": [{"decision": "Use A > B", "timestamp": None}],
        "action_items": [
            {
                "task": "Open <img src=x onerror=alert(1)>",
                "responsible_person": '"Owner"',
                "deadline": None,
            }
        ],
        "follow_up_points": [],
        "blockers": [],
        "open_questions": [],
        "uncertainties": [],
    }
    transcript = {
        "duration": 12,
        "language": "my",
        "segments": [
            {
                "start": 1,
                "end": 2,
                "speaker": "Speaker <2>",
                "text": "မင်္ဂလာပါ <script>bad()</script>",
            }
        ],
    }

    document = generate_html(
        analysis, transcript, Path("unsafe<name>.mp4"), "provider/model", "high"
    )

    assert "<script>" not in document
    assert "<img src=x" not in document
    assert "&lt;script&gt;" in document
    assert "မင်္ဂလာပါ" in document
    assert "Speaker &lt;2&gt;" in document
    assert '<meta charset="utf-8">' in document


def test_index_links_only_html_reports(tmp_path):
    (tmp_path / "B report.html").write_text("b", encoding="utf-8")
    (tmp_path / "a report.html").write_text("a", encoding="utf-8")
    (tmp_path / "private.wav").write_bytes(b"audio")

    write_index(tmp_path)
    document = (tmp_path / "index.html").read_text(encoding="utf-8")

    assert "a%20report.html" in document
    assert "B%20report.html" in document
    assert "private.wav" not in document
