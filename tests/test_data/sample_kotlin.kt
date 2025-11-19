// Sample Kotlin file for testing parsing

package com.example.test

import kotlin.math.sqrt

// Interface definition
interface Drawable {
    fun draw()
    var color: String
}

// Data class
data class Point(var x: Double, var y: Double) {
    fun distance(to: Point): Double {
        val dx = x - to.x
        val dy = y - to.y
        return sqrt(dx * dx + dy * dy)
    }

    fun move(delta: Point) {
        x += delta.x
        y += delta.y
    }
}

// Regular class with inheritance
class Shape(var color: String, var name: String) : Drawable {
    override fun draw() {
        println("Drawing $name in $color")
    }

    fun describe(): String {
        return "$name with color $color"
    }

    companion object {
        fun createDefault(): Shape {
            return Shape("black", "default")
        }
    }
}

// Object declaration (singleton)
object MathUtils {
    fun calculateArea(width: Double, height: Double): Double {
        return width * height
    }
}

// Top-level functions
fun greet(person: String) {
    println("Hello, $person!")
}

fun processNumbers(numbers: List<Int>, operation: (Int) -> Int): List<Int> {
    return numbers.map(operation)
}

// Extension function
fun String.isPalindrome(): Boolean {
    return this == this.reversed()
}
