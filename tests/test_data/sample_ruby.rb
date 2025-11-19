# Sample Ruby file for testing parsing

module MyNamespace
  # A simple class demonstrating Ruby syntax
  class Calculator
    def initialize(name)
      @name = name
    end

    # Instance method with parameters
    def add(a, b)
      a + b
    end

    # Instance method with default parameters
    def multiply(a, b = 2)
      a * b
    end

    # Class method
    def self.version
      "1.0.0"
    end
  end

  # Another class in the same module
  class StringHelper
    def self.upcase_all(text)
      text.upcase
    end

    def downcase_first(text)
      text[0].downcase + text[1..-1]
    end
  end

  # Nested module
  module Utils
    def self.log(message)
      puts "[LOG] #{message}"
    end

    def self.format_date(date)
      date.strftime("%Y-%m-%d")
    end
  end
end

# Top-level class
class TopLevelClass
  def greet
    "Hello, World!"
  end
end
