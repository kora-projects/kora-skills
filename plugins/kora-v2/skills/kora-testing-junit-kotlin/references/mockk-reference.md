# MockK Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/junit5.md`
**Example:** `.kora-agent/kora-examples/guides/kotlin/kora-kotlin-guide-testing-junit-app`

MockK is the recommended mocking library for Kora Kotlin tests. It is wired into the Graph by combining `@MockK`/`@SpyK` with `@TestComponent`.

## Contents

- [Dependency](#dependency)
- [@MockK](#mockk)
- [@SpyK](#spyk)
- [Stubbing patterns](#stubbing-patterns)
- [Verify](#verify)
- [Argument matchers](#argument-matchers)
- [Slot capture](#slot-capture)
- [Relaxed mocks](#relaxed-mocks)
- [Coroutines](#coroutines)
- [Best practices](#best-practices)
- [Troubleshooting](#troubleshooting)

> Do not attach `@ExtendWith(MockKExtension::class)`; it conflicts with `@KoraAppTest`, which manages mock creation and injection itself.

---

## Dependency

```kotlin
testImplementation("io.mockk:mockk:1.13.11")
```

---

## @MockK

`@MockK` builds the mock; `@TestComponent` registers it in the Graph in place of the real component. Do not add a `= mockk()` initializer — the annotation creates the mock.

```kotlin
@KoraAppTest(Application::class)
class UserServiceTest {

    @MockK
    @TestComponent
    lateinit var userRepository: UserRepository

    @TestComponent
    lateinit var userService: UserService

    @BeforeEach
    fun setup() {
        every { userRepository.findById("1") } returns UserResponse("1", "John", "john@example.com", LocalDateTime.now())
    }

    @Test
    fun shouldCreateUser() {
        val result = userService.getUser("1")
        assertNotNull(result)
        verify { userRepository.findById("1") }
    }
}
```

Constructor form (works the same way):

```kotlin
@KoraAppTest(Application::class)
class UserServiceTest(
    @MockK @TestComponent val userRepository: UserRepository
)
```

---

## @SpyK

`@SpyK` wraps a real implementation; methods keep their original behavior unless overridden. The field provides the instance to spy on.

```kotlin
@KoraAppTest(Application::class)
class UserServiceTest {

    @field:SpyK
    @TestComponent
    val supplier: Supplier<String> = Supplier { "1" }

    @Test
    fun shouldSpy() {
        every { supplier.get() } returns "?"
        assertEquals("?", supplier.get())
    }
}
```

---

## Stubbing patterns

### Basic

```kotlin
every { repo.findById("1") } returns user
every { repo.save(any()) } answers { firstArg() }
```

### Consecutive calls

```kotlin
every { repo.findById("1") } returnsMany listOf(first, second)
```

### Throwing

```kotlin
every { repo.findById("1") } throws RuntimeException("Database error")
```

### Mixing exact and matcher stubs

```kotlin
every { repo.findByEmail(any()) } returns generic
every { repo.findByEmail("specific@example.com") } returns specific
```

---

## Verify

```kotlin
verify { repo.findById("1") }                       // called at least once
verify(exactly = 3) { repo.findById(any()) }        // called exactly 3 times
verify(exactly = 0) { repo.delete(any()) }          // never called
verifyOrder { repo.save(any()); repo.update(any()) } // ordered (gaps allowed)
verify(timeout = 5000) { repo.findById(any()) }      // within 5s (async)
```

---

## Argument matchers

```kotlin
every { repo.findById(any()) } returns user           // any argument
every { repo.save(any<User>()) } returns user         // any of a type
every { repo.findById("1") } returns user             // exact value
every { repo.findByName(match { it.startsWith("t") }) } returns user // predicate
every { repo.save(notNull()) } returns user           // non-null
```

---

## Slot capture

Capture an argument and assert on it after the call:

```kotlin
val slot = slot<User>()
every { repo.save(capture(slot)) } returns "1"

userService.create(UserRequest("John", "john@example.com"))

assertEquals("John", slot.captured.name)
verify { repo.save(any()) }
```

---

## Relaxed mocks

```kotlin
val mock = mockk<UserRepository>(relaxed = true)        // all methods return defaults
val mock = mockk<UserRepository>(relaxUnitFun = true)   // only Unit-returning methods relaxed
```

For a `@MockK` field, pass the flag on the annotation: `@MockK(relaxed = true)`.

---

## Coroutines

Use the `co*` DSL for suspend functions and run the test body in `runTest`. See [coroutines-testing-reference.md](coroutines-testing-reference.md).

```kotlin
@MockK
@TestComponent
lateinit var userRepository: UserRepository

@Test
fun shouldFindUserAsync() = runTest {
    coEvery { userRepository.findByIdAsync("1") } returns user
    val result = userService.findByIdAsync("1")
    assertNotNull(result)
    coVerify { userRepository.findByIdAsync("1") }
}
```

---

## Best practices

1. `@MockK` + `@TestComponent` together — Kora wires the mock into the Graph; no `= mockk()` initializer.
2. No `MockKExtension` — conflicts with `@KoraAppTest`.
3. `relaxed`/`relaxUnitFun` when you do not need to stub every method.
4. `coEvery`/`coVerify` for suspend functions; wrap in `runTest`.
5. `@SpyK` for partial mocking that keeps real behavior.

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Field is a real object, not a mock | `= mockk()` next to `@MockK` | Remove the initializer |
| Mock is `null` | Missing `@TestComponent` | Add `@TestComponent` |
| Stub does not apply | Stubbed after the call | Stub in `@BeforeEach` or before invoking the code under test |
| Verify fails | Argument mismatch | Match with `any()` / a matcher |
| Coroutine test fails | `verify`/`every` on suspend method | Use `coVerify`/`coEvery` inside `runTest` |
