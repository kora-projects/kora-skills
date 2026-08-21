# KoraAppTest Extension Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/junit5.md`

The core annotations and interfaces for testing Kora applications with JUnit 5.

## Contents

- [@KoraAppTest](#koraapptest)
- [@TestComponent](#testcomponent)
- [@Tag injection](#tag-injection)
- [KoraAppTestConfigModifier](#koraapptestconfigmodifier)
- [KoraAppTestGraphModifier](#koraapptestgraphmodifier)
- [Container lifecycle](#container-lifecycle)
- [Best practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## @KoraAppTest

Builds a trimmed test version of the application graph from a `@KoraApp` interface.

### Syntax

```java
@KoraAppTest(
    value = Application.class,                            // application class (required)
    components = { Component1.class, Component2.class },  // components to initialize
    modules = { Module1.class, Module2.class }           // extra modules to include
)
class MyTest { }
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `value` | `Class` | Yes | The `@KoraApp`-annotated interface used as the graph source |
| `components` | `Class[]` | No | Components to initialize in the test |
| `modules` | `Class[]` | No | Extra `*Module` interfaces to include in the container |

### Examples

Basic:
```java
@KoraAppTest(Application.class)
class SimpleTest {
    @TestComponent
    private UserService userService;
}
```

With explicit components:
```java
@KoraAppTest(value = Application.class, components = { UserService.class, OrderService.class })
class ComponentTest { }
```

With extra modules:
```java
@KoraAppTest(value = Application.class, modules = { SomeModule.class })
class ModuleTest { }
```

---

## @TestComponent

Injects a graph component into the test. Each `@TestComponent` is also a root of the
trimmed graph, so Kora keeps it and its transitive dependencies.

Field injection:
```java
@KoraAppTest(Application.class)
class MyTest {
    @TestComponent
    private Supplier<String> component1;
}
```

Constructor injection:
```java
@KoraAppTest(Application.class)
class MyTest {
    private final Supplier<String> component1;

    MyTest(@TestComponent Supplier<String> component1) {
        this.component1 = component1;
    }
}
```

Method-parameter injection:
```java
@KoraAppTest(Application.class)
class MyTest {
    @Test
    void example(@TestComponent Supplier<String> component1) {
        assertEquals("1", component1.get());
    }
}
```

### Rules

1. Every component used in the test must be reachable from a graph root that is also part
   of the test. The component you inject is itself a root; a component nobody depends on
   will be trimmed unless it is `@Root` in the application graph.
2. Combine with `@Mock`/`@Spy` to substitute dependencies.
3. Combine with `@Tag` to inject a tagged component.

---

## @Tag injection

To inject a dependency that carries an `@Tag` in the graph, repeat the `@Tag` at the
injection point:

```java
@KoraAppTest(Application.class)
class MyTest {
    @Test
    void example(@Tag(Supplier.class) @TestComponent Supplier<String> component1) {
        assertEquals("tag1", component1.get());
    }
}
```

---

## KoraAppTestConfigModifier

Implement this interface to change configuration for the test. It must be implemented via
the interface method, not through the constructor (config is required before construction).

System properties (substituted into the real config file):
```java
@KoraAppTest(Application.class)
class MyTest implements KoraAppTestConfigModifier {
    @NotNull
    @Override
    public KoraConfigModification config() {
        return KoraConfigModification
            .ofSystemProperty("POSTGRES_JDBC_URL", "jdbc:postgresql://localhost:5432/postgres")
            .withSystemProperty("POSTGRES_USER", "postgres")
            .withSystemProperty("POSTGRES_PASS", "postgres");
    }
}
```

Config from a resource file:
```java
@Override
public KoraConfigModification config() {
    return KoraConfigModification.ofResourceFile("application-test.conf");
}
```

Inline config (replaces all config files for the test):
```java
@Override
public KoraConfigModification config() {
    return KoraConfigModification.ofString("""
        myconfig {
            myproperty = 1
        }
        """);
}
```

---

## KoraAppTestGraphModifier

Implement this interface to add, replace, or mock components in the container. Also
constructor-forbidden (the graph is needed before construction).

### Adding a component

```java
@KoraAppTest(Application.class)
class MyTest implements KoraAppTestGraphModifier {
    @Override
    public KoraGraphModification graph() {
        return KoraGraphModification.create()
            .addComponent(TypeRef.of(Supplier.class, Integer.class),
                          () -> (Supplier<Integer>) () -> 1);
    }

    @Test
    void example(@TestComponent Supplier<Integer> supplier) {
        assertEquals(1, supplier.get());
    }
}
```

### Adding a component built from an existing one

```java
@Override
public KoraGraphModification graph() {
    return KoraGraphModification.create()
        .addComponent(TypeRef.of(Supplier.class, String.class),
            graph -> {
                var existing = (Supplier<Integer>) graph.getFirst(TypeRef.of(Supplier.class, Integer.class));
                return (Supplier<String>) () -> "1" + existing.get();
            });
}
```

### Replacing a component

The middle argument is the list of `@Tag` classes on the target component (empty list when
the component is untagged):

```java
@Override
public KoraGraphModification graph() {
    return KoraGraphModification.create()
        .replaceComponent(TypeRef.of(Supplier.class, String.class),
                          List.of(Supplier.class),
                          () -> (Supplier<String>) () -> "?");
}
```

### Replacing using the existing value

```java
@Override
public KoraGraphModification graph() {
    return KoraGraphModification.create()
        .replaceComponent(TypeRef.of(Supplier.class, Integer.class),
            graph -> {
                var existing = (Supplier<Integer>) graph.getFirst(TypeRef.of(Supplier.class, Integer.class));
                return (Supplier<Integer>) () -> 1 + existing.get();
            });
}
```

---

## Container lifecycle

By default the graph is rebuilt for every `@Test` method. To build it once per class, use
the standard JUnit lifecycle annotation:

```java
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
@KoraAppTest(Application.class)
class MyTest {
    // one container shared by all test methods in the class
}
```

---

## Best practices

1. Use `@Mock` + `@TestComponent` together to mock dependencies.
2. Do not attach `MockitoExtension`/`MockKExtension` — they conflict with `@KoraAppTest`.
3. Mark test-only components `@Root` so they enter the graph.
4. Use `@TestInstance(PER_CLASS)` to speed up classes that do not need per-method isolation.
5. Override config via `KoraAppTestConfigModifier` rather than hardcoding values in tests.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Component is `null` | Not reachable from a root | Add `@Root` or inject a component that depends on it |
| Mock not applied | `MockitoExtension` attached | Remove `@ExtendWith(MockitoExtension.class)` |
| Slow initialization | `PER_METHOD` lifecycle | Use `@TestInstance(PER_CLASS)` |
| Config conflict | Multiple `KoraAppTestConfigModifier` | One config modifier per class |
