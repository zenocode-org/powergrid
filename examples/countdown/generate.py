import random
import json
import argparse
from pathlib import Path
from .types import CountdownProblem

def generate_countdown_problem(
    num_initial_numbers: int = 5, max_number_value: int = 10
) -> CountdownProblem:
    """
    Generates a solvable Countdown numbers problem by working backwards from a solution.
    We don't return the solution - just guarantee that one exists.
    """
    ops = ['+', '-', '*']
    
    # Start with a final number
    current_value = random.randint(1, 50)
    numbers_used = [current_value]

    # Iteratively build up by applying inverse operations
    # This guarantees there's at least one solution
    for _ in range(num_initial_numbers - 1):
        op = random.choice(ops)
        num = random.randint(1, max_number_value)
        
        # Ensure non-trivial operations and positive results
        if op == '*' and num == 1:
            num = random.randint(2, max_number_value)
        if op == '-':
            # Make sure subtraction doesn't create negative values
            if current_value <= num:
                # Switch to addition instead
                op = '+'

        if op == '+':
            # To get 'current_value', we add 'num' to 'current_value - num'
            current_value -= num
            # Ensure we don't go negative
            if current_value <= 0:
                current_value = abs(current_value) + 1
        elif op == '-':
            # To get 'current_value', we subtract 'num' from 'current_value + num'
            current_value += num
        elif op == '*':
            # To get 'current_value', we multiply 'current_value' by 'num'
            current_value *= num

        numbers_used.append(num)

    # Ensure target is positive
    if current_value <= 0:
        current_value = abs(current_value) + random.randint(1, 10)

    random.shuffle(numbers_used)
    
    return CountdownProblem(numbers=numbers_used, target=current_value)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Countdown numbers problems")
    parser.add_argument(
        "--num-samples", 
        type=int, 
        default=3, 
        help="Number of problems to generate (default: 3)"
    )
    parser.add_argument(
        "--output", 
        type=str, 
        help="Output file path (default: print to stdout)"
    )
    parser.add_argument(
        "--num-numbers",
        type=int,
        default=5,
        help="Number of numbers in each problem (default: 5)"
    )
    parser.add_argument(
        "--max-value",
        type=int,
        default=10,
        help="Maximum value for generated numbers (default: 10)"
    )
    
    args = parser.parse_args()
    
    # Generate the requested number of problems
    examples = []
    for _ in range(args.num_samples):
        problem = generate_countdown_problem(
            num_initial_numbers=args.num_numbers,
            max_number_value=args.max_value
        )
        examples.append(problem.model_dump())
    
    # Output the results
    output_json = json.dumps(examples, indent=2)
    
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(output_json)
        print(f"Generated {args.num_samples} problems and saved to {args.output}")
    else:
        print(output_json)
