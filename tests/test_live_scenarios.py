"""The challenge scenarios against the real stack.

Deselected by default: they call AWS Bedrock and Tavily, and cost credits.
Run with `uv run pytest -m live` after `python -m src.rag.vector_store`.
"""

import pytest

from src.agents.pipeline import run_agent

pytestmark = pytest.mark.live

MERCHANT = "cliente1988"

KNOWLEDGE_QUESTIONS = [
    "What's the difference between the Get Clássica and the Get Smart?",
    "Do I need a bank account to receive my sales via Pix?",
    "How does receivables advance (antecipação) work with Getnet?",
    "How many installments can I split a sale into with the crediário?",
    "Can I sell through WhatsApp using the Payment Link?",
]

ACCOUNT_QUESTIONS = [
    "When will the money from yesterday's sales be deposited?",
    "My card machine won't connect to the internet, what should I do?",
    "My card machine is showing a transaction decline error.",
]

GENERAL_QUESTIONS = [
    "What's the weather forecast in Porto Alegre tomorrow?",
    "What's the euro exchange rate today?",
]


def assert_useful(answer: str) -> None:
    assert answer, "the pipeline returned nothing"
    assert answer != "No response generated.", "the graph ended without a final response"
    assert len(answer) > 80, f"suspiciously short answer: {answer!r}"


@pytest.mark.parametrize("question", KNOWLEDGE_QUESTIONS)
def test_product_questions_are_answered(question):
    assert_useful(run_agent(user_question=question, user_id=MERCHANT))


@pytest.mark.parametrize("question", ACCOUNT_QUESTIONS)
def test_account_questions_reach_the_merchant_data(question):
    assert_useful(run_agent(user_question=question, user_id=MERCHANT))


@pytest.mark.parametrize("question", GENERAL_QUESTIONS)
def test_off_topic_questions_are_answered_from_the_web(question):
    answer = run_agent(user_question=question, user_id=MERCHANT)

    assert_useful(answer)
    assert "getnet" not in answer.lower() or "http" in answer.lower(), (
        "an off-topic question must be answered, not deflected to Getnet channels"
    )


def test_the_answer_follows_the_language_of_the_question():
    answer = run_agent(user_question="Quais taxas eu pago no crédito?", user_id=MERCHANT)

    assert_useful(answer)
    assert any(word in answer.lower() for word in ("taxa", "crédito", "credito", "você")), (
        f"expected a Portuguese answer, got: {answer[:200]!r}"
    )
