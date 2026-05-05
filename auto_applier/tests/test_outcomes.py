from __future__ import annotations

from auto_applier.tracking.outcomes import classify


def test_confirmation_classification():
    assert classify("Thanks for applying to Acme!") == "confirmation_received"
    assert classify("We've received your application.") == "confirmation_received"
    assert classify("Your application has been received.") == "confirmation_received"


def test_interview_classification():
    assert classify("Let's schedule a call next week.") == "interview_invitation"
    assert (
        classify("We'd love to set up time to chat.") == "interview_invitation"
    )
    assert classify("Please pick a time on Calendly: https://...") == "interview_invitation"


def test_rejection_classification():
    assert (
        classify("Unfortunately, we have decided to move forward with other candidates.")
        == "rejection"
    )
    assert classify("The position has been filled.") == "rejection"
    assert classify("We will not be moving forward.") == "rejection"


def test_rejection_outranks_confirmation_in_polite_rejection_emails():
    # Many rejection emails open with thanks — make sure rejection wins.
    text = (
        "Thanks for applying to Acme. Unfortunately, we have decided to move "
        "forward with other candidates this time."
    )
    assert classify(text) == "rejection"


def test_unrelated_email_is_unclassified():
    assert classify("Your password was changed successfully.") is None
    assert classify("Welcome to our newsletter!") is None
