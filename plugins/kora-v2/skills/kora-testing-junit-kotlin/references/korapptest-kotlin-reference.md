# `@KoraAppTest` for Kotlin (Kora 2.x)

Verified against the Kora 2.0 sources —
[`test/test-junit5`](https://github.com/kora-projects/kora/tree/2.0.0.RC2/test/test-junit5)
(including its own Kotlin tests under `src/test/kotlin/.../kotlin/mockk`) — and the migrated
[`kora-kotlin-guide-testing-junit-app`](https://github.com/kora-projects/kora-examples/tree/migration/2.0/guides/kotlin/kora-kotlin-guide-testing-junit-app),
[`kora-kotlin-guide-testing-integration-app`](https://github.com/kora-projects/kora-examples/tree/migration/2.0/guides/kotlin/kora-kotlin-guide-testing-integration-app)
and [`kora-kotlin-crud`](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/kotlin/kora-kotlin-crud)
examples.

## Contents

- [Dependency](#dependency)
- [@KoraAppTest](#koraapptest)
- [@TestComponent](#testcomponent)
- [Tag injection](#tag-injection)
- [Injecting Graph and KoraAppGraph](#injecting-graph-and-koraappgraph)
- [Mock annotations and use-site targets](#mock-annotations-and-use-site-targets)
- [Graph lifecycle](#graph-lifecycle)
- [Extension errors, verbatim](#extension-errors-verbatim)
- [Best practices](#best-practices)

---

## Dependency

```kotlin
dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

    testImplementation(platform("org.junit:junit-bom:${property("junitVersion")}"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testImplementation("io.koraframework:test-junit5")
}
```

`test-junit5` declares `api junit-jupiter` and `api junit-platform-launcher`, so JUnit arrives even
without the BOM; declaring the BOM keeps the version aligned with the rest of the build.
`mockito-core`, `mockk` and `kotlin-reflect` are `compileOnly` in `test-junit5` — the test module
supplies whichever mocking engine it uses.

The module under test needs a config format module on the **test** runtime classpath. When the app
is a separate Gradle project pulled in with `testImplementation(project(":…"))`, its `implementation`
dependencies do not leak, so add `io.koraframework:config-hocon` (or `config-yaml`) explicitly — the
migrated guide apps do exactly that.

---

## `@KoraAppTest`

`io.koraframework.test.extension.junit5.KoraAppTest`, meta-annotated `@ExtendWith(KoraJUnit5Extension::class)`,
`@Target(TYPE)`, `@Retention(RUNTIME)`.

| Attribute | Type | Required | Meaning |
|---|---|---|---|
| `value` | `KClass<*>` | yes | the interface annotated with `@KoraApp` |
| `components` | `Array<KClass<*>>` | no | extra components to initialize in addition to the `@TestComponent`s found in the test |
| `modules` | `Array<KClass<*>>` | no | extra modules whose factory methods join the test graph — **entries must be interfaces**, otherwise `Invalid @KoraAppTest module` |

```kotlin
@KoraAppTest(Application::class)
class SimpleTest {
    @TestComponent lateinit var userService: UserService
}

@KoraAppTest(
    value = TestApplication::class,
    components = [TestComponent23::class],
    modules = [SomeModule::class],
)
class WiderTest
```

At runtime the extension loads `<value.name>Graph`, verifies it is a `Supplier<ApplicationGraphDraw>`,
`copy()`s the draw, prunes it down to the roots the test declares, then initializes it. A Kotlin
interface listed in `modules` has **all** its declared methods treated as factories (the extension
detects `kotlin.Metadata` and skips the Java "default methods only" filter).

---

## `@TestComponent`

`io.koraframework.test.extension.junit5.TestComponent`, `@Target(FIELD, PARAMETER)`. It injects a
component from the graph **and** makes it a root of the test graph slice.

```kotlin
// field
@KoraAppTest(Application::class)
class FieldTest {
    @TestComponent lateinit var userService: UserService
}

// constructor
@KoraAppTest(Application::class)
class CtorTest(@TestComponent val userService: UserService)

// test-method parameter
@KoraAppTest(Application::class)
class MethodTest {
    @Test fun example(@TestComponent userService: UserService) { /* ... */ }
}
```

Rules enforced by the extension:

1. A component must exist in the compiled graph draw. Kora prunes at compile time, so anything the
   `@KoraApp` does not reach — a test-only repository, a `Lifecycle` that nothing depends on — must
   be marked `@Root` (directly, or through a `@Root` that depends on it) or listed in
   `@KoraAppTest(components = [...])`.
2. Injected fields may be neither `static` nor `final`. Use `lateinit var`, or constructor injection.
3. The same `@TestComponent` may not also be a mock, nor both a mock and a spy.
4. **Constructor injection locks the graph in.** Once constructor parameters resolve the graph,
   `@TestComponent` and mock annotations on test-method parameters are rejected, and
   `KoraAppTestConfigModifier`/`KoraAppTestGraphModifier` cannot be implemented at all.

---

## Tag injection

Repeat the component's `@Tag` (`io.koraframework.common.annotation.Tag`) at the injection point:

```kotlin
@KoraAppTest(TestApplication::class)
class TaggedTest {

    @MockK
    @Tag(LifecycleComponent::class)
    @TestComponent
    lateinit var tagged: TestComponent2

    @Test
    fun example(
        @Tag(LifecycleComponent::class) @MockK @TestComponent mock: TestComponent2,
        @TestComponent consumer: TestComponent23,
    ) {
        every { mock.get() } returns "?"
        assertEquals("?3", consumer.get())
    }
}
```

Without the tag, a type with several tagged implementations fails with
`Expected one matching graph component, but found N`.

---

## Injecting `Graph` and `KoraAppGraph`

`io.koraframework.application.graph.Graph` and `io.koraframework.test.extension.junit5.KoraAppGraph`
resolve as test-method parameters **without** `@TestComponent`:

```kotlin
@Test
fun graphIsPruned(graph: Graph) {
    assertEquals(2, graph.draw().size())
}
```

Annotating either with a mock annotation is refused (`Cannot mock Kora graph object`).

`KoraAppGraph` is the lookup facade used by graph modifiers. Its package is `@NullMarked` and every
`getFirst` overload is `@Nullable`, so **in Kotlin the result is a nullable type** — unwrap it:

```kotlin
val existing = requireNotNull(graph.getFirst(TestComponent1::class.java))
```

`getAll(...)` returns a (non-null) `List`.

---

## Mock annotations and use-site targets

The extension recognises four annotations by fully-qualified name and never requires the matching
JUnit extension:

| Annotation | Engine |
|---|---|
| `org.mockito.Mock` | Mockito |
| `org.mockito.Spy` | Mockito |
| `io.mockk.impl.annotations.MockK` | MockK |
| `io.mockk.impl.annotations.SpyK` | MockK |

It looks for them on the JVM **field** and, additionally, on the Kotlin **property** — the property
path goes through `kotlin.reflect.jvm.ReflectJvmMapping` and is only taken when `kotlin-reflect` is
on the test classpath. Since `test-junit5` declares `kotlin-reflect` `compileOnly`, Kora does not put
it there.

Consequence for Kotlin:

- **`@field:MockK` / `@field:SpyK`** — targets the field, always seen. This is what the migrated
  `kora-kotlin-crud` example and most of the framework's own Kotlin tests use. Prefer it.
- **Bare `@MockK` / `@SpyK`** — MockK's annotations also accept a Kotlin `PROPERTY` target, so the
  bare form lands on the property and is only discovered when `kotlin-reflect` is present. The
  framework covers this path in a test literally named `mockkOnProperty`; when it is missing you get
  the real component injected, with no error.
- **`@Mock` / `@Spy`** — Java annotations with no `PROPERTY` target, so they land on the field on
  their own. No `@field:` prefix needed.

Never add `= mockk()` next to the annotation and never attach `MockKExtension`/`MockitoExtension`:
`@KoraAppTest` creates the mocks, injects them into both the test and the graph, and clears them
between tests (`clearMocks` for MockK, `Mockito.reset` for Mockito).

---

## Graph lifecycle

**PER_METHOD (default).** The graph is rebuilt for every `@Test` method.

**PER_CLASS.** One graph for the whole class:

```kotlin
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
@KoraAppTest(Application::class)
class FastTests
```

Two restrictions come with it, both enforced:

- mocks declared as **test-method parameters** are rejected — one graph is shared, a parameter mock
  is per-method;
- `@TestComponent` **fields inside a `@Nested` class** of that outer test are rejected — the outer
  graph is already initialized and a nested field cannot change it. Move the fields to the outer
  class, or use `PER_METHOD`.

---

## Extension errors, verbatim

These messages come from `KoraJUnit5Extension` / `TestExtensionErrors`; match on them rather than
guessing.

| Message | Meaning |
|---|---|
| `Cannot find generated Kora application graph for: <App>` | `<App>Graph` was not generated — see the `kspTest` / `kora.app.submodule.enabled` rule in [SKILL.md](../SKILL.md) |
| `Cannot inject Kora component: … No matching component was found in the application graph.` | pruned component, or a `@Tag` mismatch |
| `Expected one matching graph component, but found N` | ambiguous type — add or correct `@Tag` |
| `Cannot create @MockK for … No matching component was found` | the mocked type is not in the graph at all |
| `Cannot create @MockK using MockK for component: … Component type does not resolve to a raw class.` | the candidate is not a `Class` or `ParameterizedType` |
| `Cannot inject @TestComponent into field: … Injected fields cannot be static.` / `… cannot be final.` | use `lateinit var` or constructor injection |
| `Cannot use KoraAppTestConfigModifier with @KoraAppTest constructor injection in: …` | modifier + constructor `@TestComponent`; move injection to fields/method parameters |
| `Cannot inject mocks through test method parameters with TestInstance.Lifecycle.PER_CLASS.` | see the PER_CLASS restrictions above |
| `IllegalArgumentException: Graph node belongs to another application graph: node index …` at graph init | a `@Conditional` node in the test graph — `copy()`/`subgraph()` keep its original condition; fixed in `2.0.0.RC2` (kora-projects/kora PR #963) — only `2.0.0.RC1` is affected, no practical workaround on RC1 |
| `PER_CLASS`: `beforeEach` fails in `resetMocks` with `…because condition failed: <reason>` | the mock reset (MockK or Mockito present) reads every node, including a condition-failed one; `KoraAppGraph.getAll` too. Fixed in `2.0.0.RC2` (kora-projects/kora PR #964) — only `2.0.0.RC1` is affected; on RC1 use `PER_METHOD` |
| `Cannot inject @TestComponent fields into @Nested class: …` | same |
| `Cannot use @TestComponent or mock annotations on test method parameters after constructor injection initialized @KoraAppTest.` | pick one initialization origin |
| `@TestComponent cannot be declared as both component and mock: …` | remove one of the annotations |
| `Invalid @KoraAppTest module: … Entries in @KoraAppTest(modules = ...) must be interfaces.` | pass the module interface, not an implementation |
| `Cannot mock Kora graph object: …` | inject `Graph`/`KoraAppGraph` directly, without a mock annotation |
| `@KoraAppTest not found for: …` | the extension ran on a class that is not annotated (usually an inherited `@ExtendWith`) |

---

## Best practices

1. `@field:MockK` + `@TestComponent`, no `= mockk()`, no `MockKExtension`.
2. `@TestInstance(PER_CLASS)` for suites that do not need a fresh graph per method — but keep mocks
   as fields, not method parameters.
3. Keep every `@TestComponent` reachable from a `@Root`; that is what `TestApplication` is for.
4. Prefer field or method-parameter injection over constructor injection whenever the test also
   implements a config or graph modifier — the two are mutually exclusive.
5. `every`/`verify`, never `coEvery`/`coVerify`, against Kora contracts — they are synchronous in 2.0.
