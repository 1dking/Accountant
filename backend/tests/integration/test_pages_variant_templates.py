"""Pure-template structural assertions for variant_seeds.

Catches template shape regressions that would break the SectionEditor
inline-edit flow. Doesn't hit the DB or HTTP — imports the seed lists
directly and asserts on the jsx_template string.
"""
import pytest

from app.pages.variant_seeds import FAQ_VARIANTS


@pytest.mark.normal
def test_faq_accordion_answer_wrapped_in_p_not_div():
    """Commit 5.1: FAQ answer wrappers must be <p> not <div>.

    The SectionEditor iframe click handler enables contentEditable only
    for elements in TEXT_TAGS (H1-H6, P, SPAN, A, LI, BUTTON, LABEL,
    TD, TH, EM, STRONG). A <div> wrapper means clicking the answer
    text has no effect — the answer is unreachable from the inline
    editor. Use <p> so the answer is naturally editable.
    """
    faq = next(v for v in FAQ_VARIANTS if v["variant_id"] == "faq_accordion")
    tpl = faq["jsx_template"]
    # Each answer is wrapped in <p> with the right Tailwind classes.
    for i in range(1, 7):
        token = f"{{{{Q{i}_A}}}}"
        assert token in tpl, f"missing answer token {token}"
        # The wrapping element directly before the token must be <p>.
        idx = tpl.index(token)
        # Walk back to find the immediately-preceding opening tag.
        snippet = tpl[max(0, idx - 200):idx]
        # Last opening tag before the token:
        last_lt = snippet.rfind("<")
        assert last_lt >= 0, f"no opening tag before {token}"
        tag_open = snippet[last_lt:]
        assert tag_open.startswith("<p "), (
            f"answer {token} must be wrapped in <p>, got: {tag_open[:80]}"
        )


@pytest.mark.normal
def test_faq_accordion_question_in_span_inside_summary():
    """The question text must live in a <span> inside <summary> so the
    SectionEditor can enable contentEditable on click. The chevron
    (svg) sits alongside; clicks on the svg should fall through to the
    browser's native <details> toggle.
    """
    faq = next(v for v in FAQ_VARIANTS if v["variant_id"] == "faq_accordion")
    tpl = faq["jsx_template"]
    for i in range(1, 7):
        q_token = f"{{{{Q{i}_Q}}}}"
        assert q_token in tpl, f"missing question token {q_token}"
        idx = tpl.index(q_token)
        snippet = tpl[max(0, idx - 200):idx]
        last_lt = snippet.rfind("<")
        tag_open = snippet[last_lt:]
        assert tag_open.startswith("<span "), (
            f"question {q_token} must be wrapped in <span>, got: {tag_open[:80]}"
        )
