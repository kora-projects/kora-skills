#!/usr/bin/env python3
"""
Kora Kafka Configuration Validator

Validates Kafka consumer and producer configuration files.

Usage:
    python validate_config.py --config application.conf
"""

import argparse
import re
import sys
from pathlib import Path


class ConfigValidator:
    """Validates Kora Kafka configuration."""
    
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.config_content = ""
    
    def load_config(self) -> bool:
        """Load configuration file."""
        if not self.config_path.exists():
            self.errors.append(f"Configuration file not found: {self.config_path}")
            return False
        
        try:
            self.config_content = self.config_path.read_text()
            return True
        except Exception as e:
            self.errors.append(f"Failed to read config file: {e}")
            return False
    
    def validate_consumer_config(self) -> None:
        """Validate consumer configuration."""
        # Check for consumer section
        consumer_match = re.search(r'kafka\s*\{\s*consumer\s*\{', self.config_content)
        if not consumer_match:
            self.warnings.append("No consumer configuration found")
            return
        
        # Check for required fields in each consumer
        consumers = re.findall(r'consumer\s*\{\s*(\w+)\s*\{', self.config_content)
        for consumer in consumers:
            consumer_block = self._extract_block(consumer)
            
            # Check topics or topicsPattern
            if 'topics' not in consumer_block and 'topicsPattern' not in consumer_block:
                self.errors.append(f"Consumer '{consumer}': missing topics or topicsPattern")
            
            # Check driverProperties
            if 'driverProperties' not in consumer_block:
                self.errors.append(f"Consumer '{consumer}': missing driverProperties")
            elif 'bootstrap.servers' not in consumer_block:
                self.errors.append(f"Consumer '{consumer}': missing bootstrap.servers in driverProperties")
    
    def validate_producer_config(self) -> None:
        """Validate producer configuration."""
        # Check for producer section
        producer_match = re.search(r'kafka\s*\{\s*producer\s*\{', self.config_content)
        if not producer_match:
            self.warnings.append("No producer configuration found")
            return
        
        # Check for required fields in each producer
        producers = re.findall(r'producer\s*\{\s*(\w+)\s*\{', self.config_content)
        for producer in producers:
            producer_block = self._extract_block(producer)
            
            # Check driverProperties
            if 'driverProperties' not in producer_block:
                self.errors.append(f"Producer '{producer}': missing driverProperties")
            elif 'bootstrap.servers' not in producer_block:
                self.errors.append(f"Producer '{producer}': missing bootstrap.servers in driverProperties")
    
    def validate_telemetry_config(self) -> None:
        """Validate telemetry configuration."""
        # Check for telemetry sections
        telemetry_sections = re.findall(r'telemetry\s*\{[^}]*\}', self.config_content, re.DOTALL)
        
        for section in telemetry_sections:
            if 'logging' not in section:
                self.warnings.append("Telemetry logging not configured")
            if 'metrics' not in section:
                self.warnings.append("Telemetry metrics not configured")
            if 'tracing' not in section:
                self.warnings.append("Telemetry tracing not configured")
    
    def _extract_block(self, name: str) -> str:
        """Extract configuration block by name."""
        pattern = rf'{name}\s*\{{([^}}]*(?:\{{[^}}]*\}}[^}}]*)*)\}}'
        match = re.search(pattern, self.config_content, re.DOTALL)
        return match.group(1) if match else ""
    
    def validate(self) -> bool:
        """Run all validations."""
        if not self.load_config():
            return False
        
        print(f"Validating: {self.config_path}")
        print("-" * 50)
        
        self.validate_consumer_config()
        self.validate_producer_config()
        self.validate_telemetry_config()
        
        # Print results
        if self.errors:
            print("\nERRORS:")
            for error in self.errors:
                print(f"  • {error}")
        
        if self.warnings:
            print("\n WARNINGS:")
            for warning in self.warnings:
                print(f"  • {warning}")
        
        if not self.errors and not self.warnings:
            print("\nConfiguration is valid!")
        
        print("-" * 50)
        
        return len(self.errors) == 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate Kora Kafka configuration"
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to configuration file (application.conf)"
    )
    
    args = parser.parse_args()
    
    validator = ConfigValidator(args.config)
    success = validator.validate()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
