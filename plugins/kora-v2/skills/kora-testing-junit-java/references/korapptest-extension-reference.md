# KoraAppTest Extension Reference

The full public surface of `io.koraframework:test-junit5` for Java, as it exists at Kora
`2.0.0.RC2`.

## Contents

- [Package map](#package-map)
- [`@KoraAppTest`](#koraapptest)
- [`@TestComponent`](#testcomponent)
- [`@Tag` injection](#tag-injection)
- [Injecting the graph itself](#injecting-the-graph-itself)
- [`KoraAppTestConfigModifier`](#koraapptestconfigmodifier)
- [`KoraAppTestGraphModifier`](#koraapptestgraphmodifier)
- [Graph lifecycle](#graph-lifecycle)
- [Rules the extension enforces](#rules-the-extension-enforces)
- [Troubleshooting](#troubleshooting)

---

## Package map

| Type | Package |
|---|---|
| `KoraAppTest`, `TestComponent` | `io.koraframework.test.extension.junit5` |
| `KoraAppTestConfigModifier`, `KoraConfigModification` | `io.koraframework.test.extension.junit5` |
| `KoraAppTestGraphModifier`, `KoraGraphModification` | `io.koraframework.test.extension.junit5` |
| `KoraAppGraph` | `io.koraframework.test.extension.junit5` |
| `MockitoStrictness` | `io.koraframework.test.extension.junit5.mockito` |
| `TypeRef`, `Graph`, `RefreshableGraph`, `Wrapped` | `io.koraframework.application.graph` |
| `Tag`, `Root`, `Component`, `KoraApp` | `io.koraframework.common.annotation` |

The package is `@NullMarked` (JSpecify), so every parameter and return value is non-null unless
annotated `@Nullable`.

---

## `@KoraAppTest`

```java
@ExtendWith(KoraJUnit5Extension.class)
@Target(TYPE) @Retention(RUNTIME)
public @interface KoraAppTest {
    Class<?> value();               // the @KoraApp interface
    Class<?>[] components() default {};
    Class<?>[] modules() default {};
}
```

The extension loads the class named `<value's FQN> + "Graph"` — the `Supplier<ApplicationGraphDraw>`
the annotation processor generated for that `@KoraApp` — with the application class's own class
loader, copies the draw, then trims it.

| Attribute | Effect |
|---|---|
| `value` | Required. Missing generated graph → `Cannot find generated Kora application graph for: …`, which lists the processor and submodule settings to check |
| `components` | Extra graph roots kept in the trimmed graph. They are **not** injected anywhere; use them to keep a `@Root`-less component alive |
| `modules` | `@Module` interfaces. Every factory method's return type (with its `@Tag`, if any) becomes a root. Java: only `default` methods count. **Entries must be interfaces** — a class is rejected with `Entries in @KoraAppTest(modules = ...) must be interfaces` |

```java
@KoraAppTest(value = Application.class,
             components = { TestComponent23.class },
             modules = { UserCreatedConsumerModule.class })
class SomeTests { }
```

`modules` is the standard way to pull a Kafka consumer or another self-starting component into a
test that never injects it directly.

### Full graph vs subgraph

If the test declares no roots at all (no `@TestComponent`, no `components`, no `modules`, no
mocks), the whole application graph is initialized. Otherwise the extension builds a subgraph out
of the requested roots plus the mocked nodes, which is why an unreferenced component disappears.

---

## `@TestComponent`

```java
@Target({FIELD, PARAMETER}) @Retention(RUNTIME)
public @interface TestComponent {}
```

Marks an element as both a graph root and an injection target. Three injection styles:

```java
// field
@KoraAppTest(Application.class)
class FieldTest {
    @TestComponent
    private UserService userService;
}

// constructor
@KoraAppTest(Application.class)
class ConstructorTest {
    private final UserService userService;

    ConstructorTest(@TestComponent UserService userService) {
        this.userService = userService;
    }
}

// test-method parameter
@KoraAppTest(Application.class)
class MethodTest {
    @Test
    void example(@TestComponent UserService userService) {
        assertNotNull(userService);
    }
}
```

Constructor injection is exclusive: once the graph was created while resolving constructor
parameters, `@TestComponent` and mock annotations on **test-method** parameters are rejected —
move them to the constructor, or switch to field/method injection.

Injected fields may not be `static` or `final`; both produce a dedicated
`ExtensionConfigurationException` naming the field.

### Wrapped components

When the graph node is a `Wrapped<T>` and the requested type is not, the extension injects the
wrapped value — unless the wrapper itself is an instance of the requested type, as with
`JdbcDataSource` and `CassandraSession`, which implement the contract they wrap. Ask for the type
you actually use and the extension resolves it.

---

## `@Tag` injection

Repeat the graph's `@Tag` at the injection point. The extension reads `@Tag` directly on the
element, and also a `@Tag` meta-annotation on any annotation present on the element.

```java
@Tag(LifecycleComponent.class)
@TestComponent
private TestComponent2 tagged;

@Test
void example(@Tag(TestComponent23.class) @TestComponent LifecycleComponent component) { }
```

Without a tag, a type that has several tagged implementations produces:

```
Cannot inject Kora component:
  …
Problem:
  Expected one matching graph component, but found 2:
  - …
Fix:
  Add or correct @Tag to select one component.
```

A common use is forcing a Kafka consumer into the graph by its generated process tag:

```java
@Tag(AutoCommitValueListenerModule.AutoCommitValueListenerProcessTag.class)
@TestComponent
private Lifecycle consumerLifecycle;
```

---

## Injecting the graph itself

Three types resolve without being graph nodes: `KoraAppGraph`, `Graph` and `RefreshableGraph`.
They may be requested as constructor or test-method parameters (`KoraAppGraph` also as a field
with `@TestComponent`), and they may **not** carry a mock annotation — the extension rejects that
with *"Cannot mock Kora graph object"*.

```java
public interface KoraAppGraph {
    @Nullable Object getFirst(Type type);
    @Nullable Object getFirst(Type type, @Nullable Class<?> tag);
    @Nullable <T> T getFirst(Class<T> type);
    @Nullable <T> T getFirst(Class<T> type, @Nullable Class<?> tag);

    default Optional<Object> findFirst(Type type);
    default Optional<Object> findFirst(Type type, Class<?> tag);
    default <T> Optional<T> findFirst(Class<T> type);
    default <T> Optional<T> findFirst(Class<T> type, @Nullable Class<?> tag);

    List<Object> getAll(Type type);
    List<Object> getAll(Type type, @Nullable Class<?> tag);
    <T> List<T> getAll(Class<T> type);
    <T> List<T> getAll(Class<T> type, @Nullable Class<?> tag);
}
```

```java
@Test
void lookUpGeneric(KoraAppGraph graph) {
    assertNotNull(graph.getFirst(TypeRef.of(GenericComponent.class, String.class)));
}
```

---

## `KoraAppTestConfigModifier`

```java
public interface KoraAppTestConfigModifier {
    KoraConfigModification config();
}
```

Implement it **on the test class**. The extension calls it on the test instance, so it cannot be
combined with constructor injection; that combination is rejected with a message explaining that
the graph is built before the instance exists. A `@Nested` class inherits the outer class's
modifier when it has none of its own.

### `KoraConfigModification`

```java
static KoraConfigModification ofString(String config);            // -> config.file (temp file)
static KoraConfigModification ofResourceFile(String configFile);  // -> config.resource
static KoraConfigModification ofSystemProperty(String k, String v);

KoraConfigModification withSystemProperty(String key, String value);
default KoraConfigModification withSystemProperties(Map<String, String> properties);
Map<String, String> systemProperties();
```

How the three layers actually behave, per `HoconConfigModule`:

- `ofString` writes the text to a temporary file and sets the `config.file` system property.
  `ofResourceFile` sets `config.resource`. Either one **replaces** `application.conf` for the test
   — it is not merged on top of it. Setting both is rejected: *"Application config source is
  ambiguous"*.
- System properties are `ConfigFactory.defaultOverrides`, the highest-priority layer. They fill
  `${PLACEHOLDER}` substitutions in whichever config file is active, and they also appear as
  top-level config keys in their own right.
- The properties are installed **only for the duration of graph initialization**: the extension
  clones `System.getProperties()`, sets `config.file`/`config.resource` and the requested
  properties, builds the graph, and restores the snapshot in a `finally` block. They are therefore
  not visible from the test body — read the value from the container object, not from
  `System.getProperty`.
- A test whose config carries system properties takes an exclusive lock while its graph
  initializes, so such classes serialize against each other; classes with no system properties do
  not. Keep `withSystemProperty` for values that genuinely come from a container.
- Initialization failures are wrapped as `@KoraAppTest graph initialization failed after: <time>`
  with the real cause attached.

```java
// substitute into the real application.conf
public KoraConfigModification config() {
    return KoraConfigModification
        .ofSystemProperty("POSTGRES_JDBC_URL", POSTGRES.getJdbcUrl())
        .withSystemProperty("POSTGRES_USER", POSTGRES.getUsername())
        .withSystemProperty("POSTGRES_PASS", POSTGRES.getPassword());
}

// a dedicated test config file on the classpath
public KoraConfigModification config() {
    return KoraConfigModification.ofResourceFile("application-test.conf");
}

// inline, replacing application.conf entirely
public KoraConfigModification config() {
    return KoraConfigModification.ofString("""
            jdbc {
              jdbcUrl = ${POSTGRES_JDBC_URL}
              username = ${POSTGRES_USER}
              password = ${POSTGRES_PASS}
            }
            """)
        .withSystemProperty("POSTGRES_JDBC_URL", POSTGRES.getJdbcUrl())
        .withSystemProperty("POSTGRES_USER", POSTGRES.getUsername())
        .withSystemProperty("POSTGRES_PASS", POSTGRES.getPassword());
}
```

Because `ofString` replaces the file, every key the graph needs must be inside the block, and every
key must be a **Kora 2.0** key — see the config section of the parent skill for the renames
(`db` → `jdbc`, `publicApiHttpPort` → `httpServer.port`, `slidingWindowSize` →
`countBased.windowSize`, telemetry `enabled` defaults).

---

## `KoraAppTestGraphModifier`

```java
public interface KoraAppTestGraphModifier {
    KoraGraphModification graph();
}
```

Also instance-based, so also incompatible with constructor injection.

```java
public final class KoraGraphModification {
    public static KoraGraphModification create();

    public <T> KoraGraphModification addComponent(Type typeToAdd, Supplier<T> instanceSupplier);
    public <T> KoraGraphModification addComponent(Type typeToAdd, @Nullable Class<?> tag, Supplier<T> instanceSupplier);
    public <T> KoraGraphModification addComponent(Type typeToAdd, Function<KoraAppGraph, T> instanceSupplier);
    public <T> KoraGraphModification addComponent(Type typeToAdd, @Nullable Class<?> tag, Function<KoraAppGraph, T> instanceSupplier);

    public <T> KoraGraphModification replaceComponent(Type typeToReplace, Supplier<? extends T> replacement);
    public <T> KoraGraphModification replaceComponent(Type typeToReplace, @Nullable Class<?> tag, Supplier<? extends T> replacement);
    public <T> KoraGraphModification replaceComponent(Type typeToReplace, Function<KoraAppGraph, ? extends T> replacement);
    public <T> KoraGraphModification replaceComponent(Type typeToReplace, @Nullable Class<?> tag, Function<KoraAppGraph, ? extends T> replacement);

    public <T> KoraGraphModification mockComponent(Type typeToMock, Supplier<? extends T> replacement);
    public <T> KoraGraphModification mockComponent(Type typeToMock, @Nullable Class<?> tag, Supplier<? extends T> replacement);
}
```

The tag parameter is a **single `Class<?>`**, not a `List` — that is the shape change from Kora 1.x.
`null` behaves like the overload without a tag.

`Supplier` vs `Function<KoraAppGraph, …>` is not just convenience:

| Form | Dependency handling |
|---|---|
| `replaceComponent(type, supplier)` | Replaces the node **without** keeping its dependencies — they leave the subgraph |
| `replaceComponent(type, graph -> …)` | Replaces the node and **keeps** its dependencies, so the lambda can read them from the graph |
| `mockComponent(type, supplier)` | Same as the `Supplier` form of `replaceComponent`: original dependencies are dropped |

### Adding a component

```java
@Override
public KoraGraphModification graph() {
    return KoraGraphModification.create()
        .addComponent(LifecycleComponent.class, TestComponent23.class,
                      () -> (LifecycleComponent) () -> "?");
}
```

### Adding a component built from an existing one

```java
@Override
public KoraGraphModification graph() {
    return KoraGraphModification.create()
        .addComponent(LifecycleComponent.class, TestComponent23.class, g -> {
            var existing = g.getFirst(TestComponent2.class, LifecycleComponent.class);
            return (LifecycleComponent) () -> "?" + existing.get();
        });
}
```

### Replacing a generic component

```java
@Override
public KoraGraphModification graph() {
    return KoraGraphModification.create()
        .replaceComponent(TypeRef.of(Function.class, String.class, Integer.class),
                          () -> (Function<String, Integer>) s -> 25);
}
```

### Replacing a tagged component

```java
@Override
public KoraGraphModification graph() {
    return KoraGraphModification.create()
        .replaceComponent(TestComponent2.class, LifecycleComponent.class,
                          () -> (TestComponent2) () -> "?");
}
```

### Replacing while keeping the real dependencies

```java
@Override
public KoraGraphModification graph() {
    return KoraGraphModification.create()
        .replaceComponent(TestComponent12.class, graph -> {
            var component1 = graph.getFirst(TestComponent1.class);
            return new TestComponent12(component1) {
                @Override
                public String get() {
                    return "?" + component1.get();
                }
            };
        });
}
```

---

## Graph lifecycle

Controlled by the standard JUnit `@TestInstance` annotation — `@KoraAppTest` has no lifecycle
attribute of its own.

| Lifecycle | Behaviour |
|---|---|
| `PER_METHOD` (default) | A fresh graph per test method; the graph is closed in `afterEach` |
| `PER_CLASS` | One graph per class, closed in `afterAll`; mocks are reset in `beforeEach` |

```java
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
@KoraAppTest(Application.class)
class SharedGraphTest { }
```

`PER_CLASS` is the cheap win for a class of read-only tests: graph construction, container
startup and Flyway migrations happen once. It is unsafe when tests mutate shared state, and it
rules out method-parameter mocks (see below).

`@Nested` classes share the outer class's graph. With a `PER_CLASS` outer class the extension
rejects `@TestComponent` fields on the nested class, because the outer graph is already built.

---

## Rules the extension enforces

Each of these produces an `ExtensionConfigurationException` with a message that states the fix:

- `@TestComponent` on a `static` or `final` field.
- Constructor injection together with `KoraAppTestConfigModifier` or `KoraAppTestGraphModifier`.
- `@TestComponent`/mock annotations on test-method parameters after constructor injection.
- Method-parameter mocks with `@TestInstance(PER_CLASS)`.
- The same candidate declared both as a plain component and as a mock, or both as a mock and a spy.
- A non-interface entry in `@KoraAppTest(modules = …)`.
- A mock annotation on `KoraAppGraph` or `Graph`.
- `@TestComponent` fields on a `@Nested` class whose outer class is `PER_CLASS`.
- A `@Mock`/`@Spy` candidate whose type does not resolve to a raw class.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Cannot find generated Kora application graph` | The test `@KoraApp` was never processed | Add `testAnnotationProcessor "io.koraframework:annotation-processors"`; check `-proc:none` is not set on `compileTestJava` |
| `No matching component was found in the application graph` | Node pruned, or the parent app's submodule is missing | Inject something that depends on it, mark it `@Root`, list it in `components`/`modules`; for a `TestApplication` add `-Akora.app.submodule.enabled=true` to the production module |
| `No matching component…` for `JsonReader<Dto>` | `@TestComponent` selects existing nodes only; `JsonReader<T>` exists only where the app reads `T` | Parse the JSON in the test, or assert on the raw body |
| `Expected one matching graph component, but found N` | Several matching nodes | Add `@Tag` at the injection point |
| `IllegalArgumentException: Graph node belongs to another application graph` (`GraphImpl$GraphConditionKey.hashCode`) at graph init | A `@Conditional` node in the test graph: `copy()`/`subgraph()` keep the original node condition | Fixed in `2.0.0.RC2` (kora-projects/kora PR #963) — only `2.0.0.RC1` is affected; no practical workaround besides keeping `@Conditional` out of the tested graph |
| `PER_CLASS` test fails in `beforeEach` with `…because condition failed: <reason>` | `resetMocks` (Mockito or MockK present) reads every node, including a condition-failed one; `KoraAppGraph.getAll` likewise | Fixed in `2.0.0.RC2` (kora-projects/kora PR #964) — only `2.0.0.RC1` is affected; on RC1 use `PER_METHOD` |
| `Entries in @KoraAppTest(modules = ...) must be interfaces` | A class was listed | List the `@Module` interface instead |
| `Cannot use KoraAppTestConfigModifier with @KoraAppTest constructor injection` | Constructor injection | Use field or test-method injection |
| `Application config source is ambiguous` | `config.file` and `config.resource` both set | One of `ofString` / `ofResourceFile` per class |
| Slow class | Graph rebuilt per method | `@TestInstance(PER_CLASS)` when the tests do not mutate shared state |
