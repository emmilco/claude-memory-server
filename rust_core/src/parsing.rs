use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tree_sitter::{Language, Parser, Query, QueryCursor};
use streaming_iterator::StreamingIterator;

/// Supported programming languages for parsing
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SupportedLanguage {
    Python,
    JavaScript,
    TypeScript,
    Java,
    Go,
    Rust,
    Ruby,
    C,
    Cpp,
    CSharp,
    Sql,
    Php,
}

impl SupportedLanguage {
    fn from_extension(ext: &str) -> Option<Self> {
        match ext {
            "py" => Some(SupportedLanguage::Python),
            "js" | "jsx" | "mjs" => Some(SupportedLanguage::JavaScript),
            "ts" | "tsx" => Some(SupportedLanguage::TypeScript),
            "java" => Some(SupportedLanguage::Java),
            "go" => Some(SupportedLanguage::Go),
            "rs" => Some(SupportedLanguage::Rust),
            "rb" => Some(SupportedLanguage::Ruby),
            "c" => Some(SupportedLanguage::C),
            "cpp" | "cc" | "cxx" | "hpp" | "h" | "hxx" | "hh" => Some(SupportedLanguage::Cpp),
            "cs" => Some(SupportedLanguage::CSharp),
            "sql" => Some(SupportedLanguage::Sql),
            "php" => Some(SupportedLanguage::Php),
            _ => None,
        }
    }

    fn get_language(&self) -> Language {
        match self {
            SupportedLanguage::Python => tree_sitter_python::LANGUAGE.into(),
            SupportedLanguage::JavaScript => tree_sitter_javascript::LANGUAGE.into(),
            SupportedLanguage::TypeScript => tree_sitter_typescript::LANGUAGE_TYPESCRIPT.into(),
            SupportedLanguage::Java => tree_sitter_java::LANGUAGE.into(),
            SupportedLanguage::Go => tree_sitter_go::LANGUAGE.into(),
            SupportedLanguage::Rust => tree_sitter_rust::LANGUAGE.into(),
            SupportedLanguage::Ruby => tree_sitter_ruby::LANGUAGE.into(),
            SupportedLanguage::C => tree_sitter_cpp::LANGUAGE.into(),
            SupportedLanguage::Cpp => tree_sitter_cpp::LANGUAGE.into(),
            SupportedLanguage::CSharp => tree_sitter_c_sharp::LANGUAGE.into(),
            SupportedLanguage::Sql => tree_sitter_sequel::LANGUAGE.into(),
            SupportedLanguage::Php => tree_sitter_php::LANGUAGE_PHP.into(),
        }
    }

    fn function_query(&self) -> &str {
        match self {
            SupportedLanguage::Python => {
                r#"
                (function_definition
                  name: (identifier) @name
                  parameters: (parameters) @params
                  body: (block) @body) @function
                "#
            }
            SupportedLanguage::JavaScript => {
                r#"
                (function_declaration
                  name: (identifier) @name
                  parameters: (formal_parameters) @params
                  body: (statement_block) @body) @function
                "#
            }
            SupportedLanguage::TypeScript => {
                // TypeScript functions can have type annotations
                r#"
                (function_declaration
                  name: (identifier) @name
                  parameters: (formal_parameters) @params
                  body: (statement_block) @body) @function
                "#
            }
            SupportedLanguage::Java => {
                r#"
                (method_declaration
                  name: (identifier) @name
                  parameters: (formal_parameters) @params
                  body: (block) @body) @function
                "#
            }
            SupportedLanguage::Go => {
                r#"
                (function_declaration
                  name: (identifier) @name
                  parameters: (parameter_list) @params
                  body: (block) @body) @function
                "#
            }
            SupportedLanguage::Rust => {
                r#"
                (function_item
                  name: (identifier) @name
                  parameters: (parameters) @params
                  body: (block) @body) @function
                "#
            }
            SupportedLanguage::Ruby => {
                r#"
                (method
                  name: (_) @name
                  parameters: (method_parameters)? @params) @function
                "#
            }
            SupportedLanguage::C | SupportedLanguage::Cpp => {
                r#"
                (function_definition
                  declarator: (function_declarator
                    declarator: (_) @name)
                  body: (compound_statement) @body) @function
                "#
            }
            SupportedLanguage::CSharp => {
                r#"
                (method_declaration
                  name: (identifier) @name) @function
                "#
            }
            SupportedLanguage::Sql => {
                // SQL functions and procedures
                r#"
                (create_function) @function
                "#
            }
            SupportedLanguage::Php => {
                r#"
                (function_definition
                  name: (name) @name
                  parameters: (formal_parameters) @params
                  body: (compound_statement) @body) @function
                "#
            }
        }
    }

