"""
Tests for configuration file parsing functionality.

This module tests JSON, YAML, and TOML configuration file support,
including extraction of top-level sections/keys as semantic units.
"""

import pytest
from mcp_performance_core import parse_source_file

# Sample JSON configuration
SAMPLE_JSON = """
{
  "name": "my-app",
  "version": "1.0.0",
  "scripts": {
    "start": "node server.js",
    "test": "jest",
    "build": "webpack"
  },
  "dependencies": {
    "express": "^4.18.0",
    "lodash": "^4.17.21"
  },
  "devDependencies": {
    "jest": "^29.0.0",
    "webpack": "^5.75.0"
  }
}
"""

# Sample YAML configuration (docker-compose)
SAMPLE_YAML = """
version: '3.8'

services:
  web:
    image: nginx:latest
    ports:
      - "80:80"
    volumes:
      - ./html:/usr/share/nginx/html

  database:
    image: postgres:14
    environment:
      POSTGRES_PASSWORD: secret

volumes:
  db_data:
"""

# Sample TOML configuration
SAMPLE_TOML = """
[package]
name = "my-crate"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = { version = "1.0", features = ["derive"] }
tokio = { version = "1.28", features = ["full"] }

[dev-dependencies]
criterion = "0.5"

[profile.release]
opt-level = 3
lto = true
"""

# Sample GitHub Actions YAML
GITHUB_ACTIONS_YAML = """
name: CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: npm test

  build:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v3
      - name: Build
        run: npm run build
"""


class TestJSONParsing:
    """Test suite for JSON configuration parsing."""

    def test_parse_json_file(self):
        """Test parsing a JSON configuration file."""
        result = parse_source_file("package.json", SAMPLE_JSON)

        assert result.language == "Json"
        assert result.file_path == "package.json"
        assert len(result.units) > 0
        assert result.parse_time_ms > 0

    def test_json_top_level_keys(self):
        """Test extraction of top-level keys from JSON."""
        result = parse_source_file("config.json", SAMPLE_JSON)

        # Extract top-level key names
        key_names = {unit.name for unit in result.units}

        # Should have these top-level keys
        assert "scripts" in key_names
        assert "dependencies" in key_names
        assert "devDependencies" in key_names

    def test_json_semantic_units(self):
        """Test that JSON keys are extracted as 'class' units."""
        result = parse_source_file("config.json", SAMPLE_JSON)

        # All units should be 'class' type (top-level sections)
        for unit in result.units:
            assert unit.unit_type == "class"
            assert unit.language == "Json"
            assert len(unit.name) > 0
            assert len(unit.content) > 0

    def test_json_empty_file(self):
        """Test parsing an empty JSON object."""
        result = parse_source_file("empty.json", "{}")

        assert result.language == "Json"
        assert len(result.units) == 0

    def test_json_malformed(self):
        """Test that malformed JSON raises an error."""
        with pytest.raises(Exception):
            parse_source_file("bad.json", "{ invalid json }")


class TestYAMLParsing:
    """Test suite for YAML configuration parsing."""

    def test_parse_yaml_file(self):
        """Test parsing a YAML configuration file."""
        result = parse_source_file("docker-compose.yml", SAMPLE_YAML)

        assert result.language == "Yaml"
        assert result.file_path == "docker-compose.yml"
        assert len(result.units) > 0
        assert result.parse_time_ms > 0

    def test_yaml_top_level_keys(self):
        """Test extraction of top-level keys from YAML."""
        result = parse_source_file("docker-compose.yml", SAMPLE_YAML)

        key_names = {unit.name for unit in result.units}

        # Should have these top-level keys
        assert "services" in key_names
        assert "volumes" in key_names
        assert "version" in key_names

    def test_yaml_semantic_units(self):
        """Test that YAML keys are extracted as 'class' units."""
        result = parse_source_file("config.yaml", SAMPLE_YAML)

        for unit in result.units:
            assert unit.unit_type == "class"
            assert unit.language == "Yaml"
            assert len(unit.name) > 0
            assert len(unit.content) > 0

    def test_yaml_yml_extension(self):
        """Test that .yml extension works."""
        result = parse_source_file("config.yml", SAMPLE_YAML)

        assert result.language == "Yaml"
        assert len(result.units) > 0

    def test_github_actions_yaml(self):
        """Test parsing GitHub Actions workflow YAML."""
        result = parse_source_file(".github/workflows/ci.yml", GITHUB_ACTIONS_YAML)

        assert result.language == "Yaml"

        key_names = {unit.name for unit in result.units}
        assert "jobs" in key_names or "on" in key_names

    def test_yaml_empty_file(self):
        """Test parsing an empty YAML file."""
        result = parse_source_file("empty.yaml", "")

        assert result.language == "Yaml"
        # Empty YAML may result in 0 units
        assert len(result.units) >= 0


