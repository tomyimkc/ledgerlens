#!/usr/bin/env bash
set -euo pipefail

TUNNEL_STATE_DIR="${LIVE_PROOF_TUNNEL_STATE_DIR:-$HOME/.cache/ledgerlens-live-proof-tunnels}"
CADDY_IMAGE="${LIVE_PROOF_CADDY_IMAGE:-caddy:2.10.2-alpine}"
CONTAINER_NAME="${LIVE_PROOF_GATEWAY_CONTAINER:-ledgerlens-live-proof-gateway}"
LEDGERLENS_ORIGIN_PORT="${LIVE_PROOF_LEDGERLENS_PORT:-18000}"
DATAHUB_ORIGIN_PORT="${LIVE_PROOF_DATAHUB_PORT:-9002}"
LEDGERLENS_GATEWAY_PORT="${LIVE_PROOF_LEDGERLENS_GATEWAY_PORT:-18080}"
DATAHUB_GATEWAY_PORT="${LIVE_PROOF_DATAHUB_GATEWAY_PORT:-19002}"
SKIP_LEDGERLENS="${LIVE_PROOF_SKIP_LEDGERLENS:-0}"
CADDYFILE="$TUNNEL_STATE_DIR/Caddyfile"
DOCKER_HOST_ALIAS="${LIVE_PROOF_DOCKER_HOST_ALIAS:-}"

usage() {
  cat <<'EOF'
Usage: deploy/live-proof/quick_tunnels.sh {check|start|status|stop}

Creates temporary Cloudflare Quick Tunnels to loopback-only, basic-authenticated
gateways. It does not create DNS records, named tunnels, VMs, or paid resources.

Required for start:
  LIVE_PROOF_PUBLIC_ACK=temporary-public-proof
  LIVE_PROOF_GATEWAY_USERNAME=<non-secret username>
  LIVE_PROOF_GATEWAY_PASSWORD_HASH=<Caddy bcrypt hash>

Optional:
  LIVE_PROOF_SKIP_LEDGERLENS=1       expose only DataHub
  LIVE_PROOF_ALLOW_IMAGE_PULL=1      allow the pinned Caddy image pull if absent
EOF
}

require_port_number() {
  local value="$1"
  local name="$2"
  if [[ ! "$value" =~ ^[0-9]+$ ]] || ((value < 1024 || value > 65535)); then
    printf '%s must be an integer between 1024 and 65535.\n' "$name" >&2
    return 2
  fi
}

port_is_listening() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
  elif command -v ss >/dev/null 2>&1; then
    ss -ltnH "sport = :$port" 2>/dev/null | grep -q .
  else
    return 1
  fi
}

origin_is_healthy() {
  local port="$1"
  local health_path="$2"
  curl --fail --silent --show-error --location --max-time 5 \
    "http://127.0.0.1:${port}${health_path}" >/dev/null
}

quick_tunnel_config_conflict() {
  [[ -f "$HOME/.cloudflared/config.yml" || -f "$HOME/.cloudflared/config.yaml" ]]
}

validate_inputs() {
  require_port_number "$LEDGERLENS_ORIGIN_PORT" LIVE_PROOF_LEDGERLENS_PORT
  require_port_number "$DATAHUB_ORIGIN_PORT" LIVE_PROOF_DATAHUB_PORT
  require_port_number "$LEDGERLENS_GATEWAY_PORT" LIVE_PROOF_LEDGERLENS_GATEWAY_PORT
  require_port_number "$DATAHUB_GATEWAY_PORT" LIVE_PROOF_DATAHUB_GATEWAY_PORT
  if [[ "$SKIP_LEDGERLENS" != "0" && "$SKIP_LEDGERLENS" != "1" ]]; then
    echo "LIVE_PROOF_SKIP_LEDGERLENS must be 0 or 1." >&2
    return 2
  fi
  if [[ "$DATAHUB_GATEWAY_PORT" == "$LEDGERLENS_GATEWAY_PORT" ]]; then
    echo "The two gateway ports must be distinct." >&2
    return 2
  fi
  if [[ -n "$DOCKER_HOST_ALIAS" && ! "$DOCKER_HOST_ALIAS" =~ ^[A-Za-z0-9.-]+$ ]]; then
    echo "LIVE_PROOF_DOCKER_HOST_ALIAS is not a valid hostname." >&2
    return 2
  fi
}

