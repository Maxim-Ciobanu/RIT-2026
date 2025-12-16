"""
Simple performance test for Nuitka compilation
Tests: loops, calculations, and function calls
"""
import time

def fibonacci(n):
    """Calculate fibonacci number recursively (inefficient but CPU-intensive)"""
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

def is_prime(n):
    """Check if number is prime"""
    if n < 2:
        return False
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            return False
    return True

def calculate_primes(limit):
    """Find all prime numbers up to limit"""
    primes = []
    for num in range(2, limit):
        if is_prime(num):
            primes.append(num)
    return primes

def main():
    print("=" * 50)
    print("Python Performance Test")
    print("=" * 50)
    
    # Test 1: Fibonacci
    print("\n[Test 1] Calculating Fibonacci(35)...")
    start = time.time()
    result = fibonacci(35)
    elapsed = time.time() - start
    print(f"Result: {result}")
    print(f"Time: {elapsed:.3f} seconds")
    
    # Test 2: Prime numbers
    print("\n[Test 2] Finding primes up to 100,000...")
    start = time.time()
    primes = calculate_primes(100000)
    elapsed = time.time() - start
    print(f"Found {len(primes)} prime numbers")
    print(f"Time: {elapsed:.3f} seconds")
    
    # Test 3: Matrix-like operations
    print("\n[Test 3] Matrix calculations (1000x1000)...")
    start = time.time()
    total = 0
    for i in range(1000):
        for j in range(1000):
            total += (i * j) ** 0.5
    elapsed = time.time() - start
    print(f"Result: {total:.2f}")
    print(f"Time: {elapsed:.3f} seconds")
    
    print("\n" + "=" * 50)
    print("Tests completed!")
    print("=" * 50)

if __name__ == "__main__":
    main()