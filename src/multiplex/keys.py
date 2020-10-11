BACKSPACE = 8
DEL = 127
BACKSPACE_OR_DEL = {BACKSPACE, DEL}

ESC = 27
ESC_MOVE = [ESC, 91]
CTRL_MOVE = ESC_MOVE + [49, 59, 53]

UP = ESC_MOVE + [65]
DOWN = ESC_MOVE + [66]
LEFT = ESC_MOVE + [67]
RIGHT = ESC_MOVE + [68]

HOME = ESC_MOVE + [72]
END = ESC_MOVE + [70]

PAGEUP = ESC_MOVE + [53, 126]
PAGEDOWN = ESC_MOVE + [54, 126]

CTRL_UP = CTRL_MOVE + [65]
CTRL_DOWN = CTRL_MOVE + [66]
CTRL_LEFT = CTRL_MOVE + [67]
CTRL_RIGHT = CTRL_MOVE + [68]

ALT_UP = [ESC] + UP
ALT_DOWN = [ESC] + DOWN
ALT_LEFT = [ESC] + LEFT
ALT_RIGHT = [ESC] + RIGHT

ALT_J = [ESC] + [ord("j")]
ALT_K = [ESC] + [ord("k")]

CTRL_K = (11,)
CTRL_J = (10,)
CTRL_B = (2,)
CTRL_F = (6,)
CTRL_U = (21,)
CTRL_D = (4,)
CTRL__ = (27,)

CTRL_TO_NAME = {
    CTRL_K: "K",
    CTRL_J: "J",
    CTRL_B: "B",
    CTRL_F: "F",
    CTRL_U: "U",
    CTRL_D: "D",
    CTRL__: "[",
}

UP_NAME = "↑"
DOWN_NAME = "↓"
LEFT_NAME = "←"
RIGHT_NAME = "→"
ALT_NAME = "⌥"

SEQ_TO_NAME = {
    tuple(UP): UP_NAME,
    tuple(DOWN): DOWN_NAME,
    tuple(LEFT): LEFT_NAME,
    tuple(RIGHT): RIGHT_NAME,
    tuple(HOME): "Home",
    tuple(END): "End",
    tuple(PAGEUP): "Page Up",
    tuple(PAGEDOWN): "Page Down",
    tuple(CTRL_UP): f"^{UP_NAME}",
    tuple(CTRL_DOWN): f"^{DOWN_NAME}",
    tuple(CTRL_LEFT): f"^{LEFT_NAME}",
    tuple(CTRL_RIGHT): f"^{RIGHT_NAME}",
    tuple(ALT_UP): f"{ALT_NAME}{UP_NAME}",
    tuple(ALT_DOWN): f"{ALT_NAME}{DOWN_NAME}",
    tuple(ALT_LEFT): f"{ALT_NAME}{LEFT_NAME}",
    tuple(ALT_RIGHT): f"{ALT_NAME}{RIGHT_NAME}",
    tuple(ALT_J): f"{ALT_NAME}j",
    tuple(ALT_K): f"{ALT_NAME}k",
}

NORMAL = "normal"
SCROLL = "scroll"
GLOBAL = "global"
HELP = "help"

bindings = {
    NORMAL: {},
    SCROLL: {},
    GLOBAL: {},
    HELP: {},
}

descriptions = {
    HELP: {},
    NORMAL: {},
    SCROLL: {},
    GLOBAL: {},
}


def generic_key_to_name(key):
    name = chr(key)
    if not name.isprintable():
        name = f"[{ord(name)}]"
    return name


def seq_to_name(seq, fallback=True):
    if not isinstance(seq, tuple):
        seq = tuple(seq)
    name = None
    if seq in CTRL_TO_NAME:
        name = f"^{CTRL_TO_NAME[seq]}"
    elif seq in SEQ_TO_NAME:
        name = SEQ_TO_NAME[seq]
    elif len(seq) == 1:
        key = seq[0]
        name = generic_key_to_name(key)
    elif fallback:
        name = "".join(generic_key_to_name(o) for o in seq)
    return name


def is_multi(k):
    return isinstance(k, list) and isinstance(k[0], (list, tuple, str))


def key_to_seq(k):
    if isinstance(k, str):
        return tuple(ord(c) for c in k)
    elif is_multi(k):
        result = []
        for e in k:
            result.extend(key_to_seq(e))
        return tuple(result)
    elif isinstance(k, (list, tuple)):
        return tuple(k)
    else:
        raise RuntimeError(k)


def bind(mode, *keys, description=None, custom_bindings=None, custom_descriptions=None):
    used_bindings = custom_bindings if custom_bindings is not None else bindings
    used_descriptions = custom_descriptions if custom_descriptions is not None else descriptions

    def wrapper(fn):
        description_keys = []
        for key in keys:
            if not is_multi(key):
                key = [key]
            sequences = [key_to_seq(k) for k in key]
            name = "".join(seq_to_name(seq) for seq in sequences)
            description_keys.append(name)
        description_keys = tuple(description_keys)
        used_descriptions[mode][description_keys] = description or fn.__name__
        for k in keys:
            used_bindings[mode][key_to_seq(k)] = fn
        return fn

    return wrapper
