# `s3-client-aws` — the AWS SDK wrapper (Kora 2.0)

Artifact **`io.koraframework:s3-client-aws`** — note the plain `io.koraframework` group, **not**
`io.koraframework.experimental` — module `io.koraframework.s3.client.aws.AwsS3ClientModule`.

This artifact configures the AWS SDK for Java v2 and publishes
`software.amazon.awssdk.services.s3.S3Client` into the graph. It contains **no `@S3` annotation and
no Kora S3 models**. If you want declarative `@S3.Client` interfaces, you want
[s3-client-kora.md](s3-client-kora.md) instead — the two artifacts are independent and neither
provides the other's API.

AWS SDK version: `software.amazon.awssdk:s3` **2.55.10**, pulled transitively.

---

## 1. Wiring

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:s3-client-aws"
    implementation "io.koraframework:http-client-apache"          // or -ok / -jdk
    implementation "io.koraframework:config-hocon"
}
```

```kotlin
dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

    implementation("io.koraframework:s3-client-aws")
    implementation("io.koraframework:http-client-jdk")
    implementation("io.koraframework:config-hocon")
}
```

```java
@KoraApp
public interface Application extends
        HoconConfigModule, LogbackModule,
        AwsS3ClientModule,
        ApacheHttpClientModule { }
```

### The transport is Kora's HTTP client, not the AWS SDK's

`s3-client-aws` **excludes** `software.amazon.awssdk:apache-client` and
`software.amazon.awssdk:netty-nio-client` from its own dependency on the SDK. Instead
`AwsS3HttpClientProvider` takes Kora's `io.koraframework.http.client.common.HttpClient` and
`KoraAwsSdkHttpClient` adapts it to the SDK's `SdkHttpClient` SPI. A Kora HTTP client module is
therefore mandatory; without one the graph fails to resolve `HttpClient`.

One consequence worth knowing: `httpClient { connectTimeout, readTimeout, … }` — the Kora HTTP
client's own config section — applies to S3 traffic too.

---

## 2. What lands in the graph

`AwsS3ClientModule` provides two things:

```java
public interface AwsS3ClientModule {

    @FactoryModule
    default AwsS3ClientFactoryModule awsS3ClientFactoryModule() {
        return new AwsS3ClientFactoryModule("s3client.aws");   // ← the config path is fixed here
    }

    default AwsS3ClientTelemetryFactory awsS3ClientTelemetryFactory(
            @Nullable Tracer tracer, @Nullable MeterRegistry meterRegistry, …) { … }
}
```

`AwsS3ClientFactoryModule` then contributes, all under `@Tag(Tag.Factory.class)`:

| Component | Notes |
|---|---|
| `AwsS3Config` | mapped from `config.get("s3client.aws")` |
| `AwsS3HttpClientProvider` | `@DefaultComponent`; wraps Kora's `HttpClient` |
| `KoraAwsSdkHttpClient` | `@DefaultComponent`; the SDK `SdkHttpClient` adapter |
| `S3Configuration` | `@DefaultComponent`; `chunkedEncodingEnabled`, `pathStyleAccessEnabled` |
| `AwsCredentialsProvider` | `@DefaultComponent`; `AwsBasicCredentials` from config |
| `AwsS3ClientFactory` | builds an `S3Client` from an `AwsS3Config` |
| **`software.amazon.awssdk.services.s3.S3Client`** | the component you inject |

### `@Tag(Tag.Factory.class)` does **not** mean you need a tag

`@Tag.Factory` is a substitution marker: inside a `@FactoryModule`, it resolves to the tag of the
factory-module **provider method itself**
(`ComponentDeclaration.fromModule` / `ComponentDependencyHelper`). `awsS3ClientFactoryModule()`
carries no `@Tag`, so the resolved tag is *none* and every component above — `S3Client` included —
is registered untagged:

```java
@Component
public class AwsS3Service {
    public AwsS3Service(S3Client s3Client) { … }     // no @Tag needed
}
```

Using `@Tag.Factory` outside a factory module is a compile error:
*"@Tag.Factory can only be used inside factory modules:"*

### Several independently configured clients

That same substitution is the mechanism for multiple clients. Declare extra tagged
`@FactoryModule` methods; every component the factory module contributes inherits the method's tag.

```java
@KoraApp
public interface Application extends AwsS3ClientModule, ApacheHttpClientModule {

    @Tag(Archive.class)
    @FactoryModule
    default AwsS3ClientFactoryModule archiveS3FactoryModule() {
        return new AwsS3ClientFactoryModule("s3client.archive");
    }

    final class Archive {}
}

