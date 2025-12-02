"""Code smell pattern library."""

from dataclasses import dataclass
from typing import List


@dataclass
class CodeSmellPattern:
    """Represents a code smell or anti-pattern."""

    id: str
    name: str
    category: str  # 'security' | 'performance' | 'maintainability' | 'best_practice'
    severity: str  # 'low' | 'medium' | 'high' | 'critical'
    description: str
    example_code: str  # Example code showing the smell
    fix_description: str
    languages: List[str]  # Applicable programming languages


# Security Patterns (Critical/High)
SECURITY_PATTERNS = [
    CodeSmellPattern(
        id="sql-injection-001",
        name="SQL Injection Risk",
        category="security",
        severity="critical",
        description="Direct string concatenation or formatting in SQL query enables SQL injection attacks",
        example_code="""query = "SELECT * FROM users WHERE id = " + user_id
# OR
query = f"SELECT * FROM users WHERE id = {user_id}"
# OR
cursor.execute("SELECT * FROM users WHERE id = " + str(user_id))""",
        fix_description="Use parameterized queries with placeholders: cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
        languages=["python", "javascript", "java", "php", "ruby", "go"],
    ),
    CodeSmellPattern(
        id="hardcoded-secret-001",
        name="Hardcoded Secret",
        category="security",
        severity="critical",
        description="API keys, passwords, or tokens hardcoded in source code can be exposed in version control",
        example_code='''API_KEY = "sk-1234567890abcdef"
PASSWORD = "my_secret_password"
aws_secret = "AKIAIOSFODNN7EXAMPLE"''',
        fix_description="Store secrets in environment variables or secure credential stores: API_KEY = os.getenv('API_KEY')",
        languages=["python", "javascript", "java", "go", "rust", "ruby", "php"],
    ),
    CodeSmellPattern(
        id="eval-usage-001",
        name="Dangerous eval() Usage",
        category="security",
        severity="high",
        description="Using eval() or exec() with user input can execute arbitrary code",
        example_code="""result = eval(user_input)
exec(code_from_user)""",
        fix_description="Use safer alternatives like ast.literal_eval() for data, or parse input explicitly",
        languages=["python", "javascript"],
    ),
    CodeSmellPattern(
        id="command-injection-001",
        name="Command Injection Risk",
        category="security",
        severity="critical",
        description="Using shell commands with user input without sanitization enables command injection",
        example_code="""os.system("ls " + user_filename)
subprocess.call("rm " + file_path, shell=True)""",
        fix_description="Use subprocess with list arguments instead of shell=True, and validate all user input",
        languages=["python", "ruby", "php", "java"],
    ),
]

# Performance Patterns (Medium/High)
PERFORMANCE_PATTERNS = [
    CodeSmellPattern(
        id="n-plus-one-001",
        name="N+1 Query Problem",
        category="performance",
        severity="high",
        description="Loop with database query inside causes N+1 queries, severely impacting performance",
        example_code="""for user in users:
    profile = db.query("SELECT * FROM profiles WHERE user_id = ?", user.id)
    # Process profile

for order in orders:
    customer = Customer.objects.get(id=order.customer_id)""",
        fix_description="Use JOIN or prefetch to load all related data at once: profiles = db.query('SELECT * FROM profiles WHERE user_id IN (?)', user_ids)",
        languages=["python", "javascript", "ruby", "java", "php"],
    ),
    CodeSmellPattern(
        id="string-concat-loop-001",
        name="Inefficient String Concatenation",
        category="performance",
        severity="medium",
        description="String concatenation in loop creates many intermediate string objects",
        example_code='''result = ""
for item in items:
    result += str(item) + ", "

text = ""
for line in lines:
    text = text + line + "\\n"''',
        fix_description="Use join() or StringBuilder: result = ', '.join(str(item) for item in items)",
        languages=["python", "java", "javascript"],
    ),
    CodeSmellPattern(
        id="missing-index-001",
        name="Query Without Index",
        category="performance",
        severity="medium",
        description="Database queries on unindexed columns cause full table scans",
        example_code="""SELECT * FROM users WHERE email = 'user@example.com'
-- If email column has no index""",
        fix_description="Add database index on frequently queried columns: CREATE INDEX idx_users_email ON users(email)",
        languages=["sql"],
    ),
]

