use serde_json::Value as JsonValue;
use serde_yaml::Value as YamlValue;
use toml::Value as TomlValue;

use crate::parsing::{SemanticUnit, ParseResult};

/// Parse JSON configuration files and extract top-level keys as semantic units
pub fn parse_json(_file_path: &str, source_code: &str) -> Result<Vec<SemanticUnit>, String> {
    let parsed: JsonValue = serde_json::from_str(source_code)
        .map_err(|e| format!("JSON parse error: {}", e))?;

    let mut units = Vec::new();

    if let JsonValue::Object(map) = parsed {
        for (key, value) in map.iter() {
            // Calculate approximate line numbers by searching in source
            let (start_line, end_line) = find_key_lines(source_code, key);

            // Create a semantic unit for this top-level key
            let content = format_json_section(key, value);

            units.push(SemanticUnit {
                unit_type: "class".to_string(), // Top-level sections as "class" units
                name: key.clone(),
                start_line,
                end_line,
                start_byte: 0, // Not accurately calculable from parsed JSON
                end_byte: content.len(),
                signature: key.clone(),
                content,
                language: "Json".to_string(),
            });
        }
    }

    Ok(units)
}

/// Parse YAML configuration files and extract top-level keys as semantic units
pub fn parse_yaml(_file_path: &str, source_code: &str) -> Result<Vec<SemanticUnit>, String> {
    let parsed: YamlValue = serde_yaml::from_str(source_code)
        .map_err(|e| format!("YAML parse error: {}", e))?;

    let mut units = Vec::new();

    if let YamlValue::Mapping(map) = parsed {
        for (key, value) in map.iter() {
            if let YamlValue::String(key_str) = key {
                let (start_line, end_line) = find_key_lines(source_code, key_str);

                let content = format_yaml_section(key_str, value);

                units.push(SemanticUnit {
                    unit_type: "class".to_string(),
                    name: key_str.clone(),
                    start_line,
                    end_line,
                    start_byte: 0,
                    end_byte: content.len(),
                    signature: key_str.clone(),
                    content,
                    language: "Yaml".to_string(),
                });
            }
        }
    }

    Ok(units)
}

/// Parse TOML configuration files and extract top-level sections as semantic units
pub fn parse_toml(_file_path: &str, source_code: &str) -> Result<Vec<SemanticUnit>, String> {
    let parsed: TomlValue = source_code.parse()
        .map_err(|e: toml::de::Error| format!("TOML parse error: {}", e))?;

    let mut units = Vec::new();

    if let TomlValue::Table(table) = parsed {
        for (key, value) in table.iter() {
            let (start_line, end_line) = find_key_lines(source_code, key);

            let content = format_toml_section(key, value);

            units.push(SemanticUnit {
                unit_type: "class".to_string(),
                name: key.clone(),
                start_line,
                end_line,
                start_byte: 0,
                end_byte: content.len(),
                signature: key.clone(),
                content,
                language: "Toml".to_string(),
            });
        }
    }

    Ok(units)
}

/// Find approximate line numbers for a key in the source code
fn find_key_lines(source: &str, key: &str) -> (usize, usize) {
    let lines: Vec<&str> = source.lines().collect();

    // Search for the key
    for (idx, line) in lines.iter().enumerate() {
        if line.contains(key) {
            let start = idx + 1; // 1-indexed

            // Estimate end line by looking for next top-level key or end of file
            let mut end = start;
            for i in (idx + 1)..lines.len() {
                // Simple heuristic: next non-indented line or end of file
                if !lines[i].starts_with(' ') && !lines[i].starts_with('\t') && !lines[i].trim().is_empty() {
                    end = i; // Line before next key
                    break;
                }
                end = i + 1;
            }

            return (start, end);
        }
    }

    (1, lines.len()) // Fallback: entire file
}

/// Format a JSON section for content display
fn format_json_section(key: &str, value: &JsonValue) -> String {
    match serde_json::to_string_pretty(value) {
        Ok(pretty) => format!("\"{}\": {}", key, pretty),
        Err(_) => format!("\"{}\": [complex object]", key),
    }
}

/// Format a YAML section for content display
fn format_yaml_section(key: &str, value: &YamlValue) -> String {
    match serde_yaml::to_string(value) {
        Ok(yaml_str) => {
            // Indent the value part
            let indented = yaml_str
                .lines()
                .map(|line| if line.is_empty() { line.to_string() } else { format!("  {}", line) })
                .collect::<Vec<_>>()
                .join("\n");
            format!("{}:\n{}", key, indented)
        }
        Err(_) => format!("{}: [complex object]", key),
    }
}

/// Format a TOML section for content display
fn format_toml_section(key: &str, value: &TomlValue) -> String {
    match toml::to_string(value) {
        Ok(toml_str) => {
            if value.is_table() {
                format!("[{}]\n{}", key, toml_str)
            } else {
                format!("{} = {}", key, toml_str.trim())
            }
        }
        Err(_) => format!("[{}]\n[complex section]", key),
    }
}

/// Parse a configuration file based on its extension
pub fn parse_config_file(file_path: &str, source_code: &str) -> Result<ParseResult, String> {
    let start = std::time::Instant::now();

    // Detect format from file extension
    let extension = std::path::Path::new(file_path)
        .extension()
        .and_then(|e| e.to_str())
        .ok_or("No file extension")?;

    let (units, language) = match extension {
        "json" => (parse_json(file_path, source_code)?, "Json"),
        "yaml" | "yml" => (parse_yaml(file_path, source_code)?, "Yaml"),
        "toml" => (parse_toml(file_path, source_code)?, "Toml"),
        _ => return Err(format!("Unsupported config file extension: {}", extension)),
    };

    let elapsed = start.elapsed();

    Ok(ParseResult {
        file_path: file_path.to_string(),
        language: language.to_string(),
        units,
        parse_time_ms: elapsed.as_secs_f64() * 1000.0,
    })
}
