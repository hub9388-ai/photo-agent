# Local acceptance only: official community registry images are no longer available.
# Compile the official source at a fixed commit; do not use an unknown mirror.
FROM golang:1.24.8-alpine@sha256:3d78beb141d98f42337f1252ecf2a5f20374109929a4c3f6817f9e4179cc0ae5 AS build
ENV CGO_ENABLED=0
RUN go install github.com/minio/minio@7aac2a2c5b7c882e68c1ce017d8256be2feea27f

FROM alpine:3.22@sha256:5291449c3df73caf6ed85e649dec1b9e818b39a5d8c871e97afc13e9cd5e8fa8
COPY --from=build /go/bin/minio /usr/local/bin/minio
COPY --from=build /go/pkg/mod/github.com/minio/minio@*/LICENSE /usr/share/licenses/minio/LICENSE
EXPOSE 9000 9001
ENTRYPOINT ["minio"]
