"""
Tests for PHP code parsing.

This test suite verifies comprehensive PHP support including:
- Basic classes and functions
- Interfaces
- Traits
- Namespaces
- Methods
- Performance requirements
"""

from mcp_performance_core import parse_source_file


# Sample PHP code with various constructs
SAMPLE_PHP = """<?php

namespace App\\Models;

// Basic class
class User {
    private $name;
    private $email;

    public function __construct($name, $email) {
        $this->name = $name;
        $this->email = $email;
    }

    public function getName() {
        return $this->name;
    }

    public function setName($name) {
        $this->name = $name;
    }
}

// Interface
interface Authenticatable {
    public function authenticate($credentials);
    public function logout();
}

// Trait
trait Timestamps {
    public function getCreatedAt() {
        return $this->created_at;
    }

    public function getUpdatedAt() {
        return $this->updated_at;
    }
}

// Class using trait
class Post {
    use Timestamps;

    private $title;
    private $content;

    public function publish() {
        echo "Publishing post: " . $this->title;
    }
}

// Free function
function calculateTotal($items) {
    $total = 0;
    foreach ($items as $item) {
        $total += $item['price'];
    }
    return $total;
}

function formatCurrency($amount) {
    return "$" . number_format($amount, 2);
}
?>"""


INTERFACE_PHP = """<?php

interface Serializable {
    public function serialize();
    public function unserialize($data);
}

interface JsonSerializable {
    public function jsonSerialize();
}
?>"""


TRAIT_PHP = """<?php

trait Logger {
    public function log($message) {
        echo "[LOG] " . $message;
    }

    public function error($message) {
        echo "[ERROR] " . $message;
    }
}

trait Cacheable {
    private $cache = [];

    public function getCached($key) {
        return $this->cache[$key] ?? null;
    }

    public function setCached($key, $value) {
        $this->cache[$key] = $value;
    }
}
?>"""


NAMESPACE_PHP = """<?php

namespace App\\Controllers\\Admin;

class DashboardController {
    public function index() {
        return view('admin.dashboard');
    }
}

namespace App\\Services;

class EmailService {
    public function send($to, $subject, $body) {
        // Send email logic
    }
}
?>"""


ABSTRACT_CLASS_PHP = """<?php

abstract class Animal {
    protected $name;

    public function __construct($name) {
        $this->name = $name;
    }

    abstract public function makeSound();

    public function getName() {
        return $this->name;
    }
}

class Dog extends Animal {
    public function makeSound() {
        return "Woof!";
    }
}
?>"""


class TestPhpFileParsing:
    """Test basic PHP file parsing."""

    def test_php_file_parsing(self):
        """Test that PHP files are parsed successfully."""
        result = parse_source_file("test.php", SAMPLE_PHP)
        assert result.language == "Php"
        assert result.file_path == "test.php"
        assert result.parse_time_ms > 0

    def test_php_extension(self):
        """Test .php file extension."""
        result = parse_source_file("test.php", SAMPLE_PHP)
        assert result.language == "Php"


class TestPhpUnitExtraction:
    """Test extraction of semantic units from PHP code."""

    def test_extracts_semantic_units(self):
        """Test that semantic units are extracted from PHP code."""
        result = parse_source_file("test.php", SAMPLE_PHP)
        assert len(result.units) > 0

    def test_unit_has_required_fields(self):
        """Test that extracted units have all required fields."""
        result = parse_source_file("test.php", SAMPLE_PHP)
        if len(result.units) > 0:
            unit = result.units[0]
            assert hasattr(unit, "unit_type")
            assert hasattr(unit, "name")
            assert hasattr(unit, "start_line")
            assert hasattr(unit, "end_line")
            assert hasattr(unit, "content")
            assert hasattr(unit, "language")
            assert unit.language == "Php"


class TestPhpClassExtraction:
    """Test PHP class extraction."""

    def test_extracts_classes(self):
        """Test that classes are extracted."""
        result = parse_source_file("test.php", SAMPLE_PHP)
        class_units = [u for u in result.units if u.unit_type == "class"]
        assert len(class_units) > 0

    def test_class_has_name(self):
        """Test that extracted classes have names."""
        result = parse_source_file("test.php", SAMPLE_PHP)
        class_units = [u for u in result.units if u.unit_type == "class"]
        if len(class_units) > 0:
            assert len(class_units[0].name) > 0

    def test_class_has_content(self):
        """Test that extracted classes have content."""
        result = parse_source_file("test.php", SAMPLE_PHP)
        class_units = [u for u in result.units if u.unit_type == "class"]
        if len(class_units) > 0:
            assert len(class_units[0].content) > 0

    def test_class_line_numbers(self):
        """Test that classes have valid line numbers."""
        result = parse_source_file("test.php", SAMPLE_PHP)
        class_units = [u for u in result.units if u.unit_type == "class"]
        if len(class_units) > 0:
            unit = class_units[0]
            assert unit.start_line > 0
            assert unit.end_line >= unit.start_line


