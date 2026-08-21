# Mockito Integration Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/junit5.md`

Using Mockito to mock and spy components inside a Kora Java test graph.

## Contents

- [Dependency](#dependency)
- [@Mock + @TestComponent](#mock--testcomponent)
- [@Mock parameters](#mock-parameters)
- [@Spy](#spy)
- [Mock strictness](#mock-strictness)
- [Stubbing patterns](#stubbing-patterns)
- [Verify](#verify)
- [Argument matchers](#argument-matchers)
- [Best practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Dependency

```groovy
testImplementation "org.mockito:mockito-core:5.18.0"
```

The Kora `test-junit5` artifact (pinned by the `kora-parent` BOM) provides `@KoraAppTest`
and `@TestComponent`. Mockito is added on top of it.

---

## @Mock + @TestComponent

`@Mock` makes a stub of the annotated component; `@TestComponent` registers that stub as a
graph component. Kora injects the same stub into the test field and into every graph
component that depends on this type. Unstubbed methods return defaults (`void`, primitive
defaults, empty collections, `null`).

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
        Mockito.when(userRepository.findById("1"))
               .thenReturn(Optional.of(new UserResponse("1", "John", "john@example.com", LocalDateTime.now())));
    }

    @Test
    void shouldReturnUser() {
        var user = userService.getUser("1");
        assertTrue(user.isPresent());
        Mockito.verify(userRepository).findById("1");
    }
}
```

**Do not use `@ExtendWith(MockitoExtension.class)`.** It cannot be combined with
`@KoraAppTest` — Kora itself creates the mock, resets it between methods, and injects it
into the graph.

---

## @Mock parameters

All `@Mock` parameters are supported:

```java
// Custom default answer
@Mock(answer = Answers.RETURNS_DEFAULTS)
@TestComponent
private UserRepository userRepository;

// Custom mock name (for diagnostics)
@Mock(name = "userRepository")
@TestComponent
private UserRepository userRepositoryNamed;
```

---

## @Spy

`@Spy` wraps the real component: methods keep their original behavior unless overridden.
You can spy a value declared in a field initializer, or a method parameter.

Spy from a field initializer:
```java
@KoraAppTest(Application.class)
class SupplierTest {

    @Spy
    @TestComponent
    private Supplier<String> component1 = () -> "12345";

    @Test
    void example() {
        assertEquals("12345", component1.get());
    }
}
```

Spy on a method parameter:
```java
@Test
void example(@Spy @TestComponent Supplier<String> component1) {
    Mockito.when(component1.get()).thenReturn("?");
    assertEquals("?", component1.get());
}
```

For void methods, override behavior with `doReturn`/`doThrow`/`doNothing` before calling.

---

## Mock strictness

`@MockitoStrictness` on the test class sets the verification level, mimicking a
`MockitoSession` over a single test method.

```java
@MockitoStrictness(Strictness.STRICT_STUBS)
@KoraAppTest(Application.class)
class UserServiceTest {

    @Mock
    @TestComponent
    private UserRepository userRepository;

    @BeforeEach
    void setup() {
        Mockito.when(userRepository.findById("1"))
               .thenReturn(Optional.of(new UserResponse("1", "John", "john@example.com", LocalDateTime.now())));
    }

    @Test
    void shouldFindUser() {
        var user = userRepository.findById("1");  // stub must be used under STRICT_STUBS
        assertTrue(user.isPresent());
    }
}
```

| Level | Behavior |
|-------|----------|
| `STRICT_STUBS` | Throws `UnnecessaryStubbingException` for unused stubs |
| `WARN` | Logs warnings about unused stubs |
| `SILENT` | No checks |

---

## Stubbing patterns

Sequence of return values:
```java
Mockito.when(userRepository.findById("1"))
       .thenReturn(Optional.of(USER_1))
       .thenReturn(Optional.of(USER_2))
       .thenReturn(Optional.empty());
```

Throwing:
```java
Mockito.when(userRepository.findById("1"))
       .thenThrow(new RuntimeException("Database error"));
```

Matchers plus a specific override:
```java
Mockito.when(userRepository.findByEmail(anyString()))
       .thenReturn(Optional.of(GENERIC_USER));
Mockito.when(userRepository.findByEmail(eq("specific@example.com")))
       .thenReturn(Optional.of(SPECIFIC_USER));
```

---

## Verify

```java
import static org.mockito.Mockito.*;

// Basic
verify(userRepository).findById("1");

// Counts
verify(userRepository, times(3)).save(any());
verify(userRepository, atLeastOnce()).findAll();
verify(userRepository, never()).deleteById(any());

// Order
var inOrder = inOrder(userRepository);
inOrder.verify(userRepository).save(any());
inOrder.verify(userRepository).update(any());
```

`ArgumentCaptor` captures the actual argument for assertions:
```java
var captor = ArgumentCaptor.forClass(User.class);
verify(userRepository).save(captor.capture());
assertEquals("test@example.com", captor.getValue().email());
```

---

## Argument matchers

```java
import static org.mockito.ArgumentMatchers.*;

when(repo.findById(anyLong())).thenReturn(Optional.of(user));
when(repo.save(any(User.class))).thenReturn(user);
when(repo.findByName(anyString())).thenReturn(user);
when(repo.findById(eq(1L))).thenReturn(Optional.of(user));
when(repo.findAllById(anyList())).thenReturn(List.of(user));
```

When one argument uses a matcher, all arguments of that call must use matchers (use `eq(...)`
for literal values).

---

## Best practices

1. Use `@Mock` + `@TestComponent` so the mock enters the DI graph.
2. Never attach `MockitoExtension` — it conflicts with `@KoraAppTest`.
3. Use `STRICT_STUBS` for important tests to detect dead stubs.
4. Use `@Spy` only for genuine partial mocking; prefer `@Mock` otherwise.
5. Capture arguments with `ArgumentCaptor` when matchers are not expressive enough.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Mock is `null` | Missing `@TestComponent` | Add `@TestComponent` to the mock field |
| Stub ignored | Stubbing happens after the call | Stub in `@BeforeEach` or before invoking |
| Verify fails | Arguments differ | Match with `any()`/`eq()` or check the real call |
| Extension conflict | `MockitoExtension` + `@KoraAppTest` | Remove `@ExtendWith(MockitoExtension.class)` |
| `ClassCastException` | Wrong generic type | Check the generics in `when(...)` |
