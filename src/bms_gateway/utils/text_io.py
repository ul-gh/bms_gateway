"""Text output helpers."""

import sys
from pathlib import Path
from types import TracebackType
from typing import Self, TextIO, override


class FileAndStdout(TextIO):
    """TextIO Object, writing simultaneously to specified file and to stdout."""

    _terminal: TextIO
    _file: TextIO

    def __init__(self, output_file: TextIO) -> None:
        """Init a FileAndStdout object."""
        self._terminal = sys.stdout
        self._file = output_file

    @override
    def write(self, message: str) -> int:
        """Write text string to terminal and output file."""
        rv = self._terminal.write(message)
        _ = self._file.write(message)
        self.flush()
        return rv

    @override
    def flush(self) -> None:
        """Flush terminal and output file cache."""
        _ = self._terminal.flush()
        self._file.flush()


class TextLogWriter:
    """Text logger for simultaneous file and screen output.

    Use as a context-manager.
    """

    _file_path: str | Path | None
    _terminal: TextIO | None
    text_prefix: str
    _flush_immediately: bool
    _file: TextIO | None

    def __init__(
        self,
        file_path: str | Path | None = None,
        *,
        terminal: TextIO = sys.stdout,
        text_prefix: str = "",
        flush_immediately: bool = False,
    ) -> None:
        """Initialize a TxtLogWriter instance."""
        self._file_path = file_path
        self._terminal = terminal
        self.text_prefix = text_prefix
        self._flush_immediately = flush_immediately
        self._file = None

    def add(self, msg: object, end: str = "\n") -> None:
        """Add text representation of input object to the log output.

        By default, this appends a newline character, which will also trigger
        flushing the terminal and file output buffers.
        """
        msg_text = f"{self.text_prefix}{msg}{end}"
        if self._file is not None:
            _ = self._file.write(msg_text)
            if self._flush_immediately:
                self._file.flush()
        if self._terminal is not None:
            _ = self._terminal.write(msg_text)
            if self._flush_immediately:
                self._terminal.flush()

    def set_output_file(self, file_obj: TextIO) -> None:
        """Set file to write to, in addition to terminal."""
        self._file = file_obj

    def __enter__(self: Self) -> Self:
        """Enter context manager context."""
        if self._file_path is not None:
            # Open or create new file for appending text, using line-buffering.
            self._file = Path(self._file_path).open(mode="at", buffering=1)
        return self

    def __exit__(
        self: Self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> bool:
        """Exit context manager context."""
        if self._file is not None:
            self._file.close()
        return True


class TextScreen():
    """Output arbitrary number of lines of text, while re-using the screen
    area previously written to.

    For this, text is put in a buffer using the put() method, and output is
    written to the screen all at once when the refresh() method is called.

    Ulrich Lukas 2026-08-07
    """

    def __init__(self, clear_extra_lines: int = 0):
        self.clear_extra_lines: int = clear_extra_lines
        self._lines_in_buffer: int = 0
        self._lines_printed: int = 0
        self._text_buffer: str = ""

    def put(self, text: str):
        """Put lines of text in buffer, but do not output anything.

        Write output all at once, clearing the previous screen contents,
        when refresh() is later called.
        """
        self._lines_in_buffer += 1 + text.count("\n")
        self._text_buffer += text.replace("\n", "\x1B[0K\n") + "\x1B[0K\n"

    def refresh(self):
        """Write output from buffer to screen, clearing previous content."""
        clear_code = f"\x1B[{self.clear_extra_lines + self._lines_printed}F" if self._lines_printed else ""
        print(f"{clear_code}{self._text_buffer}", end="")
        self._lines_printed = self._lines_in_buffer
        self._text_buffer = ""
        self._lines_in_buffer = 0