    fn class_query(&self) -> &str {
        match self {
            SupportedLanguage::Python => {
                r#"
                (class_definition
                  name: (identifier) @name
                  body: (block) @body) @class
                "#
            }
            SupportedLanguage::JavaScript => {
                r#"
                (class_declaration
                  name: (identifier) @name
                  body: (class_body) @body) @class
                "#
            }
            SupportedLanguage::TypeScript => {
                // TypeScript can use both identifier and type_identifier for class names
                r#"
                (class_declaration
                  name: (_) @name
                  body: (class_body) @body) @class
                "#
            }
            SupportedLanguage::Java => {
                r#"
                (class_declaration
                  name: (identifier) @name
                  body: (class_body) @body) @class
                "#
            }
            SupportedLanguage::Go => {
                r#"
                (type_declaration
                  (type_spec
                    name: (type_identifier) @name
                    type: (struct_type) @body)) @class
                "#
            }
            SupportedLanguage::Rust => {
                r#"
                (struct_item
                  name: (type_identifier) @name
                  body: (field_declaration_list) @body) @class
                "#
            }
            SupportedLanguage::Ruby => {
                // Ruby has both classes and modules
                r#"
                [(class
                  name: (constant) @name)
                 (module
                  name: (constant) @name)] @class
                "#
            }
            SupportedLanguage::C => {
                // C only has structs, not classes
                r#"
                (struct_specifier
                  name: (type_identifier) @name
                  body: (field_declaration_list) @body) @class
                "#
            }
            SupportedLanguage::Cpp => {
                // C++ has both classes and structs - use alternation to capture both
                r#"
                [(class_specifier
                  name: (type_identifier) @name
                  body: (field_declaration_list) @body)
                 (struct_specifier
                  name: (type_identifier) @name
                  body: (field_declaration_list) @body)] @class
                "#
            }
            SupportedLanguage::CSharp => {
                r#"
                [(class_declaration
                  name: (identifier) @name)
                 (interface_declaration
                  name: (identifier) @name)
                 (struct_declaration
                  name: (identifier) @name)] @class
                "#
            }
            SupportedLanguage::Sql => {
                // SQL tables and views as "class" equivalents
                r#"
                [
                  (create_table) @class
                  (create_view) @class
                ]
                "#
            }
            SupportedLanguage::Php => {
                // PHP classes, interfaces, and traits
                r#"
                [(class_declaration
                  name: (name) @name
                  body: (declaration_list) @body)
                 (interface_declaration
                  name: (name) @name
                  body: (declaration_list) @body)
                 (trait_declaration
                  name: (name) @name
                  body: (declaration_list) @body)] @class
                "#
            }
        }
    }
}

/// Represents a parsed semantic unit (function, class, etc.)
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass]
pub struct SemanticUnit {
    #[pyo3(get)]
    pub unit_type: String, // "function", "class", "import"
    #[pyo3(get)]
    pub name: String,
    #[pyo3(get)]
    pub start_line: usize,
    #[pyo3(get)]
    pub end_line: usize,
    #[pyo3(get)]
    pub start_byte: usize,
    #[pyo3(get)]
    pub end_byte: usize,
    #[pyo3(get)]
    pub signature: String,
    #[pyo3(get)]
    pub content: String,
    #[pyo3(get)]
    pub language: String,
}

#[pymethods]
impl SemanticUnit {
    fn __repr__(&self) -> String {
        format!(
            "SemanticUnit(type={}, name={}, lines={}-{})",
            self.unit_type, self.name, self.start_line, self.end_line
        )
    }
}

/// Parse result containing all extracted semantic units
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass]
pub struct ParseResult {
    #[pyo3(get)]
    pub file_path: String,
    #[pyo3(get)]
    pub language: String,
    #[pyo3(get)]
    pub units: Vec<SemanticUnit>,
    #[pyo3(get)]
    pub parse_time_ms: f64,
}

#[pymethods]
impl ParseResult {
    fn __repr__(&self) -> String {
        format!(
            "ParseResult(file={}, language={}, units={}, time={}ms)",
            self.file_path,
            self.language,
            self.units.len(),
            self.parse_time_ms
        )
    }
}

/// Code parser using tree-sitter
pub struct CodeParser {
    parsers: HashMap<String, Parser>,
}

impl CodeParser {
    pub fn new() -> Self {
        let mut parsers = HashMap::new();

        // Initialize parsers for each language
        for lang in [
            SupportedLanguage::Python,
            SupportedLanguage::JavaScript,
            SupportedLanguage::TypeScript,
            SupportedLanguage::Java,
            SupportedLanguage::Go,
            SupportedLanguage::Rust,
            SupportedLanguage::Ruby,
            SupportedLanguage::C,
            SupportedLanguage::Cpp,
            SupportedLanguage::CSharp,
            SupportedLanguage::Sql,
            SupportedLanguage::Php,
        ] {
            let mut parser = Parser::new();
            parser
                .set_language(&lang.get_language())
                .expect("Error loading language");
            parsers.insert(format!("{:?}", lang), parser);
        }

        Self { parsers }
    }

