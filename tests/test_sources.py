import pytest

from dexus_vault.sources import is_plaintext_remote


@pytest.mark.parametrize(
    "url, expected",
    [
        ("http://vault.example.com:8200", True),
        ("http://10.0.0.5:8200", True),
        ("http://vault:8200", True),
        ("https://vault.example.com", False),
        ("http://127.0.0.1:8200", False),
        ("http://127.1.2.3", False),
        ("http://[::1]:8200", False),
        ("http://localhost:8200", False),
        ("http://dex.localhost", False),
        (None, False),
        ("", False),
    ],
)
def test_is_plaintext_remote(url, expected):
    assert is_plaintext_remote(url) is expected
