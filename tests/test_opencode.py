import json
from pathlib import Path

from feishu_opencode_bridge.opencode import OpenCodeClient


def _json_line(event):
    return json.dumps(event, ensure_ascii=False)


def test_parse_run_output_defaults_to_last_text_part():
    client = OpenCodeClient("opencode", Path("."), 60)
    stdout = "\n".join(
        [
            _json_line({"sessionID": "ses_1", "part": {"type": "text", "text": "先分析一下"}}),
            _json_line({"part": {"type": "tool", "name": "read"}}),
            _json_line({"part": {"type": "text", "text": "最终结论"}}),
        ]
    )

    output, session_id = client._parse_run_output(stdout)

    assert output == "最终结论"
    assert session_id == "ses_1"


def test_parse_run_output_can_return_full_text_parts():
    client = OpenCodeClient("opencode", Path("."), 60, reply_full_output=True)
    stdout = "\n".join(
        [
            _json_line({"sessionID": "ses_1", "part": {"type": "text", "text": "先分析一下\n"}}),
            _json_line({"part": {"type": "tool", "name": "read"}}),
            _json_line({"part": {"type": "text", "text": "最终结论"}}),
        ]
    )

    output, session_id = client._parse_run_output(stdout)

    assert output == "先分析一下\n最终结论"
    assert session_id == "ses_1"
