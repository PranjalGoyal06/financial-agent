import re

def parse_chips(msg: str):
    chip_matches = re.findall(r"[\$@]([A-Z0-9.]+)", msg)
    seen = set()
    chips = [x for x in chip_matches if not (x in seen or seen.add(x))]
    
    if len(chips) == 2:
        focus_text = re.sub(r"[\$@][A-Z0-9.]+", "", msg).strip()
        focus = focus_text if len(focus_text) > 3 else None
        return chips, focus
    return None, None

def test_parse_chips():
    msg = "/compare $RELIANCE.NS $TCS.NS on debt levels"
    chips, focus = parse_chips(msg)
    assert chips == ["RELIANCE.NS", "TCS.NS"]
    assert focus == "/compare   on debt levels"
    
    msg2 = "/compare @RELIANCE.NS and @TCS.NS"
    chips, focus = parse_chips(msg2)
    assert chips == ["RELIANCE.NS", "TCS.NS"]
    assert focus == "/compare  and"
    
    msg3 = "/compare $AAPL"
    chips, focus = parse_chips(msg3)
    assert chips is None
