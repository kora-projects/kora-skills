# JUnit5 Extension Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/testing.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/testing.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-helloworld/`

Documentation for using the Kora JUnit5 extension for application testing.

## Overview

The Kora JUnit5 extension provides annotations and mechanisms for testing Kora applications at all levels: component, integration, and black-box tests.

**Key features:**
- Automatic initialization of the Kora DI container in tests
- Component injection via `@TestComponent`
- Mock/Stub of components via Mockito (Java) or MockK (Kotlin)
- Configuration modification via `KoraAppTestConfigModifier`
- Dependency graph modification via `KoraAppTestGraphModifier`

---

## @KoraAppTest

The main annotation for Kora application tests.

### Syntax

```java
@KoraAppTest(
    value = Application.class,      // Application class (required)
    components = { Component1.class, Component2.class },  // Components
    modules = { Module1.class, Module2.class }            // Modules
)
class MyTest { }
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `value` | Class | Yes | Application class annotated with `@KoraApp` |
| `components` | Class[] | No | Components to initialize in the test |
| `modules` | Class[] | No | Modules to include in the test |

### Examples

**Basic test:**
```java
@KoraAppTest(Application.class)
class SimpleTest {
    @TestComponent
    private UserService userService;
}
```

**With specified components:**
```java
@KoraAppTest(
    value = Application.class,
    components = { UserService.class, OrderService.class }
)
class ComponentTest { }
```

**With specified modules:**
```java
@KoraAppTest(
    value = Application.class,
    modules = { DatabaseModule.class, CacheModule.class }
)
class ModuleTest { }
```

---

## @TestComponent

Annotation for injecting components from the DI container into a test.

### Injection methods

**Into a field:**
```java
@KoraAppTest(Application.class)
class MyTest {
    @TestComponent
    private UserService userService;
}
```

**Into a constructor:**
```java
@KoraAppTest(Application.class)
class MyTest {
    private final UserService userService;
    
    MyTest(@TestComponent UserService userService) {
        this.userService = userService;
    }
}
```

**Into method parameters:**
```java
@KoraAppTest(Application.class)
class MyTest {
    @Test
    void test(@TestComponent UserService userService) {
        // usage
    }
}
```

### Important rules

1. **All components annotated with `@TestComponent` must be used by a `@Root` component** — otherwise they will not be included in the graph
2. **Can be combined with `@Mock`/`@Spy`** — for mocking dependencies
3. **Can be combined with `@Tag`** — for injection by tag

### Example with @Root

```java
@KoraAppTest(Application.class)
class MyTest {
    @Root
    @TestComponent
    private UserService userService;  // @Root guarantees inclusion in the graph
}
```

---

## Mock/Stub of components

### Java + Mockito

**Dependency:**
```groovy
testImplementation "org.mockito:mockito-core:5.18.0"
```

**Example with @Mock:**
```java
@KoraAppTest(Application.class)
class OrderServiceTest {
    @Mock
    @TestComponent
    private UserRepository userRepository;
    
    @TestComponent
    private OrderService orderService;
    
    @BeforeEach
    void setup() {
        Mockito.when(userRepository.findById(1L))
               .thenReturn(Optional.of(new User(1L, "test")));
    }
    
    @Test
    void test() {
        var order = orderService.create(1L, 99.99);
        assertNotNull(order);
    }
}
```

**Example with @Spy:**
```java
@KoraAppTest(Application.class)
class MyTest {
    @Spy
    @TestComponent
    private UserService userService = new UserService();
    
    @Test
    void test() {
        Mockito.doNothing().when(userService).sendEmail(any());
        userService.register("test@example.com");
        Mockito.verify(userService).sendEmail(any());
    }
}
```

### Kotlin + MockK

**Dependency:**
```groovy
testImplementation "io.mockk:mockk:1.13.11"
```

**Example with @MockK:**
```kotlin
@KoraAppTest(Application::class)
class OrderServiceTest {
    @MockK
    @TestComponent
    private val userRepository: UserRepository = mockk()
    
    @TestComponent
    private lateinit var orderService: OrderService
    
    @BeforeEach
    fun setup() {
        every { userRepository.findById(1L) } returns Optional.of(User(1L, "test"))
    }
    
