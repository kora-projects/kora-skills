---
name: kora-s3
description: "S3-compatible object storage integration (AWS S3, MinIO) in Kora apps. Declarative @S3.Client interfaces with @S3.Get/@S3.List/@S3.Put/@S3.Delete, imperative S3KoraClient, AWS SDK v2 or MinIO implementations, multipart uploads, and key templates. Use when storing files, images, or binary data. Triggers - @S3.Client, @S3.Get, @S3.Put, AwsS3ClientModule, MinioS3ClientModule, S3Body, S3Object, multipart upload, object storage."
---

# kora-s3 — object storage

Read this first when:
- adding S3-compatible storage (AWS S3, MinIO, Ceph) to a Kora app,
- choosing between AWS SDK (`s3-client-aws`) and MinIO (`s3-client-minio`) implementations,
- writing declarative `@S3.Client` interfaces vs using imperative `S3KoraClient`,
- streaming large files via multipart uploads with `S3Body.ofPublisher()`,
- modeling S3 key templates with `{argName}` path substitutions,
- handling S3-specific responses (`GetObjectResponse`, `ListObjectsV2Response`, presigned URLs).

## Pick an implementation

| Aspect | AWS SDK | MinIO |
|--------|---------|-------|
| Artifact | `ru.tinkoff.kora.experimental:s3-client-aws` | `ru.tinkoff.kora.experimental:s3-client-minio` |
| Module | `AwsS3ClientModule` (`ru.tinkoff.kora.s3.client.aws`) | `MinioS3ClientModule` (`ru.tinkoff.kora.s3.client.minio`) |
| Native client classes | `S3Client` (sync), `S3AsyncClient` (async), `S3AsyncClient @Tag(MultipartUpload.class)` (batch uploads) | `MinioClient` (sync), `MinioAsyncClient` (async) |
| HTTP transport | Any `kora-client` HTTP module (required) | Auto-creates OkHttp; or use the OkHttp module |
| Best for | AWS S3 itself, deep S3 feature use (versioning, ACL, etc.), AWS Java SDK ecosystem | MinIO server, simpler API surface, smaller dependency footprint |

Plug exactly one. Both expose Kora's common `S3KoraClient` / `S3KoraAsyncClient` API on top, so declarative `@S3.Client` interfaces are portable between them — switching implementations changes only the module on `@KoraApp` and a few config keys.

```groovy
implementation "ru.tinkoff.kora.experimental:s3-client-aws"
implementation "ru.tinkoff.kora:http-client-async"             // any kora-client HTTP module
```

```java
@KoraApp
public interface Application extends AwsS3ClientModule, AsyncHttpClientModule, /* ... */ { }
```

## Declarative client — the canonical shape

```java
@S3.Client("s3client.documents")
public interface DocumentsClient {

    @S3.Get
    S3Object get(String key);                      // full body + metadata

    @S3.Get
    S3ObjectMeta head(String key);                 // metadata only (faster)

    @S3.List(limit = 100)
    S3ObjectList list(String prefix);              // bodies included

    @S3.List
    S3ObjectMetaList listMeta(String prefix);      // metadata only

    @S3.Put
    S3ObjectUpload put(String key, S3Body body);

    @S3.Delete
    void delete(String key);
}
```

`@S3.Client("config.path")` on an **interface** — Kora generates the implementation and registers it as a component. The path is the per-client config block (see Configuration below).

Annotations live at `ru.tinkoff.kora.s3.client.annotation.S3` (nested annotations: `S3.Client`, `S3.Get`, `S3.List`, `S3.Put`, `S3.Delete`).

## Operations

### Get (`@S3.Get`)

```java
@S3.Get
S3Object get(String key);                          // body + meta

@S3.Get
S3ObjectMeta head(String key);                     // meta only — HEAD request, no body

@S3.Get("static-key")                              // static key in the annotation
S3Object getFixed();

@S3.Get("prefix-{tenantId}-{docId}")               // key template — args interpolated via toString()
S3Object getTyped(String tenantId, UUID docId);

@S3.Get
List<S3Object> getMany(List<String> keys);         // multi-key — NO template allowed
```

**Rules:**
- Key may be a method argument, a literal in the annotation, or a template combining both.
- Templates use `{argName}` placeholders. **Every method arg** must appear in the template (no extras).
- Multi-key get takes `List<String>` argument and returns `List<S3Object>` or `List<S3ObjectMeta>`. **Templates are not allowed** for multi-key.
- Return `S3Object` for body+meta, `S3ObjectMeta` for meta-only (HEAD request — much faster, no data transfer).

### List (`@S3.List`)

```java
@S3.List
S3ObjectList list(String prefix);                  // prefix as argument

@S3.List("static-prefix-")
S3ObjectList listFixed();                          // prefix in annotation

@S3.List(limit = 100)                              // max 1000 per S3 spec
S3ObjectList listLimited();

@S3.List("docs/{tenantId}/")                       // template
S3ObjectList listForTenant(String tenantId);

@S3.List(value = "logs/2024/", delimiter = "/")    // emulates "folder" listing
S3ObjectList listFolder();
```

