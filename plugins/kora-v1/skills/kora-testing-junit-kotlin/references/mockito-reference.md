# Mockito-Kotlin Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/junit5.md`
**Example:** `.kora-agent/kora-examples/guides/kotlin/kora-kotlin-guide-testing-junit-app` (this guide app uses Mockito with `@Mock @TestComponent`)

Mockito is the alternative to MockK for Kotlin tests — useful in mixed Java/Kotlin codebases or teams standardized on Mockito. The `mockito-kotlin` wrapper provides idiomatic helpers (`whenever`, `mock`). The Kora extension wires `@Mock`/`@Spy` mocks into the Graph the same way it does MockK mocks.

## Contents

- [Dependency](#dependency)
- [@Mock + @TestComponent](#mock--testcomponent)
- [@Spy](#spy)
- [@MockitoStrictness](#mockitostrictness)
- [Patterns](#patterns)
- [Verify](#verify)
- [Best practices](#best-practices)
- [Troubleshooting](#troubleshooting)

> Do not attach `@ExtendWith(MockitoExtension::class)`; it conflicts with `@KoraAppTest`, which manages mock creation and injection.

---

## Dependency

```kotlin
testImplementation("org.mockito:mockito-core:5.12.0")
testImplementation("org.mockito.kotlin:mockito-kotlin:5.4.0") // idiomatic Kotlin helpers
```

---

## @Mock + @TestComponent

`@Mock` builds the mock; `@TestComponent` registers it in the Graph. Use `lateinit var`; do not add a `= mock()` initializer.

```kotlin
@KoraAppTest(Application::class)
class UserServiceTest {

    @Mock
    @TestComponent
    lateinit var userRepository: UserRepository

    @TestComponent
    lateinit var userService: UserService

    @Test
    fun createUserShouldCreateAndReturnUser() {
        whenever(userRepository.save("John", "john@example.com")).thenReturn("1")

        val result = userService.createUser(UserRequest("John", "john@example.com"))

        assertEquals("1", result.id)
        verify(userRepository).save("John", "john@example.com")
    }
}
```

Without `mockito-kotlin`, use Kotlin's escaped `` `when` ``:

```kotlin
`when`(userRepository.findById("1")).thenReturn(expected)
```

---

## @Spy

Wraps a real implementation; original behavior unless overridden.

```kotlin
@KoraAppTest(Application::class)
class UserServiceTest {

    @Spy
    @TestComponent
    lateinit var userService: UserService

    @Test
    fun shouldSpy() {
        doReturn("?").whenever(userService).describe()
        assertEquals("?", userService.describe())
    }
}
```

---

## @MockitoStrictness

Controls how unused stubs are reported, like a `MockitoSession`.

```kotlin
@MockitoStrictness(Strictness.STRICT_STUBS)
@KoraAppTest(Application::class)
class UserServiceTest(@Mock @TestComponent val userRepository: UserRepository) {

    @BeforeEach
    fun setup() {
        whenever(userRepository.findById("1")).thenReturn(expected)
    }
}
```

| Level | Behavior |
|-------|----------|
| `STRICT_STUBS` | Flags unused stubs, may throw `UnnecessaryStubbingException` |
| `WARN` | Logs warnings |
| `LENIENT` | Disables the checks |

---

## Patterns

### Consecutive calls

```kotlin
whenever(userRepository.findById("1"))
    .thenReturn(first)
    .thenReturn(second)
```

### Throwing

```kotlin
whenever(userRepository.findById("1")).thenThrow(RuntimeException("Database error"))
```

### Matchers

```kotlin
whenever(userRepository.findByEmail(any())).thenReturn(generic)
whenever(userRepository.findByEmail(eq("specific@example.com"))).thenReturn(specific)
```

---

## Verify

```kotlin
verify(userRepository).findById("1")              // exactly once (default)
verify(userRepository, times(3)).findById(any())  // 3 times
verify(userRepository, never()).delete(any())     // never
inOrder(userRepository).apply {
    verify(userRepository).save(any())
    verify(userRepository).update(any())
}
```

---

## Best practices

1. `@Mock` + `@TestComponent` together; `lateinit var`, no `= mock()` initializer.
2. No `MockitoExtension` — conflicts with `@KoraAppTest`.
3. `STRICT_STUBS` to catch unused stubs in important tests.
4. Prefer MockK for pure-Kotlin codebases (better coroutine support); use Mockito for mixed Java/Kotlin code.

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Mock is `null` | Missing `@TestComponent` | Add `@TestComponent` |
| Mock not applied to Graph | `MockitoExtension` attached | Remove `@ExtendWith(MockitoExtension::class)` |
| Stub does not apply | Stubbed after the call | Stub in `@BeforeEach` or before the call |
| Verify fails | Argument mismatch | Match with `any()`/`eq()` |
