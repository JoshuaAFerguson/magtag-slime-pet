from app.llm import build_prompt, clean_dream


def test_build_prompt_carries_constraints_and_context():
    system, user = build_prompt(
        {"weather": "rain", "season": "summer", "fam": 3, "tones": ["busy"]}, max_chars=100
    )
    assert "100" in system
    assert "dream" in system.lower()
    assert "rain" in user and "summer" in user and "busy" in user


def test_build_prompt_tolerates_empty_context():
    system, user = build_prompt({})
    assert isinstance(system, str) and isinstance(user, str)
    assert "quiet" in user  # default tone


def test_clean_dream_collapses_and_terminates():
    assert clean_dream("  i drifted\n over the   pond  ") == "i drifted over the pond."


def test_clean_dream_strips_quotes_and_keeps_terminal_punct():
    assert clean_dream('"the moon hummed!"') == "the moon hummed!"


def test_clean_dream_truncates_at_word_boundary():
    out = clean_dream("one two three four five six seven", max_chars=12)
    assert len(out) <= 13  # <= max_chars + terminal period
    assert out.endswith(".")
    assert "fiv" not in out.rstrip(".")  # cut at a word boundary, no partial word


def test_clean_dream_empty():
    assert clean_dream("") == ""
    assert clean_dream("   \n  ") == ""
