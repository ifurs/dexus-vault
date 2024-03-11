path "sys/capabilities-self" { capabilities = ["update"] }

path "kv/data/dex/*" {
  capabilities = ["list", "read"]
}

path "kv/metadata/dex/*" {
  capabilities = ["list", "read"]
}