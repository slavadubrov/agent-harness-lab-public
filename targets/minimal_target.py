"""A second target with no model and no framework: the support policy as plain Python.

It speaks the same protocol as the LangChain harness target and uses only the standard
library, so it shows that the evaluator does not depend on LangChain. Like Part 3's
workflow with no agent, its rules were written with the support tasks in view; it is a
portability check and an honest control, not a general support agent.
"""

import json
import re
import sys

hello = json.loads(sys.stdin.readline())
message = hello["message"]


def send(kind, **fields):
    line = {"protocol": hello["protocol"], "run_id": hello["run_id"], "kind": kind, **fields}
    print(json.dumps(line), flush=True)


def call(name, **arguments):
    """One tool call; a lost reply from the service is retried once with the same arguments."""
    for _ in range(2):
        send("tool", name=name, arguments=arguments, call_id=None)
        answer = json.loads(sys.stdin.readline())
        if "result" in answer:
            return answer["result"]
    return {"error": answer.get("message", "the service did not answer")}


def money(cents):
    return f"${cents / 100:.2f}"


def refund(account, order_id):
    orders = {o["id"]: o for o in call("list_orders", account_id=account["id"])["orders"]}
    order = orders.get(order_id)
    if order is None:
        return f"I cannot find order {order_id} on your account, so I cannot refund it."
    if order["status"] == "cancelled":
        return f"Order {order_id} was cancelled, so it is refunded automatically."
    if order["status"] != "delivered":
        return f"Order {order_id} has not been delivered yet. Refunds start after delivery."
    if order["days_since_delivery"] > 30:
        return f"Order {order_id} was delivered more than 30 days ago, outside the refund window."
    remaining = order["total_cents"] - order["refunded_cents"]
    if remaining <= 0:
        return f"Order {order_id} has already been refunded in full."
    stated = re.search(r"\$(\d+(?:\.\d{2})?)", message)
    amount = round(float(stated.group(1)) * 100) if stated else remaining
    if amount > remaining:
        return f"I can refund at most {money(remaining)} on order {order_id}."
    result = call("issue_refund", order_id=order_id, amount_cents=amount, reason="Customer request")
    if result.get("status") == "held_for_approval":
        send("approval", request={"kind": "refund_approval", "held": [result]})
        decision = json.loads(sys.stdin.readline()).get("decision")
        if decision is None:
            return (
                f"Your refund of {money(amount)} for order {order_id} is above $200, so a "
                "supervisor will review it within two business days."
            )
        if decision == "reject":
            return (
                f"A supervisor reviewed your refund of {money(amount)} for order {order_id} "
                "and did not approve it. No refund was issued."
            )
        result = call("issue_refund", order_id=order_id, amount_cents=amount, reason="Approved")
        return (
            f"A supervisor approved your refund of {money(amount)} for order {order_id}. "
            f"It has been issued (refund {result.get('refund_id')})."
        )
    if "error" in result:
        return f"The refund could not be made: {result['error']}"
    return f"I refunded {money(amount)} for order {order_id} (refund {result['refund_id']})."


COUNTRIES = {"germany": "DE", "france": "FR", "poland": "PL", "sweden": "SE", "united states": "US"}


def address(account):
    kind = "billing" if "billing" in message.lower() else "shipping"
    if account["status"] != "active":
        return f"Your account is {account['status']}, so I cannot change its address. Please call support."
    found = re.search(r"address (?:is|to) (.+?)\.?$", message)
    parts = [p.strip() for p in found.group(1).split(",")] if found else []
    city_part = re.fullmatch(r"(\d[\d ]*)\s+(.+)", parts[1]) if len(parts) > 1 else None
    country = COUNTRIES.get(parts[2].lower()) if len(parts) > 2 else None
    missing = [
        name
        for name, value in (
            ("city", city_part),
            ("postal code", city_part),
            ("country", country),
        )
        if not value
    ]
    if missing or not parts:
        return f"Please send the full new address: {', '.join(missing)} are missing."
    postal, city = city_part.group(1), city_part.group(2)
    call(
        "update_address",
        account_id=account["id"],
        kind=kind,
        line1=parts[0],
        city=city,
        postal_code=postal,
        country=country,
    )
    return f"Your {kind} address is now {parts[0]}, {postal} {city}, {country}."


LANGUAGES = {"german": "de", "english": "en", "french": "fr", "spanish": "es", "polish": "pl"}


def preferences(account):
    text = message.lower()
    done, unsupported = [], []
    if "marketing" in text:
        value = "off" if re.search(r"stop|off|unsubscribe", text) else "on"
        call("set_preference", account_id=account["id"], key="marketing_emails", value=value)
        done.append(f"marketing emails are now {value}")
    if "sms" in text:
        call("set_preference", account_id=account["id"], key="sms_notifications", value="on")
        done.append("SMS notifications are now on")
    language = re.search(r"language to (\w+)", text)
    if language and language.group(1) in LANGUAGES:
        code = LANGUAGES[language.group(1)]
        call("set_preference", account_id=account["id"], key="language", value=code)
        done.append(f"your language is now {language.group(1).capitalize()} ({code})")
    if "dark mode" in text:
        unsupported.append("dark mode")
    reply = "Done: " + "; ".join(done) + "." if done else ""
    if unsupported:
        reply += f" Not available: {', '.join(unsupported)}. I changed nothing for it."
    return reply.strip() or "Which setting would you like to change?"


def handle():
    email = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", message)
    if email is None:
        return "Please send the email address of your account."
    account = call("look_up_account", email=email.group())
    if "error" in account:
        return "I cannot find an account with that email address."
    orders = re.findall(r"\bO-\d{4}\b", message)
    text = message.lower()
    if "refund" in text:
        if len(orders) != 1:
            return "Which order is this about? Please send the order number."
        return refund(account, orders[0])
    if "address" in text:
        return address(account)
    if re.search(r"marketing|sms|language|dark mode|paperless", text):
        return preferences(account)
    return "I have passed your message to a colleague, who will reply soon."


send("finish", reply=handle())
