# Copyright (c) Meta Platforms, Inc. and affiliates
from abc import ABC, abstractmethod
import ast
from typing import Optional, Dict, Any

class BaseEvaluator(ABC):
    
    def __init__(self, name: str, description: str):
        self._score: float = 0.0
        self._name = name
        self._description = description
    
    @property
    def score(self) -> float:
        return self._score
    
    @score.setter
    def score(self, value: float) -> None:
        if not 0 <= value <= 1:
            raise ValueError("Score must be between 0 and 1")
        self._score = value
    
    @abstractmethod
    def evaluate(self, node: ast.AST) -> float:
        pass