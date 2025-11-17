/**
 * Sample JavaScript utilities for testing code indexing.
 */

/**
 * Check if a string is a palindrome.
 * @param {string} str - The string to check
 * @returns {boolean} True if the string is a palindrome, false otherwise
 */
function isPalindrome(str) {
    const cleaned = str.toLowerCase().replace(/[^a-z0-9]/g, '');
    return cleaned === cleaned.split('').reverse().join('');
}

/**
 * Find the maximum value in an array.
 * @param {number[]} arr - The array of numbers
 * @returns {number} The maximum value
 * @throws {Error} If array is empty
 */
function findMax(arr) {
    if (arr.length === 0) {
        throw new Error('Array cannot be empty');
    }
    return Math.max(...arr);
}

/**
 * String utility class.
 */
class StringUtils {
    /**
     * Capitalize the first letter of a string.
     * @param {string} str - The string to capitalize
     * @returns {string} The capitalized string
     */
    static capitalize(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }

    /**
     * Reverse a string.
     * @param {string} str - The string to reverse
     * @returns {string} The reversed string
     */
    static reverse(str) {
        return str.split('').reverse().join('');
    }

    /**
     * Count vowels in a string.
     * @param {string} str - The string to analyze
     * @returns {number} The number of vowels
     */
    static countVowels(str) {
        const vowels = str.match(/[aeiou]/gi);
        return vowels ? vowels.length : 0;
    }
}

module.exports = {
    isPalindrome,
    findMax,
    StringUtils
};
