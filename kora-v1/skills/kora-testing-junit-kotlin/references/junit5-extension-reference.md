# Kora JUnit 5 Extension Reference (Kotlin)

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/junit5.md`
**Examples:** `.kora-agent/kora-examples/guides/kotlin/kora-kotlin-guide-testing-junit-app`, `.kora-agent/kora-examples/guides/kotlin/kora-kotlin-guide-testing-integration-app`

Config and Graph modification details for the Kora JUnit 5 extension. For the annotation basics (`@KoraAppTest`, `@TestComponent`, `@Tag`) see [korapptest-kotlin-reference.md](korapptest-kotlin-reference.md).

## Contents

- [@KoraAppTest parameters](#koraapptest-parameters)
- [KoraAppTestConfigModifier](#koraapptestconfigmodifier)
- [KoraAppTestGraphModifier](#koraapptestgraphmodifier)
- [Container initialization](#container-initialization)
- [Best practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## @KoraAppTest parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `value` | `KClass` | Yes | Application interface annotated with `@KoraApp` |
| `components` | `Array<KClass>` | No | Components to initialize in the test |
| `modules` | `Array<KClass>` | No | Modules to add to the test Graph |

```kotlin
@KoraAppTest(
    value = Application::class,
    components = [UserService::class],
    modules = [SomeModule::class]
)
class MyTest
```

---

## KoraAppTestConfigModifier

Implement the interface on the test class (not via the constructor — the modifier runs before component injection, so a constructor cannot deliver it in time).

### System properties

Substitute `${VAR}` placeholders in the default config without replacing it:

```kotlin
@KoraAppTest(Application::class)
class MyTest : KoraAppTestConfigModifier {

    override fun config(): KoraConfigModification =
        KoraConfigModification
            .ofSystemProperty("POSTGRES_JDBC_URL", "jdbc:postgresql://localhost:5432/postgres")
            .withSystemProperty("POSTGRES_USER", "postgres")
            .withSystemProperty("POSTGRES_PASS", "postgres")
}
```

### Config from a classpath file

```kotlin
override fun config(): KoraConfigModification =
    KoraConfigModification.ofResourceFile("application-test.conf")
```

### Config from a string (replaces all config)

```kotlin
override fun config(): KoraConfigModification =
    KoraConfigModification.ofString(
        """
        myconfig {
            myproperty = 1
        }
        """.trimIndent()
    )
```

`ofString` can still reference `${VAR}` placeholders and supply them with `withSystemProperty`, which is the usual Testcontainers pattern.

---

## KoraAppTestGraphModifier

Add or replace components that are not declared in the `@KoraApp`. Implement on the class, never via the constructor.

### Adding a component

```kotlin
@KoraAppTest(Application::class)
class MyTest : KoraAppTestGraphModifier {

    override fun graph(): KoraGraphModification =
        KoraGraphModification.create()
            .addComponent(TypeRef.of(Supplier::class.java, Int::class.java), Supplier { Supplier { 1 } })

    @Test
    fun example(@TestComponent supplier: Supplier<Int>) {
        assertEquals(1, supplier.get())
    }
}
```

### Adding a component derived from an existing one

```kotlin
override fun graph(): KoraGraphModification =
    KoraGraphModification.create()
        .addComponent(TypeRef.of(Supplier::class.java, String::class.java)) { graph ->
            @Suppress("UNCHECKED_CAST")
            val existing = graph.getFirst(TypeRef.of(Supplier::class.java, Int::class.java)) as Supplier<Int>
            Supplier { "1" + existing.get() }
        }
```

### Replacing a component

```kotlin
override fun graph(): KoraGraphModification =
    KoraGraphModification.create()
        .replaceComponent(
            TypeRef.of(Supplier::class.java, String::class.java),
            listOf(Supplier::class.java),
            Supplier { Supplier { "?" } }
        )
```

The third argument is the list of tags the replacement should carry; pass `listOf()` for an untagged component.

### Replacing using the existing component

```kotlin
override fun graph(): KoraGraphModification =
    KoraGraphModification.create()
        .replaceComponent(TypeRef.of(Supplier::class.java, Int::class.java)) { graph ->
            @Suppress("UNCHECKED_CAST")
            val existing = graph.getFirst(TypeRef.of(Supplier::class.java, Int::class.java)) as Supplier<Int>
            Supplier { 1 + existing.get() }
        }
```

Prefer `@MockK` + `@TestComponent` for plain mock replacement; use the Graph modifier when the type is generic, tagged, or the replacement must wrap the original.

---

## Container initialization

Default is PER_METHOD (Graph rebuilt per `@Test`). For one Graph per class:

```kotlin
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
@KoraAppTest(Application::class)
class MyTest
```

---

## Best practices

1. `@MockK` + `@TestComponent` together for mocking — do not add a separate mocking extension.
2. `@TestInstance(PER_CLASS)` when tests do not need a fresh Graph per method.
3. One `KoraAppTestConfigModifier` per class.
4. Use the Graph modifier only for generic/tagged/wrapping replacements; otherwise `@MockK`.

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Component is `null` | Not reachable from a `@Root` | Add `@Root` or use the component from a `@TestComponent` root |
| Mock not applied | `MockKExtension`/`MockitoExtension` attached | Remove the extra `@ExtendWith(...)` |
| Modifier ignored | Implemented via constructor | Implement `config()`/`graph()` on the class body |
| Slow initialization | PER_METHOD lifecycle | Use `@TestInstance(PER_CLASS)` |
| Config not overridden | Multiple `KoraAppTestConfigModifier`s | Keep exactly one per class |
