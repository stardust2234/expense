#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tls_dir="${project_root}/data/dev-tls"
ca_key="${tls_dir}/folio-dev-ca.key"
ca_cert="${tls_dir}/folio-dev-ca.pem"
server_key="${tls_dir}/server.key"
server_cert="${tls_dir}/server.pem"
server_csr="${tls_dir}/server.csr"
extensions="${tls_dir}/server.ext"
hosts_file="${tls_dir}/hosts"

mkdir -p "${tls_dir}"
chmod 700 "${tls_dir}"

if [[ ! -f "${ca_key}" || ! -f "${ca_cert}" ]]; then
  openssl genrsa -out "${ca_key}" 4096
  chmod 600 "${ca_key}"
  openssl req -x509 -new -sha256 -days 3650 \
    -key "${ca_key}" \
    -out "${ca_cert}" \
    -subj "/CN=Folio local development CA"
fi

san_entries=("DNS:localhost" "IP:127.0.0.1" "IP:::1")
if [[ -n "${DEV_HOST:-}" ]]; then
  printf '%s\n' "${DEV_HOST}" >> "${hosts_file}"
  sort -u -o "${hosts_file}" "${hosts_file}"
fi
if [[ -f "${hosts_file}" ]]; then
  while read -r configured_host; do
    [[ -z "${configured_host}" ]] && continue
    if [[ "${configured_host}" =~ ^[0-9a-fA-F:.]+$ ]]; then
      san_entries+=("IP:${configured_host}")
    else
      san_entries+=("DNS:${configured_host}")
    fi
  done < "${hosts_file}"
fi
while read -r address; do
  [[ -n "${address}" ]] && san_entries+=("IP:${address}")
done < <(hostname -I 2>/dev/null | tr ' ' '\n' | sed '/^$/d')

san_value="$(IFS=,; echo "${san_entries[*]}")"
printf 'subjectAltName=%s\nextendedKeyUsage=serverAuth\n' "${san_value}" > "${extensions}"

openssl genrsa -out "${server_key}" 2048
chmod 600 "${server_key}"
openssl req -new -key "${server_key}" -out "${server_csr}" -subj "/CN=localhost"
openssl x509 -req -sha256 -days 365 \
  -in "${server_csr}" \
  -CA "${ca_cert}" \
  -CAkey "${ca_key}" \
  -CAcreateserial \
  -out "${server_cert}" \
  -extfile "${extensions}"
rm -f "${server_csr}" "${extensions}"

printf 'HTTPS development certificate ready.\nTrust this CA on each browser device: %s\n' "${ca_cert}"

