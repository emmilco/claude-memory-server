# Sample Project

This is a small sample project used for testing the Claude Memory RAG Server indexing functionality.

## Contents

- `calculator.py` - Python module with calculator functions and classes
- `utils.js` - JavaScript utility functions
- `data_processor.ts` - TypeScript data processing utilities (coming soon)

## Usage

This project is automatically indexed during the setup verification process.

You can also manually index it:

```bash
python -m src.cli index ./examples/sample_project --project-name sample-project
```

Then test search functionality:

```python
from src.core.server import MemoryRAGServer
from src.config import get_config

server = MemoryRAGServer(get_config())
results = await server.search_code("calculator function that adds numbers")
```
