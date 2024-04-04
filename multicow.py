#!/usr/bin/python3

import argparse
from enum import Enum
import os
import pathlib
import sys
import textwrap

def visible_length(s):
    result = 0
    pos = 0
    while pos < len(s):
        escstart = s.find("\x1b[", pos)
        if escstart < 0:
            return result + len(s) - pos
        result += escstart - pos
        escend = s.find("m", escstart)
        if escend < 0:
            return result
        pos = escend + 1

def with_colour_reset(s):
    if s.find("\x1b[") < 0:
        return s
    return s + "\x1b[37m"

def coloured_remove_suffix(s, n):
    to_remove = n
    pos = len(s)
    while (to_remove > 0) and (pos > 0):
        escstart = s.rfind("\x1b[", 0, pos)
        if escstart < 0:
            break
        escend = s.find("m", escstart, pos)
        if escend > 0:
            visible = pos - escend - 1
            if visible > to_remove:
                pos = escend + 1 + (visible - to_remove)
                to_remove = 0
            else:
                to_remove -= visible
                pos = escstart
        else:
            pos = escstart
    return s[:pos - min(pos, to_remove)]

class ColouredWrapper(textwrap.TextWrapper):
    def _wrap_chunks(self, chunks):
        """_wrap_chunks(chunks : [string]) -> [string]

        Wrap a sequence of text chunks and return a list of lines of
        length 'self.width' or less.  (If 'break_long_words' is false,
        some lines may be longer than this.)  Chunks correspond roughly
        to words and the whitespace between them: each chunk is
        indivisible (modulo 'break_long_words'), but a line break can
        come between any two chunks.  Chunks should not have internal
        whitespace; ie. a chunk is either all whitespace or a "word".
        Whitespace chunks will be removed from the beginning and end of
        lines, but apart from that whitespace is preserved.
        """
        lines = []
        if self.width <= 0:
            raise ValueError("invalid width %r (must be > 0)" % self.width)
        if self.max_lines is not None:
            if self.max_lines > 1:
                indent = self.subsequent_indent
            else:
                indent = self.initial_indent
            if len(indent) + len(self.placeholder.lstrip()) > self.width:
                raise ValueError("placeholder too large for max width")

        # Arrange in reverse order so items can be efficiently popped
        # from a stack of chucks.
        chunks.reverse()

        while chunks:

            # Start the list of chunks that will make up the current line.
            # cur_len is just the length of all the chunks in cur_line.
            cur_line = []
            cur_len = 0

            # Figure out which static string will prefix this line.
            if lines:
                indent = self.subsequent_indent
            else:
                indent = self.initial_indent

            # Maximum width for this line.
            width = self.width - len(indent)

            # First chunk on line is whitespace -- drop it, unless this
            # is the very beginning of the text (ie. no lines started yet).
            if self.drop_whitespace and chunks[-1].strip() == '' and lines:
                del chunks[-1]

            while chunks:
                l = visible_length(chunks[-1])

                # Can at least squeeze this chunk onto the current line.
                if cur_len + l <= width:
                    cur_line.append(chunks.pop())
                    cur_len += l

                # Nope, this line is full.
                else:
                    break

            # The current line is full, and the next chunk is too big to
            # fit on *any* line (not just this one).
            if chunks and visible_length(chunks[-1]) > width:
                self._handle_long_word(chunks, cur_line, cur_len, width)
                cur_len = sum(map(visible_length, cur_line))

            # If the last chunk on this line is all whitespace, drop it.
            if self.drop_whitespace and cur_line and cur_line[-1].strip() == '':
                cur_len -= visible_length(cur_line[-1])
                del cur_line[-1]

            if cur_line:
                if (self.max_lines is None or
                    len(lines) + 1 < self.max_lines or
                    (not chunks or
                     self.drop_whitespace and
                     len(chunks) == 1 and
                     not chunks[0].strip()) and cur_len <= width):
                    # Convert current line back to a string and store it in
                    # list of all lines (return value).
                    lines.append(indent + ''.join(cur_line))
                else:
                    while cur_line:
                        if (cur_line[-1].strip() and
                            cur_len + len(self.placeholder) <= width):
                            cur_line.append(self.placeholder)
                            lines.append(indent + ''.join(cur_line))
                            break
                        cur_len -= visible_length(cur_line[-1])
                        del cur_line[-1]
                    else:
                        if lines:
                            prev_line = lines[-1].rstrip()
                            if (visible_length(prev_line) + len(self.placeholder) <=
                                    self.width):
                                lines[-1] = prev_line + self.placeholder
                                break
                        lines.append(indent + self.placeholder.lstrip())
                    break

        return lines

