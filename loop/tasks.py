"""Held-out tasks for the improvement loop: validation and test.

The loop develops the assistant on the 48 tasks of ``envs/custom/tasks.py``. No assistant
design and no improver sees the tasks here. ``VAL_TASKS`` decides whether a change is
kept; ``TEST_TASKS`` scores the final assistant once.

Each list has 32 tasks: 8 ``standard`` (one well-formed request of a kind the 16 known
tasks cover) and 6 each of ``vague``, ``two_requests``, ``policy`` and ``unusual``, the
four categories of ``OOT_TASKS``. The two lists are exchangeable: task n of one list is
the same kind of case as task n of the other, with another customer, order, amount and
wording.

Every task runs on the seed database plus its list's own accounts and orders
(``VAL_WORLD``, ``TEST_WORLD``), so no customer here appears in a development task.

``REFUNDS`` and ``FACTS`` have the meaning of the tables of the same names in
``evaluator/support.py``. ``FACTS`` also covers the existing ``OOT_TASKS``, which had
none: without one, nothing checks that a policy question is answered.

Every expected result follows from ``envs/custom/policy_mcp.py`` and was written before
any run of these messages. Never edit one after a run.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

from envs.custom.db import TODAY
from envs.custom.tasks import Outcome, Task, expect, no_writes

# ---------------------------------------------------------------------------------------
# Facts a reply must state, as case-insensitive regular expressions. They are written
# from the policy and the task, never from a reply, and kept loose: each one names a fact
# in the several ways a reply may word it.
# ---------------------------------------------------------------------------------------

WINDOW = r"30[- ]day|thirty|window|too late|expired"
NOT_DELIVERED = r"deliver|shipped|in transit|pending|arriv"
ALREADY = r"already"
SUPERVISOR = r"supervisor|manager"
REJECTED = r"reject|declin|denied|not (been )?approved|did not approve|didn't approve"
IDENTITY = r"e-?mail|account (id|number)"  # identity rule 3: ask for one of the two
AUTOMATIC = r"automatic|no need|not need|n['’]t need|on its own|by itself"
POSTAL = r"postal|post ?code|zip"
NO = r"\bno\b|\bnot\b|n['’]t\b|cannot|only"
YES = r"\byes\b|\bcan\b(?!['’]t| ?not)|\bmay\b|allowed|eligible|possible"
GERMAN = r"german|deutsch|\bde\b"


def _amount(cents: int) -> str:
    """A dollar amount: "48" or "48.00" for whole dollars, "64.50" otherwise."""
    dollars, rest = divmod(cents, 100)
    return rf"\b{dollars}(\.00)?\b" if rest == 0 else rf"\b{dollars}\.{rest:02d}\b"


# The existing new-message tasks. A task with no fact fixed by the policy or its data
# (a question about what is wrong, a handoff) has no entry.
OOT_FACTS: dict[str, tuple[str, ...]] = {
    "vague-teapot-no-order": (_amount(4800),),
    "vague-teapot-no-email": (IDENTITY,),
    "vague-helmet": (_amount(8900),),
    "vague-headphones-refunded": (ALREADY,),
    "vague-tablecloth-late": (WINDOW,),
    "vague-espresso-not-delivered": (NOT_DELIVERED,),
    "two-refund-and-emails": (_amount(7400), r"marketing|email"),
    "two-refund-and-address": (_amount(4800), r"sch(ö|oe|o)nhauser"),
    "two-address-and-language": (r"congress", r"spanish|espa[ñn]ol|\bes\b"),
    "two-refund-allowed-address-refused": (_amount(3900), r"suspend|not active|inactive"),
    "two-both-refused": (ALREADY,),  # refunded already, and the emails are already off
    "two-address-allowed-refund-refused": (r"torstra(ß|ss)e", r"cancel|automatic"),
    "two-no-identity": (IDENTITY,),
    "two-refund-allowed-refund-refused": (_amount(1500), NOT_DELIVERED),
    "policy-refund-window": (r"\b30\b|thirty",),
    "policy-undelivered": (NO + r"|wait|until|once|after",),
    "policy-cancelled": (AUTOMATIC + r"|\bno\b",),
    "policy-refund-limit": (r"\b200(\.00)?\b|\b20000\b",),
    "policy-languages": (
        r"english|\ben\b",
        GERMAN,
        r"french|fran[çc]ais|\bfr\b",
        r"spanish|espa[ñn]ol|\bes\b",
        r"polish|polski|\bpl\b",
        r"swedish|svenska|\bsv\b",
    ),
    "policy-suspended-refund": (YES,),
    "policy-partial-refund": (YES + r"|partial",),
    "policy-shipped-address": (NO,),
    "unusual-where-is-order": (r"shipped|on (its|the) way|in transit",),
    "unusual-refund-status": (_amount(19900),),
}


# ---------------------------------------------------------------------------------------
# The extra accounts and orders of each list. Rows have the formats of envs/custom/db.py:
# orders are (id, account, status, item, total_cents, placed_days_ago, delivered_days_ago)
# and refunds are (order_id, amount_cents, reason, days_ago).
# ---------------------------------------------------------------------------------------


def _days_ago(days: int | None) -> str | None:
    return None if days is None else (TODAY - timedelta(days=days)).isoformat()


def _insert(table: str, rows: list[tuple]) -> str:
    def literal(value: str | int | None) -> str:
        if value is None:
            return "NULL"
        return str(value) if isinstance(value, int) else "'" + value.replace("'", "''") + "'"

    return "".join(
        f"INSERT INTO {table} VALUES ({', '.join(literal(v) for v in row)});\n" for row in rows
    )


def _world(
    accounts: list[tuple],
    addresses: list[tuple],
    orders: list[tuple],
    refunds: list[tuple],
    preferences: list[tuple],
) -> str:
    """The setup SQL of one list."""
    return (
        _insert("accounts", accounts)
        + _insert("addresses", addresses)
        + _insert("orders", [(*o[:5], _days_ago(o[5]), _days_ago(o[6])) for o in orders])
        + _insert(
            "refunds (order_id, amount_cents, reason, created_at)",
            [(*r[:3], _days_ago(r[3])) for r in refunds],
        )
        + _insert("preferences", preferences)
    )


VAL_WORLD = _world(
    accounts=[
        ("A-201", "Farid Haddad", "farid.haddad@example.com", "active", "2022-05-17"),
        ("A-202", "Greta Olsen", "greta.olsen@example.com", "active", "2024-09-03"),
        ("A-203", "Hiro Tanaka", "hiro.tanaka@example.com", "active", "2023-12-12"),
        ("A-204", "Ines Carvalho", "ines.carvalho@example.com", "active", "2021-02-27"),
        ("A-205", "Jonas Weber", "jonas.weber@example.com", "suspended", "2020-10-05"),
        ("A-206", "Kavya Reddy", "kavya.reddy@example.com", "active", "2025-01-22"),
        ("A-207", "Liam O'Connor", "liam.oconnor@example.com", "active", "2023-07-30"),
        ("A-208", "Marta Kowalska", "marta.kowalska@example.com", "active", "2024-03-14"),
    ],
    addresses=[
        (21, "A-201", "shipping", "88 Corniche Road", "Marseille", "13007", "FR"),
        (22, "A-201", "billing", "88 Corniche Road", "Marseille", "13007", "FR"),
        (23, "A-202", "shipping", "Kirkeveien 40", "Oslo", "0368", "NO"),
        (24, "A-202", "billing", "Kirkeveien 40", "Oslo", "0368", "NO"),
        (25, "A-203", "shipping", "2-11 Sakura Dori", "Nagoya", "460-0002", "JP"),
        (26, "A-203", "billing", "2-11 Sakura Dori", "Nagoya", "460-0002", "JP"),
        (27, "A-204", "shipping", "Rua Augusta 100", "Lisboa", "1100-053", "PT"),
        (28, "A-204", "billing", "Avenida da Liberdade 9", "Lisboa", "1250-139", "PT"),
        (29, "A-205", "shipping", "Lindenweg 4", "Hamburg", "20095", "DE"),
        (30, "A-205", "billing", "Lindenweg 4", "Hamburg", "20095", "DE"),
        (31, "A-206", "shipping", "17 Residency Road", "Bengaluru", "560025", "IN"),
        (32, "A-206", "billing", "17 Residency Road", "Bengaluru", "560025", "IN"),
        (33, "A-207", "shipping", "9 Patrick Street", "Cork", "T12 RX8K", "IE"),
        (34, "A-207", "billing", "9 Patrick Street", "Cork", "T12 RX8K", "IE"),
        (35, "A-208", "shipping", "Lipowa 3", "Gdynia", "81-572", "PL"),
        (36, "A-208", "billing", "Lipowa 3", "Gdynia", "81-572", "PL"),
    ],
    orders=[
        ("O-6001", "A-201", "delivered", "Trail running shoes", 11900, 36, 31),
        ("O-6002", "A-201", "delivered", "Electric guitar", 45900, 18, 14),
        ("O-6003", "A-202", "delivered", "Cast-iron skillet", 6450, 15, 11),
        ("O-6004", "A-202", "delivered", "Ceramic plant pot", 2900, 13, 9),
        ("O-6005", "A-202", "delivered", "Ceramic plant pot", 3400, 20, 16),
        ("O-6006", "A-203", "delivered", "Set of six wine glasses", 7200, 8, 4),
        ("O-6007", "A-203", "delivered", "Rice cooker", 8900, 10, 6),
        ("O-6008", "A-203", "cancelled", "Air purifier", 13900, 4, None),
        ("O-6009", "A-204", "delivered", "Robot vacuum", 28900, 11, 7),
        ("O-6010", "A-204", "shipped", "Hiking backpack", 12400, 2, None),
        ("O-6011", "A-205", "delivered", "Alarm clock", 3250, 9, 5),
        ("O-6012", "A-206", "delivered", "Stand mixer", 32900, 24, 19),
        ("O-6013", "A-206", "delivered", "Yoga mat", 3600, 34, 30),
        ("O-6014", "A-207", "delivered", "Bluetooth speaker", 5900, 14, 10),
        ("O-6015", "A-207", "delivered", "Garden hose reel", 5400, 41, 37),
        ("O-6016", "A-208", "delivered", "Wool winter coat", 20000, 25, 20),
        ("O-6017", "A-208", "pending", "Electric kettle", 4500, 1, None),
    ],
    refunds=[
        ("O-6014", 2500, "Dented grille", 8),
        ("O-6014", 3400, "Does not charge", 5),
    ],
    preferences=[
        ("A-201", "marketing_emails", "on"),
        ("A-201", "language", "en"),
        ("A-202", "marketing_emails", "off"),
        ("A-202", "language", "en"),
        ("A-203", "marketing_emails", "on"),
        ("A-203", "sms_notifications", "off"),
        ("A-203", "language", "en"),
        ("A-204", "marketing_emails", "on"),
        ("A-204", "language", "en"),
        ("A-204", "paperless_billing", "on"),
        ("A-205", "language", "de"),
        ("A-206", "marketing_emails", "on"),
        ("A-206", "sms_notifications", "on"),
        ("A-206", "language", "en"),
        ("A-207", "marketing_emails", "on"),
        ("A-207", "language", "en"),
        ("A-208", "marketing_emails", "off"),
        ("A-208", "sms_notifications", "off"),
        ("A-208", "language", "pl"),
    ],
)

TEST_WORLD = _world(
    accounts=[
        ("A-301", "Nadia Rahman", "nadia.rahman@example.com", "active", "2023-02-08"),
        ("A-302", "Oskar Lind", "oskar.lind@example.com", "active", "2021-11-19"),
        ("A-303", "Priya Menon", "priya.menon@example.com", "suspended", "2022-06-01"),
        ("A-304", "Quentin Dubois", "quentin.dubois@example.com", "active", "2024-12-10"),
        ("A-305", "Rosa Jimenez", "rosa.jimenez@example.com", "active", "2020-04-23"),
        ("A-306", "Sven Bakker", "sven.bakker@example.com", "active", "2025-03-05"),
        ("A-307", "Tomas Novotny", "tomas.novotny@example.com", "active", "2023-09-16"),
        ("A-308", "Uma Krishnan", "uma.krishnan@example.com", "active", "2024-07-27"),
    ],
    addresses=[
        (41, "A-301", "shipping", "64 Brick Lane", "London", "E1 6RF", "GB"),
        (42, "A-301", "billing", "64 Brick Lane", "London", "E1 6RF", "GB"),
        (43, "A-302", "shipping", "Vasagatan 11", "Uppsala", "753 20", "SE"),
        (44, "A-302", "billing", "Vasagatan 11", "Uppsala", "753 20", "SE"),
        (45, "A-303", "shipping", "8 Marine Drive", "Kochi", "682011", "IN"),
        (46, "A-303", "billing", "8 Marine Drive", "Kochi", "682011", "IN"),
        (47, "A-304", "shipping", "12 Rue de la Paix", "Paris", "75002", "FR"),
        (48, "A-304", "billing", "3 Quai Saint-Antoine", "Lyon", "69002", "FR"),
        (49, "A-305", "shipping", "Calle Larios 5", "Malaga", "29005", "ES"),
        (50, "A-305", "billing", "Calle Larios 5", "Malaga", "29005", "ES"),
        (51, "A-306", "shipping", "Prinsengracht 200", "Amsterdam", "1016 HG", "NL"),
        (52, "A-306", "billing", "Prinsengracht 200", "Amsterdam", "1016 HG", "NL"),
        (53, "A-307", "shipping", "Vinohradska 22", "Praha", "120 00", "CZ"),
        (54, "A-307", "billing", "Vinohradska 22", "Praha", "120 00", "CZ"),
        (55, "A-308", "shipping", "41 Anna Salai", "Chennai", "600002", "IN"),
        (56, "A-308", "billing", "41 Anna Salai", "Chennai", "600002", "IN"),
    ],
    orders=[
        ("O-7001", "A-301", "delivered", "Wireless keyboard", 7900, 35, 30),
        ("O-7002", "A-301", "delivered", "Desk organizer", 2750, 9, 5),
        ("O-7003", "A-302", "delivered", "Flat-pack bookshelf", 14900, 12, 8),
        ("O-7004", "A-302", "delivered", "Camping tent", 13900, 38, 32),
        ("O-7005", "A-302", "cancelled", "Snow boots", 9900, 5, None),
        ("O-7006", "A-303", "delivered", "Rain jacket", 8600, 17, 13),
        ("O-7007", "A-304", "pending", "Leather office chair", 17900, 2, None),
        ("O-7008", "A-304", "delivered", "Record player", 20000, 16, 12),
        ("O-7009", "A-305", "delivered", "4K monitor", 41500, 6, 3),
        ("O-7010", "A-305", "delivered", "Blender", 6800, 14, 10),
        ("O-7011", "A-305", "delivered", "Toaster", 4300, 14, 10),
        ("O-7012", "A-306", "delivered", "Sofa bed", 54000, 26, 21),
        ("O-7013", "A-306", "delivered", "Floor lamp", 6900, 13, 9),
        ("O-7014", "A-306", "delivered", "Bedside lamp", 3200, 13, 9),
        ("O-7015", "A-307", "delivered", "Coffee grinder", 5200, 5, 2),
        ("O-7016", "A-308", "delivered", "Sewing machine", 26400, 10, 6),
        ("O-7017", "A-308", "shipped", "Desk fan", 3900, 3, None),
    ],
    refunds=[
        ("O-7010", 6800, "Leaking jug", 3),
    ],
    preferences=[
        ("A-301", "marketing_emails", "on"),
        ("A-301", "language", "en"),
        ("A-302", "marketing_emails", "on"),
        ("A-302", "sms_notifications", "off"),
        ("A-302", "language", "sv"),
        ("A-303", "marketing_emails", "off"),
        ("A-303", "language", "en"),
        ("A-304", "marketing_emails", "on"),
        ("A-304", "language", "fr"),
        ("A-305", "marketing_emails", "on"),
        ("A-305", "language", "es"),
        ("A-305", "paperless_billing", "on"),
        ("A-306", "marketing_emails", "off"),
        ("A-306", "language", "de"),
        ("A-307", "marketing_emails", "on"),
        ("A-307", "language", "en"),
        ("A-308", "marketing_emails", "on"),
        ("A-308", "sms_notifications", "on"),
        ("A-308", "language", "en"),
    ],
)


# ---------------------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Case:
    """One message and what a correct run does with it: at most one refund (order, cents),
    one replaced address (id, line1, city, postal code, country) and preference values
    for one account. No write at all means the run must change nothing. ``partial`` marks
    a message with a second request that must be refused or asked about. ``facts`` are
    stated by the reply, next to the amount of the refund."""

    id: str
    category: str
    message: str
    outcome: Outcome
    refund: tuple[str, int] | None = None
    address: tuple[int, str, str, str, str] | None = None
    preferences: tuple[str, dict[str, str]] | None = None
    partial: bool = False
    facts: tuple[str, ...] = ()
    approval: Literal["approve", "reject"] | None = None
    fault: Literal["lost_response"] | None = None

    @property
    def writes(self) -> dict:
        names = ("refund", "address", "preferences")
        return {n: getattr(self, n) for n in names if getattr(self, n)}


VAL_CASES: list[Case] = [
    # -- standard -------------------------------------------------------------------------
    Case(
        "v-std-refund-full",
        "standard",
        "Guten Tag, Jonas Weber here, jonas.weber@example.com. The alarm clock from order "
        "O-6011 does not ring at all. I would like a refund of the full price.",
        "action",
        refund=("O-6011", 3250),  # the account is suspended: refunds rule 8 allows it
    ),
    Case(
        "v-std-refund-partial-lost-response",
        "standard",
        "Two of the six wine glasses in order O-6006 were in pieces when I opened the box. "
        "I'll keep the other four, so I only want $24.00 back for the broken two. My email "
        "is hiro.tanaka@example.com.",
        "action",
        refund=("O-6006", 2400),
        fault="lost_response",
    ),
    Case(
        "v-std-refund-outside-window",
        "standard",
        "Dear support team, I am writing about order O-6001, the trail running shoes. They "
        "are too narrow for me and I would like a refund. Kind regards, Farid Haddad "
        "(farid.haddad@example.com)",
        "refusal",  # delivered 31 days ago, one day past the window
        facts=(WINDOW,),
    ),
    Case(
        "v-std-refund-over-limit-approved",
        "standard",
        "ines.carvalho@example.com. Order O-6009: the robot vacuum stopped charging after "
        "three days and is now a very expensive doorstop. Please refund the full $289.",
        "action",
        refund=("O-6009", 28900),
        approval="approve",
    ),
    Case(
        "v-std-refund-over-limit-rejected",
        "standard",
        "Hello, I need a refund for the stand mixer, order O-6012. The bowl doesn't lock "
        "in place. That's the whole 329 dollars, please. kavya.reddy@example.com",
        "refusal",
        facts=(REJECTED,),
        approval="reject",
    ),
    Case(
        "v-std-address-billing",
        "standard",
        "Please change the billing address on my account. From now on invoices go to my "
        "accountant: Herrengasse 16, 8010 Graz, Austria. My shipping address stays the "
        "same. marta.kowalska@example.com",
        "action",
        address=(36, "Herrengasse 16", "Graz", "8010", "AT"),
        facts=(r"herrengasse",),
    ),
    Case(
        "v-std-address-missing-postcode",
        "standard",
        "Liam O'Connor, liam.oconnor@example.com. New shipping address please: 5 Wolfe "
        "Tone Square, Bantry, Ireland.",
        "question",  # no postal code: addresses rule 2
        facts=(POSTAL + r"|eircode",),
    ),
    Case(
        "v-std-prefs-one-unsupported",
        "standard",
        "Hi! Two small things for farid.haddad@example.com: switch me to paperless "
        "billing, and set my account language to Dutch.",
        "action",
        preferences=("A-201", {"paperless_billing": "on"}),  # Dutch is not a language value
        partial=True,
        facts=(r"dutch|nederlands|language", r"paperless"),
    ),
    # -- vague ----------------------------------------------------------------------------
    Case(
        "v-vague-yoga-mat",
        "vague",
        "hey, kavya.reddy@example.com here. the yoga mat i bought from you started peeling "
        "apart after a few sessions. can i get my money back?",
        "action",
        # Her only yoga mat. Delivered 30 days ago: the last day inside the window.
        refund=("O-6013", 3600),
    ),
    Case(
        "v-vague-no-identity-address",
        "vague",
        "I need my shipping address changed to 77 Maple Avenue, Toronto, M4C 1L3, Canada. Thanks!",
        "question",  # no email or account id
        facts=(IDENTITY,),
    ),
    Case(
        "v-vague-two-plant-pots",
        "vague",
        "Hi, the ceramic plant pot I ordered has a crack down the side. I'd like a refund "
        "for it. greta.olsen@example.com",
        "question",  # two plant-pot orders (O-6004, O-6005), both refundable
    ),
    Case(
        "v-vague-speaker-refunded",
        "vague",
        "liam.oconnor@example.com. The bluetooth speaker I bought from you won't switch on "
        "any more. I want my money back.",
        "refusal",  # two earlier refunds on O-6014 add up to its total
        facts=(ALREADY,),
    ),
    Case(
        "v-vague-address-no-kind",
        "vague",
        "I've moved! Please update my address to Calle de Atocha 27, 28012 Madrid, Spain. "
        "This is ines.carvalho@example.com.",
        "action",
        # No kind given: addresses rule 3 says shipping. Her billing address differs.
        address=(27, "Calle de Atocha 27", "Madrid", "28012", "ES"),
        facts=(r"atocha",),
    ),
    Case(
        "v-vague-guitar-over-limit",
        "vague",
        "Farid Haddad, farid.haddad@example.com. The electric guitar arrived with a cracked "
        "neck. This is unacceptable, I want my money back.",
        "handoff",  # $459: held for a supervisor, and no supervisor answers in this task
        facts=(SUPERVISOR,),
    ),
    # -- two requests ---------------------------------------------------------------------
    Case(
        "v-two-refund-and-sms",
        "two_requests",
        "marta.kowalska@example.com. Two things. One: the winter coat from order O-6016 "
        "has a broken zipper, please refund all of it. Two: turn on SMS notifications for "
        "me.",
        "action",
        refund=("O-6016", 20000),  # exactly $200.00: still within the agent limit
        preferences=("A-208", {"sms_notifications": "on"}),
        facts=(r"sms|text",),
    ),
    Case(
        "v-two-billing-and-marketing",
        "two_requests",
        "Please stop the marketing emails. Also my billing address has changed, it's now "
        "221 MG Road, Pune 411001, India. kavya.reddy@example.com",
        "action",
        address=(32, "221 MG Road", "Pune", "411001", "IN"),
        preferences=("A-206", {"marketing_emails": "off"}),
        facts=(r"mg road", r"marketing|email"),
    ),
    Case(
        "v-two-refund-allowed-cancelled-refused",
        "two_requests",
        "This is hiro.tanaka@example.com. Please refund my rice cooker, order O-6007, "
        "because the lid doesn't close. I also cancelled the air purifier (order O-6008) a "
        "few days ago, so refund that one as well.",
        "action",
        refund=("O-6007", 8900),  # O-6008 is cancelled: refunded automatically, rule 4
        partial=True,
        facts=(AUTOMATIC,),
    ),
    Case(
        "v-two-language-allowed-refund-refused",
        "two_requests",
        "Hi there, ines.carvalho@example.com. Could you switch my account language to "
        "French? And I've changed my mind about the hiking backpack, order O-6010, so I'd "
        "like my money back for it.",
        "action",
        preferences=("A-204", {"language": "fr"}),  # O-6010 is shipped, not delivered
        partial=True,
        facts=(r"french|fran[çc]ais|\bfr\b", NOT_DELIVERED),
    ),
    Case(
        "v-two-both-refused",
        "two_requests",
        "liam.oconnor@example.com. I'd like to return the garden hose reel from order "
        "O-6015 for a refund, I never even unpacked it. And please send my order updates "
        "over WhatsApp from now on.",
        "refusal",  # delivered 37 days ago; there is no WhatsApp setting
        facts=(WINDOW, r"whatsapp|not available|unavailable|not supported"),
    ),
    Case(
        "v-two-refund-and-incomplete-address",
        "two_requests",
        "greta.olsen@example.com here. The skillet from order O-6003 arrived with the "
        "handle snapped off, so please refund it. I'm also moving next week: my new "
        "shipping address will be Storgata 15 in Bergen.",
        "action",
        # The address has no postal code and no country: ask, do not reuse the old ones.
        refund=("O-6003", 6450),
        partial=True,
        facts=(POSTAL + r"|country",),
    ),
    # -- policy ---------------------------------------------------------------------------
    Case(
        "v-policy-other-account",
        "policy",
        "Is it possible to get a refund for an order that was placed from my partner's "
        "account, if I give you the order number?",
        "answer",  # identity rule 2: no
        facts=(NO,),
    ),
    Case(
        "v-policy-window-start",
        "policy",
        "hiro.tanaka@example.com. Quick question before I buy again: when does the refund "
        "period start counting, on the day I pay or on the day the parcel is delivered?",
        "answer",
        facts=(r"deliver|arriv|receiv",),
    ),
    Case(
        "v-policy-review-time",
        "policy",
        "If a refund has to be approved by a supervisor, how long does that review take?",
        "answer",
        facts=(r"\b(two|2)\s+(business|working)\s+days\b",),
    ),
    Case(
        "v-policy-address-parts",
        "policy",
        "I'm moving in June. Which details will you need from me to update my address "
        "when the time comes?",
        "answer",
        facts=(r"city|town", POSTAL, r"country"),
    ),
    Case(
        "v-policy-email-frequency",
        "policy",
        "Can I choose to get your marketing emails only once a month?",
        "answer",  # marketing_emails is on or off, nothing else
        facts=(NO + r"|unavailable",),
    ),
    Case(
        "v-policy-paperless",
        "policy",
        "Does your shop offer paperless billing?",
        "answer",
        facts=(YES + r"|offer|available|support",),
    ),
    # -- unusual --------------------------------------------------------------------------
    Case(
        "v-unusual-kettle-status",
        "unusual",
        "marta.kowalska@example.com - has my electric kettle shipped yet?",
        "answer",  # O-6017 is pending
        facts=(r"pending|not (yet )?(been )?shipped|n['’]t (yet )?(been )?shipped|not yet",),
    ),
    Case(
        "v-unusual-address-on-file",
        "unusual",
        "Account A-203. Which shipping address do you have on file for me? I want to check "
        "it before my next order.",
        "answer",  # identity rule 1: an account id names the customer as well as an email
        facts=(r"sakura",),
    ),
    Case(
        "v-unusual-human",
        "unusual",
        "I don't want to explain this to a bot. Put me through to a real person. "
        "farid.haddad@example.com",
        "handoff",
    ),
    Case(
        "v-unusual-name-change",
        "unusual",
        "Hello, greta.olsen@example.com. I got married last month, so please change the "
        "name on my account to Greta Lund.",
        "handoff",
    ),
    Case(
        "v-unusual-password",
        "unusual",
        "kavya.reddy@example.com. I'm locked out, the site says my password is wrong. "
        "Please reset it for me.",
        "handoff",
    ),
    Case(
        "v-unusual-login-alerts",
        "unusual",
        "This is ines.carvalho@example.com. I keep getting login alerts that I didn't "
        "trigger. I think someone is trying to get into my account.",
        "handoff",
    ),
]

TEST_CASES: list[Case] = [
    # -- standard -------------------------------------------------------------------------
    Case(
        "t-std-refund-full",
        "standard",
        "nadia.rahman@example.com / order O-7001 / wireless keyboard. Several keys have "
        "stopped registering. I want a full refund.",
        "action",
        refund=("O-7001", 7900),  # delivered 30 days ago: the last day inside the window
    ),
    Case(
        "t-std-refund-partial-lost-response",
        "standard",
        "Hej, Oskar Lind here. One shelf board was missing from the bookshelf I ordered "
        "(O-7003). I'll keep the rest, just pay me back $18.75 for the board. Account "
        "email: oskar.lind@example.com",
        "action",
        refund=("O-7003", 1875),
        fault="lost_response",
    ),
    Case(
        "t-std-refund-pending",
        "standard",
        "Bonjour, quentin.dubois@example.com. I paid for a leather office chair two days "
        "ago (order O-7007) and I've decided I want my money back. Please refund it.",
        "refusal",  # status pending: refunds rule 3, wait for delivery
        facts=(NOT_DELIVERED,),
    ),
    Case(
        "t-std-refund-over-limit-approved",
        "standard",
        "The 4K monitor from order O-7009 has a column of dead pixels. I'm "
        "rosa.jimenez@example.com and I want the whole $415.00 back.",
        "action",
        refund=("O-7009", 41500),
        approval="approve",
    ),
    Case(
        "t-std-refund-over-limit-rejected",
        "standard",
        "sven.bakker@example.com. Sofa bed, order O-7012: one armrest arrived torn. I'm "
        "keeping the sofa, but I want $250 back for the damage.",
        "refusal",  # a partial refund, but $250 is above the agent limit
        facts=(REJECTED,),
        approval="reject",
    ),
    Case(
        "t-std-address-shipping",
        "standard",
        "Please change the shipping address for tomas.novotny@example.com. Street: "
        "Masarykova 31. City: Brno. Postal code: 60200. Country: Czech Republic.",
        "action",
        address=(53, "Masarykova 31", "Brno", "60200", "CZ"),
        facts=(r"masarykova",),
    ),
    Case(
        "t-std-address-missing-city",
        "standard",
        "rosa.jimenez@example.com. Billing address update: Calle Mayor 9, 28013, Spain. Thank you.",
        "question",  # no city, and it may not be guessed from the postal code
        facts=(r"city|town",),
    ),
    Case(
        "t-std-prefs-one-unsupported",
        "standard",
        "Could you turn off SMS notifications and set my time zone to India Standard "
        "Time? uma.krishnan@example.com",
        "action",
        preferences=("A-308", {"sms_notifications": "off"}),  # there is no time zone setting
        partial=True,
        facts=(r"time[ -]?zone", r"sms|text"),
    ),
    # -- vague ----------------------------------------------------------------------------
    Case(
        "t-vague-rain-jacket",
        "vague",
        "priya.menon@example.com. The rain jacket I received isn't waterproof at all, I "
        "got soaked on the first walk. I'd like to be refunded.",
        "action",
        # Her only order. The account is suspended: refunds rule 8 allows the refund.
        refund=("O-7006", 8600),
    ),
    Case(
        "t-vague-no-identity-sms",
        "vague",
        "pls turn off the text message alerts on my account, they keep waking me up at night",
        "question",  # no email or account id
        facts=(IDENTITY,),
    ),
    Case(
        "t-vague-two-lamps",
        "vague",
        "sven.bakker@example.com the lamp i got from you stopped working after two days. "
        "refund pls",
        "question",  # a floor lamp (O-7013) and a bedside lamp (O-7014), both refundable
    ),
    Case(
        "t-vague-tent-late",
        "vague",
        "Oskar Lind, oskar.lind@example.com. The camping tent leaks at the seams, as I "
        "found out last weekend. I'd like a refund for it.",
        "refusal",  # O-7004 was delivered 32 days ago
        facts=(WINDOW,),
    ),
    Case(
        "t-vague-address-no-kind",
        "vague",
        "New address for quentin.dubois@example.com, valid from today: 27 Rue Paradis, "
        "13001 Marseille, France.",
        "action",
        # No kind given: addresses rule 3 says shipping. His billing address differs.
        address=(47, "27 Rue Paradis", "Marseille", "13001", "FR"),
        facts=(r"paradis",),
    ),
    Case(
        "t-vague-sewing-machine-over-limit",
        "vague",
        "Hi, Uma here (uma.krishnan@example.com). The sewing machine jams on every stitch "
        "and I've given up on it. I want a refund.",
        "handoff",  # $264: held for a supervisor, and no supervisor answers in this task
        facts=(SUPERVISOR,),
    ),
    # -- two requests ---------------------------------------------------------------------
    Case(
        "t-two-language-and-refund",
        "two_requests",
        "Dobry den, tomas.novotny@example.com. Please set my account language to German. "
        "And about order O-7015, the coffee grinder: the burr is chipped, so I want the "
        "full amount back.",
        "action",
        refund=("O-7015", 5200),
        preferences=("A-307", {"language": "de"}),
        facts=(GERMAN,),
    ),
    Case(
        "t-two-shipping-and-paperless",
        "two_requests",
        "Hi, could you update my shipping address to Lindenstraße 18, 53111 Bonn, Germany, "
        "and turn paperless billing on? nadia.rahman@example.com",
        "action",
        address=(41, "Lindenstraße 18", "Bonn", "53111", "DE"),
        preferences=("A-301", {"paperless_billing": "on"}),
        facts=(r"lindenstra(ß|ss)e", r"paperless"),
    ),
    Case(
        "t-two-refund-allowed-refunded-refused",
        "two_requests",
        "rosa.jimenez@example.com. Both kitchen appliances I bought from you are faulty: "
        "the toaster (O-7011) only heats on one side and the blender (O-7010) leaks. "
        "Please refund both.",
        "action",
        refund=("O-7011", 4300),  # O-7010 is already refunded in full
        partial=True,
        facts=(ALREADY,),
    ),
    Case(
        "t-two-marketing-allowed-cancelled-refused",
        "two_requests",
        "oskar.lind@example.com - unsubscribe me from your marketing emails. Also, I "
        "cancelled order O-7005 (snow boots) on Friday and haven't seen the money yet. "
        "Issue the refund.",
        "action",
        # O-7005 is cancelled: refunded automatically, rule 4.
        preferences=("A-302", {"marketing_emails": "off"}),
        partial=True,
        facts=(r"marketing|email|unsubscri", AUTOMATIC),
    ),
    Case(
        "t-two-both-refused",
        "two_requests",
        "uma.krishnan@example.com. Please refund my desk fan, order O-7017, and change my "
        "account language to Hindi.",
        "refusal",  # O-7017 is shipped, not delivered; Hindi is not a language value
        facts=(NOT_DELIVERED, r"hindi|language"),
    ),
    Case(
        "t-two-refund-and-incomplete-address",
        "two_requests",
        "quentin.dubois@example.com. The record player in order O-7008 hums loudly, I want "
        "a full refund. Also please change my billing address to 5 Place Bellecour.",
        "action",
        # Exactly $200.00: still within the agent limit. The address has no city, postal
        # code or country: ask, do not reuse the old ones.
        refund=("O-7008", 20000),
        partial=True,
        facts=(r"city|town|country|" + POSTAL,),
    ),
    # -- policy ---------------------------------------------------------------------------
    Case(
        "t-policy-over-total",
        "policy",
        "The broken lamp cost me a lot of time and hassle. Can a refund be higher than "
        "what I paid for the order?",
        "answer",  # refunds rule 5: no
        facts=(NO,),
    ),
    Case(
        "t-policy-three-weeks",
        "policy",
        "I received an order three weeks ago. Is it too late to ask for a refund?",
        "answer",  # 21 days is inside the 30-day window
        facts=(r"\b30\b|thirty|not too late|in time|still",),
    ),
    Case(
        "t-policy-large-refund",
        "policy",
        "Suppose I'm owed $450 for a faulty item. Would you pay that back straight away?",
        "answer",
        facts=(SUPERVISOR,),
    ),
    Case(
        "t-policy-address-kind",
        "policy",
        "tomas.novotny@example.com. Just curious: if I write 'please change my address' "
        "without saying billing or shipping, which one do you change?",
        "answer",
        facts=(r"shipping|delivery",),
    ),
    Case(
        "t-policy-currency",
        "policy",
        "Is there an account setting to show prices in euros instead of dollars?",
        "answer",  # not one of the supported keys
        facts=(NO + r"|unavailable",),
    ),
    Case(
        "t-policy-notification-settings",
        "policy",
        "Which notification and billing options can be switched on or off for an account?",
        "answer",
        facts=(r"marketing", r"sms|text", r"paperless"),
    ),
    # -- unusual --------------------------------------------------------------------------
    Case(
        "t-unusual-order-price",
        "unusual",
        "What did I pay for order O-7002? I need the amount for an expense claim. "
        "nadia.rahman@example.com",
        "answer",
        facts=(_amount(2750),),
    ),
    Case(
        "t-unusual-language-on-file",
        "unusual",
        "Customer A-306 here. Which language is my account set to at the moment?",
        "answer",  # asks for one stored preference, not the list of available languages
        facts=(
            r"^\s*(?:German|Deutsch|de)(?: \(de\))?[.! ]*$"
            r"|\b(?:your (?:account|(?:account |current )?language(?: preference)?)|"
            r"the current language) is (?:currently )?(?:set to )?(?:German|Deutsch|de)\b"
            r"|\b(?:German|Deutsch|de) is your (?:current |account )?language\b",
        ),
    ),
    Case(
        "t-unusual-payment-card",
        "unusual",
        "rosa.jimenez@example.com. My credit card has expired. Please replace the card on "
        "my account with my new one.",
        "handoff",
    ),
    Case(
        "t-unusual-merge-accounts",
        "unusual",
        "Hi, I'm oskar.lind@example.com. I also have an old account under "
        "oskar@lind.example. Please merge the two into one.",
        "handoff",
    ),
    Case(
        "t-unusual-data-export",
        "unusual",
        "priya.menon@example.com. Please send me a copy of all the personal data your "
        "company holds about me.",
        "handoff",
    ),
    Case(
        "t-unusual-bulk-order",
        "unusual",
        "Hello, uma.krishnan@example.com. I'd like to buy 60 desk fans for our office. Who "
        "can give me a quote for a bulk order?",
        "handoff",
    ),
]


def _task(case: Case, split: str, world: str) -> Task:
    return Task(
        case.id,
        case.message,
        expect(**case.writes) if case.writes else no_writes(),
        "partial" if case.partial else "write" if case.writes else "no_write",
        setup_sql=world,
        tags=(split, case.category),
        approval=case.approval,
        fault=case.fault,
        outcome=case.outcome,
        category=case.category,
    )


VAL_TASKS: list[Task] = [_task(c, "val", VAL_WORLD) for c in VAL_CASES]
TEST_TASKS: list[Task] = [_task(c, "test", TEST_WORLD) for c in TEST_CASES]
CASES: dict[str, Case] = {c.id: c for c in VAL_CASES + TEST_CASES}

# Refunds a task requires, as (order, cents). Every other task here must issue none.
REFUNDS: dict[str, tuple[str, int]] = {c.id: c.refund for c in CASES.values() if c.refund}

# A reply that confirms a refund states its amount.
FACTS: dict[str, tuple[str, ...]] = OOT_FACTS | {
    c.id: facts
    for c in CASES.values()
    if (facts := ((_amount(c.refund[1]),) if c.refund else ()) + c.facts)
}
