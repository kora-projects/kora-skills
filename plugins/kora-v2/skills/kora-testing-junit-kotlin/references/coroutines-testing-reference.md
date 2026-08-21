# Coroutines Testing Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/junit5.md`

Testing suspend functions and Flows in Kora Kotlin tests with `kotlinx-coroutines-test` (`runTest`, `TestDispatcher`) and MockK's `co*` DSL. The `@KoraAppTest`/`@TestComponent`/`@MockK` wiring is identical to synchronous tests; only the test body and the mocking DSL differ.

## Contents

- [Dependency](#dependency)
- [runTest](#runtest)
- [TestDispatcher](#testdispatcher)
- [Time control](#time-control)
- [Mocking suspend functions with MockK](#mocking-suspend-functions-with-mockk)
- [Flow tests](#flow-tests)
- [Exceptions](#exceptions)
- [Best practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Dependency

```kotlin
testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.1")
```

---

## runTest

`runTest` is the entry point for coroutine tests; it provides a `TestScope` and auto-advances virtual time.

```kotlin
@KoraAppTest(Application::class)
class UserServiceCoroutineTest {

    @MockK @TestComponent lateinit var userRepository: UserRepository
    @TestComponent lateinit var userService: UserService

    @Test
    fun shouldProcessAsync() = runTest {
        coEvery { userRepository.findByIdAsync("1") } returns user
        val result = userService.findByIdAsync("1")
        assertNotNull(result)
        coVerify { userRepository.findByIdAsync("1") }
    }
}
```

---

## TestDispatcher

Inject a `TestDispatcher` into a component to control its scheduling deterministically.

### StandardTestDispatcher

```kotlin
@Test
fun testWithStandardDispatcher() = runTest {
    val dispatcher = StandardTestDispatcher(testScheduler)
    val service = UserService(dispatcher)

    service.enqueueTask("1")
    advanceUntilIdle() // run scheduled work
}
```

### UnconfinedTestDispatcher

```kotlin
@Test
fun testWithUnconfinedDispatcher() = runTest {
    val dispatcher = UnconfinedTestDispatcher(testScheduler)
    val service = UserService(dispatcher)

    service.enqueueTask("1") // runs eagerly; advanceUntilIdle() not required
}
```

---

## Time control

```kotlin
@Test
fun testTimeAdvance() = runTest {
    val service = UserService(StandardTestDispatcher(testScheduler))

    service.scheduleDelayed("1", delayMillis = 1000)

    advanceTimeBy(500)
    assertEquals(500, currentTime) // task not run yet

    advanceUntilIdle()             // runs all pending work
}
```

- `advanceUntilIdle()` — run all pending tasks.
- `advanceTimeBy(ms)` — advance virtual time by `ms`.
- `currentTime` — current virtual time of the scheduler.

---

## Mocking suspend functions with MockK

### coEvery / coVerify

```kotlin
@MockK
@TestComponent
lateinit var userRepository: UserRepository

@Test
fun shouldFindUserAsync() = runTest {
    coEvery { userRepository.findByIdAsync("1") } returns user

    val result = userService.findByIdAsync("1")

    assertNotNull(result)
    coVerify { userRepository.findByIdAsync("1") }
    coVerify(exactly = 1) { userRepository.findByIdAsync(any()) }
}
```

### coAnswers

```kotlin
coEvery { repository.processAsync(any()) } coAnswers {
    delay(100)
    firstArg<String>() + "-done"
}
```

### coVerifyOrder

```kotlin
@Test
fun shouldVerifySuspendOrder() = runTest {
    service.fullProcess()
    coVerifyOrder {
        repository.save(any())
        repository.update(any())
    }
}
```

---

## Flow tests

```kotlin
@Test
fun testFlowEmission() = runTest {
    val result = flowOf(1, 2, 3).toList()
    assertEquals(listOf(1, 2, 3), result)
}

@Test
fun testFlowWithTimeout() = runTest {
    withTimeout(1000) {
        service.eventFlow().collect { event -> process(event) }
    }
}
```

---

## Exceptions

```kotlin
@Test
fun shouldThrowFromSuspend() = runTest {
    coEvery { repository.findByIdAsync("1") } throws RuntimeException("Not found")

    val ex = assertFailsWith<RuntimeException> { service.findByIdAsync("1") }
    assertEquals("Not found", ex.message)
}
```

---

## Best practices

1. `runTest { }` for every suspend test — virtual time is auto-managed.
2. `advanceUntilIdle()` after launching background work before asserting.
3. `coEvery`/`coVerify` for suspend functions; `every`/`verify` only for blocking calls.
4. Inject a `TestDispatcher` for deterministic scheduling instead of real time.
5. `withTimeout` to guard long-running collection from hanging the suite.

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Test hangs | No `runTest` | Wrap the body in `runTest { }` |
| Scheduled work not run | Missing advance | Call `advanceUntilIdle()` after launching |
| Non-deterministic timing | Real dispatcher | Inject a `TestDispatcher` |
| `verify` fails on suspend | Wrong DSL | Use `coVerify`/`coEvery` |
