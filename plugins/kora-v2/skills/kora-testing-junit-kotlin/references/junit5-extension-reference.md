# Kora JUnit 5 Extension — config and graph modifiers (Kotlin, Kora 2.x)

Verified against
[`KoraConfigModification`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/test/test-junit5/src/main/java/io/koraframework/test/extension/junit5/KoraConfigModification.java),
[`KoraGraphModification`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/test/test-junit5/src/main/java/io/koraframework/test/extension/junit5/KoraGraphModification.java),
[`KoraAppGraph`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/test/test-junit5/src/main/java/io/koraframework/test/extension/junit5/KoraAppGraph.java)
and `KoraJUnit5Extension`, plus the framework's own Kotlin test
`kotlin/mockk/MockkGraphModificationTests.kt` and the migrated Kotlin examples.

Annotation basics (`@KoraAppTest`, `@TestComponent`, `@Tag`, lifecycle) are in
[korapptest-kotlin-reference.md](korapptest-kotlin-reference.md).

## Contents

- [Both modifiers are class-level only](#both-modifiers-are-class-level-only)
- [KoraAppTestConfigModifier](#koraapptestconfigmodifier)
- [2.0 config keys inside `ofString`](#20-config-keys-inside-ofstring)
- [KoraAppTestGraphModifier](#koraapptestgraphmodifier)
- [KoraGraphModification API](#koragraphmodification-api)
- [Kotlin SAM and nullability traps](#kotlin-sam-and-nullability-traps)
- [Choosing between a mock annotation and a graph modifier](#choosing-between-a-mock-annotation-and-a-graph-modifier)

---

## Both modifiers are class-level only

`KoraAppTestConfigModifier` and `KoraAppTestGraphModifier` are implemented by the **test class**.
They cannot be combined with constructor `@TestComponent` injection: the graph is created while
constructor parameters resolve, before the test instance exists, so the extension fails fast with

```
Cannot use KoraAppTestConfigModifier with @KoraAppTest constructor injection in:
  com.example.MyTest
```

Constructor parameters resolved by *other* extensions are fine — the migrated `kora-kotlin-crud`
`IntegrationTests` takes a Testcontainers `JdbcConnection` in its constructor and still implements
`KoraAppTestConfigModifier`.

---

## `KoraAppTestConfigModifier`

```kotlin
interface KoraAppTestConfigModifier {
    fun config(): KoraConfigModification
}
```

Three factories, and they are not interchangeable:

| Factory | What it does |
|---|---|
| `KoraConfigModification.ofSystemProperty(key, value)` | sets system properties only — the application's own `application.conf` still loads, and its `${VAR}` placeholders resolve from them |
| `KoraConfigModification.ofResourceFile("application-test.conf")` | sets `config.resource` — the named classpath file **replaces** the application config |
| `KoraConfigModification.ofString("""…""")` | writes the text to a temp file and sets `config.file` — also **replaces** the application config; `${VAR}` placeholders still work |

All three chain `withSystemProperty(key, value)` / `withSystemProperties(map)`. The extension
snapshots `System.getProperties()` before setup and restores it afterwards, so the properties do not
leak into other test classes.

### Placeholder substitution — the Testcontainers idiom

```kotlin
override fun config(): KoraConfigModification =
    KoraConfigModification.ofString(
        """
        jdbc {
          jdbcUrl = ${'$'}{POSTGRES_JDBC_URL}
          username = ${'$'}{POSTGRES_USER}
          password = ${'$'}{POSTGRES_PASS}
          poolName = "kora-test"
        }
        """.trimIndent()
    )
        .withSystemProperty("POSTGRES_JDBC_URL", POSTGRES.jdbcUrl)
        .withSystemProperty("POSTGRES_USER", POSTGRES.username)
        .withSystemProperty("POSTGRES_PASS", POSTGRES.password)
```

In a Kotlin raw string, `${'$'}{VAR}` is how a literal `${VAR}` reaches HOCON. Interpolating the
value directly (`jdbcUrl = "${connection.params().jdbcUrl()}"`) is equally valid and is what
`kora-kotlin-crud` and `kora-kotlin-petclinic` do — quote it, because a raw JDBC URL contains
characters HOCON would otherwise parse.

### Only one modifier per class

Config modifications are merged in declaration order, each overriding the previous. A class that
somehow ends up with two sources of truth for the same key is a debugging trap; keep one `config()`.

---

## 2.0 config keys inside `ofString`

HOCON embedded in Kotlin source is invisible to any scanner that only reads `.conf`/`.yaml`, which
is why 1.x keys survive there. Check every `ofString` block against this list.

| Wrong (1.x) | Right (2.0) | Failure mode |
|---|---|---|
| `db { jdbcUrl = … }` | `jdbc { jdbcUrl = … }` | `ConfigValueException: Config expected value, but got null at path: 'ROOT.jdbc.username'` |
| `publicApiHttpPort = 8081` | `httpServer.port = 8081` | unknown key, silently ignored — the public server falls back to **8080** |
| `privateApiHttpPort = 8082` | `httpServer.system.port = 8082` | unknown key, silently ignored — `SystemHttpServerConfig` overrides `port()` to **8085** |
| `privateApiHttpReadinessPath` / `…LivenessPath` / `…MetricsPath` | `httpServer.system.readinessPath` / `livenessPath` / `metricsPath` | probes answer on the default paths, scrapers hit nothing |
| `resilient.circuitbreaker.x { slidingWindowSize = 10 }` | `resilient.circuitbreaker.x { type = FIXED_WINDOW; countBased.windowSize = 10 }` | `countBased` is `@Nullable` in the interface, but `KoraCircuitBreaker`'s constructor calls `CircuitBreakerConfig.validate(...)`, so graph init fails with `IllegalArgumentException: CircuitBreaker 'x' property 'countBased' is not configured`. `type` itself is optional (default `STRIPED_APPROX`) — it is `countBased` that is mandatory for every non-`TIME_BASED` type |
| assuming metrics/logs are on | `telemetry.logging.enabled = true` / `telemetry.metrics.enabled = true` per component | both default to `false`; a test asserting on them passes vacuously or fails for the wrong reason |

A verified circuit-breaker block, from the migrated `kora-kotlin-crud` `ComponentTests`:

```kotlin
override fun config(): KoraConfigModification = KoraConfigModification.ofString(
    """
    resilient {
      circuitbreaker.pet {
        type = FIXED_WINDOW
        countBased.windowSize = 2
        minimumRequiredCalls = 2
        failureRateThreshold = 100
        permittedCallsInHalfOpenState = 1
        waitDurationInOpenState = 15s
      }
      timeout.pet.duration = 5000ms
      retry.pet {
        delay = 100ms
        attempts = 0
      }
    }
    """.trimIndent()
)
```

Named `resilient` sections no longer inherit from a `default` section — each stands alone.

---

## `KoraAppTestGraphModifier`

```kotlin
interface KoraAppTestGraphModifier {
    fun graph(): KoraGraphModification
}
```

Use it when a plain mock annotation cannot express the replacement: a generic type, a tagged
component, or a replacement that has to wrap the original.

```kotlin
@KoraAppTest(TestApplication::class)
class GraphModificationTests : KoraAppTestGraphModifier {

    @TestComponent lateinit var mock1: TestComponent1

    @Tag(LifecycleComponent::class)
    @TestComponent lateinit var mock2: TestComponent2

    override fun graph(): KoraGraphModification =
        KoraGraphModification.create()
            .replaceComponent(TestComponent1::class.java, Supplier { mockkClass(TestComponent1::class) })
            .replaceComponent(
                TestComponent2::class.java, LifecycleComponent::class.java,
                Supplier { mockkClass(TestComponent2::class) },
            )

    @Test
    fun mockFromGraph() {
        every { mock1.get() } returns "?"
        assertEquals("?", mock1.get())
    }
}
```

---

## `KoraGraphModification` API

Every method takes `java.lang.reflect.Type` as the first argument, an optional
`tag: Class<*>?` as the **second** argument, and a factory as the last. There is no list-of-tags
overload — a single tag class, or nothing.

`factory` has two shapes, and `addComponent`/`replaceComponent` are each overloaded on both:

- `Supplier<T>` — no access to the graph;
- `Function<KoraAppGraph, T>` — receives the graph so the replacement can build on the original.

| Method | Factory | Effect on the replaced node's dependencies |
|---|---|---|
| `addComponent(type[, tag], factory)` | `Supplier` or `Function` | n/a — adds a new node with no dependencies |
| `replaceComponent(type[, tag], factory)` | **`Supplier`** | dependencies **dropped** (`ApplicationGraphDraw.replaceNode`) |
| `replaceComponent(type[, tag], factory)` | **`Function<KoraAppGraph, T>`** | dependencies **kept** (`replaceNodeKeepDependencies`) |
| `mockComponent(type[, tag], factory)` | `Supplier` only | dependencies **dropped** |

> The Javadoc on `replaceComponent` says "keeps its dependencies in graph" unconditionally; the code
> does not. Only the `Function<KoraAppGraph, T>` overloads call `replaceNodeKeepDependencies` — the
> `Supplier` overloads of `replaceComponent` and every `mockComponent` overload build the same
> `GraphReplacementNoDeps` and clear the node's create/refresh dependencies. Read: if the original
> component's dependencies must still be constructed (a `Lifecycle` that has to start, a migration
> runner), take the `Function` form even when you ignore the argument.

Passing `null` for `tag` is accepted and falls through to the untagged overload.

```kotlin
override fun graph(): KoraGraphModification =
    KoraGraphModification.create()
        // generic type: TypeRef implements ParameterizedType, so it is a valid Type
        .addComponent(TypeRef.of(Supplier::class.java, Int::class.java), Supplier { Supplier { 1 } })
        // derive from the existing component
        .replaceComponent(TypeRef.of(Supplier::class.java, Int::class.java)) { graph ->
            @Suppress("UNCHECKED_CAST")
            val existing = requireNotNull(graph.getFirst(TypeRef.of(Supplier::class.java, Int::class.java))) as Supplier<Int>
            Supplier { 1 + existing.get() }
        }
```

`TypeRef` is `io.koraframework.application.graph.TypeRef`; `TypeRef.of(raw, vararg args)` builds the
parameterized type.

---

## Kotlin SAM and nullability traps

**Ambiguous overloads need an explicit SAM constructor.** Because `Supplier<T>` and
`Function<KoraAppGraph, T>` are both functional interfaces on the same parameter position, a bare
zero-argument lambda does not disambiguate. Write `Supplier { … }` explicitly — that is what the
framework's own Kotlin test does. A one-parameter trailing lambda (`{ graph -> … }`) is unambiguous
and maps to the `Function` overload.

**`KoraAppGraph.getFirst` is nullable.** The extension package is `@NullMarked` and every `getFirst`
overload carries JSpecify `@Nullable`, so Kotlin sees a nullable type. `requireNotNull(...)` before
casting; a bare `as Supplier<Int>` on `null` throws an unhelpful NPE.

**Kotlin test doubles must match contract nullability.** Kora 2.0 API is `@NullMarked`, and Kotlin
checks overrides strictly while Java does not. A fake registered through `addComponent` that
implements a Kora contract has to spell out the `@Nullable` positions as `T?`:

```kotlin
class RecordingResponseMapper : HttpServerResponseMapper<Pet> {
    // the contract declares the result @Nullable, so Kotlin must accept null here
    override fun apply(request: HttpServerRequest, result: Pet?): HttpServerResponse {
        requireNotNull(result)
        return HttpServerResponse.of(200, HttpBody.plaintext(result.name))
    }
}
```

With `result: Pet` the compiler reports `'apply' overrides nothing` — a message that never mentions
nullability, so it reads like a generics mistake. **This is a Java/Kotlin asymmetry: the Java twin of
the same fake compiles.**

Do not carry JSpecify or `jakarta.annotation` `@Nullable` into Kotlin sources; `@field:Nullable` is
an invalid target under Kotlin 2.4. Nullability is the type.

---

## Choosing between a mock annotation and a graph modifier

| Situation | Reach for |
|---|---|
| Replace one dependency with a mock, keep the rest real | `@field:MockK` (or `@Mock`) + `@TestComponent` |
| Partial mock keeping real behaviour | `@field:SpyK` (or `@Spy`) + `@TestComponent` |
| The type is generic (`Supplier<Int>`, `Cache<K, V>`) | `KoraGraphModification` with `TypeRef.of(...)` |
| The replacement must wrap or delegate to the original | `replaceComponent(type) { graph -> … }` |
| The component is not declared in the `@KoraApp` at all | `addComponent(...)`, or the `TestApplication` submodule pattern for anything Kora must *generate* |
| The real component's dependencies must not be built | `mockComponent(...)` |
