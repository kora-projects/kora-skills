# What a Kora 1.x developer must unlearn for Kora 2.0

For learners arriving with Kora 1.x habits. Teach this **before** the curriculum, not alongside it —
several of these habits produce code that compiles and then does nothing, so a learner who meets
them mid-lesson concludes the framework is unreliable rather than that their model is stale.

Order matters. §1 and §2 change how a service is *shaped*; the rest are renames and removals.

---

## 1. Kora 2.0 is synchronous, executed on virtual threads

This is the largest change, and the one that most often survives as a wrong habit because the
1.x style *looks* more modern.

**Removed as Kora contracts:** Reactor `Mono` / `Flux`, `CompletionStage`, and Kotlin `suspend`
repositories, controllers and HTTP clients. There is no `HttpServerResponseMapper` for reactive
types in `http-server-common`. Every Kora contract — a repository method, a controller handler, a
declarative HTTP client method — returns its value directly.

The runtime that makes this fine: the Undertow transport dispatches each request onto a **virtual
thread** (`http-server-undertow` uses `Thread.ofVirtual()` for handler dispatch). Blocking a virtual
thread parks a continuation instead of pinning a platform thread, so plain blocking code is the
correct, idiomatic, high-throughput style.

**Teach it as a rule the learner can apply without thinking:** write the straightforward blocking
call. That is the Kora 2.0 way.

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{userId}")
@Json
public UserResponse getUser(@Path String userId) {
    return userService.getUser(userId)
            .orElseThrow(() -> HttpServerResponseException.of(404, "User not found: " + userId));
}
```

### For a Kotlin learner specifically

| 1.x habit | Kora 2.0 |
|---|---|
| `suspend fun` on a repository / controller / `@HttpClient` method | a plain function returning the value |
| `withContext(Dispatchers.IO) { koraCall() }` | just `koraCall()` — the dispatcher hop is pure overhead on a virtual thread |
| `runBlocking { … }` as a bridge at the edge of Kora code | no bridge needed; there is nothing suspending to bridge |
| `async`/`await` for parallel fan-out | Java `StructuredTaskScope` (below) |
| `Flow` / channels for streaming | no mechanical analogue — redesign the API |

If `kotlinx-coroutines-core` remains in the build only to satisfy code that has been converted,
remove the dependency too; leaving it invites the habit back.

### Real parallelism: `StructuredTaskScope`

Concurrent fan-out — two independent calls whose results are combined — moves to Java structured
concurrency.

**`StructuredTaskScope` is a preview API, and it has changed shape across JDK releases.** Do not
memorise a signature, and do not copy one from a JDK older than the one you are on: the factories,
the `Joiner` types and the return type of `join()` have all moved between JDK 21 and today. The rule
to teach:

> Pick the **latest GA feature release of Java** at the time you are writing, and use the structured
> concurrency preview iteration **from that JDK**. Do not run an EA build in production for a newer
> preview. Re-derive the API shape from that JDK's own documentation rather than from any example,
> including this one.

The shape below was correct for **JDK 26 / Structured Concurrency Sixth Preview (JEP 525)**, the
latest GA at the time the upstream migration guides were refreshed. Treat it as an illustration of
the *pattern*, and check the API of the JDK actually in use:

```kotlin
// Shape as of JDK 26 (JEP 525). Verify against your own JDK before copying.
import java.util.concurrent.Callable
import java.util.concurrent.StructuredTaskScope

fun getDashboard(userId: Long): Dashboard =
    StructuredTaskScope.open(
        StructuredTaskScope.Joiner.awaitAllSuccessfulOrThrow<Any>(),
    ).use { scope ->
        val profile = scope.fork(Callable { profileClient.getProfile(userId) })
        val recommendations = scope.fork(Callable { recommendationClient.getForUser(userId) })

        scope.join()
        Dashboard(profile.get(), recommendations.get())
    }
