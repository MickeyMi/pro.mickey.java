ARG VERSION=v0.72.0
FROM ghcr.io/fatedier/frps:${VERSION} AS source
RUN mv /usr/bin/frps /java

FROM alpine:3
RUN apk add --no-cache tzdata && mkdir -p /etc/java
COPY --from=source /java /usr/bin/java
RUN /usr/bin/java --version
EXPOSE 7000
ENTRYPOINT ["/usr/bin/java"]
CMD ["-c", "/etc/java/config.toml"]