    @Test
    fun test() {
        val order = orderService.create(1L, 99.99)
        assertNotNull(order)
    }
}
```

**Example with @SpyK:**
```kotlin
@KoraAppTest(Application::class)
class MyTest {
    @SpyK
    @TestComponent
    private val userService: UserService = spyk(UserService())
    
    @Test
    fun test() {
        every { userService.sendEmail(any()) } just Runs
        userService.register("test@example.com")
        verify { userService.sendEmail(any()) }
    }
}
```

---

## KoraAppTestConfigModifier

Interface for modifying configuration in tests.

### System properties

```java
@KoraAppTest(Application.class)
class MyTest implements KoraAppTestConfigModifier {
    @Override
    public KoraConfigModification config() {
        return KoraConfigModification
            .ofSystemProperty("DB_URL", "jdbc:postgresql://localhost:5432/test")
            .withSystemProperty("DB_USER", "postgres")
            .withSystemProperty("DB_PASS", "postgres");
    }
}
```

### Configuration from a file

```java
@KoraAppTest(Application.class)
class MyTest implements KoraAppTestConfigModifier {
    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofResourceFile("application-test.conf");
    }
}
```

### Configuration from a string

```java
@KoraAppTest(Application.class)
class MyTest implements KoraAppTestConfigModifier {
    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofString("""
            db {
                url = "jdbc:postgresql://localhost:5432/test"
                user = "postgres"
            }
            """);
    }
}
```

---

## KoraAppTestGraphModifier

Interface for adding/replacing components in the dependency graph.

### Adding a component

```java
@KoraAppTest(Application.class)
class MyTest implements KoraAppTestGraphModifier {
    @Override
    public KoraGraphModification graph() {
        return KoraGraphModification.create()
            .addComponent(
                TypeRef.of(Supplier.class, Integer.class),
                () -> (Supplier<Integer>) () -> 42
            );
    }
    
    @Test
    void test(@TestComponent Supplier<Integer> supplier) {
        assertEquals(42, supplier.get());
    }
}
```

### Replacing a component

```java
@KoraAppTest(Application.class)
class MyTest implements KoraAppTestGraphModifier {
    @Override
    public KoraGraphModification graph() {
        return KoraGraphModification.create()
            .replaceComponent(
                TypeRef.of(UserService.class),
                List.of(),
                new MockUserService()
            );
    }
}
```

### Using an existing component

```java
@KoraAppTest(Application.class)
class MyTest implements KoraAppTestGraphModifier {
    @Override
    public KoraGraphModification graph() {
        return KoraGraphModification.create()
            .replaceComponent(
                TypeRef.of(Supplier.class, Integer.class),
                graph -> {
                    var existing = (Supplier<Integer>) graph.getFirst(
                        TypeRef.of(Supplier.class, Integer.class)
                    );
                    return (Supplier<Integer>) () -> 1 + existing.get();
                }
            );
    }
}
```

---

## Container initialization

### By default (PER_METHOD)

The container is initialized for each test.

```java
@KoraAppTest(Application.class)
class MyTest {
    // Container is re-created for each @Test
}
```

### Once per class (PER_CLASS)

```java
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
@KoraAppTest(Application.class)
class MyTest {
    // Container is created once for all tests in the class
}
```

---

## Best Practices

1. **Use `@Mock` + `@TestComponent` together** — for mocking dependencies
2. **Do not use `MockitoExtension`/`MockKExtension`** — conflicts with `@KoraAppTest`
3. **`@Root` for components in tests** — guarantees inclusion in the graph
4. **`PER_CLASS` for speed** — if tests do not require full isolation
5. **KoraAppTestConfigModifier for configuration** — instead of hardcoding in tests

---

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| Component is null | `@Root` not used | Add `@Root` or use the component in another `@Root` |
| Mock does not work | `MockitoExtension` is used | Remove `@ExtendWith(MockitoExtension.class)` |
| Slow initialization | `PER_METHOD` mode | Use `@TestInstance(PER_CLASS)` |
| Configuration conflict | Multiple `KoraAppTestConfigModifier` | Use only one per class |
