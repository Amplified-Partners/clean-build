# AppArmor profile for Amplified agent containers (AMP-289)
# ==========================================================
# Load with: sudo apparmor_parser -r -W /etc/apparmor.d/amplified-agent
# Reference in compose: security_opt: ["apparmor=amplified-agent"]
#
# Policy: deny dangerous syscalls, restrict filesystem writes,
# allow network for HTTP/gRPC only.
#
# Signed-by: Devon-abaf | 2026-05-09 | session devin-abaf337e1eda492f85af1d26fa1614b9

#include <tunables/global>

profile amplified-agent flags=(attach_disconnected,mediate_deleted) {
  #include <abstractions/base>
  #include <abstractions/nameservice>

  # ─── Filesystem ─────────────────────────────────────────────────────────────
  # Read-only access to most paths
  / r,
  /** r,

  # Writable: /tmp, /var/log, /workspace (agent working dir)
  /tmp/** rw,
  /var/tmp/** rw,
  /var/log/** rw,
  /workspace/** rw,
  /app/** r,
  /app/tmp/** rw,

  # Python/Node runtime needs
  /usr/lib/** r,
  /usr/local/** r,
  /proc/** r,
  /sys/fs/cgroup/** r,
  /dev/null rw,
  /dev/urandom r,
  /dev/zero r,

  # ─── Network ────────────────────────────────────────────────────────────────
  # Allow TCP/UDP (HTTP, gRPC, DNS)
  network inet stream,
  network inet dgram,
  network inet6 stream,
  network inet6 dgram,

  # Deny raw sockets (no packet sniffing, no ICMP spoofing)
  deny network raw,
  deny network packet,

  # ─── Capabilities ──────────────────────────────────────────────────────────
  # Deny all dangerous capabilities
  deny capability sys_admin,
  deny capability sys_module,
  deny capability sys_rawio,
  deny capability sys_ptrace,
  deny capability net_admin,
  deny capability net_raw,
  deny capability mknod,
  deny capability sys_boot,
  deny capability sys_nice,

  # ─── Mount / Ptrace ────────────────────────────────────────────────────────
  deny mount,
  deny umount,
  deny pivot_root,
  deny ptrace,

  # ─── Signal ────────────────────────────────────────────────────────────────
  # Allow signals within own container only
  signal (send, receive) peer=amplified-agent,
}
