# `s3-client-kora` — the declarative S3 client (Kora 2.0)

Artifact **`io.koraframework.experimental:s3-client-kora`** · module
`io.koraframework.s3.client.kora.KoraS3ClientModule` · processor bundled in
`io.koraframework:annotation-processors` / `io.koraframework:symbol-processors`.

This artifact contains the `@S3` annotations, the runtime `S3Client`, request/response models and
the S3 telemetry. It talks S3 over **Kora's own HTTP client** — it does not use, and does not
depend on, the AWS SDK. For the AWS SDK wrapper see [s3-client-aws.md](s3-client-aws.md).

`experimental` is part of the **group**, not a suffix on the artifact name:
`io.koraframework.experimental:s3-client-kora`.

---

## 1. Wiring

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework.experimental:s3-client-kora"
    implementation "io.koraframework:http-client-ok"             // or -jdk / -apache
    implementation "io.koraframework:config-hocon"
}
```

```kotlin
dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

    implementation("io.koraframework.experimental:s3-client-kora")
    implementation("io.koraframework:http-client-jdk")
    implementation("io.koraframework:config-hocon")
}
```

`KoraS3ClientModule` provides:

| Component | Notes |
|---|---|
| `S3ClientTelemetryFactory` | `@DefaultComponent`; wraps optional `Tracer` / `MeterRegistry` |
| `S3FactoryModule` | `@FactoryModule`, constructed as `new S3FactoryModule("s3")` |
| `ConfigValueMapper<S3Credentials>` | `@DefaultComponent`; reads `credentials { accessKey, secretKey }` |

`S3FactoryModule` in turn supplies `S3HttpClientProvider` and `S3ClientFactory`, both declared
`@Tag(Tag.Factory.class) @DefaultComponent`. Inside a `@FactoryModule` that marker resolves to the
tag of the provider method — `defaultKoraS3Factory()` has none — so both land in the graph
**untagged**. It injects `io.koraframework.http.client.common.HttpClient`, which is why a Kora HTTP
client module is mandatory.

---

## 2. What the processor generates

For `@S3.Client interface S3FileClient` in package `com.example.storage`:

| Generated type | Role |
|---|---|
| `$S3FileClient_S3ClientImpl` | The implementation. Constructor: `(String configPath, S3ClientFactory clientFactory, S3ClientConfig[WithCredentials] clientConfig[, $S3FileClient_BucketsConfig bucketsConfig])` |
| `$S3FileClient_S3Module` | A `@Module` interface providing `clientConfig(...)`, `clientImpl(...)` and, when needed, `bucketsConfig(Config)` |
| `$S3FileClient_BucketsConfig` | Only when some `@S3.Bucket` names a config path. Public final fields `bucket_0`, `bucket_1`, … read at construction from `Config` |

Inject the **interface** (`S3FileClient`), never the generated class.

AOP is preserved: the generated impl uses `extendsKeepAop` / `overridingKeepAop`, so
`@Retryable`, `@CircuitBreakable`, `@Timeout` and friends can be placed on the `@S3.Client`
interface methods.

---

## 3. `@S3` annotations — complete surface

Package `io.koraframework.s3.client.kora.annotation`. `S3` itself has `@Target({})` — only the
nested annotations are usable.

### `@S3.Client` — on the interface

| Attribute | Type | Default | Meaning |
|---|---|---|---|
| `value` | `String` | `""` | Config path for `S3ClientConfig` / `S3ClientConfigWithCredentials`. **When empty, the interface's simple name is used as the config path** — `@S3.Client interface Uploads` reads config at `Uploads`. Always pass an explicit path. |
| `factoryTag` | `Class<?>` | `Tag.class` | Tag applied to the injected `S3ClientFactory`, so one client can be bound to a specific factory (several endpoints in one app). |

### `@S3.Bucket` — on the interface, a method, or a parameter

| Attribute | Type | Default | Meaning |
|---|---|---|---|
| `value` | `String` | `""` | Config path holding the bucket **name**. Leading `.` → relative to the `@S3.Client` path. No dot → absolute path. Required on the interface/method forms; omitted on a parameter. |

Resolution order per method — first match wins, build fails when none matches:

1. a parameter annotated `@S3.Bucket` (at most one per method; two → *"S3 bucket parameter is ambiguous"*);
2. `@S3.Bucket("path")` on the method;
3. `@S3.Bucket("path")` on the interface.

```java
@S3.Client("s3client.uploads")
@S3.Bucket(".bucket")                       // s3client.uploads.bucket
public interface Uploads {

