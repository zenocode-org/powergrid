from examples.countdown.generate import generate_countdown_problem
from examples.countdown.verify import verify_solution

def test_generated_problem_has_solution():
    """
    Tests that we can generate a valid countdown problem.
    We don't test a specific solution since there may be many.
    """
    # Act
    problem = generate_countdown_problem(num_initial_numbers=4, max_number_value=10)
    
    # Assert basic structure
    assert len(problem.numbers) == 4
    assert all(isinstance(num, int) for num in problem.numbers)
    assert all(num > 0 for num in problem.numbers)  # All numbers should be positive
    assert isinstance(problem.target, int)
    assert problem.target > 0

def test_verification_works():
    """
    Tests that the verification function correctly identifies valid and invalid solutions.
    """
    from examples.countdown.types import CountdownProblem
    
    # Create a simple test case
    problem = CountdownProblem(numbers=[1, 2, 3, 4], target=10)
    
    # Test valid expressions
    assert verify_solution(problem, "1 + 2 + 3 + 4")  # 10
    assert verify_solution(problem, "2 * 3 + 4")       # 10  
    assert verify_solution(problem, "(1 + 4) * 2")     # 10
    
    # Test invalid expressions
    assert not verify_solution(problem, "1 + 2 + 3")      # 6, not 10
    assert not verify_solution(problem, "1 + 2 + 3 + 5")  # Uses 5, not available
    assert not verify_solution(problem, "1 + 1 + 4 + 4")  # Uses numbers more than available

def test_expression_evaluation():
    """
    Tests the expression evaluation function directly.
    """
    from examples.countdown.verify import evaluate_expression
    
    # Test valid evaluations
    assert evaluate_expression("2 + 3", [1, 2, 3, 4]) == 5
    assert evaluate_expression("2 * 3", [1, 2, 3, 4]) == 6
    assert evaluate_expression("(2 + 3) * 4", [1, 2, 3, 4]) == 20
    
    # Test invalid cases
    assert evaluate_expression("2 + 5", [1, 2, 3, 4]) is None  # 5 not available
    assert evaluate_expression("2 + 2", [1, 2, 3, 4]) is None  # Using 2 twice
    assert evaluate_expression("2 / 0", [1, 2, 3, 4]) is None  # Division by zero

def test_security_against_malicious_expressions():
    """
    Tests that the AST-based evaluator rejects potentially dangerous expressions.
    """
    from examples.countdown.verify import evaluate_expression
    
    # Test that function calls are rejected
    assert evaluate_expression("__import__('os').system('ls')", [1, 2, 3, 4]) is None
    
    # Test that attribute access is rejected
    assert evaluate_expression("(1).__class__", [1, 2, 3, 4]) is None
    
    # Test that complex expressions with invalid operations are rejected
    assert evaluate_expression("exec('print(1)')", [1, 2, 3, 4]) is None
    assert evaluate_expression("eval('1+1')", [1, 2, 3, 4]) is None
    
    # Test that only basic arithmetic is allowed
    assert evaluate_expression("2 ** 3", [1, 2, 3, 4]) is None  # Power operator not allowed
