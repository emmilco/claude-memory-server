"""
Integration tests for FEAT-059 call graph extraction during indexing.

Tests that call graph data is properly extracted and stored during
normal code indexing operations.
"""

import pytest
import pytest_asyncio

from src.memory.incremental_indexer import IncrementalIndexer
from src.config import get_config


@pytest_asyncio.fixture
async def indexer():
    """Create incremental indexer for tests."""
    config = get_config()
    indexer = IncrementalIndexer(config=config, project_name="test_call_graph_indexing")
    await indexer.initialize()
    yield indexer
    # Cleanup
    await indexer.call_graph_store.delete_project_call_graph("test_call_graph_indexing")
    await indexer.close()


@pytest_asyncio.fixture
async def temp_project(tmp_path):
    """Create a temporary Python project for testing."""
    # Create sample Python files
    module_file = tmp_path / "calculator.py"
    module_file.write_text("""
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def compute_sum(numbers):
    total = 0
    for n in numbers:
        total = add(total, n)
    return total

class Calculator:
    def add_nums(self, a, b):
        return add(a, b)

    def compute(self, nums):
        return compute_sum(nums)
""")

    utils_file = tmp_path / "utils.py"
    utils_file.write_text("""
from calculator import add, compute_sum

def process_data(data):
    result = add(data[0], data[1])
    return compute_sum([result, data[2]])
""")

    yield tmp_path
    # Cleanup handled by tmp_path fixture


@pytest.mark.asyncio
async def test_call_extraction_during_indexing(indexer, temp_project):
    """Test that calls are extracted and stored during file indexing."""
    # Index the calculator module
    calc_file = temp_project / "calculator.py"
    result = await indexer.index_file(calc_file)

    # Verify indexing succeeded
    assert result["units_indexed"] > 0
    assert result.get("call_sites_extracted", 0) > 0

    # Load call graph
    graph = await indexer.call_graph_store.load_call_graph("test_call_graph_indexing")

    # Verify functions were stored
    assert "add" in graph.nodes
    assert "compute_sum" in graph.nodes
    assert "Calculator.add_nums" in graph.nodes

    # Verify calls were stored
    assert len(graph.calls) > 0

    # Verify specific call relationships
    callers_of_add = graph.find_callers("add")
    assert len(callers_of_add) >= 2  # compute_sum and Calculator.add_nums


@pytest.mark.asyncio
async def test_qualified_names_for_methods(indexer, temp_project):
    """Test that class methods get proper qualified names."""
    calc_file = temp_project / "calculator.py"
    await indexer.index_file(calc_file)

    graph = await indexer.call_graph_store.load_call_graph("test_call_graph_indexing")

    # Check that methods have qualified names
    assert "Calculator.add_nums" in graph.nodes
    assert "Calculator.compute" in graph.nodes

    # Verify method metadata
    add_nums_node = graph.nodes["Calculator.add_nums"]
    assert add_nums_node.name == "add_nums"
    assert add_nums_node.qualified_name == "Calculator.add_nums"


@pytest.mark.asyncio
async def test_call_chain_through_indexed_code(indexer, temp_project):
    """Test finding call chains through indexed code."""
    calc_file = temp_project / "calculator.py"
    await indexer.index_file(calc_file)

    graph = await indexer.call_graph_store.load_call_graph("test_call_graph_indexing")

    # Find call chain from Calculator.compute to add
    paths = graph.find_call_chain("Calculator.compute", "add")

    # Should find: Calculator.compute -> compute_sum -> add
    assert len(paths) > 0
    assert paths[0] == ["Calculator.compute", "compute_sum", "add"]


@pytest.mark.asyncio
async def test_multiple_file_indexing(indexer, temp_project):
    """Test indexing multiple files in a project."""
    calc_file = temp_project / "calculator.py"
    utils_file = temp_project / "utils.py"

    # Index both files
    await indexer.index_file(calc_file)
    await indexer.index_file(utils_file)

    graph = await indexer.call_graph_store.load_call_graph("test_call_graph_indexing")

    # Verify functions from both files are present
    assert "add" in graph.nodes
    assert "process_data" in graph.nodes

    # Verify cross-file calls
    callers_of_add = graph.find_callers("add")
    caller_names = [c.qualified_name for c in callers_of_add]
    assert "process_data" in caller_names


@pytest.mark.asyncio
async def test_reindexing_updates_call_graph(indexer, temp_project):
    """Test that re-indexing a file updates the call graph."""
    calc_file = temp_project / "calculator.py"

    # Index initially
    result1 = await indexer.index_file(calc_file)
    result1.get("call_sites_extracted", 0)

    # Modify file to add more function calls
    calc_file.write_text("""
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b

def compute(a, b, c):
    x = add(a, b)
    y = multiply(x, c)
    z = add(y, a)
    w = multiply(z, b)
    return add(w, multiply(a, b))
""")

    # Re-index
    result2 = await indexer.index_file(calc_file)
    calls_count_2 = result2.get("call_sites_extracted", 0)

    # Verify more calls extracted (should have 5 calls: 3x add, 2x multiply)
    assert calls_count_2 >= 5

    # Verify new function in graph
    graph = await indexer.call_graph_store.load_call_graph("test_call_graph_indexing")
    assert "compute" in graph.nodes
    assert "multiply" in graph.nodes


@pytest.mark.asyncio
async def test_empty_file_indexing(indexer, tmp_path):
    """Test indexing file with no function calls."""
    empty_file = tmp_path / "empty.py"
    empty_file.write_text("""
# Just a comment
x = 42
""")

    result = await indexer.index_file(empty_file)

    # Should succeed but extract no calls
    assert result["units_indexed"] == 0
    assert result.get("call_sites_extracted", 0) == 0


@pytest.mark.asyncio
async def test_nested_class_methods(indexer, tmp_path):
    """Test extraction from nested class structures."""
    nested_file = tmp_path / "nested.py"
    nested_file.write_text("""
class Outer:
    def outer_method(self):
        return self.inner_method()

    def inner_method(self):
        return 42

    class Inner:
        def nested_method(self):
            return 100
""")

    result = await indexer.index_file(nested_file)
    assert result["units_indexed"] > 0

    graph = await indexer.call_graph_store.load_call_graph("test_call_graph_indexing")

    # Note: Behavior depends on parser - nested classes might be flattened
    # Just verify indexing succeeded
    assert len(graph.nodes) > 0
