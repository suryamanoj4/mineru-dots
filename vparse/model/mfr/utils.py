import re

LEFT_PATTERN = re.compile(r'(\\left)(\S*)')
RIGHT_PATTERN = re.compile(r'(\\right)(\S*)')
LEFT_COUNT_PATTERN = re.compile(r'\\left(?![a-zA-Z])')
RIGHT_COUNT_PATTERN = re.compile(r'\\right(?![a-zA-Z])')
LEFT_RIGHT_REMOVE_PATTERN = re.compile(r'\\left\.?|\\right\.?')

def fix_latex_left_right(s, fix_delimiter=True):
    """
    Fix \\left and \\right commands in LaTeX.
    1. Ensure they are followed by a valid delimiter.
    2. Balance the number of \\left and \\right commands.
    """
    # Whitelisted delimiters
    valid_delims_list = [r'(', r')', r'[', r']', r'{', r'}', r'/', r'|',
                         r'\{', r'\}', r'\lceil', r'\rceil', r'\lfloor',
                         r'\rfloor', r'\backslash', r'\uparrow', r'\downarrow',
                         r'\Uparrow', r'\Downarrow', r'\|', r'\.']

    # Add a dot for \left missing a valid delimiter
    def fix_delim(match, is_left=True):
        cmd = match.group(1)  # \left or \right
        rest = match.group(2) if len(match.groups()) > 1 else ""
        if not rest or rest not in valid_delims_list:
            return cmd + "."
        return match.group(0)

    # Use precise patterns to match \left and \right commands.
    # Ensure they are independent commands, not parts of others.
    if fix_delimiter:
        s = LEFT_PATTERN.sub(lambda m: fix_delim(m, True), s)
        s = RIGHT_PATTERN.sub(lambda m: fix_delim(m, False), s)

    # Precisely count \left and \right
    left_count = len(LEFT_COUNT_PATTERN.findall(s))  # Does not match \lefteqn etc.
    right_count = len(RIGHT_COUNT_PATTERN.findall(s))  # Does not match \rightarrow etc.

    if left_count == right_count:
        # If counts are equal, check if they are in the same groups
        return fix_left_right_pairs(s)
    else:
        # If counts are unequal, remove all \left and \right
        return LEFT_RIGHT_REMOVE_PATTERN.sub('', s)


def fix_left_right_pairs(latex_formula):
    """
    Detect and fix cases where \\left and \\right are not in the same curly brace group.

    Args:
        latex_formula (str): Input LaTeX formula.

    Returns:
        str: Fixed LaTeX formula.
    """
    # Used to track curly brace nesting levels
    brace_stack = []
    # Used to store \left information: (position, depth, delimiter)
    left_stack = []
    # Store \right information to be adjusted: (start_pos, end_pos, target_pos)
    adjustments = []

    i = 0
    while i < len(latex_formula):
        # Check if character is escaped
        if i > 0 and latex_formula[i - 1] == '\\':
            backslash_count = 0
            j = i - 1
            while j >= 0 and latex_formula[j] == '\\':
                backslash_count += 1
                j -= 1

            if backslash_count % 2 == 1:
                i += 1
                continue

        # Detect \left command
        if i + 5 < len(latex_formula) and latex_formula[i:i + 5] == "\\left" and i + 5 < len(latex_formula):
            delimiter = latex_formula[i + 5]
            left_stack.append((i, len(brace_stack), delimiter))
            i += 6  # Skip \left and delimiter
            continue

        # Detect \right command
        elif i + 6 < len(latex_formula) and latex_formula[i:i + 6] == "\\right" and i + 6 < len(latex_formula):
            delimiter = latex_formula[i + 6]

            if left_stack:
                left_pos, left_depth, left_delim = left_stack.pop()

                # If \left and \right are not at the same depth
                if left_depth != len(brace_stack):
                    # Find the end position of the curly brace group containing \left
                    target_pos = find_group_end(latex_formula, left_pos, left_depth)
                    if target_pos != -1:
                        # Record the \right to be moved
                        adjustments.append((i, i + 7, target_pos))

            i += 7  # Skip \right and delimiter
            continue

        # Handle curly braces
        if latex_formula[i] == '{':
            brace_stack.append(i)
        elif latex_formula[i] == '}':
            if brace_stack:
                brace_stack.pop()

        i += 1

    # Apply adjustments from back to front to avoid index shifts
    if not adjustments:
        return latex_formula

    result = list(latex_formula)
    adjustments.sort(reverse=True, key=lambda x: x[0])

    for start, end, target in adjustments:
        # Extract \right part
        right_part = result[start:end]
        # Remove from original position
        del result[start:end]
        # Insert at target position
        result.insert(target, ''.join(right_part))

    return ''.join(result)