```

Policy translation, which is the part worth teaching rather than the syntax:

| Coroutine intent | Structured concurrency |
|---|---|
| fail fast, cancel siblings | a joiner that awaits all successful results or throws |
| first successful result wins | the "any successful" joiner of your JDK's API |
| supervisor-like: collect outcomes, inspect failures | await all, then check each `Subtask` state and exception |
| `withTimeout` | a timeout in the scope's configuration |

Cancellation and exception propagation must be **re-tested** after such a rewrite; the semantics are
similar in spirit and different in detail.

**Preview must be enabled everywhere, not just at compilation.** `--enable-preview` is needed for
javac, for every JVM launch (tests, `JavaExec`, the production launcher), and `--release` must match
the chosen JDK. In Kotlin the compiler needs `-Xjdk-release=<N>` and `-Xjvm-enable-preview` as well.
A build that compiles and then fails at startup with a preview-feature error is this step half-done.

Note that `--enable-preview` is **not** a Kora requirement. Kora itself uses it only in its own test
task. A learner needs it only if they themselves use a preview API.

---

## 2. The request `Context` is gone

`Context` no longer exists **anywhere in the framework** — `find . -name Context.java -path '*/main/*'`
in the 2.0 source returns nothing. It was not moved to another package and not narrowed to the HTTP
APIs. It was removed.

So a 1.x pattern that threaded per-request state through Kora's `Context` — a correlation id, a
tenant, an authenticated principal, anything carried implicitly across a call chain — has **no 2.0
form to be patched into**. It has to be redesigned. Three honest answers, in the order to offer them:

- **Pass it explicitly.** On virtual threads a parameter costs nothing, and an explicit parameter is
  the shape the compile-time model rewards. This is the default answer for a learner's own state.
- **Where it genuinely must be ambient**, use the mechanism that owns that concern — MDC via
  [`kora-aop-logging`](../../kora-aop-logging/SKILL.md) for log correlation, or an
  `HttpServerInterceptor` that establishes and clears the state around `chain.process(request)`.
- **The primitive underneath both is JDK `ScopedValue`**, and that is what actually replaced
  `Context` inside the framework — worth showing, because it is the honest answer to "so where did
  the ambient state go?".

Kora's own `Principal` is the readable example (`io.koraframework.common.Principal`, verified at
`2.0.0.RC2`):

```java
public interface Principal {
    ScopedValue<Principal> VALUE = ScopedValue.newInstance();

    @Nullable
    static Principal current() { return VALUE.isBound() ? VALUE.get() : null; }

    static <T, X extends Throwable> T with(Principal principal, ScopedValue.CallableOp<T, X> op) throws X {
        return ScopedValue.where(VALUE, principal).call(op);
    }
}
```

The generated OpenAPI security interceptor publishes the principal with
`return Principal.with(principal, () -> chain.process(request));` and a handler reads it back with
`Principal.current()`. The same idiom carries telemetry — `Observation.VALUE`,
`OpentelemetryContext.VALUE`, `MDC.VALUE` — and the JDBC executor's connection context.

**The lifetime is the teaching point.** A `ScopedValue` binding lasts exactly as long as the
`call(...)` it wraps — here, `chain.process(request)`. It is visible on the request thread and on
forks of a `StructuredTaskScope` opened inside that scope, and it is **not** visible on work handed
to an arbitrary executor. Unlike a `ThreadLocal` it cannot leak past its scope, because nothing is
left behind to clear.

For an authenticated principal specifically, do not hand-roll any of this: 2.0 has a first-class
path — an `HttpServerPrincipalExtractor` producing a `Principal` that the handler receives as a
parameter — see [`kora-http-server-auth`](../../kora-http-server-auth/SKILL.md).

**Do not accept "let me just make a small holder class with a `ThreadLocal`" as the lesson's
outcome.** Say what it costs: it reintroduces implicit state that the framework no longer manages or
propagates, nothing will clear it for you, and on virtual threads a per-request `ThreadLocal` is
retained for the life of every request thread. `ScopedValue` is the primitive that replaced it, and
an explicit parameter is better than either.

---

## 3. Identity, coordinates and toolchain

| | Kora 1.x | Kora 2.0 |
|---|---|---|
| Group | `ru.tinkoff.kora` | **`io.koraframework`** |
| BOM | `ru.tinkoff.kora:kora-parent` | **`io.koraframework:kora-bom`** |
| Version | 1.x | **`2.0.0.RC2`**, published to plain `mavenCentral()` |
| Java | 17 / 21 | **25 minimum** (artifacts are class-file 69) |
| Kotlin / KSP | 1.9.x | **2.4.20 / 2.3.12** |
| Gradle | 8.x | **9.7.1** (the framework's wrapper) |
| DI annotations | `ru.tinkoff.kora.common.annotation` | **`io.koraframework.common.annotation`** |
| Every framework package | `ru.tinkoff.kora.*` | `io.koraframework.*` |

`2.0.0-SNAPSHOT` is the `master` development line, not something to put in a learner's first
project — it needs the snapshot repository (`https://central.sonatype.com/repository/maven-snapshots`)
or a local `publishToMavenLocal`. Teach `2.0.0.RC2`.

Artifacts left over in the `io/koraframework/` listing on Maven Central from the alpha era —
`kora-parent`, `cache-redis`, `scheduling-ksp` and a few others — are **not** constrained by the 2.0
BOM. If a learner's dependency resolves to one of them, the build file is wrong.

