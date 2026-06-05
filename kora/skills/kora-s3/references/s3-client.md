# Kora S3 client — distilled reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/s3.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/s3.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-s3-client-aws/`, `.kora-agent/kora-examples/kora-java-s3-client-minio/`

Focused condensation of `kora-docs/.../documentation/s3-client.md`.

> Experimental module — `ru.tinkoff.kora.experimental:s3-client-*`. Stable in practice, but minor API changes possible before "stable" status.

## Two implementations

| Aspect | AWS | MinIO |
|--------|-----|-------|
| Artifact | `ru.tinkoff.kora.experimental:s3-client-aws` | `ru.tinkoff.kora.experimental:s3-client-minio` |
| Module FQN | `ru.tinkoff.kora.s3.client.aws.AwsS3ClientModule` | `ru.tinkoff.kora.s3.client.minio.MinioS3ClientModule` |
| Built on | AWS Java SDK v2 (`software.amazon.awssdk`) | minio-java (`io.minio`) |
| HTTP transport | Any `kora-client` HTTP module (required) | Auto-creates OkHttp; or use the `kora-client` OkHttp module |
| Native sync client | `software.amazon.awssdk.services.s3.S3Client` | `io.minio.MinioClient` |
| Native async client | `software.amazon.awssdk.services.s3.S3AsyncClient` | `io.minio.MinioAsyncClient` |
| Special tagged clients | `S3AsyncClient @Tag(software.amazon.awssdk.services.s3.model.MultipartUpload.class)` | — |

Both register Kora's portable imperative clients `S3KoraClient` / `S3KoraAsyncClient` and any number of declarative `@S3.Client` interfaces.

## Common configuration (`s3client.*`)

```hocon
s3client {
  url       = "https://s3.amazonaws.com"
  accessKey = "AKIA..."
  secretKey = "..."
  region    = "us-east-1"                            # or "aws-global" for AWS S3
  telemetry { /* logging, metrics, tracing */ }
}
```

Required: `url`, `accessKey`, `secretKey`. `region` is required for AWS, optional for some MinIO setups.

## AWS-specific (`s3client.aws.*`)

```hocon
s3client.aws {
  addressStyle              = "PATH"                 # "PATH" or "VIRTUAL_HOSTED"
  requestTimeout            = "45s"
  checksumValidationEnabled = false                  # MD5 validation on upload+download
  chunkedEncodingEnabled    = true                   # chunked Content-Encoding when signing
  upload {
    bufferSize = "32MiB"                             # max in-memory buffer for the AWS Transfer Manager
    partSize   = "8MiB"                              # multipart chunk size; minimum 5MiB per S3 spec
  }
}
```

Tuning notes:
- `addressStyle = "PATH"` is the safe default. MinIO, Yandex Object Storage, and Ceph S3 typically require `PATH`. AWS S3 itself supports both — newer accounts default to `VIRTUAL_HOSTED`.
- `checksumValidationEnabled = false` skips the MD5 checksum overhead; default off for performance.
- `partSize` of 8 MiB is fine for most cases. Bump to 16–64 MiB for very large files; never below 5 MiB (S3 rejects).

## MinIO-specific (`s3client.minio.*`)

```hocon
s3client.minio {
  addressStyle   = "PATH"
  requestTimeout = "45s"
  upload {
    partSize = "8MiB"
  }
}
```

MinIO doesn't expose checksum validation or chunked-encoding switches — both are SDK defaults.

## Per-client configuration (`s3client.<name>.*`)

Each `@S3.Client("s3client.<name>")` reads its own block. Required key: `bucket`.

```hocon
s3client.documents {
  bucket = ${DOCUMENTS_BUCKET}
}

s3client.thumbnails {
  bucket = ${THUMBNAILS_BUCKET}
}
```

## Declarative annotations — package and shapes

All under `ru.tinkoff.kora.s3.client.annotation.S3` (nested types).

| Annotation | Method shape | Returns |
|-----------|--------------|---------|
| `@S3.Client("config.path")` | on the interface | — |
| `@S3.Get` | `(String key)` or `(args matching template)` or `(List<String> keys)` | `S3Object` / `S3ObjectMeta` / `List<S3Object>` / `List<S3ObjectMeta>` |
| `@S3.List` | `(String prefix)` or `(args matching template)` | `S3ObjectList` / `S3ObjectMetaList` |
| `@S3.Put` | `(String key, S3Body body)` or `(args, S3Body body)` | `void` / `S3ObjectUpload` |
| `@S3.Delete` | `(String key)` / `(List<String> keys)` / `(args matching template)` | `void` |

`S3Object` includes data; `S3ObjectMeta` is metadata only (faster — HEAD request).

### Key / prefix templates

Format: `"some-prefix-{argName1}-{argName2}-suffix"`.

