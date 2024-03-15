# General Dex GRPC Message for Client
## Need to be refactored to use the same logic as config.py
_config_keys = [
    "id",
    "secret",
    "redirect_uris",
    "trusted_peers",
    "public",
    "name",
    "logo_url",
]


def parse_list(list_from_vault: str | list) -> list:
    """
    Nativly Vault can't support lists in UI(except json view), omg Hashicop:)
    """
    if isinstance(list_from_vault, list):
        return list_from_vault

    if isinstance(list_from_vault, str):
        return list_from_vault.split(",")
    else:
        return []


def parse_bool(bool_from_vault: bool | str) -> bool:
    if isinstance(bool_from_vault, bool):
        return bool_from_vault
    return False


def _fill_missing_keys(config: dict) -> dict:
    for key in _config_keys:
        if key in ["redirect_uris", "trusted_peers"]:
            config[key] = parse_list(config.get(key))
        config["public"] = parse_bool(config.get("public", False))
    return config


def _camel_case_to_undercore(config: dict) -> dict:
    """
    Tranform camel case response from Dex GRPC
    """
    return {
        "".join(["_" + i.lower() if i.isupper() else i for i in key]).lstrip("_"): value
        for key, value in config.items()
    }


def normalize_config(client_config: dict) -> dict | None:
    """
    Normilize Dex config to one standart.
    I know, re is better, but I don't like it
    """
    if {"id", "secret"}.issubset(client_config.keys()):
        config = _camel_case_to_undercore(client_config)
        return _fill_missing_keys(config)
    return None
