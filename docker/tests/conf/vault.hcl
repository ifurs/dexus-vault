ui = true
disable_mlock = true
api_addr = "http://127.0.0.1:8200"

// storage "file" {
//   path = "/etc/vault/data"
// }
storage "inmem" {}

listener "tcp" {
  address = "0.0.0.0:8200"
  tls_disable = true
}
