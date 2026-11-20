"""A small, safe json-logic subset: validate a rule BEFORE it is saved, and evaluate it for probing.

Validation checks: known operators only, known variables only, size/depth limits, and behaviour:
for a grid of probe inputs the rule must always return one of the three actions, and
  - it must NEVER return auto_handle when there is any red flag,
  - it must NEVER return auto_handle when confidence is low (0.3).
So an admin cannot publish a rule that silently approves risky cases.
"""
from typing import Any, Dict, List

ACTIONS = ("auto_handle", "ask_more", "send_to_human")
OPERATORS = {"var", "==", "!=", "===", "!==", ">", ">=", "<", "<=", "and", "or", "!", "!!", "if", "in",
             "+", "-", "*", "/", "max", "min"}
VARIABLES = {"confidence", "red_flags", "payment_step", "match_score", "doc_confidence", "claim_confidence"}
MAX_DEPTH = 8
MAX_NODES = 80


class RuleError(ValueError):
    pass


def _truthy(v: Any) -> bool:
    return bool(v) if not isinstance(v, list) else len(v) > 0


def validate_structure(expr: Any, depth: int = 0, counter: Any = None) -> None:
    counter = counter if counter is not None else [0]
    counter[0] += 1
    if counter[0] > MAX_NODES:
        raise RuleError("Rule is too large (more than %d nodes)" % MAX_NODES)
    if depth > MAX_DEPTH:
        raise RuleError("Rule is nested too deeply (more than %d levels)" % MAX_DEPTH)
    if isinstance(expr, dict):
        if len(expr) != 1:
            raise RuleError("Each json-logic object must have exactly one operator, got %s" % sorted(expr))
        op, args = next(iter(expr.items()))
        if op not in OPERATORS:
            raise RuleError("Unknown operator '%s'. Allowed: %s" % (op, ", ".join(sorted(OPERATORS))))
        args = args if isinstance(args, list) else [args]
        if op == "var":
            if not args or not isinstance(args[0], str):
                raise RuleError("'var' needs a variable name")
            root = args[0].split(".")[0]
            if root not in VARIABLES:
                raise RuleError("Unknown variable '%s'. Allowed: %s" % (args[0], ", ".join(sorted(VARIABLES))))
            return
        if op == "if" and len(args) < 3:
            raise RuleError("'if' needs at least a condition, a then and an else")
        for a in args:
            validate_structure(a, depth + 1, counter)
    elif isinstance(expr, list):
        for a in expr:
            validate_structure(a, depth + 1, counter)
    elif not (expr is None or isinstance(expr, (str, int, float, bool))):
        raise RuleError("Unsupported value of type %s" % type(expr).__name__)


def evaluate(expr: Any, data: Dict[str, Any]) -> Any:
    if isinstance(expr, list):
        return [evaluate(a, data) for a in expr]
    if not isinstance(expr, dict):
        return expr
    op, args = next(iter(expr.items()))
    args = args if isinstance(args, list) else [args]
    if op == "var":
        cur: Any = data
        for part in str(args[0]).split("."):
            if part == "length" and isinstance(cur, (list, str)):
                cur = len(cur)
            elif isinstance(cur, dict):
                cur = cur.get(part)
            else:
                return args[1] if len(args) > 1 else None
        return cur
    if op == "if":
        i = 0
        while i + 1 < len(args):
            if _truthy(evaluate(args[i], data)):
                return evaluate(args[i + 1], data)
            i += 2
        return evaluate(args[i], data) if i < len(args) else None
    if op == "and":
        val: Any = True
        for a in args:
            val = evaluate(a, data)
            if not _truthy(val):
                return val
        return val
    if op == "or":
        val = False
        for a in args:
            val = evaluate(a, data)
            if _truthy(val):
                return val
        return val
    vals = [evaluate(a, data) for a in args]
    try:
        if op in ("==", "==="):
            return vals[0] == vals[1]
        if op in ("!=", "!=="):
            return vals[0] != vals[1]
        if op == "!":
            return not _truthy(vals[0])
        if op == "!!":
            return _truthy(vals[0])
        if op == ">":
            return vals[0] > vals[1]
        if op == ">=":
            return vals[0] >= vals[1]
        if op == "<":
            return vals[0] < vals[1]
        if op == "<=":
            return vals[0] <= vals[1]
        if op == "in":
            return vals[0] in vals[1]
        if op == "+":
            return sum(vals)
        if op == "*":
            out = 1
            for v in vals:
                out *= v
            return out
        if op == "-":
            return -vals[0] if len(vals) == 1 else vals[0] - vals[1]
        if op == "/":
            return vals[0] / vals[1]
        if op == "max":
            return max(vals)
        if op == "min":
            return min(vals)
    except (TypeError, ZeroDivisionError, IndexError) as exc:
        raise RuleError("Rule cannot be evaluated: %s" % exc)
    raise RuleError("Unsupported operator '%s'" % op)


def probes() -> List[Dict[str, Any]]:
    out = []
    for conf in (1.0, 0.95, 0.9, 0.75, 0.6, 0.3, 0.0):
        for flags in ([], ["short_payment"]):
            for pay in (False, True):
                out.append({"confidence": conf, "red_flags": flags, "payment_step": pay,
                            "match_score": conf, "doc_confidence": conf, "claim_confidence": conf})
    return out


def validate_logic(expr: Any) -> None:
    """Raises RuleError with a clear message. An empty logic is allowed by callers (they keep the old one)."""
    if not isinstance(expr, dict):
        raise RuleError("logic must be a json-logic object")
    validate_structure(expr)
    for p in probes():
        result = evaluate(expr, p)
        if result not in ACTIONS:
            raise RuleError("Rule must always return one of %s, but returned %r for %s" % (list(ACTIONS), result, p))
        if result == "auto_handle" and p["red_flags"]:
            raise RuleError("Unsafe rule: it auto-handles a case that has red flags (%s)" % p["red_flags"])
        if result == "auto_handle" and p["confidence"] <= 0.3:
            raise RuleError("Unsafe rule: it auto-handles a case with confidence %s" % p["confidence"])