# Maintainability Patterns (Medium)
MAINTAINABILITY_PATTERNS = [
    CodeSmellPattern(
        id="magic-number-001",
        name="Magic Number",
        category="maintainability",
        severity="medium",
        description="Hardcoded numeric constants reduce code readability and maintainability",
        example_code="""if status_code == 200:
    process_success()

timeout = 300
max_retries = 3""",
        fix_description="Extract to named constants: HTTP_OK = 200, TIMEOUT_SECONDS = 300, MAX_RETRIES = 3",
        languages=["python", "javascript", "java", "go", "rust", "c", "cpp"],
    ),
    CodeSmellPattern(
        id="god-class-001",
        name="God Class",
        category="maintainability",
        severity="medium",
        description="Class with too many responsibilities violates Single Responsibility Principle",
        example_code="""class UserManager:
    def create_user(self): ...
    def delete_user(self): ...
    def send_email(self): ...
    def validate_password(self): ...
    def generate_report(self): ...
    def export_data(self): ...
    def import_data(self): ...
    # 10+ methods doing unrelated things""",
        fix_description="Split into focused classes: UserService, EmailService, ReportService, etc.",
        languages=["python", "javascript", "java", "go", "rust", "ruby", "php"],
    ),
    CodeSmellPattern(
        id="long-method-chain-001",
        name="Long Method Chain",
        category="maintainability",
        severity="low",
        description="Long method chains reduce readability and make debugging difficult",
        example_code="""result = user.get_profile().get_settings().get_preferences().get_theme().get_color().to_hex()
data = api.fetch().filter().map().reduce().format()""",
        fix_description="Break into intermediate variables with meaningful names for clarity",
        languages=["python", "javascript", "ruby", "java"],
    ),
    CodeSmellPattern(
        id="commented-code-001",
        name="Commented-Out Code",
        category="maintainability",
        severity="low",
        description="Large blocks of commented code clutter the codebase and confuse readers",
        example_code="""# def old_function():
#     # This was the old implementation
#     return calculate_old_way()

# Legacy code - might need later
# for item in items:
#     process(item)""",
        fix_description="Remove commented code (it's in version control if needed): delete the commented blocks",
        languages=["python", "javascript", "java", "go", "rust", "c", "cpp", "php"],
    ),
]

# Best Practice Patterns (Low/Medium)
BEST_PRACTICE_PATTERNS = [
    CodeSmellPattern(
        id="missing-error-handling-001",
        name="Missing Error Handling",
        category="best_practice",
        severity="medium",
        description="Operations that can fail without error handling lead to crashes",
        example_code="""file = open("data.txt")
data = file.read()
file.close()

result = int(user_input)
response = requests.get(url)""",
        fix_description="Add try/except blocks around operations that can fail: try: file = open(...) except FileNotFoundError: ...",
        languages=["python", "javascript", "java", "go", "rust", "ruby"],
    ),
    CodeSmellPattern(
        id="no-input-validation-001",
        name="Missing Input Validation",
        category="best_practice",
        severity="medium",
        description="Using user input directly without validation can cause errors or security issues",
        example_code="""def process_age(age):
    # No validation
    return age * 2

username = request.form['username']
save_to_db(username)""",
        fix_description="Validate all user input: if not isinstance(age, int) or age < 0: raise ValueError('Invalid age')",
        languages=["python", "javascript", "java", "php", "ruby"],
    ),
    CodeSmellPattern(
        id="bare-except-001",
        name="Bare Except Clause",
        category="best_practice",
        severity="medium",
        description="Catching all exceptions with bare 'except:' hides bugs and makes debugging hard",
        example_code="""try:
    risky_operation()
except Exception:
    pass

try:
    process_data()
except Exception:
    logger.error("Something went wrong")""",
        fix_description="Catch specific exceptions: except (ValueError, KeyError) as e: ...",
        languages=["python"],
    ),
]

# Combine all patterns
ALL_PATTERNS = (
    SECURITY_PATTERNS
    + PERFORMANCE_PATTERNS
    + MAINTAINABILITY_PATTERNS
    + BEST_PRACTICE_PATTERNS
)


def get_patterns_by_category(category: str) -> List[CodeSmellPattern]:
    """Get all patterns for a specific category."""
    return [p for p in ALL_PATTERNS if p.category == category]


def get_patterns_by_severity(severity: str) -> List[CodeSmellPattern]:
    """Get all patterns for a specific severity level."""
    return [p for p in ALL_PATTERNS if p.severity == severity]


def get_patterns_by_language(language: str) -> List[CodeSmellPattern]:
    """Get all patterns applicable to a specific language."""
    return [
        p
        for p in ALL_PATTERNS
        if language.lower() in [lang.lower() for lang in p.languages]
    ]
