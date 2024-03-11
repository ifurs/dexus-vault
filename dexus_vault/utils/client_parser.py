# General Dex GRPC Message for Client
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
    if type(list_from_vault) == list:
        return [x for x in list_from_vault]  # TODO: Check if it really needs:)

    if type(list_from_vault) == str:
        return list_from_vault.split(",")

    else:
        return []


def _fill_missing_keys(config: dict) -> dict:
    for key in _config_keys:
        if key in ["redirect_uris", "trusted_peers"]:
            config[key] = parse_list(config.get(key, None))
        config["public"] = config.get("public", False)
    return config


def _camel_case_to_undercore(config: dict) -> dict:
    """
    Tranform camel case response from Dex GRPC
    """
    new_config = {}
    for key in config:
        new_key = "".join(["_" + i.lower() if i.isupper() else i for i in key]).lstrip(
            "_"
        )
        new_config[new_key] = config[key]
    return new_config


def normalize_config(client_config: dict) -> dict | None:
    """
    Normilize Dex config to one standart.
    I know, re is better, but I don't like it
    """
    if client_config.keys() >= {"id", "secret"}:
        config = _camel_case_to_undercore(client_config)
        return _fill_missing_keys(config)

    return None
