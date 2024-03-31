#!/usr/bin/python3

import argparse
from enum import Enum
import os
import pathlib
import sys
import textwrap

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
        lines += textwrap.wrap(line, width=args.width) if args.width else [line]

    # Truncate message at the end if too many lines
    if height_remaining is not None and (len(lines) > height_remaining):
        lines = lines[:height_remaining]
        if args.width and (len(lines[-1]) + 3 > args.width):
            lines[-1] = lines[-1][:args.width-3] + "..."
        else:
            lines[-1] += "..."

    width = max(len(s) for s in lines) if lines else 0

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
        output += [topleft + " " + lines[0] + " "*(width - len(lines[0])) + " " + topright]
        for i in range(1, len(lines)-1):
            output += [midleft + " " + lines[i] + " "*(width - len(lines[i])) + " " + midright]
        output += [botleft + " " + lines[-1] + " "*(width - len(lines[-1])) + " " + botright]
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