def find_group_end(text, pos, depth):
    """Find the end position of a curly brace group at a specific depth."""
    current_depth = depth
    i = pos

    while i < len(text):
        if text[i] == '{' and (i == 0 or not is_escaped(text, i)):
            current_depth += 1
        elif text[i] == '}' and (i == 0 or not is_escaped(text, i)):
            current_depth -= 1
            if current_depth < depth:
                return i
        i += 1

    return -1  # End position not found


def is_escaped(text, pos):
    """Check if a character is escaped."""
    backslash_count = 0
    j = pos - 1
    while j >= 0 and text[j] == '\\':
        backslash_count += 1
        j -= 1

    return backslash_count % 2 == 1


def fix_unbalanced_braces(latex_formula):
    """
    Detect unbalanced curly braces in a LaTeX formula and remove unmatched ones.

    Args:
        latex_formula (str): Input LaTeX formula.

    Returns:
        str: LaTeX formula after removing unmatched braces.
    """
    stack = []  # Store indices of left braces
    unmatched = set()  # Store indices of unmatched braces
    i = 0

    while i < len(latex_formula):
        # Check if it's an escaped brace
        if latex_formula[i] in ['{', '}']:
            backslash_count = 0
            j = i - 1
            while j >= 0 and latex_formula[j] == '\\':
                backslash_count += 1
                j -= 1

            # If preceded by an odd number of backslashes, it is escaped
            if backslash_count % 2 == 1:
                i += 1
                continue

            # Otherwise, participate in matching
            if latex_formula[i] == '{':
                stack.append(i)
            else:  # latex_formula[i] == '}'
                if stack:  # Has corresponding left brace
                    stack.pop()
                else:  # No corresponding left brace
                    unmatched.add(i)

        i += 1

    # All unmatched left braces
    unmatched.update(stack)

    # Build new string, removing unmatched braces
    return ''.join(char for i, char in enumerate(latex_formula) if i not in unmatched)


def process_latex(input_string):
    """
    Handle backslashes in LaTeX formulas:
    1. If \ is followed by special characters (#$%&~_^\\{}) or a space, keep as is.
    2. If \ is followed by two lowercase letters, keep as is.
    3. Otherwise, add a space after \.

    Args:
        input_string (str): Input LaTeX formula.

    Returns:
        str: Processed LaTeX formula.
    """

    def replace_func(match):
        # Get character after \
        next_char = match.group(1)

        # Keep special characters or space unchanged
        if next_char in "#$%&~_^|\\{} \t\n\r\v\f":
            return match.group(0)

        # If it's a letter, check the next character
        if 'a' <= next_char <= 'z' or 'A' <= next_char <= 'Z':
            pos = match.start() + 2  # Position after \x
            if pos < len(input_string) and ('a' <= input_string[pos] <= 'z' or 'A' <= input_string[pos] <= 'Z'):
                # Next character is also a letter, keep as is
                return match.group(0)

        # Otherwise, add a space after \
        return '\\' + ' ' + next_char

    # Match \ followed by a single character
    pattern = r'\\(.)'

    return re.sub(pattern, replace_func, input_string)

