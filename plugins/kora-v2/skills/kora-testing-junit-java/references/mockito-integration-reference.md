# Mockito Integration Reference

Mocking and spying components inside a Kora 2.0 Java test graph. The extension has first-class
Mockito support built in: it reads `org.mockito.Mock` and `org.mockito.Spy`, creates the
instances, swaps them into the application graph, resets them and reports unused stubbing.

## Contents

- [Dependency and the Java 25 floor](#dependency-and-the-java-25-floor)
- [`@Mock` + `@TestComponent`](#mock--testcomponent)
- [`@Mock` attributes](#mock-attributes)
- [`@Spy`](#spy)
- [Mock strictness](#mock-strictness)
- [What the extension does with your mocks](#what-the-extension-does-with-your-mocks)
- [Stubbing patterns](#stubbing-patterns)
- [Verify](#verify)
- [Argument matchers](#argument-matchers)
- [Troubleshooting](#troubleshooting)

---

## Dependency and the Java 25 floor

```groovy
testImplementation "org.mockito:mockito-core:5.24.0"
```

Mockito is `compileOnly` inside `io.koraframework:test-junit5`, and `io.koraframework:kora-bom`
constrains only Kora's own artifacts — so the version is entirely yours to choose, and choosing
badly fails at runtime, not at compile time.

**Kora 2.0 artifacts are compiled to class-file version 69 (Java 25).** Mockito generates mocks
with Byte Buddy, and a Byte Buddy that predates Java 25 refuses to instrument those classes:

```
java.lang.IllegalArgumentException: Java 25 (69) is not supported by the current version of Byte Buddy
```

Worse, when the mock is created while the graph is being built, that exception is swallowed into

```
Application graph failed to initialize with N errors
```

with no visible suppressed exception, so it reads like a dependency-injection problem.

- `mockito-core` `5.24.0` (Byte Buddy `1.18.14`) is what the framework's own version catalog pins —
  use it as the floor. Several migrated examples still carry `5.18.0`; do not copy that number.
- Diagnose with
  `./gradlew <module>:dependencyInsight --dependency byte-buddy --configuration testRuntimeClasspath`.
- `-Dnet.bytebuddy.experimental=true` only disables the safety check. It is a temporary probe, not
  a fix.

---

## `@Mock` + `@TestComponent`

`@Mock` alone is invisible to the extension — it only inspects elements that also carry
`@TestComponent`. Together they replace that node in the graph, so every component that depends on
the type receives the mock, and the test field points at the same instance.

```java
@KoraAppTest(Application.class)
class UserServiceTest {

    @Mock
    @TestComponent
    private UserRepository userRepository;

    @TestComponent
    private UserService userService;

    @Test
    void shouldReturnUser() {
        when(userRepository.findById("1"))
            .thenReturn(Optional.of(new UserResponse("1", "John", "john@example.com", LocalDateTime.now())));

        var user = userService.getUser("1");

        assertTrue(user.isPresent());
        verify(userRepository).findById("1");
    }
}
```

Mocks work on fields, constructor parameters and test-method parameters:

```java
@Test
void methodParameterMock(@Mock @TestComponent UserRepository repository,
                         @TestComponent UserService service) { }
```

Method-parameter mocks are per-method by nature, so they are rejected under
`@TestInstance(PER_CLASS)`, where one graph is shared by every method.

**Do not add `@ExtendWith(MockitoExtension.class)`.** Kora already owns creation, graph injection,
reset and unused-stub reporting; the second extension builds a parallel set of mocks that never
enters the graph.

---

## `@Mock` attributes

The extension maps the standard `@Mock` attributes onto the Mockito mock settings it creates:
`name`, `answer`, `mockMaker`, `extraInterfaces`, `strictness`, `withoutAnnotations`, `stubOnly`
and `serializable`. When `strictness` is left at `TEST_LEVEL_DEFAULT`, the class-level setting
applies.

```java
@Mock(name = "userRepository", answer = Answers.RETURNS_DEEP_STUBS)
@TestComponent
private UserRepository userRepository;

@Mock(strictness = Mock.Strictness.LENIENT)
@TestComponent
private AuditLog auditLog;
```

If the mocked type is not a class or a parameterized class (a raw `Type` the extension cannot
reduce to a `Class`), it fails with *"Component type does not resolve to a raw class"*.

---

## `@Spy`

`@Spy` keeps the real behaviour and lets you override selected methods. Two shapes:

**Spy the instance you supply** — a field initializer. The extension replaces the node with a spy
over that value and drops the node's original dependencies.

```java
@Spy
@TestComponent
private Supplier<String> component1 = () -> "12345";
```

**Spy the instance the graph builds** — no initializer, or a method/constructor parameter. The
extension keeps the node's dependencies, lets the real factory build the component, and wraps the
result.

```java
@Spy
@TestComponent
private UserRepository realRepositoryUnderSpy;

@Test
void spyParameter(@Spy @TestComponent Supplier<String> component1) {
    when(component1.get()).thenReturn("?");
    assertEquals("?", component1.get());
}
```

Stub a spy with `doReturn`/`doThrow`/`doNothing` rather than `when(...)` whenever calling the real
method would have a side effect — `when(spy.method())` invokes it for real while stubbing.

An already-spied instance is not wrapped twice.

---

## Mock strictness

```java
import io.koraframework.test.extension.junit5.mockito.MockitoStrictness;
import org.mockito.quality.Strictness;

@MockitoStrictness(Strictness.STRICT_STUBS)
@KoraAppTest(Application.class)
class UserServiceTest { }
```

Note the package: `io.koraframework.test.extension.junit5.mockito`, a subpackage of the extension.

| Level | Behaviour |
|---|---|
| `STRICT_STUBS` | Unused stubs fail the test with `UnnecessaryStubbingException`; argument mismatches are reported |
| `WARN` | **Default when the annotation is absent.** Unused stubs are logged as warnings through SLF4J |
| `LENIENT` | No reporting |

Mockito's `Strictness` enum has exactly these three constants — there is no `SILENT`.

The extension runs its own reporter in `afterEach`, over the mocks and spies it created, using
Mockito's `UniversalTestListener`. The annotation is looked up on the test class, its superclasses
and enclosing contexts, so a base class can set it once.

---

## What the extension does with your mocks

| Moment | Behaviour |
|---|---|
| Graph build | Every `@Mock`/`@Spy` candidate node is located and replaced. `@Mock` and initializer-`@Spy` drop the node's dependencies; graph-`@Spy` keeps them |
| `beforeEach`, `PER_CLASS` | All mocks in the graph are reset, including mocks inside `Wrapped<T>` nodes |
| `beforeEach`, `PER_METHOD` | Nothing to reset — the graph is new |
| `afterEach` | Unused-stubbing report at the configured strictness; with `PER_METHOD` the graph is also released |

A candidate declared both as a component and as a mock (or both mock and spy) is rejected before
the graph is built.

---

## Stubbing patterns

Sequence of return values:

```java
when(userRepository.findById("1"))
    .thenReturn(Optional.of(USER_1))
    .thenReturn(Optional.of(USER_2))
    .thenReturn(Optional.empty());
```

Throwing:

```java
when(userRepository.findById("1")).thenThrow(new IllegalStateException("Database error"));
```

Answer computed from the arguments — useful for repositories that echo what they were given:

```java
when(petCache.put(anyLong(), any())).then(invocation -> invocation.getArguments()[1]);
```

Matchers plus a specific override:

```java
when(userRepository.findByEmail(anyString())).thenReturn(Optional.of(GENERIC_USER));
when(userRepository.findByEmail(eq("specific@example.com"))).thenReturn(Optional.of(SPECIFIC_USER));
```

Kora 2.0 contracts are synchronous, so stub plain values: `Optional<T>`, `List<T>`, `T`, `long`.
There is nothing to unwrap — no `Mono.just(...)`, no `CompletableFuture.completedFuture(...)`.

---

## Verify

```java
import static org.mockito.Mockito.*;

verify(userRepository).findById("1");
verify(userRepository, times(3)).save(any());
verify(userRepository, atLeastOnce()).findAll();
verify(userRepository, never()).deleteById(any());

var inOrder = inOrder(userRepository);
inOrder.verify(userRepository).save(any());
inOrder.verify(userRepository).update(any(), any(), any());
```

`ArgumentCaptor` when a matcher cannot express the assertion:

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
when(cache.get(anyCollection())).thenReturn(Map.of());
```

When one argument uses a matcher, every argument of that call must use one — wrap literals in
`eq(...)`.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Java 25 (69) is not supported by the current version of Byte Buddy` | Old Mockito / Byte Buddy | `mockito-core:5.24.0` |
| `Application graph failed to initialize with N errors`, no cause shown | The same Byte Buddy failure, swallowed | Same fix; temporarily enable `junitXml.required` to see suppressed exceptions |
| Mock field stays `null` | `@Mock` without `@TestComponent` | Add `@TestComponent` |
| The real implementation runs instead of the mock | The mock never entered the graph | `@Mock` + `@TestComponent` on the same element, and no `MockitoExtension` |
| Duplicated mocks / doubled strictness reports | `@ExtendWith(MockitoExtension.class)` | Remove it |
| `Cannot create @Mock using Mockito … does not resolve to a raw class` | Mocked type is not a class or parameterized class | Declare the mock on a class type |
| `Cannot inject mocks through test method parameters with TestInstance.Lifecycle.PER_CLASS` | Per-method mocks with a shared graph | Use `PER_METHOD`, or move the mock to a field/constructor parameter |
| `PER_CLASS`: `beforeEach` fails in `resetMocks` with `Graph node value was not initialized because condition failed` | The reset reads every graph node, and a `@Conditional` node whose condition failed throws on read | Fixed in `2.0.0.RC2` (kora-projects/kora PR #964) — only `2.0.0.RC1` is affected; on RC1 use `PER_METHOD` |
| `UnnecessaryStubbingException` | `STRICT_STUBS` and a stub nobody used | Delete the stub or relax the level for that mock with `@Mock(strictness = LENIENT)` |
| Stub ignored | Stubbed after the call | Stub in `@BeforeEach` or before invoking |