New in 2.0 and worth introducing once the basics land: `@Conditional` (with `GraphCondition`) and
`@FactoryModule`, both in `io.koraframework.common.annotation`.

---

## 4. Integrations that no longer exist

Do not teach these, and recognise them in a learner's existing code as things that must be replaced:

| Gone | What to teach instead |
|---|---|
| `database-r2dbc` | JDBC on virtual threads — [`kora-database-jdbc`](../../kora-database-jdbc/SKILL.md). There is no reactive relational path in 2.0 |
| `database-vertx`, `vertx-*` | as above |
| `http-client-async` | `http-client-ok`, `http-client-jdk`, or `http-client-apache` |
| `s3-client-minio` | `io.koraframework:s3-client-aws` (SDK wrapper) or `io.koraframework.experimental:s3-client-kora` (declarative `@S3`) — [`kora-s3`](../../kora-s3/SKILL.md) |
| `json-module` | `json-common` — same idea, new artifact and package |
| RapiDoc for the OpenAPI UI | `scalar` — [`kora-openapi-management`](../../kora-openapi-management/SKILL.md) |
| OpenAPI generator modes `java-reactive-*`, `kotlin-suspend-*`, `kotlin-reactive-*` | only `java-client`, `java-server`, `kotlin-client`, `kotlin-server` remain |

---

## 5. Renames a 1.x learner will reach for by habit

Concise map. Each has a domain sub-skill with the full treatment; the point here is recognition.

| 1.x | 2.0 | Domain skill |
|---|---|---|
| `@ConfigValueExtractor` | `@ConfigMapper` (no type parameter) | [`kora-config-hocon`](../../kora-config-hocon/SKILL.md) |
| `extractor.extract(value)` | `mapper.map(value)` (nullable) / `mapOrThrow(value)` | " |
| `extractor.map(fn)` — *composition* | `andThen(fn)` | " |
| `@Environment`, `@SystemProperties` | `@EnvironmentConfig`, `@SystemPropertiesConfig` | " |
| config section `db { … }` | `jdbc { … }` | [`kora-database-jdbc`](../../kora-database-jdbc/SKILL.md) |
| `publicApiHttpPort`, `privateApiHttpPort` | `port`, `system.port` | [`kora-http-server`](../../kora-http-server/SKILL.md) |
| `privateApiHttpMetricsPath` etc. | `system.metricsPath`, `system.readinessPath`, `system.livenessPath` | " |
| `@Tag(HttpServerModule.class)` on a global interceptor | `@Tag(HttpServer.class)` | " |
| `@HttpClient(configPath = "x")` | `@HttpClient("x")` | [`kora-http-client`](../../kora-http-client/SKILL.md) |
| `getXConnectionFactory()` | `executor()`, carrying `inTx(...)` | [`kora-database-jdbc`](../../kora-database-jdbc/SKILL.md) |
| `database.jdbc.EntityJdbc` | `database.jdbc.annotation.EntityJdbc` | " |
| `@CircuitBreaker("n")`, `@Retry("n")` | `@CircuitBreakable(X.class)`, `@Retryable(X.class)` | [`kora-aop-resilient`](../../kora-aop-resilient/SKILL.md) |
| `slidingWindowSize` | `countBased.windowSize` + a window `type` | " |
| `@Fallback(value = "n", method = "m()")` | `@Fallback(method = "m()")` — `value` removed | " |
| `@Cacheable(parameters = "id")` | `@Cacheable(args = "id")` | [`kora-aop-caching`](../../kora-aop-caching/SKILL.md) |
| `@CacheInvalidate(invalidateAll = true)` | `@CacheInvalidateAll(X.class)` | " |
| `toStringUnchecked`, `readUnchecked` | `toString`, `read` — and they no longer declare checked exceptions | [`kora-json`](../../kora-json/SKILL.md) |
| `@ScheduleAtFixedRate`, `@ScheduleWithFixedDelay`, `@ScheduleOnce` | `@ScheduleJdkAtFixedRate`, `@ScheduleJdkWithFixedDelay`, `@ScheduleJdkOnce` — same `jdk.annotation` package | [`kora-aop-scheduling-jdk`](../../kora-aop-scheduling-jdk/SKILL.md) |
| Quartz `@ScheduleWithCron` | `@ScheduleQuartzWithCron`, package `scheduling.quartz.annotation` | [`kora-aop-scheduling-quartz`](../../kora-aop-scheduling-quartz/SKILL.md) |
| `@ScheduleWithTrigger(@Tag(MyJob.class))` | `@ScheduleQuartzWithTrigger(MyJob.class)` | " |
| `openapi.management.file` | `files` (a list) | [`kora-openapi-management`](../../kora-openapi-management/SKILL.md) |

