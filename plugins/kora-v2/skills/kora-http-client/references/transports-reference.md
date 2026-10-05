# HTTP Client Transports Reference (Kora 2.x)

Reference for [kora-http-client](../SKILL.md). Verified against the framework source at tag
**`2.0.0.RC2`**.

## Contents

- [Choosing a transport](#choosing-a-transport)
- [Wiring](#wiring)
- [Shared config: httpClient](#shared-config-httpclient)
- [OkHttp — http-client-ok](#okhttp--http-client-ok)
- [JDK — http-client-jdk](#jdk--http-client-jdk)
- [Apache — http-client-apache](#apache--http-client-apache)
- [Advanced tuning with Configurer](#advanced-tuning-with-configurer)
- [Proxy](#proxy)
- [Telemetry](#telemetry)
- [Log masking](#log-masking)
- [Removed: http-client-async](#removed-http-client-async)
- [Troubleshooting](#troubleshooting)

---

## Choosing a transport

| | `http-client-ok` | `http-client-jdk` | `http-client-apache` |
|---|---|---|---|
| Module interface | `OkHttpClientModule` | `JdkHttpClientModule` | `ApacheHttpClientModule` |
| Package | `io.koraframework.http.client.ok` | `io.koraframework.http.client.jdk` | `io.koraframework.http.client.apache` |
| Underlying client | OkHttp 3 (+ Okio) | `java.net.http.HttpClient` | Apache HttpClient 5 |
| Config section | `httpClient.ok` | `httpClient.jdk` | `httpClient.apache` |
| HTTP versions | `HTTP_1_1`, `HTTP_2`, `HTTP_3` | `HTTP_1_1`, `HTTP_2` | not selectable |
| Extra dependencies | OkHttp + Okio | none | `org.apache.httpcomponents.client5` |
| Headers it owns (dropped if you set them) | — | `connection`, `content-length`, `expect`, `host`, `upgrade` | `content-length`, `transfer-encoding` |

**Recommendation:** `http-client-ok` unless something rules it out — it is the transport the Kotlin
example application and both HTTP-client guides use. `http-client-jdk` is the zero-extra-dependency
option. `http-client-apache` (new in 2.0) fits when the service already standardises on Apache
HttpClient 5 or needs its connection-pool sizing.

Exactly **one** transport module goes into `@KoraApp`. All three register the `HttpClient`
component under the same `httpClient` base config path, so two of them in one graph is an ambiguous
binding.

---

## Wiring

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:http-client-ok"
    implementation "io.koraframework:json-common"
    implementation "io.koraframework:config-hocon"
}
```

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        JsonModule,
        OkHttpClientModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

```kotlin
@KoraApp
interface Application : HoconConfigModule, JsonModule, OkHttpClientModule

fun main() {
    KoraApplication.run { ApplicationGraph.graph() }
}
```

Each module contributes a `@FactoryModule` bound to the base path `"httpClient"`:
`OkHttpClientModule` → `new OkHttpClientFactoryModule("httpClient")`, which derives
`"httpClient.ok"`; likewise `.jdk` and `.apache`. The two-argument constructors
(`new OkHttpClientFactoryModule("myClients", "myClients.ok")`) let you relocate both paths, but the
default module methods use the single-argument form.

---

## Shared config: `httpClient`

`io.koraframework.http.client.common.HttpClientConfig`, read from the base path `httpClient`:

| Key | Type | Default | Meaning |
|---|---|---|---|
| `connectTimeout` | `Duration` | `5s` | Maximum time to establish a connection |
| `readTimeout` | `Duration` | `2m` | Maximum time to read a response |
| `useEnvProxy` | `boolean` | `false` | Read `https_proxy`/`HTTPS_PROXY`/`http_proxy`/`HTTP_PROXY` and `no_proxy`/`NO_PROXY` |
| `proxy.host` | `String` | — | Required when `proxy` is present |
| `proxy.port` | `int` | — | Required when `proxy` is present |
| `proxy.nonProxyHosts` | `List<String>` | `null` | Hosts excluded from proxying |
| `proxy.user` / `proxy.password` | `String` | `null` | Proxy credentials; both must be set for authentication |

```hocon
httpClient {
  connectTimeout = 5s
  readTimeout = 2m
  useEnvProxy = false
}
```

These are **transport-level** and shared by every declarative client. Per-call budgets are
`requestTimeout`, set inside a client's own block (or per method) — see
[declarative-client-reference](declarative-client-reference.md#client-configuration).

The JDK transport has no socket-read timeout: it applies `readTimeout` as the per-request timeout
(`HttpRequest.timeout`) of every call that sets no `requestTimeout`; a client or method
`requestTimeout` replaces it. A zero or negative `readTimeout` means no timeout.

---

## OkHttp — `http-client-ok`

`OkHttpClientConfig` at `httpClient.ok`:

| Key | Type | Default | Meaning |
|---|---|---|---|
| `followRedirects` | `boolean` | `true` | Follow HTTP redirects |
| `retryOnConnectionFailure` | `boolean` | `true` | Retry after a connection failure — can extend the effective connect time |
| `httpVersion` | enum | `HTTP_1_1` | `HTTP_1_1`, `HTTP_2`, `HTTP_3` |

```hocon
httpClient {
  connectTimeout = 5s
  readTimeout = 30s

  ok {
    followRedirects = true
    retryOnConnectionFailure = true
    httpVersion = "HTTP_2"
  }
}
```

`httpVersion` sets the protocol *preference list*, always with fallbacks:
`HTTP_2` → `[h2, http/1.1]`, `HTTP_3` → `[h3, h2, http/1.1]`. Selecting `HTTP_2` therefore cannot
break a server that only speaks HTTP/1.1.

---

## JDK — `http-client-jdk`

`JdkHttpClientConfig` at `httpClient.jdk`:

| Key | Type | Default | Meaning |
|---|---|---|---|
| `followRedirects` | `boolean` | `true` | Maps to `Redirect.NORMAL` / `Redirect.NEVER` |
| `httpVersion` | `java.net.http.HttpClient.Version` | `HTTP_1_1` | `HTTP_1_1` or `HTTP_2` |

```hocon
httpClient {
  connectTimeout = 5s
  jdk {
    followRedirects = true
    httpVersion = "HTTP_2"
  }
}
```

Unlike OkHttp, `httpVersion` here is the JDK's exact version setting, not a preference list. The
client runs on a virtual-thread executor.

`java.net.http` refuses the restricted header names `connection`, `content-length`, `expect`,
`host` and `upgrade`, so the transport **silently skips** them when copying request headers — the
JDK client derives them itself (`host` from the URI). A `Host` header set by an interceptor or a
request signer therefore never reaches the wire on this transport.

---

## Apache — `http-client-apache`

New in Kora 2.0. `ApacheHttpClientConfig` at `httpClient.apache`:

| Key | Type | Default | Meaning |
|---|---|---|---|
| `followRedirects` | `boolean` | `true` | Follow HTTP redirects |
| `maxRedirects` | `int` | `3` | Redirect hop limit |
| `maxConnections` | `int` | `availableProcessors() * 250` | Applied to both total and per-route pool size |

```hocon
httpClient {
  apache {
    followRedirects = true
    maxRedirects = 3
    maxConnections = 200
  }
}
```

`ApacheHttpClientConfig` holds **only** these three keys. Timeouts and proxy come from the shared
`httpClient` block like every other transport: `connectTimeout` becomes both the request-config and
the pool's connection connect timeout, `readTimeout` the response timeout, and `proxy` /
`useEnvProxy` a proxy selector (with credentials when both `user` and `password` are set). Do not
repeat them under `httpClient.apache` — they are not keys there.

Apache derives message framing from the entity, so the transport drops `Content-Length` and
`Transfer-Encoding` request headers instead of forwarding them (forwarding them would make
Apache's `RequestContent` reject the request).

---

## Advanced tuning with `Configurer`

`OkHttpConfigurer` no longer exists. Each transport factory takes an optional
`io.koraframework.common.Configurer<T>` over the underlying builder:

| Transport | Configurer type |
|---|---|
| OkHttp | `Configurer<okhttp3.OkHttpClient.Builder>` |
| JDK | `Configurer<java.net.http.HttpClient.Builder>` |
| Apache | `Configurer<org.apache.hc.client5.http.impl.classic.HttpClientBuilder>` and `Configurer<org.apache.hc.client5.http.config.RequestConfig.Builder>` |

```java
@Component
public final class ConnectionPoolConfigurer implements Configurer<OkHttpClient.Builder> {

    @Override
    public OkHttpClient.Builder configure(OkHttpClient.Builder builder) {
        return builder.connectionPool(new ConnectionPool(50, 5, TimeUnit.MINUTES));
    }
}
```

```kotlin
@Component
class ConnectionPoolConfigurer : Configurer<OkHttpClient.Builder> {
    override fun configure(t: OkHttpClient.Builder): OkHttpClient.Builder =
        t.connectionPool(ConnectionPool(50, 5, TimeUnit.MINUTES))
}
```

The configurer parameter is declared `@Tag(Tag.Factory.class) @Nullable`. `Tag.Factory` means
"use the tag of the enclosing factory-module method"; the default `okHttpClientFactory()` carries
no tag, so a plain untagged `@Component` resolves. It is optional — omit it entirely and the
transport uses its own defaults. `configure` **must return** the builder (or a derived one); the
return value is what gets built.

Only one configurer per builder type can be in the graph — a second one is `Multiple components
match`. Do all tuning in a single component.

---

## Proxy

Environment-driven:

```hocon
httpClient { useEnvProxy = true }
```

`HttpClientProxyConfig.fromEnv()` reads `https_proxy` → `HTTPS_PROXY` → `http_proxy` →
`HTTP_PROXY` in that order, parses `user:password@host:port` from the URI, and takes
`no_proxy` / `NO_PROXY` (comma-separated) as `nonProxyHosts`. When `useEnvProxy = true` the
environment **replaces** any explicit `proxy` block rather than merging with it.

Explicit:

```hocon
httpClient {
  proxy {
    host = "proxy.example.com"
    port = 8080
    user = "proxyuser"
    password = ${?PROXY_PASSWORD}
    nonProxyHosts = ["localhost", "127.0.0.1", "*.internal"]
  }
}
```

Proxy authentication is applied only when **both** `user` and `password` are present. All three
transports read this block from `httpClient`.

---

## Telemetry

Telemetry is per **client**, not per transport: it lives under `httpClient.<client>.telemetry` and
is described in
[declarative-client-reference](declarative-client-reference.md#client-configuration).

Defaults that bite (`TelemetryConfig` in `telemetry-common`):

| Section | Default |
|---|---|
| `telemetry.logging.enabled` | **`false`** |
| `telemetry.metrics.enabled` | **`false`** |
| `telemetry.tracing.enabled` | `true` |

```hocon
httpClient.userApi {
  url = "http://users-service:8080"
  telemetry {
    logging.enabled = true
    metrics.enabled = true
  }
}
```

Metrics additionally need a `MeterRegistry` in the graph (`micrometer-module`) and tracing needs a
`Tracer` (`opentelemetry-tracing`) — both are `@Nullable` dependencies of the default
`HttpClientTelemetryFactory`, so without them the corresponding telemetry is silently absent even
with `enabled = true`.

The client timer is registered as **`http.client.request.duration`**, tagged `http.request.method`,
`http.response.status_code`, `server.address`, `url.scheme`, `server.port` (the URI port, else `80`
for `http` / `443` for `https`), **`url.template`** (the route template — not `http.route`, which is a
server-side attribute), `error.type` (empty on success) and `system.config`, `system.name.simple`,
`system.name.canonical`. The client span carries `url.template` too. See
[`kora-telemetry-metrics`](../../kora-telemetry-metrics/SKILL.md).

---

## Log masking

Client request/response logging masks header values listed in `telemetry.logging.maskHeaders`
(default `["authorization", "set-cookie", "cookie"]`) and query values listed in `maskQueries`
(default empty). Both are logged only when the client's `.request` / `.response` logger is at
`DEBUG`; bodies are logged only at `TRACE`. A failed call without a response (connection error,
timeout) is logged at `WARN` as `HttpClient error received` on the **`.response`** logger, so that
logger's level controls it.

| What | Config picks | Graph component decides how | Default |
|---|---|---|---|
| Header / query values | `maskHeaders`, `maskQueries` | `@Tag(HttpClientTelemetry.class) MaskingStrategy` | replaced with `***` |
| Request / response bodies | body `Content-Type` → `json` (`*/json`, `*+json`), `xml` (`*/xml`, `*+xml`), `form-urlencoded` | `@Tag(HttpClientTelemetry.class) DataMasker` with that `format()` | **none — logged as is** |

- A configured list **replaces** its default: restate `authorization`, `set-cookie`, `cookie` when
  you add a header. Names are lower-cased before matching, so config case does not matter.
- There is no `mask` key (neither per client nor per method). The replacement text is the
  `MaskingStrategy`'s job; it receives the original value, so `MaskingKeepLast` can keep a suffix.
- The tag is `io.koraframework.http.client.common.telemetry.HttpClientTelemetry`, one strategy and
  one masker per format for **all** clients. For per-client body rules, subclass
  `DefaultHttpClientBodyConverter`, override `selectRequestDataMasker` / `selectResponseDataMasker`
  (they receive the client config path and canonical name) and return it from a factory method typed
  `DefaultHttpClientBodyConverter`.

```java
@Tag(HttpClientTelemetry.class)
default DataMasker httpClientJsonBodyMasker() {
    return new JsonDataMasker(MaskingPathRules.builder()
            .mask("access_token", new MaskingFull())
            .mask("client_secret", new MaskingFull())
            .build());
}
```

```kotlin
@Tag(HttpClientTelemetry::class)
fun httpClientJsonBodyMasker(): DataMasker = JsonDataMasker(
    MaskingPathRules.builder()
        .mask("access_token", MaskingFull())
        .mask("client_secret", MaskingFull())
        .build()
)
```

`MaskingStrategy`, `MaskingFull`, `MaskingKeepFirst`, `MaskingKeepLast`, `MaskingPathRules` are in
`io.koraframework.logging.common.masking`; `DataMasker`, `JsonDataMasker`, `XmlDataMasker`,
`FormUrlencodedDataMasker` in `…masking.raw`. The shared model (path syntax, fail-closed parsing,
length limits) is in [kora-aop-logging → masking](../../kora-aop-logging/references/logging-masking.md).

---

## Removed: `http-client-async`

`ru.tinkoff.kora:http-client-async` and `AsyncHttpClientModule` **do not exist in Kora 2.0** — the
artifact is not in the BOM and the module is not in the source tree. There is no async transport,
because there are no async client contracts: every generated method blocks on a virtual thread.

Migration is mechanical on the build side and semantic in the code:

1. Replace the dependency with `http-client-ok` (closest feature set: redirects, HTTP/2).
2. Replace `AsyncHttpClientModule` with `OkHttpClientModule` in `@KoraApp`.
3. Move `httpClient.async { … }` keys to `httpClient.ok { … }` — `followRedirects` carries over;
   there is no `retryOnConnectionFailure` equivalent to migrate *from*, it is new.
4. Rewrite every `CompletionStage`/`Mono`/`suspend` client method as synchronous — see
   [execution-model-reference](execution-model-reference.md).

Step 4 is the real work. Steps 1–3 alone leave a graph that fails to resolve
`HttpClientResponseMapper<CompletionStage<T>>`.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Multiple components match` for `HttpClient` | Two transport modules in the same `@KoraApp` — keep one |
| Connect timeouts under load | Raise `httpClient.connectTimeout`; on OkHttp remember `retryOnConnectionFailure = true` multiplies the effective wait |
| A `Host` / `Connection` / `Expect` header set by an interceptor is missing on the wire | JDK transport — it drops restricted headers and derives them itself |
| `connectTimeout` placed under `httpClient.apache` has no effect | It is not an Apache key; set it at `httpClient` |
| HTTP/2 not negotiated | Set `httpClient.ok.httpVersion = "HTTP_2"` (or `jdk`) and confirm the server supports it — the list always falls back to 1.1 |
| Connection pool exhausted | OkHttp/JDK: a `Configurer` component; Apache: `httpClient.apache.maxConnections` |
| No `http.client.request.duration` metric | `telemetry.metrics.enabled` is `false` by default, and a `MeterRegistry` must be in the graph |
| Credentials visible in logs | Add the header/query names to `telemetry.logging.maskHeaders` / `maskQueries` (restating the defaults); for bodies add a `@Tag(HttpClientTelemetry.class) DataMasker` — see [Log masking](#log-masking) |

---

## See also

- [declarative-client-reference](declarative-client-reference.md)
- [execution-model-reference](execution-model-reference.md)
- [interceptors-reference](interceptors-reference.md)
- [error-handling-guide](error-handling-guide.md)
