"""Script for finding shared object files needed to support .so files in a given directory.
   This is intended to support copying individual libraries into a distroless Docker image."""
import argparse
import sys
from pathlib import Path
from typing import Optional

from colorama import Fore, init
from elftools.construct.macros import ULInt32, ULInt64
from elftools.elf.elffile import ELFFile
from elftools.elf.structs import Struct
from frosch import hook

VERSION = "1.0"


def find_so_files(opts: argparse.Namespace) -> list:
    """Look for so files and write copy commands."""
    so_names = set()
    starting_path = Path(opts.so_path)

    for so_file in starting_path.glob("**/*.so"):
        if opts.verbose:
            print(f"{Fore.GREEN}{so_file}{Fore.RESET}")

        with open(so_file, "rb") as f:
            elf_file = ELFFile(f)
            e_machine = elf_file.header["e_machine"]
            dynamic = elf_file.get_section_by_name(".dynamic")
            dynstr = elf_file.get_section_by_name(".dynstr")

            if e_machine == "EM_X86_64":
                so_struct = Struct("Elf64_Dyn", ULInt64("d_tag"), ULInt64("d_val"))
            elif e_machine == "EM_386":
                so_struct = Struct("Elf32_Dyn", ULInt32("d_tag"), ULInt32("d_val"))
            else:
                raise RuntimeError(f"Unsupported Architecture: {e_machine}")

            ent_size = dynamic["sh_entsize"]
            for k in range(dynamic["sh_size"] // ent_size):
                result = so_struct.parse(dynamic.data()[k * ent_size : (k + 1) * ent_size])
                if result.d_tag == 1:
                    so_name = dynstr.get_string(result.d_val)
                    so_names.add(so_name)
                    if opts.verbose:
                        print(f"{Fore.YELLOW}  {so_name}{Fore.RESET}")

    return sorted(so_names)


def output_copy_script(opts: argparse.Namespace, so_names: Optional[list] = None) -> None:
    """This function locates the so files and generates copy commands."""
    lib_paths = {
        "/lib/x86_64-linux-gnu",
        "/lib64",
    }
    if opts.lib_paths:
        for lpath in opts.lib_paths:
            lib_paths.add(lpath)


def main(args: Optional[list] = None) -> int:
    """This function collects arguments and configuration, and starts the crawling process."""
    # Run frosch's hook.
    hook()
    # Run colorama's init.
    init()

    if args is None:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser(description=f"CopyLibs {VERSION}")
    parser.add_argument(
        "-c",
        "--color",
        action="store_true",
        default=False,
        dest="use_color",
        required=False,
        help="Use colors to highlight output",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        dest="verbose",
        required=False,
        help="Give verbose output",
    )
    parser.add_argument(
        "-p",
        "--path",
        action="store",
        default=None,
        dest="so_path",
        required=True,
        help="Path to find shared-object files",
    )
    parser.add_argument(
        "-f",
        "--copy-from",
        action="store",
        type=str,
        default=None,
        dest="copy_from",
        required=True,
        help="Path from which to copy so files",
    )
    parser.add_argument(
        "-t",
        "--copy-to",
        action="store",
        type=str,
        default=None,
        dest="copy_to",
        required=True,
        help="Path to which to copy so files",
    )
    parser.add_argument(
        "-l",
        "--lib-path",
        action="store",
        type=str,
        nargs="+",
        default=None,
        dest="lib_paths",
        required=False,
        help="Extra library path(s) to search for so files",
    )
    parser.add_argument(
        "-o",
        "--output-file",
        action="store",
        type=str,
        default=None,
        dest="output_file",
        required=False,
        help="File in which to store script output",
    )
    parser.add_argument("rest", nargs=argparse.REMAINDER)
    opts = parser.parse_args(args)

    so_files = find_so_files(opts)
    output_copy_script(opts, so_files)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