# Common mathematical environments available in KaTeX/MathJax
ENV_TYPES = ['array', 'matrix', 'pmatrix', 'bmatrix', 'vmatrix',
             'Bmatrix', 'Vmatrix', 'cases', 'aligned', 'gathered', 'align', 'align*']
ENV_BEGIN_PATTERNS = {env: re.compile(r'\\begin\{' + env + r'\}') for env in ENV_TYPES}
ENV_END_PATTERNS = {env: re.compile(r'\\end\{' + env + r'\}') for env in ENV_TYPES}
ENV_FORMAT_PATTERNS = {env: re.compile(r'\\begin\{' + env + r'\}\{([^}]*)\}') for env in ENV_TYPES}

def fix_latex_environments(s):
    """
    Detect and fix mismatched \\begin and \\end tags for LaTeX environments (e.g., array).
    1. Prepend missing \\begin tags.
    2. Append missing \\end tags.
    """
    for env in ENV_TYPES:
        begin_count = len(ENV_BEGIN_PATTERNS[env].findall(s))
        end_count = len(ENV_END_PATTERNS[env].findall(s))

        if begin_count != end_count:
            if end_count > begin_count:
                format_match = ENV_FORMAT_PATTERNS[env].search(s)
                default_format = '{c}' if env == 'array' else ''
                format_str = '{' + format_match.group(1) + '}' if format_match else default_format

                missing_count = end_count - begin_count
                begin_command = '\\begin{' + env + '}' + format_str + ' '
                s = begin_command * missing_count + s
            else:
                missing_count = begin_count - end_count
                s = s + (' \\end{' + env + '}') * missing_count

    return s


REPLACEMENTS_PATTERNS = {
    re.compile(r'\\underbar'): r'\\underline',
    re.compile(r'\\Bar'): r'\\hat',
    re.compile(r'\\Hat'): r'\\hat',
    re.compile(r'\\Tilde'): r'\\tilde',
    re.compile(r'\\slash'): r'/',
    re.compile(r'\\textperthousand'): r'‰',
    re.compile(r'\\sun'): r'☉',
    re.compile(r'\\textunderscore'): r'\\_',
    re.compile(r'\\fint'): r'⨏',
    re.compile(r'\\up '): r'\\ ',
    re.compile(r'\\vline = '): r'\\models ',
    re.compile(r'\\vDash '): r'\\models ',
    re.compile(r'\\sq \\sqcup '): r'\\square ',
    re.compile(r'\\copyright'): r'©',
}
QQUAD_PATTERN = re.compile(r'\\qquad(?!\s)')


def remove_up_commands(s: str):
    """Remove unnecessary up commands from LaTeX code."""
    UP_PATTERN = re.compile(r'\\up([a-zA-Z]+)')
    s = UP_PATTERN.sub(
        lambda m: m.group(0) if m.group(1) in ["arrow", "downarrow", "lus", "silon"] else f"\\{m.group(1)}", s
    )
    return s


def remove_unsupported_commands(s: str):
    """Remove unsupported LaTeX commands."""
    COMMANDS_TO_REMOVE_PATTERN = re.compile(
        r'\\(?:lefteqn|boldmath|ensuremath|centering|textsubscript|sides|textsl|textcent|emph|protect|null)')
    s = COMMANDS_TO_REMOVE_PATTERN.sub('', s)
    return s


def latex_rm_whitespace(s: str):
    """Remove unnecessary whitespace from LaTeX code."""
    s = fix_unbalanced_braces(s)
    s = fix_latex_left_right(s)
    s = fix_latex_environments(s)

    s = remove_up_commands(s)
    s = remove_unsupported_commands(s)

    # Apply all replacements
    for pattern, replacement in REPLACEMENTS_PATTERNS.items():
        s = pattern.sub(replacement, s)

    # Handle backslashes and spaces in LaTeX
    s = process_latex(s)

    # Add space after \qquad
    s = QQUAD_PATTERN.sub(r'\\qquad ', s)

    # Remove trailing backslash if present
    while s.endswith('\\'):
        s = s[:-1]

    return s
