from ci.llm import LLMResponse, FakeLLMClient


def test_fake_client_returns_canned_tool_input():
    client = FakeLLMClient(canned_tool_input={"price": 900_000, "km_driven": 45_000})
    resp = client.extract_structured(
        system="you extract", user="some html", tool_name="extract", tool_schema={
            "type": "object", "properties": {}, "required": [],
        },
    )
    assert isinstance(resp, LLMResponse)
    assert resp.parsed == {"price": 900_000, "km_driven": 45_000}
    assert resp.tokens_in > 0
    assert resp.tokens_out > 0


def test_fake_client_records_calls():
    client = FakeLLMClient(canned_tool_input={"x": 1})
    client.extract_structured(
        system="s", user="u", tool_name="t", tool_schema={"type": "object", "properties": {}, "required": []},
    )
    assert len(client.calls) == 1
    assert client.calls[0]["user"] == "u"
