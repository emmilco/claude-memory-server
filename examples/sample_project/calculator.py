"""Sample Python module for testing code indexing."""


class Calculator:
    """A simple calculator class for basic arithmetic operations."""

    def __init__(self):
        """Initialize the calculator."""
        self.result = 0

    def add(self, a: float, b: float) -> float:
        """Add two numbers and return the result."""
        self.result = a + b
        return self.result

    def subtract(self, a: float, b: float) -> float:
        """Subtract b from a and return the result."""
        self.result = a - b
        return self.result

    def multiply(self, a: float, b: float) -> float:
        """Multiply two numbers and return the result."""
        self.result = a * b
        return self.result

    def divide(self, a: float, b: float) -> float:
        """
        Divide a by b and return the result.

        Raises:
            ZeroDivisionError: If b is zero.
        """
        if b == 0:
            raise ZeroDivisionError("Cannot divide by zero")
        self.result = a / b
        return self.result


def factorial(n: int) -> int:
    """
    Calculate the factorial of a non-negative integer.

    Args:
        n: A non-negative integer

    Returns:
        The factorial of n

    Raises:
        ValueError: If n is negative
    """
    if n < 0:
        raise ValueError("Factorial is not defined for negative numbers")
    if n == 0 or n == 1:
        return 1
    return n * factorial(n - 1)


def fibonacci(n: int) -> int:
    """
    Generate the nth Fibonacci number.

    Args:
        n: The position in the Fibonacci sequence (0-indexed)

    Returns:
        The nth Fibonacci number
    """
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


if __name__ == "__main__":
    # Example usage
    calc = Calculator()
    print(f"5 + 3 = {calc.add(5, 3)}")
    print(f"10 - 4 = {calc.subtract(10, 4)}")
    print(f"6 * 7 = {calc.multiply(6, 7)}")
    print(f"15 / 3 = {calc.divide(15, 3)}")

    print(f"Factorial of 5 = {factorial(5)}")
    print(f"Fibonacci(10) = {fibonacci(10)}")