class TestTOMLParsing:
    """Test suite for TOML configuration parsing."""

    def test_parse_toml_file(self):
        """Test parsing a TOML configuration file."""
        result = parse_source_file("Cargo.toml", SAMPLE_TOML)

        assert result.language == "Toml"
        assert result.file_path == "Cargo.toml"
        assert len(result.units) > 0
        assert result.parse_time_ms > 0

    def test_toml_top_level_sections(self):
        """Test extraction of top-level sections from TOML."""
        result = parse_source_file("Cargo.toml", SAMPLE_TOML)

        section_names = {unit.name for unit in result.units}

        # Should have these top-level sections
        assert "package" in section_names
        assert "dependencies" in section_names
        assert "dev-dependencies" in section_names or "profile" in section_names

    def test_toml_semantic_units(self):
        """Test that TOML sections are extracted as 'class' units."""
        result = parse_source_file("config.toml", SAMPLE_TOML)

        for unit in result.units:
            assert unit.unit_type == "class"
            assert unit.language == "Toml"
            assert len(unit.name) > 0
            assert len(unit.content) > 0

    def test_toml_empty_file(self):
        """Test parsing an empty TOML file."""
        result = parse_source_file("empty.toml", "")

        assert result.language == "Toml"
        assert len(result.units) == 0

    def test_toml_malformed(self):
        """Test that malformed TOML raises an error."""
        with pytest.raises(Exception):
            parse_source_file("bad.toml", "[invalid toml")


class TestConfigPerformance:
    """Test suite for configuration parsing performance."""

    def test_json_parse_performance(self):
        """Test that JSON parsing completes in reasonable time."""
        result = parse_source_file("config.json", SAMPLE_JSON)

        # Should parse quickly
        assert result.parse_time_ms < 50

    def test_yaml_parse_performance(self):
        """Test that YAML parsing completes in reasonable time."""
        result = parse_source_file("config.yaml", SAMPLE_YAML)

        assert result.parse_time_ms < 50

    def test_toml_parse_performance(self):
        """Test that TOML parsing completes in reasonable time."""
        result = parse_source_file("config.toml", SAMPLE_TOML)

        assert result.parse_time_ms < 50


class TestConfigEdgeCases:
    """Test suite for configuration parsing edge cases."""

    def test_json_nested_objects(self):
        """Test JSON with deeply nested objects."""
        nested_json = """
        {
          "level1": {
            "level2": {
              "level3": {
                "value": "deep"
              }
            }
          }
        }
        """
        result = parse_source_file("nested.json", nested_json)

        assert result.language == "Json"
        assert len(result.units) >= 1

    def test_yaml_with_anchors(self):
        """Test YAML with anchors and aliases."""
        yaml_with_anchors = """
        defaults: &defaults
          timeout: 30
          retries: 3

        production:
          <<: *defaults
          server: prod.example.com
        """
        result = parse_source_file("config.yaml", yaml_with_anchors)

        assert result.language == "Yaml"
        assert len(result.units) >= 2

    def test_toml_with_arrays(self):
        """Test TOML with array tables."""
        toml_with_arrays = """
        [[bin]]
        name = "app1"
        path = "src/main1.rs"

        [[bin]]
        name = "app2"
        path = "src/main2.rs"
        """
        result = parse_source_file("config.toml", toml_with_arrays)

        assert result.language == "Toml"
        # bin array items should be captured
        assert len(result.units) >= 1

    def test_config_repr_methods(self):
        """Test string representation methods for config results."""
        result = parse_source_file("config.json", SAMPLE_JSON)

        # Test ParseResult repr
        result_repr = repr(result)
        assert "ParseResult" in result_repr
        assert "Json" in result_repr

        # Test SemanticUnit repr
        if result.units:
            unit_repr = repr(result.units[0])
            assert "SemanticUnit" in unit_repr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
