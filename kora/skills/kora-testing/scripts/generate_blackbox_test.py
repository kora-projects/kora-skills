#!/usr/bin/env python3
"""
Kora Black-Box Test Generator

Generates black-box test templates with Testcontainers and HTTP client.

Usage:
    python generate_blackbox_test.py --name BlackBoxTests --port 8080 --lang java
    python generate_blackbox_test.py --name BlackBoxTests --port 8080 --lang kotlin
"""

import argparse
import os
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description='Generate Kora black-box test')
    parser.add_argument('--name', required=True, help='Test class name (e.g., BlackBoxTests)')
    parser.add_argument('--port', type=int, default=8080, help='Application port')
    parser.add_argument('--package', default='ru.tinkoff.kora.example', help='Package name')
    parser.add_argument('--lang', choices=['java', 'kotlin'], default='java', help='Language')
    parser.add_argument('--output', default='.', help='Output directory')
    return parser.parse_args()


def generate_java(name, port, package):
    return f'''package {package};

import static org.junit.jupiter.api.Assertions.*;

import io.goodforgod.testcontainers.extensions.ContainerMode;
import io.goodforgod.testcontainers.extensions.Network;
import io.goodforgod.testcontainers.extensions.jdbc.*;
import java.net.http.*;
import java.time.Duration;
import java.util.Map;
import org.json.JSONObject;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.skyscreamer.jsonassert.JSONAssert;
import org.skyscreamer.jsonassert.JSONCompareMode;

@TestcontainersPostgreSQL(
    network = @Network(shared = true),
    mode = ContainerMode.PER_RUN,
    migration = @Migration(
        engine = Migration.Engines.FLYWAY,
        apply = Migration.Mode.PER_METHOD,
        drop = Migration.Mode.PER_METHOD
    )
)
class {name} {{

    private static final AppContainer container = AppContainer.build()
        .withNetwork(org.testcontainers.containers.Network.SHARED);

    @ConnectionPostgreSQL
    private JdbcConnection connection;

    @BeforeAll
    static void setup(@ConnectionPostgreSQL JdbcConnection connection) {{
        var params = connection.paramsInNetwork().orElseThrow();
        container.withEnv(Map.of(
            "DB_JDBC_URL", params.jdbcUrl(),
            "DB_USER", params.username(),
            "DB_PASS", params.password()
        ));
        container.start();
    }}

    @AfterAll
    static void cleanup() {{
        container.stop();
    }}

    @Test
    void shouldCreateResource() throws Exception {{
        // given
        var httpClient = HttpClient.newHttpClient();
        var requestBody = new JSONObject()
            .put("name", "test-resource");

        // when
        var request = HttpRequest.newBuilder()
            .POST(HttpRequest.BodyPublishers.ofString(requestBody.toString()))
            .uri(container.getURI().resolve("/api/resources"))
            .timeout(Duration.ofSeconds(5))
            .build();

        var response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        assertEquals(200, response.statusCode());

        // then
        var responseBody = new JSONObject(response.body());
        assertNotNull(responseBody.query("/id"));
        assertEquals("test-resource", responseBody.query("/name"));
    }}

    @Test
    void shouldGetResource() throws Exception {{
        // given
        var httpClient = HttpClient.newHttpClient();

        // Create resource first
        var createRequest = HttpRequest.newBuilder()
            .POST(HttpRequest.BodyPublishers.ofString("{{\\"name\\":\\"test\\"}}"))
            .uri(container.getURI().resolve("/api/resources"))
            .timeout(Duration.ofSeconds(5))
            .build();
        var createResponse = httpClient.send(createRequest, HttpResponse.BodyHandlers.ofString());
        var resourceId = new JSONObject(createResponse.body()).query("/id");

        // when
        var getRequest = HttpRequest.newBuilder()
            .GET()
            .uri(container.getURI().resolve("/api/resources/" + resourceId))
            .timeout(Duration.ofSeconds(5))
            .build();

        var getResponse = httpClient.send(getRequest, HttpResponse.BodyHandlers.ofString());
        assertEquals(200, getResponse.statusCode());
    }}

    @Test
    void shouldDeleteResource() throws Exception {{
        // given
        var httpClient = HttpClient.newHttpClient();

        // Create resource first
        var createRequest = HttpRequest.newBuilder()
            .POST(HttpRequest.BodyPublishers.ofString("{{\\"name\\":\\"test\\"}}"))
            .uri(container.getURI().resolve("/api/resources"))
            .timeout(Duration.ofSeconds(5))
            .build();
        var createResponse = httpClient.send(createRequest, HttpResponse.BodyHandlers.ofString());
        var resourceId = new JSONObject(createResponse.body()).query("/id");

        // when
        var deleteRequest = HttpRequest.newBuilder()
            .DELETE()
            .uri(container.getURI().resolve("/api/resources/" + resourceId))
            .timeout(Duration.ofSeconds(5))
            .build();

        var deleteResponse = httpClient.send(deleteRequest, HttpResponse.BodyHandlers.ofString());
        assertEquals(200, deleteResponse.statusCode());

        // then
        connection.assertCountsEquals(0, "resources");
    }}
}}
'''