class TestPhpFunctionExtraction:
    """Test PHP function extraction."""

    def test_extracts_functions(self):
        """Test that functions are extracted."""
        result = parse_source_file("test.php", SAMPLE_PHP)
        func_units = [u for u in result.units if u.unit_type == "function"]
        assert len(func_units) > 0

    def test_function_has_name(self):
        """Test that extracted functions have names."""
        result = parse_source_file("test.php", SAMPLE_PHP)
        func_units = [u for u in result.units if u.unit_type == "function"]
        if len(func_units) > 0:
            assert len(func_units[0].name) > 0

    def test_function_has_content(self):
        """Test that extracted functions have content."""
        result = parse_source_file("test.php", SAMPLE_PHP)
        func_units = [u for u in result.units if u.unit_type == "function"]
        if len(func_units) > 0:
            assert len(func_units[0].content) > 0


class TestPhpInterfaces:
    """Test PHP interface extraction."""

    def test_extracts_interfaces(self):
        """Test that interfaces are extracted as classes."""
        result = parse_source_file("test.php", INTERFACE_PHP)
        class_units = [u for u in result.units if u.unit_type == "class"]
        assert len(class_units) > 0

    def test_interface_has_name(self):
        """Test that extracted interfaces have names."""
        result = parse_source_file("test.php", INTERFACE_PHP)
        class_units = [u for u in result.units if u.unit_type == "class"]
        if len(class_units) > 0:
            assert len(class_units[0].name) > 0


class TestPhpTraits:
    """Test PHP trait extraction."""

    def test_extracts_traits(self):
        """Test that traits are extracted as classes."""
        result = parse_source_file("test.php", TRAIT_PHP)
        class_units = [u for u in result.units if u.unit_type == "class"]
        assert len(class_units) > 0

    def test_trait_has_name(self):
        """Test that extracted traits have names."""
        result = parse_source_file("test.php", TRAIT_PHP)
        class_units = [u for u in result.units if u.unit_type == "class"]
        if len(class_units) > 0:
            assert len(class_units[0].name) > 0


class TestPhpNamespaces:
    """Test PHP namespace handling."""

    def test_parses_code_with_namespaces(self):
        """Test that code with namespaces parses successfully."""
        result = parse_source_file("namespace.php", NAMESPACE_PHP)
        assert result.language == "Php"
        assert len(result.units) > 0

    def test_multiple_namespaces(self):
        """Test that multiple namespaces don't prevent parsing."""
        result = parse_source_file("namespace.php", NAMESPACE_PHP)
        class_units = [u for u in result.units if u.unit_type == "class"]
        assert len(class_units) > 0


class TestPhpAbstractClasses:
    """Test PHP abstract class extraction."""

    def test_extracts_abstract_classes(self):
        """Test that abstract classes are extracted."""
        result = parse_source_file("abstract.php", ABSTRACT_CLASS_PHP)
        class_units = [u for u in result.units if u.unit_type == "class"]
        assert len(class_units) > 0

    def test_extracts_concrete_classes(self):
        """Test that classes extending abstract classes are extracted."""
        result = parse_source_file("abstract.php", ABSTRACT_CLASS_PHP)
        class_units = [u for u in result.units if u.unit_type == "class"]
        # Should have both Animal and Dog
        assert len(class_units) >= 2


class TestPhpPerformance:
    """Test PHP parsing performance."""

    def test_parse_time_under_100ms(self):
        """Test that parsing completes in under 100ms."""
        result = parse_source_file("test.php", SAMPLE_PHP)
        assert result.parse_time_ms < 100

    def test_large_file_performance(self):
        """Test performance with larger PHP file."""
        # Create a larger file by repeating code
        large_php = SAMPLE_PHP * 10
        result = parse_source_file("large.php", large_php)
        assert result.parse_time_ms < 500  # Allow more time for larger file


class TestPhpEdgeCases:
    """Test edge cases in PHP parsing."""

    def test_empty_file(self):
        """Test parsing empty PHP file."""
        result = parse_source_file("empty.php", "<?php ?>")
        assert result.language == "Php"

    def test_comments_only(self):
        """Test parsing file with only comments."""
        php_code = "<?php\n// This is a comment\n/* Block comment */\n?>"
        result = parse_source_file("comments.php", php_code)
        assert result.language == "Php"

    def test_php_tags(self):
        """Test that PHP tags don't break parsing."""
        php_code = """<?php

class Test {
    public function method() {
        echo "Hello";
    }
}
?>"""
        result = parse_source_file("tags.php", php_code)
        assert result.language == "Php"
        assert len(result.units) > 0
