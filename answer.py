
import re
from openai import OpenAI
from rag import load_documents, retrieve
from tools.tools import lookup_order, create_ticket


# Local Ollama model — no OpenAI API credits required.
client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)

MODEL = "llama3.2:3b"

SYSTEM_PROMPT = """
You are the customer-support assistant for ZentroMart.

Rules:
1. Answer using only the supplied knowledge-base evidence.
2. Never invent policies, refund timelines, amounts, or exceptions.
3. Prefer current policies over superseded policies.
4. Distinguish business days from calendar days.
5. General policy questions do not require identity verification.
6. Never reveal specific order details without successful verification.
7. Never claim an order lookup or ticket was completed unless the
   corresponding tool confirmed it.
8. Cite evidence using [source filename — section heading].
9. If evidence is insufficient or conflicting, say so.
10. Be concise, polite, and clear.
"""


def generate_answer(question, documents):
    """Answer a general question using retrieved knowledge-base evidence."""
    evidence = retrieve(question, documents, top_k=5)

    if not evidence:
        return (
            "I couldn't find enough relevant information in the "
            "knowledge base to answer confidently.",
            [],
        )

    evidence_text = "\n\n".join(
        f"[Source: {item['source']} — "
        f"{item.get('heading', 'Knowledge-base section')}]\n"
        f"{item['text']}"
        for item in evidence
    )

    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Customer question:\n{question}\n\n"
                    f"Knowledge-base evidence:\n{evidence_text}\n\n"
                    "Answer using only this evidence and cite your sources."
                ),
            },
        ],
    )

    answer = response.choices[0].message.content
    return answer or "I couldn't generate an answer.", evidence


def show_verified_order(result):
    """Display order information only after successful verification."""
    print("\n--- VERIFIED ORDER ---")
    print(f"Order ID: {result.get('order_id', 'Not available')}")

    for field in (
        "status",
        "order_status",
        "payment_status",
        "delivery_date",
        "expected_delivery_date",
    ):
        value = result.get(field)
        if value is not None:
            label = field.replace("_", " ").title()
            print(f"{label}: {value}")

    items = result.get("items", [])
    if items:
        print("Items:")
        for item in items:
            name = item.get("product_name") or item.get("sku")
            quantity = item.get("quantity")

            if name:
                line = f"- {name}"
                if quantity is not None:
                    line += f" (quantity: {quantity})"
                print(line)

    print("Your identity was verified before order details were displayed.")


def is_ticket_request(question):
    """Identify explicit requests for a ticket or human escalation."""
    pattern = (
        r"\b(?:"
        r"create\s+(?:a\s+)?ticket|"
        r"raise\s+(?:a\s+)?ticket|"
        r"open\s+(?:a\s+)?ticket|"
        r"human\s+agent|"
        r"speak\s+to\s+(?:a\s+)?human|"
        r"talk\s+to\s+(?:a\s+)?agent|"
        r"escalate|"
        r"contact\s+(?:a\s+)?human"
        r")\b"
    )
    return re.search(pattern, question.lower()) is not None


def extract_order_id(text):
    """Extract a ZentroMart ID or an eight-digit dataset order ID."""
    match = re.search(r"\bZM\d+\b", text, re.IGNORECASE)
    if match:
        return match.group(0).upper()

    match = re.search(r"\b\d{8}\b", text)
    return match.group(0) if match else None


def main():
    documents = load_documents()

    print(f"Loaded {len(documents)} knowledge-base sections.")
    print(f"Using local Ollama model: {MODEL}")
    print("ZentroMart support assistant ready.")

    # State for the current interactive conversation.
    pending_order = None
    verification_used = False
    verification_attempts = 0
    verification_failed = False
    last_issue = ""
    pending_issue = ""
    MAX_VERIFICATION_ATTEMPTS = 1

    while True:
        try:
            question = input(
                "\nAsk a question (or type 'exit'): "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if question.lower() == "exit":
            print("Goodbye!")
            break

        if not question:
            continue

        # 1. Handle explicit ticket requests before verification.
        if is_ticket_request(question):
            issue = (pending_issue or last_issue).strip()

            if len(issue) < 20:
                print(
                    "Please describe the issue and the help you need "
                    "in a little more detail before I create a ticket."
                )
                last_issue = question
                continue

            order_id = extract_order_id(issue)

            result = create_ticket(
                summary=(
                    f"Customer issue: {issue}. "
                    "Customer requested human support."
                ),
                order_id=order_id,
                reason="Customer requested escalation",
                intent="human_escalation",
            )

            if result.get("created") is True:
                print(
                    "\nYour support ticket has been created. "
                    f"Ticket ID: {result['ticket_id']}"
                )
                last_issue = ""
                pending_issue = ""
                pending_order = None
                verification_used = False
                verification_attempts = 0
                verification_failed = False
            else:
                print(
                    "\nI couldn't create the ticket: "
                    f"{result.get('error', 'Unknown error')}"
                )

            continue

        # 2. Do not send repeated numeric verification inputs to Ollama.
        if verification_failed and question.isdigit():
            print(
                "Verification has already failed. For your privacy, "
                "please use the official support channel or request a ticket."
            )
            continue

        # 3. If an order lookup is awaiting verification, process this input.
        if pending_order is not None:
            if verification_attempts >= MAX_VERIFICATION_ATTEMPTS:
                print(
                    "Verification attempts are exhausted. "
                    "Please use the official support channel for help."
                )
                pending_order = None
                verification_used = True
                verification_failed = True
                continue

            verification_attempts += 1
            verification_used = True

            result = lookup_order(
                pending_order,
                verification_value=question,
            )

            if (
                result.get("verified") is True
                and result.get("found") is True
            ):
                show_verified_order(result)
                last_issue = ""
                pending_issue = ""
                verification_failed = False
            else:
                verification_failed = True
                print(
                    "\nI couldn't verify your details. For your privacy, "
                    "I can't disclose this order's information. "
                    "You can request a support ticket if you need further help."
                )

            pending_order = None
            continue

        # 4. Start an order lookup and require verification first.
        order_id = extract_order_id(question)

        if order_id:
            pending_order = order_id
            verification_used = False
            verification_attempts = 0
            verification_failed = False
            pending_issue = question
            last_issue = question

            result = lookup_order(order_id)

            if result.get("verification_required") is True:
                print(
                    f"\nBefore I can look up {order_id}, please provide "
                    "either the last 4 digits of the registered phone "
                    "number or the 6-digit delivery pincode."
                )
            else:
                pending_order = None
                print("I couldn't start the order verification process.")

            continue

        # 5. Answer general policy and FAQ questions using RAG.
        last_issue = question

        try:
            answer, evidence = generate_answer(question, documents)

            print("\n--- ANSWER ---")
            print(answer)

            print("\n--- RETRIEVED EVIDENCE ---")
            for index, item in enumerate(evidence, 1):
                heading = item.get(
                    "heading",
                    "Knowledge-base section",
                )
                print(
                    f"{index}. {item['source']} — {heading} "
                    f"(score: {item['score']})"
                )

        except Exception as exc:
            print(f"\nRequest failed: {exc}")
            print(
                "Check that Ollama is running and that "
                f"'{MODEL}' is available."
            )


if __name__ == "__main__":
    main()
