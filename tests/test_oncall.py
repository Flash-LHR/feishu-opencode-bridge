from feishu_opencode_bridge.oncall import parse_alert


def test_parse_alert_extracts_common_fields():
    alert = parse_alert(
        "告警名称：checkout 错误率\n"
        "告警级别：info\n"
        "服务：checkout\n"
        "环境：prod"
    )

    assert alert.name == "checkout 错误率"
    assert alert.severity == "info"
    assert alert.service == "checkout"
    assert alert.environment == "prod"
    assert alert.fingerprint


def test_alert_fingerprint_ignores_changing_numbers_for_unstructured_text():
    first = parse_alert("P1 checkout latency p99 is 1234ms")
    second = parse_alert("P1 checkout latency p99 is 5678ms")

    assert first.severity == "p1"
    assert first.fingerprint == second.fingerprint