cowpath = list(s for s in (os.getenv("COWPATH") or "").split(":") if s)
cowpath += ["/usr/share/cowsay/cows"]

def listcows():
    for i in range(len(cowpath)):
        print("Cow files in", cowpath[i])
        cows = []
        try:
            for filename in os.listdir(cowpath[i]):
                p = pathlib.Path(filename)
                if p.suffix == ".cow":
                    cows += [p.stem]
        except:
            cows = []
        cows.sort()
        print(" ".join(cows))
        if i < len(cowpath) - 1:
            print()

def findcow(cowfile):
    for path in cowpath:
        trypath = os.path.join(path, cowfile + ".cow")
        if os.path.isfile(trypath):
            return trypath
    return None

class Cow:
    def __init__(self):
        self.preamble_code = []
        self.content = []

def loadcow(path):
    try:
        lines = open(path).read().split("\n")
    except Exception as e:
        print(e)
        return None

    cow = Cow()
    header = True
    for line in lines:
        if header:
            if line.startswith("#"):
                pass
            elif line.startswith("$the_cow=") or line.startswith("$the_cow ="):
                header = False
            else:
                cow.preamble_code += [line]
        else:
            if not line or (line == "EOC"):
                break
            else:
                cow.content += [line]

    return cow

# Mutable string with an extra flag
class StringArgument:
    def __init__(self, value, default):
        self._value = list(c for c in value)
        self._default = default

    def pop(self):
        return self._value.pop()

    def __add__(self, other):
        return StringArgument(self._value + other._value, self._default and other._default)

    def __iadd__(self, other):
        self._value += other._value
        self._default = self._default and other._default

    def __str__(self):
        return "".join(self._value)

    def default(self):
        return self._default

    def assign(self, other):
        self._value = other._value
        self._default = other._default

# Perl-like function, for exec()
def chop(s):
    if not s:
        return s
    return s.pop()

def mutable(s):
    return StringArgument(s, False)

def mutable_default(s):
    return StringArgument(s, True)

def isset(s):
    return not s.default()

class QuoteState(Enum):
    OutsideQuote = 1
    InsideQuote = 2
    InsideQuoteVar = 3

# Replace perl string literals with mutable(f"...") for exec
def preprocess_quotes(s):
    res = ""
    state = QuoteState.OutsideQuote
    for c in s:
        if state == QuoteState.OutsideQuote:
            if c == "\"":
                res += "mutable(f\""
                state = QuoteState.InsideQuote
            else:
                res += c
        elif state == QuoteState.InsideQuote:
            if c == "\"":
                res += "\")"
                state = QuoteState.OutsideQuote
            elif c == "$":
                res += "{"
                state = QuoteState.InsideQuoteVar
            else:
                res += c
        elif state == QuoteState.InsideQuoteVar:
            if c == "\"":
                res += "}\")"
                state = QuoteState.OutsideQuote
            elif c == " ":
                res += "} "
                state = QuoteState.InsideQuote
            else:
                res += c
    return res

# Convert the subset of pearl used by standard cow files into python for exec()
def preprocess_preamble(s):
    s = s.replace(".=", "+=")
    s = preprocess_quotes(s)
    s = s.replace("$", "")

    if s.startswith("eyes=") or s.startswith("eyes =") or s.startswith("tongue=") or s.startswith("tongue ="):
        eq = s.find("=")
        end = s.find("unless")
        if end < 0:
            end = s.find(";")
        if end < 0:
            end = len(s)
        s = f"{s[:eq]}.assign({s[eq+1:end]}){s[end:]}"

    unless = s.find("unless");
    if unless >= 0:
        end = s.find(";")
        if end < 0:
            end = len(s)
        s = f"if not isset({s[unless+6:end]}):\n  {s[:unless]}"
    return s

# Thought line character
def get_thought(args):
    return "o" if args.think else "\\"

# One bubble, including border, excluding thought line
def make_bubble(content, args, height_remaining):
    output = []
    if height_remaining is not None: 
        # Need 2 lines for the bubble and at least 1 more for the message
        if height_remaining < 3:
            return output
        height_remaining -= 2
    if content.endswith("\n"):
        content = content[:-1]
    lines = []
    for line in content.split("\n"):
        lines += ColouredWrapper(args.width).wrap(line) if args.width else [line]
    lengths = list(map(lambda s: visible_length(s), lines))

    # Truncate message at the end if too many lines
    if height_remaining is not None and (len(lines) > height_remaining):
        lines = lines[:height_remaining]
        if args.width and (lengths[-1] + 3 > args.width):
            lines[-1] = coloured_remove_suffix(lines[-1], 3) + "..."
        else:
            lines[-1] += "..."

    width = max(lengths) if lines else 0
    lines = list(map(lambda s: with_colour_reset(s), lines))

    if args.think:
        left = "("
        topleft = "("
        midleft = "("
        botleft = "("
        right = ")"
        topright = ")"
        midright = ")"
        botright = ")"
    else:
        left = "<"
        topleft = "/"
        midleft = "|"
        botleft = "\\"
        right = ">"
        topright = "\\"
        midright = "|"
        botright = "/"

    output += [" " + "_"*(width+2)]
    if len(lines) <= 1:
        output += [left + " " + (lines[0] if lines else "") + " " + right]
    else:
        output += [topleft + " " + lines[0] + " "*(width - lengths[0]) + " " + topright]
        for i in range(1, len(lines)-1):
            output += [midleft + " " + lines[i] + " "*(width - lengths[i]) + " " + midright]
        output += [botleft + " " + lines[-1] + " "*(width - lengths[-1]) + " " + botright]
    output += [" " + "-"*(width+2)]
    return output

