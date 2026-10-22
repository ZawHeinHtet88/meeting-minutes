import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from ai_processor import (
    AIProcessingError,
    OpenCodeProcessor,
    _validate_cleaned_segments,
    validate_summary,
)


MODEL = "example-provider/example-model"
VARIANT = "high"


def valid_response():
    return {
        "title": "Weekly planning",
        "meeting_date": None,
        "summary": "The team planned the week.",
        "discussion_points": [
            {"topic": "Release", "details": "Testing continues.", "timestamp": "00:01:00"}
        ],
        "decisions": [{"decision": "Ship after tests pass.", "timestamp": None}],
        "action_items": [
            {
                "task": "Run tests",
                "owner": "Aye",
                "deadline": None,
                "timestamp": "00:02:00",
            }
        ],
        "blockers": [],
        "open_questions": [],
        "follow_ups": ["Review test results."],
        "uncertainties": [],
    }


def completed(args, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args, returncode, stdout, stderr)


def command_side_effect(response, separate_variant=True):
    def run(command, **_kwargs):
        if command[1:] == ["models"]:
            return completed(command, stdout=f"{MODEL}\n")
        if command[1:] == ["run", "--help"]:
            flag = "--variant string" if separate_variant else "--model string"
            return completed(command, stdout=flag)
        event = {"type": "text", "part": {"type": "text", "text": json.dumps(response)}}
        return completed(command, stdout=json.dumps(event) + "\n")

    return run


@patch("ai_processor.shutil.which", return_value="/usr/bin/opencode")
@patch("ai_processor.subprocess.run")
def test_calls_opencode_with_configured_model_and_variant(mock_run, _which, tmp_path):
    mock_run.side_effect = command_side_effect(valid_response(), separate_variant=True)
    processor = OpenCodeProcessor(MODEL, VARIANT, tmp_path)

    result = processor.process("[00:00:01] Hello team")

    assert result["meeting_title"] == "Weekly planning"
    run_command = mock_run.call_args_list[-1].args[0]
    assert run_command[1:6] == ["run", "--model", MODEL, "--variant", VARIANT]
    assert "--format" in run_command


@patch("ai_processor.shutil.which", return_value="/usr/bin/opencode")
@patch("ai_processor.subprocess.run")
def test_uses_v2_combined_model_variant_syntax(mock_run, _which, tmp_path):
    mock_run.side_effect = command_side_effect(valid_response(), separate_variant=False)
    processor = OpenCodeProcessor(MODEL, VARIANT, tmp_path)

    processor.process("A short transcript")

    run_command = mock_run.call_args_list[-1].args[0]
    assert run_command[1:4] == ["run", "--model", f"{MODEL}#{VARIANT}"]


@patch("ai_processor.shutil.which", return_value="/usr/bin/opencode")
@patch("ai_processor.subprocess.run")
def test_ai_result_cache_avoids_second_request(mock_run, _which, tmp_path):
    mock_run.side_effect = command_side_effect(valid_response())
    processor = OpenCodeProcessor(MODEL, VARIANT, tmp_path)
    transcript = "The same transcript"

    first = processor.process(transcript)
    calls_after_first = mock_run.call_count
    second = processor.process(transcript)

    assert first == second
    assert mock_run.call_count == calls_after_first


@patch("ai_processor.shutil.which", return_value="/usr/bin/opencode")
@patch("ai_processor.subprocess.run")
def test_unavailable_model_has_clear_error(mock_run, _which, tmp_path):
    mock_run.return_value = completed([], stdout="another-provider/another-model\n")
    processor = OpenCodeProcessor(MODEL, VARIANT, tmp_path)

    with pytest.raises(AIProcessingError, match="unavailable"):
        processor.process("Transcript")


def test_schema_validation_rejects_missing_fields():
    with pytest.raises(AIProcessingError, match="missing fields"):
        validate_summary({"meeting_title": "Incomplete"})


def test_schema_validation_rejects_bad_action_owner():
    response = valid_response()
    response["action_items"][0]["owner"] = ["not", "a", "person"]
    with pytest.raises(AIProcessingError, match="owner"):
        validate_summary(response)


def test_cleanup_cannot_change_speaker_label():
    original = [
        {"start": 0.0, "end": 2.0, "speaker": "Speaker 1", "text": "Hello"}
    ]
    cleaned = {
        "segments": [
            {
                "start": 0.0,
                "end": 2.0,
                "speaker": "Speaker 2",
                "text": "Hello.",
                "uncertainty": None,
            }
        ]
    }

    with pytest.raises(AIProcessingError, match="changed speaker"):
        _validate_cleaned_segments(cleaned, original)
