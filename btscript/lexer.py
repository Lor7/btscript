"""
btscript.lexer
~~~~~~~~~~~~~~

Lexical scanner for BTScript.
Converts raw DSL source code into a stream of Token instances with precise
line and column positions for diagnostic reporting.
"""

from typing import List
from .tokens import Token, TokenType


class LexError(Exception):
    """Raised when lexical scanning encounters invalid or unterminated tokens."""
    def __init__(self, message: str, line: int = 1, column: int = 1, file_path: str = ""):
        self.raw_message = message
        self.line = line
        self.column = column
        self.file_path = file_path
        super().__init__(message)


class Lexer:
    """Stream-based lexer tracking exact file line and column coordinates."""

    def __init__(self, source: str, file_path: str = ""):
        self.source = source
        self.file_path = file_path
        self.tokens: List[Token] = []

    def format_error(self, message: str, line: int, column: int, length: int = 1) -> str:
        lines = self.source.splitlines()
        code_line = lines[line - 1] if 1 <= line <= len(lines) else ""
        gutter = f"{line:4d} | "
        caret_indent = " " * (len(gutter) + column - 1)
        caret = "^" * max(1, length)
        loc = f"{self.file_path}:{line}:{column}" if self.file_path else f"line {line}:{column}"
        errormsg = f"\n\033[1;31mLexical Error\033[0m in {loc}:\n"
        errormsg += f"{gutter}{code_line}\n"
        errormsg += f"{caret_indent}\033[1;31m{caret}\033[0m\n"
        errormsg += f"\033[1m{message}\033[0m\n"
        return errormsg

    def error(self, message: str, line: int, column: int, length: int = 1):
        raise LexError(self.format_error(message, line, column, length), line = line, column = column, file_path = self.file_path)

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
                start_line = line
                cursor += 1
                column += 1
                start = cursor

                while cursor < L and self.source[cursor] != '"':
                    if self.source[cursor] == '\n':
                        line += 1
                        column = 1
                    else:
                        column += 1
                    cursor += 1

                if cursor >= L:
                    self.error("Unterminated string literal", line = start_line, column = start_col, length = max(1, cursor - start + 1))

                value = self.source[start:cursor]
                cursor += 1
                column += 1
                self.tokens.append(Token(type = TokenType.STRING, value = value, line = start_line, column = start_col))

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
                self.error(f"Unknown character '{char}'", line = line, column = column, length = 1)

        # Stream terminator
        self.tokens.append(Token(type = TokenType.EOF, value = "", line = line, column = column))
        return self.tokens