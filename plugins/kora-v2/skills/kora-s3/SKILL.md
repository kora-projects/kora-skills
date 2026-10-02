---
name: kora-s3
description: "S3 object storage in Kora 2.0 — two independent artifacts: the declarative client io.koraframework.experimental:s3-client-kora (@S3.Client, @S3.Bucket, @S3.Get/@S3.Head/@S3.List/@S3.Put/@S3.Delete returning GetObjectResult/HeadObjectResult/ListBucketResult) and the AWS SDK wrapper io.koraframework:s3-client-aws, which hands software.amazon.awssdk.services.s3.S3Client to the graph. Both need a Kora HTTP client module. Use when adding S3-compatible storage (AWS S3, RustFS, SeaweedFS, LocalStack, MinIO, Ceph) to a Kora service, porting a Kora 1.x @S3.Client, or debugging \"package S3 does not exist\", \"S3 operation has no bucket source\", or \"S3Client wasn't found in graph\"."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora S3

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Declarative client** | `io.koraframework.experimental:s3-client-kora` — `@S3` annotations, `S3Client`, models. **Note the `.experimental` group.** |
| **AWS SDK wrapper** | `io.koraframework:s3-client-aws` — `AwsS3ClientModule`, config, telemetry. Publishes `software.amazon.awssdk.services.s3.S3Client`. **Not** under `experimental`. |
| **BOM** | `io.koraframework:kora-bom` (`koraVersion=2.0.0.RC2`, plain `mavenCentral()`) |
| **Processor** | `annotationProcessor "io.koraframework:annotation-processors"` (Java) · `ksp("io.koraframework:symbol-processors")` (Kotlin) — both aggregates already contain the S3 processor |
| **Prerequisite** | A Kora HTTP client module — `http-client-ok`, `http-client-jdk` or `http-client-apache`. Required by **both** artifacts. |
| **AWS SDK** | `software.amazon.awssdk:s3` `2.55.10`, pulled transitively by `s3-client-aws` |