`limit` defaults to 1000 (S3's per-request maximum). `delimiter = "/"` makes S3 group keys sharing a common prefix-up-to-delimiter into "common prefixes" — useful for emulating folder listings.

Use `S3ObjectMetaList` return type to skip body fetching.

### Put (`@S3.Put`)

```java
@S3.Put
void put(String key, S3Body body);                 // void return — fire and forget

@S3.Put
S3ObjectUpload putWithMeta(String key, S3Body body);  // returns upload metadata

@S3.Put("static-key")
void putFixed(S3Body body);

@S3.Put("docs/{tenantId}/{docId}.pdf")
void putTyped(String tenantId, UUID docId, S3Body body);
```

`S3Body` is Kora's content type with factory methods at `ru.tinkoff.kora.s3.client.model.S3Body`:

| Factory | Use when |
|---------|----------|
| `S3Body.ofBytes(byte[])` | Small payloads fully in memory |
| `S3Body.ofBuffer(ByteBuffer)` | Same, via NIO buffer |
| `S3Body.ofInputStream(InputStream, long size)` | Streaming, known length |
| `S3Body.ofInputStreamReadAll(InputStream)` | Reads the stream into memory once, then serves bytes — when length is unknown but the payload fits in heap |
| `S3Body.ofInputStreamUnbound(InputStream)` | Streaming, unknown length — engages chunked transfer / multipart upload |
| `S3Body.ofPublisher(Flow.Publisher<ByteBuffer>, long size)` | Reactive streaming, known length |
| `S3Body.ofPublisher(Flow.Publisher<ByteBuffer>)` | Reactive streaming, unknown length (no `size` argument = unbound) |

Every factory has overloads adding `(..., String type)` and `(..., String type, String encoding)` for explicit content-type and content-encoding. If you don't set a content type, the SDK defaults to `application/octet-stream`.

For very large or unknown-length uploads, prefer `ofPublisher(pub)` or `ofInputStreamUnbound(is)`. They engage S3's multipart upload mechanism automatically — chunks of `s3client.aws.upload.partSize` (default 8 MiB) are uploaded concurrently.

### Delete (`@S3.Delete`)

```java
@S3.Delete
void delete(String key);

@S3.Delete
void deleteMany(List<String> keys);                // batched delete

@S3.Delete("static-key")
void deleteFixed();

@S3.Delete("docs/{tenantId}/{docId}.pdf")
void deleteTyped(String tenantId, UUID docId);
```

Deletes are best-effort by default — non-existent keys don't error. For strict semantics, check first with `@S3.Get` returning `S3ObjectMeta`.

## Configuration

### Common (`s3client.*`)

```hocon
s3client {
  url       = ${S3_URL}                            # required, e.g. "https://s3.amazonaws.com" or "http://minio.local:9000"
  accessKey = ${S3_ACCESS_KEY}                     # required
  secretKey = ${S3_SECRET_KEY}                     # required
  region    = ${?S3_REGION:aws-global}             # required for AWS S3, ignored by some MinIO setups

  telemetry {
    logging.enabled = ${?S3_LOGGING:false}
    metrics.enabled = true                         # emits s3.client.duration / s3.kora.client.duration
    tracing.enabled = true
  }
}
```

### AWS-specific (`s3client.aws.*`)

```hocon
s3client.aws {
  addressStyle              = "PATH"               # "PATH" or "VIRTUAL_HOSTED"; MinIO usually needs "PATH"
  requestTimeout            = "45s"
  checksumValidationEnabled = false                # MD5 validation; expensive at scale
  chunkedEncodingEnabled    = true                 # chunked Content-Encoding for uploads
  upload {
    bufferSize = "32MiB"                           # max in-memory buffer
    partSize   = "8MiB"                            # multipart chunk size; minimum S3-imposed: 5MiB
  }
}
```

### MinIO-specific (`s3client.minio.*`)

```hocon
s3client.minio {
  addressStyle   = "PATH"
  requestTimeout = "45s"
  upload {
    partSize = "8MiB"
  }
}
```

### Per declarative-client (`s3client.<name>.*`)

```hocon
s3client.documents {
  bucket = ${?DOCUMENTS_BUCKET:documents}          # required for the declarative client
}
```

`bucket` is required — the declarative client uses it for every operation. Override per environment via env var.

## Imperative usage

When the declarative annotations don't fit (dynamic buckets, batch deletion with reporting, presigned URLs, ACL operations, versioning, …), inject one of the imperative clients.

### Kora's portable `S3KoraClient` / `S3KoraAsyncClient`

Same surface across AWS / MinIO implementations:

```java
@Component
public final class DocumentsService {
    private final S3KoraClient s3;

    public DocumentsService(S3KoraClient s3) {
        this.s3 = s3;
    }

    public S3Object load(String bucket, String key) {
        return s3.get(bucket, key);                // bucket explicit (declarative client baked it in)
    }
}
```

### AWS native — `S3Client` / `S3AsyncClient`

For AWS SDK features Kora's portable API doesn't cover (presigned URLs, bucket lifecycle, multi-region replication config, etc.):

```java
@Component
public final class PresignerService {
    private final software.amazon.awssdk.services.s3.S3Client s3;       // injected by AwsS3ClientModule

    public PresignerService(S3Client s3) { this.s3 = s3; }
}
```

For batched uploads, inject the tagged async client:

```java
public PresignerService(@Tag(software.amazon.awssdk.services.s3.model.MultipartUpload.class)
                        software.amazon.awssdk.services.s3.S3AsyncClient uploader) { ... }
```

The `@Tag` value is the AWS SDK's own `MultipartUpload` model class — Kora reuses it as the tag identity.

### MinIO native — `MinioClient` / `MinioAsyncClient`

Same idea: inject the MinIO SDK's clients directly when you need MinIO-specific features (server-side encryption configurations, lifecycle rules, etc.).

## Exceptions

| Exception | When thrown |
|-----------|-------------|
| `S3NotFoundException` | Key doesn't exist on get/delete (in strict modes) |
| `S3DeleteException` | Bulk delete partially failed (contains per-key results) |
| `S3Exception` | Base class for other S3-related failures |

All in `ru.tinkoff.kora.s3.client.*`. Map to your domain in a global error handler (see `kora-server/references/error-handling.md`).

## What's in `references/`

- `s3-client.md` — full configuration for both implementations, all declarative-annotation parameters, `S3Body` factory matrix, response formats.

## What's in `assets/`

- `DocumentsClient.java.template` — declarative client with all four operation types.
- `DocumentsClient.kt.template` — Kotlin equivalent.
- `AwsNativeUsage.java.template` — injecting `S3Client` directly for SDK-specific features.
- `s3client.conf.snippet` — drop-in HOCON for both AWS and MinIO.

## Common pitfalls

- **Wrong artifact group.** It's `ru.tinkoff.kora.experimental:s3-client-aws`, not `ru.tinkoff.kora:s3-client-aws`. The `experimental` segment is intentional and reflects the module's status.
- **Forgetting an HTTP client module for AWS.** AWS SDK needs an HTTP transport — Kora doesn't provide one by default. Plug `AsyncHttpClientModule` (or any other `kora-client` module) alongside `AwsS3ClientModule`. MinIO can auto-create one.
- **Key template doesn't include every method arg.** Compile error. `@S3.Get("prefix-{a}") void m(String a, String b)` is invalid; either use both args in the template or move `b` out.
- **Multi-key get with a template.** Mutually exclusive. Pick one.
- **`addressStyle = "VIRTUAL_HOSTED"` against MinIO without proper DNS.** Defaults to `PATH` for a reason. Stick with `PATH` for MinIO, Ceph, and other S3-compatible servers that don't have virtual-host-style DNS configured.
- **Uploading large files with `ofBytes(...)`.** Loads everything into memory. Use `ofInputStreamUnbound` or `ofPublisher` for files larger than a few MiB.
- **`bucket` not set on a `@S3.Client`.** Required — startup fails. Externalize via env var (`s3client.documents.bucket = ${DOCUMENTS_BUCKET}`).
- **Bulk delete that throws on first miss.** S3's bulk delete is best-effort by spec. `S3DeleteException` aggregates per-key results — handle it explicitly when you need to know which keys failed.
- **Native `S3Client` injection without `AwsS3ClientModule`.** The components are registered by the module, not the framework — make sure the right module is plugged into `@KoraApp`.

## AGENTS.md alignment

- Declarative `@S3.Client` interfaces — AGENTS.md "Use Kora-specific annotations" extended to storage.
- All credentials externalized via env vars (`s3client.url`, `accessKey`, `secretKey`) — AGENTS.md "environment variables for all credentials".
- Telemetry on by default (`s3.client.duration`, `s3.kora.client.duration`, tracing spans) — AGENTS.md "observability from day one".
- Resilience: wrap declarative-client methods in a `@Component` facade and layer `@CircuitBreaker` / `@Retry` from `kora-aop` for S3 calls on hot paths.

---

## Common Pitfalls

- **Missing `@S3.Client`** → interface not recognized as S3 client without annotation.
- **Wrong S3Body factory** → use `ofInputStreamUnbound` for unknown size; `ofBytes` for small payloads.
- **Missing bucket config** → `s3client.bucket` required unless hardcoded in annotation.
- **Multipart upload not triggered** → unknown length + `ofPublisher`/`ofInputStreamUnbound` required.
- **Experimental module** → API may change; artifact is `ru.tinkoff.kora.experimental:s3-client-*`.
