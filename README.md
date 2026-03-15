# Applied AI Engineer — Take-Home Exercise

## 1. Context

You work at a frontier-lab focused on advancing the capabilities of current LLMs. A new training run is coming up and the lab asks you to spot a task at which the current model often fails and come up with a method to generate synthetic data to fill that gap.

This repository provides a starter kit and an example implementation for a simple task to guide you.

## 2. Example Implementation

The `examples/countdown/` directory contains a complete example implementation of the Countdown Numbers Game:

- **`types.py`**: Data models using Pydantic
- **`generate.py`**: Problem generation (generates problems without solutions)
- **`verify.py`**: Verification utilities to check if expressions solve problems
- **`tests/`**: Comprehensive tests for all functionality

### Running the Example

To set up and run the example:

```bash
# Install dependencies
uv sync

# Generate 3 example problems (default)
uv run python -m examples.countdown.generate

# Generate 10 problems with custom parameters
uv run python -m examples.countdown.generate --num-samples 10 --num-numbers 4 --max-value 15

# Generate problems and save to file
uv run python -m examples.countdown.generate --num-samples 100 --output data/countdown_problems.json

# Run tests
uv run pytest examples/countdown/tests/ -v
```

## 3. The Exercise

#### Model choice (`y`)
Choose any frontier model. We will supply an Openrouter key with $75 credits for you to use while completing this task.

#### Task Selection (`x`)
Identify a task (`x`) that your chosen model (`y`) currently solves correctly only about **10–90%** of the time.

Examples: sentiment shift detection, specialized code transformation, SVG animation, performing tasks on a given software via computer-use, etc.

**Important:** The task cannot be something too trivial (100% success rate) nor something currently impossible for the model (0% success rate).

#### Synthetic Data Generation
Design a scalable method to generate synthetic data we could train on to improve model (`y`) at task (`x`).

Generate at least **5 concrete example problems** in your submission that illustrate how the generated data is structured and how we could use it for training.

*Definition:* A "problem" is defined as the combination of:
1.  **input** we feed to an LLM (e.g., a task prompt or a task prompt + a state)
2.  **Golden label** (expected output) or a way to verify the LLM completed the task.

**Note:** You'll need to design appropriate prompts for your chosen task, including system prompts, user prompts, and any necessary formatting instructions for the model.

#### Verification
Implement a verification system that can determine whether an LLM's response correctly solves a given problem. This may involve parsing the response, extracting relevant information, and comparing it against the expected output or applying domain-specific validation rules.

#### Evaluation
Implement a script that allows us to run model (`y`) on a given problem for a specified number of times and compute the success rate.

**Important:** When attempting to solve the synthetic problems the LLM cannot access the internet.

## 4. Additional Notes
- To be clear, you are not required to do any training for this exercise, only the data generation for the training.
- Be prepared to walk us through your approach, design choices, implementation etc.
- Although the 10-90% range is the goal, we will accept submissions that are not in that range as long as they are not 0% or 100%.
- The focus is on your AI/ML design thinking as well as coding.

## 5. Deliverables

Please submit the following in a single repository or ZIP:

1.  **`README.md`** with:
    * An overview of your chosen task `x` and why it meets the performance criteria, model used, etc.
    * A description of your synthetic data generation strategy.
    * Instructions on how to install dependencies and run your scripts.
2.  **`generate.py`** (or equivalent):
    * A script to generate your synthetic data.
    * It should output the data in a structured format like JSON or CSV, or Parquet.
3.  **`verify.py`** (or equivalent):
    * A script or function that can verify whether an LLM's response correctly solves a given problem.
    * Should handle parsing LLM outputs and applying domain-specific validation logic.
4.  **`evaluate.py`** (or equivalent):
    * A script that lets us run one of your example problems through the model and verifies the output, with multiple attempts.
    * Should include prompt construction and response parsing logic.
5.  **`problems.{jsonl|parquet|csv}`**
    * A set of 4 or more example generated problems that fall within the 10-90% success rate bucket.

## 6. Timeline & Submission

* **Time Budget:** Please aim for 2-4 hours of your time.
* **Submission:** Please email a link to your repository or a ZIP file to the hiring team.