check_origins() {
  if [[ "$SKIP_LEDGERLENS" == "0" ]] \
    && ! origin_is_healthy "$LEDGERLENS_ORIGIN_PORT" /healthz; then
    printf 'LedgerLens origin is not healthy on loopback port %s.\n' \
      "$LEDGERLENS_ORIGIN_PORT" >&2
    return 1
  fi
  if ! origin_is_healthy "$DATAHUB_ORIGIN_PORT" /login; then
    printf 'DataHub origin is not healthy on loopback port %s.\n' \
      "$DATAHUB_ORIGIN_PORT" >&2
    return 1
  fi
}

check_command() {
  validate_inputs
  for command_name in cloudflared curl docker grep ps; do
    command -v "$command_name" >/dev/null 2>&1 || {
      printf 'Required command is unavailable: %s\n' "$command_name" >&2
      return 127
    }
  done
  docker info >/dev/null
  if [[ -z "$DOCKER_HOST_ALIAS" ]]; then
    if [[ "$(docker context show 2>/dev/null || true)" == "colima" ]]; then
      DOCKER_HOST_ALIAS=host.lima.internal
    else
      DOCKER_HOST_ALIAS=host.docker.internal
    fi
  fi
  if quick_tunnel_config_conflict; then
    cat >&2 <<'EOF'
Cloudflare Quick Tunnels are incompatible with ~/.cloudflared/config.yml or
config.yaml. Rename that file explicitly before using this temporary path.
EOF
    return 2
  fi
  check_origins
  for port in "$LEDGERLENS_GATEWAY_PORT" "$DATAHUB_GATEWAY_PORT"; do
    if port_is_listening "$port"; then
      printf 'Gateway port %s is already listening; refusing to take it over.\n' "$port" >&2
      return 2
    fi
  done
  if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
    printf 'Gateway container %s already exists; run stop or inspect it manually.\n' \
      "$CONTAINER_NAME" >&2
    return 2
  fi
  if docker image inspect "$CADDY_IMAGE" >/dev/null 2>&1; then
    echo "caddy_image=present"
  else
    echo "caddy_image=absent"
  fi
  echo "Quick-tunnel preflight passed."
}

