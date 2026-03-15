import re
import ast
from typing import List, Optional
from .types import CountdownProblem

def tokenize_expression(expr: str) -> List[str]:
    """
    Tokenize a mathematical expression into numbers, operators, and parentheses.
    """
    # Remove spaces and split on operators and parentheses
    tokens = re.findall(r'\d+|[+\-*/()]', expr.replace(' ', ''))
    return tokens

def safe_evaluate_expression(expr: str, available_numbers: List[int]) -> Optional[int]:
    """
    Safely evaluate a mathematical expression using AST parsing instead of eval.
    Returns the result if valid, None if invalid.
    """
    try:
        # Parse tokens to check number usage
        tokens = tokenize_expression(expr)
        
        # Extract numbers used in the expression
        used_numbers = []
        for token in tokens:
            if token.isdigit():
                used_numbers.append(int(token))
        
        # Check if all used numbers are available
        available_copy = available_numbers.copy()
        for num in used_numbers:
            if num in available_copy:
                available_copy.remove(num)
            else:
                return None  # Number not available or used more than available
        
        # Parse the expression into an AST
        try:
            tree = ast.parse(expr, mode='eval')
        except SyntaxError:
            return None
        
        # Evaluate using a safe AST visitor
        result = _safe_eval_ast(tree.body)
        
        # Ensure result is an integer (or close to it)
        if isinstance(result, (int, float)) and abs(result - round(result)) < 1e-10:
            return int(round(result))
        
        return None
        
    except (ValueError, TypeError, ZeroDivisionError):
        return None

def _safe_eval_ast(node) -> float:
    """
    Safely evaluate an AST node, only allowing basic arithmetic operations.
    """
    if isinstance(node, ast.Constant):  # Python 3.8+
        if isinstance(node.value, (int, float)):
            return float(node.value)
        else:
            raise ValueError("Invalid constant type")
    elif isinstance(node, ast.Constant):  # Python < 3.8 compatibility
        if isinstance(node.n, (int, float)):
            return float(node.n)
        else:
            raise ValueError("Invalid number type")
    elif isinstance(node, ast.BinOp):
        left = _safe_eval_ast(node.left)
        right = _safe_eval_ast(node.right)
        
        if isinstance(node.op, ast.Add):
            return left + right
        elif isinstance(node.op, ast.Sub):
            return left - right
        elif isinstance(node.op, ast.Mult):
            return left * right
        elif isinstance(node.op, ast.Div):
            if right == 0:
                raise ZeroDivisionError("Division by zero")
            return left / right
        else:
            raise ValueError(f"Unsupported operation: {type(node.op)}")
    elif isinstance(node, ast.UnaryOp):
        operand = _safe_eval_ast(node.operand)
        if isinstance(node.op, ast.UAdd):
            return operand
        elif isinstance(node.op, ast.USub):
            return -operand
        else:
            raise ValueError(f"Unsupported unary operation: {type(node.op)}")
    else:
        raise ValueError(f"Unsupported node type: {type(node)}")

def evaluate_expression(expr: str, available_numbers: List[int]) -> Optional[int]:
    """
    Safely evaluate a mathematical expression using only the available numbers.
    Returns the result if valid, None if invalid.
    
    This function uses AST parsing for safety instead of eval().
    """
    return safe_evaluate_expression(expr, available_numbers)

def verify_solution(problem: CountdownProblem, expression: str) -> bool:
    """
    Verify if a given expression solves the countdown problem.
    """
    result = evaluate_expression(expression, problem.numbers)
    return result == problem.target
