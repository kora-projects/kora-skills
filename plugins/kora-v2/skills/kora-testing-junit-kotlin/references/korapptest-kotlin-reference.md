# @KoraAppTest for Kotlin

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/junit5.md`
**Example:** `.kora-agent/kora-examples/guides/kotlin/kora-kotlin-guide-testing-junit-app`

The core annotations for building a Kora application Graph inside a Kotlin JUnit 5 test and injecting components from it.

## Contents

- [Dependency](#dependency)
- [@KoraAppTest](#koraapptest)
- [@TestComponent](#testcomponent)
- [Tag injection](#tag-injection)
- [@MockK + @TestComponent](#mockk--testcomponent)
- [Container lifecycle](#container-lifecycle)
- [Best practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Dependency

```kotlin
dependencies {
    ksp("ru.tinkoff.kora:symbol-processors")
    testImplementation("ru.tinkoff.kora:test-junit5")
}
```

---

## @KoraAppTest

Builds a test version of the Graph declared by a `@KoraApp` interface:

```kotlin
@KoraAppTest(Application::class)
class MyTest {
    // Graph slice built and components injected before each @Test
}
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `value` | `KClass` | Yes | The application interface annotated with `@KoraApp` |
| `components` | `Array<KClass>` | No | Components to initialize in the test |
| `modules` | `Array<KClass>` | No | Extra modules to include in the test Graph |

### Examples

Basic:

```kotlin
@KoraAppTest(Application::class)
class SimpleTest {
    @TestComponent
    lateinit var userService: UserService
}
```

With explicit components and modules:

```kotlin
@KoraAppTest(
    value = Application::class,
    components = [UserService::class, OrderService::class],
    modules = [SomeModule::class]
)
class ComponentTest
```

---

## @TestComponent

Injects a component from the Graph and makes it a root of the test Graph slice.

### Field injection

```kotlin
@KoraAppTest(Application::class)
class MyTest {
    @TestComponent
    lateinit var userService: UserService
}
```

### Constructor injection

```kotlin
@KoraAppTest(Application::class)
class MyTest(@TestComponent val userService: UserService)
```

### Test-method parameter injection

```kotlin
@KoraAppTest(Application::class)
class MyTest {
    @Test
    fun test(@TestComponent userService: UserService) {
        // usage
    }
}
```

### Rules

1. Every `@TestComponent` must be reachable from a `@Root` component (a `@TestComponent` is itself a root), otherwise it is pruned from the Graph and not built.
2. Combine with `@MockK`/`@SpyK` to mock a dependency.
3. Combine with `@Tag` to inject a tagged component.

---

## Tag injection

Repeat the component's `@Tag` next to the injection point:

```kotlin
@KoraAppTest(Application::class)
class MyTest {
    @Test
    fun example(@Tag(Supplier::class) @TestComponent supplier: Supplier<String>) {
        assertEquals("tag1", supplier.get())
    }
}
```

---

## @MockK + @TestComponent

MockK creates the mock; `@TestComponent` registers it in the Graph in place of the real component. The same mock instance is also injected into every graph component that depends on that type.

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
}
```

Do not add `= mockk()` to a `@MockK` field — the annotation already builds the mock. Do not attach `@ExtendWith(MockKExtension::class)`; it conflicts with `@KoraAppTest`, which owns the mock lifecycle.

---

## Container lifecycle

### PER_METHOD (default)

The Graph is rebuilt for each `@Test` method.

```kotlin
@KoraAppTest(Application::class)
class MyTest {
    // Graph re-created per @Test
}
```

### PER_CLASS

One Graph for all tests in the class:

```kotlin
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
@KoraAppTest(Application::class)
class MyTest {
    // Graph built once for the whole class
}
```

---

## Best practices

1. `@TestInstance(PER_CLASS)` for faster suites — builds the Graph once.
2. `@MockK` + `@TestComponent` together — Kora wires the mock into the Graph.
3. No `MockKExtension`/`MockitoExtension` — conflicts with `@KoraAppTest`.
4. Keep `@TestComponent`s reachable from a `@Root`.

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Component is `null` | Not reachable from a `@Root` | Add `@Root`, or use it from a `@TestComponent` root |
| Mock not applied | `MockKExtension` attached | Remove `@ExtendWith(MockKExtension::class)` |
| Slow initialization | PER_METHOD lifecycle | Use `@TestInstance(PER_CLASS)` |
| `lateinit` not initialized | `val` without initializer | Use `lateinit var` for property injection |
