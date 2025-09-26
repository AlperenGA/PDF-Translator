from modules.translator import translate_text

def test_translation():
    text = "This is a test."
    result = translate_text(text)
    assert isinstance(result, str)
    assert len(result) > 0