    pub fn parse_file(
        &mut self,
        file_path: &str,
        source_code: &str,
    ) -> Result<ParseResult, String> {
        let start = std::time::Instant::now();

        // Detect language from file extension
        let extension = std::path::Path::new(file_path)
            .extension()
            .and_then(|e| e.to_str())
            .ok_or("No file extension")?;

        let lang = SupportedLanguage::from_extension(extension)
            .ok_or(format!("Unsupported file extension: {}", extension))?;

        let lang_name = format!("{:?}", lang);

        // Get parser for this language
        let parser = self
            .parsers
            .get_mut(&lang_name)
            .ok_or("Parser not found")?;

        // Parse the source code
        let tree = parser
            .parse(source_code, None)
            .ok_or("Failed to parse file")?;

        let mut units = Vec::new();

        // Extract functions (with error recovery)
        match Query::new(&lang.get_language(), lang.function_query()) {
            Ok(function_query) => {
                let mut cursor = QueryCursor::new();
                let mut captures = cursor.captures(&function_query, tree.root_node(), source_code.as_bytes());

                while let Some((match_, _)) = captures.next() {
                    if let Some(capture) = match_.captures.first() {
                        let node = capture.node;
                        let name = node
                            .utf8_text(source_code.as_bytes())
                            .unwrap_or("<unknown>")
                            .lines()
                            .next()
                            .unwrap_or("")
                            .trim();

                        units.push(SemanticUnit {
                            unit_type: "function".to_string(),
                            name: name.to_string(),
                            start_line: node.start_position().row + 1,
                            end_line: node.end_position().row + 1,
                            start_byte: node.start_byte(),
                            end_byte: node.end_byte(),
                            signature: name.to_string(),
                            content: node.utf8_text(source_code.as_bytes()).unwrap_or("").to_string(),
                            language: lang_name.clone(),
                        });
                    }
                }
            }
            Err(e) => {
                // Log error but continue parsing (skip function extraction for this file)
                eprintln!("Warning: Function query failed for {}: {}. Continuing without function extraction.", file_path, e);
            }
        }

        // Extract classes (with error recovery)
        match Query::new(&lang.get_language(), lang.class_query()) {
            Ok(class_query) => {
                let mut cursor = QueryCursor::new();
                let mut captures = cursor.captures(&class_query, tree.root_node(), source_code.as_bytes());

                while let Some((match_, _)) = captures.next() {
                    if let Some(capture) = match_.captures.first() {
                        let node = capture.node;
                        let name = node
                            .utf8_text(source_code.as_bytes())
                            .unwrap_or("<unknown>")
                            .lines()
                            .next()
                            .unwrap_or("")
                            .trim();

                        units.push(SemanticUnit {
                            unit_type: "class".to_string(),
                            name: name.to_string(),
                            start_line: node.start_position().row + 1,
                            end_line: node.end_position().row + 1,
                            start_byte: node.start_byte(),
                            end_byte: node.end_byte(),
                            signature: name.to_string(),
                            content: node.utf8_text(source_code.as_bytes()).unwrap_or("").to_string(),
                            language: lang_name.clone(),
                        });
                    }
                }
            }
            Err(e) => {
                // Log error but continue parsing (skip class extraction for this file)
                eprintln!("Warning: Class query failed for {}: {}. Continuing without class extraction.", file_path, e);
            }
        }

        let elapsed = start.elapsed();

        Ok(ParseResult {
            file_path: file_path.to_string(),
            language: lang_name,
            units,
            parse_time_ms: elapsed.as_secs_f64() * 1000.0,
        })
    }
}

/// Parse a source file and extract semantic units
#[pyfunction]
pub fn parse_source_file(file_path: String, source_code: String) -> PyResult<ParseResult> {
    // Check if this is a configuration file first
    let extension = std::path::Path::new(&file_path)
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("");

    // Handle config files with native parsers
    if matches!(extension, "json" | "yaml" | "yml" | "toml") {
        return crate::config_parsing::parse_config_file(&file_path, &source_code)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e));
    }

    // Handle code files with tree-sitter
    let mut parser = CodeParser::new();
    parser
        .parse_file(&file_path, &source_code)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))
}

/// Batch parse multiple files in parallel
#[pyfunction]
pub fn batch_parse_files(files: Vec<(String, String)>) -> PyResult<Vec<ParseResult>> {
    use rayon::prelude::*;

    let results: Result<Vec<ParseResult>, String> = files
        .par_iter()
        .map(|(path, content)| {
            // Check if this is a configuration file
            let extension = std::path::Path::new(path)
                .extension()
                .and_then(|e| e.to_str())
                .unwrap_or("");

            if matches!(extension, "json" | "yaml" | "yml" | "toml") {
                crate::config_parsing::parse_config_file(path, content)
            } else {
                let mut parser = CodeParser::new();
                parser.parse_file(path, content)
            }
        })
        .collect();

    results.map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))
}
