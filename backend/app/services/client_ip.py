from ipaddress import ip_address, ip_network

from fastapi import Request


def resolve_client_ip(request: Request, *, trusted_proxy_cidrs: tuple[str, ...]) -> str:
    direct = request.client.host if request.client else "unknown"
    try:
        direct_ip = ip_address(direct)
        trusted = tuple(ip_network(cidr, strict=False) for cidr in trusted_proxy_cidrs)
    except ValueError:
        return "unknown"
    if not any(direct_ip in network for network in trusted):
        return str(direct_ip)

    forwarded = request.headers.get("x-forwarded-for", "")
    chain = [item.strip() for item in forwarded.split(",") if item.strip()]
    chain.append(str(direct_ip))
    for candidate in reversed(chain):
        try:
            candidate_ip = ip_address(candidate)
        except ValueError:
            continue
        if not any(candidate_ip in network for network in trusted):
            return str(candidate_ip)
    return str(direct_ip)
