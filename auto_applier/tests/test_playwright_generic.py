from __future__ import annotations

from auto_applier.ats.playwright_generic import (
    _ActionPlan,
    _profile_compact_yaml,
    is_captcha_present,
    is_confirmation_present,
    is_login_wall,
)


def test_confirmation_detection_phrases():
    assert is_confirmation_present("Thank you for applying!") is True
    assert is_confirmation_present("Your application has been received.") is True
    assert is_confirmation_present(
        "We've received your application and will be in touch."
    ) is True
    assert is_confirmation_present("Application submitted successfully.") is True
    assert is_confirmation_present("Please fill out the form below.") is False


def test_confirmation_detection_url():
    assert is_confirmation_present("Some body", "https://acme.com/jobs/123/confirmation") is True
    assert is_confirmation_present("Some body", "https://acme.com/jobs/123/success") is True
    assert is_confirmation_present("Some body", "https://acme.com/jobs/123") is False


def test_captcha_detection():
    assert is_captcha_present('<iframe src="recaptcha"></iframe>') is True
    assert is_captcha_present("I'm not a robot") is True
    assert is_captcha_present("Please verify you are human before continuing.") is True
    assert is_captcha_present("Normal application form") is False


def test_login_wall_detection():
    assert is_login_wall("Please sign in to continue with your application.") is True
    assert is_login_wall("Create an account to apply for this role.") is True
    assert is_login_wall("Job description here", "https://workday.com/login") is True
    assert is_login_wall("Apply now", "https://acme.com/jobs/123/apply") is False


def test_profile_compact_yaml_drops_bulk():
    profile_dict = {
        "personal": {"full_name": "Ada"},
        "experience": [
            {"company": "Acme", "title": "SRE", "bullets": ["x" * 1000]},
        ] * 50,
        "qa_bank": [{"question": "Sponsorship?", "answer": "No"}],
        "must_have_skills": ["Python"],  # not in keep_keys, gets dropped
    }
    out = _profile_compact_yaml(profile_dict)
    assert "Ada" in out
    assert "Sponsorship" in out
    # Bulk fields aren't included
    assert "x" * 100 not in out
    # And a key not in the keep list isn't either
    assert "must_have_skills" not in out


def test_action_plan_validates():
    plan = _ActionPlan.model_validate(
        {
            "actions": [
                {"type": "fill", "selector": "#email", "value": "a@b.com"},
                {"type": "click", "selector": "button[type=submit]"},
            ],
            "done": False,
            "needs_human": False,
            "reason": "",
        }
    )
    assert len(plan.actions) == 2
    assert plan.actions[0].type == "fill"
    assert plan.actions[0].selector == "#email"
    assert plan.actions[0].value == "a@b.com"
    assert plan.done is False
