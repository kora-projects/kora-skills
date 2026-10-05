# MockK with `@KoraAppTest` (Kora 2.x)

Verified against
[`GraphMockkMock`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/test/test-junit5/src/main/java/io/koraframework/test/extension/junit5/GraphMockkMock.java),
[`GraphMockkSpyk`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/test/test-junit5/src/main/java/io/koraframework/test/extension/junit5/GraphMockkSpyk.java),
`MockUtils`, the framework's own Kotlin tests under
[`test/test-junit5/src/test/kotlin/.../kotlin/mockk`](https://github.com/kora-projects/kora/tree/2.0.0.RC2/test/test-junit5/src/test/kotlin/io/koraframework/test/extension/junit5/kotlin/mockk),
the version catalog
[`gradle/libs.versions.toml`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/gradle/libs.versions.toml),
and the migrated
[`kora-kotlin-crud`](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/kotlin/kora-kotlin-crud)
example.

MockK is the recommended mocking library for Kora Kotlin tests. It is wired into the graph by
combining `@field:MockK` / `@field:SpyK` with `@TestComponent`.

## Contents

- [Dependency and the Java 25 floor](#dependency-and-the-java-25-floor)
- [Use-site targets](#use-site-targets)
- [@MockK](#mockk)
- [@SpyK](#spyk)
- [Stubbing](#stubbing)
- [Verify](#verify)
- [Argument matchers and slots](#argument-matchers-and-slots)
- [Relaxed mocks](#relaxed-mocks)
- [No coEvery against Kora contracts](#no-coevery-against-kora-contracts)
- [Troubleshooting](#troubleshooting)

---

## Dependency and the Java 25 floor

```kotlin
testImplementation("io.mockk:mockk:1.14.11")
```

| Source | Version |
|---|---|
| Kora 2.0 version catalog (`libs.versions.toml`, `mockk`) | **`1.14.11`** |
| Kotlin migration guide, stated minimum for Java 25 | `1.14.9` |
| Migrated `kora-kotlin-crud` `build.gradle.kts` | **`1.14.11`** |

**Use `1.14.11`.** Kora 2.0 artifacts are compiled to class file major version 69 (Java 25); MockK
`1.13.x` carries Byte Buddy `1.14.x`, whose transformer cannot read them and logs

```
i.m.p.j.t.InliningClassTransformer - Failed to transform class ... Java 25 (69) is not supported
```

The failure is at **runtime**, not compile time, and it hides inside
`Application graph failed to initialize with N errors` with no visible suppressed exception. Trace
the real source of the dependency with

```
./gradlew <module>:dependencyInsight --dependency byte-buddy --configuration testRuntimeClasspath
```

Do **not** "fix" this with `-Dnet.bytebuddy.experimental=true`. That flag only disables the check
that refuses an unsupported class-file version; the instrumentation is still unverified.

---

## Use-site targets

The Kora extension looks for the annotation on the JVM **field** and, additionally, on the Kotlin
**property** — the property path needs `kotlin.reflect.jvm.ReflectJvmMapping` on the test classpath,
and `test-junit5` declares `kotlin-reflect` `compileOnly`, so Kora does not supply it.

```kotlin
@field:MockK          // targets the field — always discovered. Prefer this.
@TestComponent
lateinit var repository: UserRepository

@MockK                // targets the Kotlin property — discovered only with kotlin-reflect present
@TestComponent
lateinit var cache: UserCache
```

Both forms appear in the framework's own tests (`MockkFieldsTests` covers the property path in a case
named `mockkOnProperty`), and the migrated `kora-kotlin-crud` example uses `@field:MockK` throughout.
When the property form goes undiscovered you get the **real** component injected and no error at all
— which is why `@field:` is the safe default.

On **parameters** (constructor or test method) no prefix is needed:

```kotlin
@KoraAppTest(Application::class)
class CtorTest(
    @MockK(relaxed = true) @TestComponent val repository: UserRepository,
    @TestComponent val service: UserService,
)
```

---

## `@MockK`

`io.mockk.impl.annotations.MockK`. The extension reads three attributes: `name`, `relaxed`,
`relaxUnitFun`, then calls `mockkClass` and swaps the graph node for the mock. The same instance is
injected into the test field **and** into every graph component depending on that type.

```kotlin
@KoraAppTest(Application::class)
class UserServiceTest {

    @field:MockK
    @TestComponent
    lateinit var userRepository: UserRepository

    @TestComponent
    lateinit var userService: UserService

    @BeforeEach
    fun setup() {
        every { userRepository.findById("1") } returns UserResponse("1", "John", "john@example.com", LocalDateTime.now())
    }

    @Test
    fun getUser() {
        assertNotNull(userService.getUser("1"))
        verify { userRepository.findById("1") }
    }
}
```

Rules:

- No `= mockk()` initializer — the annotation builds the mock.
- No `@ExtendWith(MockKExtension::class)` — `@KoraAppTest` owns creation, injection and reset
  (`clearMocks` between tests).
- The mocked type must resolve to a raw class or a parameterized class; otherwise
  `Cannot create @MockK using MockK for component: … does not resolve to a raw class`.
- A `@TestComponent` may not be both a mock and a plain component, nor both a mock and a spy.
- When the graph node is a `Wrapped<T>`, the extension forces `relaxed`/`relaxUnitFun` on regardless
  of the annotation and wraps the mock for you.

---

## `@SpyK`

`io.mockk.impl.annotations.SpyK`. Attributes read: `name`, `recordPrivateCalls`. Two behaviours,
chosen by whether the field has a value:

```kotlin
// Field has a value -> that instance is spied, graph dependencies are dropped
@field:SpyK
@TestComponent
var spy: TestComponent1 = TestComponent1()

// lateinit (no value) -> the component built by the graph is spied,
// and its dependencies are kept (replaceNodeKeepDependencies)
@field:SpyK
@TestComponent
lateinit var spyFromGraph: TestComponent1
```

Stub selectively in `@BeforeEach`; unstubbed methods keep real behaviour.

```kotlin
@BeforeEach
fun setupSpy() {
    every { spy.get() } returns "?"
}
```

---

## Stubbing

```kotlin
every { repo.findById("1") } returns user
every { repo.save(any()) } answers { firstArg() }
every { repo.put(any<Long>(), any()) } returnsArgument 1
every { repo.findById("1") } returnsMany listOf(first, second)
every { repo.findById("1") } throws RuntimeException("Database error")

// a Unit-returning method still needs a stub unless the mock is relaxUnitFun
every { repo.update(any()) } returns Unit
```

Mix a broad matcher with an exact value — the later, more specific stub wins:

```kotlin
every { repo.findByEmail(any()) } returns generic
every { repo.findByEmail("specific@example.com") } returns specific
```

---

## Verify

```kotlin
verify { repo.findById("1") }                          // at least once
verify(exactly = 3) { repo.findById(any()) }
verify(exactly = 0) { repo.delete(any()) }
verifyOrder { repo.save(any()); repo.update(any()) }   // ordered, gaps allowed
verify(timeout = 5000) { repo.findById(any()) }        // for work handed to another thread
```

`verify(timeout = …)` is the right tool when a Kora component dispatches work to a virtual-thread
executor and the assertion has to wait for it — there is no coroutine scheduler to advance.

---

## Argument matchers and slots

```kotlin
every { repo.findById(any()) } returns user
every { repo.save(any<User>()) } returns user
every { repo.findByName(match { it.startsWith("t") }) } returns user
every { repo.save(notNull()) } returns "1"
every { cache.get(any<Collection<Long>>()) } returns emptyMap()
```

```kotlin
val slot = slot<User>()
every { repo.save(capture(slot)) } returns "1"

userService.create(UserRequest("John", "john@example.com"))

assertEquals("John", slot.captured.name)
```

---

## Relaxed mocks

```kotlin
@field:MockK(relaxed = true)        // every method returns a default
@field:MockK(relaxUnitFun = true)   // only Unit-returning methods are relaxed
```

Standalone mocks: `mockk<UserRepository>(relaxed = true)`, or `mockkClass(UserRepository::class)`
inside a `KoraGraphModification` factory — the framework's own Kotlin test uses exactly that shape.

---

## No `coEvery` against Kora contracts

Kora 2.0 repositories, controllers and HTTP clients are **synchronous**, so `coEvery`/`coVerify` do
not apply to them and `runTest` buys nothing.

```kotlin
// 1.x
@Test fun t() = runTest {
    coEvery { userRepository.save(any()) } returns "1"
    userService.createUser(request)
    coVerify { userRepository.save(any()) }
}

// 2.0
@Test fun t() {
    every { userRepository.save(any()) } returns "1"
    userService.createUser(request)
    verify { userRepository.save(any()) }
}
```

A leftover `coEvery`/`coVerify` still **compiles** once the contract stops suspending — the block is a
`suspend` lambda, and a `suspend` lambda may call ordinary blocking functions — so the build stays
green and only a grep will find it. See
[coroutines-migration-reference.md](coroutines-migration-reference.md) for what remains of the
coroutine testing toolkit.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Field is a real object, not a mock | `= mockk()` next to the annotation | remove the initializer |
| Bare `@MockK` ignored, real component injected | annotation landed on the Kotlin property, `kotlin-reflect` absent | use `@field:MockK` |
| `Failed to transform class … Java 25 (69) is not supported` | MockK below `1.14.9` | pin `io.mockk:mockk:1.14.11` |
| `Cannot create @MockK for … No matching component was found` | the type is not in the graph, or `@Tag` mismatch | mark it `@Root`, add it to `@KoraAppTest(components = [...])`, fix the tag |
| `Cannot create @MockK using MockK for component: … does not resolve to a raw class` | mocking a type variable or array type | mock the raw/parameterized class, or use `KoraGraphModification` |
| Mock replaced but graph component still real | `MockKExtension` attached alongside `@KoraAppTest` | remove the extra `@ExtendWith(...)` |
| `@TestComponent cannot be declared as both component and mock` | both annotations on one field/parameter | split them |
| Stub never used / call unstubbed | stubbed after the call, or matcher mismatch | stub in `@BeforeEach`; widen with `any()` |
| Unit-returning method throws on a strict mock | not stubbed | `every { … } returns Unit`, or `relaxUnitFun = true` |
