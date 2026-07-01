#!/usr/bin/env python3
"""
Generate JDBC repository files from templates for Kora Framework.

Usage:
    python generate_repository.py --entity User --table users --id-type Long --lang java
    python generate_repository.py --entity OrderItem --table order_items --id-type composite --lang java

Options:
    --entity      Name of the entity class (e.g., User, OrderItem)
    --table       Name of the database table (e.g., users, order_items)
    --id-type     Type of ID: Long, UUID, String, or composite
    --lang        Language: java or kotlin (default: java)
    --package     Package name (default: com.example.repository)
    --output-dir  Output directory (default: current directory)
"""

import argparse
import os
import shutil
from pathlib import Path


def get_template_path(template_name: str, lang: str) -> str:
    """Get the path to a template file (assets/ is a sibling of scripts/)."""
    assets_dir = Path(__file__).parent.parent / "assets"
    suffix = ".kt.template" if lang == "kotlin" else ".java.template"
    return assets_dir / f"{template_name}{suffix}"


def read_template(template_path: Path) -> str:
    """Read template content."""
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    return template_path.read_text()


def replace_placeholders(content: str, replacements: dict) -> str:
    """Replace placeholders in template."""
    for key, value in replacements.items():
        content = content.replace(f"${{{key}}}", value)
    return content


def generate_entity(entity_name: str, table_name: str, id_type: str, lang: str, package: str) -> str:
    """Generate entity file content."""
    if id_type == "composite":
        template_name = "jdbc-entity-composite-id"
        replacements = {
            "package": package,
            "entity_name": entity_name,
            "table_name": table_name,
            "id1_type": "Long",
            "id1_field": "orderId",
            "id1_column": "order_id",
            "id2_type": "Long",
            "id2_field": "productId",
            "id2_column": "product_id",
            "id1_default": "null",
            "id2_default": "null",
        }
    else:
        template_name = "jdbc-entity-single-id"
        replacements = {
            "package": package,
            "entity_name": entity_name,
            "table_name": table_name,
            "id_type": id_type,
        }

    template_path = get_template_path(template_name, lang)
    content = read_template(template_path)
    return replace_placeholders(content, replacements)


def generate_repository(entity_name: str, table_name: str, id_type: str, lang: str, package: str) -> str:
    """Generate repository file content."""
    if id_type == "composite":
        template_name = "jdbc-crud-composite-id-repository"
        replacements = {
            "package": package,
            "entity_name": entity_name,
            "repository_name": f"{entity_name}Repository",
            "table_name": table_name,
            "id1_column": "order_id",
            "id2_column": "product_id",
        }
    else:
        template_name = "jdbc-crud-single-id-repository"
        replacements = {
            "package": package,
            "entity_name": entity_name,
            "repository_name": f"{entity_name}Repository",
            "id_type": id_type,
        }

    template_path = get_template_path(template_name, lang)
    content = read_template(template_path)
    return replace_placeholders(content, replacements)


def write_file(content: str, output_dir: Path, filename: str) -> Path:
    """Write content to file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / filename
    file_path.write_text(content)
    return file_path


def main():
    parser = argparse.ArgumentParser(description="Generate JDBC repository files for Kora Framework")
    parser.add_argument("--entity", required=True, help="Entity class name (e.g., User, OrderItem)")
    parser.add_argument("--table", required=True, help="Database table name (e.g., users, order_items)")
    parser.add_argument("--id-type", required=True, choices=["Long", "UUID", "String", "composite"],
                        help="ID type: Long, UUID, String, or composite")
    parser.add_argument("--lang", default="java", choices=["java", "kotlin"],
                        help="Language: java or kotlin (default: java)")
    parser.add_argument("--package", default="com.example.repository",
                        help="Package name (default: com.example.repository)")
    parser.add_argument("--output-dir", default=".",
                        help="Output directory (default: current directory)")
    parser.add_argument("--entity-only", action="store_true",
                        help="Generate only entity file")
    parser.add_argument("--repository-only", action="store_true",
                        help="Generate only repository file")

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    ext = "kt" if args.lang == "kotlin" else "java"

    if not args.entity_only:
        # Generate repository
        repository_content = generate_repository(
            args.entity, args.table, args.id_type, args.lang, args.package
        )
        repo_filename = f"{args.entity}Repository.{ext}"
        repo_path = write_file(repository_content, output_dir, repo_filename)
        print(f"Generated: {repo_path}")

    if not args.repository_only:
        # Generate entity
        entity_content = generate_entity(
            args.entity, args.table, args.id_type, args.lang, args.package
        )
        entity_filename = f"{args.entity}.{ext}"
        entity_path = write_file(entity_content, output_dir, entity_filename)
        print(f"Generated: {entity_path}")

    print("\nNext steps:")
    print(f"1. Move generated files to your project's src/main/java/{args.package.replace('.', '/')}/")
    print("2. Customize entity fields and repository methods")
    print("3. Create database migration for the table")
    print("4. Add repository to your service class")


if __name__ == "__main__":
    main()