write_caddyfile() {
  local username="${LIVE_PROOF_GATEWAY_USERNAME:-}"
  local password_hash="${LIVE_PROOF_GATEWAY_PASSWORD_HASH:-}"
  if [[ ! "$username" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "LIVE_PROOF_GATEWAY_USERNAME has unsupported characters." >&2
    return 2
  fi
  if [[ ! "$password_hash" =~ ^\$2[aby]\$ ]] \
    || [[ "$password_hash" == *$'\n'* || "$password_hash" == *$'\r'* ]]; then
    echo "LIVE_PROOF_GATEWAY_PASSWORD_HASH must be a single-line Caddy bcrypt hash." >&2
    return 2
  fi

  {
    cat <<'EOF'
{
	admin off
	auto_https off
}

(proof_security) {
	basic_auth {
EOF
    printf '\t\t%s %s\n' "$username" "$password_hash"
    cat <<'EOF'
	}
	encode zstd gzip
	header {
		Cache-Control "no-store"
		X-Content-Type-Options "nosniff"
		X-Frame-Options "DENY"
		Referrer-Policy "no-referrer"
		Permissions-Policy "camera=(), microphone=(), geolocation=()"
		-Server
	}
}
EOF
    if [[ "$SKIP_LEDGERLENS" == "0" ]]; then
      cat <<EOF

:18080 {
	import proof_security
	reverse_proxy ${DOCKER_HOST_ALIAS}:${LEDGERLENS_ORIGIN_PORT}
}
EOF
    fi
    cat <<EOF

:19002 {
	import proof_security
	reverse_proxy ${DOCKER_HOST_ALIAS}:${DATAHUB_ORIGIN_PORT}
}
EOF
  } >"$CADDYFILE"
  chmod 600 "$CADDYFILE"
}

gateway_http_code() {
  local port="$1"
  curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
    --max-time 5 "http://127.0.0.1:${port}/" 2>/dev/null || true
}

wait_for_gateway() {
  local port="$1"
  for _ in {1..30}; do
    if [[ "$(gateway_http_code "$port")" == "401" ]]; then
      return 0
    fi
    sleep 1
  done
  printf 'Authenticated gateway on port %s did not return HTTP 401.\n' "$port" >&2
  return 1
}

wait_for_tunnel_url() {
  local log_file="$1"
  local url_file="$2"
  for _ in {1..45}; do
    local url
    url="$(grep -Eo 'https://[-a-z0-9]+\.trycloudflare\.com' "$log_file" \
      2>/dev/null | head -1 || true)"
    if [[ -n "$url" ]]; then
      printf '%s\n' "$url" >"$url_file"
      chmod 600 "$url_file"
      return 0
    fi
    sleep 1
  done
  printf 'Cloudflare Quick Tunnel URL did not appear in %s.\n' "$log_file" >&2
  return 1
}

wait_for_public_auth() {
  local url="$1"
  local code=""
  for _ in {1..60}; do
    code="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
      --max-time 10 "$url" 2>/dev/null || true)"
    if [[ "$code" == "401" ]]; then
      return 0
    fi
    sleep 2
  done
  printf 'Public URL did not enforce HTTP 401 within 120 seconds (last code: %s): %s\n' \
    "${code:-unreachable}" "$url" >&2
  return 1
}

start_tunnel() {
  local name="$1"
  local gateway_port="$2"
  local log_file="$TUNNEL_STATE_DIR/${name}.log"
  local pid_file="$TUNNEL_STATE_DIR/${name}.pid"
  local url_file="$TUNNEL_STATE_DIR/${name}.url"

  : >"$log_file"
  chmod 600 "$log_file"
  nohup cloudflared --no-autoupdate tunnel \
    --url "http://127.0.0.1:${gateway_port}" >"$log_file" 2>&1 &
  printf '%s\n' "$!" >"$pid_file"
  chmod 600 "$pid_file"
  wait_for_tunnel_url "$log_file" "$url_file"
  wait_for_public_auth "$(<"$url_file")"
}

process_matches_tunnel() {
  local pid="$1"
  local gateway_port="$2"
  local command_line
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  command_line="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  [[ "$command_line" == *"cloudflared"* \
    && "$command_line" == *"127.0.0.1:${gateway_port}"* ]]
}

stop_tunnel() {
  local name="$1"
  local gateway_port="$2"
  local pid_file="$TUNNEL_STATE_DIR/${name}.pid"
  [[ -f "$pid_file" ]] || return 0
  local pid
  pid="$(<"$pid_file")"
  if process_matches_tunnel "$pid" "$gateway_port"; then
    kill -TERM "$pid"
    for _ in {1..20}; do
      if ! kill -0 "$pid" 2>/dev/null; then
        break
      fi
      sleep 0.5
    done
    if kill -0 "$pid" 2>/dev/null; then
      printf 'Tunnel PID %s did not stop after SIGTERM; leaving it for manual review.\n' \
        "$pid" >&2
      return 1
    fi
  elif kill -0 "$pid" 2>/dev/null; then
    printf 'Refusing to signal PID %s because it does not match tunnel %s.\n' \
      "$pid" "$name" >&2
    return 1
  fi
  : >"$pid_file"
}

stop_gateway() {
  if ! docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
    return 0
  fi
  local owned
  owned="$(docker inspect --format \
    '{{index .Config.Labels "com.ledgerlens.live-proof"}}' "$CONTAINER_NAME")"
  if [[ "$owned" != "true" ]]; then
    printf 'Refusing to stop unowned container %s.\n' "$CONTAINER_NAME" >&2
    return 1
  fi
  docker stop --signal SIGTERM --timeout 20 "$CONTAINER_NAME" >/dev/null
  if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
    docker rm "$CONTAINER_NAME" >/dev/null
  fi
}

stop_command() {
  local failed=0
  stop_tunnel ledgerlens "$LEDGERLENS_GATEWAY_PORT" || failed=1
  stop_tunnel datahub "$DATAHUB_GATEWAY_PORT" || failed=1
  stop_gateway || failed=1
  echo "Quick Tunnels and the owned auth gateway are stopped; private logs remain in state."
  return "$failed"
}

start_command() {
  if [[ "${LIVE_PROOF_PUBLIC_ACK:-}" != "temporary-public-proof" ]]; then
    cat >&2 <<'EOF'
Refusing to create public URLs without an explicit acknowledgement.
Review the origins and credentials, then set:
  LIVE_PROOF_PUBLIC_ACK=temporary-public-proof
EOF
    return 2
  fi

  check_command
  mkdir -p "$TUNNEL_STATE_DIR"
  chmod 700 "$TUNNEL_STATE_DIR"
  # Docker Desktop resolves bind mounts in the daemon VM. Use the physical path
  # so macOS /tmp -> /private/tmp symlinks do not become directory/file mismatches.
  TUNNEL_STATE_DIR="$(cd "$TUNNEL_STATE_DIR" && pwd -P)"
  CADDYFILE="$TUNNEL_STATE_DIR/Caddyfile"
  write_caddyfile

  if ! docker image inspect "$CADDY_IMAGE" >/dev/null 2>&1; then
    if [[ "${LIVE_PROOF_ALLOW_IMAGE_PULL:-0}" != "1" ]]; then
      printf 'Pinned image %s is absent; set LIVE_PROOF_ALLOW_IMAGE_PULL=1 to pull it.\n' \
        "$CADDY_IMAGE" >&2
      return 2
    fi
    docker pull "$CADDY_IMAGE"
  fi

  docker run --rm \
    --volume "$CADDYFILE:/etc/caddy/Caddyfile:ro" \
    "$CADDY_IMAGE" \
    caddy validate --config /etc/caddy/Caddyfile

  local completed=0
  cleanup_on_failure() {
    local exit_code=$?
    if ((completed == 0)); then
      stop_command || true
    fi
    return "$exit_code"
  }
  trap cleanup_on_failure EXIT

  local docker_args=(
    run
    --detach
    --name "$CONTAINER_NAME"
    --label com.ledgerlens.live-proof=true
    --restart no
    --read-only
    --security-opt no-new-privileges:true
    --cap-drop ALL
    --cap-add NET_BIND_SERVICE
    --tmpfs "/data:rw,noexec,nosuid,size=16m"
    --tmpfs "/config:rw,noexec,nosuid,size=16m"
  )
  if [[ "$DOCKER_HOST_ALIAS" == "host.docker.internal" ]]; then
    docker_args+=(--add-host host.docker.internal:host-gateway)
  fi
  if [[ "$SKIP_LEDGERLENS" == "0" ]]; then
    docker_args+=(--publish "127.0.0.1:${LEDGERLENS_GATEWAY_PORT}:18080")
  fi
  docker_args+=(
    --publish "127.0.0.1:${DATAHUB_GATEWAY_PORT}:19002"
    --volume "$CADDYFILE:/etc/caddy/Caddyfile:ro"
    "$CADDY_IMAGE"
    caddy run --config /etc/caddy/Caddyfile
  )
  docker "${docker_args[@]}" >/dev/null

  if [[ "$SKIP_LEDGERLENS" == "0" ]]; then
    wait_for_gateway "$LEDGERLENS_GATEWAY_PORT"
  fi
  wait_for_gateway "$DATAHUB_GATEWAY_PORT"

  if [[ "$SKIP_LEDGERLENS" == "0" ]]; then
    start_tunnel ledgerlens "$LEDGERLENS_GATEWAY_PORT"
  fi
  start_tunnel datahub "$DATAHUB_GATEWAY_PORT"

  completed=1
  trap - EXIT
  echo "Temporary authenticated public proof is ready."
  if [[ "$SKIP_LEDGERLENS" == "0" ]]; then
    printf 'LedgerLens URL: %s\n' "$(<"$TUNNEL_STATE_DIR/ledgerlens.url")"
  fi
  printf 'DataHub URL: %s\n' "$(<"$TUNNEL_STATE_DIR/datahub.url")"
  printf 'Gateway username: %s\n' "$LIVE_PROOF_GATEWAY_USERNAME"
  echo "The password and password hash were not printed."
}

status_one() {
  local name="$1"
  local gateway_port="$2"
  local pid_file="$TUNNEL_STATE_DIR/${name}.pid"
  local url_file="$TUNNEL_STATE_DIR/${name}.url"
  local running=no
  if [[ -f "$pid_file" ]] && process_matches_tunnel "$(<"$pid_file")" "$gateway_port"; then
    running=yes
  fi
  printf '%s_tunnel_running=%s\n' "$name" "$running"
  if [[ -f "$url_file" ]]; then
    printf '%s_url=%s\n' "$name" "$(<"$url_file")"
  fi
}

status_command() {
  if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
    printf 'gateway_container=%s\n' \
      "$(docker inspect --format '{{.State.Status}}' "$CONTAINER_NAME")"
  else
    echo "gateway_container=absent"
  fi
  if [[ "$SKIP_LEDGERLENS" == "0" ]]; then
    status_one ledgerlens "$LEDGERLENS_GATEWAY_PORT"
  fi
  status_one datahub "$DATAHUB_GATEWAY_PORT"
}

case "${1:-status}" in
  check)
    check_command
    ;;
  start)
    start_command
    ;;
  status)
    status_command
    ;;
  stop)
    stop_command
    ;;
  -h | --help | help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