# All bubbles and thought lines between them
def print_bubbles(content, args, top_thought):
    output = []
    height_remaining = args.height
    is_bottom = True
    if args.multibubble:
        for line in reversed(content):
            if not line:
                continue

            if height_remaining and not is_bottom:
                height_remaining -= 1 # extra thought line between bubbles
            bubble = make_bubble(line, args, height_remaining)
            if not bubble:
                break
            if height_remaining:
                height_remaining -= len(bubble)
            if not is_bottom:
                output = [" " * top_thought + get_thought(args)] + output
            output = bubble + output
            is_bottom = False
    else:
        bubble = make_bubble(" ".join(content), args, args.height)
        output = bubble

    if args.height and args.bottom:
        for i in range(args.height - len(output)):
            print()
    for line in output:
        print(line)
            

# Full output
def cowsay(cow, content, args):
    if isinstance(content, str):
        content = [content]
    # Set default flag so that perl preamble from small.cow will replace eyes
    eyes = mutable(args.eyes) if args.eyes is not None else mutable_default("oo")
    tongue = mutable(args.tongue) if args.tongue is not None else mutable_default("  ")

    for line in cow.preamble_code:
        exec(preprocess_preamble(line))

    # thought line between bubbles 1 to the left of where cow's thought line ends
    top_thought = cow.content[0].find("$thoughts") if cow.content else -1
    if top_thought > 1:
        top_thought -= 1
    if top_thought < 0:
        top_thought = 3

    print_bubbles(content, args, top_thought)

    for line in cow.content:
        out = line.replace("$thoughts", get_thought(args))
        out = out.replace("\\\\", "\\")
        out = out.replace("\\@", "@")
        out = out.replace("\\$", "$")
        out = out.replace("$eyes", str(eyes))
        out = out.replace("$tongue", str(tongue))
        sys.stdout.write(out + "\n")

def make_argparser():
    argparser = argparse.ArgumentParser(
        prog="multicow",
        description="cowsay with multiple buubles support")
    argparser.add_argument("-l", "--list", dest="listcows", action="store_true",
        help="lists the defined cows on the current COWPATH")
    argparser.add_argument("-f", "--file", dest="cowfile",
        help="specifies a particular cow picture file (cowfile) to use")
    argparser.add_argument("-m", "--multi", dest="multibubble", action="store_true",
        help="put multiple message argument into multiple bubbles")
    argparser.add_argument("-e", "--eyes", dest="eyes",
        help="selects the appearance of the cow’s eyes (default oo), should be two characters")
    argparser.add_argument("-T", "--tongue", dest="tongue",
        help="selects the appearance of the cow’s tongue, should be two characters")
    argparser.add_argument("-W", "--width", dest="width", type=int,
        help="wrap words in the message to given width")
    argparser.add_argument("-H", "--height", dest="height", type=int,
        help="truncate message (including bubbles, excluding the cow) to given number of lines; " +
        "in multi-bubble mode, top-most bubbles are omitted if they do not fit")
    argparser.add_argument("--think", dest="think", action="store_true",
        help="use cowthink bubbles")
    argparser.add_argument("--bottom", dest="bottom", action="store_true",
        help="in conjunction with -H, add empty lines at the top up to exactly the height limit")
    argparser.add_argument("content", nargs="*",
        help="message to show, read from standard input if none is given")
    return argparser

def run(args):
    if args.listcows:
        listcows()
        exit(0)
    cowfile = args.cowfile or "default"

    filepath = findcow(cowfile)
    if not filepath:
        print(f"Could not find cowfile for '{cowfile}'")
        exit(1)

    cow = loadcow(filepath)
    if not cow:
        exit(1)

    content = args.content if args.content else sys.stdin.read()
    cowsay(cow, content, args)

if __name__ == "__main__":
    run(make_argparser().parse_args())