S3 is the most heavily redesigned area in Kora 2.0. Nearly every 1.x shape is gone: there is no
`s3-client-minio` artifact, no `S3KoraClient`, no `S3Body`, no `S3Object`, no batch delete on the
declarative client, and no async/reactive variants. Jump to [§8](#8-migrating-from-kora-1x) if you
are porting 1.x code.

---

## 1. Pick the artifact

Two artifacts, easily confused. They are **independent** — neither depends on the other, and each
works alone.

| You need | Artifact | Module on `@KoraApp` | You program against |
|---|---|---|---|
| Typed interfaces for get / head / list / put / delete on known buckets | `io.koraframework.experimental:s3-client-kora` | `KoraS3ClientModule` | `@S3.Client` interfaces you declare |
| Bucket administration, presigned URLs, versioning, ACL, lifecycle, batch delete, anything else in the S3 API | `io.koraframework:s3-client-aws` | `AwsS3ClientModule` | The AWS SDK `S3Client` directly |
| Both of the above in one service | both artifacts | both modules | both |

```groovy
// Java — declarative client only
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework.experimental:s3-client-kora"
    implementation "io.koraframework:http-client-ok"          // required transport
}
```

```kotlin
// Kotlin — AWS SDK wrapper only
dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

    implementation("io.koraframework:s3-client-aws")
    implementation("io.koraframework:http-client-jdk")        // required transport
}
```

**`s3-client-minio` does not exist in Kora 2.0.** It is absent from the framework's
`settings.gradle` and there is no such directory in the source tree. MinIO is still a usable
S3-compatible **server** — like AWS S3, RustFS, SeaweedFS, LocalStack or Ceph (see
[§5](#s3-compatible-servers) and [§7](#7-testing)) — but there is no Kora module built on the MinIO
SDK any more. The replacement for the 1.x MinIO client is `s3-client-kora`, which speaks S3 over
Kora's own HTTP client.

> **"Transport" means a Kora HTTP client module, not the other S3 artifact.** Both
> `S3FactoryModule` and `AwsS3ClientFactoryModule` inject `io.koraframework.http.client.common.HttpClient`;
> `s3-client-aws` even excludes the AWS SDK's own `apache-client` and `netty-nio-client` so that all
> traffic goes through Kora's transport. Adding `s3-client-aws` to a project that only wants `@S3`
> interfaces gains you nothing.

**Wrong artifact →** `package S3 does not exist`,
`package io.koraframework.s3.client.kora.annotation does not exist`, or
`package io.koraframework.s3.client.kora.model.response does not exist`.

---

## 2. Declarative client — `s3-client-kora`

### Canonical shape

```java
package com.example.storage;

import io.koraframework.s3.client.kora.annotation.S3;
import io.koraframework.s3.client.kora.model.response.GetObjectResult;
import io.koraframework.s3.client.kora.model.response.HeadObjectResult;
import io.koraframework.s3.client.kora.model.response.ListBucketResult;

@S3.Client("s3client.uploads")   // config path for S3ClientConfigWithCredentials
@S3.Bucket(".bucket")            // leading dot ⇒ s3client.uploads.bucket
public interface S3FileClient {

    @S3.Put("files/{fileId}")
    String uploadFile(String fileId, byte[] body);      // returns the ETag

    @S3.Get("files/{fileId}")
    GetObjectResult downloadFile(String fileId);

    @S3.Head("files/{fileId}")
    HeadObjectResult fileMeta(String fileId);

    @S3.List("files/")
    ListBucketResult listFiles();

    @S3.Delete("files/{fileId}")
    void deleteFile(String fileId);
}
```

```java
@KoraApp
public interface Application extends
        HoconConfigModule, LogbackModule,
        KoraS3ClientModule,          // io.koraframework.s3.client.kora
        OkHttpClientModule {         // any Kora HTTP client module

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

```hocon
s3client.uploads {
  endpoint = ${S3_URL}          # required; was `url` in 1.x
  bucket   = ${S3_BUCKET}       # read via @S3.Bucket(".bucket"), not by the client itself
  credentials {
    accessKey = ${S3_ACCESS_KEY}
    secretKey = ${S3_SECRET_KEY}
  }
}
```

The processor generates `$S3FileClient_S3ClientImpl`, a `@Module` interface
`$S3FileClient_S3Module` that provides it, and — when any `@S3.Bucket` names a config path —
`$S3FileClient_BucketsConfig`. Inject `S3FileClient` like any component.

### Operation annotations

All nested in `io.koraframework.s3.client.kora.annotation.S3`. Every non-`default`, non-`static`
method must carry **exactly one** operation annotation.

| Annotation | Attributes | Allowed return types |
|---|---|---|
| `@S3.Client` | `value` (config path, defaults to the interface simple name), `factoryTag` (tag for the injected `S3ClientFactory`) | — (on the interface) |
| `@S3.Bucket` | `value` (config path; leading `.` = relative to `@S3.Client`) | — (on the interface, a method, or a parameter) |
| `@S3.Get` | `value` (key constant or `{param}` template) | `GetObjectResult`, `byte[]` — each also `@Nullable` |
| `@S3.Head` | `value` | `HeadObjectResult`, also `@Nullable` |
| `@S3.List` | `value` (prefix constant or template) | `ListBucketResult`, `List<String>`, `List<ListBucketResult.ListBucketItem>`, `Iterator<String>`, `Iterator<ListBucketResult.ListBucketItem>` |
| `@S3.Put` | `value` | `String` (the ETag) or `void` |
| `@S3.Delete` | `value` | `void` only |

There is **no** `limit` and **no** `delimiter` attribute on `@S3.List` — both move to
`ListObjectsArgs` (see below). `@S3.Get` no longer serves metadata: use `@S3.Head`.

### Return-type semantics

- **`GetObjectResult extends HttpClientResponse`**, so it is `Closeable` and carries `code()`,
  `headers()`, `body()` and `contentRange()`. Read the payload through
  `result.body().asInputStream()` and **close both**:

  ```java
  try (var obj = client.downloadFile(id); var body = obj.body().asInputStream()) {
      return body.readAllBytes();
  }
  ```
  Returning `byte[]` instead makes the generated code do exactly that for you.
- **`HeadObjectResult`** is a record — `bucket()`, `key()`, `size()`, `headers()` — plus derived
  `etag()`, `versionId()` and `@Nullable lastModified()`.
- **`ListBucketResult`** is a record — `@Nullable commonPrefixes()`, `keyCount()`,
  `@Nullable nextContinuationToken()`, `items()`. Each `ListBucketItem` has `bucket()`, `key()`,
  `etag()`, `checksumType()`, `checksumAlgorithm()`, `lastModified()`, `size()`,
  `@Nullable storageClass()`, `@Nullable owner()`.
- An `Iterator<…>` return **pages lazily** — the client fetches the next page on demand.

### Missing objects: `@Nullable` decides

`@S3.Get` and `@S3.Head` on a **non-nullable** return throw
`S3ClientNoSuchKeyException` when the object is absent. Mark the method `@Nullable` (Java) or
return a nullable type (Kotlin) and it returns `null` instead.

```java
@S3.Head("files/{fileId}")
@Nullable
HeadObjectResult fileMetaOrNull(String fileId);
```

```kotlin
@S3.Head("files/{fileId}")
fun fileMetaOrNull(fileId: String): HeadObjectResult?
```

### Where the bucket comes from

The bucket is **never** taken from the client config automatically. The processor resolves it in
this order, and fails the build if none applies:

1. a method parameter annotated `@S3.Bucket` — runtime bucket, at most one per method;
2. `@S3.Bucket("path")` on the **method**;
3. `@S3.Bucket("path")` on the **interface**.

For 2 and 3 the value is a **config path**: a leading dot makes it relative to the `@S3.Client`
path (`@S3.Client("s3client.uploads")` + `@S3.Bucket(".bucket")` → `s3client.uploads.bucket`),
no dot makes it absolute (`@S3.Bucket("app.buckets.uploads")`).

```java
@S3.Client("s3client.uploads")
public interface MultiBucketClient {

    @S3.Get                                      // bucket chosen at call time
    byte[] fromAnyBucket(@S3.Bucket String bucket, String key);

    @S3.Get("files/{key}")
    @S3.Bucket(".archiveBucket")                 // s3client.uploads.archiveBucket
    byte[] fromArchive(String key);
}
```

Missing bucket source → `S3 operation '…' has no bucket source.` at compile time.

### Keys and key templates

- `@S3.Get("constant-key")` — a literal with no `{}` is used verbatim.
- `@S3.Get("files/{fileId}")` — `{name}` substitutes the method parameter of that name.
- No `value` and exactly one key parameter → the key is `String.valueOf(param)`.
- No `value` and more than one key parameter → compile error; add a template.
- A collection parameter can never be a key — the declarative client is strictly single-object.

Parameters typed `S3Credentials`, one of the `*Args` types, or a body type are **excluded** from
key-template matching, so they need no placeholder.

### Upload bodies

Exactly one body parameter, of one of these types:

| Type | Behaviour |
|---|---|
| `byte[]` / Kotlin `ByteArray` | Single `PutObject` |
| `java.nio.ByteBuffer` | Single `PutObject` (copied when not array-backed) |
| `java.io.InputStream` | **Automatic multipart upload** in `upload.partSize` chunks (default 5 MiB); falls back to a single `PutObject` when the stream ends inside the first part |
| `S3Client.ContentWriter` | `write(OutputStream)` + `length()` callback, uploaded with `aws-chunked` encoding in `upload.chunkSize` chunks (default 64 KiB) |

There is no `S3Body` type in 2.0 and no publisher/reactive body.

### Per-call request options

Add a parameter of the matching `*Args` type — `GetObjectArgs`, `HeadObjectArgs`,
`PutObjectArgs`, `DeleteObjectArgs`, `ListObjectsArgs` — and the generated code forwards it.
These are mutable classes with public fields and chained setters.

```java
@S3.List
ListBucketResult listPage(ListObjectsArgs args);      // no prefix template needed with Args

var page = client.listPage(new ListObjectsArgs()
    .setPrefix("files/")
    .setDelimiter("/")
    .setMaxKeys(50)                                    // replaces 1.x @S3.List(limit = 50)
    .setContinuationToken(previous.nextContinuationToken()));
```

`GetObjectArgs`/`HeadObjectArgs` carry `range` (`io.koraframework.s3.client.kora.model.Range` —
`Range.fromTo(a, b)`, `Range.from(a)`, `Range.last(n)`), `versionId`, the conditional headers and
SSE-C fields. `PutObjectArgs` carries `contentType`, `acl`, `storageClass`, `tagging`,
object-lock and SSE fields.

### Per-call credentials

Give a method an `S3Credentials` parameter and it overrides the configured credentials for that
call. If **every** method has one, the generated config type is `S3ClientConfig` and the
`credentials { … }` block is not required; if **any** method lacks one, the config type is
`S3ClientConfigWithCredentials` and `credentials` becomes mandatory.

### Batch delete is not available declaratively

`@S3.Delete` generates `S3Client#deleteObject` only, and its return type must be `void`. A method
like `void deleteObjects(List<String> keys)` does **not** compile — the collection parameter is
rejected as a key. The runtime `S3Client#deleteObjects(credentials, bucket, keys)` exists, and the
AWS SDK has `deleteObjects(...)`; use one of those (see [§3](#3-aws-sdk-wrapper--s3-client-aws)).

---

## 3. AWS SDK wrapper — `s3-client-aws`

This artifact contains **no `@S3` annotation and no models**. It configures and publishes the AWS
SDK's own `software.amazon.awssdk.services.s3.S3Client`, running over Kora's HTTP client and
Kora's telemetry.

```java
@Component
public class AwsS3Service {

    private final S3Client s3Client;     // software.amazon.awssdk.services.s3.S3Client
    private final String bucket;

    public AwsS3Service(S3Client s3Client, S3Config config) {
        this.s3Client = s3Client;
        this.bucket = config.bucket();
    }

    public PutObjectResponse put(String key, byte[] value) {
        return s3Client.putObject(r -> r.bucket(bucket).key(key), RequestBody.fromBytes(value));
    }

    public DeleteObjectsResponse deleteMany(List<String> keys) {
        var ids = keys.stream().map(k -> ObjectIdentifier.builder().key(k).build()).toList();
        return s3Client.deleteObjects(r -> r.bucket(bucket).delete(d -> d.objects(ids)));
    }
}
```

```hocon
s3client.aws {
  url = ${S3_URL}
  credentials {
    accessKey = ${S3_ACCESS_KEY}
    secretKey = ${S3_SECRET_KEY}
  }
}
```

The config path `s3client.aws` is fixed by `AwsS3ClientModule` and is unrelated to any
`@S3.Client` path. The AWS wrapper does **not** know about buckets — hold the bucket name in your
own `@ConfigSource` interface.

> **`@Tag(Tag.Factory.class)` inside `AwsS3ClientFactoryModule` is not a problem.** Inside a
> `@FactoryModule`, `@Tag.Factory` resolves to the tag of the factory-module **method itself**, and
> `AwsS3ClientModule#awsS3ClientFactoryModule()` carries no tag — so `S3Client` lands in the graph
> untagged and injects plainly. That substitution is what lets you declare several factory-module
> methods with different tags and get several independently configured clients.

---

## 4. Using both artifacts together

Bucket administration (create, check existence) is not part of the `@S3` contract, so an
application that needs it pulls in both artifacts and extends both modules.

```groovy
implementation "io.koraframework:s3-client-aws"
implementation "io.koraframework.experimental:s3-client-kora"
implementation "io.koraframework:http-client-ok"
```

```java
@KoraApp
public interface Application extends
        HoconConfigModule, JsonModule, LogbackModule, OkHttpClientModule,
        AwsS3ClientModule,          // bucket administration via the AWS SDK
        KoraS3ClientModule,         // the declarative @S3 client
        UndertowPublicHttpServerModule { }
```

The two config sections are independent: `s3client.aws` for the SDK wrapper, and whatever path
`@S3.Client(...)` names for the declarative client.

### A bucket initialiser must be `@Root`

`@S3.Bucket` puts the bucket name into a **generated class**, not into an injectable component, so
code that needs the name separately reads the same config path itself. And a `Lifecycle` component
that only prepares external state has no dependants — **the graph prunes it**, taking the
`S3Client` it pulled along with it. The failure surfaces as a misleading

```
interface software.amazon.awssdk.services.s3.S3Client wasn't found in graph
```

Annotate it `@Root`:

```java
@Root
@Component
public final class S3BucketInitializer implements Lifecycle {

    private final S3Client s3Client;
    private final S3UploadsConfig config;

    public S3BucketInitializer(S3Client s3Client, S3UploadsConfig config) { … }

    @Override
    public void init() {
        var bucket = config.bucket();
        try {
            s3Client.headBucket(HeadBucketRequest.builder().bucket(bucket).build());
        } catch (NoSuchBucketException e) {
            s3Client.createBucket(CreateBucketRequest.builder().bucket(bucket).build());
        }
    }

    @Override
    public void release() {}
}
```

See [assets/S3BucketInitializer.java.template](assets/S3BucketInitializer.java.template) and its
Kotlin twin.

---

## 5. Configuration

Full key lists in [references/s3-client-kora.md](references/s3-client-kora.md) and
[references/s3-client-aws.md](references/s3-client-aws.md). The essentials:

| | Declarative client (`@S3.Client("<path>")`) | AWS SDK wrapper (`s3client.aws`) |
|---|---|---|
| Endpoint | **`endpoint`** (required) | **`url`** (required) |
| Credentials | `credentials { accessKey, secretKey }` | `credentials { accessKey, secretKey }` |
| Region | `region` — default `"aws-global"` | `region` — default `"aws-global"` |
| Address style | `addressStyle` — `PATH` (default) / `VIRTUAL_HOSTED` | same |
| Timeout | `requestTimeout` — default `45s` | same |
| Upload tuning | `upload { partSize = 5MiB, chunkSize = 64KiB, singlePartUploadLimit = 100MiB }` | — (no `upload` section) |
| Checksums | — | `checksumCalculationRequest`, `checksumValidationResponse` — `WHEN_REQUIRED` (default) / `WHEN_SUPPORTED`; `chunkedEncodingEnabled` (default `true`) |
| Telemetry | `telemetry { logging, metrics, tracing }` | same |

`endpoint` vs `url` is a real difference between the two modules, not a typo — using `url` under a
`@S3.Client` path fails startup with `Config expected value, but got null at path …endpoint`.

**Telemetry defaults bite:** `logging.enabled` and `metrics.enabled` default to **`false`**;
`tracing.enabled` defaults to `true`. Turn the first two on explicitly if you expect them.

```hocon
s3client.uploads.telemetry {
  logging.enabled = true      # DEBUG on the @S3.Client interface's own logger
  metrics.enabled = true      # rpc.client.call.duration, rpc.system.name=s3
}
```

Both modules emit the timer **`rpc.client.call.duration`** with `rpc.system.name=s3` — the same
value for the declarative client and the SDK wrapper. Other tags: `rpc.method`, `aws.s3.bucket`,
`error.type`, `system.config`, `system.name.simple`, `system.name.canonical`; tell clients apart by
`system.config` / `system.name.*`.

### S3-compatible servers

The declarative client signs every request itself with AWS Signature V4 and is verified by the
framework's own suite against **RustFS, SeaweedFS and LocalStack 4.14.0** (it does not rely on a
lenient server). What that guarantees on a strict server:

- Object keys and `ListObjectsArgs` values (`prefix`, `delimiter`, `startAfter`,
  `continuationToken`) are percent-encoded per SigV4 and the raw path is signed, so keys with
  spaces, `+`, `%`, `*` or non-ASCII characters work.
- Every header the client sends is signed (including multipart checksum headers and headers from
  `*Args`).
- `S3Client#deleteObjects` posts `?delete` to the bucket root; the per-key result keeps
  `VersionId` and keys containing XML entities.
- `HeadObjectResult.headers()` carries the response headers, so `etag()`, `versionId()` and
  `lastModified()` are populated.
- `putObject` / `uploadPart` with `(data, off, len)` hash and send exactly that slice; a
  `ContentWriter` put honours `PutObjectArgs` (including its content type).

Server-specific notes: keep `addressStyle = PATH` (the default) unless the server has wildcard DNS
for virtual-hosted buckets; LocalStack Community accepts any credentials (`test`/`test`), so it
cannot test authorization failures; `localstack/localstack:4.14.0` is the last image that starts
without `LOCALSTACK_AUTH_TOKEN`.

---

## 6. Exceptions

All in `io.koraframework.s3.client.kora.exception`, thrown by the **declarative client** and the
runtime `S3Client`. The AWS SDK wrapper throws AWS SDK exceptions
(`software.amazon.awssdk.services.s3.model.*`) instead.

```
RuntimeException
└── S3ClientException                       (abstract base)
    ├── S3ClientUnknownException            wraps IOException from body/stream handling
    ├── S3ClientDeleteException             batch delete — getErrors() has the per-key failures
    └── S3ClientResponseException           getHttpCode()
        └── S3ClientErrorException          getErrorCode(), getErrorMessage(), getRequestId()
            └── S3ClientNoSuchKeyException  404 on get/head of a non-nullable method
```

`S3NotFoundException` from 1.x is now `S3ClientNoSuchKeyException`. Map it in a global error
handler — see [kora-http-server](../kora-http-server/SKILL.md).

---

## 7. Testing

Test against a real S3-compatible **server** in a Testcontainer — it is the server, not a Kora
module. The migrated examples use MinIO through `testcontainers-extensions-minio`, shown below; the
framework's own suite uses RustFS, SeaweedFS and LocalStack in a plain `GenericContainer` (see the
LocalStack variant after the example), because MinIO no longer publishes reliable images.

```groovy
testImplementation "io.koraframework:test-junit5"
testImplementation "org.testcontainers:junit-jupiter:1.21.4"
testImplementation "io.goodforgod:testcontainers-extensions-minio:0.15.0"
```

```java
@TestcontainersMinio(
        mode = ContainerMode.PER_RUN,
        bucket = @Bucket(value = "uploads", create = Bucket.Mode.PER_METHOD, drop = Bucket.Mode.PER_METHOD))
@KoraAppTest(Application.class)
class S3FileClientTest implements KoraAppTestConfigModifier {

    @ConnectionMinio
    private MinioConnection minio;

    @TestComponent
    private S3FileClient client;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification
                .ofSystemProperty("S3_URL", minio.params().uri().toString())
                .withSystemProperty("S3_ACCESS_KEY", minio.params().accessKey())
                .withSystemProperty("S3_SECRET_KEY", minio.params().secretKey())
                .withSystemProperty("S3_BUCKET", "uploads");
    }

    @Test
    void putGetDelete() throws Exception {
        var body = "hello".getBytes(StandardCharsets.UTF_8);
        client.uploadFile("f1", body);

        try (var obj = client.downloadFile("f1"); var is = obj.body().asInputStream()) {
            assertArrayEquals(body, is.readAllBytes());
        }

        client.deleteFile("f1");
        assertThrows(S3ClientNoSuchKeyException.class, () -> client.downloadFile("f1"));
    }
}
```

Same wiring with LocalStack in a plain `GenericContainer` (`org.testcontainers:testcontainers`),
as the framework's `LocalStackS3ClientTest` does — create the bucket with `awslocal`:

```java
static GenericContainer<?> localstack = new GenericContainer<>(DockerImageName.parse("localstack/localstack:4.14.0"))
        .withEnv("SERVICES", "s3")
        .withExposedPorts(4566)
        .waitingFor(Wait.forHttp("/_localstack/health").forPort(4566).forStatusCode(200));

@BeforeAll
static void startS3() throws Exception {
    localstack.start();
    localstack.execInContainer("awslocal", "s3", "mb", "s3://uploads");
}

@Override
public KoraConfigModification config() {
    return KoraConfigModification
            .ofSystemProperty("S3_URL", "http://" + localstack.getHost() + ":" + localstack.getMappedPort(4566))
            .withSystemProperty("S3_ACCESS_KEY", "test")
            .withSystemProperty("S3_SECRET_KEY", "test")
            .withSystemProperty("S3_BUCKET", "uploads");
}
```

Keep `addressStyle = PATH` (the default) against self-hosted servers (RustFS, SeaweedFS,
LocalStack, MinIO, Ceph) — virtual-hosted style needs wildcard DNS they usually do not have.

---

## 8. Migrating from Kora 1.x

| Kora 1.x | Kora 2.0 |
|---|---|
| `ru.tinkoff.kora.experimental:s3-client-aws` | `io.koraframework:s3-client-aws` (SDK wrapper only) |
| `ru.tinkoff.kora.experimental:s3-client-minio` | **removed** — use `io.koraframework.experimental:s3-client-kora` |
| `ru.tinkoff.kora.s3.client.annotation.S3` | `io.koraframework.s3.client.kora.annotation.S3` |
| `@S3.Get` returning metadata | `@S3.Head` → `HeadObjectResult` |
| `S3Object` | `GetObjectResult` (an `HttpClientResponse`; body via `body().asInputStream()`) or `byte[]` |
| `S3ObjectMeta` | `HeadObjectResult` |
| `S3ObjectList` / `S3ObjectMetaList` | `ListBucketResult`, `List<String>`, `List`/`Iterator` of `ListBucketResult.ListBucketItem`, `Iterator<String>` |
| `S3Body` + `S3Body.of*` factories | `byte[]`, `ByteBuffer`, `InputStream`, `S3Client.ContentWriter` |
| `S3ObjectUpload putObject(...)` | `String putObject(...)` (the ETag) or `void` |
| `@S3.List(limit = 50)`, `delimiter = "/"` | `ListObjectsArgs.setMaxKeys(50)`, `.setDelimiter("/")` |
| `@S3.Get`/`@S3.Delete` over `List<String>` | **removed** — one object per call; batch delete via the AWS SDK or `S3Client#deleteObjects` |
| `bucket` key on the client config | `@S3.Bucket` — config path or a method parameter |
| `s3client.url` | `endpoint` under the `@S3.Client` path (SDK wrapper keeps `url` under `s3client.aws`) |
| `s3client.accessKey` / `secretKey` (flat) | nested `credentials { accessKey, secretKey }` |
| `S3NotFoundException` | `S3ClientNoSuchKeyException` |
| `S3DeleteException` | `S3ClientDeleteException` |
| `S3KoraClient` / `S3KoraAsyncClient` | **removed** — `io.koraframework.s3.client.kora.S3Client` (synchronous, credentials + bucket per call) or the AWS SDK client |
| `S3AsyncClient`, `@Tag(MultipartUpload.class)` async client | **removed** with the reactive model — contracts are synchronous on virtual threads |
| `s3client.aws.checksumValidationEnabled` | `checksumCalculationRequest` / `checksumValidationResponse` |
| `s3client.aws.upload { bufferSize, partSize }` | no `upload` section on the SDK wrapper; the declarative client has `upload { partSize, chunkSize, singlePartUploadLimit }` |
| Metrics `s3.client.duration` / `s3.kora.client.duration` | `rpc.client.call.duration`, tag `rpc.system.name=s3` |

`Context` is gone from the whole framework — remove any `Context` parameter or `Context.current()`
call from S3 code paths.

---

## 9. Common pitfalls

| Symptom | Cause / fix |
|---|---|
| `package S3 does not exist` / `package io.koraframework.s3.client.kora.annotation does not exist` | `s3-client-aws` on the classpath but not `s3-client-kora`. The `@S3` annotations live only in `io.koraframework.experimental:s3-client-kora`. |
| `Could not find io.koraframework:s3-client-kora` | Wrong group — the declarative client is `io.koraframework.experimental`. Conversely `s3-client-aws` is plain `io.koraframework`, **not** `.experimental`. |
| `Could not find …:s3-client-minio` | The artifact does not exist in 2.0. Use `s3-client-kora`; a MinIO server keeps working with it. |
| `SignatureDoesNotMatch` / unsigned-header errors from a self-hosted S3 server | Not expected from `s3-client-kora` (SigV4 encoding and header signing are verified against RustFS, SeaweedFS, LocalStack). Check `region`, credentials, clock skew and `addressStyle`, and any proxy that rewrites the path or headers. |
| `S3 operation '…' has no bucket source.` | No `@S3.Bucket` on the interface, the method or a parameter. The client config no longer supplies a bucket. |
| `Config expected value, but got null at path 'ROOT.…endpoint'` | Declarative client config uses `endpoint`; `url` is the SDK wrapper's key. |
| `Config expected value, but got null at path 'ROOT.…credentials.accessKey'` | Flat `accessKey`/`secretKey` from 1.x. They are nested under `credentials`, unless every method takes an `S3Credentials` parameter. |
| `S3 operation '…' expects one object key, but parameter '…' is a collection.` | A batch method. `@S3.Delete`/`@S3.Get` are single-object; use the AWS SDK or `S3Client#deleteObjects`. |
| `S3 operation '@S3.Get' … has unsupported return type` for metadata | `@S3.Get` returns a body. Metadata is `@S3.Head` → `HeadObjectResult`. |
| `interface software.amazon.awssdk.services.s3.S3Client wasn't found in graph` | A `Lifecycle` bucket initialiser nobody depends on was pruned. Add `@Root`. |
| `HttpClient` / transport not found in graph | No Kora HTTP client module on `@KoraApp`. Add `http-client-ok`, `http-client-jdk` or `http-client-apache` — both S3 artifacts need one. |
| `S3ClientNoSuchKeyException` where `null` was expected | Non-`@Nullable` `@S3.Get`/`@S3.Head` is strict by design. Mark it `@Nullable` (Java) or return `T?` (Kotlin). |
| Response body empty or connection leaked | `GetObjectResult` is `Closeable`. Close it **and** the `InputStream`, or return `byte[]`. |
| No S3 metrics or logs although telemetry is "on" | `logging.enabled` and `metrics.enabled` default to `false`. |
| `@S3.List` compiles nowhere / `has no object key` | A bare `@S3.List` needs a prefix parameter, a constant/template prefix, or a `ListObjectsArgs` parameter. |
| `suspend fun` on an `@S3.Client` | Contracts are synchronous in 2.0 and run on virtual threads. |
| Phantom `ru.tinkoff.kora` errors after renaming | Stale generated sources. `clean` + `--no-build-cache`; never edit `build/generated`. |

---

## References & assets

| File | Purpose |
|---|---|
| [references/s3-client-kora.md](references/s3-client-kora.md) | Declarative client in full: every `@S3.*` attribute, generated artefacts, return/body types, `*Args` fields, `S3ClientConfig`, the runtime `S3Client`, exceptions, telemetry |
| [references/s3-client-aws.md](references/s3-client-aws.md) | AWS SDK wrapper in full: `AwsS3Config`, factory-module internals and `@Tag.Factory`, multiple clients, telemetry, common SDK recipes |
| [assets/S3FileClient.java.template](assets/S3FileClient.java.template) | Declarative `@S3.Client` covering get / head / list / put / delete, templates, `*Args`, runtime bucket |
| [assets/S3FileClient.kt.template](assets/S3FileClient.kt.template) | Kotlin twin |
| [assets/AwsS3Service.java.template](assets/AwsS3Service.java.template) | AWS SDK service — batch delete, presigned URLs, everything outside the `@S3` contract |
| [assets/AwsS3Service.kt.template](assets/AwsS3Service.kt.template) | Kotlin twin |
| [assets/S3BucketInitializer.java.template](assets/S3BucketInitializer.java.template) | `@Root` + `Lifecycle` bucket initialiser (the pruning trap) |
| [assets/S3BucketInitializer.kt.template](assets/S3BucketInitializer.kt.template) | Kotlin twin |
| [assets/s3client.conf.snippet](assets/s3client.conf.snippet) | HOCON for both modules, with every key that has a default spelled out |

## Related skills

- [kora-project-dependencies](../kora-project-dependencies/SKILL.md) — BOM, groups, module coordinates
- [kora-config-hocon](../kora-config-hocon/SKILL.md) · [kora-config-yaml](../kora-config-yaml/SKILL.md) — how these sections are mapped, and `@ConfigSource` for the bucket name
- [kora-http-client](../kora-http-client/SKILL.md) — the transport module both artifacts require
- [kora-di-runtime](../kora-di-runtime/SKILL.md) — `@Root`, `Lifecycle`, graph pruning, `@Tag`
- [kora-testing-junit-java](../kora-testing-junit-java/SKILL.md) · [kora-testing-junit-kotlin](../kora-testing-junit-kotlin/SKILL.md) — `@KoraAppTest` with Testcontainers
- [kora-telemetry-metrics](../kora-telemetry-metrics/SKILL.md) · [kora-telemetry-logging](../kora-telemetry-logging/SKILL.md) — the `telemetry` sub-sections
- [kora-aop-resilient](../kora-aop-resilient/SKILL.md) — `@Retryable` / `@CircuitBreakable` on a facade around S3 calls

## Source of truth

Evidence order: framework source and tests > migrated examples > the Kora 2.0 docs
([koraframework.io/v2/en/documentation/s3-client](https://koraframework.io/v2/en/documentation/s3-client/)).
The 1.x pages (`ru.tinkoff.kora`) document the removed 1.x client — background only.

- Framework source, tag `2.0.0.RC2`:
  [experimental/s3-client-kora](https://github.com/kora-projects/kora/tree/2.0.0.RC2/experimental/s3-client-kora) ·
  [s3/s3-client-aws](https://github.com/kora-projects/kora/tree/2.0.0.RC2/s3/s3-client-aws) ·
  [s3-client-annotation-processor](https://github.com/kora-projects/kora/tree/2.0.0.RC2/experimental/s3-client-annotation-processor) ·
  [s3-client-symbol-processor](https://github.com/kora-projects/kora/tree/2.0.0.RC2/experimental/s3-client-symbol-processor) ·
  framework S3 server suite: [RustFS / SeaweedFS / LocalStack tests](https://github.com/kora-projects/kora/tree/2.0.0.RC2/experimental/s3-client-kora/src/test/java/io/koraframework/s3/client)
- Migrated guide apps, branch `migration/2.0` (both artifacts in one service):
  [kora-java-guide-s3-app](https://github.com/kora-projects/kora-examples/tree/migration/2.0/guides/java/kora-java-guide-s3-app) ·
  [kora-kotlin-guide-s3-app](https://github.com/kora-projects/kora-examples/tree/migration/2.0/guides/kotlin/kora-kotlin-guide-s3-app)
- Migrated examples, branch `migration/2.0`:
  [kora-java-s3-client-kora](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/java/kora-java-s3-client-kora) ·
  [kora-java-s3-client-aws](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/java/kora-java-s3-client-aws) ·
  [kora-kotlin-s3-client-kora](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/kotlin/kora-kotlin-s3-client-kora) ·
  [kora-kotlin-s3-client-aws](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/kotlin/kora-kotlin-s3-client-aws)
- Third-party: [AWS SDK for Java 2.x — S3](https://docs.aws.amazon.com/sdk-for-java/latest/developer-guide/examples-s3.html) ·
  [Amazon S3 API reference](https://docs.aws.amazon.com/AmazonS3/latest/API/Welcome.html) ·
  [LocalStack S3](https://docs.localstack.cloud/aws/services/s3/) ·
  [MinIO server docs](https://min.io/docs/minio/container/index.html)
