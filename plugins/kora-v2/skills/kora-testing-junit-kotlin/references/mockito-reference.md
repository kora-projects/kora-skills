# Mockito / Mockito-Kotlin with `@KoraAppTest` (Kora 2.x)

Verified against
[`GraphMockitoMock`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/test/test-junit5/src/main/java/io/koraframework/test/extension/junit5/GraphMockitoMock.java),
[`GraphMockitoSpy`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/test/test-junit5/src/main/java/io/koraframework/test/extension/junit5/GraphMockitoSpy.java),
[`MockitoStrictness`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/test/test-junit5/src/main/java/io/koraframework/test/extension/junit5/mockito/MockitoStrictness.java),
`MockitoUnusedStubbingReporter`, the version catalog
[`gradle/libs.versions.toml`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/gradle/libs.versions.toml),
and the migrated
[`kora-kotlin-guide-testing-junit-app`](https://github.com/kora-projects/kora-examples/tree/migration/2.0/guides/kotlin/kora-kotlin-guide-testing-junit-app)
and
[`kora-kotlin-crud-submodule`](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/kotlin/kora-kotlin-crud-submodule)
examples.

Mockito is the alternative to [MockK](mockk-reference.md) — pick it for a mixed Java/Kotlin codebase
or a team already standardized on it. The Kora extension wires `@Mock`/`@Spy` into the graph exactly
as it does MockK mocks. Both engines are detected by class presence, so a module can even have both
on the classpath; keep one per module anyway.

## Contents

- [Dependencies and the mockito-core pin](#dependencies-and-the-mockito-core-pin)
- [@Mock + @TestComponent](#mock--testcomponent)
- [@Spy](#spy)
- [@MockitoStrictness](#mockitostrictness)
- [Patterns](#patterns)
- [Troubleshooting](#troubleshooting)

---

## Dependencies and the mockito-core pin

```kotlin
// Mockito alone, as in the Kotlin JUnit guide app
testImplementation("org.mockito:mockito-core:5.24.0")
```

```kotlin
// With the Kotlin helpers: mockito-kotlin pulls its OWN, older mockito-core,
// whose Byte Buddy rejects Java 25 class files — pin mockito-core next to it
testImplementation("org.mockito:mockito-core:5.18.0")
testImplementation("org.mockito.kotlin:mockito-kotlin:5.4.0")
```

| Source | `mockito-core` | `mockito-kotlin` |
|---|---|---|
| Kora 2.0 version catalog | `5.24.0` | `6.4.0` |
| `kora-kotlin-guide-testing-junit-app` (no Kotlin helpers) | `5.23.0` | — |
| `kora-kotlin-crud-submodule`, `kora-kotlin-camunda-*` | `5.18.0` (explicit pin) | `5.4.0` |

The pin is the point, not the exact number: **whenever `mockito-kotlin` is on the classpath, declare
`mockito-core` explicitly next to it.** The migrated examples carry that reasoning as a comment on
the very line. Without the pin the resolved Byte Buddy is too old for Java 25 and mock creation fails
at runtime inside `Application graph failed to initialize`, with nothing pointing at Byte Buddy.

Confirm what actually resolved:

```
./gradlew <module>:dependencyInsight --dependency byte-buddy --configuration testRuntimeClasspath
```

---

## `@Mock` + `@TestComponent`

`org.mockito.Mock` is a Java annotation with `FIELD` and `PARAMETER` targets and no Kotlin `PROPERTY`
target, so on a Kotlin property it lands on the backing field on its own — **no `@field:` prefix
needed**, unlike MockK.

```kotlin
@KoraAppTest(Application::class)
class UserServiceComponentTest {

    @Mock
    @TestComponent
    lateinit var userRepository: UserRepository

    @TestComponent
    lateinit var userService: UserService

    @Test
    fun createUserShouldCreateAndReturnUser() {
        `when`(userRepository.save("John", "john@example.com")).thenReturn("1")

        val result = userService.createUser(UserRequest("John", "john@example.com"))

        assertEquals("1", result.id)
        verify(userRepository).save("John", "john@example.com")
    }
}
```

That is the migrated Kotlin guide app verbatim: Kotlin's escaped `` `when` `` and plain
`org.mockito.Mockito.verify`. With `mockito-kotlin` on the classpath the matchers get nicer while
stubbing stays Mockito's — which is what `kora-kotlin-crud-submodule` does:

```kotlin
import org.mockito.kotlin.any

Mockito.`when`(petRepository.insert(any())).thenReturn(1L)
Mockito.verify(categoryRepository, Mockito.times(2)).insert(any<String>())
```

Rules are the same as for MockK: `lateinit var`, no `= mock()` initializer, and **no**
`@ExtendWith(MockitoExtension::class)` — `@KoraAppTest` creates the mocks, injects them into the
graph and calls `Mockito.reset` between tests.

The extension honours the per-mock settings on `@Mock`: `name`, `answer`, `mockMaker`,
`extraInterfaces`, `strictness`, `withoutAnnotations`, `stubOnly`, `serializable`.

---

## `@Spy`

Like MockK's `@SpyK`, behaviour depends on whether the field holds a value:

```kotlin
// field has a value -> that instance is spied
@Spy
@TestComponent
var userService: UserService = UserService(realRepository)

// lateinit -> the component the graph builds is spied, dependencies kept
@Spy
@TestComponent
lateinit var userService: UserService
```

Stub with `doReturn(...).when(spy).method()` so the real method is not called while stubbing.

---

## `@MockitoStrictness`

`io.koraframework.test.extension.junit5.mockito.MockitoStrictness` sets the class-wide strictness for
unused-stub reporting.

```kotlin
@MockitoStrictness(Strictness.STRICT_STUBS)
@KoraAppTest(Application::class)
class UserServiceTest {
    @Mock @TestComponent lateinit var userRepository: UserRepository
}
```

| Level | Behaviour |
|---|---|
| `STRICT_STUBS` | unused stubs are reported as failures |
| `WARN` | unused stubs are logged as warnings |
| `LENIENT` | reporting off |

**When the annotation is absent the extension uses `Strictness.WARN`**, not `STRICT_STUBS` — the
Javadoc on the annotation contradicts itself; `KoraJUnit5Extension.findStrictness` is the authority
(`findMockStrictness(context).map(MockitoStrictness::value).orElse(Strictness.WARN)`). Reports are
written through SLF4J (`MockitoUnusedStubbingReporter`), so a suite with logging turned down will not
show them. This is Mockito-only — it has no effect on MockK mocks.

`@Mock(strictness = …)` overrides the class level for a single mock.

---

## Patterns

```kotlin
// consecutive returns
`when`(userRepository.findById("1")).thenReturn(first).thenReturn(second)

// throwing
`when`(userRepository.findById("1")).thenThrow(RuntimeException("Database error"))

// answer computed from the arguments
`when`(cache.put(anyLong(), any())).thenAnswer { it.arguments[1] }

// broad matcher then an exact value
`when`(userRepository.findByEmail(any())).thenReturn(generic)
`when`(userRepository.findByEmail(eq("specific@example.com"))).thenReturn(specific)

// verification
verify(userRepository).findById("1")
verify(userRepository, times(3)).findById(any())
verify(userRepository, never()).delete(any())
```

Mockito matchers are all-or-nothing per call: mixing a raw value with `any()` in the same invocation
throws `InvalidUseOfMatchersException`. Wrap the literal in `eq(...)`.

Kora contracts are synchronous in 2.0, so nothing here needs a coroutine wrapper. If the component
under test hands work to another thread, wait for it with Awaitility (already on the Testcontainers
classpath as `org.testcontainers.shaded.org.awaitility.Awaitility`, as the migrated Kafka example
does) rather than `Thread.sleep`.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Java 25 (69) is not supported` during mock creation | `mockito-kotlin` dragged in an older `mockito-core` | pin `mockito-core` explicitly next to it |
| Mock is `null` | missing `@TestComponent` | add it — `@Mock` alone does not touch the graph |
| Mock not applied to the graph | `MockitoExtension` attached alongside `@KoraAppTest` | remove `@ExtendWith(MockitoExtension::class)` |
| `Cannot create @Spy for … No matching component was found` | the spied type is not in the graph | mark it `@Root` or list it in `@KoraAppTest(components = [...])` |
| `Cannot create @Spy using Mockito for component: … does not resolve to a raw class` | spying a type variable or array type | spy the raw/parameterized class |
| Unused stubs never reported | default strictness is `WARN` and reports go through SLF4J | add `@MockitoStrictness(Strictness.STRICT_STUBS)`, or raise the log level |
| `InvalidUseOfMatchersException` | raw value mixed with matchers in one call | wrap literals in `eq(...)` |
| Real method runs while stubbing a `@Spy` | `when(spy.x()).thenReturn(...)` | use `doReturn(...).when(spy).x()` |
