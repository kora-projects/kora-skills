# Mockito Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/testing.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/testing.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-helloworld/`

Using Mockito for mocking components in Kora Java tests.

## Overview

Mockito is a library for creating mock/stub objects in Java tests. The Kora JUnit5 extension integrates with Mockito for mocking component dependencies.

**Important:** Do not use `@ExtendWith(MockitoExtension.class)` — it conflicts with `@KoraAppTest`.

---

## Dependency

```groovy
testImplementation "org.mockito:mockito-core:5.18.0"
```

---

## @Mock

Creates a mock of an object with default behavior (null, 0, false, empty collections).

```java
@KoraAppTest(Application.class)
class UserServiceTest {
    
    @Mock
    @TestComponent
    private UserRepository userRepository;
    
    @TestComponent
    private UserService userService;
    
    @BeforeEach
    void setup() {
        Mockito.when(userRepository.findById(1L))
               .thenReturn(Optional.of(new User(1L, "test@example.com")));
    }
    
    @Test
    void shouldCreateUser() {
        var user = userService.create(1L);
        assertNotNull(user);
        Mockito.verify(userRepository).findById(1L);
    }
}
```

### @Mock parameters

```java
// Custom answer
@Mock(answer = Answers.RETURNS_DEFAULTS)
@TestComponent
private UserRepository userRepository;

// Custom name
@Mock(name = "userRepository")
@TestComponent
private UserRepository userRepository;
```

---

## @Spy

Creates a spy of an object with original behavior that can be overridden.

```java
@KoraAppTest(Application.class)
class UserServiceTest {
    
    @Spy
    @TestComponent
    private UserService userService = new UserService();
    
    @Test
    void shouldSendEmail() {
        Mockito.doNothing().when(userService).sendEmail(any());
        
        userService.register("test@example.com");
        
        Mockito.verify(userService).sendEmail("test@example.com");
    }
}
```

---

## Mock Strictness

`@MockitoStrictness` verifies stub usage and detects unused stub calls.

```java
@MockitoStrictness(Strictness.STRICT_STUBS)
@KoraAppTest(Application.class)
class UserServiceTest {
    
    @Mock
    @TestComponent
    private UserRepository userRepository;
    
    @BeforeEach
    void setup() {
        Mockito.when(userRepository.findById(1L))
               .thenReturn(Optional.of(new User(1L, "test")));
    }
    
    @Test
    void shouldFindUser() {
        // userRepository.findById(1L) must be called
        var user = userRepository.findById(1L);
        assertNotNull(user);
    }
}
```

### Strictness levels

| Level | Description |
|-------|-------------|
| `STRICT_STUBS` | Warns about unused stubs, throws `UnnecessaryStubbingException` |
| `WARN` | Prints warnings to the log |
| `SILENT` | Disables checks (by default) |

---

## Kotlin + Mockito

Mockito can be used in Kotlin with the Mockito-Kotlin library.

### Dependency

```groovy
testImplementation "org.mockito.kotlin:mockito-kotlin:5.4.0"
```

### Example

```kotlin
@KoraAppTest(Application::class)
class UserServiceTest {
    
    @Mock
    @TestComponent
    private val userRepository: UserRepository = mock()
    
    @TestComponent
    private lateinit var userService: UserService
    
    @BeforeEach
    fun setup() {
        whenever(userRepository.findById(1L)).thenReturn(Optional.of(User(1L, "test")))
    }
    
    @Test
    fun `should create user`() {
        val user = userService.create(1L)
        assertNotNull(user)
        verify(userRepository).findById(1L)
    }
}
```

---

## Patterns

### Mock with multiple calls

```java
@Mock
@TestComponent
private UserRepository userRepository;

@BeforeEach
void setup() {
    Mockito.when(userRepository.findById(1L))
           .thenReturn(Optional.of(new User(1L, "first")))
           .thenReturn(Optional.of(new User(1L, "second")));
}

@Test
void shouldReturnDifferentValues() {
    var user1 = userRepository.findById(1L);  // first call
    var user2 = userRepository.findById(1L);  // second call
}
```

### Mock with exceptions

```java
@Mock
@TestComponent
private UserRepository userRepository;

@BeforeEach
void setup() {
    Mockito.when(userRepository.findById(1L))
           .thenThrow(new RuntimeException("Database error"));
}

@Test
void shouldThrowException() {
    assertThrows(RuntimeException.class, () -> userRepository.findById(1L));
}
```

### Mock with argument matchers

```java
@Mock
@TestComponent
private UserRepository userRepository;

@BeforeEach
void setup() {
    Mockito.when(userRepository.findByEmail(anyString()))
           .thenReturn(Optional.of(new User(1L, "test@example.com")));
    
    Mockito.when(userRepository.findByEmail(eq("specific@example.com")))
           .thenReturn(Optional.of(new User(2L, "specific")));
}
```

### Stubbing chain

```java
@Mock
@TestComponent
private UserRepository userRepository;

@BeforeEach
void setup() {
    var user = new User(1L, "test");
    Mockito.when(userRepository.findById(1L)).thenReturn(Optional.of(user));
    Mockito.when(userRepository.existsById(1L)).thenReturn(true);
}
```

---

## Verify

### Basic verification

```java
@Test
void shouldVerifyCall() {
    userService.create(1L);
    Mockito.verify(userRepository).findById(1L);
}
```

### Verifying call count

```java
@Test
void shouldVerifyCallCount() {
    userService.processAll();
    Mockito.verify(userRepository, Mockito.times(3)).findById(anyLong());
    Mockito.verify(userRepository, Mockito.never()).delete(anyLong());
}
```

### Verifying call order

```java
@Test
void shouldVerifyOrder() {
    userService.fullProcess();
    
    var mock = Mockito.mock(UserRepository.class);
    var inOrder = Mockito.inOrder(mock);
    
    inOrder.verify(mock).save(any());
    inOrder.verify(mock).update(any());
}
```

---

## Argument Matchers

```java
import static org.mockito.ArgumentMatchers.*;

// Any argument
Mockito.when(repo.findById(anyLong())).thenReturn(Optional.of(user));

// Any object
Mockito.when(repo.save(any(User.class))).thenReturn(user);

// Any String
Mockito.when(repo.findByName(anyString())).thenReturn(user);

// Exact value
Mockito.when(repo.findById(eq(1L))).thenReturn(user);

// Collections
Mockito.when(repo.findAllById(anyList())).thenReturn(List.of(user));
```

---

## Best Practices

1. **Use `@Mock` + `@TestComponent` together** — Kora integrates the mock into the DI graph
2. **Do not use `MockitoExtension`** — conflicts with `@KoraAppTest`
3. **`STRICT_STUBS` for important tests** — detects unused stubs
4. **Use `any()` for arguments** — simplifies stubbing
5. **Spy for partial mocking** — when the original behavior must be preserved

---

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| Mock is null | Missing `@TestComponent` | Add `@TestComponent` to the field |
| Stub does not work | Wrong order | `@BeforeEach` before `@Test` |
| Verify fails | Method not called | Check arguments with `any()` |
| Extension conflict | `MockitoExtension` + `@KoraAppTest` | Remove `@ExtendWith(MockitoExtension.class)` |
| ClassCastException | Wrong type | Check generics in `when()` |

---

## Resources

- [Mockito Documentation](https://javadoc.io/doc/org.mockito/mockito-core/latest/org/mockito/Mockito.html)
- [Mockito GitHub](https://github.com/mockito/mockito)
- [Mockito-Kotlin](https://github.com/mockito/mockito-kotlin)
