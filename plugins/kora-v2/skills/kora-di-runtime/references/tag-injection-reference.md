# `@Tag` Reference — disambiguation in Kora 2.0

**Kora 2.0** · `io.koraframework.common.annotation.Tag`

---

## 1. The annotation

```java
package io.koraframework.common.annotation;

@Retention(RetentionPolicy.RUNTIME)
@Target({ElementType.METHOD, ElementType.PARAMETER, ElementType.FIELD, ElementType.TYPE, ElementType.TYPE_USE})
public @interface Tag {

    @Tag(Any.class)
    @interface Any {}

    @Tag(Factory.class)
    @interface Factory {}

    Class<?> value();
}
```

The value is a **`Class`**, never a string. Both nested marker types from 1.x survive under the same
names; `Tag.Factory` is new in 2.0 and is described in §5.

> Import from **`io.koraframework.common.annotation`**. `io.koraframework.common` holds
> `Configurer`, `Either`, `Principal`, `PromisedProxy` and the `liveness/`, `naming/`, `readiness/`,
> `telemetry/`, `util/` subpackages — no DI annotations.

---

## 2. Matching rules

Compile-time matching is `TagUtils.tagsMatch(requiredTag, providedTag)`:

| Injection point | Component untagged | Component `@Tag(A.class)` | Component `@Tag(B.class)` |
|---|---|---|---|
| untagged | match | no | no |
| `@Tag(A.class)` | no | match | no |
| `@Tag(Tag.Any.class)` | match | match | match |

Two facts follow that surprise people:

- an **untagged** injection point does not see tagged components. Tagging one implementation of an
  interface removes it from every untagged consumer of that interface;
- `Tag.Any` is meaningful only at the **injection point**. Putting `@Tag(Tag.Any.class)` on a
  component is not a wildcard registration.

---

## 3. Tag classes

A tag is a type token. Any type works; a small, empty, purpose-named class is what the migrated
examples use, and it keeps rename/find-usages working.

```java
public final class RedisTag {
    private RedisTag() {}
}
```

```kotlin
class RedisTag private constructor()
```

Where the tag belongs to one module, nesting it keeps the namespace tidy — this is the shape used in
the migrated DI guide:

```java
@Module
public interface SmsModule {

    final class SmsTag {
        private SmsTag() {}
    }

    @Tag(SmsTag.class)
    default Notifier smsNotifier(@Nullable SmsCellularProvider provider) { … }
}
```

Referenced as `@Tag(SmsModule.SmsTag.class)` from outside the module.

Reusing an existing type as a tag is legal and common in framework modules — e.g. Kora's own HTTP
server interceptors are tagged with the `HttpServer` interface itself. Prefer a dedicated marker for
application code, where the intent is not otherwise obvious.

### Annotation tags

`TagUtils.parseTagValue` also reads a tag off an annotation that is *itself* meta-annotated with
`@Tag`. That is how `Tag.Any` and `Tag.Factory` work, and you can define your own:

```java
@Tag(RedisTag.class)
@Retention(RetentionPolicy.RUNTIME)
@Target({ElementType.TYPE, ElementType.METHOD, ElementType.PARAMETER})
public @interface Redis {}
```

`@Redis` then behaves exactly like `@Tag(RedisTag.class)`. Useful when one tag is repeated across
many injection points; unnecessary otherwise.

---

## 4. Where `@Tag` goes

**On a component class** — the component is registered under that tag:

```java
@Tag(RedisTag.class)
@Component
public final class RedisCache implements Cache { … }
```

**On a factory method** — the produced component is registered under that tag:

```java
@Tag(RedisTag.class)
default Cache redisCache(RedisConfig config) { … }
```

**On an injection point** — constructor parameter or module-method parameter:

```java
@Component
public final class UserService {

    public UserService(@Tag(RedisTag.class) Cache remote,
                       @Tag(LocalTag.class) Cache local) { … }
}
```

**Overriding a module method in `@KoraApp`** — the override must repeat the tag, otherwise it
registers an untagged component and the tagged consumers stop seeing it:

```java
@KoraApp
public interface Application extends EmailModule {

    @Tag(EmailModule.EmailTag.class)
    @Override
    default Supplier<String> emailNotifierHeaderSupplier() {
        return () -> "[EMAIL OVERRIDDEN] ";
    }
}
```

Kotlin is the same, with `::class`:

