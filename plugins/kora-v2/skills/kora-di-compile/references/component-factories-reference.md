# Component Factories Reference

**Applies to:** Kora 2.x (`io.koraframework`)

## Contents

- [Overview](#overview)
- [1. @Component — Auto Factory](#1-component--auto-factory)
- [2. Providers on @KoraApp](#2-providers-on-koraapp)
- [3. @Module Providers](#3-module-providers)
- [4. Generic Providers (Templates)](#4-generic-providers-templates)
- [5. @FactoryModule — Parameterised Modules](#5-factorymodule--parameterised-modules)
- [6. Extension Factories](#6-extension-factories)
- [Provider Patterns](#provider-patterns)
- [Factory Selection Guide](#factory-selection-guide)
- [Common Mistakes](#common-mistakes)
- [Related References](#related-references)

## Overview

A "factory" is anything the processor can call to obtain an instance. Kora 2.0 has six forms, and
choosing correctly is mostly about *who owns the construction* and *how many instances you need*.

## 1. `@Component` — Auto Factory

```java
import io.koraframework.common.annotation.Component;

@Component
public final class UserService {
    private final UserRepository repository;

    public UserService(UserRepository repository) {
        this.repository = repository;
    }
}
```

Requirements: a class, not abstract, exactly one public constructor, no raw types. `final` is a
convention, not a rule — and a class carrying an aspect annotation must **not** be final (Java) and
must be `open` (Kotlin). See
[Component Registration Reference](component-registration-reference.md).

## 2. Providers on `@KoraApp`

The `@KoraApp` interface is itself a module:

```java
@KoraApp
public interface Application extends HoconConfigModule {

    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }

    default Clock clock() { return Clock.systemUTC(); }

    default SomeService someService(Clock clock) { return new SomeService(clock); }
}
```

Good for one-offs and overrides. Anything reusable belongs in a `@Module`.

## 3. `@Module` Providers

```java
import io.koraframework.common.annotation.Module;

@Module
public interface StorageModule {

    default Function<String, byte[]> stringMapper() {
        return s -> s.getBytes(StandardCharsets.UTF_8);
    }

    default Storage<String> stringStorage(Function<String, byte[]> mapper) {
        return new TempFileStorage<>(mapper);
    }
}
```

Constraints enforced by the processor:

- `@Module` on **interfaces** only
- providers are `default` methods (Kotlin: bodied interface functions); `private`/`static` are ignored
- the return type must be a reference type and must not be raw
- a provider must not return `null` unless every consumer declares its parameter `@Nullable`

## 4. Generic Providers (Templates)

A provider with a type parameter is a **template**. The processor instantiates it once per concrete
type argument actually requested:

```java
@Module
public interface StorageModule {

    default Function<Integer, byte[]> intMapper()   { return i -> new byte[] {i.byteValue()}; }
    default Function<String, byte[]> stringMapper() { return s -> s.getBytes(UTF_8); }

    default <T> Storage<T> typedStorage(Function<T, byte[]> mapper) {
        return new TempFileStorage<>(mapper);
    }
}
```

```kotlin
@Module
interface StorageModule {

    fun intMapper(): Function<Int, ByteArray> = Function { i -> byteArrayOf(i.toByte()) }
    fun stringMapper(): Function<String, ByteArray> = Function { s -> s.toByteArray(UTF_8) }

    fun <T> typedStorage(mapper: Function<T, ByteArray>): Storage<T> = TempFileStorage(mapper)
}
```

`Storage<String>` resolves to `typedStorage(stringMapper())`, `Storage<Integer>` to
`typedStorage(intMapper())`. Templates are consulted only after concrete declarations fail. When
several templates match, the processor resolves each in isolation and requires exactly one to
succeed; two successes give `Multiple components match dependency`, none re-raises the underlying
`No component found`.

## 5. `@FactoryModule` — Parameterised Modules

New in 2.0. `@FactoryModule` (`io.koraframework.common.annotation.FactoryModule`) marks a module
method whose **return value is itself a module**. The returned type is registered as a component,
and its public instance methods become providers in the graph.

This is what lets the *same* module code be instantiated more than once with different constructor
arguments — different config paths, different tags:

```java
public class HttpClientFactoryModule {

    private final String configPath;

    public HttpClientFactoryModule(String configPath) {
        this.configPath = configPath;
    }

    @Tag(Tag.Factory.class)
    public HttpClientConfig httpClientConfig(Config config, ConfigValueMapper<HttpClientConfig> mapper) {
        return mapper.mapOrThrow(config.get(this.configPath));
    }
}

public interface OkHttpClientModule extends HttpClientModule {

    @FactoryModule
    default OkHttpClientFactoryModule okHttpClientFactory() {
        return new OkHttpClientFactoryModule("httpClient");
    }
}
```

### `@Tag(Tag.Factory.class)`

Inside a factory module, `@Tag(Tag.Factory.class)` means **"the tag of the enclosing factory-module
method"**. It works on the provider method and on its parameters. That is how one class produces two
independent, non-colliding sets of components:

```java
public interface UndertowSystemHttpServerModule extends SystemHttpServerModule {

    @FactoryModule
    @SystemApi                                   // @SystemApi is itself annotated @Tag(SystemApi.class)
    default UndertowHttpServerFactoryModule undertowSystemHttpApi() {
        return new UndertowHttpServerFactoryModule("kora-undertow-system", "httpServer.system");
    }
}

public interface UndertowPublicHttpServerModule extends UndertowSystemHttpServerModule {

    @FactoryModule
    default UndertowHttpServerFactoryModule undertowPublicHttpApi() {   // no tag
        return new UndertowHttpServerFactoryModule("kora-undertow", "httpServer");
    }
}
```

Every component the tagged instance provides is tagged `@Tag(SystemApi.class)`; every component the
untagged instance provides is untagged. One class, two servers, no clashes.

Mechanics worth knowing:

- Each provider inside a factory module gains an implicit dependency on the factory-module instance
  itself (with the module's tag), so the instance is constructed before its providers run.
- An annotation that is itself annotated `@Tag(X.class)` acts as the tag `X` — the meta-annotation
  form used by `@SystemApi`.
- `@FactoryModule` must return a class or interface type, otherwise:

  ```
  @FactoryModule method must return a class or interface type.

  Fix:
    - Change the return type to a module class/interface.
    - Remove @FactoryModule if this method is a regular provider.
  ```

- `Tag.Factory` outside a factory module is rejected:

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

You mostly *consume* factory modules (`UndertowPublicHttpServerModule`, `OkHttpClientModule`,
`LettuceModule`, `GrpcServerModule`, `CassandraDatabaseFactoryModule`) rather than write them. Write
one when you genuinely need the same wiring twice under different configuration.

## 6. Extension Factories

When no declaration and no template matches, the processor asks its registered extensions to
generate a component. That is how `@Repository`, `@Json`, `@HttpClient`, `@Valid`, generated gRPC
stubs and MapStruct/Konvert mappers reach the graph with nothing to register by hand. The full table
is in [Component Registration Reference](component-registration-reference.md#6-extension-generated-components).

## Provider Patterns

### Lifecycle hooks around a third-party object

Return `Wrapped<T>` and build a `LifecycleWrapper<>`; consumers still inject the plain `T`:

```java
import io.koraframework.application.graph.LifecycleWrapper;
import io.koraframework.application.graph.Wrapped;

@Module
public interface PoolModule {

    default Wrapped<ConnectionPool> connectionPool(PoolConfig config) {
        return new LifecycleWrapper<>(
                new HikariConnectionPool(config),
                ConnectionPool::initialize,   // init
                ConnectionPool::close);       // release
    }
}
```

See [Graph Roots & Lifecycle Reference](lifecycle-reference.md).

### Config-driven construction

```java
@Module
public interface CacheModule {

    default Cache cache(CacheConfig config) {
        return switch (config.type()) {
            case CAFFEINE -> new CaffeineCache(config);
            case NOOP     -> new NoopCache();
        };
    }
}
```

Prefer typed config (`@ConfigMapper` / `@ConfigSource`) over reading raw `Config` keys inline. For
choosing between whole components rather than branches inside one, use
[`@Conditional`](conditional-components-reference.md).

### Decorating another component

```java
@Module
public interface TracingModule {

    default HttpClient httpClient(@Tag(Raw.class) HttpClient delegate, Tracer tracer) {
        return new TracingHttpClient(delegate, tracer);
    }
}
```

Tag the inner instance so the decorator does not depend on itself — otherwise the processor reports
`Circular dependency found`.

### Optional collaborator

```java
@Module
public interface SmsModule {

    final class SmsTag { private SmsTag() {} }

    @Tag(SmsTag.class)
    default Notifier smsNotifier(@Nullable SmsCellularProvider cellularProvider) {
        return (user, message) -> { /* cellularProvider may be null */ };
    }
}
```

Java uses JSpecify `org.jspecify.annotations.Nullable`; Kotlin uses `SmsCellularProvider?`.

## Factory Selection Guide

| Need | Use |
|---|---|
| Your own service class | `@Component` |
| A third-party type, or non-trivial construction | `@Module` provider |
| A one-off, or overriding a module default | provider on `@KoraApp` |
| One construction rule, many type arguments | generic provider (template) |
| The same module wired twice with different config/tags | `@FactoryModule` + `@Tag(Tag.Factory.class)` |
| Init/cleanup around a type you do not own | `Wrapped<T>` + `LifecycleWrapper` |
| A library default the application may replace | `@DefaultComponent` |
| Pick one of several implementations at graph init | `@Conditional` |
| `@Repository`, `@Json`, `@HttpClient`, … | nothing — the extension generates it |

## Common Mistakes

### Returning `null` from a provider

The DI processor reads `@Nullable` from the **consumer's parameter**, never from the provider's
return type. A provider that returns `null` therefore hands `null` to whoever asked, whether or not
they expect it — and annotating the provider changes nothing.

```java
// BAD — consumers get a null they never opted into
@Module
public interface BadModule {
    default Service service() { return enabled ? new Service() : null; }
}

// GOOD — the absence is expressed where it is read
@Component
public final class Caller {
    public Caller(@Nullable Service service) { … }
}
```

Better still, gate the component with [`@Conditional`](conditional-components-reference.md) so it is
simply absent from the graph when it does not apply.

### Raw types

```java
// BAD — "Component provider returns a raw type:" / "Dependency uses a raw type:"
default Repository repository() { … }

// GOOD
default Repository<User> repository() { … }
```

### Primitive return type

```java
// BAD — "Module method returns a non-reference type, so it cannot be used as a graph component."
default int maxRetries() { return 3; }

// GOOD — wrap it in a type that means something
default RetryPolicy retryPolicy() { return new RetryPolicy(3); }
```

### A cycle between two providers

```java
// BAD — "Circular dependency found:"
default ServiceA serviceA(ServiceB b) { return new ServiceA(b); }
default ServiceB serviceB(ServiceA a) { return new ServiceB(a); }

// GOOD — one side takes an indirect reference
default ServiceA serviceA(ServiceB b) { return new ServiceA(b); }
default ServiceB serviceB(ValueOf<ServiceA> a) { return new ServiceB(a); }
```

The error prints the whole cycle and the `Fix:` list suggests `ValueOf<T>` or `PromiseOf<T>`.
The same error is reported when the cycle runs through an `All<T>` parameter — for example a
`GraphCondition` that injects `All<Foo>` while one `Foo` is `@Conditional` on that very condition.
The processor can substitute a generated proxy for a single component but never for a collection,
so there the only fix is to remove the back-edge. The error's first `Fix:` line suggests
`All<ValueOf<T>>` or `All<PromiseOf<T>>` instead of `All<T>` — that is a cycle through a collection
claim too and fails with the same `Circular dependency found:`.

### `@FactoryModule` on a normal provider

```java
// BAD — StorageConfig is a value, not a module
@FactoryModule
default StorageConfig storageConfig(Config config) { … }

// GOOD — plain provider
default StorageConfig storageConfig(Config config) { … }
```

### `Tag.Factory` outside a factory module

```java
// BAD — "@Tag.Factory can only be used inside factory modules:"
@Module
public interface MyModule {
    @Tag(Tag.Factory.class)
    default Cache cache() { … }
}

// GOOD — name the tag
@Module
public interface MyModule {
    @Tag(L1.class)
    default Cache cache() { … }
}
```

## Related References

- [Component Registration Reference](component-registration-reference.md) — the full resolution order
- [@DefaultComponent Reference](default-component-reference.md) — overridable providers
- [Tags & Collections Reference](tags-collections-reference.md) — `@Tag`, `All<T>`, `ValueOf<T>`
- [Conditional Components Reference](conditional-components-reference.md) — `@Conditional`
- [Graph Roots & Lifecycle Reference](lifecycle-reference.md) — `Wrapped<T>`, `LifecycleWrapper`, `@Root`
