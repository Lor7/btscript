"""
btscript.tokens
~~~~~~~~~~~~~~~

Token definitions and stream models for BTScript.
Provides lexical token types and token position tracking (file, line, column).
"""

import enum
import re
from typing import Optional, Union


class TokenType(str, enum.Enum):
    """Enumeration of all lexical token types recognized by BTScript."""

    # Literals and Identifiers
    KEYWORD = "KEYWORD"
    IDENT = "IDENT"
    NUMBER = "NUMBER"
    STRING = "STRING"
    BOOLEAN = "BOOLEAN"
    NONE = "NONE"

    # Symbols and Operators
    DOLLAR = "$"
    AT = "@"
    ARROW = "->"
    COLON = ":"
    COMMA = ","
    EQUALS = "="
    PIPE = "|"
    EXCLAMATION = "!"
    MINUS = "-"
    PLUS = "+"
    SLASH = "/"
    BACKSLASH = "\\"

    # Delimiters
    LBRACE = "{"
    RBRACE = "}"
    LPAREN = "("
    RPAREN = ")"
    LBRACKET = "["
    RBRACKET = "]"

    # Stream Termination
    EOF = "EOF"


class Token:
    """Represents a single lexical token with source position tracking."""

    def __init__(self, type: TokenType | str, value: str, line: int, column: int = 1):
        if isinstance(type, str) and not isinstance(type, TokenType):
            try:
                self.type = TokenType(type)
            except ValueError:
                self.type = TokenType[type]
        else:
            self.type = type

        self.value = value
        self.line = line
        self.column = column
    
    @property
    def length(self) -> int:
        """Visual length of the token string for diagnostic caret spans."""
        return len(self.value) if self.value else 1

    def __repr__(self) -> str:
        type_val = self.type.value if isinstance(self.type, TokenType) else self.type
        return f"Token({type_val}, '{self.value}', line={self.line}, col={self.column})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Token):
            return self.type == other.type and self.value == other.value and self.line == other.line
        return False