# MockK Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/testing.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/testing.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-helloworld/`

Using MockK for mocking components in Kora Kotlin tests.

## Overview

MockK is a library for creating mock/stub objects in Kotlin. It supports Kotlin-specific features: data classes, coroutines, extension functions.

**Important:** Do not use `@ExtendWith(MockKExtension.class)` — it conflicts with `@KoraAppTest`.

---

## Dependency

```groovy
testImplementation "io.mockk:mockk:1.13.11"
```

---

## @MockK

Creates a mock of an object.

```kotlin
@KoraAppTest(Application::class)
class UserServiceTest {
    
    @MockK
    @TestComponent
    private val userRepository: UserRepository = mockk()
    
    @TestComponent
    private lateinit var userService: UserService
    
    @BeforeEach
    fun setup() {
        every { userRepository.findById(1L) } returns Optional.of(User(1L, "test"))
    }
    
    @Test
    fun `should create user`() {
        val user = userService.create(1L)
        assertNotNull(user)
        verify { userRepository.findById(1L) }
    }
}
```

---

## @SpyK

Creates a spy of an object with original behavior.

```kotlin
@KoraAppTest(Application::class)
class UserServiceTest {
    
    @SpyK
    @TestComponent
    private val userService: UserService = spyk(UserService())
    
    @Test
    fun `should send email`() {
        every { userService.sendEmail(any()) } just Runs
        
        userService.register("test@example.com")
        
        verify { userService.sendEmail("test@example.com") }
    }
}
```

---

## Manual mock creation

```kotlin
@KoraAppTest(Application::class)
class UserServiceTest {
    
    @TestComponent
    private val userRepository: UserRepository = mockk {
        every { findById(1L) } returns Optional.of(User(1L, "test"))
    }
    
    @TestComponent
    private lateinit var userService: UserService
    
    @Test
    fun `should create user`() {
        val user = userService.create(1L)
        assertNotNull(user)
    }
}
```

---

## Relaxations

### Relaxed mocks

```kotlin
// All methods return default values
val mock = mockk<UserRepository>(relaxed = true)
```

### Relaxed with configuration

```kotlin
// Specific methods stubbed, the rest relaxed
val mock = mockk<UserRepository> {
    every { findById(any()) } returns Optional.of(User(1L, "test"))
    // Remaining methods return default values
}
```

### Relax mocks

```kotlin
// Relax only unit-returning methods
val mock = mockk<UserRepository>(relaxUnitFun = true)
```

---

## Patterns

### Mock with multiple calls

```kotlin
@MockK
@TestComponent
private val userRepository: UserRepository = mockk()

@BeforeEach
fun setup() {
    every { userRepository.findById(1L) }
        .returns(Optional.of(User(1L, "first")))
        .andThen(Optional.of(User(1L, "second")))
}

@Test
fun `should return different values`() {
    val user1 = userRepository.findById(1L)  // first call
    val user2 = userRepository.findById(1L)  // second call
}
```

### Mock with exceptions

```kotlin
@MockK
@TestComponent
private val userRepository: UserRepository = mockk()

@BeforeEach
fun setup() {
    every { userRepository.findById(1L) } throws RuntimeException("Database error")
}

@Test
fun `should throw exception`() {
    assertThrows<RuntimeException> { userRepository.findById(1L) }
}
```

### Mock with argument matchers

```kotlin
@MockK
@TestComponent
private val userRepository: UserRepository = mockk()

@BeforeEach
fun setup() {
    every { userRepository.findByEmail(any()) } returns Optional.of(User(1L, "test"))
    every { userRepository.findByEmail("specific@example.com") } returns Optional.of(User(2L, "specific"))
}
```

### Stubbing chain

```kotlin
@MockK
@TestComponent
private val userRepository: UserRepository = mockk()

@BeforeEach
fun setup() {
    val user = User(1L, "test")
    every { userRepository.findById(1L) } returns Optional.of(user)
    every { userRepository.existsById(1L) } returns true
}
```