- Each `{name}` substitutes a method argument by name, via `toString()`.
- **Every method argument** must appear in the template — extras cause compile errors.
- Multi-key operations (e.g., `List<String> keys` for `@S3.Get`) **cannot** use templates.
- `@S3.List` also supports `delimiter = "/"` for folder-style listing.
- `@S3.List` accepts `limit = N` (max 1000 per S3 spec; defaults to 1000).

### `S3Body` factories

All at `ru.tinkoff.kora.s3.client.model.S3Body`:

| Factory | Length | Backed by |
|---------|--------|-----------|
| `ofBytes(byte[])` | known | in-memory `byte[]` |
| `ofBuffer(ByteBuffer)` | known | NIO buffer |
| `ofInputStream(InputStream, long size)` | known | stream, must know length |
| `ofInputStreamReadAll(InputStream)` | unknown → known | reads stream into memory once, then serves bytes |
| `ofInputStreamUnbound(InputStream)` | unknown | stream, multipart upload engaged |
| `ofPublisher(Flow.Publisher<ByteBuffer>, long size)` | known | reactive stream |
| `ofPublisher(Flow.Publisher<ByteBuffer>)` | unknown | reactive stream, multipart (overload without `size`) |

Every factory has overloads adding `(..., String type)` and `(..., String type, String encoding)` for explicit content-type and content-encoding. Content type defaults to `application/octet-stream` when omitted.

### Response types

| Type | Contains |
|------|----------|
| `S3Object` | bucket, key, last-modified, content-type, size, body (`InputStream` / `Flow.Publisher<ByteBuffer>` accessors) |
| `S3ObjectMeta` | bucket, key, last-modified, content-type, size — no body |
| `S3ObjectList` | list of `S3Object`s, common prefixes, isTruncated, nextContinuationToken |
| `S3ObjectMetaList` | list of `S3ObjectMeta`s + same pagination info |
| `S3ObjectUpload` | key, etag, version-id, last-modified after upload |

All under `ru.tinkoff.kora.s3.client.model.*`.

## Imperative clients

### Kora-portable

```java
public interface S3KoraClient {
    S3Object   get(String bucket, String key);
    S3ObjectMeta head(String bucket, String key);
    S3ObjectList list(String bucket, String prefix);
    S3ObjectUpload put(String bucket, String key, S3Body body);
    void delete(String bucket, String key);
    // batch variants, etc.
}
```

`S3KoraAsyncClient` mirrors with `CompletionStage<T>` returns.

Use when you need explicit bucket control per call (e.g., dynamic bucket names) or when working in library code that can't depend on a specific declarative interface.

### AWS native — when to drop down

The AWS SDK exposes features the portable API doesn't cover:

- Presigned URLs (`S3Presigner`)
- Bucket lifecycle policies
- Replication configuration
- Versioning, object lock, retention
- Server-side encryption customer keys (SSE-C)
- Transfer Manager integration for hyper-fast batch transfers

Inject `software.amazon.awssdk.services.s3.S3Client` (sync) or `S3AsyncClient` (async). For the batch-upload-optimized async client, inject with `@Tag(software.amazon.awssdk.services.s3.model.MultipartUpload.class)`.

### MinIO native

Inject `io.minio.MinioClient` (sync) or `io.minio.MinioAsyncClient` (async). Used for MinIO-specific extensions (admin API, identity management, etc.).

## Response formats — AWS-specific

When using the declarative client with the AWS module, methods can return AWS SDK types directly (instead of Kora's portable types):

| Operation | Kora-portable return | AWS-native return |
|-----------|---------------------|-------------------|
| Get | `S3Object` / `S3ObjectMeta` | `GetObjectResponse` / `ResponseInputStream<GetObjectResponse>` |
| Head | `S3ObjectMeta` | `HeadObjectResponse` |
| List | `S3ObjectList` / `S3ObjectMetaList` | `ListObjectsV2Response` |
| Put | `S3ObjectUpload` | `PutObjectResponse` |
| Delete | `void` | `DeleteObjectResponse` / `DeleteObjectsResponse` |

This couples the client to the AWS SDK — only use when you genuinely need fields the portable types don't expose.

## Exceptions

All under `ru.tinkoff.kora.s3.client.*`:

- `S3Exception` — base.
- `S3NotFoundException` — key/bucket not found.
- `S3DeleteException` — bulk delete with per-key result inspection.

## Metrics

| Metric | Type | Tags |
|--------|------|------|
| `s3.client.duration` | DistributionSummary | `aws.s3.bucket`, `aws.operation.name`, `error.type` |
| `s3.kora.client.duration` | DistributionSummary | `aws.client.name`, `aws.s3.bucket`, `aws.operation.name`, `error.type` |

The `s3.client.*` series is at the SDK layer; `s3.kora.client.*` is at Kora's portable layer. Both enabled by default; disable per impl via `s3client.aws.telemetry.metrics.enabled = false` (or `minio.`).