    @S3.Get("files/{id}")
    byte[] fromDefaultBucket(String id);

    @S3.Get("files/{id}")
    @S3.Bucket("app.buckets.archive")       // absolute path — different bucket
    byte[] fromArchive(String id);

    @S3.Get
    byte[] fromRuntimeBucket(@S3.Bucket String bucket, String key);
}
```

`@S3.Bucket` with a config path and no value → *"S3 bucket config path is missing … @S3.Bucket was
used without a value"*.

### Operations

Each annotation has exactly one attribute, `String value() default ""` — a **key** (or, for
`@S3.List`, a **prefix**) that is either a constant or a `{param}` template.

| Annotation | Runtime call | Return types |
|---|---|---|
| `@S3.Get` | `getObject` | `GetObjectResult`, `byte[]` (`ByteArray`) — each optionally `@Nullable` |
| `@S3.Head` | `headObject` | `HeadObjectResult` — optionally `@Nullable` |
| `@S3.List` | `listObjectsV2` / `listObjectsV2Iterator` | `ListBucketResult`, `List<String>`, `List<ListBucketResult.ListBucketItem>`, `Iterator<String>`, `Iterator<ListBucketResult.ListBucketItem>` |
| `@S3.Put` | `putObject` (or `createMultipartUpload`+`uploadPart`+`completeMultipartUpload`) | `String` (ETag) or `void` |
| `@S3.Delete` | `deleteObject` | `void` only |

Exactly one operation annotation per method — zero → *"is not mapped to an S3 operation"*, two →
*"has more than one S3 operation annotation"*. `default` and `static` interface methods are
skipped and may hold plain Java/Kotlin code.

`@S3.List` has **no** `limit` and **no** `delimiter` attribute — both live on `ListObjectsArgs`.

---

## 4. Keys, prefixes and parameters

Parameters are split into three groups before key matching:

| Group | Excluded from the key | Types |
|---|---|---|
| Bucket | yes | any parameter annotated `@S3.Bucket` |
| Credentials | yes | `S3Credentials` |
| Request options | yes | `GetObjectArgs`, `HeadObjectArgs`, `PutObjectArgs`, `DeleteObjectArgs`, `ListObjectsArgs` |
| Body (`@S3.Put` only) | yes | `byte[]`, `ByteBuffer`, `InputStream`, `S3Client.ContentWriter` |
| **Key parameters** | **no** | everything else |

Rules, all enforced at compile time:

- `value` contains no `{` → used as a literal key/prefix. Legal with **zero** key parameters
  (`@S3.List("files/")` on a no-arg method).
- `value` contains `{name}` → `name` must match a key parameter; the generated key is a string
  concatenation, so non-`String` parameters use their `toString()`.
- A template that references **no** parameter while key parameters exist → error.
- No `value` and exactly one key parameter → key is `String.valueOf(param)`.
- No `value` and two or more key parameters → *"has N key parameters, but no key template"*.
- No `value` and no key parameters → *"has no object key"*.
- A key parameter that is a `Collection` or `Map` → error. **The declarative client is
  single-object; there is no multi-key get or batch delete.**
- Unclosed `{` → *"malformed key template … missing closing '}'"*.

```java
@S3.Get("users/{userId}/files/{fileId}")
byte[] get(String userId, UUID fileId);          // "users/" + userId + "/files/" + fileId
```

---

## 5. Response models

Package `io.koraframework.s3.client.kora.model.response`.

### `GetObjectResult`

```java
public interface GetObjectResult extends HttpClientResponse {
    record ContentRange(long firstPosition, long lastPosition, long completeLength) {}
    ContentRange contentRange();
}
```

Inherited from `HttpClientResponse` (which `extends Closeable`): `int code()`,
`HttpHeaders headers()`, `HttpBodyInput body()`, `void close()`. `HttpBodyInput` adds
`InputStream asInputStream()` on top of `HttpBody`'s `contentLength()` / `contentType()`.

**Always close it.** The generated `byte[]` variant does
`try (_rs; var _body = _rs.body(); var _is = _body.asInputStream()) { return _is.readAllBytes(); }`
— write the same thing when you take `GetObjectResult` yourself.

### `HeadObjectResult`

```java
public record HeadObjectResult(String bucket, String key, long size, HttpHeaders headers) {
    public String etag();                  // "ETag" header
    public String versionId();             // "x-amz-version-id"
    public @Nullable Instant lastModified();  // parsed from "Last-Modified", RFC 1123
}
```

`headers` are the HEAD response headers, so the derived accessors return the server's metadata.

### `ListBucketResult`

```java
public record ListBucketResult(@Nullable List<String> commonPrefixes,
                               int keyCount,
                               @Nullable String nextContinuationToken,
                               List<ListBucketItem> items) {

    public record ListBucketItem(String bucket, String key, String etag,
                                 String checksumType, String checksumAlgorithm,
                                 Instant lastModified, long size,
                                 @Nullable String storageClass,
                                 @Nullable ListBucketItemOwner owner) {}

    public record ListBucketItemOwner(String displayName, String id) {}
}
```

Pagination: pass `nextContinuationToken()` back through
`new ListObjectsArgs().setContinuationToken(...)`, or return an `Iterator<…>` and let the client
page lazily.

Also present: `UploadedPart`, `ListPartsResult`, `ListMultipartUploadsResult` — used by the
low-level multipart API on the runtime `S3Client`.

---

## 6. Nullability and missing objects

`@S3.Get` and `@S3.Head` pass a `required` flag to the runtime client, derived from the method's
nullability:

| Declaration | `required` | Object missing |
|---|---|---|
| `GetObjectResult get(String key)` | `true` | throws `S3ClientNoSuchKeyException` |
| `@Nullable GetObjectResult get(String key)` (Java) | `false` | returns `null` |
| `fun get(key: String): GetObjectResult?` (Kotlin) | `false` | returns `null` |

Java uses **JSpecify** `org.jspecify.annotations.Nullable`. Kotlin expresses it in the type — do
not carry JSpecify annotations into Kotlin.

JSpecify's `@Nullable` is `@Target(TYPE_USE)`, so **position matters** on an array return: a
nullable `byte[]` is written `byte @Nullable []`, not `@Nullable byte[]` (which annotates the
element type and is rejected). A nullable reference return is the ordinary
`@Nullable GetObjectResult`.

---

## 7. Upload bodies

Exactly one body parameter on `@S3.Put`; zero → *"has no upload body parameter"*, two → *"has N
upload body parameters"*.

| Body type | Generated behaviour |
|---|---|
| `byte[]` / `ByteArray` | `putObject(creds, bucket, key, args, data, 0, data.length)` |
| `ByteBuffer` | Uses the backing array when `hasArray()`, otherwise copies `remaining()` bytes, then `putObject(...)` |
| `InputStream` | Reads `upload.partSize` bytes. If the first read fills the buffer → `createMultipartUpload`, then `uploadPart` per chunk, then `completeMultipartUpload` (returns the final ETag). If the stream ended inside the first part → a single `putObject`. The stream is closed (try-with-resources); `IOException` is wrapped in `S3ClientUnknownException`. |
| `S3Client.ContentWriter` | `putObject(creds, bucket, key, args, writer)` — `aws-chunked` encoding in `upload.chunkSize` chunks |

```java
public interface ContentWriter extends Closeable {
    void write(OutputStream os) throws IOException;
    long length();
    default void close() throws IOException {}
}
```

There is no `S3Body` type and no `Flow.Publisher` body in Kora 2.0.

---

## 8. `*Args` — per-call request options

Package `io.koraframework.s3.client.kora.model.request`. Mutable classes with public fields and
chained `setX(...)` setters returning `this`. Adding one as a method parameter passes it straight
through; omit it and `null` is passed.

| Type | Notable fields |
|---|---|
| `ListObjectsArgs` | `prefix`, `delimiter`, `maxKeys`, `continuationToken`, `startAfter`, `fetchOwner`, `requestPayer`, `expectedBucketOwner`, `optionalObjectAttributes` |
| `GetObjectArgs` | `range` (`Range`), `versionId`, `partNumber`, `ifMatch`, `ifNoneMatch`, `ifModifiedSince`, `ifUnmodifiedSince`, `response*` overrides, `sseCustomerAlgorithm`, `sseCustomerKey`, `checksumMode`, `requestPayer`, `expectedBucketOwner` |
| `HeadObjectArgs` | same field set as `GetObjectArgs` |
| `PutObjectArgs` | `contentType`, `contentEncoding`, `contentDisposition`, `contentLanguage`, `cacheControl`, `expires`, `acl`, `grant*`, `storageClass`, `tagging`, `websiteRedirectLocation`, `serverSideEncryption`, `sseCustomerAlgorithm`, `sseCustomerKey`, `sseKmsKeyId`, `sseKmsEncryptionContext`, `bucketKeyEnabled`, `objectLockMode`, `objectLockRetainUntilDate`, `objectLockLegalHoldStatus`, `ifMatch`, `ifNoneMatch`, `requestPayer`, `expectedBucketOwner` |
| `DeleteObjectArgs` | `versionId`, `mfa`, `bypassGovernanceRetention`, `ifMatch`, `ifMatchLastModifiedTime`, `ifMatchSize`, `requestPayer`, `expectedBucketOwner` |

When a method takes a `ListObjectsArgs`, the annotation's prefix template is **not** applied —
set `prefix` on the args yourself.

### `Range`

`io.koraframework.s3.client.kora.model.Range` — a sealed interface with three factories:

| Factory | Header |
|---|---|
| `Range.fromTo(first, last)` | `bytes=first-last` |
| `Range.from(first)` | `bytes=first-` |
| `Range.last(n)` | `bytes=-n` |

---

## 9. Credentials

```java
public interface S3Credentials {
    String accessKey();
    String secretKey();
    static S3Credentials of(String accessKey, String secretKey);
}
```

A method may take an `S3Credentials` parameter; it overrides the configured credentials for that
call. At most one per method.

This choice changes the generated config type:

| Every method takes `S3Credentials` | Generated config type | `credentials { … }` in config |
|---|---|---|
| yes | `S3ClientConfig` | not read |
| no (any method without one) | `S3ClientConfigWithCredentials` | **required** |

---

## 10. Configuration — `S3ClientConfig`

Read from the path given by `@S3.Client(value)`.

| Key | Type | Default | Notes |
|---|---|---|---|
| `endpoint` | `String` | **required** | Was `url` in Kora 1.x |
| `region` | `String` | `"aws-global"` | |
| `addressStyle` | `PATH` \| `VIRTUAL_HOSTED` | `PATH` | Keep `PATH` for self-hosted servers (RustFS, SeaweedFS, LocalStack, MinIO, Ceph) |
| `requestTimeout` | `Duration` | `45s` | |
| `credentials.accessKey` | `String` | **required*** | *unless every method takes `S3Credentials` |
| `credentials.secretKey` | `String` | **required*** | |
| `upload.partSize` | `Size` | `5MiB` | Multipart part size; S3 requires 5 MiB – 5 GiB (last part exempt) |
| `upload.chunkSize` | `Size` | `64KiB` | `aws-chunked` chunk size for `ContentWriter`; S3 minimum 8 KiB |
| `upload.singlePartUploadLimit` | `Size` | `100MiB` | |
| `telemetry.logging.enabled` | `boolean` | **`false`** | |
| `telemetry.metrics.enabled` | `boolean` | **`false`** | |
| `telemetry.metrics.slo` | `Duration[]` | framework default buckets | |
| `telemetry.tracing.enabled` | `boolean` | `true` | |

`Size` literals are `<number><unit>` with a case-insensitive unit (`B`, `KiB`, `MiB`, `GiB`, …)
or a bare byte count: `partSize = "16MiB"`, `chunkSize = 65536`.

The bucket is **not** a key of this config object — it is read separately through `@S3.Bucket`.
Nothing stops you from putting it in the same block (`s3client.uploads.bucket`) and pointing
`@S3.Bucket(".bucket")` at it; that is the pattern the migrated examples use.

```hocon
s3client.uploads {
  endpoint = ${S3_URL}
  region   = "us-east-1"
  region   = ${?S3_REGION}
  bucket   = ${S3_BUCKET}

  addressStyle   = "PATH"
  requestTimeout = "45s"

  credentials {
    accessKey = ${S3_ACCESS_KEY}
    secretKey = ${S3_SECRET_KEY}
  }

  upload {
    partSize              = "16MiB"
    chunkSize             = "64KiB"
    singlePartUploadLimit = "100MiB"
  }

  telemetry {
    logging.enabled = true
    metrics.enabled = true
    tracing.enabled = true
  }
}
```

### Several clients, several endpoints

Each `@S3.Client` reads its own config path, so two interfaces pointed at two paths already give
two independently configured clients over the shared `S3ClientFactory`. To bind a client to a
*different* factory (its own HTTP client, say), declare a tagged `@FactoryModule` method returning
`S3FactoryModule` and name that tag in `@S3.Client(factoryTag = MyTag.class)`.

---

## 11. The runtime `S3Client`

`io.koraframework.s3.client.kora.S3Client` — synchronous, every method takes `S3Credentials` and
an explicit `bucket`. Use it when the declarative contract does not fit; note it is what the
generated implementations call.

| Method | Returns |
|---|---|
| `headObject(creds, bucket, key, args, required)` | `@Nullable HeadObjectResult` (+ convenience overloads, `headObjectOptional`) |
| `getObject(creds, bucket, key, args, required)` | `@Nullable GetObjectResult` (+ overloads, `getObjectOptional`) |
| `putObject(creds, bucket, key, args, data, off, len)` | `String` ETag — hashes and sends exactly `data[off, off + len)` |
| `putObject(creds, bucket, key, args, contentWriter)` | `String` ETag — streamed `aws-chunked`; `args` headers and content type are applied |
| `deleteObject(creds, bucket, key, args)` | `void` |
| **`deleteObjects(creds, bucket, List<String> keys)`** | `void` — batch delete (`POST /<bucket>?delete`), up to 1000 keys; throws `S3ClientDeleteException` with per-key errors |
| `listObjectsV2(creds, bucket, args)` | `ListBucketResult` |
| `listObjectsV2Iterator(creds, bucket, args)` | `Iterator<ListBucketResult.ListBucketItem>` (lazy paging) |
| `createMultipartUpload` / `uploadPart` / `listParts` / `completeMultipartUpload` / `abortMultipartUpload` / `listMultipartUploads` | low-level multipart API |

`deleteObjects` is the batch delete that `@S3.Delete` cannot express.

`S3Client` is not itself a graph component — the graph holds an `S3ClientFactory`. Because
`KoraS3ClientModule#defaultKoraS3Factory()` carries no `@Tag`, the `@Tag(Tag.Factory.class)` inside
`S3FactoryModule` resolves to *no tag*, so `S3ClientFactory` injects untagged:

```java
@Component
public final class BulkDeleter {

    private final S3Client s3;

    public BulkDeleter(S3ClientFactory factory, S3ClientConfigWithCredentials config) {
        this.s3 = factory.create(config);
    }

    public void purge(S3Credentials creds, String bucket, List<String> keys) {
        s3.deleteObjects(creds, bucket, keys);      // throws S3ClientDeleteException on partial failure
    }
}
```

---

## 12. Exceptions

Package `io.koraframework.s3.client.kora.exception`.

```
RuntimeException
└── S3ClientException                       abstract
    ├── S3ClientUnknownException            final; wraps IOException from body/stream handling
    ├── S3ClientDeleteException             getErrors() → List<DeleteObjectsResult.Error>
    └── S3ClientResponseException           getHttpCode()
        └── S3ClientErrorException          getErrorCode(), getErrorMessage(), @Nullable getRequestId()
            └── S3ClientNoSuchKeyException  404 NoSuchKey
```

| Kora 1.x | Kora 2.0 |
|---|---|
| `S3Exception` | `S3ClientException` |
| `S3NotFoundException` | `S3ClientNoSuchKeyException` |
| `S3DeleteException` | `S3ClientDeleteException` |

---

## 13. Telemetry

| Signal | Detail |
|---|---|
| Metrics | Micrometer `Timer` **`rpc.client.call.duration`**, tags `rpc.system.name=s3`, `rpc.method`, `aws.s3.bucket`, `error.type`, `system.config`, `system.name.simple`, `system.name.canonical` |
| Tracing | OpenTelemetry span per operation, same attributes |
| Logging | SLF4J logger named after the `@S3.Client` **interface's canonical name**. `DEBUG` for "S3Client request started" / "S3Client response received", `WARN` on failure with `exceptionType` |

Turn logging on for one client:

```hocon
s3client.uploads.telemetry.logging.enabled = true
logging.levels { "com.example.storage.S3FileClient" = "DEBUG" }
```

---

## Source of truth

- Framework source, tag `2.0.0.RC2`:
  [experimental/s3-client-kora](https://github.com/kora-projects/kora/tree/2.0.0.RC2/experimental/s3-client-kora) ·
  [s3-client-annotation-processor](https://github.com/kora-projects/kora/tree/2.0.0.RC2/experimental/s3-client-annotation-processor) ·
  [s3-client-symbol-processor](https://github.com/kora-projects/kora/tree/2.0.0.RC2/experimental/s3-client-symbol-processor)
- Migrated examples, branch `migration/2.0`:
  [kora-java-s3-client-kora](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/java/kora-java-s3-client-kora) ·
  [kora-kotlin-s3-client-kora](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/kotlin/kora-kotlin-s3-client-kora) ·
  [kora-java-guide-s3-app](https://github.com/kora-projects/kora-examples/tree/migration/2.0/guides/java/kora-java-guide-s3-app)
- [Amazon S3 API reference](https://docs.aws.amazon.com/AmazonS3/latest/API/Welcome.html) for the
  wire-level semantics these models mirror.