def generate_kotlin(name, port, package):
    return f'''package {package}

import io.goodforgod.testcontainers.extensions.ContainerMode
import io.goodforgod.testcontainers.extensions.Network
import io.goodforgod.testcontainers.extensions.jdbc.*
import org.junit.jupiter.api.AfterAll
import org.junit.jupiter.api.BeforeAll
import org.junit.jupiter.api.Test
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.time.Duration
import org.json.JSONObject

@TestcontainersPostgreSQL(
    network = @Network(shared = true),
    mode = ContainerMode.PER_RUN,
    migration = @Migration(
        engine = Migration.Engines.FLYWAY,
        apply = Migration.Mode.PER_METHOD,
        drop = Migration.Mode.PER_METHOD
    )
)
class {name} {{

    companion object {{
        private val container = AppContainer.build()
            .withNetwork(org.testcontainers.containers.Network.SHARED)

        @JvmStatic
        @BeforeAll
        fun setup(@ConnectionPostgreSQL connection: JdbcConnection) {{
            val params = connection.paramsInNetwork().orElseThrow()
            container.withEnv(mapOf(
                "DB_JDBC_URL" to params.jdbcUrl(),
                "DB_USER" to params.username(),
                "DB_PASS" to params.password()
            ))
            container.start()
        }}

        @JvmStatic
        @AfterAll
        fun cleanup() {{
            container.stop()
        }}
    }}

    @ConnectionPostgreSQL
    private lateinit var connection: JdbcConnection

    @Test
    fun `should create resource`() {{
        val httpClient = HttpClient.newHttpClient()
        val requestBody = JSONObject().put("name", "test-resource")

        val request = HttpRequest.newBuilder()
            .POST(HttpRequest.BodyPublishers.ofString(requestBody.toString()))
            .uri(container.uri.resolve("/api/resources"))
            .timeout(Duration.ofSeconds(5))
            .build()

        val response = httpClient.send(request, HttpResponse.BodyHandlers.ofString())
        org.junit.jupiter.api.Assertions.assertEquals(200, response.statusCode())

        val responseBody = JSONObject(response.body())
        org.junit.jupiter.api.Assertions.assertNotNull(responseBody.get("id"))
        org.junit.jupiter.api.Assertions.assertEquals("test-resource", responseBody.get("name"))
    }}

    @Test
    fun `should get resource`() {{
        val httpClient = HttpClient.newHttpClient()

        // Create resource first
        val createRequest = HttpRequest.newBuilder()
            .POST(HttpRequest.BodyPublishers.ofString("{{\\"name\\":\\"test\\"}}"))
            .uri(container.uri.resolve("/api/resources"))
            .timeout(Duration.ofSeconds(5))
            .build()
        val createResponse = httpClient.send(createRequest, HttpResponse.BodyHandlers.ofString())
        val resourceId = JSONObject(createResponse.body()).get("id")

        // when
        val getRequest = HttpRequest.newBuilder()
            .GET()
            .uri(container.uri.resolve("/api/resources/$resourceId"))
            .timeout(Duration.ofSeconds(5))
            .build()

        val getResponse = httpClient.send(getRequest, HttpResponse.BodyHandlers.ofString())
        org.junit.jupiter.api.Assertions.assertEquals(200, getResponse.statusCode())
    }}
}}
'''


def main():
    args = parse_args()
    
    if args.lang == 'java':
        content = generate_java(args.name, args.port, args.package)
        filename = f"{args.name}.java"
    else:
        content = generate_kotlin(args.name, args.port, args.package)
        filename = f"{args.name}.kt"
    
    output_path = Path(args.output) / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
    
    print(f"Generated: {output_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