@Component
public class ArchiveService {
    public ArchiveService(@Tag(Application.Archive.class) S3Client archive) { … }
}
```

---

## 3. Configuration — `AwsS3Config`

Fixed path **`s3client.aws`** (set by `AwsS3ClientModule`; a second factory module can point at
any other path). Unrelated to the declarative client's `@S3.Client(...)` path.

| Key | Type | Default | Notes |
|---|---|---|---|
| `url` | `String` | **required** | The endpoint. The declarative client calls this key `endpoint` — they are different modules. |
| `region` | `String` | `"aws-global"` | Passed to `Region.of(...)` |
| `addressStyle` | `PATH` \| `VIRTUAL_HOSTED` | `PATH` | `PATH` → `S3Configuration.pathStyleAccessEnabled(true)`. Keep `PATH` for self-hosted servers (RustFS, SeaweedFS, LocalStack, MinIO, Ceph). |
| `requestTimeout` | `Duration` | `45s` | |
| `chunkedEncodingEnabled` | `boolean` | `true` | `S3Configuration.chunkedEncodingEnabled` |
| `checksumCalculationRequest` | `WHEN_SUPPORTED` \| `WHEN_REQUIRED` | `WHEN_REQUIRED` | → SDK `RequestChecksumCalculation` |
| `checksumValidationResponse` | `WHEN_SUPPORTED` \| `WHEN_REQUIRED` | `WHEN_REQUIRED` | → SDK `ResponseChecksumValidation` |
| `credentials.accessKey` | `String` | **required** | |
| `credentials.secretKey` | `String` | **required** | |
| `telemetry.logging.enabled` | `boolean` | **`false`** | |
| `telemetry.metrics.enabled` | `boolean` | **`false`** | |
| `telemetry.metrics.slo` | `Duration[]` | framework default buckets | |
| `telemetry.tracing.enabled` | `boolean` | `true` | |

There is **no** `upload` section and **no** `checksumValidationEnabled` key on this module — both
were Kora 1.x shapes. Multipart tuning for the SDK is the SDK's own concern.

```hocon
s3client.aws {
  url    = ${S3_URL}
  region = "us-east-1"
  region = ${?S3_REGION}

  addressStyle           = "PATH"
  requestTimeout         = "45s"
  chunkedEncodingEnabled = true

  checksumCalculationRequest = "WHEN_REQUIRED"
  checksumValidationResponse = "WHEN_REQUIRED"

  credentials {
    accessKey = ${S3_ACCESS_KEY}
    secretKey = ${S3_SECRET_KEY}
  }

  telemetry {
    logging.enabled = true
    metrics.enabled = true
    tracing.enabled = true
  }
}
```

The bucket name is **not** part of this config. Hold it in your own `@ConfigSource` interface:

```java
@ConfigSource("my")
public interface S3Config {
    String bucket();
}
```

---

## 4. Using the SDK client

Everything is the AWS SDK for Java v2 API — Kora adds no wrapper types.

```java
@Component
public class AwsS3Service {

    private final S3Client s3Client;
    private final String bucket;

    public AwsS3Service(S3Client s3Client, S3Config config) {
        this.s3Client = s3Client;
        this.bucket = config.bucket();
    }

    public PutObjectResponse putObject(String key, byte[] value) {
        return s3Client.putObject(r -> r.bucket(bucket).key(key), RequestBody.fromBytes(value));
    }

    public ResponseInputStream<GetObjectResponse> getObject(String key) {
        return s3Client.getObject(r -> r.bucket(bucket).key(key));
    }

    public HeadObjectResponse getObjectMeta(String key) {
        return s3Client.headObject(r -> r.bucket(bucket).key(key));
    }

    public ListObjectsV2Response listObjects(String prefix) {
        return s3Client.listObjectsV2(r -> r.bucket(bucket).prefix(prefix).maxKeys(50));
    }

    public void deleteObject(String key) {
        s3Client.deleteObject(r -> r.bucket(bucket).key(key));
    }

    public DeleteObjectsResponse deleteObjects(List<String> keys) {
        var identifiers = keys.stream()
                .map(key -> ObjectIdentifier.builder().key(key).build())
                .toList();
        return s3Client.deleteObjects(r -> r.bucket(bucket).delete(d -> d.objects(identifiers)));
    }
}
```

The response of `getObject` is a `ResponseInputStream` — close it.

### Bucket administration and the pruning trap

Creating or checking a bucket is not part of the declarative `@S3` contract, so it goes through
this client. A `Lifecycle` component that only prepares external state has no dependants, and the
graph prunes unreferenced components — taking the `S3Client` it needed with it. The error names
the SDK type, not your class:

```
interface software.amazon.awssdk.services.s3.S3Client wasn't found in graph
```

Mark it `@Root`:

```java
@Root
@Component
public final class S3BucketInitializer implements Lifecycle {

    private final S3Client s3Client;
    private final S3Config config;

    public S3BucketInitializer(S3Client s3Client, S3Config config) {
        this.s3Client = s3Client;
        this.config = config;
    }

