# Assertion Patterns Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/guides/testing-junit.md`,
`.kora-agent/kora-docs/mkdocs/docs/en/documentation/junit5.md`

Assertion and verification patterns for Kora JUnit 5 tests. These are standard
JUnit/AssertJ/Mockito/Reactor libraries; Kora adds no assertion API of its own.

## Contents

- [JUnit 5 assertions](#junit-5-assertions)
- [AssertJ](#assertj)
- [Mockito verify](#mockito-verify)
- [StepVerifier (reactive)](#stepverifier-reactive)
- [JSON assertions](#json-assertions)
- [Database assertions](#database-assertions)
- [Best practices](#best-practices)

---

## JUnit 5 assertions

```java
import static org.junit.jupiter.api.Assertions.*;

@Test
void shouldCreateUser() {
    var result = userService.createUser(new UserRequest("John", "john@example.com"));

    assertNotNull(result);
    assertEquals("John", result.name());
    assertEquals("john@example.com", result.email());
}
```

Group independent checks so all failures report at once:
```java
assertAll("user response",
    () -> assertNotNull(result),
    () -> assertEquals("John", result.name()),
    () -> assertNotNull(result.id()));
```

Exception assertion:
```java
var exception = assertThrows(HttpServerResponseException.class,
    () -> userService.deleteUser("missing"));
assertEquals(404, exception.code());
```

---

## AssertJ

```groovy
testImplementation "org.assertj:assertj-core:3.24.2"
```

```java
import static org.assertj.core.api.Assertions.*;

assertThat(result)
    .isNotNull()
    .extracting("email")
    .isEqualTo("john@example.com");

assertThat(users)
    .hasSize(3)
    .extracting("email")
    .containsExactlyInAnyOrder("a@test.com", "b@test.com", "c@test.com");

assertThatThrownBy(() -> userService.createUser(new UserRequest("", "")))
    .isInstanceOf(IllegalArgumentException.class)
    .hasMessageContaining("name");
```

---

## Mockito verify

```java
import static org.mockito.Mockito.*;

verify(userRepository).save("John", "john@example.com");
verify(userRepository, times(3)).findById(any());
verify(userRepository, never()).deleteById(any());

var inOrder = inOrder(userRepository);
inOrder.verify(userRepository).save(any());
inOrder.verify(userRepository).update(any(), any(), any());
```

`ArgumentCaptor`:
```java
var captor = ArgumentCaptor.forClass(User.class);
verify(userRepository).save(captor.capture());
assertThat(captor.getValue().email()).isEqualTo("john@example.com");
```

---

## StepVerifier (reactive)

For components that return Project Reactor `Mono`/`Flux`:

```groovy
testImplementation "io.projectreactor:reactor-test:3.6.0"
```

```java
import reactor.test.StepVerifier;

StepVerifier.create(userService.getUserAsync("1"))
    .expectNextMatches(u -> u.email().equals("john@example.com"))
    .verifyComplete();

StepVerifier.create(userService.getAllAsync())
    .expectNextCount(3)
    .verifyComplete();

StepVerifier.create(userService.getUserAsync("missing"))
    .expectError(IllegalStateException.class)
    .verify();
```

---

## JSON assertions

Compare serialized output via Jackson:

```java
import com.fasterxml.jackson.databind.ObjectMapper;

var tree = new ObjectMapper().readTree(json);
assertThat(tree.get("id").asText()).isEqualTo("1");
assertThat(tree.get("email").asText()).isEqualTo("john@example.com");
assertThat(tree.get("roles").isArray()).isTrue();
```

---

## Database assertions

In integration tests, assert persistence through a test-only repository declared in the
`TestApplication` graph (see the Testcontainers JDBC reference) rather than a raw SQL
helper. The repository goes through the same Kora JDBC stack the application uses.

```java
@TestComponent
private TestApplication.TestUserRepository testUserRepository;

@Test
void shouldPersistUser() {
    userService.createUser(new UserRequest("John", "john@example.com"));

    var rows = testUserRepository.findAll();
    assertThat(rows).hasSize(1);
    assertThat(rows.get(0).email()).isEqualTo("john@example.com");
}
```

---

## Best practices

1. Use `assertAll` to group independent checks for better diagnostics.
2. Reach for AssertJ when assertions get expressive (collections, nested fields).
3. Use `StepVerifier` for any reactive return type.
4. Use `ArgumentCaptor` when matchers cannot express the assertion.
5. Assert real persistence through a `TestApplication` test repository in integration tests.
6. Avoid hardcoded IDs; capture generated values from the result.