```kotlin
@Component
class UserService(
    @Tag(RedisTag::class) private val remote: Cache,
    @Tag(LocalTag::class) private val local: Cache
)
```

---

## 5. `Tag.Factory` — the tag of the enclosing factory module

`@FactoryModule` (new in 2.0) marks a module method whose **return value is itself a module**: the
returned object is registered as a component and its own methods are processed as component
providers.

Inside such a factory module, `@Tag(Tag.Factory.class)` means *"the tag of the factory-module method
that produced this module"*. The processor substitutes it in two places:

- on a provider method of the factory module — `ComponentDeclaration.fromModule` replaces the tag
  with the factory module's tag;
- on a **parameter** of such a method — `ComponentDependencyHelper.parseDependencyClaims` does the
  same, so the method resolves its dependencies from its own tagged family.

Used outside a factory module it is a compile error:

```
@Tag.Factory can only be used inside factory modules:
  module: com.example.StorageModule

Declared at:
  com.example.StorageModule#storage(
    StorageConfig)

Fix:
  - Move this provider to a factory module (@FactoryModule).
  - Replace @Tag.Factory with an explicit @Tag(...) value.
```

**Why it exists.** It lets one factory module class be instantiated several times under different
tags and produce several independently-configured families of components of the same types, without
writing the tags into the module itself. Kora's own AWS S3 module is exactly this shape:

```java
public interface AwsS3ClientModule {

    @FactoryModule
    default AwsS3ClientFactoryModule awsS3ClientFactoryModule() {
        return new AwsS3ClientFactoryModule("s3client.aws");
    }
}

public class AwsS3ClientFactoryModule {

    private final String configPath;

    public AwsS3ClientFactoryModule(String configPath) { this.configPath = configPath; }

    @Tag(Tag.Factory.class)
    public AwsS3Config awsS3Config(Config config, ConfigValueMapper<AwsS3Config> mapper) {
        return mapper.mapOrThrow(config.get(configPath));
    }

    @Tag(Tag.Factory.class)
    public S3Client awsS3Client(@Tag(Tag.Factory.class) AwsS3Config config,
                                @Tag(Tag.Factory.class) AwsS3ClientFactory factory) {
        return factory.create(config);
    }
}
```

The seemingly alarming `@Tag(Tag.Factory.class)` on `awsS3Client` does **not** make the `S3Client`
tagged for consumers: `awsS3ClientFactoryModule()` itself carries no tag, so `Tag.Factory` resolves
to "no tag" and applications inject a plain `S3Client`. Add a tag to the factory-module method and
the whole family — config, HTTP client, `S3Client` — moves under that tag together.

To declare a second, differently-configured client, add another `@FactoryModule` method with its own
tag and config path.

---

## 6. Tags and collections

`@Tag` on an `All<T>` parameter selects which components are collected — see
[`collection-injection-reference.md`](collection-injection-reference.md).

## 7. Tags and interceptors

A `GraphInterceptor` is matched against a component by exact type **and** by tag, with the
interceptor's tag on the "required" side: an untagged interceptor intercepts only untagged
components, and `@Tag(Tag.Any.class)` on the interceptor intercepts every tag. See
[`graph-interceptor-reference.md`](graph-interceptor-reference.md).

---

## 8. Pitfalls

| Symptom | Cause |
|---|---|
| ambiguous-dependency build error | two untagged components of one type — tag them, or mark one `@DefaultComponent` |
| "no component found" after tagging one implementation | untagged consumers no longer match; tag the injection point too |
| a `@KoraApp` override silently disconnects consumers | the override dropped the `@Tag` |
| `@Tag.Factory can only be used inside factory modules` | used outside a `@FactoryModule`-provided module |
| Kotlin `ClassCastException: String cannot be cast to KSType` in KSP | a 1.x string-valued annotation left in place; 2.0 tags are `Class`/`KClass` |
| tag imported from `io.koraframework.common.Tag` | wrong package — it is `io.koraframework.common.annotation.Tag` |

---

## See also

- [`collection-injection-reference.md`](collection-injection-reference.md) — `All<T>` and tag semantics
- [`graph-interceptor-reference.md`](graph-interceptor-reference.md) — tag matching for interceptors
- [`kora-di-compile`](../../kora-di-compile/SKILL.md) — `@Module`, `@FactoryModule`, `@DefaultComponent` declarations
