def obj(name):
    return type(name, (), {})()


REDRAW = obj("REDRAW")
RECALC = obj("RECALC")
SPLIT = obj("SPLIT")
STOP = obj("STOP")
QUIT = obj("QUIT")
ALL_DOWN = obj("ALL_DOWN")
SAVE = obj("SAVE")
OUTPUT_SAVED = obj("OUTPUT_SAVED")
STREAM_DONE = obj("STREM_DONE")
