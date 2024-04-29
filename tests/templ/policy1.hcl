path "sys/capabilities-self" { capabilities = ["update"] }

# for dexus_vault, you don't need that permission
path "kv/*" {
  capabilities = ["list"]
}

# access to clients in Vault
path "kv/data/dex/*" {
  capabilities = ["list", "read"]
}

# if you use secrets v2, also provide access to metadata
path "kv/metadata/dex/*" {
  capabilities = ["list", "read"]
}
