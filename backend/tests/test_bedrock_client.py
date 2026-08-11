import pytest

from guardian.bedrock.client import BedrockProvider
from guardian.bedrock.provider import LLMError
from guardian.models.config import GuardianConfig


class FakeBedrockClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def converse(self, **kwargs):
        self.requests.append(kwargs)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def converse_response(text='{"findings": []}'):
    return {
        "output": {"message": {"content": [{"text": text}]}},
        "usage": {
            "inputTokens": 1200,
            "outputTokens": 80,
            "cacheReadInputTokens": 900,
            "cacheWriteInputTokens": 0,
        },
        "stopReason": "end_turn",
    }


class ThrottlingError(Exception):
    response = {"Error": {"Code": "ThrottlingException"}}


def test_converse_maps_usage_and_text():
    fake = FakeBedrockClient([converse_response()])
    provider = BedrockProvider(GuardianConfig(), client=fake)
    response = provider.complete(system="sys", user="user")

    assert response.text == '{"findings": []}'
    assert response.input_tokens == 1200
    assert response.cache_read_tokens == 900
    assert response.stop_reason == "end_turn"

    request = fake.requests[0]
    assert request["modelId"] == GuardianConfig().bedrock_model_id
    assert request["inferenceConfig"]["temperature"] == 0.0


def test_cache_point_added_when_enabled():
    fake = FakeBedrockClient([converse_response(), converse_response()])
    provider = BedrockProvider(GuardianConfig(), client=fake)

    provider.complete(system="sys", user="u", cache_system_prompt=True)
    assert {"cachePoint": {"type": "default"}} in fake.requests[0]["system"]

    provider.complete(system="sys", user="u", cache_system_prompt=False)
    assert {"cachePoint": {"type": "default"}} not in fake.requests[1]["system"]


def test_retry_on_throttling_then_success(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    fake = FakeBedrockClient([ThrottlingError(), converse_response()])
    provider = BedrockProvider(GuardianConfig(), client=fake)
    response = provider.complete(system="s", user="u")
    assert response.output_tokens == 80
    assert len(fake.requests) == 2


def test_non_retryable_error_raises_immediately():
    class AccessDenied(Exception):
        response = {"Error": {"Code": "AccessDeniedException"}}

    fake = FakeBedrockClient([AccessDenied(), converse_response()])
    provider = BedrockProvider(GuardianConfig(), client=fake)
    with pytest.raises(LLMError):
        provider.complete(system="s", user="u")
    assert len(fake.requests) == 1


def test_malformed_response_shape_raises():
    fake = FakeBedrockClient([{"output": {}}])
    provider = BedrockProvider(GuardianConfig(), client=fake)
    with pytest.raises(LLMError):
        provider.complete(system="s", user="u")


def test_estimated_cost():
    fake = FakeBedrockClient([converse_response()])
    provider = BedrockProvider(GuardianConfig(), client=fake)
    response = provider.complete(system="s", user="u")
    # 1200 in @ $3/M + 80 out @ $15/M + 900 cache-read @ $0.30/M
    assert response.estimated_cost_usd(3.0, 15.0, 0.30) == pytest.approx(0.00507, abs=1e-5)
