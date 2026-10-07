"""Keep HTTP, business rules and persistence separated as the application grows."""
import ast
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / 'app'


class ArchitectureTests(unittest.TestCase):
    def check_layer(self, layer, forbidden_imports, forbidden_calls=()):
        for path in (APP / layer).rglob('*.py'):
            with self.subTest(file=str(path.relative_to(APP))):
                tree = ast.parse(path.read_text(encoding='utf-8'))
                for node in ast.walk(tree):
                    imports = []
                    if isinstance(node, ast.ImportFrom):
                        imports = [node.module or '']
                    elif isinstance(node, ast.Import):
                        imports = [alias.name for alias in node.names]
                    for name in imports:
                        self.assertFalse(any(name == prefix or name.startswith(prefix + '.') for prefix in forbidden_imports), name)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                        self.assertNotIn(node.func.attr, forbidden_calls)

    def test_api_does_not_access_database(self):
        self.check_layer('api', ('app.database', 'sqlite3', 'psycopg', 'chromadb', 'redis'), ('execute', 'executemany', 'executescript'))

    def test_business_does_not_depend_on_http_or_sql_drivers(self):
        self.check_layer('services', ('app.api', 'fastapi', 'starlette', 'sqlite3', 'psycopg', 'chromadb', 'redis'), ('execute', 'executemany', 'executescript'))

    def test_database_and_adapters_do_not_import_upper_layers(self):
        for layer in ('database', 'infrastructure'):
            self.check_layer(layer, ('app.api', 'app.services', 'fastapi', 'starlette'))

    def test_no_legacy_module_imports(self):
        for layer in ('api', 'services', 'database', 'infrastructure'):
            self.check_layer(layer, ('app.common', 'app.agents', 'app.models', 'app.core.dependencies'))