    @Override
    public void init() {
        var bucket = this.config.bucket();
        try {
            this.s3Client.headBucket(HeadBucketRequest.builder().bucket(bucket).build());
        } catch (NoSuchBucketException e) {
            this.s3Client.createBucket(CreateBucketRequest.builder().bucket(bucket).build());
        }
    }

    @Override
    public void release() {}
}
```

### Presigned URLs

`S3Presigner` is not a Kora component — build one yourself, pointed at the same endpoint,
region and credentials, and close it:

```java
try (var presigner = S3Presigner.builder()
        .endpointOverride(URI.create(config.url()))
        .region(Region.of(config.region()))
        .credentialsProvider(() -> AwsBasicCredentials.create(accessKey, secretKey))
        .build()) {

    var presigned = presigner.presignGetObject(GetObjectPresignRequest.builder()
            .signatureDuration(Duration.ofMinutes(15))
            .getObjectRequest(GetObjectRequest.builder().bucket(bucket).key(key).build())
            .build());

    return presigned.url();
}
```

`S3AsyncClient`, `S3TransferManager` and the 1.x `@Tag(MultipartUpload.class)` async client are
**not** provided by this module. Kora 2.0 contracts are synchronous on virtual threads.

### Custom SDK interceptors

`AwsS3ClientFactory` collects `@Tag(Tag.Factory.class) All<ExecutionInterceptor>` and adds every
one to the client's `overrideConfiguration`, alongside Kora's own telemetry interceptor. The
`@Tag.Factory` there resolves the same way as everywhere else in this factory module — to the tag of
the `@FactoryModule` provider method — so with the stock `AwsS3ClientModule` a plain untagged
`@Component ExecutionInterceptor` is picked up. Under a **tagged** extra factory module, only
interceptors carrying that same tag are.

---

## 5. Telemetry

`AwsS3ClientTelemetryInterceptor` is an SDK `ExecutionInterceptor`, always installed.

| Signal | Detail |
|---|---|
| Metrics | Micrometer `Timer` **`rpc.client.call.duration`**, tags `rpc.system.name=s3`, `rpc.method`, `aws.s3.bucket`, `error.type`, `system.config`, `system.name.simple`, `system.name.canonical` |
| Tracing | OpenTelemetry span per operation with the same attributes |
| Logging | SLF4J logger named `software.amazon.awssdk.services.s3.S3Client`; `DEBUG` for request/response, `WARN` on failure |

Both S3 modules use the same metric name and `rpc.system.name=s3`; separate their series by
`system.config` / `system.name.canonical`.

`logging.enabled` and `metrics.enabled` default to **`false`**.

```hocon
s3client.aws.telemetry {
  logging.enabled = true
  metrics.enabled = true
}
logging.levels { "software.amazon.awssdk.services.s3.S3Client" = "DEBUG" }
```

---

## 6. Kora 1.x → 2.0

| Kora 1.x | Kora 2.0 |
|---|---|
| `ru.tinkoff.kora.experimental:s3-client-aws` | `io.koraframework:s3-client-aws` (no `experimental`) |
| `ru.tinkoff.kora.s3.client.aws.AwsS3ClientModule` | `io.koraframework.s3.client.aws.AwsS3ClientModule` |
| Module also carried `@S3.Client`, `S3KoraClient`, `S3Body`, `S3Object` | none of it — this artifact is an SDK wrapper only; the declarative client moved to `io.koraframework.experimental:s3-client-kora` |
| Flat `s3client.url` / `accessKey` / `secretKey` | `s3client.aws.url` + nested `credentials { accessKey, secretKey }` |
| `checksumValidationEnabled` | `checksumCalculationRequest` / `checksumValidationResponse` (`WHEN_REQUIRED` / `WHEN_SUPPORTED`) |
| `upload { bufferSize, partSize }` | removed from this module |
| `S3AsyncClient`, `@Tag(MultipartUpload.class) S3AsyncClient` | removed with the reactive model |
| Metrics `s3.client.duration` | `rpc.client.call.duration`, tag `rpc.system.name=s3` |

---

## Source of truth

- Framework source, tag `2.0.0.RC2`:
  [s3/s3-client-aws](https://github.com/kora-projects/kora/tree/2.0.0.RC2/s3/s3-client-aws)
- Migrated examples, branch `migration/2.0`:
  [kora-java-s3-client-aws](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/java/kora-java-s3-client-aws) ·
  [kora-kotlin-s3-client-aws](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/kotlin/kora-kotlin-s3-client-aws) ·
  [kora-java-guide-s3-app](https://github.com/kora-projects/kora-examples/tree/migration/2.0/guides/java/kora-java-guide-s3-app) (both artifacts together)
- [AWS SDK for Java 2.x — S3 examples](https://docs.aws.amazon.com/sdk-for-java/latest/developer-guide/examples-s3.html) ·
  [S3Client javadoc](https://sdk.amazonaws.com/java/api/latest/software/amazon/awssdk/services/s3/S3Client.html)
