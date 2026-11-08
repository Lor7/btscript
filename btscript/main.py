"""
btscript.main
~~~~~~~~~~~~~

CLI entrypoint and driver for BTScript.
Handles command-line arguments, parsing, semantic validation, code generation,
runtime copying, and editor extension installation.
"""

import argparse
import os
import logging
import shutil
import sys
from pathlib import Path

from .lexer import LexError
from .parser import Parser, ParseError
from .validator import Validator, SemanticError
from .transpilers import Transpiler
from .utils import inspect_tree, render_ascii_tree


def build_argparser() -> argparse.ArgumentParser:
    argparser = argparse.ArgumentParser(
        prog = "btscript",
        description = "BTScript - Behaviour Tree DSL Transpiler"
    )
    argparser.add_argument(
        "inputfile",
        nargs = "?",
        default = None,
        help = "Path to the .tree file to parse"
    )
    argparser.add_argument("-o", "--output", help = "Path to the output file to write")
    argparser.add_argument(
        "-l", "--lang",
        choices = ["python", "lua", "rust", "json", "xml", "mermaid", "ascii"],
        default = None,
        help = "Target language to transpile to (default: file directive or ascii)"
    )
    argparser.add_argument("-v", "--verbose", action = "store_true", help = "Verbose diagnostic printing")
    argparser.add_argument("-Werror", action = "store_true", help = "Treat compiler warnings as fatal errors")
    argparser.add_argument(
        "-m", "--mode",
        choices = ["transpile", "check"],
        default = "transpile",
        help = "Execution mode: transpile to code, or check validation only"
    )
    argparser.add_argument(
        "-c", "--check",
        action = "store_true",
        help = "Check syntax and semantics without writing output files"
    )
    argparser.add_argument(
        "--install-vscode",
        action = "store_true",
        help = "Install the BTScript syntax highlighting extension into VS Code"
    )
    return argparser


def cli(argv = None):
    argparser = build_argparser()
    args = argparser.parse_args(argv)

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level = log_level,
        format = "[%(levelname)s] %(message)s",
    )

    # ------------------------------------------------------------------
    # Optional Tooling: Install VS Code Syntax Extension
    # ------------------------------------------------------------------
    if args.install_vscode:
        home = Path.home()
        target = home / ".vscode" / "extensions" / "vscode-btscript"
        script_dir = Path(__file__).resolve().parent

        candidate_sources = [
            script_dir / "editors" / "vscode-btscript",
            script_dir.parent / "editors" / "vscode-btscript",
        ]
        source_dir = next((s for s in candidate_sources if (s / "package.json").exists()), None)
        if not source_dir:
            logging.error("Could not locate vscode-btscript extension directory.")
            return 1

        target.parent.mkdir(parents = True, exist_ok = True)
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source_dir, target)
        logging.info(f"Successfully installed BTScript extension to {target}")
        logging.info("Open/restart VS Code or reload window to activate syntax highlighting.")
        return 0

    if not args.inputfile:
        argparser.print_help()
        return 1

    if not os.path.exists(args.inputfile):
        raise FileNotFoundError(f"{args.inputfile} not found")

    transpile = (args.mode == "transpile" and not args.check)

    try:
        logging.info(f"Parsing '{args.inputfile}'...")
        parser = Parser(args.inputfile)
        AST, DIRECTIVE = parser.parse_file()
        if args.Werror:
            DIRECTIVE["werror"] = True
        logging.debug(f"Generated AST: {AST}")
        
        trees = AST if isinstance(AST, list) else [AST]
        for t in trees:
            logging.debug(inspect_tree(t))
            logging.info(f"\n{render_ascii_tree(t)}")

        logging.info(f"Validating AST...")
        validator = Validator(AST, DIRECTIVE)
        validator.validate()
        for warn in validator.warnings:
            logging.warning(warn)

        if not transpile:
            logging.info(f"AST validated!")
            return 0

        target_lang = args.lang or DIRECTIVE.get("lang") or "ascii"
        ext = {"python": "py", "lua": "lua", "rust": "rs", "json": "json", "xml": "xml", "mermaid": "mmd", "ascii": "txt"}[target_lang]
        default_output = str(Path(args.inputfile).with_suffix(f".{ext}"))
        outputFileName = args.output or default_output

        # For ASCII visualization: only save to file if explicitly requested via -o
        # or if @lang: ascii was explicitly declared in the file directives.
        save_to_file = True
        if target_lang == "ascii":
            if args.output:
                save_to_file = True
            elif DIRECTIVE.get("lang") == "ascii" and not args.lang:
                save_to_file = True
            else:
                save_to_file = False

        if save_to_file:
            logging.info(f"Transpiling to {target_lang}...")
            transpiler = Transpiler(AST, target_lang, DIRECTIVE)
            with open(outputFileName, "w", encoding = "utf-8") as f:
                f.write(transpiler.transpile())
            logging.info(f"Successfully generated '{outputFileName}'")

            out_dir = os.path.dirname(os.path.abspath(outputFileName))
            script_dir = os.path.dirname(os.path.abspath(__file__))
            runtime_sources = {
                "python": ("runtime.py", os.path.join(script_dir, "runtimes", "python", "runtime.py")),
                "lua": ("runtime.lua", os.path.join(script_dir, "runtimes", "lua", "runtime.lua")),
                "rust": ("runtime.rs", os.path.join(script_dir, "runtimes", "rust", "runtime.rs")),
            }
            if target_lang in runtime_sources:
                runtime_name, src = runtime_sources[target_lang]
                dst = os.path.join(out_dir, runtime_name)
                if os.path.abspath(src) != os.path.abspath(dst):
                    shutil.copy2(src, dst)
                    logging.info(f"Successfully copied the runtime")
        else:
            logging.info("Terminal visualization complete.")

        return 0

    except LexError as e:
        logging.error(f"Lexical Error:{e}")
        sys.exit(1)
    except ParseError as e:
        logging.error(f"Parse Error:{e}")
        sys.exit(1)
    except SemanticError as e:
        logging.error(f"Semantic Error:\n\t{e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error:\n\t{e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    cli()
