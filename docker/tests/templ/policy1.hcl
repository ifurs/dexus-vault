# list and read Dex clients stored in the "kv" KV v2 engine under "dex/"
path "kv/metadata/dex/*" {
  capabilities = ["list"]
}

path "kv/data/dex/*" {
  capabilities = ["read"]
}
