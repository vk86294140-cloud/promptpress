import sys
import types


class _FakeMessages:
    def __init__(self):
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return {"ok": True}


class _FakeAnthropic:
    def __init__(self, **kwargs):
        self.messages = _FakeMessages()
        self.init_kwargs = kwargs


def _install_fake_anthropic(monkeypatch):
    fake = types.ModuleType("anthropic")
    fake.Anthropic = _FakeAnthropic
    monkeypatch.setitem(sys.modules, "anthropic", fake)


def test_compresses_string_message_content(monkeypatch):
    _install_fake_anthropic(monkeypatch)
    from promptpress.middleware import CompressedAnthropic

    client = CompressedAnthropic(budget_per_message=50, api_key="x")
    big_text = "The quick brown fox jumps over the lazy dog. " * 40
    client.messages.create(
        model="claude-haiku-4-5-20251001", messages=[{"role": "user", "content": big_text}]
    )

    sent = client._client.messages.last_kwargs
    assert len(sent["messages"][0]["content"]) < len(big_text)


def test_compresses_text_blocks_and_system(monkeypatch):
    _install_fake_anthropic(monkeypatch)
    from promptpress.middleware import CompressedAnthropic

    client = CompressedAnthropic(budget_per_message=50)
    big_text = "The quick brown fox jumps over the lazy dog. " * 40
    client.messages.create(
        model="m",
        system=big_text,
        messages=[
            {
                "role": "user",
                "content": [{"type": "text", "text": big_text}, {"type": "image", "data": "x"}],
            }
        ],
    )
    sent = client._client.messages.last_kwargs
    assert len(sent["system"]) < len(big_text)
    blocks = sent["messages"][0]["content"]
    assert len(blocks[0]["text"]) < len(big_text)
    assert blocks[1] == {"type": "image", "data": "x"}


def test_getattr_proxies_to_inner_client(monkeypatch):
    _install_fake_anthropic(monkeypatch)
    from promptpress.middleware import CompressedAnthropic

    client = CompressedAnthropic(api_key="secret")
    assert client.init_kwargs == {"api_key": "secret"}
