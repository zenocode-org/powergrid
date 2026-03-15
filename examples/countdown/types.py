from typing import List
from pydantic import BaseModel, Field

class CountdownProblem(BaseModel):
    """Defines the input for the Countdown numbers game."""
    numbers: List[int] = Field(..., description="A list of numbers to be used in the expression.")
    target: int = Field(..., description="The target number to reach.")
