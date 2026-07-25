from unicodedata import normalize


def normalise_description_identity(description: str) -> str:
    canonical = " ".join(normalize("NFKC", description).casefold().split())
    if not canonical:
        raise ValueError("description identity must not be empty")
    return f"description:{canonical}"


def merchant_identity(merchant_id: int) -> str:
    if merchant_id <= 0:
        raise ValueError("merchant identity must contain a positive ID")
    return f"merchant:{merchant_id}"


def normalise_recurring_identity(identity_key: str | None, description: str) -> str:
    if identity_key is None:
        return normalise_description_identity(description)

    prefix, separator, value = normalize("NFKC", identity_key).strip().partition(":")
    if not separator:
        raise ValueError("identity_key must start with merchant: or description:")
    prefix = prefix.casefold()
    if prefix == "merchant":
        try:
            return merchant_identity(int(value))
        except ValueError as error:
            raise ValueError("merchant identity must contain a positive ID") from error
    if prefix == "description":
        return normalise_description_identity(value)
    raise ValueError("identity_key must start with merchant: or description:")
