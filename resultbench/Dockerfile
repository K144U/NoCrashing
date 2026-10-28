# One image for every ResultBench component: rb <subcommand>.
FROM golang:1.24-alpine AS build
WORKDIR /src
COPY . .
# Use vendored modules when present (offline builds), otherwise download.
RUN if [ -d vendor ]; then flags=-mod=vendor; else go mod download; fi; \
    CGO_ENABLED=0 go build $flags -trimpath -ldflags="-s -w" -o /out/rb ./cmd/rb

FROM alpine:3.20
COPY --from=build /out/rb /usr/local/bin/rb
ENTRYPOINT ["rb"]
