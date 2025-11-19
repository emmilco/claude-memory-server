// Sample Swift file for testing parsing

import Foundation

// Protocol definition
protocol Drawable {
    func draw()
    var color: String { get set }
}

// Struct with methods
struct Point {
    var x: Double
    var y: Double

    func distance(to other: Point) -> Double {
        let dx = x - other.x
        let dy = y - other.y
        return sqrt(dx*dx + dy*dy)
    }

    mutating func move(by delta: Point) {
        x += delta.x
        y += delta.y
    }
}

// Class with methods and properties
class Shape: Drawable {
    var color: String
    var name: String

    init(color: String, name: String) {
        self.color = color
        self.name = name
    }

    func draw() {
        print("Drawing \(name) in \(color)")
    }

    func describe() -> String {
        return "\(name) with color \(color)"
    }

    class func createDefault() -> Shape {
        return Shape(color: "black", name: "default")
    }
}

// Function definitions
func calculateArea(width: Double, height: Double) -> Double {
    return width * height
}

func greet(_ person: String) {
    print("Hello, \(person)!")
}

func processNumbers(_ numbers: [Int], using operation: (Int) -> Int) -> [Int] {
    return numbers.map(operation)
}
