# syntax=docker/dockerfile:1
ARG FRPS_VERSION=v0.72.0
ARG FRPS_BASE=ghcr.io/fatedier/frps:${FRPS_VERSION}
FROM ${FRPS_BASE}

ARG FRPS_VERSION
LABEL org.opencontainers.image.title="frps-custom" \
      org.opencontainers.image.description="Upstream frps with the executable named java" \
      org.opencontainers.image.version="${FRPS_VERSION}"

# Use a real rename, not a symlink or a shell wrapper: Linux comm follows
# the executable filename. The upstream binary and protocol are unchanged.
RUN test -x /usr/bin/frps \
    && test ! -e /usr/bin/java \
    && mv /usr/bin/frps /usr/bin/java \
    && mkdir -p /etc/frp

EXPOSE 7000/tcp
STOPSIGNAL SIGTERM
ENTRYPOINT ["/usr/bin/java"]
CMD ["-c", "/etc/frp/frps.toml"]
