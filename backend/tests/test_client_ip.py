from starlette.requests import Request

from app.services.client_ip import resolve_client_ip


def _request(*, peer: str, forwarded_for: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-forwarded-for", forwarded_for.encode())],
            "client": (peer, 12345),
        }
    )


def test_untrusted_peer_cannot_spoof_forwarded_client_ip() -> None:
    request = _request(peer="203.0.113.20", forwarded_for="198.51.100.7")

    assert resolve_client_ip(request, trusted_proxy_cidrs=("127.0.0.1/32",)) == "203.0.113.20"


def test_trusted_proxy_chain_resolves_first_untrusted_hop() -> None:
    request = _request(
        peer="127.0.0.1",
        forwarded_for="198.51.100.7, 10.20.30.40",
    )

    assert (
        resolve_client_ip(
            request,
            trusted_proxy_cidrs=("127.0.0.1/32", "10.0.0.0/8"),
        )
        == "198.51.100.7"
    )