---

## Verify

### Basic verification

```kotlin
@Test
fun `should verify call`() {
    userService.create(1L)
    verify { userRepository.findById(1L) }
}
```

### Verifying call count

```kotlin
@Test
fun `should verify call count`() {
    userService.processAll()
    verify(exactly = 3) { userRepository.findById(any()) }
    verify(exactly = 0) { userRepository.delete(any()) }
}
```

### Verifying call order

```kotlin
@Test
fun `should verify order`() {
    userService.fullProcess()
    
    val mock = mockk<UserRepository>()
    val order = verifyOrder {
        mock.save(any())
        mock.update(any())
    }
}
```

### Verify with timeout

```kotlin
@Test
fun `should verify with timeout`() {
    userService.asyncProcess()
    verify(timeout = 5000) { userRepository.findById(any()) }
}
```

---

## Argument Matchers

```kotlin
// Any argument
every { repo.findById(any()) } returns Optional.of(user)

// Any specific type
every { repo.save(any<User>()) } returns user

// Any String
every { repo.findByName(any<String>()) } returns user

// Exact value
every { repo.findById(1L) } returns user

// Predicate
every { repo.findByName(match { it.startsWith("test") }) } returns user

// Regex
every { repo.findByEmail(match(Regex(".+@example\\.com"))) } returns user

// Not null
every { repo.save(notNull()) } returns user
```

---

## Coroutines

### Mocking suspend functions

```kotlin
@MockK
@TestComponent
private val userRepository: UserRepository = mockk()

@BeforeEach
fun setup() {
    coEvery { userRepository.findByIdAsync(1L) } returns User(1L, "test")
}

@Test
fun `should find user async`() = runTest {
    val user = userService.findByIdAsync(1L)
    assertNotNull(user)
    coVerify { userRepository.findByIdAsync(1L) }
}
```

### Spying on suspend functions

```kotlin
@SpyK
@TestComponent
private val userService: UserService = spyk(UserService())

@Test
fun `should process async`() = runTest {
    coEvery { userService.processAsync(any()) } just Runs
    
    userService.processAsync(1L)
    
    coVerify { userService.processAsync(1L) }
}
```

---

## Data Classes

MockK works well with data classes without any additional configuration.

```kotlin
data class User(val id: Long, val name: String)

@MockK
@TestComponent
private val userRepository: UserRepository = mockk()

@BeforeEach
fun setup() {
    every { userRepository.findById(1L) } returns Optional.of(User(1L, "test"))
}

@Test
fun `should work with data class`() {
    val user = userRepository.findById(1L)
    assertEquals(1L, user?.id)
    assertEquals("test", user?.name)
}
```

---

## Extension Functions

MockK supports mocking extension functions.

```kotlin
// Mock extension functions
mockkStatic("com.example.ExtensionsKt")

@BeforeEach
fun setup() {
    every { anyString().isValidEmail() } returns true
}
```

---

## Best Practices

1. **Use `@MockK` + `@TestComponent` together** — Kora integrates the mock into the DI graph
2. **Do not use `MockKExtension`** — conflicts with `@KoraAppTest`
3. **Relaxed mocks for simplicity** — no need to stub every method
4. **`coEvery`/`coVerify` for coroutines** — correct handling of suspend functions
5. **Spy for partial mocking** — when the original behavior must be preserved

---

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| Mock is null | Missing `@TestComponent` | Add `@TestComponent` to the field |
| Stub does not work | Wrong order | `@BeforeEach` before `@Test` |
| Verify fails | Method not called | Check arguments with `any()` |
| Extension conflict | `MockKExtension` + `@KoraAppTest` | Remove `@ExtendWith(MockKExtension.class)` |
| Coroutine test fails | Missing `runTest` | Use `runTest { }` for suspend tests |

---

## Resources

- [MockK Documentation](https://mockk.io/)
- [MockK GitHub](https://github.com/mockk/mockk)
- [MockK Quick Reference](https://mockk.io/#quick-reference)
