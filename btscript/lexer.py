"""
btscript.lexer
~~~~~~~~~~~~~~

Lexical scanner for BTScript.
Converts raw DSL source code into a stream of Token instances with precise
line and column positions for diagnostic reporting.
"""

from typing import List
from .tokens import Token, TokenType


class Lexer:
    """Stream-based lexer tracking exact file line and column coordinates."""

    def __init__(self, source: str):
        self.source = source
        self.tokens: List[Token] = []

    def tokenize(self) -> List[Token]:
        self.tokens = []
        L = len(self.source)
        cursor = 0
        line = 1
        column = 1

        while cursor < L:
            char = self.source[cursor]

            # ----------------------------------------------------------
            # Whitespace & Newlines
            # ----------------------------------------------------------
            if char in {' ', '\t', '\r'}:
                cursor += 1
                column += 1

            elif char == '\n':
                cursor += 1
                line += 1
                column = 1

            # ----------------------------------------------------------
            # Comments: '#' or '//' until end-of-line
            # ----------------------------------------------------------
            elif char == '#':
                while cursor < L and self.source[cursor] != '\n':
                    cursor += 1
                    column += 1

            elif char == '/' and cursor + 1 < L and self.source[cursor + 1] == '/':
                while cursor < L and self.source[cursor] != '\n':
                    cursor += 1
                    column += 1

            # ----------------------------------------------------------
            # Multi-character Operators: '->'
            # ----------------------------------------------------------
            elif char == '-' and cursor + 1 < L and self.source[cursor + 1] == '>':
                self.tokens.append(Token(type = TokenType.ARROW, value = "->", line = line, column = column))
                cursor += 2
                column += 2

            # ----------------------------------------------------------
            # Single-character Symbols and Delimiters
            # ----------------------------------------------------------
            elif char in ['{', '}', '(', ')', '[', ']', ':', ',', '!', '-', '@', '|', '+', '/', '\\', '=', '$']:
                self.tokens.append(Token(type = char, value = char, line = line, column = column))
                cursor += 1
                column += 1

            # ----------------------------------------------------------
            # Quoted String Literals
            # ----------------------------------------------------------
            elif char == '"':
                start_col = column
                cursor += 1
                column += 1
                start = cursor

                while cursor < L and self.source[cursor] != '"':
                    if self.source[cursor] == '\n':
                        line += 1
                        column = 1
                    cursor += 1
                    column += 1

                if cursor >= L:
                    raise Exception(f"Unterminated string literal at line {line}")

                value = self.source[start:cursor]
                cursor += 1
                column += 1
                self.tokens.append(Token(type = TokenType.STRING, value = value, line = line, column = start_col))

            # ----------------------------------------------------------
            # Numeric Literals (Integers & Floats)
            # ----------------------------------------------------------
            elif char.isdigit():
                start_col = column
                start = cursor
                while cursor < L and (self.source[cursor].isdigit() or self.source[cursor] == "."):
                    cursor += 1
                    column += 1
                self.tokens.append(Token(type = TokenType.NUMBER, value = self.source[start:cursor], line = line, column = start_col))

            # ----------------------------------------------------------
            # Keywords, Booleans, None, and Identifiers
            # ----------------------------------------------------------
            elif char.isalpha() or char == '_':
                start_col = column
                start = cursor
                while cursor < L and (self.source[cursor].isalnum() or self.source[cursor] == "_"):
                    cursor += 1
                    column += 1
                word = self.source[start:cursor]

                if word in [
                    "tree", "subtree", "blackboard",
                    "sequence", "selector", "parallel", "action", "condition", "decorator",
                    "enable", "disable", "import", "stateful", "stateless"
                ]:
                    self.tokens.append(Token(type = TokenType.KEYWORD, value = word, line = line, column = start_col))
                elif word in ["true", "false"]:
                    self.tokens.append(Token(type = TokenType.BOOLEAN, value = word, line = line, column = start_col))
                elif word in ["none", "null", "nill", "undefined", "default"]:
                    self.tokens.append(Token(type = TokenType.NONE, value = word, line = line, column = start_col))
                else:
                    self.tokens.append(Token(type = TokenType.IDENT, value = word, line = line, column = start_col))

            else:
                raise Exception(f"Unknown character '{char}' at line: {line}")

        # Stream terminator
        self.tokens.append(Token(type = TokenType.EOF, value = "", line = line, column = column))
        return self.tokens