Two of these change **meaning** rather than spelling, so a mechanical rename is actively dangerous:
`map` on a config extractor (extraction in 2.0, composition in 1.x), and `@Tag(HttpServerModule.class)`
(still compiles, never invoked).

---

## 6. Nullability

Java moved to **JSpecify**: `org.jspecify.annotations.Nullable` / `@NonNull` / `@NullMarked`. These
are **type-use** annotations, so position is part of the meaning:

```java
Outer.@Nullable Inner field;      // the Inner is nullable
List<@Nullable String> items;     // elements are nullable
String @Nullable [] array;        // the array is nullable
@Nullable String[] other;         // the elements are nullable
```

The wrong position is a compile error —
`type annotation @org.jspecify.annotations.Nullable is not expected here` — which reads as a tooling
problem to someone who has never met type-use annotations. Say what it means.

In Kotlin nullability is the type (`T?`). Do not carry the Java annotations across;
`@field:Nullable` is not a valid target under Kotlin 2.4.

---

## 7. "It compiles" is not "it works"

Read this together with §4 of the [meta-skill](../../../SKILL.md), which lists every case with the
source that establishes it. The teaching point for a 1.x learner is narrower and sharper:

**The 1.x forms that fail loudly are the easy ones.** `ru.tinkoff.kora` imports, string-named
resilience annotations and removed artifacts all stop the build, and a learner fixes them in
minutes. The dangerous residue is the set of 1.x forms that still compile:

1. `@Tag(HttpServerModule.class)` — the class still exists; the interceptor silently never runs.
2. `publicApiHttpPort` / `privateApiHttpPort` — unknown HOCON keys are ignored without a warning, so
   the service comes up green on 8080/8085 instead of the configured ports.
3. Telemetry left at its defaults while an example claims to demonstrate metrics or request logging —
   both are **off** by default in 2.0.
4. A tracing exporter with no `endpoint`. `tracing.enabled` defaults to **true**, spans are still
   created, and `spanExporter`/`spanProcessor` quietly return a no-op `composite()`. Nothing is
   exported and nothing says so. (A circuit breaker missing `countBased` is *not* on this list: it
   fails loudly with `IllegalArgumentException: CircuitBreaker '<name>' property 'countBased' is
   not configured`.)
5. A redundant `@Component` on a mapper. The generated code builds a mapper **inline** only when
   all three hold: it is named by `@Mapping` / `@ResponseCodeMapper(mapper = …)`, the class is
   `final` in Java (not `open` in Kotlin) with a single public no-arg constructor, and no `@Tag` is
   involved. Everything else — a mapper resolved by type, a request mapper, an `@InterceptWith`
   interceptor, a non-final class with a no-arg constructor — is a constructor parameter of the
   generated class and *must* be a `@Component`. Getting that direction wrong fails loudly with
   `No component found`. The **quiet** one is the opposite: an unnecessary `@Component` on a
   self-instantiable mapper sits there harmlessly until something actually resolves that type from
   the graph, and only then becomes `Multiple components match` — so it survives review and
   surfaces later, in a change that looks unrelated.

For every one of these the acceptance criterion is a **test or an observed response**, never a
successful build. That single sentence is the most valuable thing this reference contains.

---

## 8. Where to look things up

Kora 2.0 has its own documentation at <https://koraframework.io/v2/en/> (ru: `/v2/ru/`), built from
the `kora-docs` branch `feature/kora-2.0`, `mkdocs/docs/v2/`. It is written for `io.koraframework`
and is the right first read for a concept. It trails the framework, though, so a key, default or
signature a learner will depend on is checked in the source. The 1.x site
(`kora-projects.github.io/kora-docs`, `docs/v1`) is 1.x conceptual background and nothing else.

| Question | Where the answer is |
|---|---|
| What is this feature for, and how is it meant to be used? | Kora 2.0 docs — <https://koraframework.io/v2/en/> |
| Does this API exist, and what is its signature? | framework source at tag `2.0.0.RC2` — <https://github.com/kora-projects/kora/tree/2.0.0.RC2> |
| How is this wired in a working application? | <https://github.com/kora-projects/kora-examples/tree/migration/2.0> — the **code and build files**, not the per-app README, which still links to the 1.x site |
| What did Kora generate for my code? | your own `build/generated/sources/annotationProcessor/` (Java) or `build/generated/ksp/` (Kotlin) |
| What is the vetted pattern for domain X? | the domain sub-skill in this package |

All three are placed on disk by **R0** in the [meta-skill](../../../SKILL.md), as
`.kora-agent/kora-source-2.0/`, `.kora-agent/kora-examples-2.0/` and `.kora-agent/kora-docs-2.0/`.
